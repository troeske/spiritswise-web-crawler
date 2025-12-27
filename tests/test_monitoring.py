"""
Tests for the monitoring and alerting system.

Task Group 9.1: Focused tests for monitoring functionality:
- Test Sentry error capture
- Test consecutive failure threshold detection
- Test CrawlError record creation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from django.utils import timezone


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = Mock()
    redis_mock.incr = Mock(return_value=1)
    redis_mock.get = Mock(return_value=b"0")
    redis_mock.set = Mock(return_value=True)
    redis_mock.delete = Mock(return_value=True)
    redis_mock.expire = Mock(return_value=True)
    return redis_mock


@pytest.fixture
def crawler_source_for_monitoring(db):
    """Create a CrawlerSource for monitoring tests."""
    from crawler.models import CrawlerSource

    return CrawlerSource.objects.create(
        name="Test Monitoring Source",
        slug="test-monitoring-source",
        base_url="https://test-monitoring.com",
        category="retailer",
        is_active=True,
    )


class TestSentryErrorCapture:
    """Test Sentry error capture with context."""

    def test_capture_crawl_error_with_breadcrumbs(self, crawler_source_for_monitoring):
        """Test that crawl errors are captured with proper Sentry breadcrumbs."""
        import crawler.monitoring.sentry_integration as sentry_module

        # Create mock sentry_sdk
        mock_sentry = Mock()
        mock_sentry.add_breadcrumb = Mock()
        mock_sentry.push_scope = Mock(return_value=MagicMock())
        mock_sentry.capture_exception = Mock()

        # Patch the module globals
        original_available = sentry_module.SENTRY_AVAILABLE
        original_sdk = sentry_module.sentry_sdk

        try:
            sentry_module.SENTRY_AVAILABLE = True
            sentry_module.sentry_sdk = mock_sentry

            from crawler.monitoring.sentry_integration import capture_crawl_error

            error = ValueError("Test fetch error")

            capture_crawl_error(
                error=error,
                source=crawler_source_for_monitoring,
                url="https://test-monitoring.com/product/123",
                tier=2,
            )

            # Verify breadcrumb was added
            mock_sentry.add_breadcrumb.assert_called()
            breadcrumb_call = mock_sentry.add_breadcrumb.call_args

            assert breadcrumb_call is not None
            breadcrumb_kwargs = breadcrumb_call[1]
            assert breadcrumb_kwargs["category"] == "crawl"
            assert "source" in breadcrumb_kwargs["data"]
            assert "url" in breadcrumb_kwargs["data"]
            assert "tier" in breadcrumb_kwargs["data"]

        finally:
            sentry_module.SENTRY_AVAILABLE = original_available
            sentry_module.sentry_sdk = original_sdk

    def test_capture_error_filters_sensitive_data(self, crawler_source_for_monitoring):
        """Test that sensitive data is filtered from Sentry events."""
        import crawler.monitoring.sentry_integration as sentry_module

        # Create mock sentry_sdk
        mock_sentry = Mock()
        mock_sentry.add_breadcrumb = Mock()
        mock_sentry.push_scope = Mock(return_value=MagicMock())
        mock_sentry.capture_exception = Mock()

        # Patch the module globals
        original_available = sentry_module.SENTRY_AVAILABLE
        original_sdk = sentry_module.sentry_sdk

        try:
            sentry_module.SENTRY_AVAILABLE = True
            sentry_module.sentry_sdk = mock_sentry

            from crawler.monitoring.sentry_integration import capture_crawl_error

            error = ValueError("API key error")

            # Capture with sensitive data in context
            capture_crawl_error(
                error=error,
                source=crawler_source_for_monitoring,
                url="https://test-monitoring.com/product/123",
                tier=1,
                extra_context={
                    "cookies": {"age_verified": "true", "api_key": "secret123"},
                    "headers": {"Authorization": "Bearer secret"},
                },
            )

            # Verify sensitive fields are filtered in breadcrumb
            breadcrumb_call = mock_sentry.add_breadcrumb.call_args
            if breadcrumb_call and "data" in breadcrumb_call[1]:
                data = breadcrumb_call[1]["data"]
                # Cookies and sensitive headers should not be in plain text
                assert "secret123" not in str(data)
                assert "Bearer secret" not in str(data)

        finally:
            sentry_module.SENTRY_AVAILABLE = original_available
            sentry_module.sentry_sdk = original_sdk


class TestConsecutiveFailureTracking:
    """Test consecutive failure detection and alerting."""

    def test_increment_failure_counter(self, mock_redis, crawler_source_for_monitoring):
        """Test that failure counter increments correctly."""
        from crawler.monitoring.failure_tracker import FailureTracker

        tracker = FailureTracker(redis_client=mock_redis)

        # Record a failure
        count = tracker.record_failure(str(crawler_source_for_monitoring.id))

        # Verify Redis incr was called
        mock_redis.incr.assert_called_once()
        assert count == 1

    def test_threshold_breach_triggers_alert(
        self, mock_redis, crawler_source_for_monitoring
    ):
        """Test that exceeding threshold triggers an alert."""
        from crawler.monitoring.failure_tracker import FailureTracker

        # Mock Redis to return count at threshold
        mock_redis.incr = Mock(return_value=5)

        tracker = FailureTracker(redis_client=mock_redis, threshold=5)

        with patch(
            "crawler.monitoring.failure_tracker.trigger_threshold_alert"
        ) as mock_alert:
            count = tracker.record_failure(str(crawler_source_for_monitoring.id))

            # Verify alert was triggered
            mock_alert.assert_called_once()
            alert_kwargs = mock_alert.call_args[1]
            assert alert_kwargs["source_id"] == str(crawler_source_for_monitoring.id)
            assert alert_kwargs["failure_count"] == 5

    def test_reset_counter_on_success(self, mock_redis, crawler_source_for_monitoring):
        """Test that counter resets on successful crawl."""
        from crawler.monitoring.failure_tracker import FailureTracker

        tracker = FailureTracker(redis_client=mock_redis)

        # Record a success (should reset counter)
        tracker.record_success(str(crawler_source_for_monitoring.id))

        # Verify Redis delete was called to reset counter
        mock_redis.delete.assert_called_once()


class TestCrawlErrorRecordCreation:
    """Test CrawlError record creation for failures."""

    @pytest.mark.django_db
    def test_create_error_record_with_full_context(
        self, crawler_source_for_monitoring
    ):
        """Test creating a CrawlError record with all context fields."""
        from crawler.monitoring.error_logger import create_crawl_error_record
        from crawler.models import CrawlError

        error_record = create_crawl_error_record(
            source=crawler_source_for_monitoring,
            url="https://test-monitoring.com/product/456",
            error_type="blocked",
            message="Request blocked by WAF",
            tier_used=2,
            response_status=403,
            response_headers={"X-Block-Reason": "Bot detected"},
            stack_trace="Traceback: ...",
        )

        # Verify record was created
        assert error_record is not None
        assert error_record.id is not None

        # Verify all fields
        assert error_record.source == crawler_source_for_monitoring
        assert error_record.url == "https://test-monitoring.com/product/456"
        assert error_record.error_type == "blocked"
        assert error_record.message == "Request blocked by WAF"
        assert error_record.tier_used == 2
        assert error_record.response_status == 403
        assert error_record.response_headers == {"X-Block-Reason": "Bot detected"}
        assert error_record.stack_trace == "Traceback: ..."
        assert not error_record.resolved

        # Verify it exists in database
        db_record = CrawlError.objects.get(id=error_record.id)
        assert db_record is not None

    @pytest.mark.django_db
    def test_create_error_record_without_optional_fields(
        self, crawler_source_for_monitoring
    ):
        """Test creating a CrawlError with minimal required fields."""
        from crawler.monitoring.error_logger import create_crawl_error_record
        from crawler.models import CrawlError

        error_record = create_crawl_error_record(
            source=crawler_source_for_monitoring,
            url="https://test-monitoring.com/error",
            error_type="timeout",
            message="Connection timed out",
        )

        assert error_record is not None
        assert error_record.tier_used is None
        assert error_record.response_status is None
        assert error_record.response_headers == {}
