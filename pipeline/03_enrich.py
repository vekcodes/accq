"""Stage 3: enrich every company. Founding year, headcount, website freshness, NOW, text for the classifier.

Founding year priority: explicit statement on the site (sinds / opgericht) beats a
"N jaar ervaring" estimate beats nothing. Wayback first capture is stored separately as
wayback_first_year (a lower bound on domain age) and never used as the founding year.
"""
from __future__ import annotations

import csv
from pathlib import Path

from accq.core import Ctx, ROOT, norm_city, norm_name
from accq.signals import (founding_year, headcount, hiring_mentions, is_family_business,
                          last_year_mentioned, split_weak, succession_hints)
from accq.web import site_pages, wayback_first_year

MAX_ABOUT_CHARS = 6000


def load_now(ctx: Ctx) -> set[str]:
    path = ROOT / ctx.cfg["universe"].get("now_register", "data/now_register.csv")
    if not path.exists():
        ctx.log(f"NOW register not found at {path.relative_to(ROOT)}; now_received stays false (see README)")
        return set()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return {norm_name(r.get("name", "")) for r in csv.DictReader(fh) if r.get("name")}


def run(ctx: Ctx) -> None:
    now = load_now(ctx)
    rows = ctx.con.execute("SELECT id, name, norm_name, website FROM companies").fetchall()
    stats = dict(founded=0, staff=0, wayback=0)
    for cid, name, nname, website in rows:
        pages = site_pages(ctx, website)
        text = " ".join(pages.values())
        fy, basis = split_weak(*founding_year(text))
        if fy and is_family_business(text) and basis:
            basis += "+familiebedrijf"
        n, nbasis = headcount(text)
        wb = wayback_first_year(ctx, website)
        about = text[:MAX_ABOUT_CHARS]
        hints = succession_hints(text)
        press = " | ".join(hints)
        if hiring_mentions(text):
            press = ("[site noemt vacatures] " + press).strip()
        ctx.con.execute(
            """UPDATE companies SET founded_year=?, founded_basis=?, wayback_first_year=?, employees=?, employees_basis=?,
               now_received=?, website_last_year=?, about_text=?, press_text=? WHERE id=?""",
            [fy, basis, wb, n, nbasis, nname in now, last_year_mentioned(text), about, press, cid])
        stats["founded"] += bool(fy); stats["staff"] += bool(n); stats["wayback"] += bool(wb)
    ctx.log(f"enrich: founding year {stats['founded']}/{len(rows)}, headcount {stats['staff']}/{len(rows)}, wayback {stats['wayback']}/{len(rows)}")
