"""
Tests for CrawledSource model.

Task Group 6: CrawledSource Article Storage Model
These tests verify the article storage model functionality for crawled pages.

Tests focus on:
- Article creation with URL uniqueness
- content_hash generation for deduplication
- extraction_status state transitions
- Wayback Machine URL storage
- Crawl attempt tracking fields
"""

import uuid
import hashlib
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from crawler.models import CrawledSource, DiscoverySourceConfig


class CrawledSourceCreationTestCase(TestCase):
    """Test CrawledSource creation with URL uniqueness."""

    def test_create_crawled_source_with_required_fields(self):
        """Test creating a crawled source with all required fields succeeds."""
        source = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2024/whiskey-winners",
            title="IWSC 2024 Whiskey Winners",
            source_type="award_page",
            extraction_status="pending",
        )

        self.assertIsNotNone(source.id)
        self.assertIsInstance(source.id, uuid.UUID)
        self.assertEqual(source.url, "https://iwsc.net/awards/2024/whiskey-winners")
        self.assertEqual(source.title, "IWSC 2024 Whiskey Winners")
        self.assertEqual(source.source_type, "award_page")
        self.assertEqual(source.extraction_status, "pending")
        self.assertIsNotNone(source.crawled_at)

    def test_url_uniqueness_constraint(self):
        """Test that URL must be unique across CrawledSource records."""
        CrawledSource.objects.create(
            url="https://example.com/article/1",
            title="First Article",
            source_type="review_article",
            extraction_status="pending",
        )

        with self.assertRaises(IntegrityError):
            CrawledSource.objects.create(
                url="https://example.com/article/1",  # Duplicate URL
                title="Duplicate Article",
                source_type="news_article",
                extraction_status="pending",
            )

    def test_create_with_discovery_source_fk(self):
        """Test creating CrawledSource with FK to DiscoverySourceConfig."""
        discovery_source = DiscoverySourceConfig.objects.create(
            name="IWSC",
            base_url="https://iwsc.net",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
        )

        crawled_source = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2024",
            title="IWSC Awards 2024",
            source_type="award_page",
            extraction_status="pending",
            discovery_source=discovery_source,
        )

        self.assertEqual(crawled_source.discovery_source, discovery_source)
        self.assertEqual(crawled_source.discovery_source.name, "IWSC")

    def test_discovery_source_can_be_null(self):
        """Test that discovery_source FK can be null (for SerpAPI discoveries)."""
        crawled_source = CrawledSource.objects.create(
            url="https://random-blog.com/whiskey-review",
            title="Random Whiskey Review",
            source_type="review_article",
            extraction_status="pending",
            discovery_source=None,
        )

        self.assertIsNone(crawled_source.discovery_source)


class CrawledSourceContentHashTestCase(TestCase):
    """Test content_hash generation for deduplication."""

    def test_content_hash_stored_correctly(self):
        """Test that content_hash is stored and can be used for dedup."""
        raw_content = "<html><body><h1>Whiskey Review</h1></body></html>"
        expected_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Whiskey Review",
            source_type="review_article",
            extraction_status="pending",
            raw_content=raw_content,
            content_hash=expected_hash,
        )

        self.assertEqual(source.content_hash, expected_hash)
        self.assertEqual(len(source.content_hash), 64)  # SHA-256 produces 64 hex chars

    def test_content_hash_utility_function(self):
        """Test the generate_content_hash utility function."""
        raw_content = "<html><body><h1>Test Content</h1></body></html>"
        expected_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        actual_hash = CrawledSource.generate_content_hash(raw_content)

        self.assertEqual(actual_hash, expected_hash)
        self.assertEqual(len(actual_hash), 64)

    def test_duplicate_detection_via_content_hash(self):
        """Test that content_hash enables duplicate content detection."""
        raw_content = "<html><body><h1>Same Content</h1></body></html>"
        content_hash = CrawledSource.generate_content_hash(raw_content)

        # Create first source
        CrawledSource.objects.create(
            url="https://example.com/page1",
            title="Page 1",
            source_type="review_article",
            extraction_status="pending",
            raw_content=raw_content,
            content_hash=content_hash,
        )

        # Check if duplicate content exists
        duplicate_exists = CrawledSource.objects.filter(
            content_hash=content_hash
        ).exists()
        self.assertTrue(duplicate_exists)


class CrawledSourceExtractionStatusTestCase(TestCase):
    """Test extraction_status state transitions."""

    def test_valid_extraction_statuses(self):
        """Test all valid extraction_status choices are accepted."""
        valid_statuses = ["pending", "processed", "failed", "needs_review"]

        for i, status in enumerate(valid_statuses):
            source = CrawledSource.objects.create(
                url=f"https://example.com/article/{i}",
                title=f"Article {i}",
                source_type="review_article",
                extraction_status=status,
            )
            self.assertEqual(source.extraction_status, status)

    def test_default_extraction_status_is_pending(self):
        """Test that default extraction_status is 'pending'."""
        source = CrawledSource.objects.create(
            url="https://example.com/default-status",
            title="Default Status Article",
            source_type="news_article",
        )
        self.assertEqual(source.extraction_status, "pending")

    def test_extraction_status_transition_to_processed(self):
        """Test transitioning extraction_status from pending to processed."""
        source = CrawledSource.objects.create(
            url="https://example.com/transition-test",
            title="Transition Test Article",
            source_type="award_page",
            extraction_status="pending",
        )

        self.assertEqual(source.extraction_status, "pending")

        # Transition to processed
        source.extraction_status = "processed"
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.extraction_status, "processed")

    def test_extraction_status_transition_to_failed(self):
        """Test transitioning extraction_status from pending to failed."""
        source = CrawledSource.objects.create(
            url="https://example.com/failed-test",
            title="Failed Test Article",
            source_type="retailer_page",
            extraction_status="pending",
        )

        # Transition to failed with error message
        source.extraction_status = "failed"
        source.last_crawl_error = "Connection timeout after 30 seconds"
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.extraction_status, "failed")
        self.assertEqual(source.last_crawl_error, "Connection timeout after 30 seconds")


