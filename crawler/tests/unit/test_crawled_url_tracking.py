"""
Unit tests for CrawledURL tracking in product_saver.

TDD tests for ensuring URLs are properly tracked when products are discovered.
"""
import pytest
from django.utils import timezone

from crawler.models import CrawledURL, CrawlerSource, DiscoveredProduct
from crawler.services.product_saver import save_discovered_product


@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource."""
    return CrawlerSource.objects.create(
        name="Test Whisky Shop",
        slug="test-whisky-shop",
        base_url="https://test-whisky-shop.com",
        category="retailer",
        product_types=["whiskey"],
        is_active=True,
    )


@pytest.fixture
def sample_extracted_data():
    """Sample extracted data from AI Enhancement Service."""
    return {
        "name": "Glenfiddich 12 Year Old",
        "brand": "Glenfiddich",
        "whiskey_type": "scotch_single_malt",
        "abv": 40.0,
        "volume_ml": 700,
        "region": "Speyside",
        "age_statement": "12 Year Old",
        "description": "A smooth and mellow single malt whisky.",
    }


class TestCrawledURLCreation:
    """Tests for CrawledURL creation when products are saved."""

    def test_crawled_url_created_on_new_product(
        self, db, sample_source, sample_extracted_data
    ):
        """CrawledURL should be created when a new product is saved."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"

        result = save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
            raw_content="<html>Sample content</html>",
        )

        # Verify product was created
        assert result.created is True
        assert result.product is not None

        # Verify CrawledURL was created
        crawled_url = CrawledURL.objects.filter(url=source_url).first()
        assert crawled_url is not None, "CrawledURL should be created when product is saved"
        assert crawled_url.is_product_page is True
        assert crawled_url.was_processed is True
        assert crawled_url.processing_status == "success"

    def test_crawled_url_hash_computed(
        self, db, sample_extracted_data
    ):
        """CrawledURL should have url_hash computed correctly."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"

        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
        )

        crawled_url = CrawledURL.objects.get(url=source_url)
        expected_hash = CrawledURL.compute_url_hash(source_url)

        assert crawled_url.url_hash == expected_hash

    def test_crawled_url_content_hash_stored(
        self, db, sample_extracted_data
    ):
        """CrawledURL should store content hash when raw_content provided."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"
        raw_content = "<html><body>Glenfiddich 12 Year Old</body></html>"

        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
            raw_content=raw_content,
        )

        crawled_url = CrawledURL.objects.get(url=source_url)
        expected_hash = CrawledURL.compute_content_hash(raw_content)

        assert crawled_url.content_hash == expected_hash

    def test_crawled_url_timestamps_set(
        self, db, sample_extracted_data
    ):
        """CrawledURL should have timestamps set correctly."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"
        before_save = timezone.now()

        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
        )

        after_save = timezone.now()
        crawled_url = CrawledURL.objects.get(url=source_url)

        assert crawled_url.first_seen_at is not None
        assert crawled_url.last_crawled_at is not None
        assert before_save <= crawled_url.first_seen_at <= after_save
        assert before_save <= crawled_url.last_crawled_at <= after_save


class TestCrawledURLUpdate:
    """Tests for CrawledURL updates when products are re-crawled."""

    def test_crawled_url_updated_on_recrawl(
        self, db, sample_extracted_data
    ):
        """CrawledURL should be updated when the same URL is re-crawled."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"

        # First crawl
        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
        )

        first_crawl = CrawledURL.objects.get(url=source_url)
        first_crawl_time = first_crawl.last_crawled_at

        # Second crawl with check_existing=True
        updated_data = {**sample_extracted_data, "abv": 43.0}
        save_discovered_product(
            extracted_data=updated_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should still be only one CrawledURL
        assert CrawledURL.objects.filter(url=source_url).count() == 1

        # Last crawled time should be updated
        updated_crawl = CrawledURL.objects.get(url=source_url)
        assert updated_crawl.last_crawled_at >= first_crawl_time

    def test_crawled_url_content_change_detected(
        self, db, sample_extracted_data
    ):
        """CrawledURL should detect content changes between crawls."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"
        original_content = "<html>Original content</html>"

        # First crawl
        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
            raw_content=original_content,
        )

        first_crawl = CrawledURL.objects.get(url=source_url)
        assert first_crawl.content_changed is False

        # Second crawl with different content
        new_content = "<html>Updated content with new info</html>"
        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
            raw_content=new_content,
            check_existing=True,
        )

        updated_crawl = CrawledURL.objects.get(url=source_url)
        assert updated_crawl.content_changed is True
        assert updated_crawl.content_hash == CrawledURL.compute_content_hash(new_content)


class TestCrawledURLDeduplication:
    """Tests for CrawledURL deduplication behavior."""

    def test_same_url_reuses_crawled_url(
        self, db, sample_extracted_data
    ):
        """Same URL should reuse existing CrawledURL entry."""
        source_url = "https://test-whisky-shop.com/products/glenfiddich-12"

        # Save product first time
        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
        )

        # Save different product with same URL (without check_existing to create new product)
        different_data = {**sample_extracted_data, "name": "Glenfiddich 15 Year Old"}
        save_discovered_product(
            extracted_data=different_data,
            source_url=source_url,  # Same URL
            product_type="whiskey",
            discovery_source="search",
        )

        # Should still be only one CrawledURL for this URL
        assert CrawledURL.objects.filter(url=source_url).count() == 1


class TestCrawledURLProcessingStatus:
    """Tests for CrawledURL processing status tracking."""

    def test_processing_status_success_on_valid_product(
        self, db, sample_extracted_data
    ):
        """Processing status should be 'success' for valid products."""
        source_url = "https://test-whisky-shop.com/products/valid-product"

        save_discovered_product(
            extracted_data=sample_extracted_data,
            source_url=source_url,
            product_type="whiskey",
            discovery_source="search",
        )

        crawled_url = CrawledURL.objects.get(url=source_url)
        assert crawled_url.processing_status == "success"
        assert crawled_url.was_processed is True
        assert crawled_url.is_product_page is True
