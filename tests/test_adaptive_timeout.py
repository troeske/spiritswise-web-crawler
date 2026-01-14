"""
Tests for Adaptive Timeout Strategy.

Task Group: Phase 3 - Adaptive Timeout Strategy
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify the timeout calculation and learning logic
for adapting timeouts based on domain performance history.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


class TestAdaptiveTimeout:
    """Tests for AdaptiveTimeout class (Task 3.1)."""

    def test_base_timeout_for_unknown_domain(self):
        """Unknown domain gets 20s base timeout."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        # New domain with no history
        profile = DomainProfile(domain="unknown-domain.com")

        timeout = AdaptiveTimeout.get_timeout(profile, attempt=0)
        assert timeout == 20000  # 20s in milliseconds

    def test_progressive_timeout_increase(self):
        """Timeout doubles on each attempt: 20s -> 40s -> 60s."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="test.com")

        timeout_0 = AdaptiveTimeout.get_timeout(profile, attempt=0)
        timeout_1 = AdaptiveTimeout.get_timeout(profile, attempt=1)
        timeout_2 = AdaptiveTimeout.get_timeout(profile, attempt=2)

        assert timeout_0 == 20000  # 20s
        assert timeout_1 == 40000  # 40s
        assert timeout_2 == 60000  # 60s (capped)

    def test_max_timeout_cap(self):
        """Timeout never exceeds 60s."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="test.com")

        # Even on attempt 10, shouldn't exceed 60s
        timeout = AdaptiveTimeout.get_timeout(profile, attempt=10)
        assert timeout <= 60000

    def test_learned_timeout_used(self):
        """Domain with history uses learned timeout."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Domain with learned history - typically responds in 5s
        profile = DomainProfile(
            domain="fast-site.com",
            avg_response_time_ms=5000,  # 5s average
            success_count=10,  # Has enough history
            recommended_timeout_ms=15000,  # Learned: ~3x avg
        )

        timeout = AdaptiveTimeout.get_timeout(profile, attempt=0)
        # Should use learned timeout (15s) as base, not default 20s
        assert timeout == 15000

    def test_slow_domain_multiplier(self):
        """Domains marked slow get increased timeout."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Domain marked as slow
        profile = DomainProfile(
            domain="slow-site.com",
            likely_slow=True,
            success_count=5,
        )

        timeout = AdaptiveTimeout.get_timeout(profile, attempt=0)
        # Slow domains get 1.5x multiplier on base timeout
        assert timeout >= 30000  # 20s * 1.5 = 30s

    def test_manual_override_respected(self):
        """Manual timeout override takes precedence."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="competition-site.com",
            manual_override_timeout_ms=45000,  # Admin set to 45s
            recommended_timeout_ms=20000,  # Learned is lower
        )

        timeout = AdaptiveTimeout.get_timeout(profile, attempt=0)
        assert timeout == 45000  # Manual override wins

    def test_update_profile_after_success(self):
        """Success updates avg response time and recommended timeout."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            avg_response_time_ms=10000,  # 10s average
            success_count=5,
        )

        updated = AdaptiveTimeout.update_profile_after_fetch(
            profile=profile,
            response_time_ms=5000,  # Fast 5s response
            success=True,
        )

        # Success count should increase
        assert updated.success_count == 6
        # Average should move toward new value (exponential moving average)
        assert updated.avg_response_time_ms < 10000  # Should decrease
        # Recommended timeout should be updated
        assert updated.recommended_timeout_ms > 0
        # Last successful fetch should be set
        assert updated.last_successful_fetch is not None

    def test_update_profile_after_failure(self):
        """Failure updates failure count."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            failure_count=2,
        )

        updated = AdaptiveTimeout.update_profile_after_fetch(
            profile=profile,
            response_time_ms=20000,
            success=False,
        )

        # Failure count should increase
        assert updated.failure_count == 3

    def test_update_profile_after_timeout(self):
        """Timeout increases timeout count and recommends higher timeout."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            timeout_count=1,
            recommended_timeout_ms=20000,
        )

        updated = AdaptiveTimeout.update_profile_after_fetch(
            profile=profile,
            response_time_ms=20000,  # Hit timeout
            success=False,
            timed_out=True,
        )

        assert updated.timeout_count == 2
        # Recommended timeout should increase after timeout
        assert updated.recommended_timeout_ms > 20000

    def test_exponential_moving_average(self):
        """Average response time uses exponential moving average."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            avg_response_time_ms=10000,  # 10s current average
            success_count=10,
        )

        # New response time of 2s
        updated = AdaptiveTimeout.update_profile_after_fetch(
            profile=profile,
            response_time_ms=2000,
            success=True,
        )

        # EMA with alpha=0.2: 0.2 * 2000 + 0.8 * 10000 = 8400
        # Should be somewhere between old and new, weighted toward old
        assert 2000 < updated.avg_response_time_ms < 10000

    def test_min_fetches_for_learned_timeout(self):
        """Learned timeout not used until minimum fetches reached."""
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Only 3 fetches - not enough history
        profile = DomainProfile(
            domain="test.com",
            success_count=3,
            avg_response_time_ms=5000,
            recommended_timeout_ms=15000,
        )

        timeout = AdaptiveTimeout.get_timeout(profile, attempt=0)
        # Should use base timeout, not learned (not enough history)
        assert timeout == 20000
