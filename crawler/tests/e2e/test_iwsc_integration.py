"""
E2E Integration Tests for IWSC 2025 Medal Winners.

RECT-E2E-001: End-to-end test with real IWSC-style data

Tests verify the complete data flow:
1. DiscoveredProduct records created with individual columns populated
2. WhiskeyDetails records created and linked
3. ProductAward records created with correct medal types
4. ProductSource junction records created
5. ProductFieldSource provenance records created
6. Brand creation and linking

Uses simulated IWSC data to test full integration without network access.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from crawler.models import (
    CrawlerSource,
    CrawledSource,
    CrawledSourceTypeChoices,
    DiscoveredProduct,
    DiscoveredBrand,
    WhiskeyDetails,
    ProductAward,
    ProductSource,
    ProductFieldSource,
    ProductType,
    SourceCategory,
    MedalChoices,
    WhiskeyTypeChoices,
)
from crawler.services.content_processor import (
    ContentProcessor,
    ProcessingResult,
    extract_individual_fields,
    _create_whiskey_details,
    create_product_awards,
    create_product_source,
    create_field_provenance_records,
    get_or_create_brand,
)


# Sample IWSC whiskey medal winner data
# Note: Uses both 'region'/'country' for DiscoveredProduct and 'whiskey_region'/'whiskey_country' for WhiskeyDetails
IWSC_WHISKEY_MEDALS = [
    {
        "name": "Macallan 18 Year Old Double Cask",
        "brand": "The Macallan",
        "product_type": "whiskey",
        "abv": 43.0,
        "age_statement": 18,
        "country": "Scotland",
        "region": "Speyside",
        "whiskey_type": "scotch_single_malt",
        "whiskey_country": "Scotland",
        "whiskey_region": "Speyside",
        "distillery": "The Macallan Distillery",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "category": "Scotch Single Malt Whisky 16-20 Years",
            }
        ],
    },
    {
        "name": "Buffalo Trace Kentucky Straight Bourbon",
        "brand": "Buffalo Trace",
        "product_type": "whiskey",
        "abv": 45.0,
        "age_statement": None,
        "country": "USA",
        "region": "Kentucky",
        "whiskey_type": "bourbon",
        "whiskey_country": "USA",
        "whiskey_region": "Kentucky",
        "distillery": "Buffalo Trace Distillery",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "silver",
                "category": "Bourbon Whiskey",
            }
        ],
    },
    {
        "name": "Hakushu 12 Year Old",
        "brand": "Suntory",
        "product_type": "whiskey",
        "abv": 43.0,
        "age_statement": 12,
        "country": "Japan",
        "region": "Yamanashi",
        "whiskey_type": "japanese",
        "whiskey_country": "Japan",
        "whiskey_region": "Yamanashi",
        "distillery": "Hakushu Distillery",
        "peated": True,
        "peat_level": "lightly_peated",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "category": "Japanese Whisky",
            }
        ],
    },
]

# Sample IWSC port wine medal winner data
IWSC_PORT_MEDALS = [
    {
        "name": "Taylor's 20 Year Old Tawny Port",
        "brand": "Taylor's",
        "product_type": "port_wine",
        "abv": 20.0,
        "country": "Portugal",
        "region": "Douro",
        "style": "tawny",
        "indication_age": "20 Year Old",
        "producer_house": "Taylor's",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "award_category": "Aged Tawny Port",
            }
        ],
    },
]


@pytest.fixture
def sample_crawler_source(db):
    """Create IWSC CrawlerSource for tests."""
    return CrawlerSource.objects.create(
        name="IWSC E2E Test",
        slug="iwsc-e2e-test",
        base_url="https://iwsc.net",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_crawled_source(db):
    """Create sample CrawledSource for tests."""
    return CrawledSource.objects.create(
        url="https://iwsc.net/awards/2025/whiskey/test",
        title="IWSC 2025 Whiskey Gold Medals",
        content_hash="iwsce2ehash001",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        raw_content="<html>IWSC 2025 Medal Winners</html>",
    )


@pytest.mark.e2e
class TestIWSCWhiskeyIntegration:
    """E2E tests for IWSC whiskey medal winners."""

    def test_individual_columns_populated(self, sample_crawler_source, sample_crawled_source, db):
        """Verify individual columns are populated, not just JSONFields."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()

        # Create product directly using helper functions
        individual_fields = extract_individual_fields(extracted_data)

        # Create brand
        brand, _ = get_or_create_brand(extracted_data)

        # Create product - individual_fields already contains 'name' from extract_individual_fields
        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="macallan-18-double-cask-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Verify individual columns populated
        assert product.name == "Macallan 18 Year Old Double Cask"
        assert product.abv == Decimal("43.0")
        assert product.age_statement == 18
        assert product.country == "Scotland"
        assert product.region == "Speyside"
        assert product.product_type == ProductType.WHISKEY

    def test_whiskey_details_created_and_linked(self, sample_crawler_source, sample_crawled_source, db):
        """Verify WhiskeyDetails record created and linked to product."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="macallan-18-whiskey-details-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Create WhiskeyDetails
        _create_whiskey_details(product, extracted_data)

        # Verify WhiskeyDetails created and linked
        assert hasattr(product, 'whiskey_details')
        details = product.whiskey_details
        assert details is not None
        assert details.whiskey_type == WhiskeyTypeChoices.SCOTCH_SINGLE_MALT
        assert details.whiskey_country == "Scotland"
        assert details.whiskey_region == "Speyside"
        assert details.distillery == "The Macallan Distillery"

    def test_product_award_created(self, sample_crawler_source, sample_crawled_source, db):
        """Verify ProductAward record created with correct data."""
        extracted_data = IWSC_WHISKEY_MEDALS[1].copy()  # Buffalo Trace with Silver
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="buffalo-trace-award-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Create awards - pass the awards list, not full extracted_data
        awards_created = create_product_awards(product, extracted_data.get("awards"))

        # Verify award created
        assert awards_created == 1

        # Query ProductAward directly since product.awards is the JSONField list
        product_awards = ProductAward.objects.filter(product=product)
        assert product_awards.count() == 1

        award = product_awards.first()
        assert award.competition == "IWSC"
        assert award.year == 2025
        assert award.medal == MedalChoices.SILVER

    def test_product_source_junction_created(self, sample_crawler_source, sample_crawled_source, db):
        """Verify ProductSource junction record created."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="macallan-source-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Create ProductSource - use positional args to match function signature
        product_source = create_product_source(
            product,
            sample_crawled_source,
            0.95,  # extraction_confidence
            extracted_data,
        )

        # Verify junction created
        assert product_source is not None
        assert product_source.product == product
        assert product_source.source == sample_crawled_source

    def test_field_provenance_records_created(self, sample_crawler_source, sample_crawled_source, db):
        """Verify ProductFieldSource provenance records created."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="macallan-provenance-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Create provenance records - match function signature
        records_created = create_field_provenance_records(
            product,
            sample_crawled_source,  # source
            extracted_data,
            None,  # field_confidences (optional)
            0.92,  # overall_confidence
        )

        # Verify provenance records created
        assert records_created > 0
        provenance = ProductFieldSource.objects.filter(product=product)
        assert provenance.count() > 0

        # Check a specific field
        name_prov = provenance.filter(field_name="name").first()
        assert name_prov is not None
        assert name_prov.extracted_value == "Macallan 18 Year Old Double Cask"

    def test_brand_created_and_linked(self, sample_crawler_source, sample_crawled_source, db):
        """Verify DiscoveredBrand created and linked to product."""
        extracted_data = IWSC_WHISKEY_MEDALS[2].copy()  # Hakushu with Suntory brand

        # Create brand
        brand, created = get_or_create_brand(
            extracted_data,
            crawled_source=sample_crawled_source,
            confidence=0.95,
        )

        # Verify brand created
        assert brand is not None
        assert brand.name == "Suntory"
        assert created is True  # New brand

    def test_multiple_whiskey_products_flow(self, sample_crawler_source, sample_crawled_source, db):
        """Test processing multiple whiskey products."""
        products_created = []

        for data in IWSC_WHISKEY_MEDALS:
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=sample_crawler_source,
                source_url=sample_crawled_source.url,
                fingerprint=f"multi-whiskey-e2e-{len(products_created)}",
                product_type=ProductType.WHISKEY,
                raw_content=sample_crawled_source.raw_content,
                raw_content_hash=sample_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            _create_whiskey_details(product, extracted_data)
            create_product_awards(product, extracted_data.get("awards"))
            products_created.append(product)

        # Verify all products created
        assert len(products_created) == 3
        assert DiscoveredProduct.objects.filter(
            fingerprint__startswith="multi-whiskey-e2e-"
        ).count() == 3

        # Verify whiskey details for all
        for product in products_created:
            assert hasattr(product, 'whiskey_details')

    def test_peated_whiskey_fields(self, sample_crawler_source, sample_crawled_source, db):
        """Test peated whiskey fields are correctly populated."""
        extracted_data = IWSC_WHISKEY_MEDALS[2].copy()  # Hakushu (peated)
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="hakushu-peated-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        _create_whiskey_details(product, extracted_data)

        # Verify peated fields
        details = product.whiskey_details
        assert details.peated is True
        assert details.peat_level == "lightly_peated"


@pytest.mark.e2e
class TestIWSCPortWineIntegration:
    """E2E tests for IWSC port wine medal winners."""

    def test_port_wine_individual_columns(self, sample_crawler_source, sample_crawled_source, db):
        """Verify port wine individual columns populated."""
        extracted_data = IWSC_PORT_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="taylors-20-tawny-e2e",
            product_type=ProductType.PORT_WINE,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        assert product.name == "Taylor's 20 Year Old Tawny Port"
        assert product.abv == Decimal("20.0")
        assert product.country == "Portugal"
        assert product.product_type == ProductType.PORT_WINE


@pytest.mark.e2e
class TestDataNotOnlyInJSONFields:
    """Verify data is NOT only in JSONFields."""

    def test_individual_columns_not_null(self, sample_crawler_source, sample_crawled_source, db):
        """Check that individual columns are populated, not just JSONFields."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="json-check-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Verify these are NOT null (not just stored in JSON)
        assert product.abv is not None
        assert product.country is not None
        assert product.region is not None
        assert product.brand is not None

    def test_extracted_data_also_populated(self, sample_crawler_source, sample_crawled_source, db):
        """Verify extracted_data JSONField also populated (dual-write)."""
        extracted_data = IWSC_WHISKEY_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url=sample_crawled_source.url,
            fingerprint="dual-write-e2e",
            product_type=ProductType.WHISKEY,
            raw_content=sample_crawled_source.raw_content,
            raw_content_hash=sample_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Verify dual-write: individual columns AND extracted_data
        assert product.abv is not None
        assert product.extracted_data is not None
        assert product.extracted_data.get("abv") == 43.0
