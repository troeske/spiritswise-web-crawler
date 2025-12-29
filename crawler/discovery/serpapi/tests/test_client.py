"""
Tests for SerpAPI Client.

Phase 2: SerpAPI Integration - TDD Tests for client.py
"""

import pytest
import responses
from unittest.mock import patch, MagicMock
from django.test import override_settings

from crawler.discovery.serpapi.client import SerpAPIClient


class TestSerpAPIClientInit:
    """Tests for SerpAPIClient initialization."""

    def test_init_with_api_key(self):
        """Should initialize with provided API key."""
        client = SerpAPIClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    @override_settings(SERPAPI_KEY="settings-key-456")
    def test_init_from_settings(self):
        """Should use API key from settings if not provided."""
        client = SerpAPIClient()
        assert client.api_key == "settings-key-456"

    @override_settings(SERPAPI_KEY="")
    def test_init_raises_without_key(self):
        """Should raise ValueError if no API key configured."""
        with pytest.raises(ValueError, match="SERPAPI_KEY not configured"):
            SerpAPIClient()

    @override_settings(SERPAPI_KEY=None)
    def test_init_raises_with_none_key(self):
        """Should raise ValueError if API key is None."""
        with pytest.raises(ValueError, match="SERPAPI_KEY not configured"):
            SerpAPIClient()


class TestSerpAPIClientGoogleSearch:
    """Tests for google_search method."""

    @responses.activate
    def test_google_search_returns_results(self):
        """Should return parsed search results."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Best Whisky 2025",
                        "link": "https://example.com/best-whisky",
                        "snippet": "Our top picks for whisky.",
                    }
                ]
            },
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        result = client.google_search("best whisky 2025")

        assert "organic_results" in result
        assert len(result["organic_results"]) == 1
        assert result["organic_results"][0]["title"] == "Best Whisky 2025"

    @responses.activate
    def test_google_search_with_num_results(self):
        """Should pass num_results parameter."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"organic_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_search("test query", num_results=20)

        # Check request params
        assert "num=20" in responses.calls[0].request.url

    @responses.activate
    def test_google_search_with_location(self):
        """Should pass location parameter."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"organic_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_search("test query", location="United Kingdom")

        # Check request params include location
        assert "location=United" in responses.calls[0].request.url


class TestSerpAPIClientGoogleShopping:
    """Tests for google_shopping method."""

    @responses.activate
    def test_google_shopping_returns_prices(self):
        """Should return shopping results with prices."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={
                "shopping_results": [
                    {
                        "title": "Glenfiddich 12 Year",
                        "price": "$45.99",
                        "source": "Total Wine",
                        "link": "https://totalwine.com/glenfiddich",
                    }
                ]
            },
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        result = client.google_shopping("glenfiddich 12")

        assert "shopping_results" in result
        assert len(result["shopping_results"]) == 1
        assert result["shopping_results"][0]["price"] == "$45.99"

    @responses.activate
    def test_google_shopping_uses_correct_engine(self):
        """Should use google_shopping engine."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"shopping_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_shopping("whisky")

        assert "engine=google_shopping" in responses.calls[0].request.url


class TestSerpAPIClientGoogleImages:
    """Tests for google_images method."""

    @responses.activate
    def test_google_images_returns_images(self):
        """Should return image results."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={
                "images_results": [
                    {
                        "title": "Whisky Bottle",
                        "original": "https://example.com/bottle.jpg",
                        "thumbnail": "https://example.com/bottle_thumb.jpg",
                        "original_width": 800,
                        "original_height": 1200,
                    }
                ]
            },
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        result = client.google_images("whisky bottle")

        assert "images_results" in result
        assert len(result["images_results"]) == 1
        assert result["images_results"][0]["original"] == "https://example.com/bottle.jpg"

    @responses.activate
    def test_google_images_uses_correct_engine(self):
        """Should use google_images engine."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"images_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_images("whisky")

        assert "engine=google_images" in responses.calls[0].request.url


class TestSerpAPIClientGoogleNews:
    """Tests for google_news method."""

    @responses.activate
    def test_google_news_returns_articles(self):
        """Should return news results."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={
                "news_results": [
                    {
                        "title": "New Whisky Release",
                        "link": "https://news.example.com/whisky",
                        "source": {"name": "Whisky Advocate"},
                        "date": "2 days ago",
                        "snippet": "A new whisky has been released...",
                    }
                ]
            },
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        result = client.google_news("new whisky releases")

        assert "news_results" in result
        assert len(result["news_results"]) == 1
        assert result["news_results"][0]["title"] == "New Whisky Release"

    @responses.activate
    def test_google_news_uses_correct_engine(self):
        """Should use google_news engine."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"news_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_news("whisky news")

        assert "engine=google_news" in responses.calls[0].request.url


class TestSerpAPIClientErrorHandling:
    """Tests for error handling."""

    @responses.activate
    def test_handles_api_error_4xx(self):
        """Should handle 4xx API errors gracefully."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"error": "Invalid API key"},
            status=401,
        )

        client = SerpAPIClient(api_key="invalid-key")

        with pytest.raises(Exception):  # Should raise requests.HTTPError
            client.google_search("test")

    @responses.activate
    def test_handles_api_error_5xx(self):
        """Should handle 5xx server errors."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"error": "Server error"},
            status=500,
        )

        client = SerpAPIClient(api_key="test-key")

        with pytest.raises(Exception):
            client.google_search("test")

    @responses.activate
    def test_handles_timeout(self):
        """Should handle request timeout."""
        import requests

        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        client = SerpAPIClient(api_key="test-key")

        with pytest.raises(requests.exceptions.Timeout):
            client.google_search("test")

    @responses.activate
    def test_handles_connection_error(self):
        """Should handle connection errors."""
        import requests

        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        client = SerpAPIClient(api_key="test-key")

        with pytest.raises(requests.exceptions.ConnectionError):
            client.google_search("test")


class TestSerpAPIClientRequestParams:
    """Tests for request parameter handling."""

    @responses.activate
    def test_includes_api_key_in_request(self):
        """Should include API key in request params."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"organic_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="my-secret-key")
        client.google_search("test")

        assert "api_key=my-secret-key" in responses.calls[0].request.url

    @responses.activate
    def test_passes_extra_kwargs(self):
        """Should pass extra kwargs to request."""
        responses.add(
            responses.GET,
            "https://serpapi.com/search",
            json={"organic_results": []},
            status=200,
        )

        client = SerpAPIClient(api_key="test-key")
        client.google_search("test", gl="uk", hl="en")

        url = responses.calls[0].request.url
        assert "gl=uk" in url
        assert "hl=en" in url
