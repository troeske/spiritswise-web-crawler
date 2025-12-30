"""
Task Group 27: SourceMetrics Model Tests

Tests for the SourceMetrics model which tracks per-source daily metrics
for crawler operations, enabling source health monitoring and error tracking.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from crawler.models import SourceMetrics, DiscoverySourceConfig


class TestSourceMetricsCreation(TestCase):
    """Test SourceMetrics model creation and basic functionality."""

    def setUp(self):
        """Create a DiscoverySourceConfig for testing FK relationship."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="IWSC",
            base_url="https://iwsc.net",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
        )

    def test_per_source_daily_metrics_creation(self):
        """
        Test that SourceMetrics can be created with required fields.

        Required fields: date, discovery_source
        Integer fields default to 0, decimal fields are nullable.
        """
        today = date.today()
        metrics = SourceMetrics.objects.create(
            date=today,
            discovery_source=self.discovery_source,
            pages_crawled=50,
            pages_succeeded=48,
            products_found=120,
            avg_products_per_page=Decimal("2.50"),
            avg_confidence=Decimal("0.87"),
        )

        metrics.refresh_from_db()
        assert metrics.id is not None
        assert metrics.date == today
        assert metrics.discovery_source == self.discovery_source
        assert metrics.pages_crawled == 50
        assert metrics.pages_succeeded == 48
        assert metrics.products_found == 120
        assert metrics.avg_products_per_page == Decimal("2.50")
        assert metrics.avg_confidence == Decimal("0.87")

    def test_uuid_primary_key(self):
        """
        Test that SourceMetrics uses UUID as primary key.
        """
        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
        )

        metrics.refresh_from_db()
        # UUID should be a 36-character string when converted
        assert len(str(metrics.id)) == 36
        assert "-" in str(metrics.id)  # UUIDs contain dashes

    def test_default_integer_values(self):
        """
        Test that integer fields default to 0.
        """
        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
        )

        metrics.refresh_from_db()
        assert metrics.pages_crawled == 0
        assert metrics.pages_succeeded == 0
        assert metrics.products_found == 0

    def test_nullable_decimal_fields(self):
        """
        Test that decimal fields can be null.
        """
        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
            avg_products_per_page=None,
            avg_confidence=None,
        )

        metrics.refresh_from_db()
        assert metrics.avg_products_per_page is None
        assert metrics.avg_confidence is None


