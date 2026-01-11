"""
Base Collector for Award Site URL Collection.

This module provides the base class and dataclass for collecting detail page
URLs from award competition listing pages. Unlike parsers that extract data,
collectors only gather URLs for later AI extraction.

The separation of concerns allows:
1. Efficient URL collection from listing pages
2. AI-powered data extraction from detail pages
3. Easy addition of new award site collectors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING


@dataclass
class AwardDetailURL:
    """
    URL collected from award site listing page for AI extraction.

    This dataclass represents a single product detail page URL discovered
    from an award competition's listing/results page. It captures metadata
    from the listing card to provide hints for AI extraction.

    Attributes:
        detail_url: Full URL to the product detail page
        listing_url: URL of the listing page where this was found
        medal_hint: Medal type from listing card (Gold, Silver, Bronze, etc.)
        score_hint: Optional score if visible on listing card
        competition: Competition name (IWSC, DWWA, etc.)
        year: Competition year
        product_type_hint: Detected product type (whiskey, port_wine, etc.)
    """

    detail_url: str
    listing_url: str
    medal_hint: str
    score_hint: Optional[int]
    competition: str
    year: int
    product_type_hint: str


class BaseCollector(ABC):
    """
    Abstract base class for award site URL collectors.

    Collectors are responsible for:
    1. Fetching listing/results pages from award sites
    2. Parsing listing pages to extract detail page URLs
    3. Detecting product types from listing card metadata
    4. Extracting medal hints from listing cards

    Unlike parsers, collectors do NOT extract product data - they only
    collect URLs for later AI extraction.
    """

    COMPETITION_NAME: str = "Unknown"
    BASE_URL: str = ""

    @abstractmethod
    def collect(self, year: int, product_types: Optional[List[str]] = None) -> List[AwardDetailURL]:
        """
        Collect detail page URLs from listing pages for a given year.

        Args:
            year: Competition year to collect URLs for
            product_types: Optional filter by product types (e.g., ["port_wine", "whiskey"])
                          If None, collects all product types

        Returns:
            List of AwardDetailURL objects containing detail page URLs and metadata
        """
        pass


def get_collector(source: str) -> BaseCollector:
    """
    Factory function to get collector by source name.

    Args:
        source: Source name (case-insensitive), e.g., 'iwsc', 'dwwa', 'sfwsc', 'wwa'

    Returns:
        Collector instance for the specified source

    Raises:
        ValueError: If source is not recognized
    """
    # Import here to avoid circular imports
    from .iwsc_collector import IWSCCollector
    from .dwwa_collector import DWWACollector
    from .sfwsc_collector import SFWSCCollector
    from .wwa_collector import WWACollector

    collectors = {
        'iwsc': IWSCCollector,
        'dwwa': DWWACollector,
        'sfwsc': SFWSCCollector,
        'wwa': WWACollector,
    }

    source_lower = source.lower()
    if source_lower not in collectors:
        raise ValueError(f"Unknown source: {source}. Available sources: {list(collectors.keys())}")

    return collectors[source_lower]()
