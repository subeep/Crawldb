"""HTML parser — extract title, text content, and links."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass
class ParsedPage:
    """Parsed HTML page data."""
    title: str = ""
    text_content: str = ""
    meta_description: str = ""
    links: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    """Normalize a URL by removing fragments and trailing slashes."""
    parsed = urlparse(url)
    # Remove fragment
    normalized = parsed._replace(fragment="")
    result = normalized.geturl()
    # Remove trailing slash for consistency (but keep root /)
    if result.endswith("/") and len(parsed.path) > 1:
        result = result.rstrip("/")
    return result


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid for crawling."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
        # Skip common non-page resources
        skip_extensions = {
            ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
            ".mp3", ".mp4", ".avi", ".mov", ".zip", ".tar", ".gz",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".ico",
        }
        path_lower = parsed.path.lower()
        for ext in skip_extensions:
            if path_lower.endswith(ext):
                return False
        return True
    except Exception:
        return False


def parse_page(html: str, base_url: str) -> ParsedPage:
    """
    Parse an HTML document and extract structured data.

    Args:
        html: Raw HTML string
        base_url: The URL the page was fetched from (for resolving relative links)

    Returns:
        ParsedPage with title, text, and extracted links
    """
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()

    # Extract meta description
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    # Extract text content (strip scripts, styles, nav, footer)
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Extract and classify links
    all_links = []
    internal = []
    external = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        # Resolve relative URLs
        absolute = urljoin(base_url, href)
        normalized = normalize_url(absolute)

        if not is_valid_url(normalized):
            continue

        all_links.append(normalized)

        link_domain = urlparse(normalized).netloc
        if link_domain == base_domain:
            internal.append(normalized)
        else:
            external.append(normalized)

    # Deduplicate while preserving order
    all_links = list(dict.fromkeys(all_links))
    internal = list(dict.fromkeys(internal))
    external = list(dict.fromkeys(external))

    return ParsedPage(
        title=title,
        text_content=text[:100000],  # Cap text length
        meta_description=meta_desc,
        links=all_links,
        internal_links=internal,
        external_links=external,
    )
