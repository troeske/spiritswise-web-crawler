"""
Task Group 23: PurchaseRecommendation Model Tests

Tests for the PurchaseRecommendation model which captures AI-generated
purchasing suggestions for inventory management.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from crawler.models import (
    DiscoveredProduct,
    PurchaseRecommendation,
    ProductType,
    RecommendationTierChoices,
    MarginPotentialChoices,
    TurnoverEstimateChoices,
    RiskLevelChoices,
    OutcomeChoices,
)


class TestPurchaseRecommendationCreation(TestCase):
    """Test PurchaseRecommendation model creation and basic functionality."""

    def setUp(self):
        """Create a base product for recommendation testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_recommendation_creation(self):
        """
        Test that PurchaseRecommendation can be created with required fields.

        Required fields: product, recommendation_score, recommendation_tier,
        recommendation_reason
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=85,
            recommendation_tier=RecommendationTierChoices.MUST_STOCK,
            recommendation_reason="High demand product with excellent reviews and competitive pricing.",
        )

        recommendation.refresh_from_db()
        assert recommendation.product_id == self.product.id
        assert recommendation.recommendation_score == 85
        assert recommendation.recommendation_tier == "must_stock"
        assert "High demand product" in recommendation.recommendation_reason
        assert recommendation.id is not None
        assert recommendation.created_at is not None
        assert recommendation.is_active is True

    def test_recommendation_fk_relationship(self):
        """
        Test that PurchaseRecommendation has correct FK relationship to DiscoveredProduct.

        related_name should be 'recommendations' on the product side.
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=75,
            recommendation_tier=RecommendationTierChoices.RECOMMENDED,
            recommendation_reason="Good value product for mid-range customers.",
        )

        # Test related_name access
        assert self.product.recommendations.count() == 1
        assert self.product.recommendations.first() == recommendation


