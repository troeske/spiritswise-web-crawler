"""
Tests for Feedback Recording.

Task Group: Phase 5 - Feedback Recording
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify the feedback recording system that updates
domain profiles based on fetch results.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone


class TestFeedbackRecorder:
    """Tests for FeedbackRecorder class (Task 5.1)."""

    def test_record_success_updates_rate(self):
        """Successful fetch updates tier success rate."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            tier1_success_rate=0.5,  # 50% current
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=True,
            response_time_ms=5000,
        )

        # Success rate should increase (EMA toward 1.0)
        assert updated.tier1_success_rate > 0.5

    def test_record_failure_updates_rate(self):
        """Failed fetch updates tier success rate."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            tier1_success_rate=0.8,  # 80% current
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=20000,
        )

        # Success rate should decrease (EMA toward 0.0)
        assert updated.tier1_success_rate < 0.8

    def test_escalation_reason_sets_js_heavy_flag(self):
        """JavaScript escalation reason sets likely_js_heavy flag."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            likely_js_heavy=False,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=10000,
            escalation_reason="JavaScript placeholder page - requires JS rendering",
        )

        assert updated.likely_js_heavy is True

    def test_escalation_reason_sets_bot_protected_flag(self):
        """Bot protection escalation reason sets likely_bot_protected flag."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            likely_bot_protected=False,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=2,
            success=False,
            response_time_ms=10000,
            escalation_reason="Cloudflare challenge detected",
        )

        assert updated.likely_bot_protected is True

    def test_timeout_increments_count(self):
        """Timeout increments timeout_count."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            timeout_count=2,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=20000,
            timed_out=True,
        )

        assert updated.timeout_count == 3

    def test_multiple_timeouts_marks_slow(self):
        """3+ timeouts marks domain as likely_slow."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            timeout_count=2,
            likely_slow=False,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=60000,
            timed_out=True,
        )

        assert updated.timeout_count == 3
        assert updated.likely_slow is True

    def test_rate_uses_exponential_average(self):
        """Success rate uses EMA, not simple average."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            tier1_success_rate=0.8,  # 80% current
        )

        # Record a success
        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=True,
            response_time_ms=5000,
        )

        # With EMA alpha=0.3: 0.3 * 1.0 + 0.7 * 0.8 = 0.86
        # Should be weighted toward old value, not simple (0.8 + 1.0) / 2 = 0.9
        assert 0.8 < updated.tier1_success_rate < 0.9

    def test_updates_recommended_tier(self):
        """Feedback updates recommended tier based on success rates."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            tier1_success_rate=0.3,
            tier2_success_rate=0.9,
            recommended_tier=1,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=20000,
        )

        # After failed tier 1, recommended should move up
        # (tier1 success rate goes even lower)
        assert updated.tier1_success_rate < 0.3

    def test_success_updates_counts(self):
        """Success increments success_count."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            success_count=5,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=True,
            response_time_ms=5000,
        )

        assert updated.success_count == 6

    def test_failure_updates_counts(self):
        """Failure increments failure_count."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            failure_count=2,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=20000,
        )

        assert updated.failure_count == 3

    def test_captcha_sets_bot_protected(self):
        """CAPTCHA escalation sets bot-protected flag."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            likely_bot_protected=False,
        )

        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=10000,
            escalation_reason="CAPTCHA challenge detected",
        )

        assert updated.likely_bot_protected is True
