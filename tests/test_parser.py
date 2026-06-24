"""Tests for HTML parser."""

from crawldb.crawler.parser import parse_page, normalize_url, is_valid_url


class TestParseHtml:
    """Test HTML parsing and link extraction."""

    def test_basic_page(self):
        html = """
        <html><head><title>Test Page</title></head>
        <body><p>Hello world content</p></body></html>
        """
        result = parse_page(html, "https://example.com")
        assert result.title == "Test Page"
        assert "Hello world content" in result.text_content

    def test_link_extraction(self):
        html = """
        <html><body>
            <a href="/about">About</a>
            <a href="https://example.com/contact">Contact</a>
            <a href="https://other.com/page">External</a>
        </body></html>
        """
        result = parse_page(html, "https://example.com")
        assert "https://example.com/about" in result.internal_links
        assert "https://example.com/contact" in result.internal_links
        assert "https://other.com/page" in result.external_links

    def test_strips_scripts_and_styles(self):
        html = """
        <html><body>
            <script>var x = 1;</script>
            <style>.foo { color: red; }</style>
            <p>Actual content</p>
        </body></html>
        """
        result = parse_page(html, "https://example.com")
        assert "var x" not in result.text_content
        assert ".foo" not in result.text_content
        assert "Actual content" in result.text_content

    def test_meta_description(self):
        html = '<html><head><meta name="description" content="A test page"></head><body>Content</body></html>'
        result = parse_page(html, "https://example.com")
        assert result.meta_description == "A test page"

    def test_skips_invalid_links(self):
        html = """
        <html><body>
            <a href="mailto:test@test.com">Email</a>
            <a href="javascript:void(0)">JS</a>
            <a href="#">Hash</a>
            <a href="https://example.com/page">Valid</a>
        </body></html>
        """
        result = parse_page(html, "https://example.com")
        assert len(result.links) == 1
        assert "https://example.com/page" in result.links

    def test_deduplicates_links(self):
        html = """
        <html><body>
            <a href="/page">Link 1</a>
            <a href="/page">Link 2</a>
            <a href="/page">Link 3</a>
        </body></html>
        """
        result = parse_page(html, "https://example.com")
        assert len(result.internal_links) == 1


class TestNormalizeUrl:
    def test_removes_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_keeps_root_path(self):
        result = normalize_url("https://example.com/")
        assert "example.com" in result


class TestIsValidUrl:
    def test_valid_http(self):
        assert is_valid_url("https://example.com/page")

    def test_rejects_ftp(self):
        assert not is_valid_url("ftp://example.com/file")

    def test_rejects_image(self):
        assert not is_valid_url("https://example.com/image.jpg")

    def test_rejects_pdf(self):
        assert not is_valid_url("https://example.com/doc.pdf")
