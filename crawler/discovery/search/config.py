"""
Search Configuration - Generic search terms and domain filtering.

Phase 3: Generic Search Discovery

Defines:
- GENERIC_SEARCH_TERMS: Search queries by product type and category
- PRIORITY_DOMAINS: High-value domains to prioritize
- EXCLUDED_DOMAINS: Domains to skip (social media, etc.)
- SearchConfig: Configuration manager class
"""

from datetime import datetime
from typing import List, Optional


# Generic search terms by product type and category
GENERIC_SEARCH_TERMS = {
    "whiskey": {
        "best_lists": [
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
        ],
        "awards": [
            "whisky of the year {year}",
            "whiskey of the year {year}",
            "award winning whisky {year}",
            "award winning bourbon {year}",
            "gold medal whisky {year}",
            "IWSC whisky winners {year}",
            "world whiskies awards {year}",
        ],
        "value": [
            "best whisky under $50",
            "best whisky under $100",
            "best value whisky",
            "best affordable bourbon",
            "best budget scotch",
        ],
        "style": [
            "best smoky whisky",
            "best peated whisky",
            "best sherry cask whisky",
            "best cask strength whisky",
        ],
        "new_releases": [
            "new whisky releases {year}",
            "new bourbon releases {year}",
            "limited edition whisky {year}",
            "new scotch releases {year}",
        ],
    },
    "port_wine": {
        "best_lists": [
            "best port wine {year}",
            "best port {year}",
            "best vintage port",
            "best tawny port",
            "best ruby port",
            "best LBV port",
            "top port wines {year}",
        ],
        "awards": [
            "award winning port wine {year}",
            "IWSC port winners {year}",
            "port wine of the year {year}",
        ],
        "style": [
            "best 10 year tawny port",
            "best 20 year tawny port",
            "best 30 year tawny port",
            "best colheita port",
            "best white port",
        ],
        "value": [
            "best port under $50",
            "best affordable port wine",
            "best value tawny port",
        ],
    },
}


# Priority order for executing searches
SEARCH_PRIORITY = [
    "best_lists",    # Highest discovery value
    "awards",        # Award mentions increase product value
    "new_releases",  # Fresh content
    "style",         # Flavor profile discovery
    "value",         # Price-conscious buyers
]


# High-value domains to prioritize in results
PRIORITY_DOMAINS = [
    "whiskyadvocate.com",
    "thewhiskeywash.com",
    "robbreport.com",
    "vinepair.com",
    "breakingbourbon.com",
    "masterofmalt.com",
    "thewhiskyexchange.com",
    "wine-searcher.com",
    "vivino.com",
    "tastingtable.com",
    "wineenthusiast.com",
    "decanter.com",
    "whiskybase.com",
    "distiller.com",
]


# Domains to exclude (not useful for product discovery)
EXCLUDED_DOMAINS = [
    "wikipedia.org",
    "reddit.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "pinterest.com",
    "youtube.com",
    "amazon.com",      # Too generic, need specific retailer pages
    "amazon.co.uk",
    "ebay.com",
    "ebay.co.uk",
    "linkedin.com",
    "tiktok.com",
    "quora.com",
]


class SearchConfig:
    """
    Configuration manager for generic searches.

    Provides methods to get search queries for different product types
    and categories, with year substitution and domain filtering.

    Usage:
        config = SearchConfig(year=2025)
        queries = config.get_queries_for_type("whiskey")
        is_good = config.is_priority_domain("whiskyadvocate.com")
    """

    def __init__(self, year: int = None):
        """
        Initialize search configuration.

        Args:
            year: Year to substitute in queries (defaults to current year)
        """
        self.year = year or datetime.now().year

    def get_queries_for_type(
        self,
        product_type: str,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """
        Get search queries for a product type.

        Args:
            product_type: "whiskey" or "port_wine"
            category: Optional category filter (e.g., "best_lists", "awards")
            limit: Maximum number of queries to return

        Returns:
            List of search query strings with year substituted
        """
        type_config = GENERIC_SEARCH_TERMS.get(product_type, {})

        if not type_config:
            return []

        queries = []

        # Iterate through categories in priority order
        for priority_cat in SEARCH_PRIORITY:
            # Skip if filtering by category and this isn't it
            if category and priority_cat != category:
                continue

            cat_queries = type_config.get(priority_cat, [])
            for query_template in cat_queries:
                # Substitute year
                formatted = query_template.format(year=self.year)
                queries.append(formatted)

                # Check limit
                if limit and len(queries) >= limit:
                    return queries

        return queries

    def get_all_queries(self, limit: Optional[int] = None) -> List[str]:
        """
        Get all queries across all product types.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of all search query strings
        """
        queries = []

        for product_type in GENERIC_SEARCH_TERMS.keys():
            type_queries = self.get_queries_for_type(product_type)
            queries.extend(type_queries)

            if limit and len(queries) >= limit:
                return queries[:limit]

        return queries

    def is_priority_domain(self, domain: str) -> bool:
        """
        Check if domain is high-priority.

        Args:
            domain: Domain name to check

        Returns:
            True if domain is in priority list
        """
        domain_lower = domain.lower()
        return any(p in domain_lower for p in PRIORITY_DOMAINS)

    def is_excluded_domain(self, domain: str) -> bool:
        """
        Check if domain should be excluded.

        Args:
            domain: Domain name to check

        Returns:
            True if domain should be excluded
        """
        domain_lower = domain.lower()
        return any(e in domain_lower for e in EXCLUDED_DOMAINS)
