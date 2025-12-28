"""
Tests for the Sitemap Parser Service.

Tests parsing of standard sitemaps, sitemap indexes, gzipped sitemaps,
URL filtering, prioritization, and robots.txt sitemap discovery.
"""

import gzip
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawler.services.sitemap_parser import (
    SitemapParser,
    SitemapURL,
    SitemapResult,
    SitemapParseError,
)


# Sample sitemap XML fixtures
STANDARD_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/whiskey-1</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/product/whiskey-2</loc>
    <lastmod>2024-01-10</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://example.com/about</loc>
    <lastmod>2023-06-01</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>
</urlset>
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-products.xml</loc>
    <lastmod>2024-01-20</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-articles.xml</loc>
    <lastmod>2024-01-18</lastmod>
  </sitemap>
</sitemapindex>
"""

MINIMAL_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
  </url>
</urlset>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/1</loc>
    <lastmod>invalid-date</lastmod>
  </url>
  <url>
    <loc>https://example.com/product/2</loc>
    <priority>not-a-number</priority>
  </url>
  <url>
    <loc>https://example.com/product/3</loc>
  </url>
  <!-- Missing closing tag intentionally left out for some elements -->
</urlset>
"""

EMPTY_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>
"""

ROBOTS_TXT_WITH_SITEMAPS = """User-agent: *
Disallow: /admin/
Disallow: /private/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-products.xml
Sitemap: https://example.com/sitemap-news.xml.gz
"""

ROBOTS_TXT_NO_SITEMAP = """User-agent: *
Disallow: /admin/
Allow: /public/
"""


class TestSitemapURL:
    """Tests for SitemapURL dataclass."""

    def test_sitemap_url_creation(self):
        """Test creating a SitemapURL with all fields."""
        url = SitemapURL(
            url="https://example.com/product/1",
            lastmod=datetime(2024, 1, 15, tzinfo=timezone.utc),
            changefreq="weekly",
            priority=0.8,
            sitemap_source="https://example.com/sitemap.xml",
        )

        assert url.url == "https://example.com/product/1"
        assert url.lastmod.year == 2024
        assert url.changefreq == "weekly"
        assert url.priority == 0.8
        assert url.sitemap_source == "https://example.com/sitemap.xml"

    def test_sitemap_url_with_optional_fields(self):
        """Test creating a SitemapURL with minimal fields."""
        url = SitemapURL(
            url="https://example.com/page",
            sitemap_source="https://example.com/sitemap.xml",
        )

        assert url.url == "https://example.com/page"
        assert url.lastmod is None
        assert url.changefreq is None
        assert url.priority is None


class TestSitemapResult:
    """Tests for SitemapResult dataclass."""

    def test_sitemap_result_creation(self):
        """Test creating a SitemapResult."""
        urls = [
            SitemapURL(url="https://example.com/1", sitemap_source="test"),
            SitemapURL(url="https://example.com/2", sitemap_source="test"),
        ]

        result = SitemapResult(
            urls=urls,
            is_index=False,
            child_sitemaps=[],
            total_urls=2,
            parse_errors=[],
        )

        assert len(result.urls) == 2
        assert result.is_index is False
        assert result.total_urls == 2
        assert len(result.parse_errors) == 0

    def test_sitemap_result_with_errors(self):
        """Test SitemapResult with parse errors."""
        result = SitemapResult(
            urls=[],
            is_index=False,
            child_sitemaps=[],
            total_urls=0,
            parse_errors=["Invalid date format", "Invalid priority value"],
        )

        assert len(result.parse_errors) == 2


class TestSitemapParserParsing:
    """Tests for parsing standard sitemaps."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_standard_sitemap(self, parser):
        """Test parsing a standard sitemap.xml."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = STANDARD_SITEMAP_XML

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.is_index is False
            assert result.total_urls == 3
            assert len(result.urls) == 3

            first_url = result.urls[0]
            assert first_url.url == "https://example.com/product/whiskey-1"
            assert first_url.changefreq == "weekly"
            assert first_url.priority == 0.8

    @pytest.mark.asyncio
    async def test_parse_minimal_sitemap(self, parser):
        """Test parsing a sitemap with only loc elements."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = MINIMAL_SITEMAP_XML

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.total_urls == 2
            for url in result.urls:
                assert url.lastmod is None
                assert url.changefreq is None
                assert url.priority is None

    @pytest.mark.asyncio
    async def test_parse_empty_sitemap(self, parser):
        """Test parsing an empty sitemap."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = EMPTY_SITEMAP_XML

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.total_urls == 0
            assert len(result.urls) == 0

    @pytest.mark.asyncio
    async def test_parse_sitemap_stores_source(self, parser):
        """Test that parsed URLs store the sitemap source."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = STANDARD_SITEMAP_XML

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            for url in result.urls:
                assert url.sitemap_source == "https://example.com/sitemap.xml"


