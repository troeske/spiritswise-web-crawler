"""
Tests for Django Admin functionality.

Task Group 8: Admin Dashboard & Source Management
These tests verify admin interfaces and actions for the Web Crawler System.
"""

import pytest
from datetime import timedelta
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone
from unittest.mock import patch, MagicMock


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    User = get_user_model()
    return User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password="testpass123",
    )


@pytest.fixture
def request_factory():
    """Create a request factory for admin tests."""
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory, admin_user):
    """Create an admin request with user and messages support attached."""
    request = request_factory.get("/admin/")
    request.user = admin_user

    # Add session support
    middleware = SessionMiddleware(lambda x: None)
    middleware.process_request(request)
    request.session.save()

    # Add messages support
    setattr(request, "_messages", FallbackStorage(request))

    return request


@pytest.mark.django_db
class TestCrawlerSourceAdmin:
    """Tests for CrawlerSource admin interface."""

    def test_trigger_crawl_action_creates_crawl_job(self, admin_request, db):
        """trigger_crawl admin action creates CrawlJob and dispatches task."""
        from crawler.models import CrawlerSource, CrawlJob
        from crawler.admin import CrawlerSourceAdmin

        # Create test sources
        active_source = CrawlerSource.objects.create(
            name="Active Source",
            slug="active-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
        )
        inactive_source = CrawlerSource.objects.create(
            name="Inactive Source",
            slug="inactive-source",
            base_url="https://example2.com",
            category="retailer",
            is_active=False,
        )

        # Setup admin
        admin_site = AdminSite()
        admin = CrawlerSourceAdmin(CrawlerSource, admin_site)

        # Mock the Celery task to avoid actually dispatching
        with patch("crawler.admin.trigger_manual_crawl") as mock_task:
            mock_task.apply_async = MagicMock()

            # Call trigger_crawl action with both sources
            queryset = CrawlerSource.objects.filter(
                id__in=[active_source.id, inactive_source.id]
            )
            admin.trigger_crawl(admin_request, queryset)

        # Verify only active source created a job
        jobs = CrawlJob.objects.all()
        assert jobs.count() == 1
        assert jobs.first().source == active_source

        # Verify task was called
        mock_task.apply_async.assert_called_once()


@pytest.mark.django_db
class TestCrawlCostAdmin:
    """Tests for cost aggregation in admin."""

    def test_cost_aggregation_display(self, db):
        """Cost aggregation correctly sums costs by service and period."""
        from crawler.models import CrawlerSource, CrawlJob, CrawlCost
        from django.db.models import Sum
        from django.db.models.functions import TruncDate

        # Create test data
        source = CrawlerSource.objects.create(
            name="Cost Test Source",
            slug="cost-test-source",
            base_url="https://example.com",
            category="retailer",
        )
        job = CrawlJob.objects.create(source=source)

        now = timezone.now()
        yesterday = now - timedelta(days=1)

        # Create costs for today
        CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=100,
            request_count=5,
            timestamp=now,
        )
        CrawlCost.objects.create(
            crawl_job=job,
            service="scrapingbee",
            cost_cents=50,
            request_count=100,
            timestamp=now,
        )
        CrawlCost.objects.create(
            crawl_job=job,
            service="openai",
            cost_cents=200,
            request_count=10,
            timestamp=now,
        )

        # Create costs for yesterday
        cost_yesterday = CrawlCost.objects.create(
            crawl_job=job,
            service="serpapi",
            cost_cents=150,
            request_count=8,
        )
        cost_yesterday.timestamp = yesterday
        cost_yesterday.save()

        # Test aggregation by service
        service_totals = (
            CrawlCost.objects.values("service")
            .annotate(total_cents=Sum("cost_cents"))
            .order_by("service")
        )

        service_dict = {s["service"]: s["total_cents"] for s in service_totals}

        assert service_dict["serpapi"] == 250  # 100 + 150
        assert service_dict["scrapingbee"] == 50
        assert service_dict["openai"] == 200

        # Test aggregation by day
        daily_totals = (
            CrawlCost.objects.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(total_cents=Sum("cost_cents"))
            .order_by("-date")
        )

        daily_list = list(daily_totals)
        # Today's total should be 350 (100 + 50 + 200)
        assert daily_list[0]["total_cents"] == 350


@pytest.mark.django_db
class TestCrawlErrorAdmin:
    """Tests for CrawlError admin filtering."""

    def test_error_log_filtering_by_source_and_type(self, db):
        """Error logs can be filtered by source and error type."""
        from crawler.models import CrawlerSource, CrawlError

        # Create test sources
        source1 = CrawlerSource.objects.create(
            name="Source 1",
            slug="source-1",
            base_url="https://example1.com",
            category="retailer",
        )
        source2 = CrawlerSource.objects.create(
            name="Source 2",
            slug="source-2",
            base_url="https://example2.com",
            category="producer",
        )

        # Create errors with different types and sources
        CrawlError.objects.create(
            source=source1,
            url="https://example1.com/page1",
            error_type="timeout",
            message="Request timed out",
        )
        CrawlError.objects.create(
            source=source1,
            url="https://example1.com/page2",
            error_type="blocked",
            message="403 Forbidden",
        )
        CrawlError.objects.create(
            source=source2,
            url="https://example2.com/page1",
            error_type="timeout",
            message="Connection timeout",
        )
        CrawlError.objects.create(
            source=source2,
            url="https://example2.com/page2",
            error_type="parse",
            message="Invalid HTML",
            resolved=True,
        )

        # Test filtering by source
        source1_errors = CrawlError.objects.filter(source=source1)
        assert source1_errors.count() == 2

        source2_errors = CrawlError.objects.filter(source=source2)
        assert source2_errors.count() == 2

        # Test filtering by error type
        timeout_errors = CrawlError.objects.filter(error_type="timeout")
        assert timeout_errors.count() == 2

        blocked_errors = CrawlError.objects.filter(error_type="blocked")
        assert blocked_errors.count() == 1

        # Test filtering by resolved status
        unresolved_errors = CrawlError.objects.filter(resolved=False)
        assert unresolved_errors.count() == 3

        resolved_errors = CrawlError.objects.filter(resolved=True)
        assert resolved_errors.count() == 1

        # Test combined filtering
        source1_timeout_errors = CrawlError.objects.filter(
            source=source1, error_type="timeout"
        )
        assert source1_timeout_errors.count() == 1
