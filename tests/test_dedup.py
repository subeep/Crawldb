"""Tests for content hash deduplication."""

from crawldb.crawler.dedup import compute_content_hash, compute_url_hash


class TestContentHash:
    """Test content hash computation and normalization."""

    def test_basic_hash(self):
        """Same text should produce the same hash."""
        h1 = compute_content_hash("Hello World")
        h2 = compute_content_hash("Hello World")
        assert h1 == h2

    def test_hash_is_sha256(self):
        """Hash should be 64 hex characters (SHA-256)."""
        h = compute_content_hash("test content")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_whitespace_normalization(self):
        """Whitespace differences should produce the same hash."""
        h1 = compute_content_hash("Hello    World")
        h2 = compute_content_hash("Hello World")
        h3 = compute_content_hash("Hello\n\t  World")
        assert h1 == h2 == h3

    def test_case_normalization(self):
        """Case differences should produce the same hash."""
        h1 = compute_content_hash("Hello World")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_different_content(self):
        """Different content should produce different hashes."""
        h1 = compute_content_hash("Page A content")
        h2 = compute_content_hash("Page B content")
        assert h1 != h2

    def test_empty_content(self):
        """Empty content should still produce a valid hash."""
        h = compute_content_hash("")
        assert len(h) == 64

    def test_url_hash(self):
        """URL hashes should be consistent."""
        h1 = compute_url_hash("https://example.com")
        h2 = compute_url_hash("https://example.com")
        assert h1 == h2
        h3 = compute_url_hash("https://other.com")
        assert h1 != h3