class TestSitemapIndexParsing:
    """Tests for parsing sitemap index files."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_sitemap_index(self, parser):
        """Test parsing a sitemap index file."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = SITEMAP_INDEX_XML

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.is_index is True
            assert len(result.child_sitemaps) == 2
            assert "https://example.com/sitemap-products.xml" in result.child_sitemaps
            assert "https://example.com/sitemap-articles.xml" in result.child_sitemaps

    @pytest.mark.asyncio
    async def test_parse_sitemap_index_returns_urls(self, parser):
        """Test parse_sitemap_index returns list of sitemap URLs."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = SITEMAP_INDEX_XML

            sitemap_urls = await parser.parse_sitemap_index(
                "https://example.com/sitemap.xml"
            )

            assert len(sitemap_urls) == 2
            assert "https://example.com/sitemap-products.xml" in sitemap_urls
            assert "https://example.com/sitemap-articles.xml" in sitemap_urls


class TestGzippedSitemaps:
    """Tests for parsing gzipped sitemaps."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_gzipped_sitemap(self, parser):
        """Test parsing a gzipped sitemap."""
        gzipped_content = gzip.compress(STANDARD_SITEMAP_XML.encode("utf-8"))

        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = gzipped_content

            result = await parser.parse_sitemap(
                "https://example.com/sitemap.xml.gz"
            )

            assert result.total_urls == 3
            assert result.is_index is False


class TestMalformedXML:
    """Tests for handling malformed XML."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_sitemap_with_invalid_date(self, parser):
        """Test parsing sitemap with invalid lastmod date."""
        malformed = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/1</loc>
    <lastmod>not-a-date</lastmod>
  </url>
</urlset>
"""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = malformed

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            # Should still parse the URL, just with None lastmod
            assert result.total_urls == 1
            assert result.urls[0].lastmod is None
            assert len(result.parse_errors) > 0

    @pytest.mark.asyncio
    async def test_parse_sitemap_with_invalid_priority(self, parser):
        """Test parsing sitemap with invalid priority value."""
        malformed = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/product/1</loc>
    <priority>not-a-number</priority>
  </url>
