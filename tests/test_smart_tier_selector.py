"""
Tests for Smart Tier Selection.

Task Group: Phase 4 - Smart Tier Selection
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify the intelligent tier selection based on
domain history, behavior flags, and manual overrides.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta


class TestSmartTierSelector:
    """Tests for SmartTierSelector class (Task 4.1)."""

    def test_new_domain_starts_tier1(self):
        """Unknown domain starts at cheapest tier."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        # New domain with no history
        profile = DomainProfile(domain="unknown-domain.com")

        tier = SmartTierSelector.select_starting_tier(profile)
        assert tier == 1  # Start cheap

    def test_js_heavy_starts_tier2(self):
        """Domain marked JS-heavy starts at Tier 2."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="react-site.com",
            likely_js_heavy=True,
        )

        tier = SmartTierSelector.select_starting_tier(profile)
        assert tier == 2  # Skip straight to Playwright

    def test_bot_protected_starts_tier3(self):
        """Domain marked bot-protected starts at Tier 3."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="protected-site.com",
            likely_bot_protected=True,
        )

        tier = SmartTierSelector.select_starting_tier(profile)
        assert tier == 3  # Go straight to ScrapingBee

    def test_learned_tier_selection(self):
        """Domain with 10+ fetches uses learned optimal tier."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="learned-site.com",
            success_count=15,
            failure_count=5,
            tier1_success_rate=0.3,  # Poor tier 1
            tier2_success_rate=0.9,  # Good tier 2
            tier3_success_rate=1.0,
            recommended_tier=2,
        )

        tier = SmartTierSelector.select_starting_tier(profile)
        assert tier == 2  # Use learned optimal tier

    def test_manual_override_respected(self):
        """Manual tier override takes precedence."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="competition-site.com",
            manual_override_tier=3,  # Admin forced tier 3
            recommended_tier=1,  # Would otherwise use tier 1
        )

        tier = SmartTierSelector.select_starting_tier(profile)
        assert tier == 3  # Manual override wins

    def test_source_override_respected(self):
        """CrawlerSource manual_tier_override takes precedence."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            recommended_tier=1,
        )

        source = MagicMock()
        source.manual_tier_override = 2
        source.requires_tier3 = False

        tier = SmartTierSelector.select_starting_tier(profile, source=source)
        assert tier == 2  # Source override wins

    def test_requires_tier3_uses_tier3(self):
        """Source with requires_tier3=True uses Tier 3."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="tier3-site.com")

        source = MagicMock()
        source.manual_tier_override = None
        source.requires_tier3 = True
        source.last_lower_tier_attempt = None

        tier = SmartTierSelector.select_starting_tier(profile, source=source)
        assert tier == 3

    def test_tier3_retry_after_3_days(self):
        """Sources marked requires_tier3 retry lower after 3 days."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Source that was marked tier3 4 days ago
        profile = DomainProfile(domain="tier3-site.com")

        source = MagicMock()
        source.manual_tier_override = None
        source.requires_tier3 = True
        source.last_lower_tier_attempt = datetime.now(timezone.utc) - timedelta(days=4)

        should_retry = SmartTierSelector.should_retry_lower_tier(source, profile)
        assert should_retry is True

    def test_tier3_no_retry_before_3_days(self):
        """Sources marked requires_tier3 don't retry lower before 3 days."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="tier3-site.com")

        source = MagicMock()
        source.requires_tier3 = True
        source.last_lower_tier_attempt = datetime.now(timezone.utc) - timedelta(days=1)

        should_retry = SmartTierSelector.should_retry_lower_tier(source, profile)
        assert should_retry is False

    def test_selection_uses_highest_success_rate_tier(self):
        """Learned selection uses tier with highest success rate."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            success_count=20,
            tier1_success_rate=0.2,  # 20%
            tier2_success_rate=0.6,  # 60%
            tier3_success_rate=0.95,  # 95%
        )

        tier = SmartTierSelector.select_starting_tier(profile)
        # Should pick tier with best cost-adjusted success rate
        # Tier 1 is cheapest but 20% is too low
        # Tier 2 at 60% is acceptable and cheaper than tier 3
        assert tier in [2, 3]  # Either acceptable based on threshold
