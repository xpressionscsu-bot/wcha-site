# WCHA Women's Hockey Stats (2026-27)

A static site driven by one `data.json` file.

- `index.html` – the viewer (Teams / Skaters / Goalies, sortable, filter by team, player search)
- `data.json` – all 8 WCHA teams and their players; this is the only file the site reads
- `scrape.py` – refreshes `data.json` from each school's official stats page

## Run it

```
pip install requests beautifulsoup4
python scrape.py            # pull current stats for all 8 teams
python -m http.server 8000  # then open http://localhost:8000
```

Re-run `scrape.py` whenever you want fresh numbers (or schedule it, e.g. a daily cron job or GitHub Action, and host the folder on GitHub Pages / Netlify).

## Notes

- Teams: Bemidji State, Minnesota, Minnesota Duluth, Minnesota State, Ohio State, St. Cloud State, St. Thomas, Wisconsin.
- Only St. Cloud State skaters are filled in as shipped; the other seven fill in on the first `scrape.py` run.
- Each team's `url` in `data.json` points at its school's `/sports/womens-ice-hockey/stats/2026-27` page. If one 404s, fix that URL.
- If a fetch fails, the scraper keeps that team's previous data instead of wiping it.
