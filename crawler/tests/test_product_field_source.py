"""
Tests for ProductFieldSource per-field provenance tracking.

Task Group 8: Per-Field Provenance Tracking
These tests verify the ProductFieldSource model that tracks which source
contributed each field value to a DiscoveredProduct, enabling detailed
provenance tracking and conflict detection.

TDD: Tests written first before model implementation.
"""

import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from crawler.models import (
    DiscoveredProduct,
    DiscoveredBrand,
    CrawledSource,
    CrawledSourceTypeChoices,
    DiscoverySourceConfig,
    DiscoverySourceTypeChoices,
    CrawlFrequencyChoices,
    ProductType,
    CrawlerSource,
    SourceCategory,
)


@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for DiscoveredProduct."""
    return CrawlerSource.objects.create(
        name="Test Field Source",
        slug="test-field-source",
        base_url="https://field-test.com",
        category=SourceCategory.REVIEW,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_discovery_config(db):
    """Create a sample DiscoverySourceConfig for CrawledSource."""
    return DiscoverySourceConfig.objects.create(
        name="Test Field Discovery Config",
        base_url="https://field-discovery-test.com",
        source_type=DiscoverySourceTypeChoices.REVIEW_BLOG,
        crawl_priority=5,
        crawl_frequency=CrawlFrequencyChoices.WEEKLY,
        reliability_score=7,
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for testing."""
    return DiscoveredBrand.objects.create(
        name="Field Test Brand",
        country="Scotland",
        region="Speyside",
    )


@pytest.fixture
def sample_product(db, sample_crawler_source, sample_brand):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_crawler_source,
        source_url="https://field-test.com/product/test",
        fingerprint="field-source-test-fingerprint",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test field source product content</html>",
        raw_content_hash="fieldsourcetest123hash",
        extracted_data={"name": "Field Test Whiskey"},
        name="Field Test Whiskey",
        brand=sample_brand,
        abv=Decimal("43.0"),
        region="Speyside",
    )


@pytest.fixture
def sample_crawled_source(db, sample_discovery_config):
    """Create a sample CrawledSource for testing field provenance."""
    return CrawledSource.objects.create(
        url="https://field-test.com/articles/whiskey-review-1",
        title="Test Whiskey Review Article",
        content_hash="fieldarticlehash123456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        raw_content="<html>Article content about whiskey</html>",
    )


@pytest.fixture
def second_crawled_source(db, sample_discovery_config):
    """Create a second CrawledSource for testing multiple sources per field."""
    return CrawledSource.objects.create(
        url="https://field-test.com/articles/whiskey-review-2",
        title="Another Whiskey Review",
        content_hash="fieldarticlehash223456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        raw_content="<html>Another article content</html>",
    )


