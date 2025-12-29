"""
Tests for Rate Limiter and Quota Tracker.

Phase 2: SerpAPI Integration - TDD Tests for rate_limiter.py
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from crawler.discovery.serpapi.rate_limiter import RateLimiter, QuotaTracker


class TestRateLimiterCanMakeRequest:
    """Tests for can_make_request method."""

    def test_can_make_request_under_limit(self):
        """Should return True when under daily limit."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 10  # Low count

            limiter = RateLimiter()
            result = limiter.can_make_request()

            assert result is True

    def test_cannot_make_request_at_limit(self):
        """Should return False when at daily limit."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = RateLimiter.DAILY_LIMIT

            limiter = RateLimiter()
            result = limiter.can_make_request()

            assert result is False

    def test_cannot_make_request_over_limit(self):
        """Should return False when over daily limit."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = RateLimiter.DAILY_LIMIT + 10

            limiter = RateLimiter()
            result = limiter.can_make_request()

            assert result is False

    def test_can_make_request_when_no_previous_requests(self):
        """Should return True when no previous requests (cache returns 0)."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 0

            limiter = RateLimiter()
            result = limiter.can_make_request()

            assert result is True


class TestRateLimiterRecordRequest:
    """Tests for record_request method."""

    def test_record_request_increments_count(self):
        """Should increment daily count in cache."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 5

            limiter = RateLimiter()
            limiter.record_request()

            # Should set count + 1
            calls = mock_cache.set.call_args_list
            # First call is daily, second is monthly
            daily_call = calls[0]
            assert daily_call[0][1] == 6  # 5 + 1

    def test_record_request_increments_monthly_count(self):
        """Should increment monthly count in cache."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 100

            limiter = RateLimiter()
            limiter.record_request()

            # Should have two set calls - daily and monthly
            assert mock_cache.set.call_count == 2

    def test_record_request_sets_cache_expiry(self):
        """Should set appropriate cache expiry times."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 0

            limiter = RateLimiter()
            limiter.record_request()

            calls = mock_cache.set.call_args_list
            # Daily cache: 24 hours = 86400 seconds
            daily_expiry = calls[0][0][2]
            assert daily_expiry == 86400

            # Monthly cache: 30 days = 2592000 seconds
            monthly_expiry = calls[1][0][2]
            assert monthly_expiry == 2592000


