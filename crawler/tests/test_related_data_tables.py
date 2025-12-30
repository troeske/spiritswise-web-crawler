"""
Tests for Related Data Tables (Awards, Prices, Ratings, Images).

Task Group 4: Related Data Tables Implementation
These tests verify the ProductAward, BrandAward, ProductPrice, ProductRating,
and ProductImage models with proper FK relationships to DiscoveredProduct
and DiscoveredBrand.

TDD: Tests written first before model implementation.
"""

import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.utils import timezone
from datetime import date

from crawler.models import (
    DiscoveredProduct,
    DiscoveredBrand,
    ProductType,
    CrawlerSource,
    SourceCategory,
)


@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Award Source",
        slug="test-award-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for testing."""
    return DiscoveredBrand.objects.create(
        name="Test Brand for Awards",
        country="Scotland",
        region="Speyside",
    )


@pytest.fixture
def sample_product(db, sample_source, sample_brand):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/product/test",
        fingerprint="related-data-test-fingerprint",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test product content</html>",
        raw_content_hash="relateddata123hash",
        extracted_data={"name": "Test Whiskey 12 Year"},
        name="Test Whiskey 12 Year",
        brand=sample_brand,
        abv=Decimal("43.0"),
        age_statement=12,
    )


class TestProductAwardCreation:
    """Tests for ProductAward model creation and FK relationship."""

    def test_product_award_creation_with_required_fields(self, sample_product):
        """ProductAward should be created with required fields and FK."""
        from crawler.models import ProductAward

        award = ProductAward.objects.create(
            product=sample_product,
            competition="IWSC",
            competition_country="UK",
            year=2024,
            medal="gold",
            award_category="Single Malt Scotch Whisky",
        )

        assert award.id is not None
        assert award.product == sample_product
        assert award.competition == "IWSC"
        assert award.competition_country == "UK"
        assert award.year == 2024
        assert award.medal == "gold"

    def test_product_award_accessible_via_related_name(self, sample_product):
        """ProductAward should be accessible via product.awards_rel."""
        from crawler.models import ProductAward

        ProductAward.objects.create(
            product=sample_product,
            competition="San Francisco World Spirits",
            competition_country="USA",
            year=2024,
            medal="double_gold",
            award_category="Best Whisky",
        )

        # Access via related_name (awards_rel to avoid conflict with awards JSONField)
        assert sample_product.awards_rel.count() == 1
        assert sample_product.awards_rel.first().competition == "San Francisco World Spirits"

    def test_product_award_all_medal_choices(self, db, sample_source, sample_brand):
        """All medal choices should be accepted."""
        from crawler.models import ProductAward, MedalChoices

        medal_types = ["double_gold", "gold", "silver", "bronze", "best_in_class", "category_winner"]

        for idx, medal in enumerate(medal_types):
            product = DiscoveredProduct.objects.create(
                source=sample_source,
                source_url=f"https://example.com/product/medal-{idx}",
                fingerprint=f"medal-test-fp-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="content",
                raw_content_hash=f"hash-medal-{idx}",
                name=f"Test Whiskey Medal {idx}",
            )

            award = ProductAward.objects.create(
                product=product,
                competition="Test Competition",
                competition_country="Test Country",
                year=2024,
                medal=medal,
                award_category="Test Category",
            )

            assert award.medal == medal

    def test_product_award_optional_fields(self, sample_product):
        """Optional fields should accept values correctly."""
        from crawler.models import ProductAward

        award = ProductAward.objects.create(
            product=sample_product,
            competition="World Whiskies Awards",
            competition_country="UK",
            year=2024,
            medal="gold",
            award_category="World's Best Single Malt",
            score=95,
            award_url="https://worldwhiskiesawards.com/award/123",
            image_url="https://worldwhiskiesawards.com/images/medal.png",
        )

        award.refresh_from_db()

        assert award.score == 95
        assert award.award_url == "https://worldwhiskiesawards.com/award/123"
        assert award.image_url == "https://worldwhiskiesawards.com/images/medal.png"

    def test_product_award_cascade_delete(self, sample_product):
        """ProductAward should be deleted when product is deleted."""
        from crawler.models import ProductAward

        award = ProductAward.objects.create(
            product=sample_product,
            competition="Test Competition",
            competition_country="Test Country",
            year=2024,
            medal="gold",
            award_category="Test Category",
        )
        award_id = award.id

        sample_product.delete()

        assert not ProductAward.objects.filter(id=award_id).exists()


