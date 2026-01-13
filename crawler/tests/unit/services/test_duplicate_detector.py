"""
Unit tests for DuplicateDetector Service.

Task 2.3: Duplicate Detection

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.7 (FEAT-007)

Tests verify:
- URL-based deduplication (canonicalization and checking)
- Content hash deduplication
- Product name/brand fuzzy matching
- Integration with discovery flow
"""

import hashlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import TestCase

from crawler.services.duplicate_detector import (
    DuplicateDetector,
    get_duplicate_detector,
    reset_duplicate_detector,
)


class URLCanonicalizationTests(TestCase):
    """Tests for URL canonicalization logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    def test_canonicalize_removes_trailing_slash(self):
        """Test that trailing slashes are removed."""
        url = "https://example.com/page/"
        canonical = self.detector._canonicalize_url(url)
        self.assertEqual(canonical, "https://example.com/page")

    def test_canonicalize_lowercases_domain(self):
        """Test that domain is lowercased."""
        url = "https://EXAMPLE.COM/Page"
        canonical = self.detector._canonicalize_url(url)
        self.assertTrue(canonical.startswith("https://example.com"))

    def test_canonicalize_removes_www(self):
        """Test that www prefix is removed."""
        url = "https://www.example.com/page"
        canonical = self.detector._canonicalize_url(url)
        self.assertEqual(canonical, "https://example.com/page")

    def test_canonicalize_removes_tracking_params(self):
        """Test that common tracking parameters are removed."""
        url = "https://example.com/page?utm_source=google&utm_medium=cpc&id=123"
        canonical = self.detector._canonicalize_url(url)
        # Should keep id=123 but remove utm params
        self.assertIn("id=123", canonical)
        self.assertNotIn("utm_source", canonical)
        self.assertNotIn("utm_medium", canonical)

    def test_canonicalize_removes_fragment(self):
        """Test that URL fragments are removed."""
        url = "https://example.com/page#section"
        canonical = self.detector._canonicalize_url(url)
        self.assertEqual(canonical, "https://example.com/page")

    def test_canonicalize_sorts_query_params(self):
        """Test that query parameters are sorted for consistent comparison."""
        url1 = "https://example.com/page?b=2&a=1"
        url2 = "https://example.com/page?a=1&b=2"
        canonical1 = self.detector._canonicalize_url(url1)
        canonical2 = self.detector._canonicalize_url(url2)
        self.assertEqual(canonical1, canonical2)

    def test_canonicalize_handles_empty_url(self):
        """Test that empty URLs are handled gracefully."""
        canonical = self.detector._canonicalize_url("")
        self.assertEqual(canonical, "")

    def test_canonicalize_handles_none_url(self):
        """Test that None URLs are handled gracefully."""
        canonical = self.detector._canonicalize_url(None)
        self.assertEqual(canonical, "")


class URLDeduplicationTests(TestCase):
    """Tests for URL-based deduplication."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_url_returns_true_for_existing(self, mock_crawled_source):
        """Test that existing URLs are detected as duplicates."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = True

        url = "https://example.com/whiskey-review"
        is_dup = self.detector.is_duplicate_url(url)

        self.assertTrue(is_dup)
        mock_crawled_source.objects.filter.assert_called_once()

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_url_returns_false_for_new(self, mock_crawled_source):
        """Test that new URLs are not detected as duplicates."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = False

        url = "https://example.com/new-whiskey-review"
        is_dup = self.detector.is_duplicate_url(url)

        self.assertFalse(is_dup)

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_url_canonicalizes_before_check(self, mock_crawled_source):
        """Test that URLs are canonicalized before duplicate check."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = False

        # URL with trailing slash and www
        url = "https://www.example.com/page/"
        self.detector.is_duplicate_url(url)

        # Should check with canonicalized URL
        call_args = mock_crawled_source.objects.filter.call_args
        self.assertIn("url", call_args.kwargs)
        self.assertEqual(call_args.kwargs["url"], "https://example.com/page")

    def test_is_duplicate_url_handles_empty_url(self):
        """Test that empty URLs return False (not duplicate)."""
        is_dup = self.detector.is_duplicate_url("")
        self.assertFalse(is_dup)

    def test_is_duplicate_url_handles_none_url(self):
        """Test that None URLs return False."""
        is_dup = self.detector.is_duplicate_url(None)
        self.assertFalse(is_dup)


class ContentHashDeduplicationTests(TestCase):
    """Tests for content hash deduplication."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    def test_generate_content_hash(self):
        """Test content hash generation."""
        content = "This is some whiskey review content."
        hash_value = self.detector._generate_content_hash(content)
        expected = hashlib.sha256(content.encode()).hexdigest()
        self.assertEqual(hash_value, expected)

    def test_generate_content_hash_normalizes_whitespace(self):
        """Test that content hash normalizes whitespace."""
        content1 = "Some   content   with   extra   spaces"
        content2 = "Some content with extra spaces"
        hash1 = self.detector._generate_content_hash(content1)
        hash2 = self.detector._generate_content_hash(content2)
        self.assertEqual(hash1, hash2)

    def test_generate_content_hash_strips_content(self):
        """Test that content hash strips leading/trailing whitespace."""
        content1 = "   Some content   "
        content2 = "Some content"
        hash1 = self.detector._generate_content_hash(content1)
        hash2 = self.detector._generate_content_hash(content2)
        self.assertEqual(hash1, hash2)

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_content_returns_true_for_existing(self, mock_crawled_source):
        """Test that existing content is detected as duplicate."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = True

        content = "This is duplicate content."
        is_dup = self.detector.is_duplicate_content(content)

        self.assertTrue(is_dup)

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_content_returns_false_for_new(self, mock_crawled_source):
        """Test that new content is not detected as duplicate."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = False

        content = "This is new unique content."
        is_dup = self.detector.is_duplicate_content(content)

        self.assertFalse(is_dup)

    @patch("crawler.models.CrawledSource")
    def test_is_duplicate_content_queries_by_hash(self, mock_crawled_source):
        """Test that content duplicate check queries by hash."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = False

        content = "Test content for hash query"
        self.detector.is_duplicate_content(content)

        call_args = mock_crawled_source.objects.filter.call_args
        self.assertIn("content_hash", call_args.kwargs)

    def test_is_duplicate_content_handles_empty_content(self):
        """Test that empty content returns False."""
        is_dup = self.detector.is_duplicate_content("")
        self.assertFalse(is_dup)

    def test_is_duplicate_content_handles_none_content(self):
        """Test that None content returns False."""
        is_dup = self.detector.is_duplicate_content(None)
        self.assertFalse(is_dup)


class ProductFuzzyMatchingTests(TestCase):
    """Tests for product name/brand fuzzy matching."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    @patch("crawler.models.DiscoveredProduct")
    def test_find_duplicate_product_exact_match(self, mock_product):
        """Test finding duplicate by exact name and brand match."""
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_existing.name = "GlenAllachie 15 Year Old"
        mock_existing.brand = MagicMock()
        mock_existing.brand.name = "GlenAllachie"
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        result = self.detector.find_duplicate_product(
            name="GlenAllachie 15 Year Old",
            brand="GlenAllachie"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, mock_existing.id)

    @patch("crawler.models.DiscoveredProduct")
    def test_find_duplicate_product_no_match(self, mock_product):
        """Test that no match is found for new product."""
        mock_product.objects.filter.return_value.first.return_value = None

        result = self.detector.find_duplicate_product(
            name="New Whiskey Product",
            brand="New Brand"
        )

        self.assertIsNone(result)

    @patch("crawler.models.DiscoveredProduct")
    def test_find_duplicate_product_first_word_match(self, mock_product):
        """Test fuzzy matching by first word of name.

        Spec Reference: Section 5.7.3
        Uses first word of name for fuzzy matching.
        """
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_existing.name = "GlenAllachie 15 Year Old"
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        # Slightly different name but same first word
        result = self.detector.find_duplicate_product(
            name="GlenAllachie 15yr",
            brand="GlenAllachie"
        )

        self.assertIsNotNone(result)
        # Should filter by brand and first word
        call_args = mock_product.objects.filter.call_args
        self.assertIn("brand__name__iexact", call_args.kwargs)

    @patch("crawler.models.DiscoveredProduct")
    def test_find_duplicate_product_case_insensitive_brand(self, mock_product):
        """Test that brand matching is case insensitive."""
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        self.detector.find_duplicate_product(
            name="Highland Park 18",
            brand="highland park"  # lowercase
        )

        call_args = mock_product.objects.filter.call_args
        self.assertIn("brand__name__iexact", call_args.kwargs)
        self.assertEqual(call_args.kwargs["brand__name__iexact"], "highland park")

    def test_find_duplicate_product_handles_empty_name(self):
        """Test that empty name returns None."""
        result = self.detector.find_duplicate_product(name="", brand="Brand")
        self.assertIsNone(result)

    def test_find_duplicate_product_handles_none_name(self):
        """Test that None name returns None."""
        result = self.detector.find_duplicate_product(name=None, brand="Brand")
        self.assertIsNone(result)

    @patch("crawler.models.DiscoveredProduct")
    def test_find_duplicate_product_without_brand(self, mock_product):
        """Test finding duplicate when brand is not provided."""
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        result = self.detector.find_duplicate_product(
            name="Mystery Whiskey",
            brand=None
        )

        self.assertIsNotNone(result)
        # Should filter by name only
        call_args = mock_product.objects.filter.call_args
        self.assertNotIn("brand__name__iexact", call_args.kwargs)


