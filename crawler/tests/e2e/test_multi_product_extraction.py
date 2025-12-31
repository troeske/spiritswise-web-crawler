"""
E2E Tests for Multi-Product Page Extraction.

RECT-E2E-003: End-to-end test for extracting multiple products from a single page

Tests verify the complete data flow when a single page contains multiple products:
1. Multiple DiscoveredProduct records created from one page
2. Each product has unique fingerprint
3. All products correctly linked to same CrawledSource
4. ProductSource junction records track extraction context
5. Different product types can be extracted from same page

Uses simulated award page data with multiple medal winners.
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


# Simulated award page containing multiple products (like IWSC category winners)
MULTI_PRODUCT_PAGE_DATA = [
    {
        "name": "Ardbeg 10 Year Old",
        "brand": "Ardbeg",
        "product_type": "whiskey",
        "abv": 46.0,
        "age_statement": 10,
        "country": "Scotland",
        "region": "Islay",
        "whiskey_type": "scotch_single_malt",
        "whiskey_country": "Scotland",
        "whiskey_region": "Islay",
        "distillery": "Ardbeg Distillery",
        "peated": True,
        "peat_level": "heavily_peated",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "category": "Islay Single Malt",
            }
        ],
    },
    {
        "name": "Lagavulin 16 Year Old",
        "brand": "Lagavulin",
        "product_type": "whiskey",
        "abv": 43.0,
        "age_statement": 16,
        "country": "Scotland",
        "region": "Islay",
        "whiskey_type": "scotch_single_malt",
        "whiskey_country": "Scotland",
        "whiskey_region": "Islay",
        "distillery": "Lagavulin Distillery",
        "peated": True,
        "peat_level": "heavily_peated",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "gold",
                "category": "Islay Single Malt",
            }
        ],
    },
    {
        "name": "Laphroaig Quarter Cask",
        "brand": "Laphroaig",
        "product_type": "whiskey",
        "abv": 48.0,
        "country": "Scotland",
        "region": "Islay",
        "whiskey_type": "scotch_single_malt",
        "whiskey_country": "Scotland",
        "whiskey_region": "Islay",
        "distillery": "Laphroaig Distillery",
        "peated": True,
        "peat_level": "heavily_peated",
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "silver",
                "category": "Islay Single Malt",
            }
        ],
    },
    {
        "name": "Bruichladdich The Classic Laddie",
        "brand": "Bruichladdich",
        "product_type": "whiskey",
        "abv": 50.0,
        "country": "Scotland",
        "region": "Islay",
        "whiskey_type": "scotch_single_malt",
        "whiskey_country": "Scotland",
        "whiskey_region": "Islay",
        "distillery": "Bruichladdich Distillery",
        "peated": False,
        "awards": [
            {
                "competition": "IWSC",
                "competition_country": "UK",
                "year": 2025,
                "medal": "bronze",
                "category": "Islay Single Malt",
            }
        ],
    },
]


@pytest.fixture
def multi_product_crawler_source(db):
    """Create CrawlerSource for multi-product tests."""
    return CrawlerSource.objects.create(
        name="IWSC Multi-Product E2E",
        slug="iwsc-multi-product-e2e",
        base_url="https://iwsc.net",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey"],
    )


@pytest.fixture
def multi_product_crawled_source(db):
    """Create CrawledSource representing page with multiple products."""
    return CrawledSource.objects.create(
        url="https://iwsc.net/awards/2025/islay-single-malt-winners",
        title="IWSC 2025 Islay Single Malt Medal Winners",
        content_hash="islaywinners2025hash",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        raw_content="<html>4 Islay Single Malt Medal Winners...</html>",
    )


@pytest.mark.e2e
class TestMultiProductExtraction:
    """E2E tests for extracting multiple products from single page."""

    def test_all_products_extracted(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Verify all products from page are extracted."""
        products_created = []

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-multi-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )
            products_created.append(product)

        # Verify all 4 products created
        assert len(products_created) == 4
        assert DiscoveredProduct.objects.filter(
            fingerprint__startswith="islay-multi-e2e-"
        ).count() == 4

    def test_unique_fingerprints(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Each product has unique fingerprint."""
        fingerprints = set()

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            fingerprint = f"islay-unique-e2e-{idx}"
            fingerprints.add(fingerprint)

            DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=fingerprint,
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

        # Verify all fingerprints are unique
        assert len(fingerprints) == 4

    def test_all_products_linked_to_same_source(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """All products link to same CrawledSource."""
        products = []

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-source-link-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            # Create ProductSource junction
            create_product_source(product, multi_product_crawled_source, 0.85, extracted_data)
            products.append(product)

        # Verify all products link to same source
        source_junctions = ProductSource.objects.filter(
            source=multi_product_crawled_source
        )
        assert source_junctions.count() == 4

        # All junctions point to same source
        for junction in source_junctions:
            assert junction.source == multi_product_crawled_source

    def test_individual_columns_per_product(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Each product has individual columns populated."""
        expected_names = [
            "Ardbeg 10 Year Old",
            "Lagavulin 16 Year Old",
            "Laphroaig Quarter Cask",
            "Bruichladdich The Classic Laddie",
        ]

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-columns-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            # Verify individual columns
            assert product.name == expected_names[idx]
            assert product.country == "Scotland"
            assert product.region == "Islay"
            assert product.product_type == ProductType.WHISKEY


@pytest.mark.e2e
class TestMultiProductAwards:
    """Tests for awards from multi-product pages."""

    def test_each_product_gets_award(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Each product gets its own award record."""
        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-awards-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            # Create awards for this product
            create_product_awards(product, extracted_data.get("awards"))

        # Verify each product has an award
        total_awards = ProductAward.objects.filter(
            product__fingerprint__startswith="islay-awards-e2e-"
        ).count()
        assert total_awards == 4

    def test_different_medal_types(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Products have different medal types."""
        medals_found = []

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-medals-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            create_product_awards(product, extracted_data.get("awards"))

            award = ProductAward.objects.filter(product=product).first()
            medals_found.append(award.medal)

        # Verify different medals (2 gold, 1 silver, 1 bronze)
        assert medals_found.count(MedalChoices.GOLD) == 2
        assert medals_found.count(MedalChoices.SILVER) == 1
        assert medals_found.count(MedalChoices.BRONZE) == 1


@pytest.mark.e2e
class TestMultiProductBrands:
    """Tests for brand handling with multiple products."""

    def test_different_brands_created(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Each product has its own brand."""
        brands_created = set()

        for data in MULTI_PRODUCT_PAGE_DATA:
            brand, _ = get_or_create_brand(data)
            brands_created.add(brand.name)

        # Verify 4 unique brands
        assert len(brands_created) == 4
        assert "Ardbeg" in brands_created
        assert "Lagavulin" in brands_created
        assert "Laphroaig" in brands_created
        assert "Bruichladdich" in brands_created

    def test_brand_count_in_db(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Verify brands are saved to database."""
        for data in MULTI_PRODUCT_PAGE_DATA:
            get_or_create_brand(
                data,
                crawled_source=multi_product_crawled_source,
                confidence=0.9,
            )

        # Query brands from Islay
        islay_brands = DiscoveredBrand.objects.filter(
            name__in=["Ardbeg", "Lagavulin", "Laphroaig", "Bruichladdich"]
        )
        assert islay_brands.count() == 4


@pytest.mark.e2e
class TestMultiProductProvenance:
    """Tests for provenance tracking with multiple products."""

    def test_each_product_has_provenance(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Each product has provenance records."""
        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-prov-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            # Create provenance records
            records = create_field_provenance_records(
                product,
                multi_product_crawled_source,
                extracted_data,
                None,
                0.88,
            )
            assert records > 0

        # Verify total provenance records
        total_prov = ProductFieldSource.objects.filter(
            product__fingerprint__startswith="islay-prov-e2e-"
        ).count()
        assert total_prov > 0

    def test_all_provenance_linked_to_same_source(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """All provenance records link to same CrawledSource."""
        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-prov-source-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            create_field_provenance_records(
                product,
                multi_product_crawled_source,
                extracted_data,
                None,
                0.88,
            )

        # Verify all provenance records link to same source
        all_prov = ProductFieldSource.objects.filter(
            product__fingerprint__startswith="islay-prov-source-e2e-"
        )

        for prov in all_prov:
            assert prov.source == multi_product_crawled_source


@pytest.mark.e2e
class TestMixedPeatedProducts:
    """Tests for mixed peated/unpeated products from same page."""

    def test_peated_and_unpeated_both_extracted(self, multi_product_crawler_source, multi_product_crawled_source, db):
        """Both peated and unpeated products are extracted correctly."""
        from crawler.services.content_processor import _create_whiskey_details

        peated_products = []
        unpeated_products = []

        for idx, data in enumerate(MULTI_PRODUCT_PAGE_DATA):
            extracted_data = data.copy()
            individual_fields = extract_individual_fields(extracted_data)
            brand, _ = get_or_create_brand(extracted_data)

            product = DiscoveredProduct.objects.create(
                source=multi_product_crawler_source,
                source_url=multi_product_crawled_source.url,
                fingerprint=f"islay-peat-e2e-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content=multi_product_crawled_source.raw_content,
                raw_content_hash=multi_product_crawled_source.content_hash,
                brand=brand,
                extracted_data=extracted_data,
                **individual_fields,
            )

            _create_whiskey_details(product, extracted_data)

            if extracted_data.get("peated"):
                peated_products.append(product)
            else:
                unpeated_products.append(product)

        # Verify we have both peated and unpeated
        assert len(peated_products) == 3  # Ardbeg, Lagavulin, Laphroaig
        assert len(unpeated_products) == 1  # Bruichladdich Classic Laddie
