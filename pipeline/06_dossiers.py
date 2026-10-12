"""Stage 6: one-page dossier per company in the top N, plus shortlist.csv for the human check."""
from __future__ import annotations

import csv

from accq.core import Ctx
from accq.letters import channels


def fetch_top(ctx: Ctx):
    n = ctx.cfg.get("top_n", 50)
    cur = ctx.con.execute("""SELECT s.rank, s.tier, s.score, s.reasons, c.*, k.owner_active, k.successor_named, k.new_hires,
                                    k.recent_ownership_change, k.owner_age_hint, k.rationale, k.backend
                             FROM scores s JOIN companies c ON c.id = s.company_id
                             LEFT JOIN classification k ON k.company_id = c.id
                             WHERE s.rank IS NOT NULL AND s.rank <= ? ORDER BY s.rank""", [n])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def val(x, unknown="onbekend"):
    return unknown if x in (None, "") else x


def dossier(c: dict) -> str:
    ch = channels(c["legal_form"], c["email"], c["phone"])
    yes_no = lambda b: "ja" if b else "nee / niet gevonden"
    evidence_warn = "" if c["backend"] not in (None, "no-evidence", "heuristic") else \
        f"\n> Let op: succession-oordeel is zwak ({c['backend'] or 'niet geclassificeerd'}). Controleer handmatig.\n"
    return f"""# {c['name']}
Rang {c['rank']} · tier **{c['tier']}** · score {c['score']:.1f}
{evidence_warn}
## Gegevens
- Plaats: {val(c['city'])} · adres: {val(c['street'])}, {val(c['postcode'], '')}
- Website: {val(c['website'])} · telefoon: {val(c['phone'])} · e-mail: {val(c['email'])}
- KVK: {val(c['kvk_number'])} · rechtsvorm: {val(c['legal_form'])} ({val(c['legal_form_basis'], 'bron onbekend')})
- Bronnen in universum: {c['sources']} ({c['source_count']})

## Leeftijd en omvang
- Oprichtingsjaar: {val(c['founded_year'])} ({val(c['founded_basis'], 'geen bewijs gevonden')})
- Eerste Wayback-capture van het domein: {val(c['wayback_first_year'])} (ondergrens voor domeinleeftijd, geen oprichtingsjaar)
- Medewerkers: {val(c['employees'])} ({val(c['employees_basis'], 'niet gevonden')})
- NOW ontvangen: {yes_no(c['now_received'])}
- Website laatst gedateerd: {val(c['website_last_year'])}

## Opvolging (classifier: {val(c['backend'], 'niet uitgevoerd')})
- Eigenaar actief: {val(c['owner_active'])} · opvolger genoemd: {val(c['successor_named'])} · nieuwe aanwas: {val(c['new_hires'])}
- Recente eigendomswijziging: {val(c['recent_ownership_change'])} · leeftijd eigenaar: {val(c['owner_age_hint'])}
- Onderbouwing: {val(c['rationale'], '-')}
- Signalen op site/pers: {val(c['press_text'], '-')}

## Waarom deze score
{chr(10).join('- ' + r for r in (c['reasons'] or '').split('; ') if r) or '- geen signalen'}

## Contactkanalen
{ch['note']}
- Brief: ja · e-mail: {'ja' if ch['email'] else 'nee'} · bellen: {'ja' if ch['phone'] else 'nee'}

## Goedkeuring
[ ] gelezen en akkoord voor brief     Beoordelaar: ________   Datum: ________
"""


def run(ctx: Ctx) -> None:
    out = ctx.run_dir / "dossiers"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    top = fetch_top(ctx)
    for c in top:
        slug = "".join(ch if ch.isalnum() else "-" for ch in c["name"].lower()).strip("-")[:40]
        (out / f"{c['rank']:02d}-{slug}.md").write_text(dossier(c), encoding="utf-8")
    with (ctx.run_dir / "shortlist.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "tier", "score", "name", "city", "website", "legal_form", "founded_year", "employees", "kvk_number", "reasons"])
        for c in top:
            w.writerow([c["rank"], c["tier"], f"{c['score']:.1f}", c["name"], c["city"], c["website"], c["legal_form"],
                        c["founded_year"], c["employees"], c["kvk_number"], c["reasons"]])
    ctx.log(f"dossiers: {len(top)} written to {out.relative_to(ctx.run_dir.parent.parent)}; shortlist.csv ready for the human check")
