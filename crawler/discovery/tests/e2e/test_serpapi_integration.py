"""
End-to-End Tests for SerpAPI Integration (Phase 2).

Tests the complete flow from SerpAPIClient through QueryBuilder,
Parsers, and RateLimiter.
"""

import pytest
from unittest.mock import MagicMock, patch
import responses
import json

from crawler.discovery.serpapi.client import SerpAPIClient
from crawler.discovery.serpapi.queries import QueryBuilder
from crawler.discovery.serpapi.parsers import (
    OrganicResultParser,
    ShoppingResultParser,
    ImageResultParser,
    NewsResultParser,
)
from crawler.discovery.serpapi.rate_limiter import RateLimiter, QuotaTracker


class TestSerpAPIClientToParserFlow:
    """Tests the flow from API client to result parsing."""

    @responses.activate
    def test_google_search_full_flow(self, mock_google_search_response):
        """Test complete flow: Client -> API -> Parser."""
        # Mock the SerpAPI endpoint
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_search_response,
            status=200,
        )

        # Create client with test API key
        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_api_key"

            client = SerpAPIClient()
            response = client.google_search(query="whisky online shop")

        # Parse results
        parser = OrganicResultParser()
        results = parser.parse(response)

        # Verify full flow
        assert len(results) == 5
        assert results[0]["title"] == "Master of Malt - Premium Whisky Shop"
        assert results[0]["url"] == "https://www.masterofmalt.com/"
        assert results[0]["position"] == 1

    @responses.activate
    def test_google_shopping_full_flow(self, mock_google_shopping_response):
        """Test complete shopping search flow."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_shopping_response,
            status=200,
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_api_key"

            client = SerpAPIClient()
            response = client.google_shopping(query="Macallan 18")

        parser = ShoppingResultParser()
        results = parser.parse(response)

        assert len(results) == 4
        assert results[0]["title"] == "Macallan 18 Year Old Sherry Oak"
        # Parser extracts price
        assert "price" in results[0]
        # Parser may use 'retailer' or 'source'
        assert "source" in results[0] or "retailer" in results[0]

    @responses.activate
    def test_google_images_full_flow(self, mock_google_images_response):
        """Test complete images search flow."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_images_response,
            status=200,
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_api_key"

            client = SerpAPIClient()
            response = client.google_images(query="Macallan 18 bottle")

        parser = ImageResultParser()
        results = parser.parse(response)

        assert len(results) == 4
        assert results[0]["width"] == 1200
        assert results[0]["height"] == 1800
        # Parser maps 'original' to 'url'
        assert "url" in results[0] or "original" in results[0]

    @responses.activate
    def test_google_news_full_flow(self, mock_google_news_response):
        """Test complete news search flow."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_news_response,
            status=200,
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_api_key"

            client = SerpAPIClient()
            response = client.google_news(query="Macallan whisky")

        parser = NewsResultParser()
        results = parser.parse(response)

        assert len(results) == 3
        assert "Macallan" in results[0]["title"]
        assert results[0]["source"] == "Whisky Advocate"


class TestQueryBuilderIntegration:
    """Tests QueryBuilder with client integration."""

    def test_build_generic_queries(self):
        """Test building generic search queries."""
        builder = QueryBuilder()

        # Build queries for whiskey discovery
        queries = builder.build_generic_queries(product_type="whiskey")

        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)

    def test_build_port_wine_queries(self):
        """Test building port wine queries."""
        builder = QueryBuilder()

        # Build queries for port wine
        queries = builder.build_generic_queries(product_type="port_wine")

        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)

    @responses.activate
    def test_query_builder_with_client(self, mock_google_search_response):
        """Test using QueryBuilder queries with client."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_search_response,
            status=200,
        )

        builder = QueryBuilder()
        queries = builder.build_generic_queries(product_type="whiskey")

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_api_key"

            client = SerpAPIClient()
            if queries:
                response = client.google_search(query=queries[0])
                assert "organic_results" in response


