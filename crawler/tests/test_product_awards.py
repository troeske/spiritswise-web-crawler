"""
Tests for ProductAward Creation from AI Response Awards Data.

RECT-004: Create ProductAward Records from Awards Data

These tests verify that the ContentProcessor extracts awards from
AI Enhancement response and creates individual ProductAward records
instead of only storing in JSONFields.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    ProductAward,
    MedalChoices,
    CrawlerSource,
    SourceCategory,
)
from crawler.services.content_processor import (
    ContentProcessor,
    ProcessingResult,
    create_product_awards,
    AWARD_FIELD_MAPPING,
)
from crawler.services.ai_client import EnhancementResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Award Extraction Source",
        slug="test-award-extraction-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_product(db, sample_source):
    """Create a sample DiscoveredProduct for testing awards."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/product/award-test",
        fingerprint="award-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test product content</html>",
        raw_content_hash="awardtest123hash",
        extracted_data={"name": "Test Whiskey 18 Year"},
        name="Test Whiskey 18 Year",
        abv=Decimal("43.0"),
        age_statement=18,
    )


@pytest.fixture
def single_award_data():
    """Single award data from AI response."""
    return {
        "competition": "IWSC",
        "competition_country": "UK",
        "year": 2024,
        "medal": "gold",
        "score": 95,
        "category": "Single Malt Scotch Whisky",
        "url": "https://iwsc.net/awards/123",
        "image_url": "https://iwsc.net/images/gold-medal.png",
    }


@pytest.fixture
def multiple_awards_data():
    """Multiple awards data from AI response."""
    return [
        {
            "competition": "IWSC",
            "competition_country": "UK",
            "year": 2024,
            "medal": "gold",
            "score": 95,
            "category": "Single Malt Scotch Whisky",
            "url": "https://iwsc.net/awards/123",
        },
        {
            "competition": "San Francisco World Spirits",
            "competition_country": "USA",
            "year": 2023,
            "medal": "double_gold",
            "score": None,
            "category": "Best Whisky",
            "url": "https://sfwsc.com/awards/456",
        },
        {
            "competition": "World Whiskies Awards",
            "competition_country": "UK",
            "year": 2022,
            "medal": "best_in_class",
            "score": None,
            "category": "World's Best Single Malt",
            "url": "https://worldwhiskiesawards.com/789",
        },
    ]


# =============================================================================
# Unit Tests for Award Field Mapping (No DB needed)
# =============================================================================

class TestAwardFieldMapping:
    """Unit tests for award field mapping configuration."""

    def test_award_field_mapping_includes_all_fields(self):
        """Award field mapping should include all required fields."""
        required_fields = [
            "competition",
            "competition_country",
            "year",
            "medal",
            "score",
            "category",
            "url",
            "image_url",
        ]
        for field in required_fields:
            assert field in AWARD_FIELD_MAPPING, f"Missing award field: {field}"

    def test_award_field_mapping_model_fields(self):
        """Award field mapping should map to correct model fields."""
        # Check key mappings to model field names
        assert AWARD_FIELD_MAPPING["competition"][0] == "competition"
        assert AWARD_FIELD_MAPPING["competition_country"][0] == "competition_country"
        assert AWARD_FIELD_MAPPING["year"][0] == "year"
        assert AWARD_FIELD_MAPPING["medal"][0] == "medal"
        assert AWARD_FIELD_MAPPING["score"][0] == "score"
        assert AWARD_FIELD_MAPPING["category"][0] == "award_category"
        assert AWARD_FIELD_MAPPING["url"][0] == "award_url"
        assert AWARD_FIELD_MAPPING["image_url"][0] == "image_url"


# =============================================================================
# Integration Tests for ProductAward Creation
# =============================================================================

