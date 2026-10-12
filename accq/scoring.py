"""Hard filters + weighted signals. Pure functions; weights come from the market config."""
from __future__ import annotations

from datetime import date

STALE_AFTER_YEARS = 3


def hard_filter(row: dict, f: dict) -> tuple[str, list[str]]:
    """Return (tier, notes). tier: qualified | needs_check | excluded.

    Known violations exclude. Unknown values either keep the company in a needs_check tier or
    drop it, per config. Unknown is never treated as a pass.
    """
    notes, unknown = [], False
    fy = row.get("founded_year")
    if fy is None:
        if f.get("unknown_founded", "keep") == "drop":
            return "excluded", ["founding year unknown"]
        unknown = True
        notes.append("founding year unknown")
    elif fy > f["founded_by"]:
        return "excluded", [f"founded {fy}, after {f['founded_by']}"]
    emp = row.get("employees")
    if emp is None:
        if f.get("unknown_employees", "keep") == "drop":
            return "excluded", ["headcount unknown"]
        unknown = True
        notes.append("headcount unknown")
    elif not (f["employees_min"] <= emp <= f["employees_max"]):
        return "excluded", [f"{emp} employees outside {f['employees_min']}-{f['employees_max']}"]
    return ("needs_check" if unknown else "qualified"), notes


def score(row: dict, cls: dict | None, w: dict, today: date | None = None) -> tuple[float, list[str]]:
    today = today or date.today()
    total, reasons = 0.0, []

    def add(key: str, factor: float, why: str) -> None:
        nonlocal total
        pts = w.get(key, 0.0) * factor
        if pts:
            total += pts
            reasons.append(f"{pts:+.1f} {why}")

    cls = cls or {}
    if cls.get("owner_age_hint") == "60+":
        add("owner_60_plus", 1, "owner likely 60+")
    if cls.get("owner_active") == "yes":
        add("owner_active", 1, "owner visibly operating")
    ss = cls.get("successor_named")
    if ss == "yes":
        add("successor_named", 1, "successor named")
    elif ss == "no":
        add("no_successor", 1, "explicitly no successor")
    elif cls:  # classified but silent
        add("no_successor", 0.5, "no successor found (absence of evidence, half weight)")
    if cls.get("recent_ownership_change") == "yes":
        add("recent_ownership_change", 1, "recent ownership change")
    if cls.get("new_hires") == "yes":
        add("new_hires", 1, "new hires / recruiting")
    if row.get("now_received"):
        add("now_received", 1, "received NOW support")
    ly = row.get("website_last_year")
    if ly and today.year - ly >= STALE_AFTER_YEARS:
        add("stale_website", 1, f"website last dated {ly}")
    if (row.get("source_count") or 0) >= 2:
        add("multi_source", 1, "found in 2+ sources")
    return total, reasons
