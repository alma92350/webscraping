import re
from typing import Optional, Tuple

import trafilatura
from bs4 import BeautifulSoup


def extract_content(html: str, url: Optional[str] = None) -> Tuple[str, str]:
    """Extract a title and the main readable text from a page's HTML.

    Uses trafilatura (a readability-style extractor) as the primary
    strategy, since it identifies and drops boilerplate (nav, ads, social
    widgets, footers) far more reliably than a class/id substring match.
    Falls back to a plain BeautifulSoup text dump for pages trafilatura
    can't parse at all (e.g. near-empty pages), so the API still returns
    something rather than an error.
    """
    document = trafilatura.bare_extraction(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
        with_metadata=True,
    )

    text = (document.text or "").strip() if document else ""
    title = (document.title or "").strip() if document else ""

    if not text:
        title, text = _fallback_extract(html)

    if not title:
        title = _title_from_html(html)

    return title or "No title found", text


def _title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _fallback_extract(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = _title_from_html(html)

    for tag in soup(["script", "style", "iframe", "noscript", "meta", "link", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text
