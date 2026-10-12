"""Stage 5: hard filters, weighted score, rank. Suppressed companies are removed here."""
from __future__ import annotations

import csv
from datetime import date

from accq.core import Ctx, ROOT, norm_name
from accq.scoring import hard_filter, score

TIER_ORDER = {"qualified": 0, "needs_check": 1}


def load_suppression(market: str) -> tuple[set[str], set[str]]:
    path = ROOT / "markets" / f"{market}.suppression.csv"
    names, kvks = set(), set()
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if r.get("name"):
                    names.add(norm_name(r["name"]))
                if r.get("kvk_number"):
                    kvks.add(r["kvk_number"].strip())
    return names, kvks


def run(ctx: Ctx) -> None:
    cur = ctx.con.execute("""SELECT c.*, k.owner_active, k.successor_named, k.new_hires, k.recent_ownership_change, k.owner_age_hint
                             FROM companies c LEFT JOIN classification k ON k.company_id = c.id""")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    sup_names, sup_kvks = load_suppression(ctx.market)
    cfg_f, cfg_w = ctx.cfg["filters"], ctx.cfg["weights"]
    ctx.con.execute("DELETE FROM scores")
    out = []
    for r in rows:
        if r["norm_name"] in sup_names or (r["kvk_number"] and r["kvk_number"] in sup_kvks):
            continue  # suppressed: no score, dossier or letter
        tier, notes = hard_filter(r, cfg_f)
        cls = {k: r[k] for k in ("owner_active", "successor_named", "new_hires", "recent_ownership_change", "owner_age_hint")} if r["owner_active"] else None
        s, reasons = score(r, cls, cfg_w, date.today())
        out.append((r["id"], tier, s, reasons + [f"[{n}]" for n in notes]))
    ranked = sorted((o for o in out if o[1] in TIER_ORDER), key=lambda o: (TIER_ORDER[o[1]], -o[2]))
    rank_of = {o[0]: i for i, o in enumerate(ranked, 1)}
    for cid, tier, s, reasons in out:
        ctx.con.execute("INSERT INTO scores VALUES (?,?,?,?,?)", [cid, tier, s, rank_of.get(cid), "; ".join(reasons)])
    n = {t: sum(1 for o in out if o[1] == t) for t in ("qualified", "needs_check", "excluded")}
    ctx.log(f"score: {n['qualified']} qualified, {n['needs_check']} needs-check (unknowns), {n['excluded']} excluded, {len(rows)-len(out)} suppressed")
