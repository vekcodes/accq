"""Pure functions that pull signals out of Dutch website text. No I/O, easy to test."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

THIS_YEAR = date.today().year

ABOUT_HINTS = ("over ons", "over-ons", "overons", "about", "geschiedenis", "historie",
               "ons verhaal", "wie zijn wij", "het bedrijf", "bedrijfsprofiel", "team",
               "medewerkers", "vacature", "werken bij", "contact", "nieuws")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def find_about_links(html: str, base: str, limit: int = 6) -> list[str]:
    from urllib.parse import urljoin, urlparse
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base).netloc
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ") + " " + a["href"]).lower()
        if any(h in label for h in ABOUT_HINTS):
            u = urljoin(base, a["href"]).split("#")[0]
            if urlparse(u).netloc == host and u not in out and not re.search(r"\.(pdf|jpe?g|png|zip)$", u, re.I):
                out.append(u)
    return out[:limit]


# ---- founding year -----------------------------------------------------
_FOUND_PATTERNS = [
    (r"\bsinds\s+(?:het\s+jaar\s+)?(1[89]\d\d|20[0-2]\d)\b", "sinds"),
    (r"\bopgericht\s+(?:in|op)\s+(?:[\w\s]{0,20}?)(1[89]\d\d|20[0-2]\d)\b", "opgericht"),
    (r"\b(?:in|anno)\s+(1[89]\d\d|20[0-2]\d)\s+(?:werd|is|zijn)\s+[\w\s]{0,40}?(?:opgericht|gestart|begonnen|gesticht)", "in-jaar"),
    (r"\bestablished\s+(?:in\s+)?(1[89]\d\d|20[0-2]\d)\b", "established"),
    (r"\b(?:sinds|vanaf)\s+(1[89]\d\d|20[0-2]\d)\b", "sinds"),
    (r"\bbestaat\s+(?:al\s+)?sinds\s+(1[89]\d\d|20[0-2]\d)\b", "sinds"),
    (r"\banno\s+(1[89]\d\d|20[0-2]\d)\b", "anno"),
]
_YEARS_PATTERN = re.compile(r"\b(?:al\s+)?(?:meer\s+dan\s+|ruim\s+|ruim\s+meer\s+dan\s+|ruim\s+|ca\.?\s+)?(\d{2,3})\s+jaar\s+(?:ervaring|actief|bestaan|geleden|in\s+het\s+vak|vakmanschap)", re.I)


def founding_year(text: str) -> tuple[int | None, str | None]:
    """Earliest plausible explicit founding year, with the phrase type that gave it."""
    hits: list[tuple[int, str]] = []
    low = text.lower()
    for pat, label in _FOUND_PATTERNS:
        for m in re.finditer(pat, low):
            y = int(m.group(1))
            if 1850 <= y <= THIS_YEAR:
                hits.append((y, label))
    if hits:
        # 'sinds 2019' next to a 'sinds 1978' is usually a product/location; take the earliest.
        y, label = min(hits)
        return y, f"website:{label}"
    # "40 jaar ervaring" is a weak signal about the owner, not the company: report it as such.
    m = _YEARS_PATTERN.search(low)
    if m:
        n = int(m.group(1))
        if 5 <= n <= 120:
            return THIS_YEAR - n, "website:jaar-ervaring(weak)"
    return None, None


def is_family_business(text: str) -> bool:
    return bool(re.search(r"familiebedrijf|familie-?bedrijf|derde generatie|tweede generatie|vader en zoon|van vader op zoon", text.lower()))


# ---- headcount ---------------------------------------------------------
def headcount(text: str) -> tuple[int | None, str | None]:
    low = text.lower()
    best = None
    for m in re.finditer(r"\b(\d{1,3})\s+(?:vaste\s+)?(?:medewerkers|collega'?s|vakmensen|monteurs|installateurs|werknemers|man\s+personeel)\b", low):
        n = int(m.group(1))
        if 1 <= n <= 500:
            best = max(best or 0, n)
    if best:
        return best, "website:aantal-medewerkers"
    return None, None


# ---- legal identity ----------------------------------------------------
_KVK = re.compile(r"(?:kvk|k\.v\.k\.?|kamer\s+van\s+koophandel|handelsregister)[^0-9]{0,40}(\d{8})\b", re.I)


def kvk_number(text: str) -> str | None:
    m = _KVK.search(text)
    return m.group(1) if m else None


def legal_form(name: str, text: str = "") -> tuple[str | None, str | None]:
    """Legal form from the company name, falling back to site text. None = unknown."""
    n = f" {name.lower()} "
    for pat, form in ((r"\bb\.?\s?v\.?\b", "BV"), (r"\bn\.?\s?v\.?\b", "NV"), (r"\bv\.?\s?o\.?\s?f\.?\b", "VOF"),
                      (r"\bc\.?\s?v\.?\b", "CV"), (r"\bstichting\b", "Stichting"), (r"\beenmanszaak\b", "Eenmanszaak")):
        if re.search(pat, n):
            return form, "name"
    t = text.lower()
    for pat, form in ((r"\b\w[\w\s&.\-]{1,40}\sb\.?v\.?(?=[\s,.;)]|$)", "BV"), (r"\bv\.?o\.?f\.?\b", "VOF"), (r"\beenmanszaak\b", "Eenmanszaak")):
        if re.search(pat, t):
            return form, "website-text"
    return None, None


def is_natural_person_form(form: str | None) -> bool:
    """Eenmanszaak/VOF/CV are natural persons for direct-marketing law. Unknown is treated strictly."""
    return form not in ("BV", "NV")


# ---- website freshness -------------------------------------------------
def last_year_mentioned(text: str) -> int | None:
    """Latest copyright / dated-news year; a proxy for 'site not updated in years'."""
    years = [int(y) for y in re.findall(r"(?:©|copyright|\(c\))\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", text.lower())]
    years += [int(y) for y in re.findall(r"\b(?:nieuws|bericht|geplaatst|datum)[^.]{0,40}?\b(20[0-2]\d)\b", text.lower())]
    years = [y for y in years if 1995 <= y <= THIS_YEAR]
    return max(years) if years else None


def hiring_mentions(text: str) -> bool:
    return bool(re.search(r"\b(vacatures?|wij zoeken|solliciteer|kom werken bij|werken bij)\b", text.lower()))


def succession_hints(text: str) -> list[str]:
    """Raw phrases worth showing the classifier and the human reader."""
    pats = r"(opvolg\w*|overname|overgenomen|nieuwe eigenaar|bedrijfsopvolging|directie overgedragen|zoon\s+\w+\s+neemt|dochter\s+\w+\s+neemt|met pensioen|pensioen|jubileum|\d+\s*jaar bestaan)"
    out = []
    for m in re.finditer(pats, text.lower()):
        s = max(0, m.start() - 80)
        out.append(text[s:m.end() + 80].strip())
    return out[:6]


def split_weak(year: int | None, basis: str | None) -> tuple[int | None, str | None]:
    """Weak estimates ("40 jaar ervaring") describe the owner, not the company. They must not
    feed the hard filter, so they are kept only as a text hint in the basis column."""
    if year and basis and "(weak)" in basis:
        return None, f"alleen indicatie, geen oprichtingsjaar: ca. {year} (op basis van jaren ervaring)"
    return year, basis
