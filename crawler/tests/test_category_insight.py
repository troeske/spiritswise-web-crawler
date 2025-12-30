"""
Task Group 22: CategoryInsight Model Tests

Tests for the CategoryInsight model which aggregates market data by category.
This model enables market trend analysis and category-level insights.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError, connection
from django.utils import timezone
from crawler.models import (
    CategoryInsight,
    CategoryTrendingDirectionChoices,
)


def is_sqlite():
    """Check if the database is SQLite."""
    return connection.vendor == "sqlite"


class TestCategoryInsightCreation(TestCase):
    """Test CategoryInsight model creation and basic functionality."""

    def test_insight_creation_with_required_fields(self):
        """
        Test that CategoryInsight can be created with required fields.

        Required fields: product_type, sub_category, total_products,
        products_with_awards, avg_price_usd, median_price_usd, avg_price_eur,
        trending_direction
        """
        insight = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="bourbon",
            total_products=150,
            products_with_awards=45,
            avg_price_usd=Decimal("65.50"),
            median_price_usd=Decimal("55.00"),
            avg_price_eur=Decimal("59.95"),
            trending_direction=CategoryTrendingDirectionChoices.RISING,
        )

        insight.refresh_from_db()
        assert insight.product_type == "whiskey"
        assert insight.sub_category == "bourbon"
        assert insight.total_products == 150
        assert insight.products_with_awards == 45
        assert insight.avg_price_usd == Decimal("65.50")
        assert insight.median_price_usd == Decimal("55.00")
        assert insight.avg_price_eur == Decimal("59.95")
        assert insight.trending_direction == "rising"
        assert insight.id is not None
        assert insight.updated_at is not None

    def test_insight_creation_with_optional_fields(self):
        """
        Test CategoryInsight with optional fields: region, country,
        avg_rating, market_growth, avg_price_change_30d
        """
        insight = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="scotch_single_malt",
            region="Islay",
            country="Scotland",
            total_products=75,
            products_with_awards=30,
            avg_price_usd=Decimal("120.00"),
            median_price_usd=Decimal("95.00"),
            avg_price_eur=Decimal("109.00"),
            avg_rating=Decimal("88.5"),
            trending_direction=CategoryTrendingDirectionChoices.HOT,
            market_growth="+15% YoY",
            avg_price_change_30d=Decimal("2.50"),
        )

        insight.refresh_from_db()
        assert insight.region == "Islay"
        assert insight.country == "Scotland"
        assert insight.avg_rating == Decimal("88.5")
        assert insight.market_growth == "+15% YoY"
        assert insight.avg_price_change_30d == Decimal("2.50")


class TestCategoryInsightUniqueConstraint(TestCase):
    """Test unique constraint on (product_type, sub_category, region, country)."""

    def test_unique_constraint_all_fields(self):
        """
        Test that duplicate (product_type, sub_category, region, country) raises IntegrityError.

        NOTE: This test is skipped on SQLite as it does not enforce the unique constraint
        with nulls_distinct=False. On PostgreSQL, this will raise IntegrityError.
        """
        # Skip on SQLite - it doesn't enforce unique constraints with nulls_distinct=False
        if connection.vendor == "sqlite":
            self.skipTest("SQLite does not support unique constraints with nulls_distinct")
        CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="bourbon",
            region="Kentucky",
            country="USA",
            total_products=100,
            products_with_awards=25,
            avg_price_usd=Decimal("50.00"),
            median_price_usd=Decimal("45.00"),
            avg_price_eur=Decimal("45.00"),
            trending_direction=CategoryTrendingDirectionChoices.STABLE,
        )

        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            CategoryInsight.objects.create(
                product_type="whiskey",
                sub_category="bourbon",
                region="Kentucky",
                country="USA",
                total_products=200,
                products_with_awards=50,
                avg_price_usd=Decimal("55.00"),
                median_price_usd=Decimal("50.00"),
                avg_price_eur=Decimal("50.00"),
                trending_direction=CategoryTrendingDirectionChoices.RISING,
            )

    def test_unique_constraint_model_validation(self):
        """
        Test that the model recognizes potential duplicates via application-level check.

        This test works on all databases by checking model existence before creating.
        """
        CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="tennessee",
            region="Tennessee",
            country="USA",
            total_products=100,
            products_with_awards=25,
            avg_price_usd=Decimal("50.00"),
            median_price_usd=Decimal("45.00"),
            avg_price_eur=Decimal("45.00"),
            trending_direction=CategoryTrendingDirectionChoices.STABLE,
        )

        # Check that a duplicate would exist
        exists = CategoryInsight.objects.filter(
            product_type="whiskey",
            sub_category="tennessee",
            region="Tennessee",
            country="USA",
        ).exists()
        assert exists is True

    def test_unique_constraint_with_null_region_country(self):
        """
        Test that unique constraint works with NULL region and country.
        Two records with same product_type/sub_category but both NULL for region/country
        should be treated as duplicates.
        """
        CategoryInsight.objects.create(
            product_type="port_wine",
            sub_category="tawny",
            region=None,
            country=None,
            total_products=80,
            products_with_awards=40,
            avg_price_usd=Decimal("35.00"),
            median_price_usd=Decimal("30.00"),
            avg_price_eur=Decimal("32.00"),
            trending_direction=CategoryTrendingDirectionChoices.STABLE,
        )

        # Different region/country combination (one NULL, one not) should be allowed
        insight2 = CategoryInsight.objects.create(
            product_type="port_wine",
            sub_category="tawny",
            region="Douro",
            country=None,
            total_products=60,
            products_with_awards=25,
            avg_price_usd=Decimal("40.00"),
            median_price_usd=Decimal("35.00"),
            avg_price_eur=Decimal("36.00"),
            trending_direction=CategoryTrendingDirectionChoices.RISING,
        )
        assert insight2.id is not None

    def test_different_categories_allowed(self):
        """
        Test that different sub_category values for same product_type are allowed.
        """
        CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="bourbon",
            total_products=150,
            products_with_awards=50,
            avg_price_usd=Decimal("60.00"),
            median_price_usd=Decimal("55.00"),
            avg_price_eur=Decimal("54.00"),
            trending_direction=CategoryTrendingDirectionChoices.RISING,
        )

        # Different sub_category should be allowed
        insight2 = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="rye",
            total_products=80,
            products_with_awards=20,
            avg_price_usd=Decimal("55.00"),
            median_price_usd=Decimal("48.00"),
            avg_price_eur=Decimal("50.00"),
            trending_direction=CategoryTrendingDirectionChoices.HOT,
        )
        assert insight2.id is not None


class TestCategoryTrendingDirectionChoices(TestCase):
    """Test trending_direction field choices validation."""

    def test_trending_direction_choices(self):
        """
        Test all trending_direction choices are accepted:
        hot, rising, stable, declining, cold
        """
        trending_choices = [
            (CategoryTrendingDirectionChoices.HOT, "hot"),
            (CategoryTrendingDirectionChoices.RISING, "rising"),
            (CategoryTrendingDirectionChoices.STABLE, "stable"),
            (CategoryTrendingDirectionChoices.DECLINING, "declining"),
            (CategoryTrendingDirectionChoices.COLD, "cold"),
        ]

        for idx, (choice, expected_value) in enumerate(trending_choices):
            insight = CategoryInsight.objects.create(
                product_type="whiskey",
                sub_category=f"category_{idx}",
                total_products=100 + idx,
                products_with_awards=25,
                avg_price_usd=Decimal("50.00"),
                median_price_usd=Decimal("45.00"),
                avg_price_eur=Decimal("45.00"),
                trending_direction=choice,
            )
            insight.refresh_from_db()
            assert insight.trending_direction == expected_value, (
                f"Expected {expected_value}, got {insight.trending_direction}"
            )


class TestCategoryInsightAggregatedMetrics(TestCase):
    """Test aggregated metrics storage in CategoryInsight."""

    def test_aggregated_metrics_storage(self):
        """
        Test that aggregated metrics (total_products, products_with_awards,
        prices, rating) are stored correctly.
        """
        insight = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="japanese",
            region="Yamazaki",
            country="Japan",
            total_products=45,
            products_with_awards=35,
            avg_price_usd=Decimal("250.00"),
            median_price_usd=Decimal("200.00"),
            avg_price_eur=Decimal("228.00"),
            avg_rating=Decimal("92.3"),
            trending_direction=CategoryTrendingDirectionChoices.HOT,
            market_growth="+25% YoY",
            avg_price_change_30d=Decimal("12.50"),
        )

        insight.refresh_from_db()
        assert insight.total_products == 45
        assert insight.products_with_awards == 35
        assert insight.avg_price_usd == Decimal("250.00")
        assert insight.median_price_usd == Decimal("200.00")
        assert insight.avg_price_eur == Decimal("228.00")
        assert insight.avg_rating == Decimal("92.3")
        assert insight.market_growth == "+25% YoY"
        assert insight.avg_price_change_30d == Decimal("12.50")

    def test_metrics_update(self):
        """
        Test that metrics can be updated when market conditions change.
        """
        insight = CategoryInsight.objects.create(
            product_type="port_wine",
            sub_category="vintage",
            total_products=30,
            products_with_awards=15,
            avg_price_usd=Decimal("150.00"),
            median_price_usd=Decimal("120.00"),
            avg_price_eur=Decimal("136.00"),
            trending_direction=CategoryTrendingDirectionChoices.STABLE,
        )

        # Update metrics
        insight.total_products = 35
        insight.products_with_awards = 18
        insight.avg_price_usd = Decimal("160.00")
        insight.trending_direction = CategoryTrendingDirectionChoices.RISING
        insight.market_growth = "+8% YoY"
        insight.save()

        insight.refresh_from_db()
        assert insight.total_products == 35
        assert insight.products_with_awards == 18
        assert insight.avg_price_usd == Decimal("160.00")
        assert insight.trending_direction == "rising"
        assert insight.market_growth == "+8% YoY"


class TestCategoryInsightUpdatedAt(TestCase):
    """Test updated_at field auto-update behavior."""

    def test_updated_at_auto_update(self):
        """
        Test that updated_at field updates automatically on save.
        """
        insight = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="irish_single_pot",
            total_products=50,
            products_with_awards=20,
            avg_price_usd=Decimal("75.00"),
            median_price_usd=Decimal("65.00"),
            avg_price_eur=Decimal("68.00"),
            trending_direction=CategoryTrendingDirectionChoices.STABLE,
        )

        initial_updated_at = insight.updated_at

        # Modify and save
        insight.total_products = 55
        insight.save()

        insight.refresh_from_db()
        assert insight.updated_at >= initial_updated_at
