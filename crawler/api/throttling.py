"""
Unified Product Pipeline Phase 6: API Throttling Classes

Custom throttle classes for API rate limiting.
"""

from rest_framework.throttling import UserRateThrottle


class ExtractionThrottle(UserRateThrottle):
    """
    Throttle for extraction endpoints.

    Rate: 50 requests per hour per user.
    Applied to: /api/v1/extract/url/, /api/v1/extract/urls/, /api/v1/extract/search/
    """

    rate = '50/hour'
    scope = 'extraction'


class CrawlTriggerThrottle(UserRateThrottle):
    """
    Throttle for crawl trigger endpoints.

    Rate: 10 requests per hour per user.
    Applied to: /api/v1/crawl/awards/
    """

    rate = '10/hour'
    scope = 'crawl_trigger'