class TestRateLimiterDailyKey:
    """Tests for daily key generation."""

    def test_daily_key_includes_date(self):
        """Daily key should include today's date."""
        limiter = RateLimiter()
        key = limiter._daily_key()

        today = datetime.now().strftime("%Y-%m-%d")
        assert today in key

    def test_daily_key_includes_prefix(self):
        """Daily key should include cache prefix."""
        limiter = RateLimiter(cache_prefix="test_prefix")
        key = limiter._daily_key()

        assert "test_prefix" in key

    def test_daily_key_changes_each_day(self):
        """Daily key should change with different dates."""
        limiter = RateLimiter()

        with patch("crawler.discovery.serpapi.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2025-01-15"
            key1 = limiter._daily_key()

            mock_dt.now.return_value.strftime.return_value = "2025-01-16"
            key2 = limiter._daily_key()

        assert key1 != key2


class TestRateLimiterMonthlyKey:
    """Tests for monthly key generation."""

    def test_monthly_key_includes_month(self):
        """Monthly key should include current month."""
        limiter = RateLimiter()
        key = limiter._monthly_key()

        month = datetime.now().strftime("%Y-%m")
        assert month in key

    def test_monthly_key_changes_each_month(self):
        """Monthly key should change with different months."""
        limiter = RateLimiter()

        with patch("crawler.discovery.serpapi.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2025-01"
            key1 = limiter._monthly_key()

            mock_dt.now.return_value.strftime.return_value = "2025-02"
            key2 = limiter._monthly_key()

        assert key1 != key2


class TestRateLimiterGetRemaining:
    """Tests for get_remaining_daily and get_remaining_monthly."""

    def test_get_remaining_daily(self):
        """Should return remaining daily requests."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 50

            limiter = RateLimiter()
            remaining = limiter.get_remaining_daily()

            assert remaining == RateLimiter.DAILY_LIMIT - 50

    def test_get_remaining_daily_never_negative(self):
        """Should never return negative remaining."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = RateLimiter.DAILY_LIMIT + 100

            limiter = RateLimiter()
            remaining = limiter.get_remaining_daily()

            assert remaining == 0

    def test_get_remaining_monthly(self):
        """Should return remaining monthly requests."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 1000

            limiter = RateLimiter()
            remaining = limiter.get_remaining_monthly()

            assert remaining == RateLimiter.MONTHLY_QUOTA - 1000

    def test_get_remaining_monthly_never_negative(self):
        """Should never return negative remaining."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = RateLimiter.MONTHLY_QUOTA + 100

            limiter = RateLimiter()
            remaining = limiter.get_remaining_monthly()

            assert remaining == 0


class TestQuotaTrackerGetUsageStats:
    """Tests for QuotaTracker.get_usage_stats."""

    def test_get_usage_stats_returns_dict(self):
        """Should return usage statistics dictionary."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 50

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)
            stats = tracker.get_usage_stats()

            assert isinstance(stats, dict)
            assert "daily_remaining" in stats
            assert "daily_limit" in stats
            assert "monthly_remaining" in stats
            assert "monthly_limit" in stats

    def test_get_usage_stats_includes_limits(self):
        """Should include configured limits."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            mock_cache.get.return_value = 0

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)
            stats = tracker.get_usage_stats()

            assert stats["daily_limit"] == RateLimiter.DAILY_LIMIT
            assert stats["monthly_limit"] == RateLimiter.MONTHLY_QUOTA


class TestQuotaTrackerIsQuotaLow:
    """Tests for QuotaTracker.is_quota_low."""

    def test_is_quota_low_under_threshold(self):
        """Should return True when quota is under threshold."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            # Set monthly count high (4900 out of 5000 = 100 remaining = 2%)
            mock_cache.get.return_value = 4900

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)

            assert tracker.is_quota_low(threshold=0.1) is True

    def test_is_quota_low_above_threshold(self):
        """Should return False when quota is above threshold."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            # Set monthly count low (1000 out of 5000 = 4000 remaining = 80%)
            mock_cache.get.return_value = 1000

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)

            assert tracker.is_quota_low(threshold=0.1) is False

    def test_is_quota_low_default_threshold(self):
        """Should use default 10% threshold."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            # 4600 used = 400 remaining = 8% (under 10% threshold)
            mock_cache.get.return_value = 4600

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)

            assert tracker.is_quota_low() is True

    def test_is_quota_low_custom_threshold(self):
        """Should respect custom threshold."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache") as mock_cache:
            # 4000 used = 1000 remaining = 20%
            mock_cache.get.return_value = 4000

            limiter = RateLimiter()
            tracker = QuotaTracker(limiter)

            # 20% remaining is low for 25% threshold
            assert tracker.is_quota_low(threshold=0.25) is True
            # But not low for 10% threshold
            assert tracker.is_quota_low(threshold=0.1) is False


class TestRateLimiterConstants:
    """Tests for RateLimiter constants."""

    def test_monthly_quota_constant(self):
        """Should have correct monthly quota."""
        assert RateLimiter.MONTHLY_QUOTA == 5000

    def test_daily_limit_constant(self):
        """Should have correct daily limit."""
        # ~5000 / 30 days = ~165
        assert RateLimiter.DAILY_LIMIT == 165


class TestRateLimiterCachePrefix:
    """Tests for custom cache prefix."""

    def test_custom_prefix_in_daily_key(self):
        """Should use custom prefix in daily key."""
        limiter = RateLimiter(cache_prefix="custom")
        key = limiter._daily_key()

        assert key.startswith("custom:")

    def test_custom_prefix_in_monthly_key(self):
        """Should use custom prefix in monthly key."""
        limiter = RateLimiter(cache_prefix="custom")
        key = limiter._monthly_key()

        assert key.startswith("custom:")

    def test_default_prefix(self):
        """Should use 'serpapi' as default prefix."""
        limiter = RateLimiter()
        key = limiter._daily_key()

        assert key.startswith("serpapi:")