class DiscoveryFlowIntegrationTests(TestCase):
    """Tests for integration with discovery flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    @patch("crawler.models.CrawledSource")
    def test_check_url_before_fetch(self, mock_crawled_source):
        """Test checking URL before fetching to avoid redundant requests.

        Spec Reference: Section 5.7.1
        Check URL before fetching to avoid redundant processing.
        """
        mock_crawled_source.objects.filter.return_value.exists.return_value = True

        # Should return True indicating URL should be skipped
        should_skip = self.detector.should_skip_url("https://example.com/whiskey")
        self.assertTrue(should_skip)

    @patch("crawler.models.CrawledSource")
    def test_check_content_after_fetch(self, mock_crawled_source):
        """Test checking content after fetching to avoid redundant extraction.

        Spec Reference: Section 5.7.2
        Check content after fetching to skip duplicate content.
        """
        mock_crawled_source.objects.filter.return_value.exists.return_value = True

        content = "Fetched content from new URL but same as existing."
        should_skip = self.detector.should_skip_content(content)
        self.assertTrue(should_skip)

    @patch("crawler.models.DiscoveredProduct")
    def test_check_product_after_extraction(self, mock_product):
        """Test checking product after extraction to avoid duplicate saves.

        Spec Reference: Section 5.7.3
        Check product after extraction to link to existing.
        """
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        existing_id = self.detector.find_duplicate_product(
            name="Highland Park 18 Year Old",
            brand="Highland Park"
        )

        self.assertIsNotNone(existing_id)

    @patch("crawler.models.CrawledSource")
    def test_full_deduplication_flow_url_duplicate(self, mock_crawled_source):
        """Test full deduplication flow where URL is duplicate."""
        mock_crawled_source.objects.filter.return_value.exists.return_value = True

        # Check all stages
        url_check = self.detector.check_all(
            url="https://example.com/existing-page",
            content=None,
            product_name=None,
            product_brand=None
        )

        self.assertTrue(url_check["is_duplicate"])
        self.assertEqual(url_check["duplicate_type"], "url")

    @patch("crawler.models.CrawledSource")
    def test_full_deduplication_flow_content_duplicate(self, mock_crawled_source):
        """Test full deduplication flow where content is duplicate."""
        # URL not duplicate
        mock_crawled_source.objects.filter.return_value.exists.side_effect = [
            False,  # URL check
            True,   # Content check
        ]

        url_check = self.detector.check_all(
            url="https://example.com/new-page",
            content="Duplicate content here",
            product_name=None,
            product_brand=None
        )

        self.assertTrue(url_check["is_duplicate"])
        self.assertEqual(url_check["duplicate_type"], "content")

    @patch("crawler.models.CrawledSource")
    @patch("crawler.models.DiscoveredProduct")
    def test_full_deduplication_flow_product_duplicate(self, mock_product, mock_crawled_source):
        """Test full deduplication flow where product is duplicate."""
        # URL and content not duplicate
        mock_crawled_source.objects.filter.return_value.exists.return_value = False

        # Product is duplicate
        mock_existing = MagicMock()
        mock_existing.id = uuid4()
        mock_product.objects.filter.return_value.first.return_value = mock_existing

        result = self.detector.check_all(
            url="https://example.com/new-page",
            content="New unique content",
            product_name="Highland Park 18",
            product_brand="Highland Park"
        )

        self.assertTrue(result["is_duplicate"])
        self.assertEqual(result["duplicate_type"], "product")
        self.assertEqual(result["existing_product_id"], mock_existing.id)


class SingletonPatternTests(TestCase):
    """Tests for singleton pattern implementation."""

    def tearDown(self):
        """Reset singleton after each test."""
        reset_duplicate_detector()

    def test_get_duplicate_detector_returns_singleton(self):
        """Test that get_duplicate_detector returns same instance."""
        detector1 = get_duplicate_detector()
        detector2 = get_duplicate_detector()
        self.assertIs(detector1, detector2)

    def test_reset_duplicate_detector_clears_singleton(self):
        """Test that reset_duplicate_detector clears the singleton."""
        detector1 = get_duplicate_detector()
        reset_duplicate_detector()
        detector2 = get_duplicate_detector()
        self.assertIsNot(detector1, detector2)


class RecordTrackingTests(TestCase):
    """Tests for tracking URLs and content that have been checked."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector()

    def test_record_url_adds_to_session_cache(self):
        """Test that recorded URLs are cached for session-level dedup."""
        url = "https://example.com/page"
        self.detector.record_url(url)
        self.assertTrue(self.detector.is_url_in_session(url))

    def test_record_url_canonicalizes(self):
        """Test that recorded URLs are canonicalized for cache."""
        url = "https://www.example.com/page/"
        self.detector.record_url(url)
        # Should find with different formatting
        self.assertTrue(self.detector.is_url_in_session("https://example.com/page"))

    def test_record_content_hash_adds_to_session_cache(self):
        """Test that recorded content hashes are cached for session-level dedup."""
        content = "Some test content"
        self.detector.record_content(content)
        self.assertTrue(self.detector.is_content_in_session(content))

    def test_clear_session_cache_resets_tracking(self):
        """Test that session cache can be cleared."""
        self.detector.record_url("https://example.com/page")
        self.detector.record_content("Some content")
        self.detector.clear_session_cache()
        self.assertFalse(self.detector.is_url_in_session("https://example.com/page"))
        self.assertFalse(self.detector.is_content_in_session("Some content"))
