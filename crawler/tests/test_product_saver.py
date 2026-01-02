"""
Tests for Unified Product Saver Module.

UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 1: TDD Test File

This test file defines the expected behavior of the save_discovered_product()
function that will be the SINGLE entry point for creating/updating
DiscoveredProduct records across all discovery flows.

TDD Approach: These tests are written FIRST before implementation.
All tests should FAIL initially until product_saver.py is implemented.

Test Categories:
1. TestProductSaveResult - Tests for the result dataclass
2. TestSaveDiscoveredProductCore - Core save functionality (12 tests)
3. TestDeduplication - Fingerprint/name matching (4 tests)
4. TestDataNormalization - Normalizing different source formats (3 tests)
5. TestFieldExtraction - Extracting and converting fields (5 tests)
"""

import pytest
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlerSource,
    CrawledSource,
    CrawlJob,
    SourceCategory,
    WhiskeyDetails,
    PortWineDetails,
    ProductAward,
    ProductRating,
    ProductImage,
    ProductSource,
    ProductFieldSource,
    DiscoveredBrand,
    MedalChoices,
    ImageTypeChoices,
    CrawledSourceTypeChoices,
    ExtractionStatusChoices,
    DiscoverySourceConfig,
    SourceTypeChoices,
    CrawlFrequencyChoices,
    CrawlStrategyChoices,
)

