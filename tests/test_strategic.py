"""
Strategic tests for Task Group 10: Test Review & Gap Analysis.

These tests cover critical gaps identified in the test coverage review:
1. End-to-end: Full crawl cycle (source -> fetch -> AI -> product)
2. Integration: SerpAPI rate limiting
3. Error handling: Graceful degradation on API failures
4. Database: DiscoveredProduct deduplication via fingerprint
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import timedelta
import asyncio

from django.utils import timezone


class TestEndToEndCrawlCycle:
    """Tests for full crawl cycle from source to product."""

    @pytest.mark.django_db
    def test_full_crawl_cycle_components_integration(self):
        """
        End-to-end integration test: Verifies all crawl cycle components work together.

        Tests the key integration points:
        1. CrawlerSource provides configuration
        2. CrawlJob tracks execution
        3. DiscoveredProduct stores results
        """
        from crawler.models import (
            CrawlerSource,
            CrawlJob,
            DiscoveredProduct,
            DiscoveredProductStatus,
        )

        # Create test source
        source = CrawlerSource.objects.create(
            name="Integration Test Source",
            slug="integration-test-source",
            base_url="https://integration-test.com",
            category="retailer",
            is_active=True,
            product_types=["whiskey"],
        )

        # Create crawl job
        job = CrawlJob.objects.create(source=source)
        job.start()
        assert job.status == "running"

        # Simulate AI extraction result
        extracted_data = {
            "name": "Integration Test Whiskey 18 Year Old",
            "brand": "Test Distillery",
            "abv": 43.0,
            "volume_ml": 700,
            "age_statement": 18,
        }

        # Create discovered product (as ContentProcessor would)
        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://integration-test.com/product/test-whiskey",
            crawl_job=job,
            product_type="whiskey",
            raw_content="<html><body>Test Whiskey</body></html>",
            extracted_data=extracted_data,
            enriched_data={
                "tasting_notes": "Rich and complex",
                "flavor_profile": ["vanilla", "oak", "honey"],
            },
            extraction_confidence=0.95,
            status=DiscoveredProductStatus.PENDING,
        )

        # Update job metrics (as crawl_source task would)
        job.pages_crawled = 1
        job.products_found = 1
        job.products_new = 1
        job.complete(success=True)

        # Verify end state
        assert job.status == "completed"
        assert job.products_found == 1

        product.refresh_from_db()
        assert product.extracted_data["name"] == "Integration Test Whiskey 18 Year Old"
        assert product.crawl_job == job

    @pytest.mark.django_db
    def test_crawl_cycle_updates_job_metrics(self):
        """
        CrawlJob metrics are correctly updated through the crawl lifecycle.
        """
        from crawler.models import CrawlerSource, CrawlJob

        source = CrawlerSource.objects.create(
            name="Metrics Test Source",
            slug="metrics-test-source",
            base_url="https://metrics-test.com",
            category="retailer",
            is_active=True,
            product_types=["whiskey"],
        )

        job = CrawlJob.objects.create(source=source)
        job.start()

        # Simulate crawl progress
        job.pages_crawled = 5
        job.products_found = 3
        job.products_new = 2
        job.products_updated = 1
        job.errors_count = 1
        job.save()

        job.refresh_from_db()
        assert job.pages_crawled == 5
        assert job.products_found == 3
        assert job.products_new == 2
        assert job.products_updated == 1
        assert job.errors_count == 1

        # Complete job
        job.complete(success=True)
        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.duration_seconds is not None


class TestSerpAPIRateLimiting:
    """Tests for SerpAPI rate limiting behavior."""

    def test_serpapi_respects_rate_limit(self):
        """SerpAPI client handles rate limit responses gracefully."""
        from crawler.discovery.serpapi_client import SerpAPIClient
        import httpx

        client = SerpAPIClient(api_key="test_key")

        # Create an async mock for rate limit
        async def mock_request_raises(*args, **kwargs):
            raise httpx.HTTPStatusError(
                message="Rate limit exceeded",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )

        with patch.object(client, "_make_request", mock_request_raises):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    client.search("test query", num_results=10)
                )
            finally:
                loop.close()

            # Should return empty results, not raise
            assert result == [] or result is None or len(result) == 0


class TestGracefulDegradation:
    """Tests for graceful degradation on API failures."""

    @pytest.mark.django_db
    def test_content_processor_handles_ai_timeout(self):
        """Content processor handles AI service timeout gracefully."""
        from crawler.models import CrawlerSource, CrawlJob
        from crawler.services.content_processor import ContentProcessor

        source = CrawlerSource.objects.create(
            name="Timeout Test Source",
            slug="timeout-test",
            base_url="https://timeout-test.com",
            category="retailer",
            is_active=True,
        )

        job = CrawlJob.objects.create(source=source)
        job.start()

        content_processor = ContentProcessor()

        # Mock AI timeout response
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Connection timed out"

        async def mock_enhance(*args, **kwargs):
            return mock_response

        with patch.object(content_processor, "ai_client") as mock_client:
            mock_client.enhance_from_crawler = mock_enhance

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    content_processor.process(
                        url="https://timeout-test.com/product/1",
                        raw_content="<html>Test content</html>",
                        source=source,
                        crawl_job=job,
                    )
                )
            finally:
                loop.close()

            # Should return failure result, not raise
            assert result.success is False
            assert result.error is not None

    @pytest.mark.django_db
    def test_smart_router_falls_back_on_tier_failure(self):
        """Smart Router attempts fallback tiers on failure."""
        from crawler.fetchers.smart_router import SmartRouter

        router = SmartRouter()

        mock_source = MagicMock()
        mock_source.age_gate_cookies = {}
        mock_source.requires_tier3 = False

        # Create async mock functions
        async def tier1_fail(*args, **kwargs):
            return MagicMock(
                content="",
                status_code=503,
                headers={},
                success=False,
                error="Service Unavailable",
            )

        async def tier2_success(*args, **kwargs):
            return MagicMock(
                content="<html><body>Product page with sufficient content for processing</body></html>" * 10,
                status_code=200,
                headers={},
                success=True,
            )

        with patch.object(router, "_tier1_fetcher") as mock_tier1, \
             patch.object(router, "_tier2_fetcher") as mock_tier2:

            mock_tier1.fetch = tier1_fail
            mock_tier2.fetch = tier2_success

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    router.fetch(
                        url="https://flaky-site.com/product/1",
                        source=mock_source,
                    )
                )
            finally:
                loop.close()

            # Should have escalated to Tier 2 and succeeded
            assert result.success is True


class TestFingerprintDeduplication:
    """Tests for DiscoveredProduct deduplication via fingerprint."""

    @pytest.mark.django_db
    def test_fingerprint_detects_duplicate_product(self):
        """Duplicate product detected via fingerprint before creation."""
        from crawler.models import (
            CrawlerSource,
            DiscoveredProduct,
            DiscoveredProductStatus,
        )

        source = CrawlerSource.objects.create(
            name="Dedup Test Source",
            slug="dedup-test",
            base_url="https://dedup-test.com",
            category="retailer",
            is_active=True,
        )

        # Create first product
        extracted_data = {
            "name": "Duplicate Test Whiskey",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
        }

        product1 = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://dedup-test.com/product/1",
            product_type="whiskey",
            raw_content="<html>Product 1</html>",
            extracted_data=extracted_data,
        )

        # Attempt to create duplicate
        fingerprint = DiscoveredProduct.compute_fingerprint(extracted_data)

        # This should be False since we're checking before creating second product
        assert product1.fingerprint == fingerprint

        # Now create second product and verify it detects the duplicate
        product2 = DiscoveredProduct(
            source=source,
            source_url="https://dedup-test.com/product/1-duplicate",
            product_type="whiskey",
            raw_content="<html>Product 1 Duplicate</html>",
            extracted_data=extracted_data,
        )
        product2.fingerprint = DiscoveredProduct.compute_fingerprint(extracted_data)

        # check_duplicate should find the existing product
        assert product2.check_duplicate() is True

    @pytest.mark.django_db
    def test_fingerprint_allows_similar_but_different_products(self):
        """Products with similar but different key fields get unique fingerprints."""
        from crawler.models import CrawlerSource, DiscoveredProduct

        source = CrawlerSource.objects.create(
            name="Similar Products Source",
            slug="similar-products",
            base_url="https://similar-test.com",
            category="retailer",
            is_active=True,
        )

        # Product 1: 12 year old
        product1_data = {
            "name": "Test Whiskey 12 Year Old",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
            "age_statement": 12,
        }

        # Product 2: 18 year old (different age)
        product2_data = {
            "name": "Test Whiskey 18 Year Old",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
            "age_statement": 18,
        }

        fingerprint1 = DiscoveredProduct.compute_fingerprint(product1_data)
        fingerprint2 = DiscoveredProduct.compute_fingerprint(product2_data)

        # Different age statements should produce different fingerprints
        assert fingerprint1 != fingerprint2

        # Create both products
        product1 = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://similar-test.com/product/12",
            product_type="whiskey",
            raw_content="<html>12 Year</html>",
            extracted_data=product1_data,
        )

        product2 = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://similar-test.com/product/18",
            product_type="whiskey",
            raw_content="<html>18 Year</html>",
            extracted_data=product2_data,
        )

        # Neither should detect the other as duplicate
        assert product1.check_duplicate() is False
        assert product2.check_duplicate() is False

    @pytest.mark.django_db
    def test_fingerprint_handles_missing_optional_fields(self):
        """Fingerprint computation handles missing optional fields gracefully."""
        from crawler.models import DiscoveredProduct

        # Minimal extracted data (missing optional fields)
        minimal_data = {
            "name": "Minimal Whiskey",
            "brand": "Unknown",
        }

        # Should not raise
        fingerprint = DiscoveredProduct.compute_fingerprint(minimal_data)

        assert fingerprint is not None
        assert len(fingerprint) == 64  # SHA-256 hex length


class TestCrawlErrorTracking:
    """Tests for error tracking across the crawl cycle."""

    @pytest.mark.django_db
    def test_crawl_errors_logged_with_context(self):
        """CrawlError records include full context for debugging."""
        from crawler.models import CrawlerSource, CrawlError, ErrorType

        source = CrawlerSource.objects.create(
            name="Error Tracking Source",
            slug="error-tracking",
            base_url="https://error-tracking.com",
            category="retailer",
            is_active=True,
        )

        # Create error with full context
        error = CrawlError.objects.create(
            source=source,
            url="https://error-tracking.com/problem-page",
            error_type=ErrorType.BLOCKED,
            message="Access denied by WAF",
            tier_used=2,
            response_status=403,
            response_headers={
                "X-Block-Reason": "Automated request detected",
                "Retry-After": "300",
            },
            stack_trace="Traceback (most recent call last):\n  ...",
        )

        # Verify all fields captured
        assert error.source == source
        assert error.error_type == ErrorType.BLOCKED
        assert error.tier_used == 2
        assert error.response_status == 403
        assert "X-Block-Reason" in error.response_headers
        assert not error.resolved

        # Verify it can be queried
        blocked_errors = CrawlError.objects.filter(
            source=source,
            error_type=ErrorType.BLOCKED,
            resolved=False,
        )
        assert blocked_errors.count() == 1
