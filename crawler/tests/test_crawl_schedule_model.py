"""
TDD Tests for CrawlSchedule unified scheduling model.

Tests written BEFORE implementation per TDD approach.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError


class TestCrawlScheduleModel(TestCase):
    """Tests for CrawlSchedule model creation and fields."""

    def test_create_competition_schedule(self):
        """Test creating a competition category schedule."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        schedule = CrawlSchedule.objects.create(
            name="IWSC Awards Crawler",
            slug="iwsc-awards",
            category=ScheduleCategory.COMPETITION,
            frequency=ScheduleFrequency.MONTHLY,
            priority=8,
            search_terms=["iwsc:2024", "iwsc:2025"],
            max_results_per_term=100,
            product_types=["whiskey", "gin"],
            base_url="https://iwsc.net/results/search/",
        )

        assert schedule.id is not None
        assert schedule.name == "IWSC Awards Crawler"
        assert schedule.category == ScheduleCategory.COMPETITION
        assert schedule.frequency == ScheduleFrequency.MONTHLY
        assert schedule.is_active is True
        assert schedule.search_terms == ["iwsc:2024", "iwsc:2025"]

    def test_create_discovery_schedule(self):
        """Test creating a discovery category schedule."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        schedule = CrawlSchedule.objects.create(
            name="Daily Whisky Discovery",
            slug="daily-whisky",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["best whisky 2024", "rare bourbon"],
            max_results_per_term=10,
            product_types=["whiskey"],
        )

        assert schedule.category == ScheduleCategory.DISCOVERY
        assert schedule.frequency == ScheduleFrequency.DAILY
        assert len(schedule.search_terms) == 2

    def test_slug_must_be_unique(self):
        """Test that slug field enforces uniqueness."""
        from crawler.models import CrawlSchedule, ScheduleCategory

        CrawlSchedule.objects.create(
            name="Schedule 1",
            slug="unique-slug",
            category=ScheduleCategory.DISCOVERY,
        )

        with pytest.raises(IntegrityError):
            CrawlSchedule.objects.create(
                name="Schedule 2",
                slug="unique-slug",  # Duplicate slug
                category=ScheduleCategory.DISCOVERY,
            )

    def test_default_values(self):
        """Test that default values are set correctly."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        schedule = CrawlSchedule.objects.create(
            name="Minimal Schedule",
            slug="minimal",
            category=ScheduleCategory.DISCOVERY,
        )

        assert schedule.is_active is True
        assert schedule.frequency == ScheduleFrequency.DAILY
        assert schedule.priority == 5
        assert schedule.max_results_per_term == 10
        assert schedule.search_terms == []
        assert schedule.product_types == []
        assert schedule.exclude_domains == []
        assert schedule.daily_quota == 100
        assert schedule.monthly_quota == 2000
        assert schedule.total_runs == 0

    def test_uuid_primary_key(self):
        """Test that id is a UUID."""
        from crawler.models import CrawlSchedule, ScheduleCategory

        schedule = CrawlSchedule.objects.create(
            name="UUID Test",
            slug="uuid-test",
            category=ScheduleCategory.DISCOVERY,
        )

        assert isinstance(schedule.id, uuid.UUID)


