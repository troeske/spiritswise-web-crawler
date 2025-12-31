"""
Tests for DiscoveredBrand model.

Task Group 1: DiscoveredBrand Model Implementation
These tests verify the new DiscoveredBrand model for tracking spirit brands/distilleries.

TDD: Tests written first before model implementation.
"""

import pytest
from django.db import IntegrityError
from django.utils.text import slugify


class TestDiscoveredBrandCreation:
    """Tests for DiscoveredBrand model creation and basic functionality."""

    def test_brand_creation_with_required_fields(self, db):
        """Brand should be created with name and auto-generated slug."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Macallan")

        assert brand.id is not None
        assert brand.name == "Macallan"
        assert brand.slug == "macallan"

    def test_brand_creation_with_all_fields(self, db):
        """Brand should store all optional fields correctly."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
            description="One of the world's best-selling single malt whiskies.",
            website="https://www.glenfiddich.com",
            country="Scotland",
            region="Speyside",
        )

        brand.refresh_from_db()

        assert brand.name == "Glenfiddich"
        assert brand.slug == "glenfiddich"
        assert brand.description == "One of the world's best-selling single malt whiskies."
        assert brand.website == "https://www.glenfiddich.com"
        assert brand.country == "Scotland"
        assert brand.region == "Speyside"

    def test_brand_timestamps_auto_set(self, db):
        """Brand should have created_at and updated_at auto-populated."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Laphroaig")

        assert brand.created_at is not None
        assert brand.updated_at is not None


class TestDiscoveredBrandUniqueness:
    """Tests for unique constraint enforcement on DiscoveredBrand."""

    def test_unique_name_constraint(self, db):
        """Creating two brands with the same name should raise IntegrityError."""
        from crawler.models import DiscoveredBrand

        DiscoveredBrand.objects.create(name="Highland Park")

        with pytest.raises(IntegrityError):
            DiscoveredBrand.objects.create(name="Highland Park")

    def test_unique_slug_constraint(self, db):
        """Creating two brands with the same slug should raise IntegrityError."""
        from crawler.models import DiscoveredBrand

        DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")

        with pytest.raises(IntegrityError):
            # Manually setting same slug should fail
            DiscoveredBrand.objects.create(name="Another Brand", slug="test-brand")


class TestDiscoveredBrandSlugGeneration:
    """Tests for automatic slug generation on DiscoveredBrand."""

    def test_slug_auto_generated_from_name(self, db):
        """Slug should be auto-generated from name if not provided."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="The Glenlivet")

        assert brand.slug == "the-glenlivet"

    def test_slug_handles_special_characters(self, db):
        """Slug should properly handle special characters in name."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Bunnahabhain (Islay)")

        assert brand.slug == "bunnahabhain-islay"

    def test_slug_not_overwritten_if_provided(self, db):
        """Slug should not be overwritten if explicitly provided."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(
            name="Custom Name",
            slug="my-custom-slug"
        )

        assert brand.slug == "my-custom-slug"

    def test_slug_preserved_on_update(self, db):
        """Slug should be preserved when updating other fields."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Ardbeg")
        original_slug = brand.slug

        brand.description = "Updated description"
        brand.save()
        brand.refresh_from_db()

        assert brand.slug == original_slug


class TestDiscoveredBrandCounters:
    """Tests for denormalized counter fields on DiscoveredBrand."""

    def test_counter_fields_default_to_zero(self, db):
        """Counter fields should default to 0."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Bowmore")

        assert brand.product_count == 0
        assert brand.mention_count == 0
        assert brand.award_count == 0

    def test_counter_fields_can_be_updated(self, db):
        """Counter fields should be updatable."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Talisker")

        brand.product_count = 15
        brand.mention_count = 42
        brand.award_count = 7
        brand.save()

        brand.refresh_from_db()

        assert brand.product_count == 15
        assert brand.mention_count == 42
        assert brand.award_count == 7

    def test_counter_fields_persist_correctly(self, db):
        """Counter fields should persist through database reload."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(
            name="Oban",
            product_count=10,
            mention_count=25,
            award_count=5,
        )

        # Reload from database
        reloaded = DiscoveredBrand.objects.get(pk=brand.pk)

        assert reloaded.product_count == 10
        assert reloaded.mention_count == 25
        assert reloaded.award_count == 5


class TestDiscoveredBrandStringRepresentation:
    """Tests for string representation of DiscoveredBrand."""

    def test_str_returns_name(self, db):
        """String representation should return the brand name."""
        from crawler.models import DiscoveredBrand

        brand = DiscoveredBrand.objects.create(name="Dalmore")

        assert str(brand) == "Dalmore"


