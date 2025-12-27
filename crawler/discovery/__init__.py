"""
Discovery System - Product and source discovery mechanisms.

This module implements multiple discovery patterns for finding
spirits products and producer websites:

Hub & Spoke Discovery:
- hub_parser: Parses brand listings from retailer hub pages
- hub_crawler: Orchestrates crawling of hub pages
- serpapi_client: SerpAPI integration for official site discovery
- spoke_registry: Validates and registers discovered sources

Prestige-Led Discovery (Competitions):
- competitions/parsers: Competition result page parsers
- competitions/skeleton_manager: Creates skeleton products from competition data
- competitions/enrichment_searcher: SerpAPI triple search for enrichment
- competitions/fuzzy_matcher: Name matching for skeleton enrichment
"""

from .hub_parser import HubPageParser, BrandInfo
from .hub_crawler import HubCrawler
from .serpapi_client import SerpAPIClient, SearchResult
from .spoke_registry import SpokeRegistry

# Competition-driven discovery
from .competitions import (
    BaseCompetitionParser,
    IWSCParser,
    SFWSCParser,
    WorldWhiskiesAwardsParser,
    DecanterWWAParser,
    CompetitionResult,
    SkeletonProductManager,
    EnrichmentSearcher,
    SkeletonMatcher,
)

__all__ = [
    # Hub & Spoke Discovery
    "HubPageParser",
    "BrandInfo",
    "HubCrawler",
    "SerpAPIClient",
    "SearchResult",
    "SpokeRegistry",
    # Prestige-Led Discovery (Competitions)
    "BaseCompetitionParser",
    "IWSCParser",
    "SFWSCParser",
    "WorldWhiskiesAwardsParser",
    "DecanterWWAParser",
    "CompetitionResult",
    "SkeletonProductManager",
    "EnrichmentSearcher",
    "SkeletonMatcher",
]
