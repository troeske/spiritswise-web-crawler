"""
Unit tests for Wayback Machine integration service.

Tests Phase 4.6: Internet Archive (Wayback Machine) Integration
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

import requests


# Test WaybackService class
class TestWaybackServiceInit:
    """Tests for WaybackService initialization."""

    def test_wayback_service_instantiation(self):
        """Test WaybackService can be instantiated."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()
        assert service is not None

    def test_wayback_service_singleton(self):
        """Test WaybackService is a singleton."""
        from crawler.services.wayback_service import WaybackService

        service1 = WaybackService()
        service2 = WaybackService()
        assert service1 is service2


# Test archive_url method
class TestArchiveUrl:
    """Tests for archive_url method."""

    @pytest.mark.django_db
    def test_archive_url_success(self):
        """Test successful URL archiving."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/test-page",
            title="Test Page",
            source_type="review_article"
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/test-page"
        }
        mock_response.text = "OK"

        with patch('requests.post', return_value=mock_response) as mock_post:
            result = service.archive_url(source)

        assert result['success'] is True
        assert 'web.archive.org' in result['wayback_url']

    @pytest.mark.django_db
    def test_archive_url_updates_source_status(self):
        """Test successful archive updates CrawledSource status."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource, WaybackStatusChoices

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/update-status",
            title="Update Status Test",
            source_type="review_article"
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/update-status"
        }
        mock_response.text = "OK"

        with patch('requests.post', return_value=mock_response):
            service.archive_url(source)

        source.refresh_from_db()
        assert source.wayback_status == WaybackStatusChoices.SAVED
        assert source.wayback_url is not None
        assert source.wayback_saved_at is not None

    @pytest.mark.django_db
    def test_archive_url_failure_status(self):
        """Test failed archive returns error."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/fail-test",
            title="Fail Test",
            source_type="review_article"
        )

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch('requests.post', return_value=mock_response):
            result = service.archive_url(source)

        assert result['success'] is False
        assert 'error' in result

    @pytest.mark.django_db
    def test_archive_url_timeout(self):
        """Test archive handles timeout gracefully."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/timeout-test",
            title="Timeout Test",
            source_type="review_article"
        )

        with patch('requests.post', side_effect=requests.exceptions.Timeout("Timeout")):
            result = service.archive_url(source)

        assert result['success'] is False
        assert 'timeout' in result['error'].lower()

    @pytest.mark.django_db
    def test_archive_url_connection_error(self):
        """Test archive handles connection error gracefully."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/connection-test",
            title="Connection Test",
            source_type="review_article"
        )

        with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Failed")):
            result = service.archive_url(source)

        assert result['success'] is False
        assert 'connection' in result['error'].lower()


# Test extract_archive_url method
class TestExtractArchiveUrl:
    """Tests for extracting archive URL from response."""

    def test_extract_from_content_location(self):
        """Test extracting URL from Content-Location header."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()

        mock_response = Mock()
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/page"
        }

        url = service._extract_archive_url(mock_response, "https://example.com/page")

        assert url == "https://web.archive.org/web/20260109120000/https://example.com/page"

    def test_extract_from_location_header(self):
        """Test extracting URL from Location redirect header."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()

        mock_response = Mock()
        mock_response.headers = {
            "Location": "https://web.archive.org/web/20260109120000/https://example.com/page"
        }

        url = service._extract_archive_url(mock_response, "https://example.com/page")

        assert url == "https://web.archive.org/web/20260109120000/https://example.com/page"

    def test_extract_constructs_fallback_url(self):
        """Test fallback URL construction when headers missing."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()

        mock_response = Mock()
        mock_response.headers = {}

        url = service._extract_archive_url(mock_response, "https://example.com/page")

        assert url is not None
        assert "web.archive.org" in url
        assert "example.com/page" in url


# Test mark_failed method
class TestMarkFailed:
    """Tests for marking archive as failed."""

    @pytest.mark.django_db
    def test_mark_failed_updates_status(self):
        """Test marking a source as failed updates wayback_status."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource, WaybackStatusChoices

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/mark-fail",
            title="Mark Fail Test",
            source_type="review_article"
        )

        service.mark_failed(source)

        source.refresh_from_db()
        assert source.wayback_status == WaybackStatusChoices.FAILED


# Test cleanup eligibility
class TestCleanupEligibility:
    """Tests for cleanup eligibility check."""

    def test_is_cleanup_eligible_requires_saved_status(self):
        """Test cleanup eligible only when wayback_status is saved."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()

        assert service.is_cleanup_eligible("processed", "saved") is True
        assert service.is_cleanup_eligible("processed", "pending") is False
        assert service.is_cleanup_eligible("processed", "failed") is False

    def test_is_cleanup_eligible_requires_processed_extraction(self):
        """Test cleanup eligible only when extraction is processed."""
        from crawler.services.wayback_service import WaybackService

        service = WaybackService()

        assert service.is_cleanup_eligible("processed", "saved") is True
        assert service.is_cleanup_eligible("pending", "saved") is False
        assert service.is_cleanup_eligible("failed", "saved") is False


