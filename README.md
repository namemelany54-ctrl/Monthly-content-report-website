# Creative Performance Intelligence

Interactive report for SURYA Coffee Explorers and Monster and Friends, built from Publer (workspace COFFLORER).
Status: DRAFT, local only. Nothing here writes to Publer or to the COFFLORER AI Workspace on Drive, and it is separate from the November report cycle that starts 1 Dec.

## Open it

Double-click `index.html`, or serve the folder: `python -m http.server 8765 --directory .` then open http://localhost:8765.

## Refresh with new Publer data

1. In Publer: Analytics > Post Insights > pick the range (This year) > Export CSV.
2. Save the file into `data/raw/` without renaming older files. Suggested name:
   `publer-post-insights_<from>_<to>_exported-<YYYY-MM-DDTHHMM>.csv`
3. Add one entry to `data/raw/sources.json` (copy the existing `publer_csv` entry; set `file`, `as_of` = export time in Bangkok time, `covers_from`, `covers_to`).
4. Run `python refresh.py`. It rewrites only `data/dashboard-data.js`.
5. Reload the page. The header shows the refresh time, the latest Publer read time and the latest post.

`refresh.py` uses the Python standard library only. It removes duplicates by platform + post URL, keeps missing values as missing, and when two sources describe the same post it takes each field from the source with the later `as_of`.

Keep every old raw file. They are the audit trail, and a series of snapshots is what makes age-matched comparisons (for example reach at 7 days) possible later.

### Why a manual CSV export

On 14 Nov 2026 the Publer connector's export tool returned a link to an image, not a CSV, and its post-level tool returns 10 rows per call with full captions and duplicate Instagram rows. The CSV from the Publer web app is the reliable bulk source. Connector reads are still useful for small top-ups (Saves, Post clicks, posts newer than the last CSV): put them in a JSON file shaped like `data/raw/connector-delta_*.json` and list it in `sources.json` with `"type": "supplement_json"`.

## Files

| Path | Purpose |
|---|---|
| `index.html` | The dashboard. Does not change on refresh. |
| `refresh.py` | Builds `data/dashboard-data.js` from the sources in `data/raw/sources.json`. |
| `data/raw/` | Raw source snapshots and the manifest. Read-only by convention. |
| `config/pillars.json` | Caption rules that tag each post with a content pillar. Edit, then refresh. |
| `config/insights.th.json` | The written analysis (Thai): executive points, Gemini vs Claude, data issues, recommendations, next-month plan. Not regenerated automatically; update `written_for_as_of` when you revise it. The page warns when the data is newer than this text. |
| `tools/parse_gemini_md.py` | Turns the per-post tables in Gemini's report into a supplement JSON. |

## Known limits

See the Data Quality tab. The main ones: metrics are cumulative at read time (not age-matched), the CSV has no Saves or Post clicks, TikTok "Reach" is views, pillar tags are rule-based and unreviewed, and Publer has no paid/organic, watch-time or sales data.

## v2 (combined UI, 14 Nov 2026)

This folder is a copy of `creative-performance-intelligence/` with the dark-navy single-page UI adapted from the October reference site. Same data pipeline; `refresh.py` additionally reads:

- `data/raw/account-followers_*.json` (source type `account_followers`): weekly follower counts per account, read from the Publer connector one account at a time. Shown only in the Audience section.
- `config/thumbnails.json` + `assets/thumbnails/`: cover images keyed by platform + post URL. Images only; no metrics come from the reference package.
- a `Recruitment` rule in `config/pillars.json`, used by the "exclude Recruitment" toggle.

Preview: `python -m http.server 8766 --directory .` then http://localhost:8766. Not published anywhere.
