"""
Task Group 26: CrawlerMetrics Model Tests

Tests for the CrawlerMetrics model which tracks daily aggregate metrics
for crawler operations, extraction success rates, and API usage.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from crawler.models import CrawlerMetrics


class TestCrawlerMetricsCreation(TestCase):
    """Test CrawlerMetrics model creation and basic functionality."""

    def test_daily_metrics_creation(self):
        """
        Test that CrawlerMetrics can be created with required fields.

        Required fields: date (unique)
        All integer fields default to 0, decimal fields are nullable.
        """
        today = date.today()
        metrics = CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=150,
            pages_succeeded=145,
            pages_failed=5,
            products_extracted=80,
            products_created=50,
            products_merged=20,
            products_flagged_review=10,
            serpapi_queries=25,
            scrapingbee_requests=100,
            ai_enhancement_calls=75,
            wayback_saves=30,
        )

        metrics.refresh_from_db()
        assert metrics.id is not None
        assert metrics.date == today
        assert metrics.pages_crawled == 150
        assert metrics.pages_succeeded == 145
        assert metrics.pages_failed == 5
        assert metrics.products_extracted == 80
        assert metrics.products_created == 50
        assert metrics.products_merged == 20
        assert metrics.products_flagged_review == 10
        assert metrics.serpapi_queries == 25
        assert metrics.scrapingbee_requests == 100
        assert metrics.ai_enhancement_calls == 75
        assert metrics.wayback_saves == 30

    def test_uuid_primary_key(self):
        """
        Test that CrawlerMetrics uses UUID as primary key.
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
        )

        metrics.refresh_from_db()
        # UUID should be a 36-character string when converted
        assert len(str(metrics.id)) == 36
        assert "-" in str(metrics.id)  # UUIDs contain dashes


class TestUniqueDateConstraint(TestCase):
    """Test unique date constraint on CrawlerMetrics."""

    def test_unique_date_constraint(self):
        """
        Test that date field has unique constraint.

        Only one CrawlerMetrics record should exist per date.
        """
        test_date = date.today()

        # Create first record for the date
        CrawlerMetrics.objects.create(
            date=test_date,
            pages_crawled=100,
        )

        # Attempt to create second record for same date should fail
        with pytest.raises(IntegrityError):
            CrawlerMetrics.objects.create(
                date=test_date,
                pages_crawled=200,
            )

    def test_different_dates_allowed(self):
        """
        Test that different dates can have their own records.
        """
        today = date.today()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)

        metrics_today = CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=100,
        )
        metrics_yesterday = CrawlerMetrics.objects.create(
            date=yesterday,
            pages_crawled=90,
        )
        metrics_day_before = CrawlerMetrics.objects.create(
            date=day_before,
            pages_crawled=80,
        )

        assert CrawlerMetrics.objects.count() == 3
        assert metrics_today.date == today
        assert metrics_yesterday.date == yesterday
        assert metrics_day_before.date == day_before


class TestSuccessRateCalculation(TestCase):
    """Test success rate calculation fields."""

    def test_crawl_success_rate_calculation(self):
        """
        Test crawl_success_rate DecimalField storage and calculation.

        Success rate = (pages_succeeded / pages_crawled) * 100
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            pages_crawled=200,
            pages_succeeded=180,
            pages_failed=20,
            crawl_success_rate=Decimal("90.00"),  # 180/200 * 100
        )

        metrics.refresh_from_db()
        assert metrics.crawl_success_rate == Decimal("90.00")

    def test_extraction_success_rate_calculation(self):
        """
        Test extraction_success_rate DecimalField storage.
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            products_extracted=100,
            products_created=70,
            products_merged=20,
            products_flagged_review=10,
            extraction_success_rate=Decimal("90.00"),  # (70+20)/100 * 100
        )

        metrics.refresh_from_db()
        assert metrics.extraction_success_rate == Decimal("90.00")

    def test_success_rates_nullable(self):
        """
        Test that success rate fields can be null.
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            crawl_success_rate=None,
            extraction_success_rate=None,
        )

        metrics.refresh_from_db()
        assert metrics.crawl_success_rate is None
        assert metrics.extraction_success_rate is None


class TestAPIUsageTracking(TestCase):
    """Test API usage tracking fields."""

    def test_api_usage_fields(self):
        """
        Test all API usage tracking fields.

        - serpapi_queries: IntegerField default 0
        - scrapingbee_requests: IntegerField default 0
        - ai_enhancement_calls: IntegerField default 0
        - wayback_saves: IntegerField default 0
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            serpapi_queries=50,
            scrapingbee_requests=200,
            ai_enhancement_calls=150,
            wayback_saves=75,
        )

        metrics.refresh_from_db()
        assert metrics.serpapi_queries == 50
        assert metrics.scrapingbee_requests == 200
        assert metrics.ai_enhancement_calls == 150
        assert metrics.wayback_saves == 75

    def test_api_usage_defaults_to_zero(self):
        """
        Test that API usage fields default to 0.
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
        )

        metrics.refresh_from_db()
        assert metrics.serpapi_queries == 0
        assert metrics.scrapingbee_requests == 0
        assert metrics.ai_enhancement_calls == 0
        assert metrics.wayback_saves == 0


class TestQualityAndPerformanceMetrics(TestCase):
    """Test quality and performance metric fields."""

    def test_quality_metrics_storage(self):
        """
        Test quality metrics fields storage.

        - avg_completeness_score: DecimalField nullable
        - avg_confidence_score: DecimalField nullable
        - conflicts_detected: IntegerField default 0
        - duplicates_merged: IntegerField default 0
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            avg_completeness_score=Decimal("78.50"),
            avg_confidence_score=Decimal("0.85"),
            conflicts_detected=15,
            duplicates_merged=8,
        )

        metrics.refresh_from_db()
        assert metrics.avg_completeness_score == Decimal("78.50")
        assert metrics.avg_confidence_score == Decimal("0.85")
        assert metrics.conflicts_detected == 15
        assert metrics.duplicates_merged == 8

    def test_performance_metrics_storage(self):
        """
        Test performance metrics fields storage.

        - avg_crawl_time_ms: IntegerField nullable
        - avg_extraction_time_ms: IntegerField nullable
        - queue_depth: IntegerField default 0
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            avg_crawl_time_ms=1500,
            avg_extraction_time_ms=3200,
            queue_depth=250,
        )

        metrics.refresh_from_db()
        assert metrics.avg_crawl_time_ms == 1500
        assert metrics.avg_extraction_time_ms == 3200
        assert metrics.queue_depth == 250

    def test_performance_metrics_nullable_and_defaults(self):
        """
        Test that performance metric nullable fields and defaults work correctly.
        """
        metrics = CrawlerMetrics.objects.create(
            date=date.today(),
            avg_crawl_time_ms=None,
            avg_extraction_time_ms=None,
            # queue_depth not specified, should default to 0
        )

        metrics.refresh_from_db()
        assert metrics.avg_crawl_time_ms is None
        assert metrics.avg_extraction_time_ms is None
        assert metrics.queue_depth == 0
        assert metrics.conflicts_detected == 0
        assert metrics.duplicates_merged == 0
