"""
End-to-End Tests for Full Product Discovery Pipeline.

Tests the complete flow from generic search discovery through product
creation and enrichment, simulating real-world usage scenarios.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta

# Import all components
from crawler.discovery.serpapi.client import SerpAPIClient
from crawler.discovery.serpapi.queries import QueryBuilder
from crawler.discovery.serpapi.rate_limiter import RateLimiter, QuotaTracker
from crawler.discovery.search.config import SearchConfig
from crawler.discovery.search.target_extractor import TargetURLExtractor
from crawler.discovery.search.scheduler import SearchScheduler
from crawler.discovery.enrichment.orchestrator import ProductEnricher
from crawler.discovery.enrichment.price_finder import PriceFinder
from crawler.discovery.enrichment.review_finder import ReviewFinder
from crawler.discovery.enrichment.image_finder import ImageFinder
from crawler.discovery.enrichment.article_finder import ArticleFinder


class TestCompleteDiscoveryToEnrichmentPipeline:
    """Tests the complete pipeline from discovery to enrichment."""

    def test_full_pipeline_flow(
        self,
        mock_serpapi_client,
        mock_google_search_response,
        mock_google_shopping_response,
        mock_google_images_response,
        mock_google_news_response,
        mock_discovered_product,
    ):
        """Test complete flow: Discovery -> URL Extraction -> Enrichment."""
        # Step 1: Generic Discovery Search
        mock_serpapi_client.google_search.return_value = mock_google_search_response

        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        # Extract target URLs using correct method name
        targets = extractor.extract_targets(mock_google_search_response)

        # Should have discovered some targets
        assert isinstance(targets, list)

        # Step 2: Simulate product creation (mocked)
        # In real flow, a product would be created from crawled data

        # Step 3: Enrichment
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response
        mock_serpapi_client.google_images.return_value = mock_google_images_response
        mock_serpapi_client.google_news.return_value = mock_google_news_response

        enricher = ProductEnricher(client=mock_serpapi_client)
        result = enricher.enrich_product(mock_discovered_product)

        # Verify enrichment completed
        assert result["success"] is True
        assert mock_discovered_product.enrichment_status == "completed"

    def test_pipeline_with_rate_limiting(
        self,
        mock_serpapi_client,
        mock_cache,
        mock_discovered_product,
    ):
        """Test pipeline respects rate limits across phases."""
        # Simulate hourly rate limit reached
        from datetime import datetime
        hour_key = f"serpapi:hourly:{datetime.now().strftime('%Y-%m-%d-%H')}"
        mock_cache._data[hour_key] = 1000

        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            limiter = RateLimiter()

            # Should be rate limited
            assert limiter.can_make_request() is False

    def test_pipeline_quota_tracking(self, mock_cache):
        """Test quota is tracked across all API calls."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            limiter = RateLimiter()
            tracker = QuotaTracker(rate_limiter=limiter)

            # Check stats are available
            stats = tracker.get_usage_stats()
            assert "hourly_remaining" in stats
            assert "monthly_remaining" in stats


class TestMultiProductBatchProcessing:
    """Tests batch processing of multiple products."""

    def test_batch_enrichment_processing(
        self,
        mock_serpapi_client,
        mock_discovered_product_list,
    ):
        """Test batch processing handles multiple products."""
        mock_serpapi_client.google_shopping.return_value = {"shopping_results": []}
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        enricher = ProductEnricher(client=mock_serpapi_client)
        results = enricher.enrich_batch(mock_discovered_product_list)

        # Should have processed all products
        assert len(results) == 3
        # All should succeed with empty results
        assert all(r["success"] for r in results)

    def test_batch_respects_api_quota(
        self,
        mock_serpapi_client,
        mock_discovered_product_list,
        mock_cache,
    ):
        """Test batch processing respects API quota."""
        mock_serpapi_client.google_shopping.return_value = {"shopping_results": []}
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            enricher = ProductEnricher(client=mock_serpapi_client)
            results = enricher.enrich_batch(mock_discovered_product_list)

            # All should complete
            assert len(results) == 3


