"""
Tests for CrawlSchedule model and scheduling utilities.

Task Group 15: CrawlSchedule Model
These tests verify crawl scheduling per discovery source with exponential backoff.

TDD: Tests written first before implementation.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone


class TestCrawlScheduleCreation:
    """Tests for CrawlSchedule creation with required fields."""

    def test_crawl_schedule_creation_with_required_fields(self, db):
        """CrawlSchedule should be created with required fields."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        # Create a discovery source first
        source = DiscoverySourceConfig.objects.create(
            name="Test Source Schedule",
            base_url="https://example.com",
            source_type=DiscoverySourceTypeChoices.AWARD_COMPETITION,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.DAILY,
            reliability_score=7,
        )

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="daily",
            next_run=now + timedelta(hours=24),
        )

        assert schedule.id is not None
        assert schedule.discovery_source == source
        assert schedule.schedule_type == "daily"
        assert schedule.next_run is not None
        assert schedule.is_active is True  # Default
        assert schedule.priority_boost == 0  # Default
        assert schedule.pages_per_run == 100  # Default
        assert schedule.error_count == 0  # Default
        assert schedule.paused_until is None  # Default

    def test_crawl_schedule_types_validation(self, db):
        """CrawlSchedule should support all schedule types: daily, weekly, monthly, on_demand."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
            ScheduleTypeChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Types",
            base_url="https://example.com/types",
            source_type=DiscoverySourceTypeChoices.REVIEW_BLOG,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=6,
        )

        now = timezone.now()

        # Test all schedule types
        for schedule_type in [
            ScheduleTypeChoices.DAILY,
            ScheduleTypeChoices.WEEKLY,
            ScheduleTypeChoices.MONTHLY,
            ScheduleTypeChoices.ON_DEMAND,
        ]:
            schedule = CrawlSchedule.objects.create(
                discovery_source=source,
                schedule_type=schedule_type,
                next_run=now,
            )
            assert schedule.schedule_type == schedule_type

    def test_crawl_schedule_related_name(self, db):
        """DiscoverySourceConfig should access schedules via related_name 'schedules'."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Related",
            base_url="https://example.com/related",
            source_type=DiscoverySourceTypeChoices.RETAILER,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.DAILY,
            reliability_score=8,
        )

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="daily",
            next_run=now,
        )

        # Access via related_name
        assert source.schedules.count() == 1
        assert source.schedules.first() == schedule


class TestNextRunCalculation:
    """Tests for next_run calculation based on schedule_type."""

    def test_calculate_next_run_daily(self):
        """Daily schedule should set next_run to 24 hours from now."""
        from crawler.utils.scheduling import calculate_next_run

        now = timezone.now()
        next_run = calculate_next_run("daily", now)

        expected = now + timedelta(hours=24)
        # Allow 1 second tolerance
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_weekly(self):
        """Weekly schedule should set next_run to 7 days from now."""
        from crawler.utils.scheduling import calculate_next_run

        now = timezone.now()
        next_run = calculate_next_run("weekly", now)

        expected = now + timedelta(days=7)
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_monthly(self):
        """Monthly schedule should set next_run to 30 days from now."""
        from crawler.utils.scheduling import calculate_next_run

        now = timezone.now()
        next_run = calculate_next_run("monthly", now)

        expected = now + timedelta(days=30)
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_on_demand(self):
        """On-demand schedule should not set automatic next_run (returns None)."""
        from crawler.utils.scheduling import calculate_next_run

        now = timezone.now()
        next_run = calculate_next_run("on_demand", now)

        # On-demand schedules don't automatically schedule next run
        assert next_run is None


