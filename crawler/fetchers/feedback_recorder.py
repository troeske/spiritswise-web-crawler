"""
Feedback Recording for Domain Learning.

This module records fetch results and updates domain profiles to enable
learning from historical performance patterns.

Updates Include:
- Tier success rates (exponential moving average)
- Timeout counts and slow domain detection
- Behavior flags (JS-heavy, bot-protected)
- Success/failure counts
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crawler.fetchers.domain_intelligence import DomainProfile

logger = logging.getLogger(__name__)


class FeedbackRecorder:
    """
    Records fetch results and updates domain profiles for learning.

    Uses exponential moving average for success rates to adapt
    quickly while maintaining stability.
    """

    # Weight for new observations in EMA
    EMA_ALPHA = 0.3

    # Timeouts before marking domain as slow
    SLOW_THRESHOLD = 3

    # Keywords in escalation reasons that indicate JS rendering needed
    JS_KEYWORDS = [
        "javascript",
        "js rendering",
        "js placeholder",
        "js-heavy",
    ]

    # Keywords in escalation reasons that indicate bot protection
    BOT_PROTECTION_KEYWORDS = [
        "cloudflare",
        "captcha",
        "403",
        "bot",
        "challenge",
    ]

    @classmethod
    def record_fetch_result(
        cls,
        profile: "DomainProfile",
        tier: int,
        success: bool,
        response_time_ms: int,
        timed_out: bool = False,
        escalation_reason: Optional[str] = None,
    ) -> "DomainProfile":
        """
        Record fetch result and update domain profile.

        Args:
            profile: Domain profile to update
            tier: Tier used for this fetch (1, 2, or 3)
            success: Whether the fetch succeeded
            response_time_ms: Response time in milliseconds
            timed_out: Whether the fetch timed out
            escalation_reason: Reason for escalation (if any)

        Returns:
            Updated profile (modified in place, also returned)
        """
        # Update success/failure counts
        if success:
            profile.success_count += 1
            profile.last_successful_fetch = datetime.now(timezone.utc)
        else:
            profile.failure_count += 1

        # Update tier success rate using EMA
        cls._update_tier_success_rate(profile, tier, success)

        # Handle timeout
        if timed_out:
            profile.timeout_count += 1
            if profile.timeout_count >= cls.SLOW_THRESHOLD:
                profile.likely_slow = True
                logger.debug(
                    "Marking %s as likely_slow (timeout_count=%d)",
                    profile.domain,
                    profile.timeout_count,
                )

        # Process escalation reason to set behavior flags
        if escalation_reason:
            cls._process_escalation_reason(profile, escalation_reason)

        # Update last_updated timestamp
        profile.last_updated = datetime.now(timezone.utc)

        logger.debug(
            "Recorded fetch result for %s: tier=%d, success=%s, time=%dms",
            profile.domain,
            tier,
            success,
            response_time_ms,
        )

        return profile

    @classmethod
    def _update_tier_success_rate(
        cls,
        profile: "DomainProfile",
        tier: int,
        success: bool,
    ) -> None:
        """Update the success rate for a specific tier using EMA."""
        # Get current rate
        if tier == 1:
            current_rate = profile.tier1_success_rate
        elif tier == 2:
            current_rate = profile.tier2_success_rate
        elif tier == 3:
            current_rate = profile.tier3_success_rate
        else:
            return

        # Calculate new rate using EMA
        # Success = 1.0, Failure = 0.0
        new_value = 1.0 if success else 0.0
        new_rate = cls.EMA_ALPHA * new_value + (1 - cls.EMA_ALPHA) * current_rate

        # Update the profile
        if tier == 1:
            profile.tier1_success_rate = new_rate
        elif tier == 2:
            profile.tier2_success_rate = new_rate
        elif tier == 3:
            profile.tier3_success_rate = new_rate

        logger.debug(
            "Updated tier %d success rate for %s: %.2f -> %.2f",
            tier,
            profile.domain,
            current_rate,
            new_rate,
        )

    @classmethod
    def _process_escalation_reason(
        cls,
        profile: "DomainProfile",
        reason: str,
    ) -> None:
        """Process escalation reason to set behavior flags."""
        reason_lower = reason.lower()

        # Check for JS-related escalation
        for keyword in cls.JS_KEYWORDS:
            if keyword in reason_lower:
                profile.likely_js_heavy = True
                logger.debug(
                    "Marking %s as likely_js_heavy (reason: %s)",
                    profile.domain,
                    reason,
                )
                break

        # Check for bot protection escalation
        for keyword in cls.BOT_PROTECTION_KEYWORDS:
            if keyword in reason_lower:
                profile.likely_bot_protected = True
                logger.debug(
                    "Marking %s as likely_bot_protected (reason: %s)",
                    profile.domain,
                    reason,
                )
                break

    @classmethod
    def calculate_recommended_tier(cls, profile: "DomainProfile") -> int:
        """
        Calculate recommended tier based on success rates.

        Prefers cheaper tiers when viable.

        Args:
            profile: Domain profile with tier success rates

        Returns:
            Recommended tier (1, 2, or 3)
        """
        # Threshold for considering a tier viable
        MIN_VIABLE = 0.50

        if profile.tier1_success_rate >= MIN_VIABLE:
            return 1
        elif profile.tier2_success_rate >= MIN_VIABLE:
            return 2
        else:
            return 3