# Test perform_cleanup method
class TestPerformCleanup:
    """Tests for performing raw content cleanup."""

    @pytest.mark.django_db
    def test_perform_cleanup_clears_content(self):
        """Test cleanup clears raw_content."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource, WaybackStatusChoices

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/cleanup",
            title="Cleanup Test",
            source_type="review_article",
            raw_content="<html>content</html>",
            wayback_status=WaybackStatusChoices.SAVED,
            extraction_status="processed"
        )

        result = service.perform_cleanup(source)

        assert result is True
        source.refresh_from_db()
        assert source.raw_content is None
        assert source.raw_content_cleared is True

    @pytest.mark.django_db
    def test_perform_cleanup_skips_if_not_saved(self):
        """Test cleanup skips if wayback not saved."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/no-cleanup",
            title="No Cleanup Test",
            source_type="review_article",
            raw_content="<html>content</html>",
            wayback_status="pending"
        )

        result = service.perform_cleanup(source)

        assert result is False
        source.refresh_from_db()
        assert source.raw_content is not None


# Test get_pending_archive_sources
class TestGetPendingArchiveSources:
    """Tests for getting sources pending archival."""

    @pytest.mark.django_db
    def test_get_pending_returns_processed_pending_sources(self):
        """Test getting sources ready for archival."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        # Create eligible source (processed, pending wayback)
        CrawledSource.objects.create(
            url="https://example.com/pending1",
            title="Pending 1",
            source_type="review_article",
            extraction_status="processed",
            wayback_status="pending"
        )

        # Create already archived source
        CrawledSource.objects.create(
            url="https://example.com/saved1",
            title="Saved 1",
            source_type="review_article",
            extraction_status="processed",
            wayback_status="saved"
        )

        # Create not yet extracted source
        CrawledSource.objects.create(
            url="https://example.com/not-extracted",
            title="Not Extracted",
            source_type="review_article",
            extraction_status="pending",
            wayback_status="pending"
        )

        pending = service.get_pending_archive_sources()

        assert len(pending) == 1
        assert pending[0].url == "https://example.com/pending1"

    @pytest.mark.django_db
    def test_get_pending_respects_limit(self):
        """Test pending sources limit is respected."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        # Create multiple eligible sources
        for i in range(5):
            CrawledSource.objects.create(
                url=f"https://example.com/pending-{i}",
                title=f"Pending {i}",
                source_type="review_article",
                extraction_status="processed",
                wayback_status="pending"
            )

        pending = service.get_pending_archive_sources(limit=3)

        assert len(pending) == 3


# Test retry logic
class TestRetryLogic:
    """Tests for retry with exponential backoff."""

    @pytest.mark.django_db
    def test_archive_with_retry_succeeds_on_retry(self):
        """Test archive retries on failure and succeeds."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/retry-success",
            title="Retry Success",
            source_type="review_article"
        )

        # First call fails, second succeeds
        mock_fail = Mock()
        mock_fail.status_code = 503
        mock_fail.text = "Service Unavailable"

        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/retry-success"
        }
        mock_success.text = "OK"

        with patch('requests.post', side_effect=[mock_fail, mock_success]):
            with patch('time.sleep'):  # Don't actually sleep
                result = service.archive_with_retry(source, max_retries=2)

        assert result['success'] is True

    @pytest.mark.django_db
    def test_archive_with_retry_marks_failed_after_max(self):
        """Test archive marks failed after max retries."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource, WaybackStatusChoices

        service = WaybackService()

        source = CrawledSource.objects.create(
            url="https://example.com/retry-fail",
            title="Retry Fail",
            source_type="review_article"
        )

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep'):  # Don't actually sleep
                result = service.archive_with_retry(source, max_retries=3)

        assert result['success'] is False

        source.refresh_from_db()
        assert source.wayback_status == WaybackStatusChoices.FAILED


# Test batch archival
class TestBatchArchival:
    """Tests for batch archival operations."""

    @pytest.mark.django_db
    def test_archive_batch(self):
        """Test archiving a batch of sources."""
        from crawler.services.wayback_service import WaybackService
        from crawler.models import CrawledSource

        service = WaybackService()

        # Create batch of sources
        sources = []
        for i in range(3):
            source = CrawledSource.objects.create(
                url=f"https://example.com/batch-{i}",
                title=f"Batch {i}",
                source_type="review_article",
                extraction_status="processed",
                wayback_status="pending"
            )
            sources.append(source)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/batch"
        }
        mock_response.text = "OK"

        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep'):  # Rate limiting sleep
                results = service.archive_batch(sources, rate_limit_seconds=0)

        assert len(results) == 3
        assert all(r['success'] for r in results)
