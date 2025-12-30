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
