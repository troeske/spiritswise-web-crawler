"""
Prestige-Led Discovery (Competition-Driven) System.

This module implements competition-driven product discovery by parsing
award results from major spirits competitions and creating skeleton
products for enrichment.

Components:
- parsers: Competition result page parsers (IWSC, SFWSC, WWA, Decanter)
- skeleton_manager: Creates and manages skeleton products from competition data
- enrichment_searcher: SerpAPI triple search for skeleton enrichment
- fuzzy_matcher: Name matching for skeleton-to-crawled product matching
"""

from .parsers import (
    BaseCompetitionParser,
    IWSCParser,
    SFWSCParser,
    WorldWhiskiesAwardsParser,
    DecanterWWAParser,
    CompetitionResult,
)
from .skeleton_manager import SkeletonProductManager
from .enrichment_searcher import EnrichmentSearcher
from .fuzzy_matcher import SkeletonMatcher

__all__ = [
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
