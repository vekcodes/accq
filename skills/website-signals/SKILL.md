---
name: website-signals
description: Extract founding year, headcount and freshness signals from a Dutch company website. The deterministic extractors live in accq/signals.py; this prompt is for the cases they miss.
---

Given the text of a Dutch company website, return ONLY JSON:

- `founded_year`: integer or null. Only if the text states when the company started
  ("sinds 1978", "opgericht in 1985", "anno 1969"). A copyright year is NOT a founding year.
  "40 jaar ervaring" describes experience, not the founding year: return null and put it in `notes`.
- `employees`: integer or null. Only an explicit statement ("12 medewerkers"). Count of
  photos on a team page is acceptable only if each person is named; say so in `notes`.
- `family_business`: true/false.
- `founder_named`: the name of the founder/owner if clearly stated, else null.
- `notes`: one short sentence.

Prefer null over a guess. Skills in this folder are evaluated separately from the pipeline.