class CrawledSourceWaybackTestCase(TestCase):
    """Test Wayback Machine URL storage."""

    def test_wayback_url_storage(self):
        """Test that Wayback Machine URLs are stored correctly."""
        wayback_url = "https://web.archive.org/web/20241230123456/https://example.com/article"

        source = CrawledSource.objects.create(
            url="https://example.com/article",
            title="Archived Article",
            source_type="review_article",
            extraction_status="processed",
            wayback_url=wayback_url,
            wayback_status="saved",
        )

        self.assertEqual(source.wayback_url, wayback_url)
        self.assertEqual(source.wayback_status, "saved")

    def test_valid_wayback_statuses(self):
        """Test all valid wayback_status choices are accepted."""
        valid_statuses = ["pending", "saved", "failed", "not_applicable"]

        for i, status in enumerate(valid_statuses):
            source = CrawledSource.objects.create(
                url=f"https://example.com/wayback/{i}",
                title=f"Wayback Test {i}",
                source_type="news_article",
                extraction_status="pending",
                wayback_status=status,
            )
            self.assertEqual(source.wayback_status, status)

    def test_default_wayback_status_is_pending(self):
        """Test that default wayback_status is 'pending'."""
        source = CrawledSource.objects.create(
            url="https://example.com/default-wayback",
            title="Default Wayback Status",
            source_type="review_article",
            extraction_status="pending",
        )
        self.assertEqual(source.wayback_status, "pending")

    def test_wayback_saved_at_timestamp(self):
        """Test that wayback_saved_at timestamp is stored correctly."""
        from django.utils import timezone

        source = CrawledSource.objects.create(
            url="https://example.com/wayback-timestamp",
            title="Wayback Timestamp Test",
            source_type="award_page",
            extraction_status="processed",
            wayback_status="saved",
            wayback_saved_at=timezone.now(),
        )

        self.assertIsNotNone(source.wayback_saved_at)


class CrawledSourceCrawlTrackingTestCase(TestCase):
    """Test crawl attempt tracking fields."""

    def test_crawl_attempts_tracking(self):
        """Test that crawl_attempts counter is tracked correctly."""
        source = CrawledSource.objects.create(
            url="https://example.com/crawl-attempts",
            title="Crawl Attempts Test",
            source_type="retailer_page",
            extraction_status="pending",
            crawl_attempts=0,
        )

        self.assertEqual(source.crawl_attempts, 0)

        # Increment crawl attempts
        source.crawl_attempts += 1
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.crawl_attempts, 1)

    def test_crawl_strategy_used_storage(self):
        """Test that crawl_strategy_used is stored correctly."""
        source = CrawledSource.objects.create(
            url="https://example.com/strategy-test",
            title="Strategy Test Article",
            source_type="distillery_page",
            extraction_status="processed",
            crawl_strategy_used="js_render",
        )

        self.assertEqual(source.crawl_strategy_used, "js_render")

    def test_detected_obstacles_json_storage(self):
        """Test that detected_obstacles JSONField stores data correctly."""
        obstacles = {
            "age_gate": True,
            "captcha": False,
            "js_required": True,
            "details": ["Cookie consent popup detected", "Age verification form found"],
        }

        source = CrawledSource.objects.create(
            url="https://example.com/obstacles-test",
            title="Obstacles Test Article",
            source_type="retailer_page",
            extraction_status="pending",
            detected_obstacles=obstacles,
        )

        source.refresh_from_db()
        self.assertEqual(source.detected_obstacles["age_gate"], True)
        self.assertEqual(source.detected_obstacles["captcha"], False)
        self.assertEqual(len(source.detected_obstacles["details"]), 2)

    def test_raw_content_cleared_flag(self):
        """Test raw_content_cleared flag works correctly."""
        source = CrawledSource.objects.create(
            url="https://example.com/raw-content-test",
            title="Raw Content Test",
            source_type="review_article",
            extraction_status="processed",
            raw_content="<html>Some content</html>",
            raw_content_cleared=False,
        )

        self.assertFalse(source.raw_content_cleared)
        self.assertIsNotNone(source.raw_content)

        # Clear raw content and set flag
        source.raw_content = None
        source.raw_content_cleared = True
        source.save()

        source.refresh_from_db()
        self.assertTrue(source.raw_content_cleared)
        self.assertIsNone(source.raw_content)


class CrawledSourceSourceTypeTestCase(TestCase):
    """Test source_type choices validation."""

    def test_valid_source_types(self):
        """Test all valid source_type choices are accepted."""
        valid_types = [
            "award_page",
            "review_article",
            "retailer_page",
            "distillery_page",
            "news_article",
        ]

        for i, source_type in enumerate(valid_types):
            source = CrawledSource.objects.create(
                url=f"https://example.com/type-{i}",
                title=f"Source Type Test {i}",
                source_type=source_type,
                extraction_status="pending",
            )
            self.assertEqual(source.source_type, source_type)
