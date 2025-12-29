"""
Result Parsers - Extract structured data from SerpAPI responses.

Phase 2: SerpAPI Integration

Parsers for each search type:
- OrganicResultParser: Reviews, articles, general pages
- ShoppingResultParser: Prices, retailers, product listings
- ImageResultParser: Product photos, bottle images
- NewsResultParser: News articles, press mentions
"""

import re
from typing import List, Dict, Any
from urllib.parse import urlparse


class OrganicResultParser:
    """
    Parse organic search results from Google Search.

    Extracts:
    - URL, title, snippet
    - Source domain
    - Search position
    """

    def parse(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract useful data from organic results.

        Args:
            response: SerpAPI response dictionary

        Returns:
            List of parsed results with url, title, snippet, source, position
        """
        results = []
        organic = response.get("organic_results", [])

        for item in organic:
            url = item.get("link", "")
            parsed = {
                "url": url,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "source": self._extract_source(url),
                "position": item.get("position", 0),
            }
            results.append(parsed)

        return results

    def _extract_source(self, url: str) -> str:
        """
        Extract domain as source name.

        Args:
            url: Full URL string

        Returns:
            Domain name without www prefix
        """
        try:
            domain = urlparse(url).netloc
            return domain.replace("www.", "")
        except Exception:
            return ""


class ShoppingResultParser:
    """
    Parse Google Shopping results.

    Extracts:
    - Price (normalized to float)
    - Currency (USD, GBP, EUR)
    - Retailer name
    - Product URL
    - Thumbnail image
    """

    def parse(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract price and retailer data from shopping results.

        Args:
            response: SerpAPI response dictionary

        Returns:
            List of parsed results with price, currency, retailer, url, thumbnail
        """
        results = []
        shopping = response.get("shopping_results", [])

        for item in shopping:
            price_data = self._parse_price(item.get("price", ""))
            parsed = {
                "title": item.get("title", ""),
                "price": price_data["price"],
                "currency": price_data["currency"],
                "retailer": item.get("source", ""),
                "url": item.get("link", ""),
                "thumbnail": item.get("thumbnail", ""),
            }
            results.append(parsed)

        return results

    def _parse_price(self, price_str: str) -> Dict[str, Any]:
        """
        Parse price string into value and currency.

        Handles formats:
        - "$89.99" (USD)
        - "£75.00" (GBP)
        - "€85,00" (EUR - comma as decimal)
        - "$1,299.99" (USD with thousands separator)

        Args:
            price_str: Price string from shopping result

        Returns:
            Dict with 'price' (float) and 'currency' (str)
        """
        currency_map = {"$": "USD", "£": "GBP", "€": "EUR"}

        # Default currency
        currency = "USD"

        # Detect currency from symbol
        for symbol, code in currency_map.items():
            if symbol in price_str:
                currency = code
                break

        # Extract numeric value
        # Remove everything except digits, commas, and periods
        numbers = re.findall(r"[\d,.]+", price_str)

        if numbers:
            price_str_clean = numbers[0]

            # Handle European format (comma as decimal)
            if currency == "EUR" and "," in price_str_clean and "." not in price_str_clean:
                price_str_clean = price_str_clean.replace(",", ".")
            else:
                # Handle thousands separator (remove commas)
                price_str_clean = price_str_clean.replace(",", "")

            try:
                price = float(price_str_clean)
            except ValueError:
                price = 0.0
        else:
            price = 0.0

        return {"price": price, "currency": currency}


class ImageResultParser:
    """
    Parse Google Images results.

    Extracts:
    - Original image URL
    - Thumbnail URL
    - Source domain
    - Dimensions
    - Image type classification (bottle, label, lifestyle, product)
    """

    def parse(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract image URLs and metadata.

        Args:
            response: SerpAPI response dictionary

        Returns:
            List of parsed results with url, thumbnail, source, dimensions, type
        """
        results = []
        images = response.get("images_results", [])

        for item in images:
            parsed = {
                "url": item.get("original", ""),
                "thumbnail": item.get("thumbnail", ""),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "width": item.get("original_width", 0),
                "height": item.get("original_height", 0),
                "type": self._classify_image_type(item),
            }
            results.append(parsed)

        return results

    def _classify_image_type(self, item: Dict) -> str:
        """
        Classify image as bottle, label, lifestyle, or product.

        Uses title keywords to determine image type.

        Args:
            item: Image result item from SerpAPI

        Returns:
            Image type string: 'bottle', 'label', 'lifestyle', or 'product'
        """
        title = (item.get("title", "") or "").lower()

        if "bottle" in title:
            return "bottle"
        elif "label" in title:
            return "label"
        elif any(word in title for word in ["bar", "glass", "tasting", "drink"]):
            return "lifestyle"
        else:
            return "product"


class NewsResultParser:
    """
    Parse Google News results.

    Extracts:
    - Article URL
    - Title
    - Source publication
    - Publication date
    - Snippet/description
    - Thumbnail image
    """

    def parse(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract news article data.

        Args:
            response: SerpAPI response dictionary

        Returns:
            List of parsed results with url, title, source, date, snippet, thumbnail
        """
        results = []
        news = response.get("news_results", [])

        for item in news:
            # Source can be a dict with 'name' key or missing
            source_data = item.get("source", {})
            if isinstance(source_data, dict):
                source = source_data.get("name", "")
            else:
                source = str(source_data) if source_data else ""

            parsed = {
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "source": source,
                "date": item.get("date", ""),
                "snippet": item.get("snippet", ""),
                "thumbnail": item.get("thumbnail", ""),
                "mention_type": "news",
            }
            results.append(parsed)

        return results
