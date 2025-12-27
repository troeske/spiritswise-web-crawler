"""
Tests for database models.

Task Group 2: Database Models & Migrations
These tests verify model functionality for the Web Crawler System.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum


@pytest.mark.django_db
class TestCrawlerSource:
    """Tests for CrawlerSource model functionality."""

    def test_is_due_for_crawl_returns_true_when_next_crawl_at_is_none(self):
        """Source with no next_crawl_at is due for crawling."""
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Test Source",
            slug="test-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=None,
        )

        assert source.is_due_for_crawl() is True

    def test_is_due_for_crawl_returns_true_when_past_due(self):
        """Source past its next_crawl_at is due for crawling."""
        from crawler.models import CrawlerSource

        past_time = timezone.now() - timedelta(hours=1)
        source = CrawlerSource.objects.create(
            name="Past Due Source",
            slug="past-due-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=past_time,
        )

        assert source.is_due_for_crawl() is True

    def test_is_due_for_crawl_returns_false_when_not_due(self):
        """Source not yet at next_crawl_at is not due for crawling."""
        from crawler.models import CrawlerSource

        future_time = timezone.now() + timedelta(hours=1)
        source = CrawlerSource.objects.create(
            name="Future Source",
            slug="future-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=future_time,
        )

        assert source.is_due_for_crawl() is False

    def test_is_due_for_crawl_returns_false_when_inactive(self):
        """Inactive source is not due for crawling regardless of time."""
        from crawler.models import CrawlerSource

        past_time = timezone.now() - timedelta(hours=1)
        source = CrawlerSource.objects.create(
            name="Inactive Source",
            slug="inactive-source",
            base_url="https://example.com",
            category="retailer",
            is_active=False,
            next_crawl_at=past_time,
        )

        assert source.is_due_for_crawl() is False


@pytest.mark.django_db
class TestDiscoveredProduct:
    """Tests for DiscoveredProduct model functionality."""

    def test_fingerprint_computation_produces_consistent_hash(self):
        """Fingerprint computation produces consistent results for same data."""
        from crawler.models import DiscoveredProduct

        extracted_data = {
            "name": "Glenfiddich 18 Year Old",
            "brand": "Glenfiddich",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
            "distillery": "Glenfiddich",
            "age_statement": 18,
        }

        fingerprint1 = DiscoveredProduct.compute_fingerprint(extracted_data)
        fingerprint2 = DiscoveredProduct.compute_fingerprint(extracted_data)

        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 64  # SHA-256 hex length

    def test_fingerprint_differs_for_different_products(self):
        """Different products produce different fingerprints."""
        from crawler.models import DiscoveredProduct

        product1_data = {
            "name": "Glenfiddich 18 Year Old",
            "brand": "Glenfiddich",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
        }

        product2_data = {
            "name": "Macallan 12 Year Old",
            "brand": "Macallan",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 43.0,
        }

        fingerprint1 = DiscoveredProduct.compute_fingerprint(product1_data)
        fingerprint2 = DiscoveredProduct.compute_fingerprint(product2_data)

        assert fingerprint1 != fingerprint2


@pytest.mark.django_db
class TestCrawlJob:
    """Tests for CrawlJob model functionality."""

    def test_status_transition_from_pending_to_running(self):
        """CrawlJob can transition from pending to running."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlJobStatus

        source = CrawlerSource.objects.create(
            name="Job Test Source",
            slug="job-test-source",
            base_url="https://example.com",
            category="retailer",
        )

        job = CrawlJob.objects.create(source=source)
        assert job.status == CrawlJobStatus.PENDING
        assert job.started_at is None

        job.start()

        assert job.status == CrawlJobStatus.RUNNING
        assert job.started_at is not None

    def test_status_transition_from_running_to_completed(self):
        """CrawlJob can transition from running to completed."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlJobStatus

        source = CrawlerSource.objects.create(
            name="Complete Test Source",
            slug="complete-test-source",
            base_url="https://example.com",
            category="retailer",
        )

        job = CrawlJob.objects.create(source=source)
        job.start()
        job.complete(success=True)

        assert job.status == CrawlJobStatus.COMPLETED
        assert job.completed_at is not None

    def test_status_transition_from_running_to_failed(self):
        """CrawlJob can transition from running to failed with error message."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlJobStatus

        source = CrawlerSource.objects.create(
            name="Fail Test Source",
            slug="fail-test-source",
            base_url="https://example.com",
            category="retailer",
        )

        job = CrawlJob.objects.create(source=source)
        job.start()
        job.complete(success=False, error_message="Connection timeout")

        assert job.status == CrawlJobStatus.FAILED
        assert job.error_message == "Connection timeout"
        assert job.completed_at is not None


@pytest.mark.django_db
class TestCrawlCost:
    """Tests for CrawlCost model aggregation functionality."""

    def test_aggregate_costs_by_service(self):
        """CrawlCost can be aggregated by service."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlCost

        source = CrawlerSource.objects.create(
            name="Cost Test Source",
            slug="cost-test-source",
            base_url="https://example.com",
            category="retailer",
        )

        job = CrawlJob.objects.create(source=source)

        # Create cost records for different services
        CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=150,
            request_count=10,
        )
        CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=100,
            request_count=7,
        )
        CrawlCost.objects.create(
            crawl_job=job,
            service="scrapingbee",
            cost_cents=50,
            request_count=100,
        )
        CrawlCost.objects.create(
            crawl_job=job,
            service="openai",
            cost_cents=200,
            request_count=5,
        )

        # Aggregate by service
        serpapi_total = CrawlCost.objects.filter(service="serpapi").aggregate(
            total=Sum("cost_cents")
        )["total"]
        scrapingbee_total = CrawlCost.objects.filter(service="scrapingbee").aggregate(
            total=Sum("cost_cents")
        )["total"]
        openai_total = CrawlCost.objects.filter(service="openai").aggregate(
            total=Sum("cost_cents")
        )["total"]

        assert serpapi_total == 250
        assert scrapingbee_total == 50
        assert openai_total == 200

    def test_aggregate_costs_by_timestamp_range(self):
        """CrawlCost can be filtered and aggregated by timestamp range."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlCost

        source = CrawlerSource.objects.create(
            name="Time Range Source",
            slug="time-range-source",
            base_url="https://example.com",
            category="retailer",
        )

        job = CrawlJob.objects.create(source=source)

        now = timezone.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        # Create cost records at different times
        cost1 = CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=100,
            request_count=5,
        )
        cost1.timestamp = now
        cost1.save()

        cost2 = CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=200,
            request_count=10,
        )
        cost2.timestamp = yesterday
        cost2.save()

        cost3 = CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=300,
            request_count=15,
        )
        cost3.timestamp = last_week
        cost3.save()

        # Filter by last 2 days
        two_days_ago = now - timedelta(days=2)
        recent_total = CrawlCost.objects.filter(
            timestamp__gte=two_days_ago
        ).aggregate(total=Sum("cost_cents"))["total"]

        assert recent_total == 300  # cost1 (100) + cost2 (200)
