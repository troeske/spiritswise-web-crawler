"""
E2E Integration Tests for Spirit Competition Award Winners.

RECT-E2E-002: End-to-end test with competition-style data for spirits

Tests verify the complete data flow for various spirit types:
1. DiscoveredProduct records created with spirit-specific columns
2. ProductAward records created with correct medal types
3. ProductSource and ProductFieldSource provenance records
4. Brand creation and linking
5. Region/country data properly populated

Uses simulated competition data for Brandy/Cognac and Gin products.
"""

import pytest
from decimal import Decimal

from crawler.models import (
    CrawlerSource,
    CrawledSource,
    CrawledSourceTypeChoices,
    DiscoveredProduct,
    DiscoveredBrand,
    ProductAward,
    ProductSource,
    ProductFieldSource,
    ProductType,
    SourceCategory,
    MedalChoices,
)
from crawler.services.content_processor import (
    extract_individual_fields,
    create_product_awards,
    create_product_source,
    create_field_provenance_records,
    get_or_create_brand,
)


# Sample Brandy/Cognac competition medal winners
# Based on typical spirits competition format (ISC, SFWSC, etc.)
BRANDY_COMPETITION_MEDALS = [
    {
        "name": "Hennessy XO",
        "brand": "Hennessy",
        "product_type": "brandy",
        "abv": 40.0,
        "country": "France",
        "region": "Cognac",
        "awards": [
            {
                "competition": "ISC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "category": "Cognac XO",
                "score": 95,
            }
        ],
    },
    {
        "name": "Remy Martin VSOP",
        "brand": "Remy Martin",
        "product_type": "brandy",
        "abv": 40.0,
        "country": "France",
        "region": "Cognac",
        "awards": [
            {
                "competition": "ISC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "silver",
                "category": "Cognac VSOP",
                "score": 88,
            }
        ],
    },
    {
        "name": "Calvados Pays d'Auge XO",
        "brand": "Christian Drouin",
        "product_type": "brandy",
        "abv": 42.0,
        "country": "France",
        "region": "Normandy",
        "awards": [
            {
                "competition": "ISC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "bronze",
                "category": "Apple Brandy",
                "score": 82,
            }
        ],
    },
]

# Sample Gin competition medal winners
GIN_COMPETITION_MEDALS = [
    {
        "name": "Sipsmith London Dry Gin",
        "brand": "Sipsmith",
        "product_type": "gin",
        "abv": 41.6,
        "country": "UK",
        "region": "London",
        "awards": [
            {
                "competition": "SFWSC",
                "competition_country": "USA",
                "year": 2025,
                "medal": "double_gold",
                "category": "London Dry Gin",
                "score": 98,
            }
        ],
    },
    {
        "name": "Hendrick's Gin",
        "brand": "Hendrick's",
        "product_type": "gin",
        "abv": 44.0,
        "country": "UK",
        "region": "Scotland",
        "awards": [
            {
                "competition": "SFWSC",
                "competition_country": "USA",
                "year": 2025,
                "medal": "gold",
                "category": "Contemporary Gin",
                "score": 94,
            }
        ],
    },
]


@pytest.fixture
def brandy_crawler_source(db):
    """Create CrawlerSource for brandy tests."""
    return CrawlerSource.objects.create(
        name="ISC E2E Test",
        slug="isc-e2e-test",
        base_url="https://internationalspiritscompetition.com",
        category=SourceCategory.COMPETITION,
        product_types=["brandy", "gin"],
    )


@pytest.fixture
def brandy_crawled_source(db):
    """Create sample CrawledSource for brandy tests."""
    return CrawledSource.objects.create(
        url="https://isc.com/awards/2025/brandy/gold",
        title="ISC 2025 Brandy Gold Medals",
        content_hash="isce2ehash001",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        raw_content="<html>ISC 2025 Brandy Medal Winners</html>",
    )


