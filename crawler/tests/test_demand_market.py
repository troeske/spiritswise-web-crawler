"""
Task Group 20: Demand Signal & Market Positioning Fields Tests

Tests for the demand signal and market positioning fields on DiscoveredProduct.
These fields enable inventory purchasing recommendations and market analysis.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from crawler.models import (
    DiscoveredProduct,
    ProductType,
    TrendDirectionChoices,
    PriceTierChoices,
    TargetAudienceChoices,
)


class TestDemandSignalFields(TestCase):
    """Test demand signal fields on DiscoveredProduct."""

    def test_trend_score_storage_and_validation(self):
        """
        Test that trend_score is stored correctly and validates range 1-100.

        trend_score represents calculated overall popularity score.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product1",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            trend_score=85,
        )

        product.refresh_from_db()
        assert product.trend_score == 85

    def test_trend_score_null_when_not_set(self):
        """
        Test that trend_score can be null (not yet calculated).
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product2",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # trend_score not set
        )

        product.refresh_from_db()
        assert product.trend_score is None

    def test_trend_direction_choices(self):
        """
        Test trend_direction accepts valid choices: rising, stable, declining.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product3",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            trend_direction=TrendDirectionChoices.RISING,
        )

        product.refresh_from_db()
        assert product.trend_direction == "rising"

        # Test stable
        product.trend_direction = TrendDirectionChoices.STABLE
        product.save()
        product.refresh_from_db()
        assert product.trend_direction == "stable"

        # Test declining
        product.trend_direction = TrendDirectionChoices.DECLINING
        product.save()
        product.refresh_from_db()
        assert product.trend_direction == "declining"

    def test_buzz_score_storage(self):
        """
        Test that buzz_score is stored correctly (1-100, nullable).

        buzz_score represents social media + press mention intensity.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product4",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            buzz_score=72,
        )

        product.refresh_from_db()
        assert product.buzz_score == 72

    def test_limited_edition_and_allocated_flags(self):
        """
        Test is_limited_edition and is_allocated boolean fields.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product5",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            is_limited_edition=True,
            is_allocated=True,
            batch_size=5000,
            release_year=2024,
        )

        product.refresh_from_db()
        assert product.is_limited_edition is True
        assert product.is_allocated is True
        assert product.batch_size == 5000
        assert product.release_year == 2024


class TestMarketPositioningFields(TestCase):
    """Test market positioning fields on DiscoveredProduct."""

    def test_price_tier_choices(self):
        """
        Test price_tier accepts all valid choices from PriceTierChoices.

        Price tiers: budget, value, mid_range, premium, ultra_premium, luxury
        """
        price_tiers = [
            (PriceTierChoices.BUDGET, "budget"),
            (PriceTierChoices.VALUE, "value"),
            (PriceTierChoices.MID_RANGE, "mid_range"),
            (PriceTierChoices.PREMIUM, "premium"),
            (PriceTierChoices.ULTRA_PREMIUM, "ultra_premium"),
            (PriceTierChoices.LUXURY, "luxury"),
        ]

        for choice, expected_value in price_tiers:
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/product_{expected_value}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
                price_tier=choice,
            )
            product.refresh_from_db()
            assert product.price_tier == expected_value, f"Expected {expected_value}, got {product.price_tier}"

    def test_target_audience_choices(self):
        """
        Test target_audience accepts all valid choices from TargetAudienceChoices.

        Target audiences: beginner, casual, enthusiast, collector, investor
        """
        audiences = [
            (TargetAudienceChoices.BEGINNER, "beginner"),
            (TargetAudienceChoices.CASUAL, "casual"),
            (TargetAudienceChoices.ENTHUSIAST, "enthusiast"),
            (TargetAudienceChoices.COLLECTOR, "collector"),
            (TargetAudienceChoices.INVESTOR, "investor"),
        ]

        for choice, expected_value in audiences:
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/product_aud_{expected_value}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
                target_audience=choice,
            )
            product.refresh_from_db()
            assert product.target_audience == expected_value

    def test_availability_score_range(self):
        """
        Test availability_score is stored correctly (1-10, nullable).

        10=widely available, 1=extremely rare/allocated
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product_avail",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            availability_score=7,
        )

        product.refresh_from_db()
        assert product.availability_score == 7


class TestAggregatedAvailabilityFields(TestCase):
    """Test aggregated availability fields on DiscoveredProduct."""

    def test_retailer_and_stock_counts(self):
        """
        Test retailer_count and in_stock_count default values and storage.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product_counts",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            retailer_count=5,
            in_stock_count=3,
        )

        product.refresh_from_db()
        assert product.retailer_count == 5
        assert product.in_stock_count == 3

    def test_retailer_count_default_is_zero(self):
        """
        Test that retailer_count defaults to 0.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product_default",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.retailer_count == 0
        assert product.in_stock_count == 0

    def test_price_aggregation_fields(self):
        """
        Test avg_price_usd, min_price_usd, max_price_usd, price_volatility storage.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product_prices",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            avg_price_usd=Decimal("85.99"),
            min_price_usd=Decimal("69.99"),
            max_price_usd=Decimal("109.99"),
            price_volatility=Decimal("12.50"),
        )

        product.refresh_from_db()
        assert product.avg_price_usd == Decimal("85.99")
        assert product.min_price_usd == Decimal("69.99")
        assert product.max_price_usd == Decimal("109.99")
        assert product.price_volatility == Decimal("12.50")

    def test_price_fields_nullable(self):
        """
        Test that price aggregation fields can be null.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product_no_prices",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # No price fields set
        )

        product.refresh_from_db()
        assert product.avg_price_usd is None
        assert product.min_price_usd is None
        assert product.max_price_usd is None
        assert product.price_volatility is None


class TestDemandMarketFieldsIntegration(TestCase):
    """Integration tests for demand signal and market positioning fields together."""

    def test_full_demand_market_profile(self):
        """
        Test creating a product with all demand/market fields populated.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/full_profile",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # Demand signal fields
            trend_score=88,
            trend_direction=TrendDirectionChoices.RISING,
            buzz_score=75,
            search_interest=1250,
            is_limited_edition=True,
            is_allocated=False,
            batch_size=10000,
            release_year=2024,
            # Market positioning fields
            price_tier=PriceTierChoices.PREMIUM,
            target_audience=TargetAudienceChoices.ENTHUSIAST,
            availability_score=6,
            # Aggregated availability fields
            retailer_count=12,
            in_stock_count=8,
            avg_price_usd=Decimal("149.99"),
            min_price_usd=Decimal("129.99"),
            max_price_usd=Decimal("179.99"),
            price_volatility=Decimal("15.50"),
        )

        product.refresh_from_db()

        # Verify all fields
        assert product.trend_score == 88
        assert product.trend_direction == "rising"
        assert product.buzz_score == 75
        assert product.search_interest == 1250
        assert product.is_limited_edition is True
        assert product.is_allocated is False
        assert product.batch_size == 10000
        assert product.release_year == 2024
        assert product.price_tier == "premium"
        assert product.target_audience == "enthusiast"
        assert product.availability_score == 6
        assert product.retailer_count == 12
        assert product.in_stock_count == 8
        assert product.avg_price_usd == Decimal("149.99")
        assert product.min_price_usd == Decimal("129.99")
        assert product.max_price_usd == Decimal("179.99")
        assert product.price_volatility == Decimal("15.50")
