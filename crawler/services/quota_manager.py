"""
Quota Manager - Tracks API usage and enforces limits.

Phase 6: Quota Management
Implements usage tracking, limit enforcement, and monthly resets.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class QuotaManager:
    """
    Manages API quota tracking and enforcement.

    Tracks usage for:
    - SerpAPI (search calls)
    - ScrapingBee (page fetches)
    - AI Enhancement Service (extraction calls)

    Features:
    - Monthly usage tracking
    - Configurable limits per API
    - Low quota warnings
    - Automatic monthly reset
    """

    # Default monthly limits
    DEFAULT_LIMITS = {
        "serpapi": 1000,        # 1000 searches/month
        "scrapingbee": 5000,    # 5000 pages/month
        "ai_service": 2000,     # 2000 extractions/month
    }

    # Warning threshold (percentage)
    WARNING_THRESHOLD = 0.80  # Warn at 80% usage

    def __init__(self):
        """Initialize the quota manager."""
        self._limits = self.DEFAULT_LIMITS.copy()
        self._usage_cache: Dict[str, Dict[str, int]] = {}

    def _get_current_month(self) -> str:
        """Get current month key (YYYY-MM)."""
        return timezone.now().strftime("%Y-%m")

    def _get_or_create_usage(self, api_name: str):
        """Get or create QuotaUsage record for API and current month."""
        from crawler.models import QuotaUsage

        month_key = self._get_current_month()

        usage, created = QuotaUsage.objects.get_or_create(
            api_name=api_name,
            month=month_key,
            defaults={
                "current_usage": 0,
                "monthly_limit": self._limits.get(api_name, 1000),
            }
        )

        if created:
            logger.info(f"Created new quota record for {api_name} ({month_key})")

        return usage

    def get_usage(self, api_name: str) -> int:
        """
        Get current usage for an API.

        Args:
            api_name: Name of the API (serpapi, scrapingbee, ai_service)

        Returns:
            Current usage count for this month
        """
        usage = self._get_or_create_usage(api_name)
        return usage.current_usage

    def record_usage(self, api_name: str, count: int = 1):
        """
        Record API usage.

        Args:
            api_name: Name of the API
            count: Number of calls to record (default 1)
        """
        with transaction.atomic():
            usage = self._get_or_create_usage(api_name)
            usage.current_usage += count
            usage.last_used = timezone.now()
            usage.save()

            logger.debug(f"Recorded {count} {api_name} calls, total: {usage.current_usage}")

    def set_limit(self, api_name: str, limit: int):
        """
        Set the monthly limit for an API.

        Args:
            api_name: Name of the API
            limit: Maximum calls allowed per month
        """
        self._limits[api_name] = limit

        # Update the database record if it exists
        usage = self._get_or_create_usage(api_name)
        usage.monthly_limit = limit
        usage.save(update_fields=["monthly_limit"])

        logger.info(f"Set {api_name} limit to {limit}")

    def can_use(self, api_name: str, count: int = 1) -> bool:
        """
        Check if we can use the API without exceeding quota.

        Args:
            api_name: Name of the API
            count: Number of calls we want to make

        Returns:
            True if usage would be within limits
        """
        usage = self._get_or_create_usage(api_name)
        limit = usage.monthly_limit

        remaining = limit - usage.current_usage
        return remaining >= count

    def get_remaining(self, api_name: str) -> int:
        """
        Get remaining quota for an API.

        Args:
            api_name: Name of the API

        Returns:
            Number of calls remaining this month
        """
        usage = self._get_or_create_usage(api_name)
        remaining = usage.monthly_limit - usage.current_usage
        return max(0, remaining)

    def check_quota_warnings(self, api_name: str):
        """
        Check if quota is running low and log warnings.

        Args:
            api_name: Name of the API
        """
        usage = self._get_or_create_usage(api_name)
        limit = usage.monthly_limit

        if limit == 0:
            return

        usage_ratio = usage.current_usage / limit

        if usage_ratio >= self.WARNING_THRESHOLD:
            remaining = limit - usage.current_usage
            logger.warning(
                f"Quota warning: {api_name} at {usage_ratio*100:.1f}% "
                f"({remaining} remaining of {limit})"
            )

    def get_all_usage_stats(self) -> Dict[str, Dict]:
        """
        Get usage statistics for all APIs.

        Returns:
            Dict with usage stats per API
        """
        from crawler.models import QuotaUsage

        month_key = self._get_current_month()
        stats = {}

        for api_name in self.DEFAULT_LIMITS.keys():
            try:
                usage = QuotaUsage.objects.get(
                    api_name=api_name,
                    month=month_key,
                )
                stats[api_name] = {
                    "current_usage": usage.current_usage,
                    "monthly_limit": usage.monthly_limit,
                    "remaining": max(0, usage.monthly_limit - usage.current_usage),
                    "percentage": (usage.current_usage / usage.monthly_limit * 100)
                        if usage.monthly_limit > 0 else 0,
                    "last_used": usage.last_used,
                }
            except QuotaUsage.DoesNotExist:
                stats[api_name] = {
                    "current_usage": 0,
                    "monthly_limit": self._limits.get(api_name, 1000),
                    "remaining": self._limits.get(api_name, 1000),
                    "percentage": 0,
                    "last_used": None,
                }

        return stats


# Global instance for easy access
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """Get the global QuotaManager instance."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager
