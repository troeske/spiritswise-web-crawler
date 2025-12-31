"""
Tests for BrandSource and BrandAward Records.

RECT-013: Implement BrandSource and BrandAward Records

These tests verify that BrandSource and BrandAward records are created
correctly when extracting brand data from sources.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal

from crawler.models import (
    DiscoveredBrand,
    DiscoveredProduct,
    CrawlerSource,
    CrawledSource,
    CrawledSourceTypeChoices,
    BrandSource,
    BrandAward,
    SourceCategory,
    ProductType,
    MedalChoices,
)
from crawler.services.content_processor import (
    create_brand_source,
    create_brand_award,
    get_or_create_brand,
)


@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for tests."""
    return CrawlerSource.objects.create(
        name="IWSC",
        slug="iwsc",
        base_url="https://iwsc.net",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_crawled_source(db):
    """Create a sample CrawledSource for tests."""
    return CrawledSource.objects.create(
        url="https://iwsc.net/awards/2025/whiskey",
        title="IWSC 2025 Whiskey Awards",
        content_hash="brandsourcehash001",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        raw_content="<html>Brand Awards</html>",
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for tests."""
    return DiscoveredBrand.objects.create(
        name="Macallan",
        country="Scotland",
        region="Speyside",
    )


@pytest.fixture
def sample_product(db, sample_crawler_source, sample_brand):
    """Create a sample DiscoveredProduct for tests."""
    return DiscoveredProduct.objects.create(
        source=sample_crawler_source,
        source_url="https://iwsc.net/products/macallan-18",
        fingerprint="brand-test-product-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Macallan 18</html>",
        raw_content_hash="brandtesthash001",
        name="Macallan 18 Year Old",
        brand=sample_brand,
    )


class TestBrandSourceCreation:
    """Tests for BrandSource junction record creation."""

    def test_brand_source_created_on_extraction(self, sample_brand, sample_crawled_source):
        """BrandSource junction created when brand extracted from source."""
        brand_source = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.95,
        )

        assert brand_source is not None
        assert brand_source.brand == sample_brand
        assert brand_source.source == sample_crawled_source
        assert brand_source.extraction_confidence == Decimal("0.95")

    def test_brand_source_extraction_confidence_stored(self, sample_brand, sample_crawled_source):
        """Extraction confidence stored in BrandSource."""
        brand_source = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.87,
        )

        assert brand_source.extraction_confidence == Decimal("0.87")

    def test_brand_source_mention_type_stored(self, sample_brand, sample_crawled_source):
        """Mention type stored in BrandSource."""
        brand_source = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.9,
            mention_type="award_winner",
        )

        assert brand_source.mention_type == "award_winner"

    def test_brand_source_mention_count_default(self, sample_brand, sample_crawled_source):
        """Mention count defaults to 1."""
        brand_source = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.9,
        )

        assert brand_source.mention_count == 1

    def test_brand_source_unique_constraint(self, sample_brand, sample_crawled_source):
        """Same brand + source doesn't create duplicate, returns existing."""
        brand_source1 = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.9,
        )
        brand_source2 = create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.95,  # Different confidence
        )

        # Should return same record
        assert brand_source1.id == brand_source2.id
        # Should update confidence
        brand_source1.refresh_from_db()
        assert brand_source1.extraction_confidence == Decimal("0.95")

    def test_brand_source_returns_none_without_crawled_source(self, sample_brand):
        """Returns None if no crawled_source provided."""
        result = create_brand_source(
            brand=sample_brand,
            crawled_source=None,
            confidence=0.9,
        )

        assert result is None

    def test_brand_source_returns_none_without_brand(self, sample_crawled_source):
        """Returns None if no brand provided."""
        result = create_brand_source(
            brand=None,
            crawled_source=sample_crawled_source,
            confidence=0.9,
        )

        assert result is None