class TestBrandAwardCreation:
    """Tests for BrandAward model creation and FK relationship."""

    def test_brand_award_creation_with_required_fields(self, sample_brand):
        """BrandAward should be created with required fields and FK."""
        from crawler.models import BrandAward

        award = BrandAward.objects.create(
            brand=sample_brand,
            competition="Distillery of the Year",
            competition_country="Scotland",
            year=2024,
            medal="gold",
            award_category="Scottish Distillery Excellence",
        )

        assert award.id is not None
        assert award.brand == sample_brand
        assert award.competition == "Distillery of the Year"
        assert award.year == 2024

    def test_brand_award_accessible_via_related_name(self, sample_brand):
        """BrandAward should be accessible via brand.awards."""
        from crawler.models import BrandAward

        BrandAward.objects.create(
            brand=sample_brand,
            competition="Icons of Whisky",
            competition_country="UK",
            year=2024,
            medal="category_winner",
            award_category="Craft Producer of the Year",
        )

        # Access via related_name
        assert sample_brand.awards.count() == 1
        assert sample_brand.awards.first().competition == "Icons of Whisky"

    def test_brand_award_cascade_delete(self, sample_brand):
        """BrandAward should be deleted when brand is deleted."""
        from crawler.models import BrandAward

        award = BrandAward.objects.create(
            brand=sample_brand,
            competition="Test Brand Competition",
            competition_country="Test Country",
            year=2024,
            medal="gold",
            award_category="Test Brand Category",
        )
        award_id = award.id

        sample_brand.delete()

        assert not BrandAward.objects.filter(id=award_id).exists()


class TestProductPriceMultiCurrency:
    """Tests for ProductPrice model with multi-currency support."""

    def test_product_price_creation_with_required_fields(self, sample_product):
        """ProductPrice should be created with required fields."""
        from crawler.models import ProductPrice

        price = ProductPrice.objects.create(
            product=sample_product,
            retailer="Whisky Exchange",
            retailer_country="UK",
            price=Decimal("89.95"),
            currency="GBP",
            url="https://thewhiskyexchange.com/product/123",
            date_observed=date.today(),
        )

        assert price.id is not None
        assert price.product == sample_product
        assert price.price == Decimal("89.95")
        assert price.currency == "GBP"

    def test_product_price_multi_currency(self, sample_product):
        """ProductPrice should support multiple currencies."""
        from crawler.models import ProductPrice

        currencies = [
            ("USD", Decimal("99.99"), "USA"),
            ("EUR", Decimal("89.99"), "Germany"),
            ("GBP", Decimal("79.99"), "UK"),
            ("JPY", Decimal("12500.00"), "Japan"),
            ("AUD", Decimal("145.00"), "Australia"),
            ("CAD", Decimal("125.00"), "Canada"),
        ]

        for currency, price_val, country in currencies:
            ProductPrice.objects.create(
                product=sample_product,
                retailer=f"Test Retailer {country}",
                retailer_country=country,
                price=price_val,
                currency=currency,
                url=f"https://retailer-{country.lower()}.com/product",
                date_observed=date.today(),
            )

        assert sample_product.prices.count() == 6

    def test_product_price_normalized_fields(self, sample_product):
        """ProductPrice should store USD and EUR normalized values."""
        from crawler.models import ProductPrice

        price = ProductPrice.objects.create(
            product=sample_product,
            retailer="Test Retailer",
            retailer_country="UK",
            price=Decimal("89.95"),
            currency="GBP",
            price_usd=Decimal("113.50"),
            price_eur=Decimal("104.75"),
            url="https://retailer.com/product",
            date_observed=date.today(),
        )

        price.refresh_from_db()

        assert price.price_usd == Decimal("113.50")
        assert price.price_eur == Decimal("104.75")

    def test_product_price_in_stock_field(self, sample_product):
        """ProductPrice should track stock availability."""
        from crawler.models import ProductPrice

        price = ProductPrice.objects.create(
            product=sample_product,
            retailer="Test Retailer",
            retailer_country="UK",
            price=Decimal("89.95"),
            currency="GBP",
            url="https://retailer.com/product",
            date_observed=date.today(),
            in_stock=True,
        )

        price.refresh_from_db()
        assert price.in_stock is True

    def test_product_price_accessible_via_related_name(self, sample_product):
        """ProductPrice should be accessible via product.prices."""
        from crawler.models import ProductPrice

        ProductPrice.objects.create(
            product=sample_product,
            retailer="Test Retailer",
            retailer_country="USA",
            price=Decimal("99.00"),
            currency="USD",
            url="https://retailer.com/product",
            date_observed=date.today(),
        )

        assert sample_product.prices.count() == 1
        assert sample_product.prices.first().retailer == "Test Retailer"


