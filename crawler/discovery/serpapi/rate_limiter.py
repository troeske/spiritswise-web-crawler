"""
Rate Limiter and Quota Tracker - Manage SerpAPI request limits.

Phase 2: SerpAPI Integration

Provides:
- Hourly request limiting (plan-based rate limit)
- Monthly quota tracking
- Usage statistics
- Low quota alerts
"""

import logging
from datetime import datetime

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limit SerpAPI requests to stay within quota.

    Uses Django cache for distributed tracking across workers.

    Limits are configurable via settings:
    - SERPAPI_MONTHLY_QUOTA: Monthly search quota (default 5000)
    - SERPAPI_HOURLY_LIMIT: Hourly rate limit (default 1000)

    Usage:
        limiter = RateLimiter()
        if limiter.can_make_request():
            # Make API call
            limiter.record_request()
    """

    def __init__(self, cache_prefix: str = "serpapi"):
        """
        Initialize rate limiter.

        Args:
            cache_prefix: Prefix for cache keys (allows multiple instances)
        """
        self.cache_prefix = cache_prefix
        # Load limits from settings (configurable per plan)
        self.monthly_quota = getattr(settings, "SERPAPI_MONTHLY_QUOTA", 5000)
        self.hourly_limit = getattr(settings, "SERPAPI_HOURLY_LIMIT", 1000)

    def can_make_request(self) -> bool:
        """
        Check if we can make another request this hour.

        Returns:
            True if under hourly limit and monthly quota, False otherwise
        """
        hourly_count = self._get_hourly_count()
        monthly_count = cache.get(self._monthly_key(), 0)
        return hourly_count < self.hourly_limit and monthly_count < self.monthly_quota

    def record_request(self) -> None:
        """
        Record that a request was made.

        Increments both hourly and monthly counters in cache.
        """
        # Update hourly count
        hourly_key = self._hourly_key()
        hourly_count = cache.get(hourly_key, 0)
        cache.set(hourly_key, hourly_count + 1, 3600)  # 1 hour

        # Update monthly count
        monthly_key = self._monthly_key()
        monthly_count = cache.get(monthly_key, 0)
        cache.set(monthly_key, monthly_count + 1, 2592000)  # 30 days

        logger.debug(
            f"SerpAPI request recorded. Hourly: {hourly_count + 1}/{self.hourly_limit}, "
            f"Monthly: {monthly_count + 1}/{self.monthly_quota}"
        )

    def get_remaining_hourly(self) -> int:
        """
        Get remaining requests for this hour.

        Returns:
            Number of requests remaining (never negative)
        """
        return max(0, self.hourly_limit - self._get_hourly_count())

    def get_remaining_monthly(self) -> int:
        """
        Get remaining requests for the month.

        Returns:
            Number of requests remaining (never negative)
        """
        monthly_count = cache.get(self._monthly_key(), 0)
        return max(0, self.monthly_quota - monthly_count)

    def _get_hourly_count(self) -> int:
        """Get count of requests made this hour."""
        return cache.get(self._hourly_key(), 0)

    def _hourly_key(self) -> str:
        """
        Generate cache key for hourly count.

        Returns:
            Cache key string like "serpapi:hourly:2025-01-15-14"
        """
        hour = datetime.now().strftime("%Y-%m-%d-%H")
        return f"{self.cache_prefix}:hourly:{hour}"

    def _monthly_key(self) -> str:
        """
        Generate cache key for monthly count.

        Returns:
            Cache key string like "serpapi:monthly:2025-01"
        """
        month = datetime.now().strftime("%Y-%m")
        return f"{self.cache_prefix}:monthly:{month}"


class QuotaTracker:
    """
    Track SerpAPI quota usage and provide alerts.

    Provides high-level statistics and monitoring for quota management.

    Usage:
        limiter = RateLimiter()
        tracker = QuotaTracker(limiter)

        stats = tracker.get_usage_stats()
        if tracker.is_quota_low():
            logger.warning("SerpAPI quota is running low!")
    """

    def __init__(self, rate_limiter: RateLimiter):
        """
        Initialize quota tracker.

        Args:
            rate_limiter: RateLimiter instance for quota data
        """
        self.rate_limiter = rate_limiter

    def get_usage_stats(self) -> dict:
        """
        Get current usage statistics.

        Returns:
            Dict with hourly_remaining, hourly_limit, monthly_remaining, monthly_limit
        """
        return {
            "hourly_remaining": self.rate_limiter.get_remaining_hourly(),
            "hourly_limit": self.rate_limiter.hourly_limit,
            "monthly_remaining": self.rate_limiter.get_remaining_monthly(),
            "monthly_limit": self.rate_limiter.monthly_quota,
        }

    def is_quota_low(self, threshold: float = 0.1) -> bool:
        """
        Check if quota is running low.

        Args:
            threshold: Fraction of quota considered "low" (default 0.1 = 10%)

        Returns:
            True if remaining monthly quota is below threshold
        """
        monthly_remaining = self.rate_limiter.get_remaining_monthly()
        low_threshold = self.rate_limiter.monthly_quota * threshold
        return monthly_remaining < low_threshold
