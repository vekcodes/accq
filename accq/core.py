"""Shared plumbing: market config, DuckDB state, cached HTTP, text helpers."""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "genflows-accq/0.1 (research; contact via genflowsagency.com)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    norm_name TEXT,
    city TEXT, postcode TEXT, street TEXT,
    website TEXT, phone TEXT, email TEXT,
    sources TEXT,              -- comma separated source tags
    source_count INTEGER,
    kvk_number TEXT, legal_form TEXT, legal_form_basis TEXT,
    founded_year INTEGER, founded_basis TEXT,
    wayback_first_year INTEGER,
    employees INTEGER, employees_basis TEXT,
    now_received BOOLEAN DEFAULT FALSE,
    website_last_year INTEGER,
    about_text TEXT, press_text TEXT
);
CREATE TABLE IF NOT EXISTS classification (
    company_id INTEGER PRIMARY KEY,
    owner_active TEXT, successor_named TEXT, new_hires TEXT,
    recent_ownership_change TEXT, owner_age_hint TEXT,
    rationale TEXT, backend TEXT
);
CREATE TABLE IF NOT EXISTS scores (
    company_id INTEGER PRIMARY KEY,
    tier TEXT, score DOUBLE, rank INTEGER, reasons TEXT
);
"""


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(b\.?\s?v\.?|v\.?o\.?f\.?|n\.?v\.?|holding|beheer|installatie(?:bedrijf|techniek)?|techniek)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def norm_city(city: str) -> str:
    s = unicodedata.normalize("NFKD", city or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", "", s)


def load_market(name: str) -> dict:
    path = ROOT / "markets" / f"{name}.yaml"
    if not path.exists():
        raise SystemExit(f"No market config at {path}")
    return yaml.safe_load(path.read_text())


@dataclass
class Ctx:
    market: str
    cfg: dict
    run_dir: Path
    cache_dir: Path
    con: duckdb.DuckDBPyConnection
    offline: bool = False
    delay: float = 1.0
    _last_fetch: dict = field(default_factory=dict)

    @classmethod
    def open(cls, market: str, offline: bool = False, root: Path | None = None) -> "Ctx":
        root = root or ROOT
        cfg = load_market(market)
        run_dir = root / "runs" / market
        run_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = root / "cache"
        cache_dir.mkdir(exist_ok=True)
        con = duckdb.connect(str(run_dir / f"{market}.duckdb"))
        con.execute(SCHEMA)
        return cls(market, cfg, run_dir, cache_dir, con, offline)

    # ---- cached HTTP -------------------------------------------------
    def fetch(self, url: str, *, data: bytes | None = None, timeout: int = 25,
              max_bytes: int = 1_500_000) -> str | None:
        """GET/POST with an on-disk cache. Returns text, or None on failure.

        Failures are cached too (as an empty marker) so a dead URL is not retried
        within a run. Delete cache/ to force refresh.
        """
        path = self._cache_path(url, data)
        if path.exists():
            txt = path.read_text(encoding="utf-8", errors="replace")
            return txt if txt != "\x00FAIL" else None
        if self.offline:
            return None
        host = urllib.parse.urlparse(url).netloc
        wait = self.delay - (time.time() - self._last_fetch.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read(max_bytes)
                charset = r.headers.get_content_charset() or "utf-8"
            txt = raw.decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            txt = None
        self._last_fetch[host] = time.time()
        path.write_text(txt if txt is not None else "\x00FAIL", encoding="utf-8")
        return txt

    def _cache_path(self, url: str, data: bytes | None = None) -> Path:
        key = hashlib.sha1((url + (data or b"").decode("latin1")).encode()).hexdigest()
        return self.cache_dir / key[:2] / key

    def forget(self, url: str, data: bytes | None = None) -> None:
        """Drop a cache entry, e.g. when a 200 response turned out to be an error page."""
        self._cache_path(url, data).unlink(missing_ok=True)

    def fetch_json(self, url: str, **kw):
        txt = self.fetch(url, **kw)
        if not txt:
            return None
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return None

    def log(self, msg: str) -> None:
        print(f"[{self.market}] {msg}", flush=True)


def clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/') if p.path != '/' else ''}"


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