class TestErrorCountAndBackoff:
    """Tests for error_count tracking and exponential backoff behavior."""

    def test_error_count_increments(self, db):
        """error_count should be incrementable on schedule."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Errors",
            base_url="https://example.com/errors",
            source_type=DiscoverySourceTypeChoices.NEWS_OUTLET,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.DAILY,
            reliability_score=5,
        )

        schedule = CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="daily",
            next_run=timezone.now(),
        )

        assert schedule.error_count == 0

        schedule.error_count += 1
        schedule.save()
        schedule.refresh_from_db()

        assert schedule.error_count == 1

    def test_exponential_backoff_calculation(self):
        """Next_run should have exponential backoff applied when error_count > 0.

        Uses weekly schedule (7 days) to test backoff without hitting the 7-day cap.
        - 0 errors: 7 days
        - 1 error: 14 days (but capped at 7 days)
        So we test with small error counts that stay under cap for 24h base.
        """
        from crawler.utils.scheduling import calculate_next_run_with_backoff

        now = timezone.now()
        base_interval = timedelta(hours=24)

        # No errors - no backoff
        next_run_0 = calculate_next_run_with_backoff("daily", now, error_count=0)
        expected_0 = now + base_interval
        assert abs((next_run_0 - expected_0).total_seconds()) < 1

        # 1 error - 2x backoff (48 hours)
        next_run_1 = calculate_next_run_with_backoff("daily", now, error_count=1)
        expected_1 = now + (base_interval * 2)
        assert abs((next_run_1 - expected_1).total_seconds()) < 1

        # 2 errors - 4x backoff (96 hours = 4 days, under cap)
        next_run_2 = calculate_next_run_with_backoff("daily", now, error_count=2)
        expected_2 = now + (base_interval * 4)
        assert abs((next_run_2 - expected_2).total_seconds()) < 1

        # 3 errors - 8x backoff (192 hours = 8 days) but capped at 7 days
        next_run_3 = calculate_next_run_with_backoff("daily", now, error_count=3)
        max_delay = timedelta(days=7)
        # Should be capped at 7 days, not 8 days
        assert (next_run_3 - now) <= max_delay
        assert (next_run_3 - now) == max_delay  # Exactly at cap

    def test_backoff_has_maximum_limit(self):
        """Exponential backoff should have a maximum cap to prevent excessive delays."""
        from crawler.utils.scheduling import calculate_next_run_with_backoff

        now = timezone.now()

        # 10 errors would be 2^10 = 1024x backoff without cap
        # Should be capped at reasonable maximum (e.g., 7 days max delay)
        next_run = calculate_next_run_with_backoff("daily", now, error_count=10)

        max_delay = timedelta(days=7)
        assert (next_run - now) <= max_delay

    def test_paused_until_respected_in_calculation(self):
        """Next_run calculation should respect paused_until if set."""
        from crawler.utils.scheduling import calculate_next_run_with_backoff

        now = timezone.now()
        paused_until = now + timedelta(days=3)

        # If paused_until is set and is after calculated next_run, use paused_until
        next_run = calculate_next_run_with_backoff(
            "daily",
            now,
            error_count=0,
            paused_until=paused_until,
        )

        # Should be at least paused_until
        assert next_run >= paused_until


class TestPagesPerRunLimiting:
    """Tests for pages_per_run field and limiting behavior."""

    def test_pages_per_run_default_value(self, db):
        """pages_per_run should default to 100."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Pages",
            base_url="https://example.com/pages",
            source_type=DiscoverySourceTypeChoices.AGGREGATOR,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.DAILY,
            reliability_score=5,
        )

        schedule = CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="daily",
            next_run=timezone.now(),
        )

        assert schedule.pages_per_run == 100

    def test_pages_per_run_can_be_customized(self, db):
        """pages_per_run should be customizable per schedule."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Pages Custom",
            base_url="https://example.com/pages-custom",
            source_type=DiscoverySourceTypeChoices.AWARD_COMPETITION,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=9,
        )

        schedule = CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="weekly",
            next_run=timezone.now(),
            pages_per_run=500,
        )

        assert schedule.pages_per_run == 500


class TestScheduleQueryOptimization:
    """Tests for schedule query optimization via indexes."""

    def test_active_schedules_query(self, db):
        """Should efficiently query active schedules ready to run."""
        from crawler.models import (
            CrawlSchedule,
            DiscoverySourceConfig,
            DiscoverySourceTypeChoices,
            CrawlFrequencyChoices,
        )

        source = DiscoverySourceConfig.objects.create(
            name="Test Source Query",
            base_url="https://example.com/query",
            source_type=DiscoverySourceTypeChoices.REVIEW_BLOG,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.DAILY,
            reliability_score=5,
        )

        now = timezone.now()

        # Create schedules - some due, some not
        CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="daily",
            next_run=now - timedelta(hours=1),  # Due
            is_active=True,
        )
        CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="weekly",
            next_run=now + timedelta(hours=1),  # Not due
            is_active=True,
        )
        CrawlSchedule.objects.create(
            discovery_source=source,
            schedule_type="monthly",
            next_run=now - timedelta(hours=2),  # Due but inactive
            is_active=False,
        )

        # Query active schedules due to run
        due_schedules = CrawlSchedule.objects.filter(
            is_active=True,
            next_run__lte=now,
        )

        assert due_schedules.count() == 1
        assert due_schedules.first().schedule_type == "daily"