# Import the module under test - This will fail until implementation exists
from crawler.services.product_saver import (
    ProductSaveResult,
    save_discovered_product,
    normalize_extracted_data,
    extract_core_fields,
    extract_tasting_fields,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Product Saver Source",
        slug="test-product-saver-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_discovery_source_config(db):
    """Create a sample DiscoverySourceConfig for testing."""
    return DiscoverySourceConfig.objects.create(
        name="Test Discovery Source",
        base_url="https://awards.example.com",
        source_type=SourceTypeChoices.AWARD_COMPETITION,
        crawl_frequency=CrawlFrequencyChoices.WEEKLY,
        crawl_strategy=CrawlStrategyChoices.SIMPLE,
        crawl_priority=5,  # Required field
        reliability_score=8,  # Required field
    )


@pytest.fixture
def sample_crawled_source(db, sample_discovery_source_config):
    """Create a sample CrawledSource for testing."""
    return CrawledSource.objects.create(
        url="https://example.com/products/test-whiskey",
        title="Test Whiskey Product Page",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        extraction_status=ExtractionStatusChoices.PENDING,
        discovery_source=sample_discovery_source_config,
    )


@pytest.fixture
def sample_crawl_job(db, sample_crawler_source):
    """Create a sample CrawlJob for testing."""
    return CrawlJob.objects.create(
        source=sample_crawler_source,
    )


@pytest.fixture
def sample_whiskey_data():
    """Sample extracted data for a whiskey product."""
    return {
        "name": "Glenfiddich 18 Year Old",
        "brand": "Glenfiddich",
        "abv": "43.0",
        "age_statement": "18",
        "volume_ml": "700",
        "region": "Speyside",
        "country": "Scotland",
        "gtin": "5010327325125",
        "bottler": None,
        # Tasting profile - Appearance
        "color_description": "Deep amber with golden highlights",
        "color_intensity": "7",
        "clarity": "brilliant",
        "viscosity": "medium",
        # Tasting profile - Nose
        "nose_description": "Rich oak with hints of dried fruit and honey",
        "primary_aromas": ["oak", "honey", "dried fruit"],
        "primary_intensity": "8",
        "secondary_aromas": ["vanilla", "almond"],
        "aroma_evolution": "Opens with honey, evolves to oak",
        # Tasting profile - Palate
        "palate_flavors": ["toffee", "cinnamon", "dark chocolate"],
        "initial_taste": "Sweet honey and toffee",
        "mid_palate_evolution": "Develops spice notes",
        "flavor_intensity": "7",
        "complexity": "8",
        "mouthfeel": "creamy",
        # Tasting profile - Finish
        "finish_length": "8",
        "warmth": "6",
        "dryness": "4",
        "finish_flavors": ["oak", "spice", "tobacco"],
        "finish_evolution": "Lingering oak with subtle smoke",
        "final_notes": "Long, elegant finish with dried fruit",
        # Whiskey-specific
        "whiskey_type": "scotch_single_malt",
        "distillery": "Glenfiddich Distillery",
        "cask_type": "ex-bourbon",
        "cask_finish": "sherry",
        # Awards
        "awards": [
            {
                "competition": "IWSC",
                "year": 2024,
                "medal": "gold",
                "category": "Single Malt Scotch",
            }
        ],
        # Ratings
        "ratings": [
            {
                "source": "Whisky Advocate",
                "score": 92,
                "max_score": 100,
                "reviewer": "John Reviewer",
            }
        ],
        # Images
        "images": [
            {
                "url": "https://example.com/images/glenfiddich18.jpg",
                "type": "bottle",
                "source": "Official Website",
            }
        ],
    }


@pytest.fixture
def sample_port_wine_data():
    """Sample extracted data for a port wine product."""
    return {
        "name": "Taylor's 20 Year Old Tawny",
        "brand": "Taylor's",
        "abv": "20.0",
        "volume_ml": "750",
        "region": "Douro",
        "country": "Portugal",
        # Tasting profile
        "color_description": "Rich amber with mahogany rim",
        "nose_description": "Dried fruits, nuts, and caramel",
        "palate_flavors": ["walnut", "fig", "honey"],
        "finish_length": "9",
        # Port-specific
        "style": "tawny",
        "indication_age": "20 Year",
        "producer_house": "Taylor's",
    }


@pytest.fixture
def sample_competition_data():
    """Sample data from competition/award flow (uses product_name/producer)."""
    return {
        "product_name": "Lagavulin 16 Year Old",
        "producer": "Lagavulin Distillery",
        "abv": "43",
        "age_statement": "16",
        "region": "Islay",
        "country": "Scotland",
        "medal": "Gold",
        "competition": "IWSC",
        "year": 2024,
        "category": "Single Malt Scotch - Islay",
    }


# =============================================================================
# 1. TestProductSaveResult - Tests for the result dataclass
# =============================================================================


class TestProductSaveResult(TestCase):
    """Tests for the ProductSaveResult dataclass."""

    def test_dataclass_has_all_fields(self):
        """ProductSaveResult should have all required fields."""
        # Verify the dataclass has all expected fields
        expected_fields = [
            "product",
            "created",
            "whiskey_details_created",
            "port_wine_details_created",
            "awards_created",
            "ratings_created",
            "images_created",
            "source_record_created",
            "provenance_records_created",
            "brand_created",
            "brand",
        ]

        for field in expected_fields:
            assert hasattr(ProductSaveResult, "__dataclass_fields__"), \
                "ProductSaveResult should be a dataclass"
            assert field in ProductSaveResult.__dataclass_fields__, \
                f"ProductSaveResult missing field: {field}"

    def test_default_values(self):
        """ProductSaveResult should have sensible default values."""
        # Create a minimal result with just required fields
        mock_product = MagicMock(spec=DiscoveredProduct)

        result = ProductSaveResult(product=mock_product)

        # Verify defaults
        assert result.product == mock_product
        assert result.created is False
        assert result.whiskey_details_created is False
        assert result.port_wine_details_created is False
        assert result.awards_created == 0
        assert result.ratings_created == 0
        assert result.images_created == 0
        assert result.source_record_created is False
        assert result.provenance_records_created == 0
        assert result.brand_created is False
        assert result.brand is None

    def test_can_instantiate_with_product(self):
        """ProductSaveResult can be instantiated with full data."""
        mock_product = MagicMock(spec=DiscoveredProduct)
        mock_brand = MagicMock(spec=DiscoveredBrand)

        result = ProductSaveResult(
            product=mock_product,
            created=True,
            whiskey_details_created=True,
            port_wine_details_created=False,
            awards_created=3,
            ratings_created=2,
            images_created=1,
            source_record_created=True,
            provenance_records_created=15,
            brand_created=True,
            brand=mock_brand,
        )

        assert result.product == mock_product
        assert result.created is True
        assert result.whiskey_details_created is True
        assert result.port_wine_details_created is False
        assert result.awards_created == 3
        assert result.ratings_created == 2
        assert result.images_created == 1
        assert result.source_record_created is True
        assert result.provenance_records_created == 15
        assert result.brand_created is True
        assert result.brand == mock_brand


# =============================================================================
# 2. TestSaveDiscoveredProductCore - Core save functionality (12 tests)
# =============================================================================


@pytest.mark.django_db
class TestSaveDiscoveredProductCore:
    """Tests for core save_discovered_product() functionality."""

    def test_creates_product_with_name(self, sample_crawler_source, sample_whiskey_data):
        """save_discovered_product creates a product with correct name."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.product is not None
        assert result.product.name == "Glenfiddich 18 Year Old"
        assert result.created is True

    def test_creates_product_with_individual_columns(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """Product created with individual columns (abv, age, volume, region, country)."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        product = result.product
        product.refresh_from_db()

        # Core fields should be populated in individual columns
        assert product.abv == 43.0
        assert product.age_statement == 18
        assert product.volume_ml == 700
        assert product.region == "Speyside"
        assert product.country == "Scotland"
        assert product.gtin == "5010327325125"

    def test_creates_product_with_tasting_profile_columns(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """Product created with tasting profile individual columns."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        product = result.product
        product.refresh_from_db()

        # Appearance
        assert product.color_description == "Deep amber with golden highlights"
        assert product.color_intensity == 7
        assert product.clarity == "brilliant"
        assert product.viscosity == "medium"

        # Nose
        assert product.nose_description == "Rich oak with hints of dried fruit and honey"
        assert product.primary_aromas == ["oak", "honey", "dried fruit"]
        assert product.primary_intensity == 8
        assert product.secondary_aromas == ["vanilla", "almond"]
        assert product.aroma_evolution == "Opens with honey, evolves to oak"

        # Palate
        assert product.palate_flavors == ["toffee", "cinnamon", "dark chocolate"]
        assert product.initial_taste == "Sweet honey and toffee"
        assert product.mid_palate_evolution == "Develops spice notes"
        assert product.flavor_intensity == 7
        assert product.complexity == 8
        assert product.mouthfeel == "creamy"

        # Finish
        assert product.finish_length == 8
        assert product.warmth == 6
        assert product.dryness == 4
        assert product.finish_flavors == ["oak", "spice", "tobacco"]
        assert product.finish_evolution == "Lingering oak with subtle smoke"
        assert product.final_notes == "Long, elegant finish with dried fruit"

    def test_creates_whiskey_details_for_whiskey(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """WhiskeyDetails record created when product_type='whiskey'."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.whiskey_details_created is True
        assert result.port_wine_details_created is False

        # Verify WhiskeyDetails record exists
        product = result.product
        assert hasattr(product, "whiskey_details")
        details = product.whiskey_details

        assert details.whiskey_type == "scotch_single_malt"
        assert details.whiskey_country == "Scotland"
        assert details.whiskey_region == "Speyside"
        assert details.distillery == "Glenfiddich Distillery"
        assert details.cask_type == "ex-bourbon"
        assert details.cask_finish == "sherry"

    def test_creates_port_wine_details_for_port_wine(
        self, sample_crawler_source, sample_port_wine_data
    ):
        """PortWineDetails record created when product_type='port_wine'."""
        result = save_discovered_product(
            extracted_data=sample_port_wine_data,
            source_url="https://example.com/products/taylors-20",
            product_type="port_wine",
            discovery_source="competition",
        )

        assert result.port_wine_details_created is True
        assert result.whiskey_details_created is False

        # Verify PortWineDetails record exists
        product = result.product
        assert hasattr(product, "port_details")
        details = product.port_details

        assert details.style == "tawny"
        assert details.indication_age == "20 Year"
        assert details.producer_house == "Taylor's"

    def test_creates_product_awards_from_awards_data(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """ProductAward records created from awards_data."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.awards_created == 1

        # Verify ProductAward record
        product = result.product
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() == 1

        award = awards.first()
        assert award.competition == "IWSC"
        assert award.year == 2024
        assert award.medal == MedalChoices.GOLD
        assert award.award_category == "Single Malt Scotch"

    def test_creates_product_ratings_from_ratings(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """ProductRating records created from ratings in extracted_data."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.ratings_created == 1

        # Verify ProductRating record
        product = result.product
        ratings = ProductRating.objects.filter(product=product)
        assert ratings.count() == 1

        rating = ratings.first()
        assert rating.source == "Whisky Advocate"
        assert rating.score == 92
        assert rating.max_score == 100
        assert rating.reviewer == "John Reviewer"

    def test_creates_product_images_from_images(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """ProductImage records created from images in extracted_data."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.images_created == 1

        # Verify ProductImage record
        product = result.product
        images = ProductImage.objects.filter(product=product)
        assert images.count() == 1

        image = images.first()
        assert image.url == "https://example.com/images/glenfiddich18.jpg"
        assert image.image_type == ImageTypeChoices.BOTTLE
        assert image.source == "Official Website"

    def test_creates_product_source_junction(
        self, sample_crawler_source, sample_crawled_source, sample_whiskey_data
    ):
        """ProductSource junction created when crawled_source provided."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
            crawled_source=sample_crawled_source,
        )

        assert result.source_record_created is True

        # Verify ProductSource junction record
        product = result.product
        product_sources = ProductSource.objects.filter(product=product)
        assert product_sources.count() == 1

        ps = product_sources.first()
        assert ps.source == sample_crawled_source

    def test_creates_field_provenance_records(
        self, sample_crawler_source, sample_crawled_source, sample_whiskey_data
    ):
        """ProductFieldSource records created for each extracted field."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
            crawled_source=sample_crawled_source,
            field_confidences={
                "name": 0.95,
                "abv": 0.90,
                "age_statement": 0.85,
            },
        )

        # At least some provenance records should be created
        assert result.provenance_records_created > 0

        # Verify ProductFieldSource records
        product = result.product
        field_sources = ProductFieldSource.objects.filter(product=product)
        assert field_sources.count() > 0

        # Check specific field provenance
        name_source = field_sources.filter(field_name="name").first()
        assert name_source is not None
        assert name_source.source == sample_crawled_source
        assert float(name_source.confidence) == 0.95

    def test_gets_or_creates_brand(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """DiscoveredBrand created/linked correctly."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result.brand_created is True
        assert result.brand is not None
        assert result.brand.name == "Glenfiddich"

        # Verify product is linked to brand
        product = result.product
        assert product.brand == result.brand

        # Creating another product with same brand should reuse existing
        second_data = sample_whiskey_data.copy()
        second_data["name"] = "Glenfiddich 21 Year Old"
        second_data["age_statement"] = "21"

        result2 = save_discovered_product(
            extracted_data=second_data,
            source_url="https://example.com/products/glenfiddich-21",
            product_type="whiskey",
            discovery_source="competition",
        )

        assert result2.brand_created is False
        assert result2.brand == result.brand

    def test_returns_product_save_result(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """save_discovered_product returns ProductSaveResult with correct data."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        # Verify result type and structure
        assert isinstance(result, ProductSaveResult)
        assert isinstance(result.product, DiscoveredProduct)
        assert isinstance(result.created, bool)
        assert isinstance(result.awards_created, int)
        assert isinstance(result.ratings_created, int)
        assert isinstance(result.images_created, int)


# =============================================================================
# 3. TestDeduplication - Fingerprint/name matching (4 tests)
# =============================================================================


@pytest.mark.django_db
class TestDeduplication:
    """Tests for product deduplication logic."""

    def test_deduplicates_by_fingerprint(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """Existing product updated when fingerprint matches."""
        # Create first product
        result1 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        first_product_id = result1.product.id

        # Create with same data (same fingerprint)
        result2 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://another-site.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should return same product, not create new
        assert result2.product.id == first_product_id
        assert result2.created is False

    def test_deduplicates_by_exact_name(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """Existing product updated when name exactly matches."""
        # Create first product
        result1 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        first_product_id = result1.product.id

        # Create with same name but different fields
        second_data = {
            "name": "Glenfiddich 18 Year Old",  # Same name
            "abv": "43.0",
            "region": "Speyside",
            "country": "Scotland",
        }

        result2 = save_discovered_product(
            extracted_data=second_data,
            source_url="https://another-site.com/products/glenfiddich",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should return same product
        assert result2.product.id == first_product_id
        assert result2.created is False

    def test_merges_data_on_existing_product(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """Data merged when updating existing product."""
        # Create first product with minimal data
        minimal_data = {
            "name": "Glenfiddich 18 Year Old",
            "brand": "Glenfiddich",
            "abv": "43.0",
            "product_type": "whiskey",
        }

        result1 = save_discovered_product(
            extracted_data=minimal_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        # Now update with more complete data
        result2 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://another-site.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Product should be enriched with new data
        product = result2.product
        product.refresh_from_db()

        assert result2.created is False
        assert product.age_statement == 18
        assert product.region == "Speyside"
        assert product.nose_description == "Rich oak with hints of dried fruit and honey"

    def test_creates_new_when_no_match(
        self, sample_crawler_source, sample_whiskey_data
    ):
        """New product created when no fingerprint/name match."""
        # Create first product
        result1 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://example.com/products/glenfiddich-18",
            product_type="whiskey",
            discovery_source="competition",
        )

        # Create different product
        different_data = {
            "name": "Lagavulin 16 Year Old",
            "brand": "Lagavulin",
            "abv": "43.0",
            "age_statement": "16",
            "region": "Islay",
            "country": "Scotland",
        }

        result2 = save_discovered_product(
            extracted_data=different_data,
            source_url="https://example.com/products/lagavulin-16",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should be a new product
        assert result2.product.id != result1.product.id
        assert result2.created is True
        assert result2.product.name == "Lagavulin 16 Year Old"


# =============================================================================
# 4. TestDataNormalization - Normalizing different source formats (3 tests)
# =============================================================================


@pytest.mark.django_db
class TestDataNormalization:
    """Tests for normalizing data from different source formats."""

    def test_normalizes_competition_data(self, sample_crawler_source, sample_competition_data):
        """Competition award_data normalized correctly (product_name -> name, producer -> brand)."""
        result = save_discovered_product(
            extracted_data=sample_competition_data,
            source_url="https://iwsc.net/results/2024",
            product_type="whiskey",
            discovery_source="competition",
        )

        product = result.product

        # product_name should be normalized to name
        assert product.name == "Lagavulin 16 Year Old"

        # producer should be normalized to brand
        assert product.brand is not None
        assert product.brand.name == "Lagavulin Distillery"

        # Award should be created
        assert result.awards_created == 1

    def test_normalizes_discovery_data(self, sample_crawler_source):
        """Discovery extracted_data normalized correctly."""
        discovery_data = {
            "name": "Highland Park 12",
            "brand": "Highland Park",
            "abv": 43.0,  # Already numeric
            "age_statement": 12,  # Already numeric
            "region": "Orkney",
            "country": "Scotland",
            "taste_profile": {
                "nose": ["heather", "honey", "peat"],
                "palate": ["honey", "smoke", "oak"],
                "finish": "Long with heather notes",
            },
        }

        result = save_discovered_product(
            extracted_data=discovery_data,
            source_url="https://whisky-site.com/highland-park-12",
            product_type="whiskey",
            discovery_source="search",
        )

        product = result.product

        assert product.name == "Highland Park 12"
        assert product.abv == 43.0
        assert product.age_statement == 12

    def test_handles_missing_fields_gracefully(self, sample_crawler_source):
        """Missing fields don't cause errors."""
        minimal_data = {
            "name": "Mystery Whiskey",
            # Minimal data - most fields missing
        }

        result = save_discovered_product(
            extracted_data=minimal_data,
            source_url="https://example.com/mystery",
            product_type="whiskey",
            discovery_source="unknown",
        )

        product = result.product

        assert product.name == "Mystery Whiskey"
        assert product.abv is None
        assert product.age_statement is None
        assert product.region is None
        assert product.country is None


# =============================================================================
# 5. TestFieldExtraction - Extracting and converting fields (5 tests)
# =============================================================================


class TestFieldExtraction(TestCase):
    """Tests for field extraction helper functions."""

    def test_extracts_core_fields(self):
        """extract_core_fields extracts name, abv, age, volume."""
        data = {
            "name": "Test Whiskey",
            "abv": "43.0",
            "age_statement": "18",
            "volume_ml": "700",
            "region": "Speyside",
            "country": "Scotland",
            "gtin": "5010327325125",
        }

        fields = extract_core_fields(data)

        assert fields["name"] == "Test Whiskey"
        assert fields["abv"] == 43.0
        assert fields["age_statement"] == 18
        assert fields["volume_ml"] == 700
        assert fields["region"] == "Speyside"
        assert fields["country"] == "Scotland"
        assert fields["gtin"] == "5010327325125"

    def test_extracts_tasting_fields(self):
        """extract_tasting_fields extracts all tasting profile fields."""
        data = {
            "color_description": "Deep amber",
            "color_intensity": "7",
            "clarity": "brilliant",
            "viscosity": "medium",
            "nose_description": "Rich oak",
            "primary_aromas": ["oak", "honey"],
            "primary_intensity": "8",
            "palate_flavors": ["toffee", "vanilla"],
            "finish_length": "9",
            "warmth": "6",
        }

        fields = extract_tasting_fields(data)

        assert fields["color_description"] == "Deep amber"
        assert fields["color_intensity"] == 7
        assert fields["clarity"] == "brilliant"
        assert fields["nose_description"] == "Rich oak"
        assert fields["primary_aromas"] == ["oak", "honey"]
        assert fields["finish_length"] == 9

    def test_converts_string_to_float_for_abv(self):
        """String ABV values converted to float."""
        data = {"abv": "  43.5  "}  # With whitespace
        fields = extract_core_fields(data)

        assert fields["abv"] == 43.5
        assert isinstance(fields["abv"], float)

        # Also test already-numeric value
        data2 = {"abv": 40.0}
        fields2 = extract_core_fields(data2)
        assert fields2["abv"] == 40.0

    def test_converts_string_to_int_for_age(self):
        """String age_statement values converted to int."""
        data = {"age_statement": "  18  "}  # With whitespace
        fields = extract_core_fields(data)

        assert fields["age_statement"] == 18
        assert isinstance(fields["age_statement"], int)

        # Also test decimal string
        data2 = {"age_statement": "18.0"}
        fields2 = extract_core_fields(data2)
        assert fields2["age_statement"] == 18

    def test_handles_null_values(self):
        """Null/empty values don't appear in extracted fields."""
        data = {
            "name": "Test Whiskey",
            "abv": None,
            "age_statement": "",
            "region": "   ",  # Whitespace only
            "country": None,
        }

        fields = extract_core_fields(data)

        assert fields["name"] == "Test Whiskey"
        assert "abv" not in fields or fields["abv"] is None
        assert "age_statement" not in fields or fields["age_statement"] is None
        assert "region" not in fields or fields["region"] is None


# =============================================================================
# TestNormalizeExtractedData - Tests for the normalize function
# =============================================================================


class TestNormalizeExtractedData(TestCase):
    """Tests for normalize_extracted_data function."""

    def test_normalizes_product_name_to_name(self):
        """product_name field normalized to name."""
        data = {"product_name": "Lagavulin 16"}
        normalized = normalize_extracted_data(data)

        assert normalized["name"] == "Lagavulin 16"
        assert "product_name" not in normalized

    def test_normalizes_producer_to_brand(self):
        """producer field normalized to brand."""
        data = {"producer": "Lagavulin Distillery"}
        normalized = normalize_extracted_data(data)

        assert normalized["brand"] == "Lagavulin Distillery"
        assert "producer" not in normalized

    def test_preserves_original_name_and_brand(self):
        """Original name/brand preserved if product_name/producer not present."""
        data = {
            "name": "Glenfiddich 18",
            "brand": "Glenfiddich",
        }
        normalized = normalize_extracted_data(data)

        assert normalized["name"] == "Glenfiddich 18"
        assert normalized["brand"] == "Glenfiddich"

    def test_name_takes_precedence_over_product_name(self):
        """name takes precedence if both name and product_name present."""
        data = {
            "name": "Original Name",
            "product_name": "Competition Name",
        }
        normalized = normalize_extracted_data(data)

        # name should take precedence
        assert normalized["name"] == "Original Name"