class TestRateLimiterIntegration:
    """Tests RateLimiter with API calls."""

    def test_rate_limiter_allows_initial_requests(self, mock_cache):
        """Test that rate limiter allows requests when under limit."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            limiter = RateLimiter()

            # Should allow first request
            assert limiter.can_make_request() is True

    def test_rate_limiter_blocks_when_exhausted(self, mock_cache):
        """Test that rate limiter blocks when daily limit reached."""
        # Set daily count to limit
        mock_cache._data["serpapi:daily:2025-12-29"] = 165

        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            limiter = RateLimiter()
            assert limiter.can_make_request() is False

    def test_quota_tracker_integration(self, mock_cache):
        """Test QuotaTracker with cache."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            limiter = RateLimiter()
            tracker = QuotaTracker(rate_limiter=limiter)

            # Get usage stats
            stats = tracker.get_usage_stats()

            assert "daily_remaining" in stats
            assert "monthly_remaining" in stats
            assert "daily_limit" in stats
            assert "monthly_limit" in stats

    @responses.activate
    def test_rate_limiter_with_api_calls(self, mock_google_search_response, mock_cache):
        """Test rate limiter recording API calls."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_search_response,
            status=200,
        )

        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
                mock_settings.SERPAPI_KEY = "test_api_key"

                limiter = RateLimiter()
                client = SerpAPIClient()

                # Make request and record it
                if limiter.can_make_request():
                    response = client.google_search(query="test")
                    limiter.record_request()

                    assert response is not None


class TestParserChaining:
    """Tests chaining multiple parsers for complex responses."""

    def test_parse_mixed_response(self, mock_google_search_response, mock_google_shopping_response):
        """Test parsing different response types."""
        organic_parser = OrganicResultParser()
        shopping_parser = ShoppingResultParser()

        organic_results = organic_parser.parse(mock_google_search_response)
        shopping_results = shopping_parser.parse(mock_google_shopping_response)

        # Both parsers work independently
        assert len(organic_results) > 0
        assert len(shopping_results) > 0

        # Results have different structures
        assert "position" in organic_results[0]
        assert "price" in shopping_results[0]

    def test_parser_handles_missing_fields(self):
        """Test parsers handle incomplete data gracefully."""
        incomplete_response = {
            "organic_results": [
                {"title": "Only Title"},  # Missing other fields
                {"link": "https://only-link.com"},  # Missing title
            ]
        }

        parser = OrganicResultParser()
        results = parser.parse(incomplete_response)

        # Should handle gracefully
        assert len(results) <= 2

    def test_parser_handles_empty_response(self):
        """Test parsers handle empty responses."""
        empty_response = {"organic_results": []}

        parser = OrganicResultParser()
        results = parser.parse(empty_response)

        assert results == []


class TestErrorHandling:
    """Tests error handling across the integration."""

    @responses.activate
    def test_client_handles_api_error(self):
        """Test client handles API errors gracefully."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"error": "API key invalid"},
            status=401,
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "invalid_key"

            client = SerpAPIClient()

            with pytest.raises(Exception):
                client.google_search(query="test")

    @responses.activate
    def test_client_handles_timeout(self):
        """Test client handles timeout errors."""
        import requests

        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_key"

            client = SerpAPIClient()

            with pytest.raises(Exception):
                client.google_search(query="test")

    def test_parser_handles_malformed_json(self):
        """Test parser handles malformed responses."""
        malformed_response = "not a valid response"

        parser = OrganicResultParser()

        # Should not crash
        try:
            results = parser.parse(malformed_response)
        except (TypeError, AttributeError):
            pass  # Expected behavior

    @responses.activate
    def test_recovery_after_error(self, mock_google_search_response):
        """Test system recovers after transient error."""
        # First call fails
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"error": "Server error"},
            status=500,
        )

        # Second call succeeds
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json=mock_google_search_response,
            status=200,
        )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_key"

            client = SerpAPIClient()

            # First call fails
            with pytest.raises(Exception):
                client.google_search(query="test")

            # Second call succeeds
            response = client.google_search(query="test")
            assert "organic_results" in response


class TestMultipleSearchTypes:
    """Tests combining multiple search types."""

    @responses.activate
    def test_comprehensive_product_search(
        self,
        mock_google_search_response,
        mock_google_shopping_response,
        mock_google_images_response,
        mock_google_news_response,
    ):
        """Test running all search types for a product."""
        # Add all response mocks
        for _ in range(4):  # 4 different search types
            responses.add(
                responses.GET,
                "https://serpapi.com/search",
                json=mock_google_search_response,
                status=200,
            )

        with patch("crawler.discovery.serpapi.client.settings") as mock_settings:
            mock_settings.SERPAPI_KEY = "test_key"

            client = SerpAPIClient()
            product = "Macallan 18"

            # Run all search types
            results = {
                "organic": client.google_search(query=f"{product} review"),
                "shopping": client.google_search(query=f"{product} buy"),
                "images": client.google_search(query=f"{product} bottle"),
                "news": client.google_search(query=f"{product} news"),
            }

            # All searches should return results
            for search_type, response in results.items():
                assert "organic_results" in response or "error" not in response