class TestBrandMentionCount:
    """Tests for brand mention_count updates."""

    def test_brand_mention_count_incremented_on_new_source(self, sample_brand, sample_crawled_source):
        """Brand.mention_count incremented when new BrandSource created."""
        initial_count = sample_brand.mention_count

        create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.9,
        )

        sample_brand.refresh_from_db()
        assert sample_brand.mention_count == initial_count + 1

    def test_brand_mention_count_not_duplicated(self, sample_brand, sample_crawled_source):
        """Brand.mention_count not incremented on duplicate source."""
        create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.9,
        )
        initial_count = sample_brand.mention_count

        # Create again (duplicate)
        create_brand_source(
            brand=sample_brand,
            crawled_source=sample_crawled_source,
            confidence=0.95,
        )

        sample_brand.refresh_from_db()
        # Should not increment since it's an update, not new
        assert sample_brand.mention_count == initial_count


class TestBrandAwardCreation:
    """Tests for BrandAward record creation."""

    def test_brand_award_created(self, sample_brand):
        """BrandAward created for brand-level awards."""
        award = create_brand_award(
            brand=sample_brand,
            competition="Distillery of the Year",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Single Malt Distillery",
        )

        assert award is not None
        assert award.brand == sample_brand
        assert award.competition == "Distillery of the Year"
        assert award.year == 2025
        assert award.medal == "gold"

    def test_brand_award_with_optional_fields(self, sample_brand):
        """BrandAward created with optional fields."""
        award = create_brand_award(
            brand=sample_brand,
            competition="Best Distillery",
            competition_country="USA",
            year=2024,
            medal="silver",
            award_category="Overall Excellence",
            score=95,
            award_url="https://example.com/award/123",
        )

        assert award.score == 95
        assert award.award_url == "https://example.com/award/123"

    def test_brand_award_medal_validation(self, sample_brand):
        """Invalid medal type is handled gracefully."""
        # Invalid medal - should return None
        award = create_brand_award(
            brand=sample_brand,
            competition="Test Competition",
            competition_country="UK",
            year=2025,
            medal="invalid_medal",
            award_category="Test Category",
        )

        assert award is None

    def test_brand_award_returns_none_without_brand(self):
        """Returns None if no brand provided."""
        result = create_brand_award(
            brand=None,
            competition="Test Competition",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Test Category",
        )

        assert result is None

    def test_brand_award_returns_none_missing_required(self, sample_brand):
        """Returns None if required fields missing."""
        # Missing competition
        result = create_brand_award(
            brand=sample_brand,
            competition=None,
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Test Category",
        )

        assert result is None


class TestBrandAwardCount:
    """Tests for brand award_count updates."""

    def test_brand_award_count_incremented(self, sample_brand):
        """Brand.award_count incremented when new BrandAward created."""
        initial_count = sample_brand.award_count

        create_brand_award(
            brand=sample_brand,
            competition="Test Competition",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Test Category",
        )

        sample_brand.refresh_from_db()
        assert sample_brand.award_count == initial_count + 1

    def test_brand_award_count_multiple_awards(self, sample_brand):
        """Brand.award_count correct with multiple awards."""
        initial_count = sample_brand.award_count

        create_brand_award(
            brand=sample_brand,
            competition="Competition A",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Category A",
        )
        create_brand_award(
            brand=sample_brand,
            competition="Competition B",
            competition_country="USA",
            year=2024,
            medal="silver",
            award_category="Category B",
        )

        sample_brand.refresh_from_db()
        assert sample_brand.award_count == initial_count + 2


class TestBrandAwardDuplicatePrevention:
    """Tests for preventing duplicate brand awards."""

    def test_duplicate_brand_award_not_created(self, sample_brand):
        """Same award (brand + competition + year + medal + category) not duplicated."""
        award1 = create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Distillery Excellence",
        )

        award2 = create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Distillery Excellence",
        )

        # Should return same record
        assert award1.id == award2.id

        # Should only have one BrandAward
        assert BrandAward.objects.filter(
            brand=sample_brand,
            competition="IWSC",
            year=2025,
        ).count() == 1

    def test_different_year_creates_new_award(self, sample_brand):
        """Different year creates new award record."""
        award1 = create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Excellence",
        )

        award2 = create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2024,  # Different year
            medal="gold",
            award_category="Excellence",
        )

        assert award1.id != award2.id


