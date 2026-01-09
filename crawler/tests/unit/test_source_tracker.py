"""
Unit tests for SourceTracker service.

Tests Phase 4.5: Source Tracking and Content Archival
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4


@pytest.fixture
def sample_brand(db):
    """Create a sample brand for tests."""
    from crawler.models import DiscoveredBrand
    return DiscoveredBrand.objects.create(
        name="Test Brand",
        slug="test-brand"
    )


@pytest.fixture
def sample_discovery_source(db):
    """Create a sample discovery source for tests."""
    from crawler.models import DiscoverySourceConfig
    return DiscoverySourceConfig.objects.create(
        name="Test Source",
        source_type="retailer",
        base_url="https://example.com",
        is_active=True,
        crawl_priority=5,
        crawl_frequency="weekly",
        reliability_score=7
    )


@pytest.fixture
def sample_crawled_source(db):
    """Create a sample crawled source for tests."""
    from crawler.models import CrawledSource
    return CrawledSource.objects.create(
        url="https://example.com/test",
        title="Test Page",
        source_type="review_article"
    )


@pytest.fixture
def sample_product(db, sample_brand):
    """Create a sample product for tests."""
    from crawler.models import DiscoveredProduct
    return DiscoveredProduct.objects.create(
        name="Test Whiskey",
        brand=sample_brand,
        product_type="whiskey"
    )

# Test CrawledSource new fields
class TestCrawledSourceNewFields:
    """Tests for new CrawledSource model fields."""

    def test_preprocessed_content_field_exists(self):
        """Test that preprocessed_content field is available."""
        from crawler.models import CrawledSource

        # Check field exists
        field = CrawledSource._meta.get_field('preprocessed_content')
        assert field is not None
        assert field.null is True
        assert field.blank is True

    def test_preprocessed_at_field_exists(self):
        """Test that preprocessed_at field is available."""
        from crawler.models import CrawledSource

        field = CrawledSource._meta.get_field('preprocessed_at')
        assert field is not None
        assert field.null is True
        assert field.blank is True

    def test_cleanup_eligible_field_exists(self):
        """Test that cleanup_eligible field is available."""
        from crawler.models import CrawledSource

        field = CrawledSource._meta.get_field('cleanup_eligible')
        assert field is not None


# Test cleanup eligibility logic
class TestCleanupEligibility:
    """Tests for cleanup eligibility logic."""

    def test_cleanup_eligible_default_false(self):
        """Test that cleanup_eligible defaults to False."""
        from crawler.models import CrawledSource

        # Create instance without saving
        source = CrawledSource(
            url="https://example.com/test",
            title="Test Page"
        )
        assert source.cleanup_eligible is False

    def test_cleanup_eligible_requires_processed_status(self):
        """Test cleanup eligible only when extraction_status is PROCESSED."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        # PENDING status - not eligible
        assert tracker.is_cleanup_eligible("pending", "saved") is False

        # FAILED status - not eligible
        assert tracker.is_cleanup_eligible("failed", "saved") is False

        # PROCESSED status - eligible (if wayback saved)
        assert tracker.is_cleanup_eligible("processed", "saved") is True

    def test_cleanup_eligible_requires_wayback_saved(self):
        """Test cleanup eligible only when wayback_status is SAVED."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        # PENDING wayback - not eligible
        assert tracker.is_cleanup_eligible("processed", "pending") is False

        # FAILED wayback - not eligible
        assert tracker.is_cleanup_eligible("processed", "failed") is False

        # SAVED wayback - eligible
        assert tracker.is_cleanup_eligible("processed", "saved") is True

    def test_cleanup_eligible_both_conditions_required(self):
        """Test both extraction processed AND wayback saved required."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        # Neither condition met
        assert tracker.is_cleanup_eligible("pending", "pending") is False

        # Only extraction met
        assert tracker.is_cleanup_eligible("processed", "pending") is False

        # Only wayback met
        assert tracker.is_cleanup_eligible("pending", "saved") is False

        # Both conditions met
        assert tracker.is_cleanup_eligible("processed", "saved") is True


