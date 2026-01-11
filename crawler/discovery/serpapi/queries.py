"""
Query Builder - Optimized search query generation for product discovery.

Phase 2: SerpAPI Integration

Builds search queries for:
- Generic product discovery (best lists, awards, new releases)
- Product-specific searches (prices, reviews, images, news)
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crawler.models import DiscoveredProduct


# Generic search terms configuration
WHISKEY_BEST_LISTS = [
    "best whisky {year}",
    "best whiskey {year}",
    "best single malt {year}",
    "best scotch whisky {year}",
    "best bourbon {year}",
    "best bourbon whiskey {year}",
    "best japanese whisky {year}",
    "best irish whiskey {year}",
    "best rye whiskey {year}",
    "top 10 whisky {year}",
    "top 10 bourbon {year}",
]

WHISKEY_AWARD_TERMS = [
    "whisky of the year {year}",
    "whiskey of the year {year}",
    "award winning whisky {year}",
    "award winning bourbon {year}",
    "gold medal whisky {year}",
]

WHISKEY_NEW_RELEASES = [
    "new whisky releases {year}",
    "new bourbon releases {year}",
    "limited edition whisky {year}",
]

WHISKEY_STYLE_TERMS = [
    "best smoky whisky",
    "best peated whisky",
    "best sherry cask whisky",
]

PORT_BEST_LISTS = [
    "best port wine {year}",
    "best port {year}",
    "best vintage port",
    "best tawny port",
    "best ruby port",
    "best LBV port",
    "top port wines {year}",
]

PORT_AWARD_TERMS = [
    "award winning port wine {year}",
    "port wine of the year {year}",
]

PORT_STYLE_TERMS = [
    "best 10 year tawny port",
    "best 20 year tawny port",
    "best colheita port",
]


class QueryBuilder:
    """
    Build optimized search queries for product discovery.

    Generates queries for both generic discovery (finding new products)
    and product-specific enrichment (finding details about known products).
    """

    def build_generic_queries(
        self,
        product_type: str,
        category: Optional[str] = None,
        year: Optional[int] = None,
    ) -> List[str]:
        """
        Build generic search queries for a product type.

        Args:
            product_type: "whiskey" or "port_wine"
            category: Optional category filter (e.g., "bourbon", "tawny")
            year: Year to substitute in queries (defaults to current year)

        Returns:
            List of search query strings ready for SerpAPI
        """
        year = year or datetime.now().year

        if product_type == "whiskey":
            return self._build_whiskey_queries(category, year)
        elif product_type == "port_wine":
            return self._build_port_queries(category, year)
        else:
            return []

    def build_product_price_query(self, product: "DiscoveredProduct") -> str:
        """
        Build query to find product prices.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Search query string for price discovery
        """
        # Use individual columns instead of extracted_data
        name = (product.name or "").strip()
        brand = (product.brand.name if product.brand else "").strip()

        # Quote product name for exact match
        if name:
            query_parts = [f'"{name}"']
        else:
            query_parts = []

        if brand:
            query_parts.append(brand)

        query_parts.append("buy price")

        return " ".join(query_parts).strip()

    def build_product_review_query(self, product: "DiscoveredProduct") -> str:
        """
        Build query to find product reviews.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Search query string for review discovery
        """
        # Use individual column instead of extracted_data
        name = (product.name or "").strip()

        if name:
            return f'"{name}" review tasting notes rating'.strip()
        else:
            return "review tasting notes rating"

    def build_product_image_query(self, product: "DiscoveredProduct") -> str:
        """
        Build query to find product images.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Search query string for image discovery
        """
        # Use individual columns instead of extracted_data
        name = (product.name or "").strip()
        brand = (product.brand.name if product.brand else "").strip()

        parts = []
        if name:
            parts.append(name)
        if brand:
            parts.append(brand)
        parts.append("bottle whisky")

        return " ".join(parts).strip()

    def build_product_news_query(self, product: "DiscoveredProduct") -> str:
        """
        Build query to find news/articles about product.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Search query string for news discovery
        """
        # Use individual column instead of extracted_data
        name = (product.name or "").strip()

        if name:
            return f'"{name}" whisky news'.strip()
        else:
            return "whisky news"

    def _build_whiskey_queries(
        self,
        category: Optional[str],
        year: int,
    ) -> List[str]:
        """Build whiskey-specific queries."""
        queries = []

        # Best lists (high priority)
        for template in WHISKEY_BEST_LISTS:
            queries.append(template.format(year=year))

        # Award terms
        for template in WHISKEY_AWARD_TERMS:
            queries.append(template.format(year=year))

        # New releases
        for template in WHISKEY_NEW_RELEASES:
            queries.append(template.format(year=year))

        # Style terms (no year substitution needed)
        queries.extend(WHISKEY_STYLE_TERMS)

        # Category-specific query
        if category:
            queries.append(f"best {category} whisky {year}")

        return queries

    def _build_port_queries(
        self,
        category: Optional[str],
        year: int,
    ) -> List[str]:
        """Build port wine-specific queries."""
        queries = []

        # Best lists
        for template in PORT_BEST_LISTS:
            queries.append(template.format(year=year))

        # Award terms
        for template in PORT_AWARD_TERMS:
            queries.append(template.format(year=year))

        # Style terms
        queries.extend(PORT_STYLE_TERMS)

        # Category-specific query
        if category:
            queries.append(f"best {category} port {year}")

        return queries