class TestProductAwardCreation:
    """Integration tests for ProductAward creation from AI response."""

    def test_single_award_creates_record(self, sample_product, single_award_data):
        """One award in AI response should create one ProductAward record."""
        awards_created = create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )

        assert awards_created == 1
        assert ProductAward.objects.filter(product=sample_product).count() == 1

    def test_multiple_awards_create_multiple_records(self, sample_product, multiple_awards_data):
        """Three awards should create three ProductAward records."""
        awards_created = create_product_awards(
            product=sample_product,
            awards_data=multiple_awards_data,
        )

        assert awards_created == 3
        assert ProductAward.objects.filter(product=sample_product).count() == 3

    def test_award_fields_mapped_correctly(self, sample_product, single_award_data):
        """Award fields should be mapped correctly to model fields."""
        create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )

        award = ProductAward.objects.get(product=sample_product)

        assert award.competition == "IWSC"
        assert award.competition_country == "UK"
        assert award.year == 2024
        assert award.medal == "gold"
        assert award.score == 95
        assert award.award_category == "Single Malt Scotch Whisky"
        assert award.award_url == "https://iwsc.net/awards/123"
        assert award.image_url == "https://iwsc.net/images/gold-medal.png"

    def test_medal_choices_validated(self, sample_product):
        """Only valid medal types should be accepted."""
        valid_medals = ["double_gold", "gold", "silver", "bronze", "best_in_class", "category_winner"]

        for medal in valid_medals:
            # Clear existing awards first
            ProductAward.objects.filter(product=sample_product).delete()

            award_data = {
                "competition": "Test Competition",
                "competition_country": "Test Country",
                "year": 2024,
                "medal": medal,
                "category": "Test Category",
            }

            awards_created = create_product_awards(
                product=sample_product,
                awards_data=[award_data],
            )

            assert awards_created == 1
            award = ProductAward.objects.get(product=sample_product)
            assert award.medal == medal

    def test_invalid_medal_skipped(self, sample_product):
        """Invalid medal types should be skipped (award not created)."""
        award_data = {
            "competition": "Test Competition",
            "competition_country": "Test Country",
            "year": 2024,
            "medal": "platinum",  # Invalid medal type
            "category": "Test Category",
        }

        awards_created = create_product_awards(
            product=sample_product,
            awards_data=[award_data],
        )

        # Award should not be created with invalid medal
        assert awards_created == 0
        assert ProductAward.objects.filter(product=sample_product).count() == 0

    def test_award_url_stored(self, sample_product, single_award_data):
        """Award source URL should be stored for provenance."""
        create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )

        award = ProductAward.objects.get(product=sample_product)
        assert award.award_url == "https://iwsc.net/awards/123"

    def test_award_count_denormalized(self, sample_product, multiple_awards_data):
        """DiscoveredProduct.award_count should be updated after awards created."""
        assert sample_product.award_count == 0

        create_product_awards(
            product=sample_product,
            awards_data=multiple_awards_data,
        )

        sample_product.refresh_from_db()
        assert sample_product.award_count == 3

    def test_duplicate_awards_not_created(self, sample_product, single_award_data):
        """Same award from same source should not create duplicate."""
        # Create award first time
        awards_created_1 = create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )
        assert awards_created_1 == 1

        # Try to create same award again
        awards_created_2 = create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )
        assert awards_created_2 == 0  # No new award created

        # Should still only have one award
        assert ProductAward.objects.filter(product=sample_product).count() == 1

    def test_null_optional_fields_handled(self, sample_product):
        """Optional fields with null values should be handled gracefully."""
        award_data = {
            "competition": "Test Competition",
            "competition_country": "Test Country",
            "year": 2024,
            "medal": "gold",
            "category": "Test Category",
            "score": None,  # Optional, null
            "url": None,  # Optional, null
            "image_url": None,  # Optional, null
        }

        awards_created = create_product_awards(
            product=sample_product,
            awards_data=[award_data],
        )

        assert awards_created == 1
        award = ProductAward.objects.get(product=sample_product)
        assert award.score is None
        assert award.award_url is None
        assert award.image_url is None

    def test_empty_awards_list_handled(self, sample_product):
        """Empty awards list should not create any records."""
        awards_created = create_product_awards(
            product=sample_product,
            awards_data=[],
        )

        assert awards_created == 0
        assert ProductAward.objects.filter(product=sample_product).count() == 0

    def test_none_awards_handled(self, sample_product):
        """None awards_data should not create any records."""
        awards_created = create_product_awards(
            product=sample_product,
            awards_data=None,
        )

        assert awards_created == 0
        assert ProductAward.objects.filter(product=sample_product).count() == 0

    def test_missing_required_fields_skipped(self, sample_product):
        """Awards missing required fields should be skipped."""
        # Missing competition name
        award_data = {
            "competition_country": "UK",
            "year": 2024,
            "medal": "gold",
            "category": "Test Category",
        }

        awards_created = create_product_awards(
            product=sample_product,
            awards_data=[award_data],
        )

        assert awards_created == 0
        assert ProductAward.objects.filter(product=sample_product).count() == 0


class TestAwardExtractionFromAIResponse:
    """Tests for extracting awards from full AI response structure."""

    def test_awards_extracted_from_extracted_data(self, sample_product, multiple_awards_data):
        """Awards should be extracted from extracted_data dict."""
        extracted_data = {
            "name": "Test Whiskey",
            "abv": 43.0,
            "awards": multiple_awards_data,
        }

        # Extract and create awards from extracted_data
        awards_list = extracted_data.get("awards", [])
        awards_created = create_product_awards(
            product=sample_product,
            awards_data=awards_list,
        )

        assert awards_created == 3

    def test_awards_accessible_via_related_name(self, sample_product, single_award_data):
        """ProductAward should be accessible via product.awards_rel."""
        create_product_awards(
            product=sample_product,
            awards_data=[single_award_data],
        )

        assert sample_product.awards_rel.count() == 1
        assert sample_product.awards_rel.first().competition == "IWSC"
