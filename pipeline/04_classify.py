"""Stage 4: classify succession signals per company (owner active, successor, new hires, ownership change).

Companies with no usable text are NOT sent to a model: they get all-"unknown" so nothing is invented.
Backend comes from the market config (classifier.backend) and can be overridden with --backend.
"""
from __future__ import annotations

import json

from accq.classify import build_evidence, classify, normalise, skill_prompt
from accq.core import Ctx

MIN_TEXT = 200  # characters of site text below which there is nothing to judge


def run(ctx: Ctx) -> None:
    backend = ctx.cfg.get("classifier", {}).get("backend", "claude-cli")
    model = ctx.cfg.get("classifier", {}).get("model", "haiku")
    rows = ctx.con.execute("SELECT id, name, about_text, press_text FROM companies").fetchall()
    ctx.con.execute("DELETE FROM classification")
    results_path = ctx.run_dir / "classify_results.jsonl"
    batch_path = ctx.run_dir / "classify_batch.jsonl"

    imported = {}
    if backend == "export" and results_path.exists():
        for line in results_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                imported[int(r["id"])] = normalise(r)

    batch, done, skipped, failed = [], 0, 0, 0
    for cid, name, about, press in rows:
        ev = build_evidence(name, about, press)
        if len(about or "") < MIN_TEXT:
            res, used = normalise({"rationale": "geen bruikbare websitetekst"}), "no-evidence"
            skipped += 1
        elif backend == "export":
            if cid in imported:
                res, used = imported[cid], "export-import"
            else:
                batch.append({"id": cid, "name": name, "evidence": ev})
                continue
        else:
            res, used = classify(ev, backend, model), backend
            if res is None:
                failed += 1
                continue
        ctx.con.execute("INSERT INTO classification VALUES (?,?,?,?,?,?,?,?)",
                        [cid, res["owner_active"], res["successor_named"], res["new_hires"],
                         res["recent_ownership_change"], res["owner_age_hint"], res["rationale"], used])
        done += 1
    if backend == "export" and batch:
        batch_path.write_text("\n".join(json.dumps(b, ensure_ascii=False) for b in batch) + "\n")
        (ctx.run_dir / "classify_instructions.md").write_text(
            "# Classify these companies\n\nFor each line in `classify_batch.jsonl`, apply the prompt below and write one JSON line\n"
            "per company to `classify_results.jsonl` with keys: id, owner_active, successor_named, new_hires,\n"
            "recent_ownership_change, owner_age_hint, rationale. Then re-run stage 4.\n\n---\n\n" + skill_prompt())
        ctx.log(f"export: {len(batch)} companies need judging -> {batch_path.name}; see classify_instructions.md. Re-run stage 4 after.")
    ctx.log(f"classify[{backend}]: {done} stored ({skipped} without evidence), {failed} failed, {len(batch)} awaiting export")