class TestRecommendationTierChoices(TestCase):
    """Test recommendation_tier field choices validation."""

    def setUp(self):
        """Create a base product for tier testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/tier-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_recommendation_tier_choices(self):
        """
        Test all recommendation_tier choices are accepted:
        must_stock, recommended, consider, watch, skip
        """
        tier_choices = [
            (RecommendationTierChoices.MUST_STOCK, "must_stock"),
            (RecommendationTierChoices.RECOMMENDED, "recommended"),
            (RecommendationTierChoices.CONSIDER, "consider"),
            (RecommendationTierChoices.WATCH, "watch"),
            (RecommendationTierChoices.SKIP, "skip"),
        ]

        for idx, (choice, expected_value) in enumerate(tier_choices):
            recommendation = PurchaseRecommendation.objects.create(
                product=self.product,
                recommendation_score=100 - (idx * 15),  # Vary scores
                recommendation_tier=choice,
                recommendation_reason=f"Test reason for {expected_value} tier.",
            )
            recommendation.refresh_from_db()
            assert recommendation.recommendation_tier == expected_value, (
                f"Expected {expected_value}, got {recommendation.recommendation_tier}"
            )


class TestScoringFactors(TestCase):
    """Test scoring factor fields (demand, quality, value, uniqueness, trend)."""

    def setUp(self):
        """Create a base product for scoring testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/scoring-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_scoring_factors_storage(self):
        """
        Test that scoring factors (1-10 range) are stored correctly:
        demand_score, quality_score, value_score, uniqueness_score, trend_score_factor
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=88,
            recommendation_tier=RecommendationTierChoices.MUST_STOCK,
            recommendation_reason="Excellent scores across all factors.",
            demand_score=9,
            quality_score=8,
            value_score=7,
            uniqueness_score=10,
            trend_score_factor=8,
        )

        recommendation.refresh_from_db()
        assert recommendation.demand_score == 9
        assert recommendation.quality_score == 8
        assert recommendation.value_score == 7
        assert recommendation.uniqueness_score == 10
        assert recommendation.trend_score_factor == 8

    def test_business_factors_storage(self):
        """
        Test business factor fields:
        category_gap_fill, complements_existing (BooleanFields)
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=72,
            recommendation_tier=RecommendationTierChoices.RECOMMENDED,
            recommendation_reason="Fills gap in Japanese whiskey category.",
            category_gap_fill=True,
            complements_existing=False,
        )

        recommendation.refresh_from_db()
        assert recommendation.category_gap_fill is True
        assert recommendation.complements_existing is False

    def test_margin_potential_choices(self):
        """
        Test margin_potential choices: low, medium, high, premium
        """
        margin_choices = [
            (MarginPotentialChoices.LOW, "low"),
            (MarginPotentialChoices.MEDIUM, "medium"),
            (MarginPotentialChoices.HIGH, "high"),
            (MarginPotentialChoices.PREMIUM, "premium"),
        ]

        for idx, (choice, expected_value) in enumerate(margin_choices):
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/margin-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
            )
            recommendation = PurchaseRecommendation.objects.create(
                product=product,
                recommendation_score=70 + idx,
                recommendation_tier=RecommendationTierChoices.CONSIDER,
                recommendation_reason=f"Test margin {expected_value}.",
                margin_potential=choice,
            )
            recommendation.refresh_from_db()
            assert recommendation.margin_potential == expected_value

    def test_turnover_estimate_choices(self):
        """
        Test turnover_estimate choices: slow, moderate, fast, very_fast
        """
        turnover_choices = [
            (TurnoverEstimateChoices.SLOW, "slow"),
            (TurnoverEstimateChoices.MODERATE, "moderate"),
            (TurnoverEstimateChoices.FAST, "fast"),
            (TurnoverEstimateChoices.VERY_FAST, "very_fast"),
        ]

        for idx, (choice, expected_value) in enumerate(turnover_choices):
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/turnover-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
            )
            recommendation = PurchaseRecommendation.objects.create(
                product=product,
                recommendation_score=65 + idx,
                recommendation_tier=RecommendationTierChoices.CONSIDER,
                recommendation_reason=f"Test turnover {expected_value}.",
                turnover_estimate=choice,
            )
            recommendation.refresh_from_db()
            assert recommendation.turnover_estimate == expected_value

    def test_risk_level_choices(self):
        """
        Test risk_level choices: low, medium, high
        """
        risk_choices = [
            (RiskLevelChoices.LOW, "low"),
            (RiskLevelChoices.MEDIUM, "medium"),
            (RiskLevelChoices.HIGH, "high"),
        ]

        for idx, (choice, expected_value) in enumerate(risk_choices):
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/risk-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
            )
            recommendation = PurchaseRecommendation.objects.create(
                product=product,
                recommendation_score=60 + idx,
                recommendation_tier=RecommendationTierChoices.WATCH,
                recommendation_reason=f"Test risk {expected_value}.",
                risk_level=choice,
            )
            recommendation.refresh_from_db()
            assert recommendation.risk_level == expected_value


class TestExpirationHandling(TestCase):
    """Test expiration and active status handling."""

    def setUp(self):
        """Create a base product for expiration testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/expiration-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_expires_at_field(self):
        """
        Test that expires_at DateTimeField is stored correctly.
        """
        future_date = timezone.now() + timedelta(days=30)
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=80,
            recommendation_tier=RecommendationTierChoices.RECOMMENDED,
            recommendation_reason="Recommendation valid for 30 days.",
            expires_at=future_date,
        )

        recommendation.refresh_from_db()
        # Compare with some tolerance
        time_diff = abs((recommendation.expires_at - future_date).total_seconds())
        assert time_diff < 1  # Within 1 second

    def test_expires_at_nullable(self):
        """
        Test that expires_at can be null (recommendation doesn't expire).
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=90,
            recommendation_tier=RecommendationTierChoices.MUST_STOCK,
            recommendation_reason="Evergreen recommendation.",
            expires_at=None,
        )

        recommendation.refresh_from_db()
        assert recommendation.expires_at is None

    def test_is_active_default_true(self):
        """
        Test that is_active defaults to True.
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=75,
            recommendation_tier=RecommendationTierChoices.CONSIDER,
            recommendation_reason="Active recommendation.",
        )

        recommendation.refresh_from_db()
        assert recommendation.is_active is True

    def test_is_active_can_be_disabled(self):
        """
        Test that is_active can be set to False.
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=60,
            recommendation_tier=RecommendationTierChoices.SKIP,
            recommendation_reason="Disabled recommendation.",
            is_active=False,
        )

        recommendation.refresh_from_db()
        assert recommendation.is_active is False


