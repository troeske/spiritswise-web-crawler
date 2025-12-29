"""
Review Finder for Product Enrichment.

Phase 4: Product Enrichment - Find reviews via Google Search API.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from crawler.discovery.serpapi.parsers import OrganicResultParser

logger = logging.getLogger(__name__)


# Configuration for known review sites
REVIEW_SITES = {
    "whiskyadvocate.com": {
        "max_score": 100,
        "pattern": r"(\d+)\s*points?",
    },
    "masterofmalt.com": {
        "max_score": 5,
        "pattern": r"(\d+\.?\d*)\s*/\s*5",
    },
    "thewhiskyexchange.com": {
        "max_score": 5,
        "pattern": r"(\d+\.?\d*)\s*(?:out of\s*)?5",
    },
    "whiskybase.com": {
        "max_score": 100,
        "pattern": r"(\d+\.?\d*)\s*/\s*100",
    },
    "totalwine.com": {
        "max_score": 100,
        "pattern": r"(\d+)\s*points?",
    },
}


class ReviewFinder:
    """Finds product reviews via Google Search."""

    def __init__(self, client):
        """
        Initialize ReviewFinder.

        Args:
            client: SerpAPIClient instance
        """
        self.client = client
        self.parser = OrganicResultParser()

    def find_reviews(self, product, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find reviews for a product.

        Args:
            product: DiscoveredProduct instance
            max_results: Maximum number of results to return

        Returns:
            List of review entries with url, title, source, and optional score
        """
        try:
            product_name = product.extracted_data.get("name", "")

            # Build search query for reviews
            query = f"{product_name} review"

            # Search Google
            response = self.client.google_search(query=query)

            # Parse results
            organic_results = response.get("organic_results", [])

            reviews = []
            for result in organic_results:
                link = result.get("link", "")
                title = result.get("title", "")
                snippet = result.get("snippet", "")

                # Extract source domain
                source = self._extract_source(link)

                review_entry = {
                    "url": link,
                    "title": title,
                    "source": source,
                    "snippet": snippet,
                }

                # Try to extract rating from snippet
                rating = self._extract_rating(source, snippet)
                if rating:
                    review_entry["score"] = rating["score"]
                    review_entry["max_score"] = rating["max_score"]

                reviews.append(review_entry)

                if len(reviews) >= max_results:
                    break

            return reviews

        except Exception as e:
            logger.error(f"Error finding reviews: {e}")
            return []

    def _extract_source(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _extract_rating(self, source: str, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract rating from text based on source.

        Args:
            source: Source domain
            text: Text to extract rating from (snippet)

        Returns:
            Dict with score and max_score, or None if not found
        """
        # Check if we have a known pattern for this source
        if source in REVIEW_SITES:
            config = REVIEW_SITES[source]
            pattern = config["pattern"]
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    return {
                        "score": score,
                        "max_score": config["max_score"],
                    }
                except ValueError:
                    pass

        # Try generic patterns
        # Pattern: X/100 or X out of 100
        match = re.search(r"(\d+\.?\d*)\s*/\s*100", text)
        if match:
            try:
                return {
                    "score": float(match.group(1)),
                    "max_score": 100,
                }
            except ValueError:
                pass

        # Pattern: X/5 or X out of 5
        match = re.search(r"(\d+\.?\d*)\s*/\s*5", text)
        if match:
            try:
                return {
                    "score": float(match.group(1)),
                    "max_score": 5,
                }
            except ValueError:
                pass

        # Pattern: X stars
        match = re.search(r"(\d+\.?\d*)\s*stars?", text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                # Assume 5-star scale for stars
                return {
                    "score": score,
                    "max_score": 5,
                }
            except ValueError:
                pass

        # Pattern: X points (for 100-point scales)
        match = re.search(r"(\d+)\s*points?", text, re.IGNORECASE)
        if match:
            try:
                score = int(match.group(1))
                if 50 <= score <= 100:  # Valid 100-point scale score
                    return {
                        "score": score,
                        "max_score": 100,
                    }
            except ValueError:
                pass

        return None


class ReviewAggregator:
    """Aggregates reviews to product model."""

    def aggregate_reviews(self, product, reviews: List[Dict[str, Any]]) -> None:
        """
        Aggregate review data to product.

        Args:
            product: DiscoveredProduct instance
            reviews: List of review entries
        """
        for review in reviews:
            # Add review with score as rating
            if "score" in review and "max_score" in review:
                rating_data = {
                    "score": review["score"],
                    "max_score": review["max_score"],
                    "source": review["source"],
                    "url": review["url"],
                }
                product.add_rating(rating_data)

            # Add as press mention
            mention_data = {
                "url": review["url"],
                "title": review["title"],
                "source": review["source"],
                "snippet": review.get("snippet", ""),
                "type": "review",
            }
            product.add_press_mention(mention_data)

        product.save()
