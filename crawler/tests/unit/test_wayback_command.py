"""
Unit tests for archive_to_wayback management command.

Tests Phase 4.8: Wayback Archive Job
"""

import pytest
from io import StringIO
from unittest.mock import Mock, patch
from django.core.management import call_command


class TestArchiveToWaybackCommand:
    """Tests for archive_to_wayback management command."""

    @pytest.mark.django_db
    def test_command_exists(self):
        """Test archive_to_wayback command can be called."""
        out = StringIO()
        call_command('archive_to_wayback', '--dry-run', stdout=out)
        output = out.getvalue()
        assert 'archive' in output.lower() or 'wayback' in output.lower() or 'dry' in output.lower()

    @pytest.mark.django_db
    def test_dry_run_does_not_archive(self):
        """Test dry run mode doesn't actually archive."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        source = CrawledSource.objects.create(
            url="https://example.com/dry-run",
            title="Dry Run Test",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING
        )

        out = StringIO()
        call_command('archive_to_wayback', '--dry-run', stdout=out)

        source.refresh_from_db()
        assert source.wayback_status == WaybackStatusChoices.PENDING  # Status unchanged

    @pytest.mark.django_db
    def test_archive_calls_wayback_service(self):
        """Test archive calls WaybackService."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        source = CrawledSource.objects.create(
            url="https://example.com/archive-test",
            title="Archive Test",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/archive-test"
        }
        mock_response.text = "OK"

        out = StringIO()
        with patch('requests.post', return_value=mock_response):
            call_command('archive_to_wayback', stdout=out)

        source.refresh_from_db()
        assert source.wayback_status == WaybackStatusChoices.SAVED

    @pytest.mark.django_db
    def test_skips_non_pending_sources(self):
        """Test archive skips sources not pending."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Already saved
        CrawledSource.objects.create(
            url="https://example.com/already-saved",
            title="Already Saved",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        # Not yet processed
        CrawledSource.objects.create(
            url="https://example.com/not-processed",
            title="Not Processed",
            source_type="review_article",
            extraction_status="pending",
            wayback_status=WaybackStatusChoices.PENDING
        )

        out = StringIO()
        call_command('archive_to_wayback', '--dry-run', stdout=out)
        output = out.getvalue()

        # Should report 0 eligible
        assert 'No sources' in output or '0' in output

    @pytest.mark.django_db
    def test_respects_batch_size(self):
        """Test archive respects batch size parameter."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Create multiple pending sources
        for i in range(5):
            CrawledSource.objects.create(
                url=f"https://example.com/batch-{i}",
                title=f"Batch {i}",
                source_type="review_article",
                extraction_status="processed",
                wayback_status=WaybackStatusChoices.PENDING
            )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/batch"
        }
        mock_response.text = "OK"

        out = StringIO()
        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep'):  # Don't actually sleep for rate limiting
                call_command('archive_to_wayback', '--batch-size=2', stdout=out)

        # Only 2 should be archived in this batch
        saved = CrawledSource.objects.filter(
            wayback_status=WaybackStatusChoices.SAVED
        ).count()
        assert saved == 2

    @pytest.mark.django_db
    def test_handles_archive_failure(self):
        """Test archive handles failure gracefully."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        source = CrawledSource.objects.create(
            url="https://example.com/fail-test",
            title="Fail Test",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING
        )

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        out = StringIO()
        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep'):  # Don't actually sleep for retry
                call_command('archive_to_wayback', '--max-retries=1', stdout=out)

        source.refresh_from_db()
        # After max retries, should be marked failed
        assert source.wayback_status == WaybackStatusChoices.FAILED


class TestRateLimiting:
    """Tests for rate limiting in archive command."""

    @pytest.mark.django_db
    def test_rate_limit_delay(self):
        """Test rate limiting delay between requests."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        for i in range(2):
            CrawledSource.objects.create(
                url=f"https://example.com/rate-{i}",
                title=f"Rate {i}",
                source_type="review_article",
                extraction_status="processed",
                wayback_status=WaybackStatusChoices.PENDING
            )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/rate"
        }
        mock_response.text = "OK"

        out = StringIO()
        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep') as mock_sleep:
                call_command('archive_to_wayback', '--rate-limit=2', stdout=out)

        # Should have called sleep for rate limiting between requests
        assert mock_sleep.call_count >= 1


class TestReporting:
    """Tests for command reporting."""

    @pytest.mark.django_db
    def test_reports_success_count(self):
        """Test command reports success count."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        for i in range(3):
            CrawledSource.objects.create(
                url=f"https://example.com/report-{i}",
                title=f"Report {i}",
                source_type="review_article",
                extraction_status="processed",
                wayback_status=WaybackStatusChoices.PENDING
            )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20260109120000/https://example.com/report"
        }
        mock_response.text = "OK"

        out = StringIO()
        with patch('requests.post', return_value=mock_response):
            with patch('time.sleep'):
                call_command('archive_to_wayback', stdout=out)

        output = out.getvalue()
        assert '3' in output  # Should mention success count
