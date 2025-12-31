"""
Tests for ProductRating Creation in ContentProcessor.

RECT-007: Create ProductRating Records from Ratings Data

These tests verify that ratings from AI response are extracted and
stored as individual ProductRating records instead of in JSONField.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal
from datetime import date

from crawler.models import (
    DiscoveredProduct,
    ProductType,
    CrawlerSource,
    SourceCategory,
    ProductRating,
)
from crawler.services.content_processor import (
    create_product_ratings,
    RATING_FIELD_MAPPING,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Rating Source",
        slug="test-rating-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_product(db, sample_source):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/whiskey/test",
        fingerprint="rating-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test whiskey content</html>",
        raw_content_hash="rating001hash",
        extracted_data={"name": "Test Whiskey"},
        name="Test Whiskey",
    )


# =============================================================================
# Unit Tests for Rating Field Mapping Coverage
# =============================================================================

class TestRatingFieldMappingCoverage:
    """Tests to verify RATING_FIELD_MAPPING covers all required fields."""

    def test_mapping_includes_source_fields(self):
        """Mapping should include source fields."""
        source_fields = ["source", "source_country"]
        for field in source_fields:
            assert field in RATING_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_score_fields(self):
        """Mapping should include score fields."""
        score_fields = ["score", "max_score"]
        for field in score_fields:
            assert field in RATING_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_optional_fields(self):
        """Mapping should include optional fields."""
        optional_fields = ["reviewer", "review_url", "date", "review_count"]
        for field in optional_fields:
            assert field in RATING_FIELD_MAPPING, f"Missing field: {field}"


# =============================================================================
# Integration Tests for ProductRating Creation
# =============================================================================

class TestProductRatingCreation:
    """Integration tests for ProductRating creation."""

    def test_single_rating_creates_record(self, db, sample_product):
        """One rating in AI response creates one ProductRating record."""
        ratings_data = [
            {
                "source": "Whisky Advocate",
                "score": 92,
                "max_score": 100,
            }
        ]

        count = create_product_ratings(sample_product, ratings_data)

        assert count == 1
        assert ProductRating.objects.filter(product=sample_product).count() == 1

    def test_multiple_ratings_create_multiple_records(self, db, sample_product):
        """Multiple ratings create multiple ProductRating records."""
        ratings_data = [
            {"source": "Whisky Advocate", "score": 92, "max_score": 100},
            {"source": "Wine Enthusiast", "score": 94, "max_score": 100},
            {"source": "Jim Murray", "score": 88.5, "max_score": 100},
        ]

        count = create_product_ratings(sample_product, ratings_data)

        assert count == 3
        assert ProductRating.objects.filter(product=sample_product).count() == 3

    def test_rating_fields_mapped(self, db, sample_product):
        """All rating fields should be properly mapped."""
        ratings_data = [
            {
                "source": "Whisky Advocate",
                "source_country": "USA",
                "score": 92,
                "max_score": 100,
                "reviewer": "John Hansell",
                "review_url": "https://whiskyadvocate.com/review/123",
                "date": "2024-06-15",
                "review_count": 1,
            }
        ]

        create_product_ratings(sample_product, ratings_data)

        rating = ProductRating.objects.get(product=sample_product)
        assert rating.source == "Whisky Advocate"
        assert rating.source_country == "USA"
        assert rating.score == Decimal("92")
        assert rating.max_score == 100
        assert rating.reviewer == "John Hansell"
        assert rating.review_url == "https://whiskyadvocate.com/review/123"
        assert rating.date == date(2024, 6, 15)
        assert rating.review_count == 1

    def test_score_as_decimal(self, db, sample_product):
        """Scores should be stored as Decimal for precision."""
        ratings_data = [
            {"source": "Test Source", "score": 88.5, "max_score": 100},
        ]

        create_product_ratings(sample_product, ratings_data)

        rating = ProductRating.objects.get(product=sample_product)
        assert rating.score == Decimal("88.5")

    def test_score_from_string(self, db, sample_product):
        """Scores as strings should be converted to Decimal."""
        ratings_data = [
            {"source": "Test Source", "score": "92.5", "max_score": "100"},
        ]

        create_product_ratings(sample_product, ratings_data)

        rating = ProductRating.objects.get(product=sample_product)
        assert rating.score == Decimal("92.5")
        assert rating.max_score == 100

    def test_rating_count_updated(self, db, sample_product):
        """DiscoveredProduct.rating_count should be updated."""
        assert sample_product.rating_count == 0

        ratings_data = [
            {"source": "Source 1", "score": 90, "max_score": 100},
            {"source": "Source 2", "score": 85, "max_score": 100},
        ]

        create_product_ratings(sample_product, ratings_data)

        sample_product.refresh_from_db()
        assert sample_product.rating_count == 2

    def test_duplicate_ratings_prevented(self, db, sample_product):
        """Same rating from same source should not be duplicated."""
        ratings_data = [
            {"source": "Whisky Advocate", "score": 92, "max_score": 100},
        ]

        # Create first rating
        count1 = create_product_ratings(sample_product, ratings_data)
        assert count1 == 1

        # Try to create same rating again
        count2 = create_product_ratings(sample_product, ratings_data)
        assert count2 == 0  # No new ratings created

        # Should still only have 1 rating
        assert ProductRating.objects.filter(product=sample_product).count() == 1

    def test_missing_required_fields_skipped(self, db, sample_product):
        """Ratings missing required fields should be skipped."""
        ratings_data = [
            {"source": "Valid Source", "score": 90, "max_score": 100},  # Valid
            {"source": "Missing Score", "max_score": 100},  # Missing score
            {"score": 90, "max_score": 100},  # Missing source
            {"source": "Missing Max", "score": 90},  # Missing max_score
        ]

        count = create_product_ratings(sample_product, ratings_data)

        assert count == 1  # Only the valid one
        assert ProductRating.objects.filter(product=sample_product).count() == 1

    def test_null_ratings_data_returns_zero(self, db, sample_product):
        """None ratings_data should return 0."""
        count = create_product_ratings(sample_product, None)
        assert count == 0

    def test_empty_ratings_data_returns_zero(self, db, sample_product):
        """Empty list should return 0."""
        count = create_product_ratings(sample_product, [])
        assert count == 0

    def test_date_parsing(self, db, sample_product):
        """Date should be parsed from various formats."""
        ratings_data = [
            {"source": "Source 1", "score": 90, "max_score": 100, "date": "2024-06-15"},
        ]

        create_product_ratings(sample_product, ratings_data)

        rating = ProductRating.objects.get(product=sample_product)
        assert rating.date == date(2024, 6, 15)

    def test_invalid_date_handled_gracefully(self, db, sample_product):
        """Invalid date should not crash, just be None."""
        ratings_data = [
            {"source": "Source 1", "score": 90, "max_score": 100, "date": "invalid-date"},
        ]

        count = create_product_ratings(sample_product, ratings_data)

        assert count == 1
        rating = ProductRating.objects.get(product=sample_product)
        assert rating.date is None

    def test_different_max_scores(self, db, sample_product):
        """Different max_score values should be stored correctly."""
        ratings_data = [
            {"source": "100 Point Scale", "score": 92, "max_score": 100},
            {"source": "5 Star Scale", "score": 4.5, "max_score": 5},
            {"source": "10 Point Scale", "score": 8.5, "max_score": 10},
        ]

        create_product_ratings(sample_product, ratings_data)

        ratings = ProductRating.objects.filter(product=sample_product).order_by('source')

        r100 = ratings.get(source="100 Point Scale")
        assert r100.score == Decimal("92")
        assert r100.max_score == 100

        r5 = ratings.get(source="5 Star Scale")
        assert r5.score == Decimal("4.5")
        assert r5.max_score == 5

        r10 = ratings.get(source="10 Point Scale")
        assert r10.score == Decimal("8.5")
        assert r10.max_score == 10
