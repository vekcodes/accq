# accq

Free-first pipeline that finds old, owner-run Dutch small businesses and prepares acquisition
outreach drafts. See `Project brief_ ...md` for the why and `CLAUDE.md` for the rules.

```
uv sync
uv run accq run installation_overijssel          # stages 1-7
uv run accq run installation_overijssel --from 4 --to 7 --backend export
uv run accq eval --backend claude-cli            # classifier vs. labelled set
uv run pytest
```

Output lands in `runs/<market>/`: `shortlist.csv`, `dossiers/*.md`, `letters/*.md`, and the DuckDB file.
**Letters are drafts. Nothing is sent. A person approves the batch.**

## Stages
| # | Script | What it does | Free source |
|---|---|---|---|
| 1 | `01_universe` | OSM + any `data/extra/<market>/*.csv`, deduped on name+place | OpenStreetMap |
| 2 | `02_match_entity` | KVK number + legal form from the company's own site | website |
| 3 | `03_enrich` | founding year, headcount, site freshness, NOW match, Wayback | website, Wayback CDX |
| 4 | `04_classify` | owner active / successor / hires / ownership change | `claude -p` (your Claude login) |
| 5 | `05_score` | hard filters, weighted score, rank, suppression list | |
| 6 | `06_dossiers` | one-page dossier + `shortlist.csv` for the human check | |
| 7 | `07_letters` | Dutch letter drafts; channels follow legal form | |

## Known limits (free stack)
- **Universe is thin.** OSM returned ~38 installers for all of Overijssel. Add more by dropping CSVs
  (columns `name,city,postcode,street,website,phone,email,source`) in `data/extra/installation_overijssel/`:
  a Clay export, an association member list (check its terms first), or a Google Places export.
- **No reviews yet.** The review-based owner-activity signal needs Google Places or a scraper.
- **Owner age is inferred**, never looked up. The optional paid KVK extract (director birth date) is out of scope.
- **NOW register is not wired to a download.** UWV publishes it per application period; convert it to
  `data/now_register.csv` (`name,city,amount`) and stage 3 will match on normalised name. TVL has no public file found.
- **Many companies will have unknown founding year/headcount.** They land in the `needs_check` tier,
  never silently in `qualified`. Set `unknown_founded: drop` in the market config for a strict list.
- **Wayback first capture is domain age, not company age**; it is shown separately and never used as the founding year.
- **Classifier eval set is synthetic** (12 items written by Claude). Replace with real labelled Dutch review/about
  threads before trusting the numbers. The skill prompts live in `skills/` and are evaluated with `accq eval`.

## New market
Copy `markets/installation_overijssel.yaml`, change `name`, `sbi`, `bbox`, `osm_filters`, `extra_dir`. Add
`markets/<name>.suppression.csv` (`name` or `kvk_number` column) for anyone who opted out.
# accq
