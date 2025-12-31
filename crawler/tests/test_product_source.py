"""
Tests for ProductSource Junction Record Creation.

RECT-005: Create ProductSource Junction Records

These tests verify that when content is processed and a DiscoveredProduct
is created/updated, the corresponding ProductSource junction records are
created to track the relationship between products and their crawled sources.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from django.db import IntegrityError
from django.utils import timezone

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlerSource,
    SourceCategory,
    CrawledSource,
    CrawledSourceTypeChoices,
    ProductSource,
    DiscoverySourceConfig,
    DiscoverySourceTypeChoices,
    CrawlFrequencyChoices,
    ExtractionStatusChoices,
)
from crawler.services.content_processor import (
    ContentProcessor,
    ProcessingResult,
    extract_individual_fields,
    get_extracted_field_names,
    create_product_source,
)
from crawler.services.ai_client import EnhancementResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for DiscoveredProduct."""
    return CrawlerSource.objects.create(
        name="Test ProductSource Source",
        slug="test-productsource-source",
        base_url="https://productsource-test.com",
        category=SourceCategory.REVIEW,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_discovery_config(db):
    """Create a sample DiscoverySourceConfig for CrawledSource."""
    return DiscoverySourceConfig.objects.create(
        name="Test ProductSource Discovery Config",
        base_url="https://ps-discovery-test.com",
        source_type=DiscoverySourceTypeChoices.REVIEW_BLOG,
        crawl_priority=5,
        crawl_frequency=CrawlFrequencyChoices.WEEKLY,
        reliability_score=7,
    )


@pytest.fixture
def sample_crawled_source(db, sample_discovery_config):
    """Create a sample CrawledSource for testing ProductSource creation."""
    return CrawledSource.objects.create(
        url="https://productsource-test.com/articles/whiskey-review",
        title="Test Whiskey Review Article",
        content_hash="ps_article_hash_123456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        extraction_status=ExtractionStatusChoices.PENDING,
        raw_content="<html>Article content about whiskey</html>",
    )


@pytest.fixture
def second_crawled_source(db, sample_discovery_config):
    """Create a second CrawledSource for testing unique constraint."""
    return CrawledSource.objects.create(
        url="https://productsource-test.com/articles/another-review",
        title="Another Whiskey Review Article",
        content_hash="ps_article_hash_223456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        extraction_status=ExtractionStatusChoices.PENDING,
        raw_content="<html>Another article content</html>",
    )


@pytest.fixture
def sample_product(db, sample_crawler_source):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_crawler_source,
        source_url="https://productsource-test.com/product/test",
        fingerprint="productsource-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test product content</html>",
        raw_content_hash="productsourcetest123hash",
        extracted_data={"name": "ProductSource Test Whiskey"},
        name="ProductSource Test Whiskey",
        abv=43.0,
        mention_count=0,
    )


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client for ContentProcessor tests."""
    client = MagicMock()
    client.enhance_from_crawler = AsyncMock(
        return_value=EnhancementResult(
            success=True,
            product_type="whiskey",
            confidence=0.92,
            extracted_data={
                "name": "Glenfiddich 18 Year Old",
                "abv": "43.0",
                "age_statement": "18",
                "region": "Speyside",
                "country": "Scotland",
                "nose_description": "Rich oak with hints of dried fruit",
                "color_description": "Deep amber",
            },
            enrichment={"category": "single_malt"},
            error=None,
        )
    )
    return client


# =============================================================================
# Test Class: ProductSource Created on Extraction
# =============================================================================

class TestProductSourceCreatedOnExtraction:
    """Tests for ProductSource record creation during content processing."""

    def test_product_source_created_on_extraction(
        self, db, sample_product, sample_crawled_source
    ):
        """ProductSource record created linking product to crawled source."""
        # Manually create ProductSource to verify the pattern
        product_source = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.92"),
            fields_extracted=["name", "abv", "region"],
        )

        assert product_source.id is not None
        assert product_source.product == sample_product
        assert product_source.source == sample_crawled_source
        assert product_source.extracted_at is not None

    def test_extraction_confidence_stored(
        self, db, sample_product, sample_crawled_source
    ):
        """AI confidence score stored in ProductSource."""
        confidence = Decimal("0.85")
        product_source = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=confidence,
            fields_extracted=["name"],
        )

        product_source.refresh_from_db()
        assert product_source.extraction_confidence == confidence

    def test_fields_extracted_tracked(
        self, db, sample_product, sample_crawled_source
    ):
        """List of field names extracted stored in JSONField."""
        fields = ["name", "abv", "age_statement", "region", "nose_description"]
        product_source = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.90"),
            fields_extracted=fields,
        )

        product_source.refresh_from_db()
        assert product_source.fields_extracted == fields

    def test_extracted_at_timestamp(
        self, db, sample_product, sample_crawled_source
    ):
        """Extraction timestamp recorded."""
        before = timezone.now()
        product_source = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.88"),
            fields_extracted=["name"],
        )
        after = timezone.now()

        assert product_source.extracted_at is not None
        assert before <= product_source.extracted_at <= after

    def test_unique_constraint_enforced(
        self, db, sample_product, sample_crawled_source
    ):
        """Same product+source combination only creates one record."""
        # Create first ProductSource
        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )

        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            ProductSource.objects.create(
                product=sample_product,
                source=sample_crawled_source,
                extraction_confidence=Decimal("0.90"),
                fields_extracted=["name", "abv"],
            )

    def test_mention_count_updated(
        self, db, sample_product, sample_crawled_source
    ):
        """DiscoveredProduct.mention_count incremented."""
        assert sample_product.mention_count == 0

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.88"),
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1


# =============================================================================
# Test Class: ProductSource Helper Functions (Unit Tests)
# =============================================================================

class TestProductSourceHelperFunctions:
    """Unit tests for ProductSource helper functions."""

    def test_get_extracted_field_names_with_values(self):
        """get_extracted_field_names returns fields with non-null values."""
        extracted_data = {
            "name": "Glenfiddich 18",
            "abv": "43.0",
            "age_statement": "18",
            "region": "Speyside",
            "country": None,  # Null
            "nose_description": "",  # Empty string
        }

        fields = get_extracted_field_names(extracted_data)

        assert "name" in fields
        assert "abv" in fields
        assert "age_statement" in fields
        assert "region" in fields
        assert "country" not in fields  # Null excluded
        assert "nose_description" not in fields  # Empty excluded

    def test_get_extracted_field_names_with_lists(self):
        """get_extracted_field_names only includes non-empty lists."""
        extracted_data = {
            "name": "Test Whiskey",
            "primary_aromas": ["oak", "honey"],  # Non-empty list
            "secondary_aromas": [],  # Empty list
            "palate_flavors": None,  # Null list
        }

        fields = get_extracted_field_names(extracted_data)

        assert "name" in fields
        assert "primary_aromas" in fields  # Non-empty list included
        assert "secondary_aromas" not in fields  # Empty list excluded
        assert "palate_flavors" not in fields  # Null excluded

    def test_create_product_source_creates_record(
        self, db, sample_product, sample_crawled_source
    ):
        """create_product_source creates a new ProductSource record."""
        extracted_data = {
            "name": "Test Whiskey",
            "abv": "43.0",
            "region": "Speyside",
        }

        product_source = create_product_source(
            product=sample_product,
            crawled_source=sample_crawled_source,
            extraction_confidence=0.85,
            extracted_data=extracted_data,
        )

        assert product_source is not None
        assert product_source.product == sample_product
        assert product_source.source == sample_crawled_source
        assert product_source.extraction_confidence == Decimal("0.85")
        assert "name" in product_source.fields_extracted
        assert "abv" in product_source.fields_extracted
        assert "region" in product_source.fields_extracted

    def test_create_product_source_handles_existing(
        self, db, sample_product, sample_crawled_source
    ):
        """create_product_source updates existing record instead of duplicating."""
        # Create initial ProductSource
        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.80"),
            fields_extracted=["name"],
        )

        # Try to create again with different data
        extracted_data = {
            "name": "Test Whiskey",
            "abv": "43.0",
        }

        product_source = create_product_source(
            product=sample_product,
            crawled_source=sample_crawled_source,
            extraction_confidence=0.90,
            extracted_data=extracted_data,
        )

        # Should update existing, not create new
        assert product_source is not None
        assert ProductSource.objects.filter(
            product=sample_product,
            source=sample_crawled_source,
        ).count() == 1

        # Should have merged fields and higher confidence
        assert product_source.extraction_confidence == Decimal("0.90")
        assert "name" in product_source.fields_extracted
        assert "abv" in product_source.fields_extracted

    def test_create_product_source_returns_none_without_crawled_source(
        self, db, sample_product
    ):
        """create_product_source returns None when crawled_source is None."""
        result = create_product_source(
            product=sample_product,
            crawled_source=None,
            extraction_confidence=0.85,
            extracted_data={"name": "Test"},
        )

        assert result is None


# =============================================================================
# Test Class: ProductSource M2M Relationship Queries
# =============================================================================

class TestProductSourceM2MQueries:
    """Tests for querying ProductSource M2M relationships."""

    def test_query_product_sources_from_product(
        self, db, sample_product, sample_crawled_source, second_crawled_source
    ):
        """Can query all sources for a product via product.product_sources."""
        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )
        ProductSource.objects.create(
            product=sample_product,
            source=second_crawled_source,
            extraction_confidence=Decimal("0.90"),
            fields_extracted=["abv"],
        )

        # Query from product side
        sources = sample_product.product_sources.all()
        assert sources.count() == 2

    def test_query_products_from_crawled_source(
        self, db, sample_product, sample_crawler_source, sample_crawled_source
    ):
        """Can query all products from a source via source.products."""
        # Create second product
        product2 = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url="https://productsource-test.com/product/test2",
            fingerprint="productsource-test-fingerprint-002",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test product 2</html>",
            raw_content_hash="productsourcetest456hash",
            extracted_data={"name": "Another Test Whiskey"},
            name="Another Test Whiskey",
        )

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )
        ProductSource.objects.create(
            product=product2,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.88"),
            fields_extracted=["name"],
        )

        # Query from crawled source side
        products = sample_crawled_source.products.all()
        assert products.count() == 2

    def test_filter_product_sources_by_confidence(
        self, db, sample_product, sample_crawled_source, second_crawled_source
    ):
        """Can filter ProductSource records by extraction confidence."""
        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.60"),
            fields_extracted=["name"],
        )
        ProductSource.objects.create(
            product=sample_product,
            source=second_crawled_source,
            extraction_confidence=Decimal("0.95"),
            fields_extracted=["name", "abv"],
        )

        # Filter high confidence sources
        high_confidence = sample_product.product_sources.filter(
            extraction_confidence__gte=Decimal("0.80")
        )
        assert high_confidence.count() == 1
        assert high_confidence.first().source == second_crawled_source


# =============================================================================
# Test Class: Signal Handlers for mention_count
# =============================================================================

class TestProductSourceSignals:
    """Tests for Django signals updating mention_count on ProductSource changes."""

    def test_mention_count_incremented_on_create(
        self, db, sample_product, sample_crawled_source
    ):
        """mention_count should increment when ProductSource is created."""
        assert sample_product.mention_count == 0

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

    def test_mention_count_decremented_on_delete(
        self, db, sample_product, sample_crawled_source
    ):
        """mention_count should decrement when ProductSource is deleted."""
        ps = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

        ps.delete()

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 0

    def test_mention_count_with_multiple_sources(
        self, db, sample_product, sample_crawled_source, second_crawled_source
    ):
        """mention_count should correctly track multiple sources."""
        assert sample_product.mention_count == 0

        ps1 = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

        ps2 = ProductSource.objects.create(
            product=sample_product,
            source=second_crawled_source,
            extraction_confidence=Decimal("0.90"),
            fields_extracted=["abv"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 2

        ps1.delete()

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1
