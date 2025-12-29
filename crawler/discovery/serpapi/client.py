"""
SerpAPI Client - HTTP client wrapper for SerpAPI endpoints.

Phase 2: SerpAPI Integration

Provides a unified interface for:
- Google Search (organic results)
- Google Shopping (prices, retailers)
- Google Images (product photos)
- Google News (articles, mentions)
"""

import logging
import requests
from typing import Dict, Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class SerpAPIClient:
    """
    Wrapper for SerpAPI Google Search API.

    Supports multiple search types for comprehensive product discovery:
    - Organic search for reviews and articles
    - Shopping search for prices and retailers
    - Image search for product photos
    - News search for recent articles

    Usage:
        client = SerpAPIClient()
        results = client.google_search("best whisky 2025")
        prices = client.google_shopping("Glenfiddich 12")
    """

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str = None):
        """
        Initialize SerpAPI client.

        Args:
            api_key: SerpAPI API key. If not provided, uses settings.SERPAPI_KEY

        Raises:
            ValueError: If no API key is configured
        """
        self.api_key = api_key or getattr(settings, "SERPAPI_KEY", None)

        if not self.api_key:
            raise ValueError("SERPAPI_KEY not configured")

    def google_search(
        self,
        query: str,
        num_results: int = 10,
        location: str = "United States",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform Google organic search.

        Args:
            query: Search query string
            num_results: Number of results to return (default 10)
            location: Search location for localized results
            **kwargs: Additional SerpAPI parameters (gl, hl, etc.)

        Returns:
            SerpAPI response dictionary with organic_results

        Raises:
            requests.RequestException: On network or API errors
        """
        params = {
            "engine": "google",
            "q": query,
            "num": num_results,
            "location": location,
            "api_key": self.api_key,
            **kwargs,
        }
        return self._make_request(params)

    def google_shopping(
        self,
        query: str,
        num_results: int = 20,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform Google Shopping search for prices.

        Args:
            query: Product search query
            num_results: Number of results to return (default 20)
            **kwargs: Additional SerpAPI parameters

        Returns:
            SerpAPI response dictionary with shopping_results

        Raises:
            requests.RequestException: On network or API errors
        """
        params = {
            "engine": "google_shopping",
            "q": query,
            "num": num_results,
            "api_key": self.api_key,
            **kwargs,
        }
        return self._make_request(params)

    def google_images(
        self,
        query: str,
        num_results: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search Google Images for product photos.

        Args:
            query: Image search query
            num_results: Number of results to return (default 10)
            **kwargs: Additional SerpAPI parameters

        Returns:
            SerpAPI response dictionary with images_results

        Raises:
            requests.RequestException: On network or API errors
        """
        params = {
            "engine": "google_images",
            "q": query,
            "num": num_results,
            "api_key": self.api_key,
            **kwargs,
        }
        return self._make_request(params)

    def google_news(
        self,
        query: str,
        num_results: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search Google News for articles.

        Args:
            query: News search query
            num_results: Number of results to return (default 10)
            **kwargs: Additional SerpAPI parameters

        Returns:
            SerpAPI response dictionary with news_results

        Raises:
            requests.RequestException: On network or API errors
        """
        params = {
            "engine": "google_news",
            "q": query,
            "num": num_results,
            "api_key": self.api_key,
            **kwargs,
        }
        return self._make_request(params)

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to SerpAPI.

        Args:
            params: Request parameters including engine, query, api_key

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: On network or API errors
        """
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"SerpAPI request failed: {e}")
            raise
