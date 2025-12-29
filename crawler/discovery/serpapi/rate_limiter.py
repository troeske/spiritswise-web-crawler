"""
Rate Limiter and Quota Tracker - Manage SerpAPI request limits.

Phase 2: SerpAPI Integration

Provides:
- Daily request limiting (stay within budget)
- Monthly quota tracking
- Usage statistics
- Low quota alerts
"""

import logging
from datetime import datetime

from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limit SerpAPI requests to stay within quota.

    Uses Django cache for distributed tracking across workers.

    Limits:
    - MONTHLY_QUOTA: 5000 searches per month (SerpAPI plan)
    - DAILY_LIMIT: ~165 searches per day (5000 / 30)

    Usage:
        limiter = RateLimiter()
        if limiter.can_make_request():
            # Make API call
            limiter.record_request()
    """

    MONTHLY_QUOTA = 5000
    DAILY_LIMIT = 165  # ~5000 / 30 days

    def __init__(self, cache_prefix: str = "serpapi"):
        """
        Initialize rate limiter.

        Args:
            cache_prefix: Prefix for cache keys (allows multiple instances)
        """
        self.cache_prefix = cache_prefix

    def can_make_request(self) -> bool:
        """
        Check if we can make another request today.

        Returns:
            True if under daily limit, False otherwise
        """
        daily_count = self._get_daily_count()
        return daily_count < self.DAILY_LIMIT

    def record_request(self) -> None:
        """
        Record that a request was made.

        Increments both daily and monthly counters in cache.
        """
        # Update daily count
        daily_key = self._daily_key()
        daily_count = cache.get(daily_key, 0)
        cache.set(daily_key, daily_count + 1, 86400)  # 24 hours

        # Update monthly count
        monthly_key = self._monthly_key()
        monthly_count = cache.get(monthly_key, 0)
        cache.set(monthly_key, monthly_count + 1, 2592000)  # 30 days

        logger.debug(
            f"SerpAPI request recorded. Daily: {daily_count + 1}/{self.DAILY_LIMIT}, "
            f"Monthly: {monthly_count + 1}/{self.MONTHLY_QUOTA}"
        )

    def get_remaining_daily(self) -> int:
        """
        Get remaining requests for today.

        Returns:
            Number of requests remaining (never negative)
        """
        return max(0, self.DAILY_LIMIT - self._get_daily_count())

    def get_remaining_monthly(self) -> int:
        """
        Get remaining requests for the month.

        Returns:
            Number of requests remaining (never negative)
        """
        monthly_count = cache.get(self._monthly_key(), 0)
        return max(0, self.MONTHLY_QUOTA - monthly_count)

    def _get_daily_count(self) -> int:
        """Get count of requests made today."""
        return cache.get(self._daily_key(), 0)

    def _daily_key(self) -> str:
        """
        Generate cache key for daily count.

        Returns:
            Cache key string like "serpapi:daily:2025-01-15"
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{self.cache_prefix}:daily:{today}"

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
            Dict with daily_remaining, daily_limit, monthly_remaining, monthly_limit
        """
        return {
            "daily_remaining": self.rate_limiter.get_remaining_daily(),
            "daily_limit": RateLimiter.DAILY_LIMIT,
            "monthly_remaining": self.rate_limiter.get_remaining_monthly(),
            "monthly_limit": RateLimiter.MONTHLY_QUOTA,
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
        low_threshold = RateLimiter.MONTHLY_QUOTA * threshold
        return monthly_remaining < low_threshold
