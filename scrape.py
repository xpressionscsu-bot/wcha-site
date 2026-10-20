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
    # header row = first row that has a "Player" column (some sites put a caption row first)
    hi = next((i for i, tr in enumerate(rows)
               if "player" in [norm(c.get_text(" ")) for c in tr.find_all(["th", "td"])]), 0)
    headers = [norm(c.get_text(" ")) for c in rows[hi].find_all(["th", "td"])]
    out = []
    for tr in rows[hi + 1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 4:
            continue
        rec = dict(zip(headers, cells))  # tolerate extra/missing trailing cells
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
        # goalie columns vary by school: GP-GS / AVG / SHO -> gp / gaa / so
        if "gp_gs" in row:
            m = re.match(r"(\d+)", str(rec.get("gp_gs", "")))
            row["gp"] = int(m.group(1)) if m else None
            row.pop("gp_gs")
        if "avg" in row:
            row["gaa"] = row.pop("avg")
        if "sho" in row:
            row["so"] = row.pop("sho")
        row.pop("bio_link", None)
        out.append(row)
    return headers, out


def scrape_team(url: str):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    print(f"  GET {url} -> {resp.status_code}, {len(resp.text)} bytes")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    skaters, goalies = [], []
    seen = []
    for t in soup.find_all("table"):
        headers, rows = parse_table(t)
        if not headers or "player" not in headers:
            continue
        seen.append((headers[:8], len(rows)))
        is_goalie = bool({"gaa", "avg", "sv_pct", "gp_gs"} & set(headers))
        if is_goalie:
            if not goalies:  # first goalie table = overall; later ones are conference splits
                goalies = rows
        elif "pts" in headers and not skaters:
            skaters = rows  # first match = overall; later tables are conference splits
    if not skaters:
        print(f"  tables with a Player column: {seen or 'none (page may load stats with JavaScript)'}")
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
