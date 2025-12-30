"""
Task Group 29: Health Check Endpoint Tests

Tests for the health check endpoint which provides system status information
for monitoring and load balancer health checks.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from crawler.models import CrawlerMetrics


class TestHealthyStatusResponse(TestCase):
    """Test healthy status response from health endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_healthy_status_returns_200(self):
        """
        Test that health endpoint returns 200 when system is healthy.

        Expected response:
        - HTTP 200 status code
        - status field set to "healthy"
        - Content-Type is application/json
        """
        # Create metrics for last 24h to simulate healthy system
        CrawlerMetrics.objects.create(
            date=date.today(),
            pages_crawled=100,
            pages_succeeded=95,
            pages_failed=5,
            crawl_success_rate=Decimal("95.00"),
            products_extracted=50,
            products_created=40,
            extraction_success_rate=Decimal("80.00"),
        )

        response = self.client.get("/api/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_response_contains_required_fields(self):
        """
        Test that health response contains all required fields.

        Expected fields:
        - status: overall health status
        - database: database connection status
        - redis: redis connection status (or "not_configured")
        - celery_workers: number of active celery workers (or 0)
        - queue_depth: current queue depth
        """
        response = self.client.get("/api/health/")

        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "celery_workers" in data
        assert "queue_depth" in data

    def test_health_response_json_content_type(self):
        """
        Test that health endpoint returns JSON content type.
        """
        response = self.client.get("/api/health/")

        assert response["Content-Type"] == "application/json"


class TestDatabaseConnectionCheck(TestCase):
    """Test database connection health check."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_database_connected_status(self):
        """
        Test that database status shows "connected" when DB is accessible.

        The fact that the test is running means DB is connected,
        so this should always return "connected".
        """
        response = self.client.get("/api/health/")

        data = response.json()
        assert data["database"] == "connected"

    @patch("django.db.connection.ensure_connection")
    def test_database_error_status(self, mock_ensure_connection):
        """
        Test that database status shows "error" when DB is not accessible.
        """
        mock_ensure_connection.side_effect = Exception("Connection refused")

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["database"] == "error"
        assert data["status"] == "unhealthy"

    @patch("django.db.connection.ensure_connection")
    def test_unhealthy_returns_503_on_db_error(self, mock_ensure_connection):
        """
        Test that health endpoint returns 503 when database is unavailable.
        """
        mock_ensure_connection.side_effect = Exception("Connection refused")

        response = self.client.get("/api/health/")

        assert response.status_code == 503


class TestRedisConnectionCheck(TestCase):
    """Test Redis connection health check with mocking."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @patch("crawler.views.get_redis_connection")
    def test_redis_connected_status(self, mock_get_redis):
        """
        Test that redis status shows "connected" when Redis is accessible.
        """
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["redis"] == "connected"

    @patch("crawler.views.get_redis_connection")
    def test_redis_error_status(self, mock_get_redis):
        """
        Test that redis status shows "not_configured" when Redis is not available.

        Note: Redis being unavailable does NOT make the system unhealthy
        since Redis/Celery may be optional for basic operation.
        """
        mock_get_redis.side_effect = Exception("Redis connection refused")

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["redis"] in ["not_configured", "error"]
        # System should still be healthy if only Redis is down
        assert data["status"] == "healthy"

    @patch("crawler.views.get_redis_connection")
    def test_redis_not_configured(self, mock_get_redis):
        """
        Test graceful handling when Redis is not configured.
        """
        mock_get_redis.return_value = None

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["redis"] == "not_configured"


class TestCeleryWorkerCount(TestCase):
    """Test Celery worker count in health check with mocking."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @patch("crawler.views.get_celery_worker_count")
    def test_celery_workers_count(self, mock_get_workers):
        """
        Test that celery_workers shows correct worker count.
        """
        mock_get_workers.return_value = 3

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["celery_workers"] == 3

    @patch("crawler.views.get_celery_worker_count")
    def test_celery_not_available(self, mock_get_workers):
        """
        Test graceful handling when Celery is not available.
        """
        mock_get_workers.return_value = 0

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["celery_workers"] == 0
        # System should still be healthy if Celery workers are at 0
        assert data["status"] == "healthy"

    @patch("crawler.views.get_celery_worker_count")
    def test_celery_connection_error(self, mock_get_workers):
        """
        Test graceful handling when Celery connection fails.
        """
        mock_get_workers.side_effect = Exception("Celery not available")

        response = self.client.get("/api/health/")

        data = response.json()
        assert data["celery_workers"] == 0
        # System should still be considered healthy
        assert data["status"] == "healthy"


class TestSuccessRateCalculation(TestCase):
    """Test 24h success rate calculation in health check."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_24h_crawl_success_rate_calculation(self):
        """
        Test that crawl_success_rate_24h is calculated from CrawlerMetrics.

        Success rate is calculated from the most recent metrics record.
        """
        today = date.today()
        CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=200,
            pages_succeeded=188,
            pages_failed=12,
            crawl_success_rate=Decimal("94.00"),
        )

        response = self.client.get("/api/health/")

        data = response.json()
        assert "crawl_success_rate_24h" in data
        assert data["crawl_success_rate_24h"] == 94.00

    def test_24h_extraction_success_rate_calculation(self):
        """
        Test that extraction_success_rate_24h is calculated from CrawlerMetrics.
        """
        today = date.today()
        CrawlerMetrics.objects.create(
            date=today,
            products_extracted=100,
            products_created=70,
            products_merged=15,
            products_flagged_review=15,
            extraction_success_rate=Decimal("85.00"),
        )

        response = self.client.get("/api/health/")

        data = response.json()
        assert "extraction_success_rate_24h" in data
        assert data["extraction_success_rate_24h"] == 85.00

    def test_no_metrics_returns_null_rates(self):
        """
        Test that null rates are returned when no metrics exist.
        """
        # Ensure no metrics exist
        CrawlerMetrics.objects.all().delete()

        response = self.client.get("/api/health/")

        data = response.json()
        assert data.get("crawl_success_rate_24h") is None
        assert data.get("extraction_success_rate_24h") is None

    def test_last_crawl_timestamp_included(self):
        """
        Test that last_crawl timestamp is included in response.
        """
        today = date.today()
        CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=100,
        )

        response = self.client.get("/api/health/")

        data = response.json()
        assert "last_crawl" in data


class TestHealthCheckNoAuth(TestCase):
    """Test that health check endpoint requires no authentication."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_no_auth_required(self):
        """
        Test that health endpoint is accessible without authentication.

        This is required for load balancer health checks.
        """
        # No authentication headers or cookies set
        response = self.client.get("/api/health/")

        # Should not return 401 or 403
        assert response.status_code in [200, 503]

    def test_health_url_path(self):
        """
        Test that health endpoint is accessible at /api/health/.
        """
        response = self.client.get("/api/health/")

        # Endpoint should exist and return valid status
        assert response.status_code in [200, 503]