class TestGetOrCreateBrandWithSource:
    """Tests for get_or_create_brand integration with BrandSource."""

    def test_brand_source_created_when_brand_created(self, db, sample_crawled_source):
        """BrandSource created when new brand created from extraction."""
        extracted_data = {
            "brand": "Glenfiddich",
            "country": "Scotland",
            "region": "Speyside",
        }

        brand, created = get_or_create_brand(
            extracted_data=extracted_data,
            crawled_source=sample_crawled_source,
            confidence=0.92,
        )

        assert brand is not None
        assert created is True

        # BrandSource should be created
        brand_source = BrandSource.objects.filter(
            brand=brand,
            source=sample_crawled_source,
        ).first()
        assert brand_source is not None
        assert brand_source.extraction_confidence == Decimal("0.92")

    def test_brand_source_created_when_brand_reused(self, db, sample_brand, sample_crawled_source):
        """BrandSource created when existing brand reused."""
        # Create a second CrawledSource
        crawled_source_2 = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2025/another",
            title="IWSC 2025 Another Awards",
            content_hash="brandsourcehash002",
            source_type=CrawledSourceTypeChoices.AWARD_PAGE,
            raw_content="<html>More Brand Awards</html>",
        )

        extracted_data = {
            "brand": "Macallan",  # Same as sample_brand
            "country": "Scotland",
        }

        brand, created = get_or_create_brand(
            extracted_data=extracted_data,
            crawled_source=crawled_source_2,
            confidence=0.88,
        )

        assert brand is not None
        assert brand.id == sample_brand.id  # Reused existing brand
        assert created is False

        # BrandSource should be created for new source
        brand_source = BrandSource.objects.filter(
            brand=brand,
            source=crawled_source_2,
        ).first()
        assert brand_source is not None


class TestBrandSourceQueries:
    """Tests for querying BrandSource relationships."""

    def test_query_brand_sources(self, sample_brand, sample_crawled_source, db):
        """Can query all sources for a brand."""
        # Create multiple sources
        crawled_source_2 = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2025/page2",
            title="IWSC 2025 Page 2",
            content_hash="brandsourcehash003",
            source_type=CrawledSourceTypeChoices.AWARD_PAGE,
            raw_content="<html>Page 2</html>",
        )

        create_brand_source(sample_brand, sample_crawled_source, 0.9)
        create_brand_source(sample_brand, crawled_source_2, 0.85)

        # Query via related name
        sources = sample_brand.sources.all()
        assert sources.count() == 2

    def test_query_brands_from_source(self, sample_crawled_source, db):
        """Can query all brands from a source."""
        brand1 = DiscoveredBrand.objects.create(name="Brand A", slug="brand-a")
        brand2 = DiscoveredBrand.objects.create(name="Brand B", slug="brand-b")

        create_brand_source(brand1, sample_crawled_source, 0.9)
        create_brand_source(brand2, sample_crawled_source, 0.85)

        # Query via related name
        brands = sample_crawled_source.brands.all()
        assert brands.count() == 2


class TestBrandAwardQueries:
    """Tests for querying BrandAward relationships."""

    def test_query_brand_awards(self, sample_brand):
        """Can query all awards for a brand."""
        create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="Excellence",
        )
        create_brand_award(
            brand=sample_brand,
            competition="SWA",
            competition_country="USA",
            year=2024,
            medal="silver",
            award_category="Quality",
        )

        # Query via related name
        awards = sample_brand.awards.all()
        assert awards.count() == 2

    def test_filter_brand_awards_by_year(self, sample_brand):
        """Can filter brand awards by year."""
        create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2025,
            medal="gold",
            award_category="A",
        )
        create_brand_award(
            brand=sample_brand,
            competition="IWSC",
            competition_country="UK",
            year=2024,
            medal="silver",
            award_category="B",
        )

        awards_2025 = sample_brand.awards.filter(year=2025)
        assert awards_2025.count() == 1
        assert awards_2025.first().medal == "gold"
