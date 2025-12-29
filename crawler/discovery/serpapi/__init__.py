"""
SerpAPI Integration Module - Phase 2 Product Discovery.

This module provides a comprehensive SerpAPI client for product discovery
through Google Search, Shopping, Images, and News APIs.

Components:
- SerpAPIClient: HTTP client wrapper for SerpAPI endpoints
- QueryBuilder: Optimized search query generation
- Parsers: Result extraction for each search type
- RateLimiter: Quota management and rate limiting
"""

from .client import SerpAPIClient
from .queries import QueryBuilder
from .parsers import (
    OrganicResultParser,
    ShoppingResultParser,
    ImageResultParser,
    NewsResultParser,
)
from .rate_limiter import RateLimiter, QuotaTracker

__all__ = [
    "SerpAPIClient",
    "QueryBuilder",
    "OrganicResultParser",
    "ShoppingResultParser",
    "ImageResultParser",
    "NewsResultParser",
    "RateLimiter",
    "QuotaTracker",
]
