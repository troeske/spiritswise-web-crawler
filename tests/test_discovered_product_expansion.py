"""
Tests for DiscoveredProduct Model Expansion.

Task Group 2: DiscoveredProduct Model Expansion
These tests verify the expanded DiscoveredProduct model functionality including:
- Core field creation (gtin, name, product_type, abv)
- Brand FK relationship
- ArrayField storage (primary_cask, finishing_cask)
- Conflict detection fields (has_conflicts, conflict_details)
- Denormalized counter fields
- Fingerprint computation compatibility
- Tasting profile fields
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError


@pytest.mark.django_db
class TestDiscoveredProductCoreFields:
    """Tests for DiscoveredProduct core field expansion."""

    def test_core_fields_creation(self):
        """DiscoveredProduct can be created with new core fields."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Core",
            slug="test-source-core",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/1",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            # New core fields
            gtin="12345678901234",
            name="Glenfiddich 18 Year Old",
            category="Single Malt Scotch",
            abv=Decimal("43.0"),
        )

        product.refresh_from_db()
        assert product.gtin == "12345678901234"
        assert product.name == "Glenfiddich 18 Year Old"
        assert product.category == "Single Malt Scotch"
        assert product.abv == Decimal("43.0")

    def test_gtin_nullable(self):
        """GTIN field can be null."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source GTIN",
            slug="test-source-gtin",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/gtin",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            gtin=None,
            name="Unknown Product",
        )

        product.refresh_from_db()
        assert product.gtin is None


@pytest.mark.django_db
class TestDiscoveredProductBrandRelationship:
    """Tests for DiscoveredProduct FK relationship to DiscoveredBrand."""

    def test_brand_fk_relationship(self):
        """DiscoveredProduct can link to DiscoveredBrand via FK."""
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredBrand,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Brand",
            slug="test-source-brand",
            base_url="https://example.com",
            category="retailer",
        )

        brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
            country="Scotland",
            region="Speyside",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/brand",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Glenfiddich 18",
            brand=brand,
        )

        product.refresh_from_db()
        assert product.brand == brand
        assert product.brand.name == "Glenfiddich"
        # Test reverse relation
        assert product in brand.products.all()

    def test_brand_nullable(self):
        """Brand FK can be null."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Brand Null",
            slug="test-source-brand-null",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/nobrand",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Unknown Whiskey",
            brand=None,
        )

        product.refresh_from_db()
        assert product.brand is None


@pytest.mark.django_db
class TestDiscoveredProductArrayFields:
    """Tests for DiscoveredProduct ArrayField storage."""

    def test_arrayfield_storage(self):
        """ArrayFields correctly store lists of values."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Array",
            slug="test-source-array",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/array",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Complex Whiskey",
            primary_cask=["ex-bourbon", "american_oak"],
            finishing_cask=["sherry", "oloroso"],
            wood_type=["american_oak", "european_oak"],
            cask_treatment=["charred", "toasted"],
        )

        product.refresh_from_db()
        assert product.primary_cask == ["ex-bourbon", "american_oak"]
        assert product.finishing_cask == ["sherry", "oloroso"]
        assert product.wood_type == ["american_oak", "european_oak"]
        assert product.cask_treatment == ["charred", "toasted"]

    def test_arrayfield_empty_default(self):
        """ArrayFields default to empty list."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Array Empty",
            slug="test-source-array-empty",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/array-empty",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Simple Whiskey",
        )

        product.refresh_from_db()
        assert product.primary_cask == []
        assert product.finishing_cask == []


@pytest.mark.django_db
class TestDiscoveredProductConflictDetection:
    """Tests for DiscoveredProduct conflict detection fields."""

    def test_conflict_detection_fields(self):
        """Conflict detection fields store conflict information."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Conflict",
            slug="test-source-conflict",
            base_url="https://example.com",
            category="retailer",
        )

        conflict_details = {
            "field": "abv",
            "values": [
                {"source_id": "source-1", "value": 43.0},
                {"source_id": "source-2", "value": 45.0},
            ],
        }

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/conflict",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Conflicted Whiskey",
            has_conflicts=True,
            conflict_details=conflict_details,
        )

        product.refresh_from_db()
        assert product.has_conflicts is True
        assert product.conflict_details == conflict_details
        assert product.conflict_details["field"] == "abv"

    def test_conflict_fields_default(self):
        """Conflict fields have correct defaults."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source No Conflict",
            slug="test-source-no-conflict",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/noconflict",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Clear Whiskey",
        )

        product.refresh_from_db()
        assert product.has_conflicts is False
        assert product.conflict_details is None