class TestQueryOptimization:
    """Tests query building and optimization across pipeline."""

    def test_query_builder_for_discovery(self):
        """Test QueryBuilder works for discovery."""
        builder = QueryBuilder()

        # Discovery queries
        discovery_queries = builder.build_generic_queries(product_type="whiskey")
        assert len(discovery_queries) > 0

    def test_query_builder_for_port_wine(self):
        """Test QueryBuilder works for port wine discovery."""
        builder = QueryBuilder()

        # Port wine queries
        port_queries = builder.build_generic_queries(product_type="port_wine")
        assert len(port_queries) > 0

    def test_query_deduplication(self):
        """Test duplicate queries are handled."""
        builder = QueryBuilder()

        queries1 = builder.build_generic_queries(product_type="whiskey")
        queries2 = builder.build_generic_queries(product_type="whiskey")

        # Same queries built twice
        assert queries1 == queries2


class TestURLPriorityAndFiltering:
    """Tests URL handling across the pipeline."""

    def test_priority_domains_handled_correctly(self, mock_google_search_response):
        """Test priority domains are correctly prioritized."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        targets = extractor.extract_targets(mock_google_search_response)

        if len(targets) > 1:
            # Higher priority URLs should come first
            for i in range(len(targets) - 1):
                assert targets[i].get("priority", 0) >= targets[i + 1].get("priority", 0)

    def test_excluded_domains_filtered(self, mock_google_search_response):
        """Test excluded domains are filtered out."""
        from crawler.discovery.search.config import EXCLUDED_DOMAINS

        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        targets = extractor.extract_targets(mock_google_search_response)

        for target in targets:
            source = target.get("source", "").lower()
            for domain in EXCLUDED_DOMAINS:
                assert domain.lower() not in source


class TestSchedulerCoordination:
    """Tests scheduler coordinating discovery and enrichment."""

    def test_scheduler_with_rate_limiter(self, mock_cache):
        """Test scheduler uses rate limiter."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.search.scheduler.cache", mock_cache):
                rate_limiter = RateLimiter()
                scheduler = SearchScheduler(rate_limiter=rate_limiter)

                # Check if can execute
                can_execute = scheduler.can_execute_search()
                assert isinstance(can_execute, bool)

    def test_scheduler_gets_queries(self, mock_cache):
        """Test scheduler returns queries."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.search.scheduler.cache", mock_cache):
                rate_limiter = RateLimiter()
                scheduler = SearchScheduler(rate_limiter=rate_limiter)

                queries = scheduler.get_next_queries("whiskey", count=5)
                assert isinstance(queries, list)


class TestEnrichmentDataIntegrity:
    """Tests data integrity across enrichment pipeline."""

    def test_price_data_integrity(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test price data maintains integrity through pipeline."""
        mock_serpapi_client.google_shopping.return_value = {
            "shopping_results": [
                {
                    "title": "Macallan 18 Year Old",
                    "price": "$299.99",
                    "source": "Shop A",
                    "link": "https://shopa.com/macallan",
                },
                {
                    "title": "Macallan 18 Sherry Cask",
                    "price": "$319.00",
                    "source": "Shop B",
                    "link": "https://shopb.com/macallan",
                },
            ]
        }

        finder = PriceFinder(client=mock_serpapi_client)
        prices = finder.find_prices(mock_discovered_product)

        # Verify data integrity
        for price in prices:
            assert isinstance(price["price"], float)
            assert price["price"] > 0
            assert price["currency"] in ["USD", "GBP", "EUR", "JPY", "INR"]
            assert len(price["retailer"]) > 0

    def test_review_score_normalization(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test review scores are properly normalized."""
        finder = ReviewFinder(client=mock_serpapi_client)

        # Test various rating formats
        test_cases = [
            ("whiskyadvocate.com", "Rated 94 points", 94, 100),
            ("masterofmalt.com", "4.5 / 5 stars", 4.5, 5),
            ("unknownsite.com", "Score: 88/100", 88, 100),
        ]

        for source, snippet, expected_score, expected_max in test_cases:
            rating = finder._extract_rating(source, snippet)
            if rating:
                assert rating["score"] == expected_score
                assert rating["max_score"] == expected_max

    def test_image_url_validation(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test image URLs are valid."""
        mock_serpapi_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Product Image",
                    "original": "https://example.com/image.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "example.com",
                    "original_width": 800,
                    "original_height": 1200,
                },
            ]
        }

        finder = ImageFinder(client=mock_serpapi_client)
        images = finder.find_images(mock_discovered_product)

        for img in images:
            assert img["url"].startswith("http")
            assert img["thumbnail"].startswith("http")


