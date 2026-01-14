"""
Tests for Domain Intelligence Store.

Task Group: Phase 1 - Domain Intelligence Store
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify the domain profile model and Redis-backed storage
for learning site-specific behavior patterns.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestCrawlerSourceOverrideFields:
    """Tests for CrawlerSource manual override fields (Task 1.4)."""

    def test_crawler_source_has_override_fields(self):
        """CrawlerSource model has manual override fields."""
        from crawler.models import CrawlerSource

        # Check fields exist
        field_names = [f.name for f in CrawlerSource._meta.fields]
        assert "manual_tier_override" in field_names
        assert "manual_timeout_override" in field_names

    def test_override_fields_are_nullable(self):
        """Override fields are nullable (most sources won't have overrides)."""
        from crawler.models import CrawlerSource

        tier_field = CrawlerSource._meta.get_field("manual_tier_override")
        timeout_field = CrawlerSource._meta.get_field("manual_timeout_override")

        assert tier_field.null is True
        assert tier_field.blank is True
        assert timeout_field.null is True
        assert timeout_field.blank is True

    def test_tier_override_has_choices(self):
        """Tier override field has valid choices (1, 2, 3)."""
        from crawler.models import CrawlerSource

        tier_field = CrawlerSource._meta.get_field("manual_tier_override")
        tier_values = [choice[0] for choice in tier_field.choices]

        assert 1 in tier_values
        assert 2 in tier_values
        assert 3 in tier_values


class TestDomainProfile:
    """Tests for DomainProfile dataclass."""

    def test_domain_profile_defaults(self):
        """New profile has sensible defaults."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="example.com")

        # Check defaults
        assert profile.domain == "example.com"
        assert profile.avg_response_time_ms == 0.0
        assert profile.timeout_count == 0
        assert profile.success_count == 0
        assert profile.failure_count == 0
        # Tier success rates start optimistic
        assert profile.tier1_success_rate == 1.0
        assert profile.tier2_success_rate == 1.0
        assert profile.tier3_success_rate == 1.0
        # Behavior flags default to False
        assert profile.likely_js_heavy is False
        assert profile.likely_bot_protected is False
        assert profile.likely_slow is False
        # Recommended settings
        assert profile.recommended_tier == 1
        assert profile.recommended_timeout_ms == 20000  # 20s base
        # Timestamps are None initially
        assert profile.last_updated is None
        assert profile.last_successful_fetch is None
        # Manual overrides are None
        assert profile.manual_override_tier is None
        assert profile.manual_override_timeout_ms is None

    def test_domain_profile_serialization(self):
        """Profile can be serialized to/from JSON."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        now = datetime.now(timezone.utc)
        profile = DomainProfile(
            domain="whiskybase.com",
            avg_response_time_ms=1500.5,
            timeout_count=3,
            success_count=10,
            failure_count=2,
            tier1_success_rate=0.5,
            tier2_success_rate=0.8,
            tier3_success_rate=1.0,
            likely_js_heavy=True,
            likely_bot_protected=False,
            likely_slow=True,
            recommended_tier=2,
            recommended_timeout_ms=30000,
            last_updated=now,
            last_successful_fetch=now,
        )

        # Serialize to JSON
        json_str = profile.to_json()
        assert isinstance(json_str, str)

        # Deserialize from JSON
        restored = DomainProfile.from_json(json_str)
        assert restored.domain == "whiskybase.com"
        assert restored.avg_response_time_ms == 1500.5
        assert restored.timeout_count == 3
        assert restored.success_count == 10
        assert restored.failure_count == 2
        assert restored.tier1_success_rate == 0.5
        assert restored.tier2_success_rate == 0.8
        assert restored.tier3_success_rate == 1.0
        assert restored.likely_js_heavy is True
        assert restored.likely_bot_protected is False
        assert restored.likely_slow is True
        assert restored.recommended_tier == 2
        assert restored.recommended_timeout_ms == 30000
        # Datetime should be preserved
        assert restored.last_updated is not None
        assert restored.last_successful_fetch is not None

    def test_domain_profile_from_dict(self):
        """Profile can be created from dict."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        data = {
            "domain": "smws.com",
            "avg_response_time_ms": 2000.0,
            "success_count": 5,
            "tier1_success_rate": 0.2,
            "likely_bot_protected": True,
            "recommended_tier": 3,
        }

        profile = DomainProfile.from_dict(data)
        assert profile.domain == "smws.com"
        assert profile.avg_response_time_ms == 2000.0
        assert profile.success_count == 5
        assert profile.tier1_success_rate == 0.2
        assert profile.likely_bot_protected is True
        assert profile.recommended_tier == 3
        # Non-specified fields should have defaults
        assert profile.timeout_count == 0
        assert profile.likely_js_heavy is False

    def test_domain_profile_to_dict(self):
        """Profile can be converted to dict."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            success_count=10,
            likely_slow=True,
        )

        data = profile.to_dict()
        assert isinstance(data, dict)
        assert data["domain"] == "test.com"
        assert data["success_count"] == 10
        assert data["likely_slow"] is True

    def test_domain_profile_handles_null_timestamps(self):
        """Profile handles null timestamps in serialization."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="example.com")
        json_str = profile.to_json()
        restored = DomainProfile.from_json(json_str)

        assert restored.last_updated is None
        assert restored.last_successful_fetch is None

    def test_domain_profile_total_fetches(self):
        """Profile calculates total fetches correctly."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            success_count=10,
            failure_count=3,
        )

        assert profile.total_fetches == 13

    def test_domain_profile_overall_success_rate(self):
        """Profile calculates overall success rate correctly."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            success_count=8,
            failure_count=2,
        )

        assert profile.overall_success_rate == 0.8

    def test_domain_profile_overall_success_rate_no_fetches(self):
        """Profile returns 1.0 success rate when no fetches yet."""
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(domain="new-domain.com")
        assert profile.overall_success_rate == 1.0


class TestDomainIntelligenceStore:
    """Tests for DomainIntelligenceStore class."""

    def test_store_get_nonexistent_domain(self):
        """Returns new profile for unknown domain."""
        from crawler.fetchers.domain_intelligence import (
            DomainIntelligenceStore,
            DomainProfile,
        )

        # Mock the cache to return None (cache miss)
        with patch("crawler.fetchers.domain_intelligence.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_caches.__getitem__.return_value = mock_cache

            store = DomainIntelligenceStore()
            profile = store.get_profile("unknown-domain.com")

            assert isinstance(profile, DomainProfile)
            assert profile.domain == "unknown-domain.com"
            # Should have defaults
            assert profile.success_count == 0
            assert profile.recommended_tier == 1

    def test_store_save_and_retrieve(self):
        """Profile persists to cache and can be retrieved."""
        from crawler.fetchers.domain_intelligence import (
            DomainIntelligenceStore,
            DomainProfile,
        )

        saved_data = {}

        def mock_set(key, value, timeout=None):
            saved_data[key] = value
            return True

        def mock_get(key):
            return saved_data.get(key)

        with patch("crawler.fetchers.domain_intelligence.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.set = mock_set
            mock_cache.get = mock_get
            mock_caches.__getitem__.return_value = mock_cache

            store = DomainIntelligenceStore()

            # Save a profile
            profile = DomainProfile(
                domain="test-domain.com",
                success_count=5,
                tier1_success_rate=0.8,
            )
            result = store.save_profile(profile)
            assert result is True

            # Retrieve it
            retrieved = store.get_profile("test-domain.com")
            assert retrieved.domain == "test-domain.com"
            assert retrieved.success_count == 5
            assert retrieved.tier1_success_rate == 0.8

    def test_store_ttl_applied(self):
        """Saved profiles have 30-day TTL."""
        from crawler.fetchers.domain_intelligence import (
            DomainIntelligenceStore,
            DomainProfile,
        )

        captured_timeout = None

        def mock_set(key, value, timeout=None):
            nonlocal captured_timeout
            captured_timeout = timeout
            return True

        with patch("crawler.fetchers.domain_intelligence.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.set = mock_set
            mock_caches.__getitem__.return_value = mock_cache

            store = DomainIntelligenceStore()
            profile = DomainProfile(domain="test.com")
            store.save_profile(profile)

            # TTL should be 30 days in seconds
            expected_ttl = 30 * 24 * 60 * 60
            assert captured_timeout == expected_ttl

    def test_store_handles_cache_unavailable(self):
        """Returns default profile if cache fails."""
        from crawler.fetchers.domain_intelligence import (
            DomainIntelligenceStore,
            DomainProfile,
        )

        with patch("crawler.fetchers.domain_intelligence.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.get.side_effect = Exception("Redis unavailable")
            mock_caches.__getitem__.return_value = mock_cache

            store = DomainIntelligenceStore()
            profile = store.get_profile("test.com")

            # Should return a default profile, not raise
            assert isinstance(profile, DomainProfile)
            assert profile.domain == "test.com"

    def test_store_cache_key_format(self):
        """Cache keys have proper format."""
        from crawler.fetchers.domain_intelligence import DomainIntelligenceStore

        store = DomainIntelligenceStore()
        key = store._get_cache_key("example.com")

        assert key.startswith("domain_intel:")
        assert "example.com" in key

    def test_store_delete_profile(self):
        """Profile can be deleted."""
        from crawler.fetchers.domain_intelligence import (
            DomainIntelligenceStore,
            DomainProfile,
        )

        deleted_keys = []

        def mock_delete(key):
            deleted_keys.append(key)
            return True

        with patch("crawler.fetchers.domain_intelligence.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.delete = mock_delete
            mock_caches.__getitem__.return_value = mock_cache

            store = DomainIntelligenceStore()
            result = store.delete_profile("test.com")

            assert result is True
            assert len(deleted_keys) == 1
            assert "test.com" in deleted_keys[0]
