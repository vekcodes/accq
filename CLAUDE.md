# accq: sourcing old Dutch businesses for acquisition outreach

Brief: `Project brief_ sourcing old Dutch businesses for acquisition outreach.md` (draft, 7 Oct 2026).
Goal: per market, one command produces a ranked top-50 shortlist, a dossier per company and
draft letters. **A person approves everything. Nothing is ever sent automatically.**

## Commands
- `uv run accq run installation_overijssel` — full pipeline (stages 01-07)
- `uv run accq run <market> --from 3 --to 5` — part of the pipeline
- `uv run accq eval` — score the succession classifier against `evals/succession_testset.jsonl`
- `uv run pytest`

## Layout
- `markets/<market>.yaml` — one config per market (filters, weights, letter sender)
- `pipeline/NN_*.py` — numbered stages, each exposes `run(ctx)`; state lives in `runs/<market>/<market>.duckdb`
- `skills/` — prompts for the succession classifier and website signals, evaluated separately
- `cache/` — every HTTP fetch is cached; no source is hit twice for the same URL
- `data/extra/<market>/*.csv` — drop-in extra universe sources (Clay, association lists, ...)

## Data handling (AVG / GDPR) — applies to every message you generate
- Store business contact details and derived signals only. No LinkedIn profile dumps,
  no birth dates outside the optional KVK extract step.
- Respect `markets/<market>.suppression.csv` (column `name` or `kvk_number`). Suppressed
  companies never get a dossier or letter.
- Letters are the default channel. Email and phone only for a BV/NV (with opt-out).
  Eenmanszaak, VOF and unknown legal forms are treated as natural persons: no email
  without prior consent (Telecommunicatiewet art. 11.7), no calls without opt-in.
- Every letter says where we got the contact details and how to opt out.
- Unknown legal form is treated as the strict case.

## Honesty rules
- Never invent a founding year, headcount or owner age. Unknown stays unknown and is shown as such.
- Wayback first-capture is a *lower bound on domain age*, not a founding date; it is labelled as such.
- Synthetic test data is labelled synthetic.
