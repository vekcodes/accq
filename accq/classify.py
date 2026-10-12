"""Succession classification: shared by pipeline stage 4 and `accq eval`.

Backends
- claude-cli : headless `claude -p` per company (uses your Claude Code login, no API key)
- export     : write a batch file for classification inside an interactive Claude Code session,
               then read the answers back from classify_results.jsonl
- heuristic  : keyword baseline. Cheap and offline; useful as a floor for the eval, not for real ranking.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from accq.core import ROOT

SKILL = ROOT / "skills" / "succession-classifier" / "SKILL.md"
KEYS = ("owner_active", "successor_named", "new_hires", "recent_ownership_change", "owner_age_hint")
ALLOWED = {
    "owner_active": {"yes", "no", "unknown"}, "successor_named": {"yes", "no", "unknown"},
    "new_hires": {"yes", "no", "unknown"}, "recent_ownership_change": {"yes", "no", "unknown"},
    "owner_age_hint": {"60+", "under60", "unknown"},
}


def skill_prompt() -> str:
    return re.sub(r"^---.*?---\s*", "", SKILL.read_text(), flags=re.S)


def build_evidence(name: str, about: str | None, press: str | None, reviews: str | None = None) -> str:
    parts = [f"Bedrijf: {name}"]
    if about:
        parts.append(f"Website-tekst:\n{about}")
    if press:
        parts.append(f"Signalen/pers:\n{press}")
    if reviews:
        parts.append(f"Reviews:\n{reviews}")
    return "\n\n".join(parts)


def normalise(d: dict) -> dict:
    out = {}
    for k in KEYS:
        v = str(d.get(k, "unknown")).strip().lower()
        out[k] = v if v in ALLOWED[k] else "unknown"
    out["rationale"] = str(d.get("rationale", ""))[:400]
    return out


def parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return normalise(json.loads(m.group(0)))
    except json.JSONDecodeError:
        return None


def heuristic(evidence: str) -> dict:
    t = evidence.lower()
    yes = lambda pat: "yes" if re.search(pat, t) else "unknown"
    return normalise(dict(
        owner_active=yes(r"\b(eigenaar|oprichter|directeur-eigenaar|mijn bedrijf|ik ben)\b"),
        successor_named=yes(r"opvolg|neemt het bedrijf over|zoon \w+ neemt|dochter \w+ neemt|derde generatie|tweede generatie"),
        new_hires=yes(r"vacature|wij zoeken|solliciteer"),
        recent_ownership_change=yes(r"overgenomen|overname|nieuwe eigenaar|onderdeel van .{0,30}groep|vestiging"),
        owner_age_hint=yes(r"pensioen|40 jaar|45 jaar|50 jaar").replace("yes", "60+"),
        rationale="keyword baseline (heuristic backend)"))


def claude_cli(evidence: str, model: str = "haiku", timeout: int = 180) -> dict | None:
    prompt = skill_prompt() + "\n\n--- EVIDENCE ---\n" + evidence + "\n\nAntwoord nu met alleen het JSON-object."
    try:
        p = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json"], input=prompt,
                           capture_output=True, text=True, timeout=timeout)
        outer = json.loads(p.stdout)
        return parse_json(outer.get("result", "")) if isinstance(outer, dict) else None
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        return None


def classify(evidence: str, backend: str, model: str = "haiku") -> dict | None:
    if backend == "heuristic":
        return heuristic(evidence)
    if backend == "claude-cli":
        return claude_cli(evidence, model)
    raise ValueError(f"backend {backend!r} is not a per-item backend")