class TestProductRatingCreation:
    """Tests for ProductRating model creation."""

    def test_product_rating_creation_with_required_fields(self, sample_product):
        """ProductRating should be created with required fields."""
        from crawler.models import ProductRating

        rating = ProductRating.objects.create(
            product=sample_product,
            source="Whisky Advocate",
            score=Decimal("92.5"),
            max_score=100,
        )

        assert rating.id is not None
        assert rating.product == sample_product
        assert rating.score == Decimal("92.5")
        assert rating.max_score == 100

    def test_product_rating_with_optional_fields(self, sample_product):
        """ProductRating should store optional fields correctly."""
        from crawler.models import ProductRating

        rating = ProductRating.objects.create(
            product=sample_product,
            source="Whisky Magazine",
            source_country="UK",
            score=Decimal("88.0"),
            max_score=100,
            reviewer="Jim Murray",
            review_url="https://whiskymag.com/reviews/123",
            date=date(2024, 6, 15),
        )

        rating.refresh_from_db()

        assert rating.source_country == "UK"
        assert rating.reviewer == "Jim Murray"
        assert rating.review_url == "https://whiskymag.com/reviews/123"
        assert rating.date == date(2024, 6, 15)

    def test_product_rating_accessible_via_related_name(self, sample_product):
        """ProductRating should be accessible via product.ratings_rel."""
        from crawler.models import ProductRating

        ProductRating.objects.create(
            product=sample_product,
            source="Test Source",
            score=Decimal("90.0"),
            max_score=100,
        )

        # Using ratings_rel to avoid conflict with existing ratings JSONField
        assert sample_product.ratings_rel.count() == 1
        assert sample_product.ratings_rel.first().source == "Test Source"


class TestProductImageCreation:
    """Tests for ProductImage model creation with image_type choices."""

    def test_product_image_creation_with_required_fields(self, sample_product):
        """ProductImage should be created with required fields."""
        from crawler.models import ProductImage

        image = ProductImage.objects.create(
            product=sample_product,
            url="https://images.example.com/bottle.jpg",
            image_type="bottle",
            source="Distillery Website",
        )

        assert image.id is not None
        assert image.product == sample_product
        assert image.url == "https://images.example.com/bottle.jpg"
        assert image.image_type == "bottle"

    def test_product_image_all_type_choices(self, db, sample_source):
        """All image_type choices should be accepted."""
        from crawler.models import ProductImage

        image_types = ["bottle", "label", "packaging", "lifestyle"]

        for idx, img_type in enumerate(image_types):
            product = DiscoveredProduct.objects.create(
                source=sample_source,
                source_url=f"https://example.com/product/img-{idx}",
                fingerprint=f"img-test-fp-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="content",
                raw_content_hash=f"hash-img-{idx}",
                name=f"Test Image Product {idx}",
            )

            image = ProductImage.objects.create(
                product=product,
                url=f"https://images.example.com/{img_type}.jpg",
                image_type=img_type,
                source="Test Source",
            )

            assert image.image_type == img_type

    def test_product_image_with_dimensions(self, sample_product):
        """ProductImage should store width and height dimensions."""
        from crawler.models import ProductImage

        image = ProductImage.objects.create(
            product=sample_product,
            url="https://images.example.com/bottle-large.jpg",
            image_type="bottle",
            source="Retailer",
            width=1200,
            height=1600,
        )

        image.refresh_from_db()

        assert image.width == 1200
        assert image.height == 1600

    def test_product_image_accessible_via_related_name(self, sample_product):
        """ProductImage should be accessible via product.images_rel."""
        from crawler.models import ProductImage

        ProductImage.objects.create(
            product=sample_product,
            url="https://images.example.com/test.jpg",
            image_type="bottle",
            source="Test Source",
        )

        # Using images_rel to avoid conflict with existing images JSONField
        assert sample_product.images_rel.count() == 1
        assert sample_product.images_rel.first().url == "https://images.example.com/test.jpg"