class TestCrawlScheduleFrequencyCalculation(TestCase):
    """Tests for next_run calculation based on frequency."""

    def test_calculate_next_run_hourly(self):
        """Test hourly frequency calculation."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            name="Hourly",
            slug="hourly",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.HOURLY,
        )
        schedule.last_run = now
        schedule.save()

        next_run = schedule.calculate_next_run()
        expected = now + timedelta(hours=1)

        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_daily(self):
        """Test daily frequency calculation."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            name="Daily",
            slug="daily",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
        )
        schedule.last_run = now
        schedule.save()

        next_run = schedule.calculate_next_run()
        expected = now + timedelta(days=1)

        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_weekly(self):
        """Test weekly frequency calculation."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            name="Weekly",
            slug="weekly",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.WEEKLY,
        )
        schedule.last_run = now
        schedule.save()

        next_run = schedule.calculate_next_run()
        expected = now + timedelta(weeks=1)

        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_monthly(self):
        """Test monthly frequency calculation."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        now = timezone.now()
        schedule = CrawlSchedule.objects.create(
            name="Monthly",
            slug="monthly",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.MONTHLY,
        )
        schedule.last_run = now
        schedule.save()

        next_run = schedule.calculate_next_run()
        expected = now + timedelta(days=30)

        assert abs((next_run - expected).total_seconds()) < 1

    def test_calculate_next_run_no_last_run_uses_now(self):
        """Test that calculate_next_run uses now() if no last_run."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        schedule = CrawlSchedule.objects.create(
            name="Never Run",
            slug="never-run",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
        )

        # No last_run set
        assert schedule.last_run is None

        # Calculate next run - should use current time as base
        before = timezone.now()
        next_run = schedule.calculate_next_run()
        after = timezone.now()

        # next_run should be approximately 1 day from now
        expected_min = before + timedelta(days=1)
        expected_max = after + timedelta(days=1)

        assert next_run >= expected_min
        assert next_run <= expected_max


class TestCrawlScheduleUpdateMethods(TestCase):
    """Tests for schedule update methods."""

    def test_update_next_run(self):
        """Test update_next_run method sets last_run and next_run."""
        from crawler.models import CrawlSchedule, ScheduleCategory, ScheduleFrequency

        schedule = CrawlSchedule.objects.create(
            name="Update Test",
            slug="update-test",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
        )

        assert schedule.last_run is None
        assert schedule.next_run is None
        assert schedule.total_runs == 0

        schedule.update_next_run()

        schedule.refresh_from_db()
        assert schedule.last_run is not None
        assert schedule.next_run is not None
        assert schedule.total_runs == 1
        assert schedule.next_run > schedule.last_run

    def test_record_run_stats(self):
        """Test recording run statistics."""
        from crawler.models import CrawlSchedule, ScheduleCategory

        schedule = CrawlSchedule.objects.create(
            name="Stats Test",
            slug="stats-test",
            category=ScheduleCategory.DISCOVERY,
        )

        assert schedule.total_products_found == 0

        schedule.record_run_stats(
            products_found=10,
            products_new=7,
            products_duplicate=3,
            errors=1,
        )

        schedule.refresh_from_db()
        assert schedule.total_products_found == 10
        assert schedule.total_products_new == 7
        assert schedule.total_products_duplicate == 3
        assert schedule.total_errors == 1

        # Record more stats (cumulative)
        schedule.record_run_stats(
            products_found=5,
            products_new=4,
            products_duplicate=1,
            errors=0,
        )

        schedule.refresh_from_db()
        assert schedule.total_products_found == 15
        assert schedule.total_products_new == 11
        assert schedule.total_products_duplicate == 4
        assert schedule.total_errors == 1


class TestCrawlScheduleQuerysets(TestCase):
    """Tests for querying due schedules."""

    def test_find_due_schedules(self):
        """Test finding schedules that are due for execution."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from django.db.models import Q

        now = timezone.now()

        # Create schedules with different next_run states
        due_schedule = CrawlSchedule.objects.create(
            name="Due",
            slug="due",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now - timedelta(hours=1),  # Past due
        )

        never_run = CrawlSchedule.objects.create(
            name="Never Run",
            slug="never-run-query",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=None,  # Never run = should be due
        )

        future_schedule = CrawlSchedule.objects.create(
            name="Future",
            slug="future",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now + timedelta(hours=1),  # Not yet due
        )

        inactive_schedule = CrawlSchedule.objects.create(
            name="Inactive",
            slug="inactive",
            category=ScheduleCategory.DISCOVERY,
            is_active=False,
            next_run=now - timedelta(hours=1),  # Due but inactive
        )

        # Query for due schedules
        due_schedules = CrawlSchedule.objects.filter(
            is_active=True,
        ).filter(
            Q(next_run__isnull=True) | Q(next_run__lte=now)
        )

        due_ids = list(due_schedules.values_list("id", flat=True))

        assert due_schedule.id in due_ids
        assert never_run.id in due_ids
        assert future_schedule.id not in due_ids
        assert inactive_schedule.id not in due_ids

    def test_filter_by_category(self):
        """Test filtering schedules by category."""
        from crawler.models import CrawlSchedule, ScheduleCategory

        comp = CrawlSchedule.objects.create(
            name="Competition",
            slug="comp-filter",
            category=ScheduleCategory.COMPETITION,
        )

        disc = CrawlSchedule.objects.create(
            name="Discovery",
            slug="disc-filter",
            category=ScheduleCategory.DISCOVERY,
        )

        competitions = CrawlSchedule.objects.filter(
            category=ScheduleCategory.COMPETITION
        )
        discoveries = CrawlSchedule.objects.filter(
            category=ScheduleCategory.DISCOVERY
        )

        assert comp in competitions
        assert comp not in discoveries
        assert disc in discoveries
        assert disc not in competitions


class TestCrawlScheduleStrRepresentation(TestCase):
    """Tests for string representation."""

    def test_str_representation(self):
        """Test __str__ method."""
        from crawler.models import CrawlSchedule, ScheduleCategory

        schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-str",
            category=ScheduleCategory.DISCOVERY,
        )

        str_repr = str(schedule)
        assert "Test Schedule" in str_repr
        assert "Discovery" in str_repr


class TestScheduleFrequencyChoices(TestCase):
    """Tests for ScheduleFrequency enum."""

    def test_all_frequency_choices_exist(self):
        """Test that all expected frequency choices are defined."""
        from crawler.models import ScheduleFrequency

        expected = [
            "HOURLY",
            "EVERY_6_HOURS",
            "EVERY_12_HOURS",
            "DAILY",
            "WEEKLY",
            "BIWEEKLY",
            "MONTHLY",
            "QUARTERLY",
        ]

        for freq in expected:
            assert hasattr(ScheduleFrequency, freq), f"Missing {freq}"


class TestScheduleCategoryChoices(TestCase):
    """Tests for ScheduleCategory enum."""

    def test_all_category_choices_exist(self):
        """Test that all expected category choices are defined."""
        from crawler.models import ScheduleCategory

        expected = ["COMPETITION", "DISCOVERY", "RETAILER"]

        for cat in expected:
            assert hasattr(ScheduleCategory, cat), f"Missing {cat}"