# Test SourceTracker class
class TestSourceTrackerInit:
    """Tests for SourceTracker initialization."""

    def test_source_tracker_instantiation(self):
        """Test SourceTracker can be instantiated."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()
        assert tracker is not None

    def test_source_tracker_singleton(self):
        """Test SourceTracker is a singleton."""
        from crawler.services.source_tracker import SourceTracker

        tracker1 = SourceTracker()
        tracker2 = SourceTracker()
        assert tracker1 is tracker2


# Test store_crawled_source method
class TestStoreCrawledSource:
    """Tests for store_crawled_source method."""

    @pytest.mark.django_db
    def test_store_crawled_source_creates_record(self):
        """Test storing a new crawled source creates a database record."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource

        tracker = SourceTracker()

        result = tracker.store_crawled_source(
            url="https://example.com/test-page",
            title="Test Product Page",
            raw_content="<html><body>Test content</body></html>",
            source_type="review_article"
        )

        assert result is not None
        assert result.url == "https://example.com/test-page"
        assert result.title == "Test Product Page"
        assert result.raw_content == "<html><body>Test content</body></html>"
        assert result.source_type == "review_article"

    @pytest.mark.django_db
    def test_store_crawled_source_with_preprocessed_content(self):
        """Test storing source with preprocessed content."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        result = tracker.store_crawled_source(
            url="https://example.com/preprocessed",
            title="Preprocessed Page",
            raw_content="<html>raw</html>",
            preprocessed_content="Clean text extracted from page",
            source_type="review_article"
        )

        assert result.preprocessed_content == "Clean text extracted from page"
        assert result.preprocessed_at is not None

    @pytest.mark.django_db
    def test_store_crawled_source_generates_content_hash(self):
        """Test content hash is generated for deduplication."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        result = tracker.store_crawled_source(
            url="https://example.com/hash-test",
            title="Hash Test",
            raw_content="<html>content for hashing</html>",
            source_type="review_article"
        )

        assert result.content_hash is not None
        assert len(result.content_hash) == 64  # SHA-256 hash

    @pytest.mark.django_db
    def test_store_crawled_source_updates_existing(self):
        """Test storing source with existing URL updates the record."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        # Create initial record
        result1 = tracker.store_crawled_source(
            url="https://example.com/update-test",
            title="Original Title",
            raw_content="<html>original</html>",
            source_type="review_article"
        )

        # Update with same URL
        result2 = tracker.store_crawled_source(
            url="https://example.com/update-test",
            title="Updated Title",
            raw_content="<html>updated</html>",
            source_type="review_article"
        )

        assert result1.id == result2.id  # Same record
        assert result2.title == "Updated Title"
        assert result2.raw_content == "<html>updated</html>"

    @pytest.mark.django_db
    def test_store_crawled_source_with_discovery_source(self, sample_discovery_source):
        """Test storing source linked to a discovery source."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        result = tracker.store_crawled_source(
            url="https://example.com/linked-test",
            title="Linked Page",
            raw_content="<html>linked</html>",
            source_type="review_article",
            discovery_source_id=sample_discovery_source.pk
        )

        assert result.discovery_source_id == sample_discovery_source.pk


