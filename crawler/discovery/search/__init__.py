"""
Generic Search Discovery Module - Phase 3 Product Discovery.

This module discovers new products by searching for generic terms like
"best whisky 2025", "award winning bourbon", etc. and extracting target
URLs for scraping.

Components:
- SearchConfig: Search term configuration and domain filtering
- TargetURLExtractor: Extract and prioritize target URLs from results
- SearchScheduler: Schedule searches within rate limits
- Celery Tasks: Automated discovery execution
"""

from .config import SearchConfig, GENERIC_SEARCH_TERMS, PRIORITY_DOMAINS, EXCLUDED_DOMAINS
from .target_extractor import TargetURLExtractor
from .scheduler import SearchScheduler

__all__ = [
    "SearchConfig",
    "GENERIC_SEARCH_TERMS",
    "PRIORITY_DOMAINS",
    "EXCLUDED_DOMAINS",
    "TargetURLExtractor",
    "SearchScheduler",
]
