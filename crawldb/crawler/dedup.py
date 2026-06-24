"""Content hash deduplication via SHA-256."""

from __future__ import annotations

import hashlib
import re


def compute_content_hash(text: str) -> str:
    """
    Compute a SHA-256 hash of normalized text content.

    Normalization:
    - Lowercase
    - Collapse all whitespace to single spaces
    - Strip leading/trailing whitespace

    This ensures that pages with minor whitespace differences
    are detected as duplicates.
    """
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_url_hash(url: str) -> str:
    """Compute a SHA-256 hash of a URL (for seen-URL tracking)."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