# Test link_product_to_source method
class TestLinkProductToSource:
    """Tests for link_product_to_source method."""

    @pytest.mark.django_db
    def test_link_product_to_source_creates_junction(self, sample_product, sample_crawled_source):
        """Test linking a product to a source creates junction record."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import ProductSource

        tracker = SourceTracker()

        # Link them
        result = tracker.link_product_to_source(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            extraction_confidence=0.85,
            fields_extracted=["name", "brand", "abv"]
        )

        assert result is not None
        assert result.product_id == sample_product.pk
        assert result.source_id == sample_crawled_source.pk
        assert float(result.extraction_confidence) == 0.85
        assert result.fields_extracted == ["name", "brand", "abv"]

    @pytest.mark.django_db
    def test_link_product_to_source_updates_existing(self, sample_product, sample_crawled_source):
        """Test linking with same product+source updates the junction."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        # Create initial link
        result1 = tracker.link_product_to_source(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            extraction_confidence=0.7,
            fields_extracted=["name"]
        )

        # Update link
        result2 = tracker.link_product_to_source(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            extraction_confidence=0.9,
            fields_extracted=["name", "brand", "abv"]
        )

        assert result1.id == result2.id  # Same record
        assert float(result2.extraction_confidence) == 0.9
        assert result2.fields_extracted == ["name", "brand", "abv"]

    @pytest.mark.django_db
    def test_link_product_to_source_with_mention_type(self, sample_brand):
        """Test linking with mention type."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource, DiscoveredProduct

        tracker = SourceTracker()

        source = CrawledSource.objects.create(
            url="https://example.com/mention-test",
            title="Mention Test",
            source_type="award_page"
        )

        product = DiscoveredProduct.objects.create(
            name="Award Whiskey",
            brand=sample_brand,
            product_type="whiskey"
        )

        result = tracker.link_product_to_source(
            product_id=product.pk,
            source_id=source.pk,
            extraction_confidence=0.95,
            fields_extracted=["name", "awards"],
            mention_type="award_winner"
        )

        assert result.mention_type == "award_winner"


# Test track_field_provenance method
class TestTrackFieldProvenance:
    """Tests for track_field_provenance method."""

    @pytest.mark.django_db
    def test_track_field_provenance_creates_record(self, sample_product, sample_crawled_source):
        """Test tracking field provenance creates a record."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import ProductFieldSource

        tracker = SourceTracker()

        result = tracker.track_field_provenance(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.92
        )

        assert result is not None
        assert result.product_id == sample_product.pk
        assert result.source_id == sample_crawled_source.pk
        assert result.field_name == "abv"
        assert result.extracted_value == "43.0"
        assert float(result.confidence) == 0.92

    @pytest.mark.django_db
    def test_track_field_provenance_multiple_fields(self, sample_product, sample_crawled_source):
        """Test tracking provenance for multiple fields."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import ProductFieldSource

        tracker = SourceTracker()

        # Track multiple fields
        fields = [
            ("name", "Multi Field Whiskey", 0.95),
            ("brand", "Test Brand", 0.90),
            ("abv", "46.0", 0.85),
            ("description", "A complex whiskey", 0.80)
        ]

        for field_name, value, confidence in fields:
            tracker.track_field_provenance(
                product_id=sample_product.pk,
                source_id=sample_crawled_source.pk,
                field_name=field_name,
                extracted_value=value,
                confidence=confidence
            )

        # Verify all recorded
        records = ProductFieldSource.objects.filter(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk
        )
        assert records.count() == 4

    @pytest.mark.django_db
    def test_track_field_provenance_updates_existing(self, sample_product, sample_crawled_source):
        """Test tracking provenance for same field updates record."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import ProductFieldSource

        tracker = SourceTracker()

        # Track initial value
        result1 = tracker.track_field_provenance(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.70
        )

        # Update with higher confidence
        result2 = tracker.track_field_provenance(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.95
        )

        assert result1.id == result2.id  # Same record updated
        assert result2.extracted_value == "43.0"
        assert float(result2.confidence) == 0.95

    @pytest.mark.django_db
    def test_track_field_provenance_multiple_sources_same_field(self, sample_brand):
        """Test same field can have provenance from multiple sources."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource, DiscoveredProduct, ProductFieldSource

        tracker = SourceTracker()

        source1 = CrawledSource.objects.create(
            url="https://example.com/source1",
            title="Source 1",
            source_type="review_article"
        )

        source2 = CrawledSource.objects.create(
            url="https://example.com/source2",
            title="Source 2",
            source_type="retailer_page"
        )

        product = DiscoveredProduct.objects.create(
            name="Multi Source Whiskey",
            brand=sample_brand,
            product_type="whiskey"
        )

        # Track from source 1
        tracker.track_field_provenance(
            product_id=product.pk,
            source_id=source1.pk,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.85
        )

        # Track from source 2
        tracker.track_field_provenance(
            product_id=product.pk,
            source_id=source2.pk,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.90
        )

        # Verify both recorded
        records = ProductFieldSource.objects.filter(
            product_id=product.pk,
            field_name="abv"
        )
        assert records.count() == 2


# Test batch operations
class TestBatchOperations:
    """Tests for batch tracking operations."""

    @pytest.mark.django_db
    def test_track_extraction_result_all_fields(self, sample_product, sample_crawled_source):
        """Test tracking an entire extraction result."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import ProductSource, ProductFieldSource

        tracker = SourceTracker()

        extracted_data = {
            "name": "Batch Whiskey",
            "brand": "Test Brand",
            "abv": 43.0,
            "description": "A fine whiskey",
            "palate_flavors": ["vanilla", "oak", "honey"]
        }

        field_confidences = {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.85,
            "description": 0.80,
            "palate_flavors": 0.75
        }

        tracker.track_extraction_result(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk,
            extracted_data=extracted_data,
            field_confidences=field_confidences,
            overall_confidence=0.85
        )

        # Verify product source link
        ps = ProductSource.objects.get(product_id=sample_product.pk, source_id=sample_crawled_source.pk)
        assert float(ps.extraction_confidence) == 0.85
        assert "name" in ps.fields_extracted

        # Verify field sources
        pfs_count = ProductFieldSource.objects.filter(
            product_id=sample_product.pk,
            source_id=sample_crawled_source.pk
        ).count()
        assert pfs_count == 5  # All 5 fields tracked