@pytest.mark.django_db
class TestDiscoveredProductDenormalizedCounters:
    """Tests for DiscoveredProduct denormalized counter fields."""

    def test_counter_fields_exist_with_defaults(self):
        """Counter fields exist with default value of 0."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Counter",
            slug="test-source-counter",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/counter",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Counter Test Whiskey",
        )

        product.refresh_from_db()
        assert product.award_count == 0
        assert product.rating_count == 0
        assert product.price_count == 0
        # mention_count already exists in the model
        assert product.mention_count == 0

    def test_counter_fields_can_be_updated(self):
        """Counter fields can be updated to non-zero values."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Counter Update",
            slug="test-source-counter-update",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/counter-update",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Award Winner Whiskey",
            award_count=5,
            rating_count=12,
            price_count=3,
        )

        product.refresh_from_db()
        assert product.award_count == 5
        assert product.rating_count == 12
        assert product.price_count == 3


@pytest.mark.django_db
class TestDiscoveredProductFingerprintCompatibility:
    """Tests for fingerprint computation compatibility with new fields."""

    def test_fingerprint_still_works_with_expanded_model(self):
        """Fingerprint computation works with expanded model."""
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredBrand,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Fingerprint",
            slug="test-source-fingerprint",
            base_url="https://example.com",
            category="retailer",
        )

        brand = DiscoveredBrand.objects.create(
            name="Macallan",
            country="Scotland",
            region="Speyside",
        )

        # Create product with extracted_data (legacy approach)
        extracted_data = {
            "name": "Macallan 18",
            "brand": "Macallan",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 43.0,
            "age_statement": 18,
        }

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/fingerprint",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            extracted_data=extracted_data,
            # New fields
            name="Macallan 18",
            brand=brand,
            abv=Decimal("43.0"),
            age_statement=18,
        )

        # Fingerprint should be computed from extracted_data
        assert product.fingerprint is not None
        assert len(product.fingerprint) == 64

    def test_check_duplicate_works_with_expanded_model(self):
        """Duplicate detection works with expanded model."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Dup",
            slug="test-source-dup",
            base_url="https://example.com",
            category="retailer",
        )

        extracted_data = {
            "name": "Duplicate Test Product",
            "brand": "TestBrand",
            "product_type": "whiskey",
            "volume_ml": 700,
            "abv": 40.0,
        }

        product1 = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/dup1",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test 1</html>",
            extracted_data=extracted_data,
            name="Duplicate Test Product",
        )

        product2 = DiscoveredProduct(
            source=source,
            source_url="https://example.com/product/dup2",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test 2</html>",
            extracted_data=extracted_data,
            name="Duplicate Test Product",
        )
        # Compute fingerprint for unsaved product
        product2.fingerprint = DiscoveredProduct.compute_fingerprint(extracted_data)

        # Check for duplicate
        assert product2.check_duplicate() is True


@pytest.mark.django_db
class TestDiscoveredProductTastingProfile:
    """Tests for DiscoveredProduct tasting profile fields."""

    def test_tasting_profile_appearance_fields(self):
        """Appearance tasting profile fields store correctly."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Appearance",
            slug="test-source-appearance",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/appearance",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Appearance Test Whiskey",
            color_description="Deep amber with golden highlights",
            color_intensity=7,
            clarity="brilliant",
            viscosity="medium",
        )

        product.refresh_from_db()
        assert product.color_description == "Deep amber with golden highlights"
        assert product.color_intensity == 7
        assert product.clarity == "brilliant"
        assert product.viscosity == "medium"

    def test_tasting_profile_nose_fields(self):
        """Nose tasting profile fields store correctly."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Nose",
            slug="test-source-nose",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/nose",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Nose Test Whiskey",
            primary_aromas=["vanilla", "honey", "oak", "caramel"],
            primary_intensity=8,
            secondary_aromas=["citrus", "floral"],
            aroma_evolution="Opens with vanilla, develops honey notes",
            nose_description="Rich and complex nose",
        )

        product.refresh_from_db()
        assert product.primary_aromas == ["vanilla", "honey", "oak", "caramel"]
        assert product.primary_intensity == 8
        assert product.secondary_aromas == ["citrus", "floral"]
        assert "vanilla" in product.aroma_evolution
        assert product.nose_description == "Rich and complex nose"

    def test_tasting_profile_palate_fields(self):
        """Palate tasting profile fields store correctly."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Palate",
            slug="test-source-palate",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/palate",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Palate Test Whiskey",
            initial_taste="Sweet and warming",
            mid_palate_evolution="Develops spicy oak notes",
            palate_flavors=["vanilla", "toffee", "cinnamon", "dried fruit"],
            flavor_intensity=8,
            complexity=9,
            mouthfeel="oily",
        )

        product.refresh_from_db()
        assert product.initial_taste == "Sweet and warming"
        assert "spicy" in product.mid_palate_evolution
        assert len(product.palate_flavors) == 4
        assert product.flavor_intensity == 8
        assert product.complexity == 9
        assert product.mouthfeel == "oily"

    def test_tasting_profile_finish_fields(self):
        """Finish tasting profile fields store correctly."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Finish",
            slug="test-source-finish",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/finish",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Finish Test Whiskey",
            finish_length=9,
            warmth=7,
            dryness=5,
            finish_flavors=["oak", "spice", "tobacco"],
            finish_evolution="Long lingering finish with oak",
            final_notes="Ends with gentle warmth",
        )

        product.refresh_from_db()
        assert product.finish_length == 9
        assert product.warmth == 7
        assert product.dryness == 5
        assert product.finish_flavors == ["oak", "spice", "tobacco"]
        assert "lingering" in product.finish_evolution
        assert product.final_notes == "Ends with gentle warmth"

    def test_tasting_profile_overall_fields(self):
        """Overall tasting profile fields store correctly."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Overall",
            slug="test-source-overall",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/overall",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Overall Test Whiskey",
            balance=8,
            overall_complexity=9,
            uniqueness=7,
            drinkability=8,
            price_quality_ratio=7,
            experience_level="enthusiast",
            serving_recommendation="neat",
            food_pairings="Dark chocolate, aged cheese",
        )

        product.refresh_from_db()
        assert product.balance == 8
        assert product.overall_complexity == 9
        assert product.uniqueness == 7
        assert product.drinkability == 8
        assert product.price_quality_ratio == 7
        assert product.experience_level == "enthusiast"
        assert product.serving_recommendation == "neat"
        assert "chocolate" in product.food_pairings


