"""Stage 2: legal entity. KVK number and legal form from the company's own website.

Dutch businesses must show their KVK number on their site, so it is usually in the footer,
contact or terms page. This is the free replacement for the paid KVK lookup. Where nothing
is found the field stays NULL: unknown legal form is later treated as the strict case.
"""
from __future__ import annotations

from accq.core import Ctx
from accq.signals import kvk_number, legal_form
from accq.web import site_pages


def run(ctx: Ctx) -> None:
    rows = ctx.con.execute("SELECT id, name, website FROM companies").fetchall()
    found_kvk = found_form = 0
    for cid, name, website in rows:
        pages = site_pages(ctx, website)
        text = " ".join(pages.values())
        kvk = kvk_number(text)
        form, basis = legal_form(name, text)
        found_kvk += bool(kvk)
        found_form += bool(form)
        ctx.con.execute("UPDATE companies SET kvk_number=?, legal_form=?, legal_form_basis=? WHERE id=?", [kvk, form, basis, cid])
    ctx.log(f"entity match: KVK number for {found_kvk}/{len(rows)}, legal form for {found_form}/{len(rows)}")
