"""`accq run <market>` and `accq eval`."""
from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

from accq.core import ROOT, Ctx

STAGES = {1: "01_universe", 2: "02_match_entity", 3: "03_enrich", 4: "04_classify",
          5: "05_score", 6: "06_dossiers", 7: "07_letters"}


def cmd_run(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT))
    ctx = Ctx.open(a.market, offline=a.offline)
    ctx.delay = a.delay
    if a.backend:
        ctx.cfg.setdefault("classifier", {})["backend"] = a.backend
    for n in range(a.start, a.end + 1):
        ctx.log(f"--- stage {n}: {STAGES[n]}")
        import_module(f"pipeline.{STAGES[n]}").run(ctx)
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    from accq.classify import KEYS, build_evidence, classify
    path = ROOT / "evals" / "succession_testset.jsonl"
    items = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    hit = {k: 0 for k in KEYS}
    n = 0
    for it in items:
        res = classify(build_evidence(it["name"], it.get("about"), it.get("press"), it.get("reviews")), a.backend, a.model)
        if res is None:
            print(f"  {it['id']}: backend returned nothing")
            continue
        n += 1
        for k in KEYS:
            ok = res[k] == it["expected"][k]
            hit[k] += ok
            if not ok:
                print(f"  {it['id']} {k}: got {res[k]!r}, expected {it['expected'][k]!r}")
    print(f"\nbackend={a.backend}  items scored={n}/{len(items)}  (test set is {items[0].get('provenance', 'unspecified')})")
    for k in KEYS:
        print(f"  {k:26s} {hit[k]}/{n}" + (f"  {hit[k]/n:.0%}" if n else ""))
    return 0


def main() -> None:
    p = argparse.ArgumentParser(prog="accq")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the pipeline for a market")
    r.add_argument("market")
    r.add_argument("--from", dest="start", type=int, default=1)
    r.add_argument("--to", dest="end", type=int, default=7)
    r.add_argument("--backend", choices=["claude-cli", "export", "heuristic"])
    r.add_argument("--offline", action="store_true", help="use only cached fetches")
    r.add_argument("--delay", type=float, default=1.0, help="seconds between requests to the same host")
    r.set_defaults(fn=cmd_run)
    e = sub.add_parser("eval", help="score the succession classifier on the labelled test set")
    e.add_argument("--backend", default="heuristic", choices=["claude-cli", "heuristic"])
    e.add_argument("--model", default="haiku")
    e.set_defaults(fn=cmd_eval)
    a = p.parse_args()
    raise SystemExit(a.fn(a))
