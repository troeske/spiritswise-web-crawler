"""
Smart Tier Selection for Adaptive Fetching.

This module provides intelligent starting tier selection based on:
- Domain behavior flags (JS-heavy, bot-protected)
- Historical success rates per tier
- Manual admin overrides
- Cost optimization (prefer cheaper tiers when viable)

Tier Overview:
- Tier 1: httpx (cheapest, fastest)
- Tier 2: Playwright (JavaScript rendering, moderate cost)
- Tier 3: ScrapingBee (most expensive, best bot bypass)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crawler.fetchers.domain_intelligence import DomainProfile
    from crawler.models import CrawlerSource

logger = logging.getLogger(__name__)


class SmartTierSelector:
    """
    Intelligent tier selection for fetch requests.

    Chooses the optimal starting tier based on domain history,
    behavior flags, and cost considerations.
    """

    # Minimum successful fetches before trusting learned tier
    MIN_FETCHES_FOR_CONFIDENCE = 10

    # Days before retrying lower tier for tier3 sources
    TIER3_RETRY_DAYS = 3

    # Minimum success rate to consider a tier viable
    MIN_VIABLE_SUCCESS_RATE = 0.50  # 50%

    @classmethod
    def select_starting_tier(
        cls,
        domain_profile: "DomainProfile",
        source: Optional["CrawlerSource"] = None,
    ) -> int:
        """
        Choose optimal starting tier for a domain.

        Priority order:
        1. Manual override from DomainProfile
        2. Manual override from CrawlerSource
        3. CrawlerSource.requires_tier3 flag
        4. Domain behavior flags (JS-heavy, bot-protected)
        5. Learned optimal tier (if enough history)
        6. Default to Tier 1 (cheapest)

        Args:
            domain_profile: Domain's historical performance profile
            source: Optional CrawlerSource configuration

        Returns:
            Starting tier (1, 2, or 3)
        """
        # 1. Check domain profile manual override
        if domain_profile.manual_override_tier:
            logger.debug(
                "Using domain profile manual override tier %d for %s",
                domain_profile.manual_override_tier,
                domain_profile.domain,
            )
            return domain_profile.manual_override_tier

        # 2. Check source manual override
        if source and source.manual_tier_override:
            logger.debug(
                "Using source manual override tier %d for %s",
                source.manual_tier_override,
                domain_profile.domain,
            )
            return source.manual_tier_override

        # 3. Check source requires_tier3 flag
        if source and source.requires_tier3:
            logger.debug(
                "Source requires tier 3 for %s",
                domain_profile.domain,
            )
            return 3

        # 4. Check behavior flags
        if domain_profile.likely_bot_protected:
            logger.debug(
                "Domain %s marked as bot-protected, starting at tier 3",
                domain_profile.domain,
            )
            return 3

        if domain_profile.likely_js_heavy:
            logger.debug(
                "Domain %s marked as JS-heavy, starting at tier 2",
                domain_profile.domain,
            )
            return 2

        # 5. Use learned optimal tier if enough history
        total_fetches = domain_profile.success_count + domain_profile.failure_count
        if total_fetches >= cls.MIN_FETCHES_FOR_CONFIDENCE:
            optimal_tier = cls._select_optimal_tier_from_history(domain_profile)
            logger.debug(
                "Using learned optimal tier %d for %s (based on %d fetches)",
                optimal_tier,
                domain_profile.domain,
                total_fetches,
            )
            return optimal_tier

        # 6. Default to cheapest tier
        logger.debug(
            "No history for %s, starting at tier 1",
            domain_profile.domain,
        )
        return 1

    @classmethod
    def _select_optimal_tier_from_history(
        cls,
        domain_profile: "DomainProfile",
    ) -> int:
        """
        Select optimal tier based on historical success rates.

        Prefers cheaper tiers when their success rate is acceptable.

        Args:
            domain_profile: Domain profile with tier success rates

        Returns:
            Optimal tier (1, 2, or 3)
        """
        # Check tiers in order of preference (cheapest first)
        if domain_profile.tier1_success_rate >= cls.MIN_VIABLE_SUCCESS_RATE:
            return 1

        if domain_profile.tier2_success_rate >= cls.MIN_VIABLE_SUCCESS_RATE:
            return 2

        # Default to tier 3 if lower tiers aren't viable
        return 3

    @classmethod
    def should_retry_lower_tier(
        cls,
        source: "CrawlerSource",
        domain_profile: "DomainProfile",
    ) -> bool:
        """
        Check if we should try lower tiers for a tier3 source.

        Periodically retries lower tiers to see if they've become viable
        (site may have changed, bot protection may have been relaxed).

        Args:
            source: CrawlerSource with requires_tier3 flag
            domain_profile: Domain profile

        Returns:
            True if we should retry lower tier
        """
        if not source.requires_tier3:
            return False

        # Check if we've tried lower tier recently
        last_attempt = getattr(source, "last_lower_tier_attempt", None)
        if last_attempt is None:
            # Never tried lower tier, should try
            return True

        # Check if enough time has passed
        days_since = (datetime.now(timezone.utc) - last_attempt).days
        should_retry = days_since >= cls.TIER3_RETRY_DAYS

        if should_retry:
            logger.debug(
                "Should retry lower tier for %s (%d days since last attempt)",
                domain_profile.domain,
                days_since,
            )

        return should_retry

    @classmethod
    def get_tier_name(cls, tier: int) -> str:
        """Get human-readable tier name."""
        tier_names = {
            1: "Tier 1 - httpx",
            2: "Tier 2 - Playwright",
            3: "Tier 3 - ScrapingBee",
        }
        return tier_names.get(tier, f"Tier {tier}")