class TestDenormalizedCounterSignals:
    """Tests for Django signals updating denormalized counters."""

    def test_product_award_count_updated_on_create(self, sample_product):
        """DiscoveredProduct.award_count should update when ProductAward is created."""
        from crawler.models import ProductAward

        assert sample_product.award_count == 0

        ProductAward.objects.create(
            product=sample_product,
            competition="Test Competition",
            competition_country="Test Country",
            year=2024,
            medal="gold",
            award_category="Test Category",
        )

        sample_product.refresh_from_db()
        assert sample_product.award_count == 1

    def test_product_award_count_updated_on_delete(self, sample_product):
        """DiscoveredProduct.award_count should update when ProductAward is deleted."""
        from crawler.models import ProductAward

        award = ProductAward.objects.create(
            product=sample_product,
            competition="Test Competition",
            competition_country="Test Country",
            year=2024,
            medal="gold",
            award_category="Test Category",
        )

        sample_product.refresh_from_db()
        assert sample_product.award_count == 1

        award.delete()

        sample_product.refresh_from_db()
        assert sample_product.award_count == 0

    def test_brand_award_count_updated_on_create(self, sample_brand):
        """DiscoveredBrand.award_count should update when BrandAward is created."""
        from crawler.models import BrandAward

        assert sample_brand.award_count == 0

        BrandAward.objects.create(
            brand=sample_brand,
            competition="Test Brand Competition",
            competition_country="Test Country",
            year=2024,
            medal="gold",
            award_category="Test Brand Category",
        )

        sample_brand.refresh_from_db()
        assert sample_brand.award_count == 1

    def test_product_price_count_updated_on_create(self, sample_product):
        """DiscoveredProduct.price_count should update when ProductPrice is created."""
        from crawler.models import ProductPrice

        assert sample_product.price_count == 0

        ProductPrice.objects.create(
            product=sample_product,
            retailer="Test Retailer",
            retailer_country="USA",
            price=Decimal("99.00"),
            currency="USD",
            url="https://retailer.com/product",
            date_observed=date.today(),
        )

        sample_product.refresh_from_db()
        assert sample_product.price_count == 1

    def test_product_rating_count_updated_on_create(self, sample_product):
        """DiscoveredProduct.rating_count should update when ProductRating is created."""
        from crawler.models import ProductRating

        assert sample_product.rating_count == 0

        ProductRating.objects.create(
            product=sample_product,
            source="Test Source",
            score=Decimal("90.0"),
            max_score=100,
        )

        sample_product.refresh_from_db()
        assert sample_product.rating_count == 1

    def test_multiple_awards_increment_counter(self, sample_product):
        """Multiple awards should correctly increment award_count."""
        from crawler.models import ProductAward

        assert sample_product.award_count == 0

        for i in range(3):
            ProductAward.objects.create(
                product=sample_product,
                competition=f"Competition {i}",
                competition_country="Test Country",
                year=2024,
                medal="gold",
                award_category=f"Category {i}",
            )

        sample_product.refresh_from_db()
        assert sample_product.award_count == 3