# Test update_cleanup_eligibility
class TestUpdateCleanupEligibility:
    """Tests for update_cleanup_eligibility method."""

    @pytest.mark.django_db
    def test_update_cleanup_eligibility_sets_true(self):
        """Test updating eligibility sets it to True when conditions met."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource

        tracker = SourceTracker()

        source = CrawledSource.objects.create(
            url="https://example.com/eligible-test",
            title="Eligible Test",
            source_type="review_article",
            extraction_status="processed",
            wayback_status="saved"
        )

        tracker.update_cleanup_eligibility(source.pk)

        source.refresh_from_db()
        assert source.cleanup_eligible is True

    @pytest.mark.django_db
    def test_update_cleanup_eligibility_stays_false(self):
        """Test eligibility stays False when conditions not met."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource

        tracker = SourceTracker()

        source = CrawledSource.objects.create(
            url="https://example.com/not-eligible",
            title="Not Eligible Test",
            source_type="review_article",
            extraction_status="processed",
            wayback_status="pending"  # Not saved yet
        )

        tracker.update_cleanup_eligibility(source.pk)

        source.refresh_from_db()
        assert source.cleanup_eligible is False


# Test get_pending_cleanup_sources
class TestGetPendingCleanupSources:
    """Tests for getting sources pending cleanup."""

    @pytest.mark.django_db
    def test_get_pending_cleanup_sources(self):
        """Test getting sources eligible for cleanup."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource

        tracker = SourceTracker()

        # Create eligible source (not cleared yet)
        CrawledSource.objects.create(
            url="https://example.com/cleanup1",
            title="Cleanup 1",
            source_type="review_article",
            raw_content="<html>content</html>",
            raw_content_cleared=False,
            cleanup_eligible=True
        )

        # Create already cleared source
        CrawledSource.objects.create(
            url="https://example.com/cleanup2",
            title="Cleanup 2",
            source_type="review_article",
            raw_content=None,
            raw_content_cleared=True,
            cleanup_eligible=True
        )

        # Create not eligible source
        CrawledSource.objects.create(
            url="https://example.com/cleanup3",
            title="Cleanup 3",
            source_type="review_article",
            raw_content="<html>content</html>",
            raw_content_cleared=False,
            cleanup_eligible=False
        )

        pending = tracker.get_pending_cleanup_sources()

        # Only first source should be returned
        assert pending.count() == 1
        assert pending.first().url == "https://example.com/cleanup1"


# Test get_source_by_url
class TestGetSourceByUrl:
    """Tests for getting source by URL."""

    @pytest.mark.django_db
    def test_get_source_by_url_found(self):
        """Test getting existing source by URL."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource

        tracker = SourceTracker()

        source = CrawledSource.objects.create(
            url="https://example.com/find-me",
            title="Find Me",
            source_type="review_article"
        )

        found = tracker.get_source_by_url("https://example.com/find-me")

        assert found is not None
        assert found.id == source.id

    @pytest.mark.django_db
    def test_get_source_by_url_not_found(self):
        """Test getting non-existent source by URL."""
        from crawler.services.source_tracker import SourceTracker

        tracker = SourceTracker()

        found = tracker.get_source_by_url("https://example.com/does-not-exist")

        assert found is None


# Test get_product_sources
class TestGetProductSources:
    """Tests for getting sources for a product."""

    @pytest.mark.django_db
    def test_get_product_sources(self, sample_brand):
        """Test getting all sources for a product."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource, DiscoveredProduct

        tracker = SourceTracker()

        # Create product
        product = DiscoveredProduct.objects.create(
            name="Multi Source Product",
            brand=sample_brand,
            product_type="whiskey"
        )

        # Create and link multiple sources
        for i in range(3):
            source = CrawledSource.objects.create(
                url=f"https://example.com/source-{i}",
                title=f"Source {i}",
                source_type="review_article"
            )
            tracker.link_product_to_source(
                product_id=product.pk,
                source_id=source.pk,
                extraction_confidence=0.8,
                fields_extracted=["name"]
            )

        sources = tracker.get_product_sources(product.pk)

        assert len(sources) == 3


# Test get_field_provenance_history
class TestGetFieldProvenanceHistory:
    """Tests for getting field provenance history."""

    @pytest.mark.django_db
    def test_get_field_provenance_history(self, sample_brand):
        """Test getting provenance history for a field."""
        from crawler.services.source_tracker import SourceTracker
        from crawler.models import CrawledSource, DiscoveredProduct

        tracker = SourceTracker()

        product = DiscoveredProduct.objects.create(
            name="History Product",
            brand=sample_brand,
            product_type="whiskey"
        )

        # Track field from multiple sources
        for i in range(3):
            source = CrawledSource.objects.create(
                url=f"https://example.com/history-{i}",
                title=f"History {i}",
                source_type="review_article"
            )
            tracker.track_field_provenance(
                product_id=product.pk,
                source_id=source.pk,
                field_name="abv",
                extracted_value=f"{40 + i}.0",
                confidence=0.8 + (i * 0.05)
            )

        history = tracker.get_field_provenance_history(
            product_id=product.pk,
            field_name="abv"
        )

        assert len(history) == 3
        # Should be ordered by confidence descending
        assert float(history[0].confidence) >= float(history[1].confidence)
