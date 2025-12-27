"""
Tests for Task Group 6: Celery Tasks & URL Frontier.

Tests cover:
1. Due source detection (next_crawl_at <= now)
2. CrawlJob creation and status transitions
3. URL frontier priority queue ordering
"""

import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    mock = MagicMock()
    mock.sismember.return_value = False
    mock.sadd.return_value = True
    mock.zadd.return_value = True
    mock.zcard.return_value = 0
    mock.zpopmin.return_value = []
    mock.zrange.return_value = []
    mock.scard.return_value = 0
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.mark.django_db
class TestDueSourceDetection:
    """Tests for due source detection functionality."""

    def test_source_is_due_when_next_crawl_at_is_past(self, db):
        """Test that a source with next_crawl_at in the past is due."""
        from crawler.models import CrawlerSource

        # Create a source with next_crawl_at in the past
        source = CrawlerSource.objects.create(
            name="Due Source",
            slug="due-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=timezone.now() - timedelta(hours=1),
        )

        assert source.is_due_for_crawl() is True

    def test_source_not_due_when_next_crawl_at_is_future(self, db):
        """Test that a source with next_crawl_at in the future is not due."""
        from crawler.models import CrawlerSource

        # Create a source with next_crawl_at in the future
        source = CrawlerSource.objects.create(
            name="Future Source",
            slug="future-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=timezone.now() + timedelta(hours=1),
        )

        assert source.is_due_for_crawl() is False

    def test_inactive_source_is_never_due(self, db):
        """Test that an inactive source is never due even if next_crawl_at is past."""
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="Inactive Source",
            slug="inactive-source",
            base_url="https://example.com",
            category="retailer",
            is_active=False,
            next_crawl_at=timezone.now() - timedelta(hours=1),
        )

        assert source.is_due_for_crawl() is False

    def test_source_with_no_next_crawl_at_is_due(self, db):
        """Test that a source with null next_crawl_at is due."""
        from crawler.models import CrawlerSource

        source = CrawlerSource.objects.create(
            name="New Source",
            slug="new-source",
            base_url="https://example.com",
            category="retailer",
            is_active=True,
            next_crawl_at=None,
        )

        assert source.is_due_for_crawl() is True


@pytest.mark.django_db
class TestCrawlJobStatusTransitions:
    """Tests for CrawlJob creation and status transitions."""

    def test_crawl_job_created_with_pending_status(self, db, crawler_source):
        """Test that new CrawlJob starts with PENDING status."""
        from crawler.models import CrawlJob, CrawlJobStatus

        job = CrawlJob.objects.create(source=crawler_source)

        assert job.status == CrawlJobStatus.PENDING
        assert job.started_at is None
        assert job.completed_at is None

    def test_crawl_job_start_transitions_to_running(self, db, crawler_source):
        """Test that start() transitions job to RUNNING status."""
        from crawler.models import CrawlJob, CrawlJobStatus

        job = CrawlJob.objects.create(source=crawler_source)
        job.start()

        assert job.status == CrawlJobStatus.RUNNING
        assert job.started_at is not None
        assert job.completed_at is None

    def test_crawl_job_complete_transitions_to_completed(self, db, crawler_source):
        """Test that complete() transitions job to COMPLETED status."""
        from crawler.models import CrawlJob, CrawlJobStatus

        job = CrawlJob.objects.create(source=crawler_source)
        job.start()
        job.complete(success=True)

        job.refresh_from_db()
        assert job.status == CrawlJobStatus.COMPLETED
        assert job.completed_at is not None

    def test_crawl_job_complete_with_failure(self, db, crawler_source):
        """Test that complete(success=False) transitions job to FAILED status."""
        from crawler.models import CrawlJob, CrawlJobStatus

        job = CrawlJob.objects.create(source=crawler_source)
        job.start()
        job.complete(success=False, error_message="Test error")

        job.refresh_from_db()
        assert job.status == CrawlJobStatus.FAILED
        assert job.error_message == "Test error"

    def test_crawl_job_duration_calculated_correctly(self, db, crawler_source):
        """Test that job duration is calculated correctly."""
        from crawler.models import CrawlJob

        job = CrawlJob.objects.create(source=crawler_source)
        job.start()

        # Set specific times for predictable duration
        job.started_at = timezone.now() - timedelta(minutes=5)
        job.completed_at = timezone.now()
        job.save()

        # Duration should be approximately 5 minutes (300 seconds)
        duration = job.duration_seconds
        assert 295 <= duration <= 305


class TestURLFrontierPriorityOrdering:
    """Tests for URL frontier priority queue ordering."""

    def test_priority_inversion_score_calculation(self, mock_redis):
        """Test that higher priority URLs get lower scores."""
        from crawler.queue.url_frontier import URLFrontier

        frontier = URLFrontier(redis_client=mock_redis)

        # Add URLs with different priorities
        frontier.add_url("test-queue", "https://high-priority.com", priority=10)
        frontier.add_url("test-queue", "https://low-priority.com", priority=1)

        # Verify zadd was called with inverted scores
        calls = mock_redis.zadd.call_args_list
        assert len(calls) == 2

        # Extract scores from calls
        # Score for priority 10 should be 0 (10 - 10)
        # Score for priority 1 should be 9 (10 - 1)

    def test_higher_priority_url_retrieved_first(self, mock_redis):
        """Test that URLs are retrieved in priority order (highest first)."""
        import json
        from crawler.queue.url_frontier import URLFrontier

        frontier = URLFrontier(redis_client=mock_redis)

        # Configure mock to return high priority URL first
        high_priority_entry = json.dumps({
            "url": "https://high-priority.com",
            "url_hash": "abc123",
            "source_id": None,
            "added_at": "2024-01-01T00:00:00",
            "metadata": {},
        })

        mock_redis.zpopmin.return_value = [(high_priority_entry, 0)]

        result = frontier.get_next_url("test-queue")

        assert result is not None
        assert result["url"] == "https://high-priority.com"

    def test_url_deduplication_prevents_duplicates(self, mock_redis):
        """Test that duplicate URLs are not added to queue."""
        from crawler.queue.url_frontier import URLFrontier

        frontier = URLFrontier(redis_client=mock_redis)

        # First URL should be added
        mock_redis.sismember.return_value = False
        result1 = frontier.add_url("test-queue", "https://example.com")

        # Second URL with same hash should be rejected
        mock_redis.sismember.return_value = True
        result2 = frontier.add_url("test-queue", "https://example.com")

        assert result1 is True
        assert result2 is False

    def test_domain_cookie_caching(self, mock_redis):
        """Test domain-specific cookie caching."""
        import json
        from crawler.queue.url_frontier import URLFrontier

        frontier = URLFrontier(redis_client=mock_redis)

        cookies = {"age_verified": "true", "session_id": "abc123"}
        frontier.set_domain_cookies("example.com", cookies, ttl_seconds=3600)

        # Verify setex was called with correct key and serialized cookies
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert "crawler:cookies:example.com" in str(call_args)

        # Test retrieval
        mock_redis.get.return_value = json.dumps(cookies)
        retrieved = frontier.get_domain_cookies("example.com")

        assert retrieved == cookies
