"""
Tests for Wayback Machine Integration.

Task Group 31: Wayback Machine Integration
These tests verify the Wayback Machine integration functionality.

Tests focus on:
- Archive save trigger via service
- wayback_url storage on CrawledSource
- wayback_status updates (pending -> saved/failed)
- Error handling and retry logic
- raw_content cleanup utility
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from crawler.models import CrawledSource, WaybackStatusChoices


class WaybackSaveServiceTestCase(TestCase):
    """Test archive save trigger via Wayback service."""

    def setUp(self):
        """Create test CrawledSource."""
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/whiskey-review/macallan-18",
            title="Macallan 18 Review",
            source_type="review_article",
            extraction_status="processed",
            raw_content="<html><body><h1>Macallan 18 Review</h1></body></html>",
            wayback_status=WaybackStatusChoices.PENDING,
        )

    @patch("crawler.services.wayback.requests.post")
    def test_archive_save_success(self, mock_post):
        """Test successful archive save to Wayback Machine."""
        from crawler.services.wayback import save_to_wayback

        # Mock successful Wayback Machine response with redirect
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Location": "/web/20241230120000/https://example.com/whiskey-review/macallan-18"
        }
        mock_post.return_value = mock_response

        result = save_to_wayback(self.crawled_source)

        self.assertTrue(result["success"])
        self.assertIsNotNone(result["wayback_url"])
        self.assertIn("web.archive.org", result["wayback_url"])

        # Verify CrawledSource was updated
        self.crawled_source.refresh_from_db()
        self.assertEqual(self.crawled_source.wayback_status, WaybackStatusChoices.SAVED)
        self.assertIsNotNone(self.crawled_source.wayback_url)
        self.assertIsNotNone(self.crawled_source.wayback_saved_at)

    @patch("crawler.services.wayback.requests.post")
    def test_archive_save_failure(self, mock_post):
        """Test archive save failure handling."""
        from crawler.services.wayback import save_to_wayback

        # Mock failed Wayback Machine response
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service temporarily unavailable"
        mock_post.return_value = mock_response

        result = save_to_wayback(self.crawled_source)

        self.assertFalse(result["success"])
        self.assertIn("error", result)

        # Verify CrawledSource was NOT updated to saved
        self.crawled_source.refresh_from_db()
        self.assertEqual(self.crawled_source.wayback_status, WaybackStatusChoices.PENDING)


class WaybackUrlStorageTestCase(TestCase):
    """Test wayback_url storage on CrawledSource."""

    def test_wayback_url_format_stored_correctly(self):
        """Test that Wayback URL format is stored correctly."""
        wayback_url = "https://web.archive.org/web/20241230120000/https://example.com/article"

        source = CrawledSource.objects.create(
            url="https://example.com/article",
            title="Test Article",
            source_type="review_article",
            extraction_status="processed",
            wayback_url=wayback_url,
            wayback_status=WaybackStatusChoices.SAVED,
            wayback_saved_at=timezone.now(),
        )

        source.refresh_from_db()
        self.assertEqual(source.wayback_url, wayback_url)
        self.assertTrue(source.wayback_url.startswith("https://web.archive.org/web/"))

    def test_wayback_url_can_be_null(self):
        """Test that wayback_url can be null initially."""
        source = CrawledSource.objects.create(
            url="https://example.com/pending-article",
            title="Pending Article",
            source_type="news_article",
            extraction_status="pending",
        )

        self.assertIsNone(source.wayback_url)
        self.assertEqual(source.wayback_status, WaybackStatusChoices.PENDING)


class WaybackStatusUpdateTestCase(TestCase):
    """Test wayback_status state transitions."""

    def test_status_transition_pending_to_saved(self):
        """Test transition from pending to saved status."""
        source = CrawledSource.objects.create(
            url="https://example.com/status-test",
            title="Status Test Article",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING,
        )

        self.assertEqual(source.wayback_status, WaybackStatusChoices.PENDING)

        # Simulate successful archive
        source.wayback_status = WaybackStatusChoices.SAVED
        source.wayback_url = "https://web.archive.org/web/20241230/https://example.com/status-test"
        source.wayback_saved_at = timezone.now()
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.wayback_status, WaybackStatusChoices.SAVED)
        self.assertIsNotNone(source.wayback_url)
        self.assertIsNotNone(source.wayback_saved_at)

    def test_status_transition_pending_to_failed(self):
        """Test transition from pending to failed status."""
        source = CrawledSource.objects.create(
            url="https://example.com/failed-test",
            title="Failed Test Article",
            source_type="review_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING,
        )

        # Simulate failed archive attempt
        source.wayback_status = WaybackStatusChoices.FAILED
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.wayback_status, WaybackStatusChoices.FAILED)
        self.assertIsNone(source.wayback_url)


class WaybackErrorHandlingTestCase(TestCase):
    """Test error handling in Wayback integration."""

    def setUp(self):
        """Create test CrawledSource."""
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/error-test",
            title="Error Test Article",
            source_type="news_article",
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.PENDING,
        )

    @patch("crawler.services.wayback.requests.post")
    def test_network_error_handling(self, mock_post):
        """Test handling of network errors during archive save."""
        from crawler.services.wayback import save_to_wayback
        import requests

        # Mock network error
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        result = save_to_wayback(self.crawled_source)

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("crawler.services.wayback.requests.post")
    def test_timeout_error_handling(self, mock_post):
        """Test handling of timeout errors during archive save."""
        from crawler.services.wayback import save_to_wayback
        import requests

        # Mock timeout error
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        result = save_to_wayback(self.crawled_source)

        self.assertFalse(result["success"])
        self.assertIn("error", result)


class RawContentCleanupTestCase(TestCase):
    """Test raw_content cleanup utility."""

    def test_cleanup_after_wayback_saved(self):
        """Test that raw_content can be cleared after wayback save."""
        from crawler.services.wayback import cleanup_raw_content

        source = CrawledSource.objects.create(
            url="https://example.com/cleanup-test",
            title="Cleanup Test Article",
            source_type="review_article",
            extraction_status="processed",
            raw_content="<html><body><h1>Large HTML content here</h1></body></html>",
            content_hash="abc123def456",
            wayback_status=WaybackStatusChoices.SAVED,
            wayback_url="https://web.archive.org/web/20241230/https://example.com/cleanup-test",
            wayback_saved_at=timezone.now(),
        )

        self.assertIsNotNone(source.raw_content)
        self.assertFalse(source.raw_content_cleared)

        # Run cleanup
        cleanup_raw_content(source)

        source.refresh_from_db()
        self.assertIsNone(source.raw_content)
        self.assertTrue(source.raw_content_cleared)
        # Verify content_hash is preserved for deduplication
        self.assertEqual(source.content_hash, "abc123def456")

    def test_cleanup_requires_saved_status(self):
        """Test that cleanup only works when wayback_status is saved."""
        from crawler.services.wayback import cleanup_raw_content

        source = CrawledSource.objects.create(
            url="https://example.com/no-cleanup-test",
            title="No Cleanup Test",
            source_type="review_article",
            extraction_status="processed",
            raw_content="<html><body>Content</body></html>",
            content_hash="xyz789",
            wayback_status=WaybackStatusChoices.PENDING,
        )

        # Attempt cleanup on pending status
        cleanup_raw_content(source)

        source.refresh_from_db()
        # Content should NOT be cleared
        self.assertIsNotNone(source.raw_content)
        self.assertFalse(source.raw_content_cleared)
