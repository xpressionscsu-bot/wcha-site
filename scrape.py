#!/usr/bin/env python3
"""Refresh data.json from each WCHA school's official women's hockey stats page.

Usage:
    pip install requests beautifulsoup4
    python scrape.py

Each school runs a Sidearm Sports site with the same stats layout, so one parser
covers all eight. Edit the `url` fields in data.json if a school uses a different path.
"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA = Path(__file__).with_name("data.json")
HEADERS = {"User-Agent": "wcha-stats-site/1.0 (personal project; polite 1 req/sec)"}


def norm(h: str) -> str:
    h = h.strip().lower().replace("+/-", "plus_minus").replace("%", "_pct")
    return re.sub(r"[^a-z0-9_]+", "_", h).strip("_")


def num(s: str):
    s = s.strip().replace(",", "")
    if s in ("", "-", "--"):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def flip_name(cell: str) -> str:
    # "Sauriol, Alice" -> "Alice Sauriol"
    if "," in cell:
        last, first = [p.strip() for p in cell.split(",", 1)]
        return f"{first} {last}"
    return cell.strip()


def parse_table(table):
    rows = table.find_all("tr")
    if not rows:
        return None, []
    headers = [norm(c.get_text(" ")) for c in rows[0].find_all(["th", "td"])]
    out = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) != len(headers):
            continue
        rec = dict(zip(headers, cells))
        who = rec.get("player", "")
        if not who or who.lower() in ("total", "opponents", "opponent"):
            continue
        row = {k: num(v) for k, v in rec.items() if k not in ("player", "")}
        row["name"] = flip_name(who)
        if "#" in rec:
            row["num"] = num(rec["#"])
        row.pop("#", None)
        if "pn_pim" in row:  # "2-4" -> penalties-minutes
            m = re.match(r"\d+-(\d+)", str(rec["pn_pim"]))
            row["pim"] = int(m.group(1)) if m else None
            row.pop("pn_pim")
        out.append(row)
    return headers, out


def scrape_team(url: str):
    html = requests.get(url, headers=HEADERS, timeout=30)
    html.raise_for_status()
    soup = BeautifulSoup(html.text, "html.parser")
    skaters, goalies = [], []
    for t in soup.find_all("table"):
        headers, rows = parse_table(t)
        if not headers or "player" not in headers:
            continue
        if "gaa" in headers or "sv_pct" in headers:
            goalies = rows
        elif "pts" in headers and not skaters:
            skaters = rows  # first match = overall; later tables are conference splits
    record = None
    m = re.search(r"Team Stats\s*\((\d+-\d+(?:-\d+)?),\s*(\d+-\d+(?:-\d+)?)\)", soup.get_text(" "))
    if m:
        record = {"overall": m.group(1), "conference": m.group(2)}
    return record, skaters, goalies


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for team in data["teams"]:
        try:
            record, skaters, goalies = scrape_team(team["url"])
        except Exception as e:  # keep the old data for this team if the fetch fails
            print(f"! {team['name']}: {e}", file=sys.stderr)
            continue
        if not skaters:
            print(f"! {team['name']}: no skater table found, keeping old data", file=sys.stderr)
            continue
        team.update(record=record, skaters=skaters, goalies=goalies or team.get("goalies", []))
        print(f"{team['name']}: {len(skaters)} skaters, {len(goalies)} goalies, record {record}")
        time.sleep(1)
    data["updated"] = date.today().isoformat()
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
