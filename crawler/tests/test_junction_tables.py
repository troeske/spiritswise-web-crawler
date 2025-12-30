"""
Tests for Junction Tables (ProductSource, BrandSource).

Task Group 7: Junction Tables Implementation
These tests verify the ProductSource and BrandSource many-to-many junction tables
that link DiscoveredProduct/DiscoveredBrand to CrawledSource with extraction
metadata (confidence, fields extracted).

TDD: Tests written first before model implementation.
"""

import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.utils import timezone

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
        name="Test Junction Source",
        slug="test-junction-source",
        base_url="https://junction-test.com",
        category=SourceCategory.REVIEW,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_discovery_config(db):
    """Create a sample DiscoverySourceConfig for CrawledSource."""
    return DiscoverySourceConfig.objects.create(
        name="Test Discovery Config",
        base_url="https://discovery-test.com",
        source_type=DiscoverySourceTypeChoices.REVIEW_BLOG,
        crawl_priority=5,
        crawl_frequency=CrawlFrequencyChoices.WEEKLY,
        reliability_score=7,
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for testing."""
    return DiscoveredBrand.objects.create(
        name="Junction Test Brand",
        country="Scotland",
        region="Speyside",
    )


@pytest.fixture
def sample_product(db, sample_crawler_source, sample_brand):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_crawler_source,
        source_url="https://junction-test.com/product/test",
        fingerprint="junction-table-test-fingerprint",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test junction product content</html>",
        raw_content_hash="junctiontest123hash",
        extracted_data={"name": "Junction Test Whiskey"},
        name="Junction Test Whiskey",
        brand=sample_brand,
        abv=Decimal("43.0"),
    )


@pytest.fixture
def sample_crawled_source(db, sample_discovery_config):
    """Create a sample CrawledSource for testing junction tables."""
    return CrawledSource.objects.create(
        url="https://junction-test.com/articles/whiskey-review",
        title="Test Whiskey Review Article",
        content_hash="junctionarticlehash123456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        raw_content="<html>Article content about whiskey</html>",
    )


@pytest.fixture
def second_crawled_source(db, sample_discovery_config):
    """Create a second CrawledSource for testing multiple sources."""
    return CrawledSource.objects.create(
        url="https://junction-test.com/articles/another-review",
        title="Another Whiskey Review",
        content_hash="junctionarticlehash223456789012345678901234567890123456",
        discovery_source=sample_discovery_config,
        source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
        raw_content="<html>Another article content</html>",
    )


class TestProductSourceCreation:
    """Tests for ProductSource junction model creation and M2M relationship."""

    def test_product_source_creation_with_required_fields(
        self, sample_product, sample_crawled_source
    ):
        """ProductSource should be created with required fields and FKs."""
        from crawler.models import ProductSource

        product_source = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name", "abv", "region"],
        )

        assert product_source.id is not None
        assert product_source.product == sample_product
        assert product_source.source == sample_crawled_source
        assert product_source.extraction_confidence == 0.85
        assert product_source.fields_extracted == ["name", "abv", "region"]
        assert product_source.extracted_at is not None

    def test_product_source_accessible_via_product_sources_related_name(
        self, sample_product, sample_crawled_source
    ):
        """ProductSource should be accessible via product.product_sources."""
        from crawler.models import ProductSource

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.90,
            fields_extracted=["name"],
        )

        # Using product_sources since 'sources' is already used by legacy field
        assert sample_product.product_sources.count() == 1
        assert sample_product.product_sources.first().source == sample_crawled_source

    def test_product_source_accessible_via_crawled_source_products(
        self, sample_product, sample_crawled_source
    ):
        """ProductSource should be accessible via crawled_source.products."""
        from crawler.models import ProductSource

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.88,
            fields_extracted=["name", "abv"],
        )

        # Access from CrawledSource side
        assert sample_crawled_source.products.count() == 1
        assert sample_crawled_source.products.first().product == sample_product

    def test_product_source_unique_constraint(
        self, sample_product, sample_crawled_source
    ):
        """Unique constraint should prevent duplicate (product, source) pairs."""
        from crawler.models import ProductSource

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name"],
        )

        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            ProductSource.objects.create(
                product=sample_product,
                source=sample_crawled_source,
                extraction_confidence=0.90,
                fields_extracted=["name", "abv"],
            )

    def test_product_source_confidence_validation(
        self, sample_product, sample_crawled_source
    ):
        """Extraction confidence should be validated between 0 and 1."""
        from crawler.models import ProductSource
        from django.core.exceptions import ValidationError

        # Valid confidence values should work
        ps = ProductSource(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.0,
            fields_extracted=[],
        )
        ps.full_clean()  # Should not raise

        ps.extraction_confidence = 1.0
        ps.full_clean()  # Should not raise

        # Invalid confidence values should raise ValidationError
        ps.extraction_confidence = 1.5
        with pytest.raises(ValidationError):
            ps.full_clean()

        ps.extraction_confidence = -0.1
        with pytest.raises(ValidationError):
            ps.full_clean()

    def test_product_from_multiple_sources(
        self, sample_product, sample_crawled_source, second_crawled_source
    ):
        """A product can be linked to multiple CrawledSources."""
        from crawler.models import ProductSource

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name", "abv"],
        )

        ProductSource.objects.create(
            product=sample_product,
            source=second_crawled_source,
            extraction_confidence=0.90,
            fields_extracted=["region", "maturation_notes"],
        )

        assert sample_product.product_sources.count() == 2


class TestBrandSourceCreation:
    """Tests for BrandSource junction model creation and M2M relationship."""

    def test_brand_source_creation_with_required_fields(
        self, sample_brand, sample_crawled_source
    ):
        """BrandSource should be created with required fields and FKs."""
        from crawler.models import BrandSource

        brand_source = BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.92,
        )

        assert brand_source.id is not None
        assert brand_source.brand == sample_brand
        assert brand_source.source == sample_crawled_source
        assert brand_source.extraction_confidence == 0.92
        assert brand_source.extracted_at is not None

    def test_brand_source_accessible_via_brand_sources_related_name(
        self, sample_brand, sample_crawled_source
    ):
        """BrandSource should be accessible via brand.sources."""
        from crawler.models import BrandSource

        BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.88,
        )

        assert sample_brand.sources.count() == 1
        assert sample_brand.sources.first().source == sample_crawled_source

    def test_brand_source_accessible_via_crawled_source_brands(
        self, sample_brand, sample_crawled_source
    ):
        """BrandSource should be accessible via crawled_source.brands."""
        from crawler.models import BrandSource

        BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.75,
        )

        # Access from CrawledSource side
        assert sample_crawled_source.brands.count() == 1
        assert sample_crawled_source.brands.first().brand == sample_brand

    def test_brand_source_unique_constraint(
        self, sample_brand, sample_crawled_source
    ):
        """Unique constraint should prevent duplicate (brand, source) pairs."""
        from crawler.models import BrandSource

        BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.85,
        )

        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            BrandSource.objects.create(
                brand=sample_brand,
                source=sample_crawled_source,
                extraction_confidence=0.90,
            )


class TestMentionCountSignals:
    """Tests for Django signals updating mention_count on ProductSource/BrandSource changes."""

    def test_product_mention_count_updated_on_product_source_create(
        self, sample_product, sample_crawled_source
    ):
        """DiscoveredProduct.mention_count should update when ProductSource is created."""
        from crawler.models import ProductSource

        assert sample_product.mention_count == 0

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

    def test_product_mention_count_updated_on_product_source_delete(
        self, sample_product, sample_crawled_source
    ):
        """DiscoveredProduct.mention_count should update when ProductSource is deleted."""
        from crawler.models import ProductSource

        ps = ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

        ps.delete()

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 0

    def test_brand_mention_count_updated_on_brand_source_create(
        self, sample_brand, sample_crawled_source
    ):
        """DiscoveredBrand.mention_count should update when BrandSource is created."""
        from crawler.models import BrandSource

        assert sample_brand.mention_count == 0

        BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.90,
        )

        sample_brand.refresh_from_db()
        assert sample_brand.mention_count == 1

    def test_brand_mention_count_updated_on_brand_source_delete(
        self, sample_brand, sample_crawled_source
    ):
        """DiscoveredBrand.mention_count should update when BrandSource is deleted."""
        from crawler.models import BrandSource

        bs = BrandSource.objects.create(
            brand=sample_brand,
            source=sample_crawled_source,
            extraction_confidence=0.90,
        )

        sample_brand.refresh_from_db()
        assert sample_brand.mention_count == 1

        bs.delete()

        sample_brand.refresh_from_db()
        assert sample_brand.mention_count == 0

    def test_multiple_sources_increment_mention_count(
        self, sample_product, sample_crawled_source, second_crawled_source
    ):
        """Multiple ProductSource entries should correctly increment mention_count."""
        from crawler.models import ProductSource

        assert sample_product.mention_count == 0

        ProductSource.objects.create(
            product=sample_product,
            source=sample_crawled_source,
            extraction_confidence=0.85,
            fields_extracted=["name"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 1

        ProductSource.objects.create(
            product=sample_product,
            source=second_crawled_source,
            extraction_confidence=0.90,
            fields_extracted=["abv"],
        )

        sample_product.refresh_from_db()
        assert sample_product.mention_count == 2