# =============================================================================
# RECT-010: DiscoveredBrand Creation and Linking Tests
# =============================================================================

class TestBrandFieldMappingCoverage:
    """Tests for BRAND_FIELD_MAPPING coverage."""

    def test_mapping_includes_name(self):
        """Mapping should include name field."""
        from crawler.services.content_processor import BRAND_FIELD_MAPPING
        assert "name" in BRAND_FIELD_MAPPING

    def test_mapping_includes_country(self):
        """Mapping should include country field."""
        from crawler.services.content_processor import BRAND_FIELD_MAPPING
        assert "country" in BRAND_FIELD_MAPPING

    def test_mapping_includes_region(self):
        """Mapping should include region field."""
        from crawler.services.content_processor import BRAND_FIELD_MAPPING
        assert "region" in BRAND_FIELD_MAPPING


class TestGetOrCreateBrand:
    """Integration tests for get_or_create_brand function."""

    def test_brand_created_from_extraction(self, db):
        """Brand name in AI response -> DiscoveredBrand record."""
        from crawler.models import DiscoveredBrand
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {
            "brand": "Macallan",
            "brand_country": "Scotland",
            "brand_region": "Speyside",
        }

        brand, created = get_or_create_brand(extracted_data)

        assert brand is not None
        assert created is True
        assert brand.name == "Macallan"
        assert DiscoveredBrand.objects.filter(name="Macallan").exists()

    def test_existing_brand_reused(self, db):
        """Same brand name -> reuse existing DiscoveredBrand."""
        from crawler.models import DiscoveredBrand
        from crawler.services.content_processor import get_or_create_brand

        # Create brand first
        existing_brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
            slug="glenfiddich",
        )

        extracted_data = {"brand": "Glenfiddich"}

        brand, created = get_or_create_brand(extracted_data)

        assert brand is not None
        assert created is False
        assert brand.id == existing_brand.id
        # Should still only be 1 brand
        assert DiscoveredBrand.objects.filter(name="Glenfiddich").count() == 1

    def test_brand_slug_generated(self, db):
        """Unique slug generated from brand name."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {"brand": "The Balvenie"}

        brand, created = get_or_create_brand(extracted_data)

        assert brand.slug == slugify("The Balvenie")
        assert brand.slug == "the-balvenie"

    def test_brand_country_populated(self, db):
        """Brand country extracted from AI response."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {
            "brand": "Yamazaki",
            "brand_country": "Japan",
        }

        brand, created = get_or_create_brand(extracted_data)

        assert brand.country == "Japan"

    def test_brand_region_populated(self, db):
        """Brand region extracted from AI response."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {
            "brand": "Highland Park",
            "brand_country": "Scotland",
            "brand_region": "Islands",
        }

        brand, created = get_or_create_brand(extracted_data)

        assert brand.region == "Islands"

    def test_no_brand_returns_none(self, db):
        """No brand in AI response -> returns None."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {"name": "Mystery Whiskey"}

        brand, created = get_or_create_brand(extracted_data)

        assert brand is None
        assert created is False

    def test_empty_brand_returns_none(self, db):
        """Empty brand string -> returns None."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {"brand": ""}

        brand, created = get_or_create_brand(extracted_data)

        assert brand is None

    def test_whitespace_brand_returns_none(self, db):
        """Whitespace-only brand string -> returns None."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {"brand": "   "}

        brand, created = get_or_create_brand(extracted_data)

        assert brand is None

    def test_brand_name_case_insensitive_match(self, db):
        """Brand matching should be case insensitive."""
        from crawler.models import DiscoveredBrand
        from crawler.services.content_processor import get_or_create_brand

        # Create brand with uppercase
        DiscoveredBrand.objects.create(
            name="MACALLAN",
            slug="macallan",
        )

        extracted_data = {"brand": "Macallan"}

        brand, created = get_or_create_brand(extracted_data)

        # Should match existing (case insensitive)
        assert created is False
        assert DiscoveredBrand.objects.count() == 1

    def test_fallback_to_distillery_as_brand(self, db):
        """If no brand but distillery present, use distillery."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {
            "distillery": "Springbank Distillery",
            "distillery_country": "Scotland",
        }

        brand, created = get_or_create_brand(extracted_data)

        # Should create brand from distillery name
        assert brand is not None
        assert "Springbank" in brand.name

    def test_fallback_to_producer_as_brand(self, db):
        """If no brand but producer present, use producer."""
        from crawler.services.content_processor import get_or_create_brand

        extracted_data = {
            "producer": "Fonseca",
            "producer_country": "Portugal",
        }

        brand, created = get_or_create_brand(extracted_data)

        assert brand is not None
        assert brand.name == "Fonseca"
