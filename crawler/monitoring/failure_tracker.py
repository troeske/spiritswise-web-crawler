"""
Consecutive failure tracking for crawler sources.

Task 9.3 Implementation:
- Tracks failures per source in Redis
- Alert threshold: 5 consecutive failures (configurable)
- Triggers Sentry alert on threshold breach
- Resets counter on successful crawl

Usage:
    from crawler.monitoring import get_failure_tracker

    tracker = get_failure_tracker()

    # On failure
    count = tracker.record_failure(source_id)

    # On success
    tracker.record_success(source_id)
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Default threshold for consecutive failures before alerting
DEFAULT_FAILURE_THRESHOLD = 5

# TTL for failure counters in Redis (24 hours)
FAILURE_COUNTER_TTL = 86400


def trigger_threshold_alert(
    source_id: str,
    failure_count: int,
    source_name: Optional[str] = None,
) -> None:
    """
    Trigger an alert when the failure threshold is breached.

    Args:
        source_id: ID of the CrawlerSource
        failure_count: Current consecutive failure count
        source_name: Name of the CrawlerSource (optional)
    """
    from .sentry_integration import capture_alert

    message = (
        f"Consecutive failure threshold breached for source {source_name or source_id}: "
        f"{failure_count} consecutive failures"
    )

    logger.warning(message)

    capture_alert(
        message=message,
        level="warning",
        source_id=source_id,
        source_name=source_name,
        extra_data={
            "failure_count": failure_count,
            "threshold": DEFAULT_FAILURE_THRESHOLD,
        },
    )


class FailureTracker:
    """
    Tracks consecutive failures per source using Redis.

    Alerts when a source exceeds the configured failure threshold.
    Counter is reset on successful crawl.
    """

    def __init__(
        self,
        redis_client=None,
        threshold: int = DEFAULT_FAILURE_THRESHOLD,
        key_prefix: str = "crawler:failures:",
    ):
        """
        Initialize the failure tracker.

        Args:
            redis_client: Redis client instance
            threshold: Number of consecutive failures before alerting
            key_prefix: Redis key prefix for failure counters
        """
        self.redis_client = redis_client
        self.threshold = threshold
        self.key_prefix = key_prefix

    def _get_key(self, source_id: str) -> str:
        """Generate Redis key for a source's failure counter."""
        return f"{self.key_prefix}{source_id}"

    def record_failure(self, source_id: str, source_name: Optional[str] = None) -> int:
        """
        Record a failure for a source.

        Increments the consecutive failure counter and triggers an alert
        if the threshold is reached.

        Args:
            source_id: ID of the CrawlerSource
            source_name: Name of the CrawlerSource (for alert context)

        Returns:
            Current failure count after increment
        """
        if self.redis_client is None:
            logger.warning("Redis client not available, failure tracking disabled")
            return 0

        key = self._get_key(source_id)

        try:
            # Increment counter
            count = self.redis_client.incr(key)

            # Set TTL on first failure
            if count == 1:
                self.redis_client.expire(key, FAILURE_COUNTER_TTL)

            logger.debug(
                f"Recorded failure for source {source_id}: "
                f"count={count}, threshold={self.threshold}"
            )

            # Check threshold
            if count >= self.threshold:
                trigger_threshold_alert(
                    source_id=source_id,
                    failure_count=count,
                    source_name=source_name,
                )

            return count

        except Exception as e:
            logger.warning(f"Failed to record failure in Redis: {e}")
            return 0

    def record_success(self, source_id: str) -> None:
        """
        Record a successful crawl for a source.

        Resets the consecutive failure counter.

        Args:
            source_id: ID of the CrawlerSource
        """
        if self.redis_client is None:
            logger.warning("Redis client not available, failure tracking disabled")
            return

        key = self._get_key(source_id)

        try:
            # Delete the counter to reset
            self.redis_client.delete(key)
            logger.debug(f"Reset failure counter for source {source_id}")

        except Exception as e:
            logger.warning(f"Failed to reset failure counter in Redis: {e}")

    def get_failure_count(self, source_id: str) -> int:
        """
        Get the current consecutive failure count for a source.

        Args:
            source_id: ID of the CrawlerSource

        Returns:
            Current failure count (0 if no failures or Redis unavailable)
        """
        if self.redis_client is None:
            return 0

        key = self._get_key(source_id)

        try:
            count = self.redis_client.get(key)
            return int(count) if count else 0

        except Exception as e:
            logger.warning(f"Failed to get failure count from Redis: {e}")
            return 0


# Singleton instance
_failure_tracker: Optional[FailureTracker] = None


def get_failure_tracker() -> FailureTracker:
    """
    Get the global failure tracker instance.

    Creates the tracker with Redis connection on first call.

    Returns:
        FailureTracker instance
    """
    global _failure_tracker

    if _failure_tracker is None:
        redis_client = _get_redis_client()
        threshold = getattr(
            settings, "CRAWLER_FAILURE_THRESHOLD", DEFAULT_FAILURE_THRESHOLD
        )
        _failure_tracker = FailureTracker(
            redis_client=redis_client,
            threshold=threshold,
        )

    return _failure_tracker


def _get_redis_client():
    """
    Get a Redis client from the Celery broker URL.

    Returns:
        Redis client or None if connection fails
    """
    try:
        import redis

        broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/1")

        # Parse Redis URL
        client = redis.from_url(broker_url)

        # Test connection
        client.ping()

        return client

    except Exception as e:
        logger.warning(f"Failed to connect to Redis for failure tracking: {e}")
        return None