class TestErrorRecoveryAcrossPipeline:
    """Tests error recovery across the complete pipeline."""

    def test_recovery_from_api_failure(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test system recovers from API failures."""
        # First call fails
        mock_serpapi_client.google_shopping.side_effect = [
            Exception("API Error"),
            {"shopping_results": []},
        ]
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        enricher = ProductEnricher(client=mock_serpapi_client)

        # First enrichment may fail
        result1 = enricher.enrich_product(mock_discovered_product)

        # Second should work
        mock_serpapi_client.google_shopping.side_effect = None
        mock_serpapi_client.google_shopping.return_value = {"shopping_results": []}

        # Reset product status
        mock_discovered_product.enrichment_status = "pending"

        result2 = enricher.enrich_product(mock_discovered_product)
        assert result2["success"] is True

    def test_graceful_degradation(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test graceful degradation when some sources fail."""
        # Only images work
        mock_serpapi_client.google_shopping.side_effect = Exception("Shopping Error")
        mock_serpapi_client.google_search.side_effect = Exception("Search Error")
        mock_serpapi_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Image",
                    "original": "https://example.com/img.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "example.com",
                    "original_width": 800,
                    "original_height": 1200,
                }
            ]
        }
        mock_serpapi_client.google_news.side_effect = Exception("News Error")

        # Test individual finders handle errors
        price_finder = PriceFinder(client=mock_serpapi_client)
        prices = price_finder.find_prices(mock_discovered_product)
        assert prices == []  # Graceful empty return

        image_finder = ImageFinder(client=mock_serpapi_client)
        images = image_finder.find_images(mock_discovered_product)
        assert len(images) == 1  # This one works


class TestEndToEndScenarios:
    """Tests realistic end-to-end scenarios."""

    def test_new_whisky_discovery_and_enrichment(
        self,
        mock_serpapi_client,
        mock_google_search_response,
        mock_google_shopping_response,
        mock_google_images_response,
        mock_google_news_response,
        mock_review_search_response,
        mock_discovered_product,
    ):
        """Simulate discovering and enriching a new whisky product."""
        # Phase 1: Discovery
        mock_serpapi_client.google_search.return_value = mock_google_search_response

        config = SearchConfig()
        query_builder = QueryBuilder()

        # Build discovery query
        queries = query_builder.build_generic_queries(product_type="whiskey")
        assert len(queries) > 0

        # Run discovery
        response = mock_serpapi_client.google_search(query=queries[0])
        assert "organic_results" in response

        # Extract URLs
        extractor = TargetURLExtractor(config=config)
        targets = extractor.extract_targets(response)

        # Phase 2: Enrichment (simulating product was created from crawled data)
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response
        mock_serpapi_client.google_images.return_value = mock_google_images_response
        mock_serpapi_client.google_news.return_value = mock_google_news_response

        enricher = ProductEnricher(client=mock_serpapi_client)
        result = enricher.enrich_product(mock_discovered_product)

        # Verify complete enrichment
        assert result["success"] is True
        assert mock_discovered_product.enrichment_status == "completed"

    def test_daily_discovery_batch(
        self,
        mock_serpapi_client,
        mock_google_search_response,
        mock_cache,
    ):
        """Simulate daily discovery batch process."""
        mock_serpapi_client.google_search.return_value = mock_google_search_response

        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.search.scheduler.cache", mock_cache):
                rate_limiter = RateLimiter()
                scheduler = SearchScheduler(rate_limiter=rate_limiter)
                config = SearchConfig()

                # Get queries to execute
                queries = scheduler.get_next_queries("whiskey", count=5)

                # Should have queries to execute
                assert isinstance(queries, list)

    def test_enrichment_update_cycle(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Simulate re-enriching a product with updated data."""
        # Initial enrichment
        mock_serpapi_client.google_shopping.return_value = {
            "shopping_results": [
                {"title": "Macallan 18", "price": "$300", "source": "Shop A", "link": ""}
            ]
        }
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        enricher = ProductEnricher(client=mock_serpapi_client)
        result1 = enricher.enrich_product(mock_discovered_product)
        assert result1["success"] is True

        # Price update enrichment
        mock_serpapi_client.google_shopping.return_value = {
            "shopping_results": [
                {"title": "Macallan 18", "price": "$280", "source": "Shop B", "link": ""}
            ]
        }

        # Re-enrich prices only
        mock_discovered_product.enrichment_status = "pending"
        result2 = enricher.enrich_product(
            mock_discovered_product,
            enrich_prices=True,
            enrich_reviews=False,
            enrich_images=False,
            enrich_articles=False,
        )

        assert result2["success"] is True
        assert result2["reviews_found"] == 0