</urlset>
"""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = malformed

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.total_urls == 1
            assert result.urls[0].priority is None
            assert len(result.parse_errors) > 0

    @pytest.mark.asyncio
    async def test_parse_completely_invalid_xml(self, parser):
        """Test parsing completely invalid XML."""
        invalid = "This is not XML at all"

        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = invalid

            with pytest.raises(SitemapParseError):
                await parser.parse_sitemap("https://example.com/sitemap.xml")


class TestRobotsTxtDiscovery:
    """Tests for discovering sitemaps from robots.txt."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_discover_sitemaps_from_robots(self, parser):
        """Test discovering sitemaps from robots.txt."""
        with patch.object(parser, "_fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_WITH_SITEMAPS

            sitemaps = await parser.discover_sitemaps_from_robots(
                "https://example.com/robots.txt"
            )

            assert len(sitemaps) == 3
            assert "https://example.com/sitemap.xml" in sitemaps
            assert "https://example.com/sitemap-products.xml" in sitemaps
            assert "https://example.com/sitemap-news.xml.gz" in sitemaps

    @pytest.mark.asyncio
    async def test_discover_no_sitemaps_in_robots(self, parser):
        """Test robots.txt with no sitemap directives."""
        with patch.object(parser, "_fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_NO_SITEMAP

            sitemaps = await parser.discover_sitemaps_from_robots(
                "https://example.com/robots.txt"
            )

            assert len(sitemaps) == 0


class TestURLFiltering:
    """Tests for URL pattern filtering."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    def test_filter_urls_by_pattern(self, parser):
        """Test filtering URLs by regex patterns."""
        urls = [
            SitemapURL(url="https://example.com/product/whiskey-1", sitemap_source="test"),
            SitemapURL(url="https://example.com/product/whiskey-2", sitemap_source="test"),
            SitemapURL(url="https://example.com/about", sitemap_source="test"),
            SitemapURL(url="https://example.com/blog/article-1", sitemap_source="test"),
            SitemapURL(url="https://example.com/shop/rum/bottle-1", sitemap_source="test"),
        ]

        patterns = [r"/product/", r"/shop/"]

        filtered = parser.filter_urls_by_pattern(urls, patterns)

        assert len(filtered) == 3
        assert any("/product/whiskey-1" in u.url for u in filtered)
        assert any("/product/whiskey-2" in u.url for u in filtered)
        assert any("/shop/rum/bottle-1" in u.url for u in filtered)
        assert not any("/about" in u.url for u in filtered)
        assert not any("/blog/" in u.url for u in filtered)

    def test_filter_urls_empty_patterns(self, parser):
        """Test filtering with empty patterns returns all URLs."""
        urls = [
            SitemapURL(url="https://example.com/page1", sitemap_source="test"),
            SitemapURL(url="https://example.com/page2", sitemap_source="test"),
        ]

        filtered = parser.filter_urls_by_pattern(urls, [])

        assert len(filtered) == 2

    def test_filter_urls_no_matches(self, parser):
        """Test filtering with patterns that match nothing."""
        urls = [
            SitemapURL(url="https://example.com/about", sitemap_source="test"),
            SitemapURL(url="https://example.com/contact", sitemap_source="test"),
        ]

        patterns = [r"/product/"]

        filtered = parser.filter_urls_by_pattern(urls, patterns)

        assert len(filtered) == 0


class TestURLPrioritization:
    """Tests for URL prioritization."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    def test_prioritize_urls_by_lastmod(self, parser):
        """Test that URLs are sorted by lastmod (most recent first)."""
        urls = [
            SitemapURL(
                url="https://example.com/old",
                lastmod=datetime(2023, 1, 1, tzinfo=timezone.utc),
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/newest",
                lastmod=datetime(2024, 6, 15, tzinfo=timezone.utc),
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/medium",
                lastmod=datetime(2024, 3, 1, tzinfo=timezone.utc),
                sitemap_source="test",
            ),
        ]

        prioritized = parser.prioritize_urls(urls)

        assert prioritized[0].url == "https://example.com/newest"
        assert prioritized[1].url == "https://example.com/medium"
        assert prioritized[2].url == "https://example.com/old"

    def test_prioritize_urls_by_priority_when_no_lastmod(self, parser):
        """Test that URLs without lastmod are sorted by priority."""
        urls = [
            SitemapURL(
                url="https://example.com/low",
                priority=0.3,
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/high",
                priority=0.9,
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/medium",
                priority=0.5,
                sitemap_source="test",
            ),
        ]

        prioritized = parser.prioritize_urls(urls)

        assert prioritized[0].url == "https://example.com/high"
        assert prioritized[1].url == "https://example.com/medium"
        assert prioritized[2].url == "https://example.com/low"

    def test_prioritize_urls_mixed(self, parser):
        """Test prioritization with mixed lastmod and priority."""
        urls = [
            SitemapURL(
                url="https://example.com/recent-low-priority",
                lastmod=datetime(2024, 6, 1, tzinfo=timezone.utc),
                priority=0.3,
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/old-high-priority",
                lastmod=datetime(2023, 1, 1, tzinfo=timezone.utc),
                priority=0.9,
                sitemap_source="test",
            ),
        ]

        prioritized = parser.prioritize_urls(urls)

        # Recent date should come first
        assert prioritized[0].url == "https://example.com/recent-low-priority"

    def test_prioritize_urls_with_none_values(self, parser):
        """Test prioritization handles None lastmod and priority."""
        urls = [
            SitemapURL(url="https://example.com/no-metadata", sitemap_source="test"),
            SitemapURL(
                url="https://example.com/has-date",
                lastmod=datetime(2024, 1, 1, tzinfo=timezone.utc),
                sitemap_source="test",
            ),
            SitemapURL(
                url="https://example.com/has-priority",
                priority=0.8,
                sitemap_source="test",
            ),
        ]

        prioritized = parser.prioritize_urls(urls)

        # URL with date should come first
        assert prioritized[0].url == "https://example.com/has-date"


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_fetch_timeout_handling(self, parser):
        """Test handling of fetch timeout."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.side_effect = TimeoutError("Connection timed out")

            with pytest.raises(SitemapParseError) as exc_info:
                await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, parser):
        """Test handling of connection errors."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("Failed to connect")

            with pytest.raises(SitemapParseError) as exc_info:
                await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert "connection" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_404_handling(self, parser):
        """Test handling of 404 responses."""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.side_effect = SitemapParseError("HTTP 404: Not Found")

            with pytest.raises(SitemapParseError) as exc_info:
                await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert "404" in str(exc_info.value)


class TestLargeSitemaps:
    """Tests for handling large sitemaps."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_large_sitemap(self, parser):
        """Test parsing a sitemap with many URLs."""
        # Generate a large sitemap (1000 URLs)
        url_entries = "\n".join(
            f"  <url><loc>https://example.com/product/{i}</loc></url>"
            for i in range(1000)
        )
        large_sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_entries}
</urlset>
"""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = large_sitemap

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.total_urls == 1000
            assert len(result.urls) == 1000


class TestDateParsing:
    """Tests for date format parsing."""

    @pytest.fixture
    def parser(self):
        """Create a SitemapParser instance."""
        return SitemapParser()

    @pytest.mark.asyncio
    async def test_parse_date_formats(self, parser):
        """Test parsing various date formats."""
        sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2024-01-15</lastmod>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
    <lastmod>2024-01-15T10:30:00Z</lastmod>
  </url>
  <url>
    <loc>https://example.com/page3</loc>
    <lastmod>2024-01-15T10:30:00+00:00</lastmod>
  </url>
</urlset>
"""
        with patch.object(parser, "_fetch_sitemap_content") as mock_fetch:
            mock_fetch.return_value = sitemap

            result = await parser.parse_sitemap("https://example.com/sitemap.xml")

            assert result.total_urls == 3
            # All dates should be successfully parsed
            for url in result.urls:
                assert url.lastmod is not None
                assert url.lastmod.year == 2024
                assert url.lastmod.month == 1
                assert url.lastmod.day == 15