class TestProductFieldSourceCreation:
    """Tests for ProductFieldSource model creation and field storage."""

    def test_field_provenance_creation_with_required_fields(
        self, sample_product, sample_crawled_source
    ):
        """ProductFieldSource should be created with required fields and FKs."""
        from crawler.models import ProductFieldSource

        field_source = ProductFieldSource.objects.create(
            product=sample_product,
            field_name="abv",
            source=sample_crawled_source,
            confidence=0.92,
            extracted_value="43.0",
        )

        assert field_source.id is not None
        assert field_source.product == sample_product
        assert field_source.field_name == "abv"
        assert field_source.source == sample_crawled_source
        assert field_source.confidence == 0.92
        assert field_source.extracted_value == "43.0"
        assert field_source.extracted_at is not None

    def test_unique_constraint_on_product_field_source(
        self, sample_product, sample_crawled_source
    ):
        """Unique constraint should prevent duplicate (product, field_name, source) tuples."""
        from crawler.models import ProductFieldSource

        # Create first field source entry
        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="region",
            source=sample_crawled_source,
            confidence=0.85,
            extracted_value="Speyside",
        )

        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            ProductFieldSource.objects.create(
                product=sample_product,
                field_name="region",
                source=sample_crawled_source,
                confidence=0.90,
                extracted_value="Highland",  # Different value, same (product, field, source)
            )

    def test_confidence_score_storage_and_validation(
        self, sample_product, sample_crawled_source
    ):
        """Confidence scores should be validated between 0 and 1."""
        from crawler.models import ProductFieldSource

        # Valid confidence values should work
        pfs = ProductFieldSource(
            product=sample_product,
            field_name="age_statement",
            source=sample_crawled_source,
            confidence=0.0,
            extracted_value="12",
        )
        pfs.full_clean()  # Should not raise

        pfs.confidence = 1.0
        pfs.full_clean()  # Should not raise

        pfs.confidence = 0.5
        pfs.full_clean()  # Should not raise

        # Invalid confidence values should raise ValidationError
        pfs.confidence = 1.5
        with pytest.raises(ValidationError):
            pfs.full_clean()

        pfs.confidence = -0.1
        with pytest.raises(ValidationError):
            pfs.full_clean()

    def test_extracted_value_storage_for_various_field_types(
        self, sample_product, sample_crawled_source
    ):
        """Extracted value should store string representation of various field types."""
        from crawler.models import ProductFieldSource

        # Test storing a JSON array value (like primary_aromas)
        aromas_source = ProductFieldSource.objects.create(
            product=sample_product,
            field_name="primary_aromas",
            source=sample_crawled_source,
            confidence=0.88,
            extracted_value='["vanilla", "honey", "dried fruit"]',
        )
        assert aromas_source.extracted_value == '["vanilla", "honey", "dried fruit"]'

        # Test storing a numeric value (like flavor_intensity)
        intensity_source = ProductFieldSource.objects.create(
            product=sample_product,
            field_name="flavor_intensity",
            source=sample_crawled_source,
            confidence=0.75,
            extracted_value="8",
        )
        assert intensity_source.extracted_value == "8"

        # Test storing a longer text value (like maturation_notes)
        notes_source = ProductFieldSource.objects.create(
            product=sample_product,
            field_name="maturation_notes",
            source=sample_crawled_source,
            confidence=0.82,
            extracted_value="Aged in ex-bourbon casks with a sherry finish for 2 years",
        )
        assert "ex-bourbon" in notes_source.extracted_value


class TestProductFieldSourceRelationships:
    """Tests for ProductFieldSource relationships and related names."""

    def test_field_sources_accessible_via_product_related_name(
        self, sample_product, sample_crawled_source
    ):
        """ProductFieldSource should be accessible via product.field_sources."""
        from crawler.models import ProductFieldSource

        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="abv",
            source=sample_crawled_source,
            confidence=0.90,
            extracted_value="43.0",
        )

        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="region",
            source=sample_crawled_source,
            confidence=0.85,
            extracted_value="Speyside",
        )

        assert sample_product.field_sources.count() == 2
        field_names = list(sample_product.field_sources.values_list("field_name", flat=True))
        assert "abv" in field_names
        assert "region" in field_names

    def test_field_extractions_accessible_via_crawled_source_related_name(
        self, sample_product, sample_crawled_source
    ):
        """ProductFieldSource should be accessible via crawled_source.field_extractions."""
        from crawler.models import ProductFieldSource

        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="name",
            source=sample_crawled_source,
            confidence=0.95,
            extracted_value="Field Test Whiskey",
        )

        assert sample_crawled_source.field_extractions.count() == 1
        assert sample_crawled_source.field_extractions.first().field_name == "name"

    def test_same_field_from_multiple_sources(
        self, sample_product, sample_crawled_source, second_crawled_source
    ):
        """Same field can have values from multiple sources with different confidences."""
        from crawler.models import ProductFieldSource

        # Same field from first source
        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="abv",
            source=sample_crawled_source,
            confidence=0.85,
            extracted_value="43.0",
        )

        # Same field from second source
        ProductFieldSource.objects.create(
            product=sample_product,
            field_name="abv",
            source=second_crawled_source,
            confidence=0.92,
            extracted_value="43.0",
        )

        # Verify we can query all sources for a field
        abv_sources = sample_product.field_sources.filter(field_name="abv")
        assert abv_sources.count() == 2

        # Verify we can order by confidence to find most trusted source
        highest_confidence = abv_sources.order_by("-confidence").first()
        assert highest_confidence.source == second_crawled_source
        assert highest_confidence.confidence == 0.92
