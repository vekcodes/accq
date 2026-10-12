"""Fetch a company's website (home + about/contact/legal pages) through the shared cache."""
from __future__ import annotations

from accq.core import Ctx, domain_of
from accq.signals import find_about_links, html_to_text

LEGAL_HINTS = ("voorwaarden", "privacy", "disclaimer", "colofon", "impressum")


def site_pages(ctx: Ctx, website: str | None, limit: int = 6) -> dict[str, str]:
    """{url: plain text}. Empty if the site is unreachable. Cached, so safe to call from several stages."""
    if not website:
        return {}
    html = ctx.fetch(website) or (ctx.fetch(website.replace("https://", "http://")) if website.startswith("https://") else None)
    if not html:
        return {}
    pages = {website: html_to_text(html)}
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    links = find_about_links(html, website, limit)
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(website).netloc
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ") + " " + a["href"]).lower()
        if any(h in label for h in LEGAL_HINTS):
            u = urljoin(website, a["href"]).split("#")[0]
            if urlparse(u).netloc == host and u not in links and len(links) < limit + 3:
                links.append(u)
    for u in links:
        h = ctx.fetch(u)
        if h:
            pages[u] = html_to_text(h)
    return pages


def wayback_first_year(ctx: Ctx, website: str | None) -> int | None:
    """Year of the first archived 200 capture of the domain. A LOWER BOUND on domain age,
    not a founding date: companies often get a website years after they start."""
    dom = domain_of(website)
    if not dom:
        return None
    url = f"https://web.archive.org/cdx/search/cdx?url={dom}&limit=1&output=json&fl=timestamp&filter=statuscode:200"
    rows = ctx.fetch_json(url)
    if rows and len(rows) > 1:
        try:
            return int(rows[1][0][:4])
        except (ValueError, IndexError):
            return None
    return None
