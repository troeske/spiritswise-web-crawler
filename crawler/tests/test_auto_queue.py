"""
Tests for Auto-Queue Integration Service.

Tests the integration between link extraction and URL frontier for automated
link discovery and queueing during crawling.
"""

import pytest
from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import re


@dataclass
class MockExtractedLink:
    """Mock extracted link for testing."""
    url: str
    text: str = ""
    link_type: str = "unknown"
    is_internal: bool = True
    is_product: bool = False
    is_category: bool = False
    is_pagination: bool = False


class TestAutoQueueServiceExtraction:
    """Tests for extracting and queuing links from crawled pages."""

    @pytest.mark.asyncio
    async def test_process_crawled_page_extracts_links(self, db):
        """AutoQueueService extracts links from HTML content."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Test Source",
            slug="test-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
            product_url_patterns=[r"/product/\d+"],
        )

        html = """
        <html>
        <body>
            <a href="https://example.com/product/123">Product 1</a>
            <a href="https://example.com/product/456">Product 2</a>
            <a href="https://example.com/category/whiskey">Whiskey Category</a>
        </body>
        </html>
        """

        # Mock the frontier
        mock_frontier = MagicMock()
        mock_frontier.add_url = MagicMock(return_value=True)
        mock_frontier.is_url_seen = MagicMock(return_value=False)

        # Mock link extractor
        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(
                url="https://example.com/product/123",
                text="Product 1",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
            MockExtractedLink(
                url="https://example.com/product/456",
                text="Product 2",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
            MockExtractedLink(
                url="https://example.com/category/whiskey",
                text="Whiskey Category",
                link_type="category",
                is_internal=True,
                is_category=True,
            ),
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        result = await service.process_crawled_page(
            url="https://example.com/",
            html=html,
            source=source,
            current_depth=0,
        )

        assert result.total_links_found == 3
        assert result.product_links == 2

    @pytest.mark.asyncio
    async def test_process_crawled_page_respects_disabled_auto_discover(self, db):
        """AutoQueueService does not queue links when auto_discover_links=False."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="No Auto Discover",
            slug="no-auto-discover",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=False,
        )

        html = "<html><body><a href='/product/123'>Product</a></body></html>"

        mock_frontier = MagicMock()
        mock_link_extractor = MagicMock()

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        result = await service.process_crawled_page(
            url="https://example.com/",
            html=html,
            source=source,
            current_depth=0,
        )

        assert result.queued_links == 0
        mock_frontier.add_url.assert_not_called()