@pytest.mark.e2e
class TestBrandyIntegration:
    """E2E tests for Brandy/Cognac competition medal winners."""

    def test_brandy_individual_columns_populated(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify brandy individual columns are populated, not just JSONFields."""
        extracted_data = BRANDY_COMPETITION_MEDALS[0].copy()  # Hennessy XO
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="hennessy-xo-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Verify individual columns populated
        assert product.name == "Hennessy XO"
        assert product.abv == Decimal("40.0")
        assert product.country == "France"
        assert product.region == "Cognac"
        assert product.product_type == ProductType.BRANDY

    def test_brandy_award_with_score(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify brandy award includes score."""
        extracted_data = BRANDY_COMPETITION_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="hennessy-score-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        # Create awards
        awards_created = create_product_awards(product, extracted_data.get("awards"))

        # Verify award created with score
        assert awards_created == 1
        product_awards = ProductAward.objects.filter(product=product)
        assert product_awards.count() == 1

        award = product_awards.first()
        assert award.competition == "ISC"
        assert award.year == 2025
        assert award.medal == MedalChoices.GOLD
        assert award.score == 95

    def test_multiple_brandy_products(self, brandy_crawler_source, brandy_crawled_source, db):
        """Test processing multiple brandy products."""
        products_created = []

        for idx, data in enumerate(BRANDY_COMPETITION_MEDALS):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=brandy_crawler_source,
                source_url=brandy_crawled_source.url,
                fingerprint=f"multi-brandy-e2e-{idx}",
                product_type=ProductType.BRANDY,
                raw_content=brandy_crawled_source.raw_content,
                raw_content_hash=brandy_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )
            products_created.append(product)

        # Verify all products created
        assert len(products_created) == 3
        assert DiscoveredProduct.objects.filter(
            fingerprint__startswith="multi-brandy-e2e-"
        ).count() == 3

    def test_brandy_brand_creation(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify brandy brand is created and linked."""
        extracted_data = BRANDY_COMPETITION_MEDALS[1].copy()  # Remy Martin

        brand, created = get_or_create_brand(
            extracted_data,
            crawled_source=brandy_crawled_source,
            confidence=0.92,
        )

        assert brand is not None
        assert brand.name == "Remy Martin"
        assert created is True


@pytest.mark.e2e
class TestGinIntegration:
    """E2E tests for Gin competition medal winners."""

    def test_gin_individual_columns_populated(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify gin individual columns are populated."""
        extracted_data = GIN_COMPETITION_MEDALS[0].copy()  # Sipsmith
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="sipsmith-gin-e2e",
            product_type=ProductType.GIN,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        assert product.name == "Sipsmith London Dry Gin"
        # ABV may be stored as float or Decimal depending on model/db
        assert float(product.abv) == 41.6
        assert product.country == "UK"
        assert product.region == "London"
        assert product.product_type == ProductType.GIN

    def test_gin_double_gold_medal(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify double gold medal type is handled."""
        extracted_data = GIN_COMPETITION_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="sipsmith-double-gold-e2e",
            product_type=ProductType.GIN,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        create_product_awards(product, extracted_data.get("awards"))
        award = ProductAward.objects.filter(product=product).first()

        assert award.medal == MedalChoices.DOUBLE_GOLD
        assert award.score == 98

    def test_gin_from_scotland(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify Scottish gin country/region."""
        extracted_data = GIN_COMPETITION_MEDALS[1].copy()  # Hendrick's
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="hendricks-gin-e2e",
            product_type=ProductType.GIN,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        assert product.country == "UK"
        assert product.region == "Scotland"


@pytest.mark.e2e
class TestAwardMedalVariety:
    """Tests for different medal types across spirit categories."""

    def test_gold_medal(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify gold medal handling."""
        extracted_data = BRANDY_COMPETITION_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="gold-medal-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        create_product_awards(product, extracted_data.get("awards"))
        award = ProductAward.objects.filter(product=product).first()

        assert award.medal == MedalChoices.GOLD

    def test_silver_medal(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify silver medal handling."""
        extracted_data = BRANDY_COMPETITION_MEDALS[1].copy()  # Remy Martin with silver
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="silver-medal-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        create_product_awards(product, extracted_data.get("awards"))
        award = ProductAward.objects.filter(product=product).first()

        assert award.medal == MedalChoices.SILVER
        assert award.score == 88

    def test_bronze_medal(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify bronze medal handling."""
        extracted_data = BRANDY_COMPETITION_MEDALS[2].copy()  # Calvados with bronze
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="bronze-medal-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        create_product_awards(product, extracted_data.get("awards"))
        award = ProductAward.objects.filter(product=product).first()

        assert award.medal == MedalChoices.BRONZE
        assert award.score == 82


@pytest.mark.e2e
class TestProductSourceProvenance:
    """Tests for ProductSource and ProductFieldSource provenance tracking."""

    def test_product_source_junction(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify ProductSource junction for brandy products."""
        extracted_data = BRANDY_COMPETITION_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="brandy-source-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        product_source = create_product_source(
            product,
            brandy_crawled_source,
            0.90,
            extracted_data,
        )

        assert product_source is not None
        assert product_source.product == product
        assert product_source.source == brandy_crawled_source

    def test_field_provenance_records(self, brandy_crawler_source, brandy_crawled_source, db):
        """Verify ProductFieldSource provenance records."""
        extracted_data = BRANDY_COMPETITION_MEDALS[0].copy()
        individual_fields = extract_individual_fields(extracted_data)
        brand, _ = get_or_create_brand(extracted_data)

        product = DiscoveredProduct.objects.create(
            source=brandy_crawler_source,
            source_url=brandy_crawled_source.url,
            fingerprint="brandy-provenance-e2e",
            product_type=ProductType.BRANDY,
            raw_content=brandy_crawled_source.raw_content,
            raw_content_hash=brandy_crawled_source.content_hash,
            brand=brand,
            extracted_data=extracted_data,
            **individual_fields,
        )

        records_created = create_field_provenance_records(
            product,
            brandy_crawled_source,
            extracted_data,
            None,
            0.92,
        )

        assert records_created > 0
        provenance = ProductFieldSource.objects.filter(product=product)
        assert provenance.count() > 0

        # Check specific field
        name_prov = provenance.filter(field_name="name").first()
        assert name_prov is not None
        assert name_prov.extracted_value == "Hennessy XO"