class TestOutcomeTracking(TestCase):
    """Test outcome tracking for ML improvement."""

    def setUp(self):
        """Create a base product for outcome testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/outcome-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_acted_upon_default_false(self):
        """
        Test that acted_upon defaults to False.
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=85,
            recommendation_tier=RecommendationTierChoices.MUST_STOCK,
            recommendation_reason="Pending action.",
        )

        recommendation.refresh_from_db()
        assert recommendation.acted_upon is False

    def test_outcome_choices(self):
        """
        Test outcome choices: success, moderate, poor
        """
        outcome_choices = [
            (OutcomeChoices.SUCCESS, "success"),
            (OutcomeChoices.MODERATE, "moderate"),
            (OutcomeChoices.POOR, "poor"),
        ]

        for idx, (choice, expected_value) in enumerate(outcome_choices):
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/outcome-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
            )
            recommendation = PurchaseRecommendation.objects.create(
                product=product,
                recommendation_score=75,
                recommendation_tier=RecommendationTierChoices.RECOMMENDED,
                recommendation_reason=f"Outcome test {expected_value}.",
                acted_upon=True,
                outcome=choice,
            )
            recommendation.refresh_from_db()
            assert recommendation.acted_upon is True
            assert recommendation.outcome == expected_value

    def test_outcome_nullable(self):
        """
        Test that outcome can be null (not yet determined).
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=70,
            recommendation_tier=RecommendationTierChoices.CONSIDER,
            recommendation_reason="Outcome pending.",
            acted_upon=True,
            outcome=None,
        )

        recommendation.refresh_from_db()
        assert recommendation.outcome is None


class TestSuggestionFields(TestCase):
    """Test suggestion fields for actionable recommendations."""

    def setUp(self):
        """Create a base product for suggestion testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/suggestion-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_suggestion_fields_storage(self):
        """
        Test that suggestion fields are stored correctly:
        suggested_quantity, suggested_retail_price, estimated_margin_percent, reorder_threshold
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=92,
            recommendation_tier=RecommendationTierChoices.MUST_STOCK,
            recommendation_reason="Full recommendation with suggestions.",
            suggested_quantity=12,
            suggested_retail_price=Decimal("89.99"),
            estimated_margin_percent=Decimal("35.5"),
            reorder_threshold=3,
        )

        recommendation.refresh_from_db()
        assert recommendation.suggested_quantity == 12
        assert recommendation.suggested_retail_price == Decimal("89.99")
        assert recommendation.estimated_margin_percent == Decimal("35.5")
        assert recommendation.reorder_threshold == 3

    def test_suggestion_fields_nullable(self):
        """
        Test that all suggestion fields can be null.
        """
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=65,
            recommendation_tier=RecommendationTierChoices.WATCH,
            recommendation_reason="Minimal recommendation without suggestions.",
            # All suggestion fields left unset
        )

        recommendation.refresh_from_db()
        assert recommendation.suggested_quantity is None
        assert recommendation.suggested_retail_price is None
        assert recommendation.estimated_margin_percent is None
        assert recommendation.reorder_threshold is None
