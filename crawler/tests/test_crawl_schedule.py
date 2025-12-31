"""
Tests for CrawlSchedule model and scheduling utilities.

RECT-016: CrawlSchedule Implementation
These tests verify crawl scheduling per discovery source with exponential backoff.

Updated to match actual CrawlSchedule model fields.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from crawler.models import (
    CrawlSchedule,
    DiscoverySourceConfig,
    SourceTypeChoices,
    CrawlFrequencyChoices,
)
from crawler.utils.scheduling import (
    calculate_next_run,
    calculate_next_run_with_backoff,
    reset_error_backoff,
    apply_error_backoff,
    get_due_schedules,
)


@pytest.fixture
def sample_source(db):
    """Create a sample DiscoverySourceConfig for tests."""
    return DiscoverySourceConfig.objects.create(
        name="Test Schedule Source",
        base_url="https://example.com",
        source_type=SourceTypeChoices.AWARD_COMPETITION,
        crawl_priority=5,
        crawl_frequency=CrawlFrequencyChoices.DAILY,
        reliability_score=8,
    )


@pytest.fixture
def sample_schedule(db, sample_source):
    """Create a sample CrawlSchedule for tests."""
    return CrawlSchedule.objects.create(
        source=sample_source,
        next_run=timezone.now() + timedelta(hours=24),
    )


class TestCrawlScheduleCreation:
    """Tests for CrawlSchedule creation with required fields."""

    def test_crawl_schedule_creation_with_required_fields(self, db, sample_source):
        """CrawlSchedule should be created with required fields."""
        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now + timedelta(hours=24),
        )

        assert schedule.id is not None
        assert schedule.source == sample_source
        assert schedule.next_run is not None
        assert schedule.is_active is True  # Default
        assert schedule.priority_boost == 0  # Default
        assert schedule.consecutive_errors == 0  # Default
        assert schedule.current_backoff_hours == 0  # Default

    def test_crawl_schedule_related_name(self, db, sample_source):
        """DiscoverySourceConfig should access schedules via related_name 'schedules'."""
        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now,
        )

        # Access via related_name
        assert sample_source.schedules.count() == 1
        assert sample_source.schedules.first() == schedule

    def test_crawl_schedule_last_run_and_status(self, db, sample_source):
        """CrawlSchedule tracks last_run and last_status."""
        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now + timedelta(hours=24),
            last_run=now,
            last_status="success",
        )

        assert schedule.last_run == now
        assert schedule.last_status == "success"


class TestNextRunCalculation:
    """Tests for next_run calculation based on schedule_type."""

    def test_calculate_next_run_daily(self):
        """Daily schedule should set next_run to 24 hours from now."""
        now = timezone.now()
        next_run = calculate_next_run("daily", now)

        expected = now + timedelta(hours=24)
        # Allow 1 second tolerance
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_weekly(self):
        """Weekly schedule should set next_run to 7 days from now."""
        now = timezone.now()
        next_run = calculate_next_run("weekly", now)

        expected = now + timedelta(days=7)
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_monthly(self):
        """Monthly schedule should set next_run to 30 days from now."""
        now = timezone.now()
        next_run = calculate_next_run("monthly", now)

        expected = now + timedelta(days=30)
        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_on_demand(self):
        """On-demand schedule should not set automatic next_run (returns None)."""
        now = timezone.now()
        next_run = calculate_next_run("on_demand", now)

        # On-demand schedules don't automatically schedule next run
        assert next_run is None


class TestErrorCountAndBackoff:
    """Tests for consecutive_errors tracking and exponential backoff behavior."""

    def test_consecutive_errors_increments(self, sample_schedule):
        """consecutive_errors should be incrementable on schedule."""
        assert sample_schedule.consecutive_errors == 0

        sample_schedule.consecutive_errors += 1
        sample_schedule.save()
        sample_schedule.refresh_from_db()

        assert sample_schedule.consecutive_errors == 1

    def test_exponential_backoff_calculation(self):
        """Next_run should have exponential backoff applied when error_count > 0."""
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
        now = timezone.now()

        # 10 errors would be 2^10 = 1024x backoff without cap
        # Should be capped at reasonable maximum (e.g., 7 days max delay)
        next_run = calculate_next_run_with_backoff("daily", now, error_count=10)

        max_delay = timedelta(days=7)
        assert (next_run - now) <= max_delay

    def test_paused_until_respected_in_calculation(self):
        """Next_run calculation should respect paused_until if set."""
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


class TestScheduleQueryOptimization:
    """Tests for schedule query optimization via indexes."""

    def test_active_schedules_query(self, db, sample_source):
        """Should efficiently query active schedules ready to run."""
        now = timezone.now()

        # Create schedules - some due, some not
        schedule_due = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now - timedelta(hours=1),  # Due
            is_active=True,
        )
        CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now + timedelta(hours=1),  # Not due
            is_active=True,
        )
        CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now - timedelta(hours=2),  # Due but inactive
            is_active=False,
        )

        # Query active schedules due to run
        due_schedules = CrawlSchedule.objects.filter(
            is_active=True,
            next_run__lte=now,
        )

        assert due_schedules.count() == 1
        assert due_schedules.first() == schedule_due

    def test_get_due_schedules_function(self, db, sample_source):
        """get_due_schedules returns ordered list of due schedules."""
        now = timezone.now()

        # Create a due schedule
        schedule = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=now - timedelta(hours=1),
            is_active=True,
        )

        due = get_due_schedules()
        assert schedule in due


class TestPriorityBoost:
    """Tests for priority_boost field."""

    def test_priority_boost_default(self, sample_schedule):
        """priority_boost should default to 0."""
        assert sample_schedule.priority_boost == 0

    def test_priority_boost_can_be_set(self, sample_source, db):
        """priority_boost should be customizable."""
        schedule = CrawlSchedule.objects.create(
            source=sample_source,
            next_run=timezone.now() + timedelta(hours=24),
            priority_boost=5,
        )

        assert schedule.priority_boost == 5


class TestCurrentBackoffHours:
    """Tests for current_backoff_hours field."""

    def test_current_backoff_hours_default(self, sample_schedule):
        """current_backoff_hours should default to 0."""
        assert sample_schedule.current_backoff_hours == 0

    def test_current_backoff_hours_increments(self, sample_schedule):
        """current_backoff_hours can be incremented."""
        sample_schedule.current_backoff_hours = 24
        sample_schedule.save()
        sample_schedule.refresh_from_db()

        assert sample_schedule.current_backoff_hours == 24
