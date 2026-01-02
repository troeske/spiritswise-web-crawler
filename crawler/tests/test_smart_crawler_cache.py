"""
Tests for SmartCrawler CrawledSource Caching.

Fix 1 of Duplicate Crawling Fixes: Use cached content from CrawledSource
to avoid redundant ScrapingBee API calls.

TDD Approach: These tests are written FIRST before implementation.

Tests verify:
1. Cache hit - Uses CrawledSource content instead of re-crawling
2. Cache miss - Crawls normally when no cache exists
3. Cache save - Saves crawled content to CrawledSource for reuse
4. Re-crawl on failure - Re-crawls if previous extraction failed
"""

import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from crawler.models import (
    CrawledSource,
    CrawledSourceTypeChoices,
    ExtractionStatusChoices,
)
from crawler.services.smart_crawler import SmartCrawler


@pytest.mark.django_db
class TestCrawledSourceCache:
    """Tests for SmartCrawler CrawledSource caching functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock clients
        self.mock_scrapingbee = Mock()
        self.mock_ai_client = Mock()

        # Create SmartCrawler instance
        self.crawler = SmartCrawler(
            scrapingbee_client=self.mock_scrapingbee,
            ai_client=self.mock_ai_client
        )

        # Sample test data
        self.test_url = "https://example.com/whiskey/test-product"
        self.test_content = "<html><body><h1>Test Whiskey Product</h1><p>Description here.</p></body></html>"
        self.test_product_type = "whiskey"

    def test_uses_cached_content_when_available(self):
        """Should use CrawledSource content instead of re-crawling."""
        # Create a CrawledSource with successful extraction (processed status)
        content_hash = hashlib.sha256(self.test_content.encode()).hexdigest()
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test Whiskey Product",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.PROCESSED,
            raw_content=self.test_content,
            content_hash=content_hash,
        )

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                    "producer": "Test Distillery",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee was NOT called (cache hit)
        self.mock_scrapingbee.fetch_page.assert_not_called()

        # Verify AI enhancement WAS called with cached content
        self.mock_ai_client.enhance_from_crawler.assert_called_once()
        call_args = self.mock_ai_client.enhance_from_crawler.call_args
        assert self.test_url in call_args.kwargs.get('source_url', '') or \
               self.test_url in str(call_args)

        # Verify result is successful
        assert result["success"] is True

    def test_crawls_when_no_cache(self):
        """Should crawl normally when URL not in CrawledSource."""
        # No CrawledSource exists for this URL

        # Configure mock ScrapingBee to return success
        self.mock_scrapingbee.fetch_page.return_value = {
            "success": True,
            "content": self.test_content,
        }

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                    "producer": "Test Distillery",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee WAS called (cache miss)
        self.mock_scrapingbee.fetch_page.assert_called_once()

        # Verify AI enhancement was called
        self.mock_ai_client.enhance_from_crawler.assert_called_once()

        # Verify result is successful
        assert result["success"] is True

    def test_saves_to_crawled_source_after_crawl(self):
        """Should save crawled content to CrawledSource."""
        # No CrawledSource exists initially
        assert CrawledSource.objects.filter(url=self.test_url).count() == 0

        # Configure mock ScrapingBee to return success
        self.mock_scrapingbee.fetch_page.return_value = {
            "success": True,
            "content": self.test_content,
        }

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                    "producer": "Test Distillery",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify CrawledSource record was created
        assert CrawledSource.objects.filter(url=self.test_url).count() == 1

        # Verify content was saved
        saved_source = CrawledSource.objects.get(url=self.test_url)
        assert saved_source.raw_content is not None
        assert len(saved_source.raw_content) > 0
        assert saved_source.content_hash is not None
        assert len(saved_source.content_hash) == 64  # SHA-256 hash

    def test_recrawls_if_previous_extraction_failed(self):
        """Should re-crawl if previous extraction failed."""
        # Create CrawledSource with extraction_status='failed'
        content_hash = hashlib.sha256(self.test_content.encode()).hexdigest()
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test Whiskey Product",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.FAILED,
            raw_content=self.test_content,
            content_hash=content_hash,
            last_crawl_error="Previous extraction error",
        )

        # Configure mock ScrapingBee to return success (for re-crawl)
        new_content = "<html><body><h1>Updated Test Whiskey</h1></body></html>"
        self.mock_scrapingbee.fetch_page.return_value = {
            "success": True,
            "content": new_content,
        }

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                    "producer": "Test Distillery",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee WAS called (re-crawl because previous failed)
        self.mock_scrapingbee.fetch_page.assert_called_once()

        # Verify result is successful
        assert result["success"] is True

    def test_recrawls_if_previous_extraction_pending(self):
        """Should re-crawl if previous extraction is still pending."""
        # Create CrawledSource with extraction_status='pending'
        content_hash = hashlib.sha256(self.test_content.encode()).hexdigest()
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test Whiskey Product",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.PENDING,
            raw_content=self.test_content,
            content_hash=content_hash,
        )

        # Configure mock ScrapingBee to return success
        self.mock_scrapingbee.fetch_page.return_value = {
            "success": True,
            "content": self.test_content,
        }

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee WAS called (re-crawl because pending status)
        self.mock_scrapingbee.fetch_page.assert_called_once()

    def test_uses_cache_with_needs_review_status(self):
        """Should use cache if extraction_status is 'needs_review' (partial success)."""
        # Create CrawledSource with extraction_status='needs_review'
        content_hash = hashlib.sha256(self.test_content.encode()).hexdigest()
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test Whiskey Product",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.NEEDS_REVIEW,
            raw_content=self.test_content,
            content_hash=content_hash,
        )

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee was NOT called (use cache for needs_review)
        self.mock_scrapingbee.fetch_page.assert_not_called()

        # Verify AI enhancement was called
        self.mock_ai_client.enhance_from_crawler.assert_called_once()

    def test_does_not_use_cache_without_content(self):
        """Should re-crawl if cached source has no content."""
        # Create CrawledSource with processed status but no raw_content
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test Whiskey Product",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.PROCESSED,
            raw_content=None,  # No content stored
            raw_content_cleared=True,
        )

        # Configure mock ScrapingBee to return success
        self.mock_scrapingbee.fetch_page.return_value = {
            "success": True,
            "content": self.test_content,
        }

        # Configure mock AI client to return success
        self.mock_ai_client.enhance_from_crawler.return_value = {
            "success": True,
            "data": {
                "extracted_data": {
                    "name": "Test Whiskey",
                }
            }
        }

        # Call _try_extraction
        result = self.crawler._try_extraction(self.test_url, self.test_product_type)

        # Verify ScrapingBee WAS called (no cached content available)
        self.mock_scrapingbee.fetch_page.assert_called_once()


@pytest.mark.django_db
class TestCrawledSourceCacheHelpers:
    """Tests for the cache helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_scrapingbee = Mock()
        self.mock_ai_client = Mock()
        self.crawler = SmartCrawler(
            scrapingbee_client=self.mock_scrapingbee,
            ai_client=self.mock_ai_client
        )
        self.test_url = "https://example.com/whiskey/helper-test"
        self.test_content = "<html><body><h1>Helper Test Content</h1></body></html>"

    def test_check_crawled_source_returns_content_for_processed(self):
        """_check_crawled_source should return content for processed status."""
        content_hash = hashlib.sha256(self.test_content.encode()).hexdigest()
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.PROCESSED,
            raw_content=self.test_content,
            content_hash=content_hash,
        )

        result = self.crawler._check_crawled_source(self.test_url)

        assert result == self.test_content

    def test_check_crawled_source_returns_none_for_failed(self):
        """_check_crawled_source should return None for failed status."""
        CrawledSource.objects.create(
            url=self.test_url,
            title="Test",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.FAILED,
            raw_content=self.test_content,
        )

        result = self.crawler._check_crawled_source(self.test_url)

        assert result is None

    def test_check_crawled_source_returns_none_for_nonexistent(self):
        """_check_crawled_source should return None for non-existent URL."""
        result = self.crawler._check_crawled_source("https://nonexistent.com/page")

        assert result is None

    def test_save_to_crawled_source_creates_record(self):
        """_save_to_crawled_source should create a CrawledSource record."""
        assert CrawledSource.objects.filter(url=self.test_url).count() == 0

        self.crawler._save_to_crawled_source(self.test_url, self.test_content)

        assert CrawledSource.objects.filter(url=self.test_url).count() == 1
        saved = CrawledSource.objects.get(url=self.test_url)
        assert saved.raw_content == self.test_content
        assert saved.content_hash is not None

    def test_save_to_crawled_source_updates_existing(self):
        """_save_to_crawled_source should update existing record."""
        # Create initial record
        CrawledSource.objects.create(
            url=self.test_url,
            title="Old Title",
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.FAILED,
            raw_content="old content",
        )

        # Save new content
        new_content = "<html><body>New content</body></html>"
        self.crawler._save_to_crawled_source(self.test_url, new_content)

        # Should still be one record
        assert CrawledSource.objects.filter(url=self.test_url).count() == 1

        # Content should be updated
        saved = CrawledSource.objects.get(url=self.test_url)
        assert saved.raw_content == new_content

    def test_save_to_crawled_source_truncates_large_content(self):
        """_save_to_crawled_source should truncate very large content."""
        # Create content larger than 500KB
        large_content = "x" * 600000

        self.crawler._save_to_crawled_source(self.test_url, large_content)

        saved = CrawledSource.objects.get(url=self.test_url)
        assert len(saved.raw_content) <= 500000
