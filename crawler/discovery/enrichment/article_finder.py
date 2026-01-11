"""
Article Finder for Product Enrichment.

Phase 4: Product Enrichment - Find articles via Google News API.
"""

import re
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

from crawler.discovery.serpapi.parsers import NewsResultParser

logger = logging.getLogger(__name__)


class ArticleFinder:
    """Finds product articles via Google News search."""

    def __init__(self, client):
        """
        Initialize ArticleFinder.

        Args:
            client: SerpAPIClient instance
        """
        self.client = client
        self.parser = NewsResultParser()

    def find_articles(self, product, max_results: int = 10, max_age_days: int = 365) -> List[Dict[str, Any]]:
        """
        Find articles mentioning a product.

        Args:
            product: DiscoveredProduct instance
            max_results: Maximum number of results to return
            max_age_days: Maximum age of articles in days

        Returns:
            List of article entries with url, title, source, date, snippet
        """
        try:
            # Use individual columns instead of extracted_data
            product_name = product.name or ""
            brand = product.brand.name if product.brand else ""

            # Build search query
            query = f"{brand} {product_name}".strip() if brand else product_name

            # Search Google News
            response = self.client.google_news(query=query)

            # Parse results
            news_results = response.get("news_results", [])

            articles = []
            for result in news_results:
                date_str = result.get("date", "")
                age_days = self._parse_date_age(date_str)

                # Filter old articles
                if age_days > max_age_days:
                    continue

                # Extract source name
                source_info = result.get("source", {})
                if isinstance(source_info, dict):
                    source = source_info.get("name", "")
                else:
                    source = str(source_info)

                article_entry = {
                    "url": result.get("link", ""),
                    "title": result.get("title", ""),
                    "source": source,
                    "date": date_str,
                    "snippet": result.get("snippet", ""),
                }

                # Include thumbnail if available
                if result.get("thumbnail"):
                    article_entry["thumbnail"] = result["thumbnail"]

                articles.append(article_entry)

                if len(articles) >= max_results:
                    break

            return articles

        except Exception as e:
            logger.error(f"Error finding articles: {e}")
            return []

    def _parse_date_age(self, date_str: str) -> int:
        """
        Parse relative date string to age in days.

        Args:
            date_str: Date string like "2 days ago", "1 week ago", etc.

        Returns:
            Age in days (9999 for unknown formats)
        """
        if not date_str:
            return 9999

        date_lower = date_str.lower()

        # Handle "yesterday"
        if "yesterday" in date_lower:
            return 1

        # Handle hours ago (same day)
        match = re.search(r"(\d+)\s*hours?\s*ago", date_lower)
        if match:
            return 0

        # Handle days ago
        match = re.search(r"(\d+)\s*days?\s*ago", date_lower)
        if match:
            return int(match.group(1))

        # Handle weeks ago
        match = re.search(r"(\d+)\s*weeks?\s*ago", date_lower)
        if match:
            return int(match.group(1)) * 7

        # Handle months ago
        match = re.search(r"(\d+)\s*months?\s*ago", date_lower)
        if match:
            return int(match.group(1)) * 30

        # Handle years ago
        match = re.search(r"(\d+)\s*years?\s*ago", date_lower)
        if match:
            return int(match.group(1)) * 365

        # Unknown format - return large number to filter it out
        return 9999


class ArticleAggregator:
    """Aggregates articles to product model."""

    def aggregate_articles(self, product, articles: List[Dict[str, Any]]) -> None:
        """
        Aggregate article data to product.

        Args:
            product: DiscoveredProduct instance
            articles: List of article entries
        """
        for article in articles:
            mention_data = {
                "url": article["url"],
                "title": article["title"],
                "source": article["source"],
                "date": article.get("date", ""),
                "snippet": article.get("snippet", ""),
                "thumbnail": article.get("thumbnail", ""),
                "type": "article",
            }
            product.add_press_mention(mention_data)

        product.save()