class TestCrawlDepthLimits:
    """Tests for respecting crawl depth limits."""

    @pytest.mark.asyncio
    async def test_respects_max_crawl_depth(self, db):
        """AutoQueueService respects max_crawl_depth configuration."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Depth Limited Source",
            slug="depth-limited",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
            max_crawl_depth=2,
        )

        html = "<html><body><a href='/product/123'>Product</a></body></html>"

        mock_frontier = MagicMock()
        mock_frontier.add_url = MagicMock(return_value=True)
        mock_frontier.is_url_seen = MagicMock(return_value=False)

        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(
                url="https://example.com/product/123",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        # At depth 3, should not queue (exceeds max_crawl_depth=2)
        result = await service.process_crawled_page(
            url="https://example.com/deep/page",
            html=html,
            source=source,
            current_depth=3,
        )

        assert result.queued_links == 0
        assert result.filtered_links >= 1

    @pytest.mark.asyncio
    async def test_allows_links_within_depth_limit(self, db):
        """AutoQueueService allows links when within depth limit."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Depth Allowed",
            slug="depth-allowed",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
            max_crawl_depth=3,
        )

        mock_frontier = MagicMock()
        mock_frontier.add_url = MagicMock(return_value=True)
        mock_frontier.is_url_seen = MagicMock(return_value=False)

        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(
                url="https://example.com/product/123",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        # At depth 1, should queue (within max_crawl_depth=3)
        result = await service.process_crawled_page(
            url="https://example.com/page",
            html="<html></html>",
            source=source,
            current_depth=1,
        )

        assert result.queued_links >= 1


class TestPriorityAssignment:
    """Tests for priority assignment based on link type."""

    def test_product_page_priority(self):
        """Product pages get priority 8."""
        from crawler.services.auto_queue_service import AutoQueueService

        mock_link = MockExtractedLink(
            url="https://example.com/product/123",
            link_type="product",
            is_product=True,
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        source = MagicMock()
        source.product_url_patterns = [r"/product/\d+"]

        priority = service.calculate_priority(mock_link, source)
        assert priority == 8

    def test_category_page_priority(self):
        """Category pages get priority 6."""
        from crawler.services.auto_queue_service import AutoQueueService

        mock_link = MockExtractedLink(
            url="https://example.com/category/whiskey",
            link_type="category",
            is_category=True,
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        priority = service.calculate_priority(mock_link, MagicMock())
        assert priority == 6

    def test_pagination_priority(self):
        """Pagination links get priority 5."""
        from crawler.services.auto_queue_service import AutoQueueService

        mock_link = MockExtractedLink(
            url="https://example.com/products?page=2",
            link_type="pagination",
            is_pagination=True,
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        priority = service.calculate_priority(mock_link, MagicMock())
        assert priority == 5

    def test_related_product_priority(self):
        """Related product links get priority 9."""
        from crawler.services.auto_queue_service import AutoQueueService

        mock_link = MockExtractedLink(
            url="https://example.com/product/789",
            link_type="related",
            is_product=True,
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        priority = service.calculate_priority(mock_link, MagicMock())
        assert priority == 9

    def test_external_link_priority(self):
        """External links get priority 3."""
        from crawler.services.auto_queue_service import AutoQueueService

        mock_link = MockExtractedLink(
            url="https://other-site.com/article",
            link_type="unknown",
            is_internal=False,
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        priority = service.calculate_priority(mock_link, MagicMock())
        assert priority == 3


class TestDeduplication:
    """Tests for deduplication against already crawled URLs."""

    @pytest.mark.asyncio
    async def test_filters_already_seen_urls(self, db):
        """AutoQueueService filters URLs already in the frontier."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Dedup Test",
            slug="dedup-test",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
        )

        mock_frontier = MagicMock()
        # First URL is seen, second is not
        mock_frontier.is_url_seen = MagicMock(side_effect=[True, False])
        mock_frontier.add_url = MagicMock(return_value=True)

        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(
                url="https://example.com/product/123",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
            MockExtractedLink(
                url="https://example.com/product/456",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        result = await service.process_crawled_page(
            url="https://example.com/",
            html="<html></html>",
            source=source,
            current_depth=0,
        )

        assert result.duplicate_links == 1
        assert result.queued_links == 1


class TestFrontierIntegration:
    """Tests for integration with URLFrontier."""

    @pytest.mark.asyncio
    async def test_adds_links_to_frontier_with_priority(self, db):
        """AutoQueueService adds links to frontier with correct priority."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource, CrawlJob

        source = CrawlerSource.objects.create(
            name="Frontier Test",
            slug="frontier-test",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
        )

        crawl_job = CrawlJob.objects.create(source=source)

        mock_frontier = MagicMock()
        mock_frontier.is_url_seen = MagicMock(return_value=False)
        mock_frontier.add_url = MagicMock(return_value=True)

        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(
                url="https://example.com/product/123",
                link_type="product",
                is_internal=True,
                is_product=True,
            ),
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        await service.process_crawled_page(
            url="https://example.com/",
            html="<html></html>",
            source=source,
            current_depth=0,
        )

        # Verify add_url was called with correct parameters
        mock_frontier.add_url.assert_called()
        call_args = mock_frontier.add_url.call_args
        assert call_args.kwargs.get("priority") == 8  # Product priority
        assert "example.com/product/123" in call_args.kwargs.get("url", "")

    @pytest.mark.asyncio
    async def test_queue_discovered_links_returns_count(self, db):
        """queue_discovered_links returns number of URLs queued."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource, CrawlJob

        source = CrawlerSource.objects.create(
            name="Queue Count Test",
            slug="queue-count-test",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
        )

        crawl_job = CrawlJob.objects.create(source=source)

        mock_frontier = MagicMock()
        mock_frontier.is_url_seen = MagicMock(return_value=False)
        # First two succeed, third fails (already seen)
        mock_frontier.add_url = MagicMock(side_effect=[True, True, False])

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=mock_frontier,
        )

        links = [
            MockExtractedLink(url="https://example.com/product/1", is_internal=True),
            MockExtractedLink(url="https://example.com/product/2", is_internal=True),
            MockExtractedLink(url="https://example.com/product/3", is_internal=True),
        ]

        count = await service.queue_discovered_links(
            links=links,
            source=source,
            crawl_job=crawl_job,
        )

        assert count == 2


class TestSourcePatternMatching:
    """Tests for source-specific pattern matching."""

    def test_should_queue_matches_product_patterns(self, db):
        """should_queue_link matches against product_url_patterns."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Pattern Test",
            slug="pattern-test",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            product_url_patterns=[
                r"/whiskey/[a-z-]+$",
                r"/product/\d+",
            ],
        )

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        # Should match first pattern
        link1 = MockExtractedLink(
            url="https://example.com/whiskey/glenfiddich-18",
            is_internal=True,
        )
        assert service.should_queue_link(link1, source) is True

        # Should match second pattern
        link2 = MockExtractedLink(
            url="https://example.com/product/12345",
            is_internal=True,
        )
        assert service.should_queue_link(link2, source) is True

        # Should not match (internal but no pattern match)
        link3 = MockExtractedLink(
            url="https://example.com/about-us",
            is_internal=True,
        )
        # Internal links are still queued even without pattern match
        assert service.should_queue_link(link3, source) is True

    def test_should_queue_rejects_external_non_product_links(self):
        """should_queue_link rejects external links that are not products."""
        from crawler.services.auto_queue_service import AutoQueueService

        service = AutoQueueService(
            link_extractor=MagicMock(),
            frontier=MagicMock(),
        )

        mock_source = MagicMock()
        mock_source.product_url_patterns = []
        mock_source.base_url = "https://example.com"

        link = MockExtractedLink(
            url="https://other-site.com/random-page",
            is_internal=False,
        )

        assert service.should_queue_link(link, mock_source) is False


class TestAutoQueueResult:
    """Tests for AutoQueueResult dataclass."""

    def test_auto_queue_result_fields(self):
        """AutoQueueResult has all required fields."""
        from crawler.services.auto_queue_service import AutoQueueResult

        result = AutoQueueResult(
            total_links_found=10,
            product_links=5,
            queued_links=4,
            filtered_links=2,
            duplicate_links=1,
            links_by_type={"product": 5, "category": 3, "pagination": 2},
        )

        assert result.total_links_found == 10
        assert result.product_links == 5
        assert result.queued_links == 4
        assert result.filtered_links == 2
        assert result.duplicate_links == 1
        assert result.links_by_type["product"] == 5


class TestRateLimiting:
    """Tests for rate limiting in URL discovery."""

    @pytest.mark.asyncio
    async def test_respects_max_pages_limit(self, db):
        """AutoQueueService respects source max_pages configuration."""
        from crawler.services.auto_queue_service import AutoQueueService
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Max Pages Test",
            slug="max-pages-test",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            auto_discover_links=True,
            max_pages=50,
        )

        # Mock frontier to report 45 pages already in queue
        mock_frontier = MagicMock()
        mock_frontier.get_queue_size = MagicMock(return_value=45)
        mock_frontier.get_seen_count = MagicMock(return_value=45)
        mock_frontier.is_url_seen = MagicMock(return_value=False)
        mock_frontier.add_url = MagicMock(return_value=True)

        # 10 links found, but only 5 should be queued to stay under max_pages
        mock_link_extractor = MagicMock()
        mock_link_extractor.extract_links = MagicMock(return_value=[
            MockExtractedLink(url=f"https://example.com/product/{i}", is_internal=True)
            for i in range(10)
        ])

        service = AutoQueueService(
            link_extractor=mock_link_extractor,
            frontier=mock_frontier,
        )

        result = await service.process_crawled_page(
            url="https://example.com/",
            html="<html></html>",
            source=source,
            current_depth=0,
        )

        # Should only queue 5 to stay under the 50 max_pages limit
        assert result.queued_links <= 5
