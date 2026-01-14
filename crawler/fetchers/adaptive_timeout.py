"""
Adaptive Timeout Strategy for Domain-Specific Fetch Optimization.

This module provides intelligent timeout calculation based on:
- Historical domain response times
- Progressive increase on retries
- Manual admin overrides
- Learned slow domain detection

Timeout Strategy:
- Base: 20s for unknown domains
- Progressive: 20s -> 40s -> 60s on retries (capped at 60s)
- Learned: Uses exponential moving average of response times
- Slow domains: 1.5x multiplier
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawler.fetchers.domain_intelligence import DomainProfile

logger = logging.getLogger(__name__)


class AdaptiveTimeout:
    """
    Adaptive timeout calculation for fetch requests.

    Uses domain history and retry context to determine optimal timeout.
    """

    # Base timeout for unknown domains
    BASE_TIMEOUT_MS = 20000  # 20s

    # Maximum timeout cap
    MAX_TIMEOUT_MS = 60000  # 60s

    # Minimum successful fetches before using learned timeout
    MIN_FETCHES_FOR_LEARNING = 5

    # Multiplier for domains marked as slow
    SLOW_DOMAIN_MULTIPLIER = 1.5

    # Exponential moving average alpha (weight for new values)
    EMA_ALPHA = 0.2

    # Multiplier for recommended timeout (avg * this)
    TIMEOUT_MULTIPLIER = 3.0

    # Increase factor for timeouts after timeout failure
    TIMEOUT_INCREASE_FACTOR = 1.25

    @classmethod
    def get_timeout(
        cls,
        domain_profile: "DomainProfile",
        attempt: int = 0,
    ) -> int:
        """
        Calculate timeout in milliseconds for a fetch attempt.

        Args:
            domain_profile: Domain's historical performance profile
            attempt: Retry attempt number (0-indexed)

        Returns:
            Timeout in milliseconds
        """
        # Check for manual override first
        if domain_profile.manual_override_timeout_ms:
            timeout = domain_profile.manual_override_timeout_ms
            logger.debug(
                "Using manual timeout override for %s: %dms",
                domain_profile.domain,
                timeout,
            )
            return min(timeout, cls.MAX_TIMEOUT_MS)

        # Start with base timeout
        base_timeout = cls.BASE_TIMEOUT_MS

        # Use learned timeout if enough history exists
        total_fetches = domain_profile.success_count + domain_profile.failure_count
        if (
            total_fetches >= cls.MIN_FETCHES_FOR_LEARNING
            and domain_profile.recommended_timeout_ms > 0
        ):
            base_timeout = domain_profile.recommended_timeout_ms
            logger.debug(
                "Using learned timeout for %s: %dms (from %d fetches)",
                domain_profile.domain,
                base_timeout,
                total_fetches,
            )

        # Apply slow domain multiplier
        if domain_profile.likely_slow:
            base_timeout = int(base_timeout * cls.SLOW_DOMAIN_MULTIPLIER)
            logger.debug(
                "Applying slow domain multiplier for %s: %dms",
                domain_profile.domain,
                base_timeout,
            )

        # Progressive increase on retries (double each time, capped)
        timeout = base_timeout
        for _ in range(attempt):
            timeout = min(timeout * 2, cls.MAX_TIMEOUT_MS)

        # Apply cap
        timeout = min(timeout, cls.MAX_TIMEOUT_MS)

        logger.debug(
            "Calculated timeout for %s (attempt %d): %dms",
            domain_profile.domain,
            attempt,
            timeout,
        )

        return timeout

    @classmethod
    def update_profile_after_fetch(
        cls,
        profile: "DomainProfile",
        response_time_ms: int,
        success: bool,
        timed_out: bool = False,
    ) -> "DomainProfile":
        """
        Update domain profile based on fetch result.

        Uses exponential moving average for response time tracking.

        Args:
            profile: Domain profile to update
            response_time_ms: Actual response time (or timeout value)
            success: Whether the fetch succeeded
            timed_out: Whether the fetch timed out (subset of failure)

        Returns:
            Updated profile (modified in place, also returned)
        """
        if success:
            # Update success count
            profile.success_count += 1
            profile.last_successful_fetch = datetime.now(timezone.utc)

            # Update exponential moving average of response time
            if profile.avg_response_time_ms == 0:
                # First successful fetch
                profile.avg_response_time_ms = float(response_time_ms)
            else:
                # EMA update: new_avg = alpha * new_value + (1 - alpha) * old_avg
                profile.avg_response_time_ms = (
                    cls.EMA_ALPHA * response_time_ms
                    + (1 - cls.EMA_ALPHA) * profile.avg_response_time_ms
                )

            # Update recommended timeout (3x average, minimum 10s)
            profile.recommended_timeout_ms = max(
                int(profile.avg_response_time_ms * cls.TIMEOUT_MULTIPLIER),
                10000,  # Minimum 10s
            )

            logger.debug(
                "Updated profile for %s after success: avg=%.0fms, recommended=%dms",
                profile.domain,
                profile.avg_response_time_ms,
                profile.recommended_timeout_ms,
            )

        else:
            # Update failure count
            profile.failure_count += 1

            if timed_out:
                # Update timeout count
                profile.timeout_count += 1

                # Increase recommended timeout after timeout
                if profile.recommended_timeout_ms > 0:
                    profile.recommended_timeout_ms = min(
                        int(profile.recommended_timeout_ms * cls.TIMEOUT_INCREASE_FACTOR),
                        cls.MAX_TIMEOUT_MS,
                    )
                else:
                    # No learned timeout yet, set to increased base
                    profile.recommended_timeout_ms = int(
                        cls.BASE_TIMEOUT_MS * cls.TIMEOUT_INCREASE_FACTOR
                    )

                # Mark as likely slow after multiple timeouts
                if profile.timeout_count >= 3:
                    profile.likely_slow = True

                logger.debug(
                    "Updated profile for %s after timeout: timeout_count=%d, recommended=%dms",
                    profile.domain,
                    profile.timeout_count,
                    profile.recommended_timeout_ms,
                )

        return profile