class TestUniqueConstraint(TestCase):
    """Test unique constraint on (date, discovery_source)."""

    def setUp(self):
        """Create a DiscoverySourceConfig for testing FK relationship."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="Whisky Advocate",
            base_url="https://whiskyadvocate.com",
            source_type="review_blog",
            crawl_priority=7,
            crawl_frequency="daily",
            reliability_score=8,
        )

    def test_unique_constraint_on_date_and_discovery_source(self):
        """
        Test that unique constraint on (date, discovery_source) is enforced.

        Only one SourceMetrics record should exist per date per source.
        """
        test_date = date.today()

        # Create first record for the date and source
        SourceMetrics.objects.create(
            date=test_date,
            discovery_source=self.discovery_source,
            pages_crawled=100,
        )

        # Attempt to create second record for same date and source should fail
        with pytest.raises(IntegrityError):
            SourceMetrics.objects.create(
                date=test_date,
                discovery_source=self.discovery_source,
                pages_crawled=200,
            )

    def test_same_date_different_sources_allowed(self):
        """
        Test that same date can have metrics for different sources.
        """
        today = date.today()

        source2 = DiscoverySourceConfig.objects.create(
            name="Master of Malt",
            base_url="https://masterofmalt.com",
            source_type="retailer",
            crawl_priority=6,
            crawl_frequency="daily",
            reliability_score=7,
        )

        metrics1 = SourceMetrics.objects.create(
            date=today,
            discovery_source=self.discovery_source,
            pages_crawled=50,
        )
        metrics2 = SourceMetrics.objects.create(
            date=today,
            discovery_source=source2,
            pages_crawled=80,
        )

        assert SourceMetrics.objects.count() == 2
        assert metrics1.discovery_source.name == "Whisky Advocate"
        assert metrics2.discovery_source.name == "Master of Malt"

    def test_same_source_different_dates_allowed(self):
        """
        Test that same source can have metrics for different dates.
        """
        today = date.today()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)

        metrics_today = SourceMetrics.objects.create(
            date=today,
            discovery_source=self.discovery_source,
            pages_crawled=100,
        )
        metrics_yesterday = SourceMetrics.objects.create(
            date=yesterday,
            discovery_source=self.discovery_source,
            pages_crawled=90,
        )
        metrics_day_before = SourceMetrics.objects.create(
            date=day_before,
            discovery_source=self.discovery_source,
            pages_crawled=80,
        )

        assert SourceMetrics.objects.count() == 3
        assert metrics_today.date == today
        assert metrics_yesterday.date == yesterday
        assert metrics_day_before.date == day_before


class TestErrorTrackingJSONField(TestCase):
    """Test errors JSONField for tracking error types and counts."""

    def setUp(self):
        """Create a DiscoverySourceConfig for testing FK relationship."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="The Whisky Exchange",
            base_url="https://thewhiskyexchange.com",
            source_type="retailer",
            crawl_priority=7,
            crawl_frequency="daily",
            reliability_score=8,
        )

    def test_errors_jsonfield_storage(self):
        """
        Test that errors JSONField stores error types and counts correctly.
        """
        errors_data = [
            {"type": "connection_timeout", "count": 5},
            {"type": "rate_limit", "count": 2},
            {"type": "parse_error", "count": 1},
        ]

        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
            pages_crawled=100,
            pages_succeeded=92,
            errors=errors_data,
        )

        metrics.refresh_from_db()
        assert len(metrics.errors) == 3
        assert metrics.errors[0]["type"] == "connection_timeout"
        assert metrics.errors[0]["count"] == 5
        assert metrics.errors[1]["type"] == "rate_limit"
        assert metrics.errors[2]["type"] == "parse_error"

    def test_errors_default_empty_list(self):
        """
        Test that errors JSONField defaults to empty list.
        """
        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
        )

        metrics.refresh_from_db()
        assert metrics.errors == []

    def test_errors_with_detailed_info(self):
        """
        Test that errors JSONField can store detailed error information.
        """
        errors_data = [
            {
                "type": "age_gate_failed",
                "count": 3,
                "urls": [
                    "https://example.com/page1",
                    "https://example.com/page2",
                    "https://example.com/page3",
                ],
                "last_occurrence": "2024-12-30T10:30:00Z",
            },
        ]

        metrics = SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=self.discovery_source,
            errors=errors_data,
        )

        metrics.refresh_from_db()
        assert len(metrics.errors[0]["urls"]) == 3
        assert "last_occurrence" in metrics.errors[0]


class TestRelatedNameMetrics(TestCase):
    """Test that DiscoverySourceConfig can access metrics via related_name."""

    def test_discovery_source_metrics_related_name(self):
        """
        Test that DiscoverySourceConfig.metrics returns related SourceMetrics.
        """
        discovery_source = DiscoverySourceConfig.objects.create(
            name="Distillery Trail",
            base_url="https://distillerytrail.com",
            source_type="news_outlet",
            crawl_priority=5,
            crawl_frequency="weekly",
            reliability_score=6,
        )

        today = date.today()
        yesterday = today - timedelta(days=1)

        SourceMetrics.objects.create(
            date=today,
            discovery_source=discovery_source,
            pages_crawled=30,
        )
        SourceMetrics.objects.create(
            date=yesterday,
            discovery_source=discovery_source,
            pages_crawled=25,
        )

        # Access via related_name 'metrics'
        source_metrics = discovery_source.metrics.all()
        assert source_metrics.count() == 2

    def test_cascade_delete_on_source_deletion(self):
        """
        Test that SourceMetrics are deleted when DiscoverySourceConfig is deleted.
        """
        discovery_source = DiscoverySourceConfig.objects.create(
            name="Temp Source",
            base_url="https://temp.com",
            source_type="aggregator",
            crawl_priority=4,
            crawl_frequency="monthly",
            reliability_score=5,
        )

        SourceMetrics.objects.create(
            date=date.today(),
            discovery_source=discovery_source,
            pages_crawled=10,
        )

        assert SourceMetrics.objects.count() == 1

        # Delete the source
        discovery_source.delete()

        # Metrics should be deleted too
        assert SourceMetrics.objects.count() == 0
