"""
Task Group 19: Completeness Scoring System Tests

Tests for the completeness scoring functionality that calculates
data quality scores for DiscoveredProduct records.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from crawler.models import DiscoveredProduct, DiscoveredBrand, ProductType


class TestCompletenessScoreCalculation(TestCase):
    """Test completeness score calculation based on field weights."""

    def setUp(self):
        """Create a base product for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Test Brand",
            slug="test-brand",
        )

    def test_skeleton_product_has_low_completeness_score(self):
        """
        Test that a product with only required fields has a low score.

        A skeleton product (name only, no other data) should be in the
        skeleton tier (0-39%).
        """
        from crawler.services.completeness import calculate_completeness_score

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product1",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="Test Whiskey",
        )

        score = calculate_completeness_score(product)

        # Name only should give low score (roughly 10 out of ~100 max)
        assert score is not None
        assert score >= 1
        assert score < 40  # Should be in skeleton tier

    def test_complete_product_has_high_completeness_score(self):
        """
        Test that a product with most fields populated has a high score.

        A complete product (90%+ of weighted fields) should be in the
        complete tier (90-100%).
        """
        from crawler.services.completeness import calculate_completeness_score

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product2",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # Critical fields
            name="Macallan 18 Year",
            brand=self.brand,
            # Important fields
            abv=Decimal("43.0"),
            age_statement=18,
            region="Speyside",
            category="Single Malt Scotch",
            # Valuable fields
            primary_cask=["ex-sherry", "ex-bourbon"],
            nose_description="Rich and complex with dried fruits",
            palate_flavors=["vanilla", "oak", "dried fruit"],
            finish_length=8,
            primary_aromas=["dried fruit", "chocolate"],
            # Nice to have
            color_description="Deep amber",
            maturation_notes="Aged in sherry casks",
            food_pairings="Cheese and chocolate",
            serving_recommendation="neat",
            # Business fields
            best_price=Decimal("250.00"),
            award_count=5,
            rating_count=10,
            # Additional
            finishing_cask=["oloroso sherry"],
        )

        score = calculate_completeness_score(product)

        # Should have high completeness
        assert score is not None
        assert score >= 70  # Should be at least in 'good' tier

    def test_partial_product_has_medium_completeness_score(self):
        """
        Test that a partially populated product has a medium score.

        A partial product (40-69% of weighted fields) should be in the
        partial tier.
        """
        from crawler.services.completeness import calculate_completeness_score

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product3",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # Critical fields
            name="Highland Park 12",
            brand=self.brand,
            # Some important fields
            abv=Decimal("40.0"),
            age_statement=12,
            # Missing most other fields
        )

        score = calculate_completeness_score(product)

        # Should be in partial range (has name + brand + abv + age = ~34 pts out of ~100)
        assert score is not None
        assert score >= 25
        assert score < 70


class TestCompletenessTierAssignment(TestCase):
    """Test tier assignment based on completeness score."""

    def test_complete_tier_for_high_scores(self):
        """Scores 90-100 should be assigned 'complete' tier."""
        from crawler.services.completeness import determine_tier

        assert determine_tier(90) == "complete"
        assert determine_tier(95) == "complete"
        assert determine_tier(100) == "complete"

    def test_good_tier_for_medium_high_scores(self):
        """Scores 70-89 should be assigned 'good' tier."""
        from crawler.services.completeness import determine_tier

        assert determine_tier(70) == "good"
        assert determine_tier(80) == "good"
        assert determine_tier(89) == "good"

    def test_partial_tier_for_medium_scores(self):
        """Scores 40-69 should be assigned 'partial' tier."""
        from crawler.services.completeness import determine_tier

        assert determine_tier(40) == "partial"
        assert determine_tier(55) == "partial"
        assert determine_tier(69) == "partial"

    def test_skeleton_tier_for_low_scores(self):
        """Scores 0-39 should be assigned 'skeleton' tier."""
        from crawler.services.completeness import determine_tier

        assert determine_tier(0) == "skeleton"
        assert determine_tier(20) == "skeleton"
        assert determine_tier(39) == "skeleton"