@pytest.mark.django_db
class TestDiscoveredProductHelperMethods:
    """Tests for DiscoveredProduct helper methods with new structure."""

    def test_add_discovery_source_works(self):
        """add_discovery_source helper method still works."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Helper",
            slug="test-source-helper",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/helper",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Helper Test Whiskey",
        )

        product.add_discovery_source("competition")
        product.add_discovery_source("serpapi")

        product.refresh_from_db()
        assert "competition" in product.discovery_sources
        assert "serpapi" in product.discovery_sources

    def test_add_rating_works(self):
        """add_rating helper method still works."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Rating",
            slug="test-source-rating",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/rating",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Rating Test Whiskey",
        )

        rating = {
            "source": "Whisky Advocate",
            "score": 92,
            "max_score": 100,
            "reviewer": "John Doe",
        }
        product.add_rating(rating)

        product.refresh_from_db()
        assert len(product.ratings) == 1
        assert product.ratings[0]["source"] == "Whisky Advocate"

    def test_update_best_price_works(self):
        """update_best_price helper method still works."""
        from crawler.models import (
            DiscoveredProduct,
            CrawlerSource,
            ProductType,
        )

        source = CrawlerSource.objects.create(
            name="Test Source Price",
            slug="test-source-price",
            base_url="https://example.com",
            category="retailer",
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/product/price",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            name="Price Test Whiskey",
        )

        product.update_best_price(99.99, "USD", "Total Wine", "https://totalwine.com/p")

        product.refresh_from_db()
        assert product.best_price == Decimal("99.99")
        assert product.best_price_currency == "USD"
        assert product.best_price_retailer == "Total Wine"
