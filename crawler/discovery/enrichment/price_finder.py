"""
Price Finder for Product Enrichment.

Phase 4: Product Enrichment - Find prices via Google Shopping API.
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from crawler.discovery.serpapi.parsers import ShoppingResultParser
from crawler.discovery.serpapi.queries import QueryBuilder

logger = logging.getLogger(__name__)


class PriceFinder:
    """Finds product prices via Google Shopping search."""

    def __init__(self, client):
        """
        Initialize PriceFinder.

        Args:
            client: SerpAPIClient instance
        """
        self.client = client
        self.parser = ShoppingResultParser()
        self.query_builder = QueryBuilder()

    def find_prices(self, product, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find prices for a product.

        Args:
            product: DiscoveredProduct instance
            max_results: Maximum number of results to return

        Returns:
            List of price entries with price, currency, retailer, url
        """
        try:
            product_name = product.extracted_data.get("name", "")
            brand = product.extracted_data.get("brand", "")

            # Build search query
            query = f"{brand} {product_name}".strip() if brand else product_name

            # Search Google Shopping
            response = self.client.google_shopping(query=query)

            # Parse results
            shopping_results = response.get("shopping_results", [])

            prices = []
            for result in shopping_results:
                title = result.get("title", "")

                # Filter irrelevant results
                if not self._is_relevant_result(product_name.lower(), title.lower()):
                    continue

                price_str = result.get("price", "")
                price_value = self._parse_price(price_str)

                if price_value is None:
                    continue

                currency = self._extract_currency(price_str)

                price_entry = {
                    "price": price_value,
                    "currency": currency,
                    "retailer": result.get("source", ""),
                    "url": result.get("link", ""),
                }
                prices.append(price_entry)

                if len(prices) >= max_results:
                    break

            return prices

        except Exception as e:
            logger.error(f"Error finding prices: {e}")
            return []

    def get_best_price(self, prices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Get the best (lowest) price from a list of prices.

        Args:
            prices: List of price entries

        Returns:
            Best price entry or None if no valid prices
        """
        if not prices:
            return None

        # Filter out zero/invalid prices
        valid_prices = [p for p in prices if p.get("price", 0) > 0]

        if not valid_prices:
            return None

        return min(valid_prices, key=lambda p: p["price"])

    def _is_relevant_result(self, product_name: str, result_title: str) -> bool:
        """
        Check if a search result is relevant to the product.

        Args:
            product_name: Original product name (lowercase)
            result_title: Search result title (lowercase)

        Returns:
            True if result is relevant
        """
        # Extract significant words from product name (skip common words)
        stop_words = {"the", "a", "an", "of", "and", "or", "for", "in", "on", "at", "to"}
        product_words = [
            w for w in product_name.split()
            if w not in stop_words and len(w) > 2
        ]

        if not product_words:
            return True

        # Count matching words
        matches = sum(1 for word in product_words if word in result_title)

        # Require at least 50% of significant words to match
        threshold = len(product_words) * 0.5
        return matches >= threshold

    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Parse price string to float.

        Args:
            price_str: Price string like "$45.99" or "45.99 USD"

        Returns:
            Float price or None if parsing fails
        """
        if not price_str:
            return None

        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[£€$¥₹]", "", price_str)
        cleaned = cleaned.replace(",", "").strip()

        # Extract numeric value
        match = re.search(r"(\d+\.?\d*)", cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None

        return None

    def _extract_currency(self, price_str: str) -> str:
        """
        Extract currency from price string.

        Args:
            price_str: Price string

        Returns:
            Currency code (default USD)
        """
        if "$" in price_str:
            return "USD"
        elif "£" in price_str:
            return "GBP"
        elif "€" in price_str:
            return "EUR"
        elif "¥" in price_str:
            return "JPY"
        elif "₹" in price_str:
            return "INR"
        return "USD"


class PriceAggregator:
    """Aggregates prices to product model."""

    def aggregate_prices(self, product, prices: List[Dict[str, Any]]) -> None:
        """
        Aggregate price data to product.

        Args:
            product: DiscoveredProduct instance
            prices: List of price entries
        """
        # Add prices to history
        for price_entry in prices:
            history_entry = {
                "price": price_entry["price"],
                "currency": price_entry["currency"],
                "retailer": price_entry["retailer"],
                "url": price_entry["url"],
                "date": datetime.utcnow().isoformat(),
            }
            product.price_history.append(history_entry)

        # Update best price
        if prices:
            valid_prices = [p for p in prices if p.get("price", 0) > 0]
            if valid_prices:
                best = min(valid_prices, key=lambda p: p["price"])
                product.update_best_price(
                    price=best["price"],
                    currency=best["currency"],
                    retailer=best["retailer"],
                    url=best["url"]
                )

        product.save()
