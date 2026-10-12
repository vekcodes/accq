"""Stage 1: build the universe from free sources and deduplicate on name + place.

Sources: OpenStreetMap (Overpass), plus any CSV dropped in the market's extra_dir
(Clay export, association member list, Google Places export, ...). The NOW register is
joined in stage 3. A company found in 2+ sources is flagged by source_count.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
from pathlib import Path

from accq.core import Ctx, ROOT, clean_url, domain_of, norm_city, norm_name

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]


def overpass_query(cfg: dict) -> str:
    """Prefer the real administrative boundary (`area`) over a rectangle, which spills into Germany/other provinces."""
    u = cfg["universe"]
    body = "\n".join(f"  {f}{'(area.a)' if u.get('area') else ''};" for f in u["osm_filters"])
    if u.get("area"):
        a = u["area"]
        head = f'[out:json][timeout:180];\narea["boundary"="administrative"]["admin_level"="{a["admin_level"]}"]["name"="{a["name"]}"]->.a;'
    else:
        s, w, n, e = u["bbox"]
        head = f"[out:json][timeout:90][bbox:{s},{w},{n},{e}];"
    return f"{head}\n(\n{body}\n);\nout center tags;"


NL_POSTCODE = re.compile(r"^\d{4}\s?[A-Za-z]{2}$")


def fetch_osm(ctx: Ctx, rounds: int = 3) -> list[dict]:
    """Try each public Overpass server, then back off and go round again: they are often overloaded."""
    q = overpass_query(ctx.cfg)
    data = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(rounds):
        for url in OVERPASS:
            txt = ctx.fetch(url, data=data, timeout=120, max_bytes=20_000_000)
            try:
                els = json.loads(txt)["elements"] if txt else None
            except (json.JSONDecodeError, KeyError):
                els = None
            if els is not None:
                return els
            ctx.forget(url, data)  # errors (even 200-with-error-page) must never be cached
            ctx.log(f"Overpass {url} gave no usable answer")
        if attempt < rounds - 1 and not ctx.offline:
            ctx.log("all servers busy, waiting 30s before retrying")
            time.sleep(30)
    ctx.log("WARNING: all Overpass servers failed; continuing with CSV sources only")
    return []


def osm_rows(elements: list[dict]) -> list[dict]:
    rows = []
    for el in elements:
        t = el.get("tags", {})
        name = t.get("name") or t.get("brand")
        if not name:
            continue
        pc = t.get("addr:postcode", "")
        if pc and not NL_POSTCODE.match(pc.strip()):
            continue  # not a Dutch postcode (e.g. German 5-digit): outside the market
        street = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
        rows.append(dict(
            name=name, city=t.get("addr:city", ""), postcode=t.get("addr:postcode", ""), street=street,
            website=t.get("website") or t.get("contact:website") or t.get("brand:website"),
            phone=t.get("phone") or t.get("contact:phone"), email=t.get("email") or t.get("contact:email"),
            source="osm"))
    return rows


def csv_rows(extra_dir: Path) -> list[dict]:
    rows = []
    for f in sorted(extra_dir.glob("*.csv")) if extra_dir.exists() else []:
        with f.open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if (r.get("name") or "").strip():
                    r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
                    r["source"] = r.get("source") or f"csv:{f.stem}"
                    rows.append(r)
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    """Merge on (normalised name, city) or on website domain. Fill gaps from later rows."""
    merged: dict[str, dict] = {}
    by_domain: dict[str, str] = {}
    for r in rows:
        r["website"] = clean_url(r.get("website"))
        key = f"{norm_name(r['name'])}|{norm_city(r.get('city', ''))}"
        dom = domain_of(r["website"])
        if dom and dom in by_domain:
            key = by_domain[dom]
        if key in merged:
            m = merged[key]
            for f in ("city", "postcode", "street", "website", "phone", "email"):
                m[f] = m.get(f) or r.get(f)
            m["sources"].add(r["source"])
        else:
            merged[key] = {**r, "sources": {r["source"]}}
        if dom:
            by_domain.setdefault(dom, key)
    return list(merged.values())


def run(ctx: Ctx) -> None:
    rows = osm_rows(fetch_osm(ctx))
    n_osm = len(rows)
    extra = csv_rows(ROOT / ctx.cfg["universe"].get("extra_dir", "data/extra/none"))
    companies = dedupe(rows + extra)
    ctx.log(f"universe: {n_osm} OSM rows + {len(extra)} CSV rows -> {len(companies)} unique companies")
    for t in ("scores", "classification", "companies"):
        ctx.con.execute(f"DELETE FROM {t}")
    for i, c in enumerate(companies, 1):
        ctx.con.execute(
            "INSERT INTO companies (id,name,norm_name,city,postcode,street,website,phone,email,sources,source_count) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [i, c["name"], norm_name(c["name"]), c.get("city"), c.get("postcode"), c.get("street"), c.get("website"),
             c.get("phone"), c.get("email"), ",".join(sorted(c["sources"])), len(c["sources"])])
    with_site = ctx.con.execute("SELECT count(*) FROM companies WHERE website IS NOT NULL").fetchone()[0]
    ctx.log(f"{with_site} of {len(companies)} have a website (the rest cannot be enriched from the web)")