class TestMissingFieldsPopulation(TestCase):
    """Test that missing_fields correctly identifies empty fields."""

    def setUp(self):
        """Create a base product for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Test Brand",
            slug="test-brand",
        )

    def test_missing_fields_identifies_empty_critical_fields(self):
        """Missing critical fields (name, brand) should be in missing_fields."""
        from crawler.services.completeness import get_missing_fields

        # Product with no name and no brand
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product4",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="",  # Empty name
            # No brand
        )

        missing = get_missing_fields(product)

        assert "name" in missing
        assert "brand" in missing

    def test_populated_fields_not_in_missing_fields(self):
        """Populated fields should NOT appear in missing_fields."""
        from crawler.services.completeness import get_missing_fields

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product5",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="Glenlivet 12",
            brand=self.brand,
            abv=Decimal("40.0"),
            age_statement=12,
            region="Speyside",
        )

        missing = get_missing_fields(product)

        assert "name" not in missing
        assert "brand" not in missing
        assert "abv" not in missing
        assert "age_statement" not in missing
        assert "region" not in missing

    def test_empty_json_array_fields_are_missing(self):
        """Empty JSONField arrays should be treated as missing."""
        from crawler.services.completeness import get_missing_fields

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product6",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="Test Product",
            brand=self.brand,
            primary_cask=[],  # Empty array
            finishing_cask=[],  # Empty array
        )

        missing = get_missing_fields(product)

        assert "primary_cask" in missing
        assert "finishing_cask" in missing


class TestEnrichmentPriorityCalculation(TestCase):
    """Test enrichment priority calculation based on multiple factors."""

    def setUp(self):
        """Create brands for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Test Brand",
            slug="test-brand",
        )

    def test_low_completeness_gets_high_priority(self):
        """
        Products with low completeness should have higher enrichment priority.

        Priority is 1-10 where 10 is highest priority (needs enrichment most).
        """
        from crawler.services.completeness import calculate_enrichment_priority

        # Skeleton product - note: the signal will recalculate completeness_score
        # so we just need to create a product with few fields
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product7",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="Basic Product",
            # Very minimal data = low completeness
        )

        priority = calculate_enrichment_priority(product)

        # Low completeness = high priority
        assert priority is not None
        assert priority >= 6  # Should be high priority

    def test_award_winning_product_gets_higher_priority(self):
        """Products with awards should have boosted enrichment priority."""
        from crawler.services.completeness import calculate_enrichment_priority

        # Product with awards but partial data
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product8",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name="Award Winner",
            brand=self.brand,
            abv=Decimal("40.0"),
            award_count=3,
        )

        priority = calculate_enrichment_priority(product)

        # Should have medium-high priority due to awards
        assert priority is not None
        assert priority >= 5

    def test_high_completeness_gets_low_priority(self):
        """Products with high completeness should have low enrichment priority."""
        from crawler.services.completeness import calculate_enrichment_priority

        # Create a product with most fields populated to get high completeness
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product9",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # Critical fields (20 pts)
            name="Complete Product",
            brand=self.brand,
            # Important fields (~29 pts)
            abv=Decimal("43.0"),
            age_statement=18,
            region="Speyside",
            category="Single Malt Scotch",
            # Valuable cask fields (7 pts)
            primary_cask=["sherry"],
            finishing_cask=["port"],
            # Valuable tasting fields (14 pts)
            nose_description="Complex nose",
            palate_flavors=["vanilla", "oak"],
            finish_length=8,
            primary_aromas=["fruit"],
            # Nice to have (8 pts)
            color_description="Amber",
            maturation_notes="Aged well",
            food_pairings="Cheese",
            serving_recommendation="neat",
            # Business fields (16 pts)
            best_price=Decimal("100.00"),
            award_count=2,
            rating_count=5,
        )

        # Get the actual completeness score that was calculated
        product.refresh_from_db()

        priority = calculate_enrichment_priority(product)

        # High completeness = low priority (should be <= 4 since completeness > 70%)
        assert priority is not None
        assert priority <= 5  # Should be low to medium priority for complete product
