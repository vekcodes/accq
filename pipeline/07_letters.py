"""Stage 7: draft letters for the shortlist. Drafts only: nothing is ever sent by this project."""
from __future__ import annotations

from accq.core import Ctx
from accq.letters import letter

from importlib import import_module


def run(ctx: Ctx) -> None:
    fetch_top = import_module("pipeline.06_dossiers").fetch_top
    out = ctx.run_dir / "letters"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    top = fetch_top(ctx)
    for c in top:
        slug = "".join(ch if ch.isalnum() else "-" for ch in c["name"].lower()).strip("-")[:40]
        (out / f"{c['rank']:02d}-{slug}.md").write_text(letter(c, ctx.cfg["letter"]), encoding="utf-8")
    ctx.log(f"letters: {len(top)} DRAFTS in {out.name}/ (awaiting human approval; not sent)")
