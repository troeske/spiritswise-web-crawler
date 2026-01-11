"""
Unified Product Pipeline Phase 6: REST API Module

This module provides REST API endpoints for:
- On-demand product extraction from URLs
- Batch extraction from multiple URLs
- Search-based extraction via SerpAPI
- Award crawl triggering and status monitoring
- Source health monitoring

All endpoints require authentication and have rate limiting.
"""

from crawler.api.views import (
    extract_from_url,
    extract_from_urls,
    extract_from_search,
    trigger_award_crawl,
    get_crawl_status,
    list_award_sources,
    sources_health,
)
from crawler.api.throttling import (
    ExtractionThrottle,
    CrawlTriggerThrottle,
)

__all__ = [
    # Views
    'extract_from_url',
    'extract_from_urls',
    'extract_from_search',
    'trigger_award_crawl',
    'get_crawl_status',
    'list_award_sources',
    'sources_health',
    # Throttling
    'ExtractionThrottle',
    'CrawlTriggerThrottle',
]
