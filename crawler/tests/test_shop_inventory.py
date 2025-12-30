"""
Task Group 24: ShopInventory Model Tests

Tests for the ShopInventory model which tracks shop's owned inventory.
This model can be linked to DiscoveredProduct for comparison and gap analysis.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from crawler.models import (
    DiscoveredProduct,
    ShopInventory,
    ProductType,
    PriceTierChoices,
)


class TestShopInventoryCreation(TestCase):
    """Test ShopInventory model creation and basic functionality."""

    def test_inventory_creation(self):
        """
        Test that ShopInventory can be created with required fields.

        Required fields: product_name, product_type, sub_category,
        price_tier, current_stock, reorder_point
        """
        inventory = ShopInventory.objects.create(
            product_name="Glenfiddich 12 Year",
            product_type="whiskey",
            sub_category="scotch_single_malt",
            price_tier=PriceTierChoices.MID_RANGE,
            current_stock=24,
            reorder_point=6,
        )

        inventory.refresh_from_db()
        assert inventory.id is not None
        assert inventory.product_name == "Glenfiddich 12 Year"
        assert inventory.product_type == "whiskey"
        assert inventory.sub_category == "scotch_single_malt"
        assert inventory.price_tier == "mid_range"
        assert inventory.current_stock == 24
        assert inventory.reorder_point == 6
        assert inventory.is_active is True  # Default value

    def test_inventory_uuid_primary_key(self):
        """
        Test that ShopInventory uses UUID as primary key.
        """
        inventory = ShopInventory.objects.create(
            product_name="Buffalo Trace Bourbon",
            product_type="whiskey",
            sub_category="bourbon",
            price_tier=PriceTierChoices.VALUE,
            current_stock=48,
            reorder_point=12,
        )

        inventory.refresh_from_db()
        # UUID should be a 36-character string when converted
        assert len(str(inventory.id)) == 36
        assert "-" in str(inventory.id)  # UUIDs contain dashes


class TestMatchedProductLinking(TestCase):
    """Test matched_product FK relationship to DiscoveredProduct."""

    def setUp(self):
        """Create a DiscoveredProduct for linking tests."""
        self.discovered_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            extracted_data={
                "name": "Lagavulin 16 Year",
                "brand": "Lagavulin",
            },
        )

    def test_matched_product_fk_relationship(self):
        """
        Test that ShopInventory can be linked to DiscoveredProduct.

        matched_product: FK to DiscoveredProduct, nullable
        related_name: 'shop_inventory'
        """
        inventory = ShopInventory.objects.create(
            product_name="Lagavulin 16 Year",
            matched_product=self.discovered_product,
            product_type="whiskey",
            sub_category="scotch_single_malt",
            region="Islay",
            price_tier=PriceTierChoices.PREMIUM,
            current_stock=12,
            reorder_point=4,
        )

        inventory.refresh_from_db()
        assert inventory.matched_product == self.discovered_product
        assert inventory.matched_product_id == self.discovered_product.id

        # Test related_name access from DiscoveredProduct
        assert self.discovered_product.shop_inventory.count() == 1
        assert self.discovered_product.shop_inventory.first() == inventory

    def test_matched_product_nullable(self):
        """
        Test that matched_product can be null (not matched to any DiscoveredProduct).
        """
        inventory = ShopInventory.objects.create(
            product_name="Unknown Whisky",
            matched_product=None,  # Not matched
            product_type="whiskey",
            sub_category="other",
            price_tier=PriceTierChoices.BUDGET,
            current_stock=6,
            reorder_point=2,
        )

        inventory.refresh_from_db()
        assert inventory.matched_product is None
        assert inventory.matched_product_id is None


class TestStockManagementFields(TestCase):
    """Test stock management related fields."""

    def test_current_stock_and_reorder_point(self):
        """
        Test current_stock and reorder_point IntegerFields.
        """
        inventory = ShopInventory.objects.create(
            product_name="Taylor's 10 Year Tawny Port",
            product_type="port_wine",
            sub_category="tawny",
            price_tier=PriceTierChoices.MID_RANGE,
            current_stock=18,
            reorder_point=5,
        )

        inventory.refresh_from_db()
        assert inventory.current_stock == 18
        assert inventory.reorder_point == 5

        # Test stock below reorder point scenario
        inventory.current_stock = 3
        inventory.save()

        inventory.refresh_from_db()
        assert inventory.current_stock < inventory.reorder_point

    def test_monthly_sales_avg_decimal(self):
        """
        Test monthly_sales_avg DecimalField (nullable).
        """
        inventory = ShopInventory.objects.create(
            product_name="Maker's Mark Bourbon",
            product_type="whiskey",
            sub_category="bourbon",
            price_tier=PriceTierChoices.VALUE,
            current_stock=36,
            reorder_point=12,
            monthly_sales_avg=Decimal("8.50"),
        )

        inventory.refresh_from_db()
        assert inventory.monthly_sales_avg == Decimal("8.50")

    def test_monthly_sales_avg_nullable(self):
        """
        Test that monthly_sales_avg can be null.
        """
        inventory = ShopInventory.objects.create(
            product_name="New Arrival Whisky",
            product_type="whiskey",
            sub_category="other",
            price_tier=PriceTierChoices.MID_RANGE,
            current_stock=12,
            reorder_point=4,
            monthly_sales_avg=None,  # No sales data yet
        )

        inventory.refresh_from_db()
        assert inventory.monthly_sales_avg is None

    def test_last_restocked_datetime(self):
        """
        Test last_restocked DateTimeField (nullable).
        """
        restock_time = timezone.now() - timedelta(days=7)
        inventory = ShopInventory.objects.create(
            product_name="Grahams Six Grapes Port",
            product_type="port_wine",
            sub_category="ruby",
            price_tier=PriceTierChoices.VALUE,
            current_stock=24,
            reorder_point=8,
            last_restocked=restock_time,
        )

        inventory.refresh_from_db()
        # Compare with some tolerance
        time_diff = abs((inventory.last_restocked - restock_time).total_seconds())
        assert time_diff < 1

    def test_last_restocked_nullable(self):
        """
        Test that last_restocked can be null.
        """
        inventory = ShopInventory.objects.create(
            product_name="Brand New Item",
            product_type="whiskey",
            sub_category="bourbon",
            price_tier=PriceTierChoices.VALUE,
            current_stock=24,
            reorder_point=6,
            last_restocked=None,
        )

        inventory.refresh_from_db()
        assert inventory.last_restocked is None

    def test_is_active_default(self):
        """
        Test is_active BooleanField default value is True.
        """
        inventory = ShopInventory.objects.create(
            product_name="Active Product",
            product_type="whiskey",
            sub_category="scotch_blend",
            price_tier=PriceTierChoices.BUDGET,
            current_stock=48,
            reorder_point=12,
        )

        inventory.refresh_from_db()
        assert inventory.is_active is True

    def test_is_active_can_be_false(self):
        """
        Test is_active can be set to False for discontinued items.
        """
        inventory = ShopInventory.objects.create(
            product_name="Discontinued Product",
            product_type="port_wine",
            sub_category="vintage",
            price_tier=PriceTierChoices.LUXURY,
            current_stock=0,
            reorder_point=0,
            is_active=False,
        )

        inventory.refresh_from_db()
        assert inventory.is_active is False


class TestPriceTierAndRegion(TestCase):
    """Test price_tier choices and region field."""

    def test_price_tier_choices(self):
        """
        Test all price_tier choices are accepted.
        Reuses PriceTierChoices from Task Group 20.
        """
        price_tiers = [
            (PriceTierChoices.BUDGET, "budget"),
            (PriceTierChoices.VALUE, "value"),
            (PriceTierChoices.MID_RANGE, "mid_range"),
            (PriceTierChoices.PREMIUM, "premium"),
            (PriceTierChoices.ULTRA_PREMIUM, "ultra_premium"),
            (PriceTierChoices.LUXURY, "luxury"),
        ]

        for idx, (choice, expected_value) in enumerate(price_tiers):
            inventory = ShopInventory.objects.create(
                product_name=f"Product Tier {idx}",
                product_type="whiskey",
                sub_category="various",
                price_tier=choice,
                current_stock=10,
                reorder_point=2,
            )
            inventory.refresh_from_db()
            assert inventory.price_tier == expected_value

    def test_region_nullable(self):
        """
        Test region CharField can be null.
        """
        # With region
        inventory_with_region = ShopInventory.objects.create(
            product_name="Islay Whisky",
            product_type="whiskey",
            sub_category="scotch_single_malt",
            region="Islay",
            price_tier=PriceTierChoices.PREMIUM,
            current_stock=6,
            reorder_point=2,
        )
        inventory_with_region.refresh_from_db()
        assert inventory_with_region.region == "Islay"

        # Without region
        inventory_no_region = ShopInventory.objects.create(
            product_name="Blended Whisky",
            product_type="whiskey",
            sub_category="scotch_blend",
            region=None,
            price_tier=PriceTierChoices.VALUE,
            current_stock=24,
            reorder_point=6,
        )
        inventory_no_region.refresh_from_db()
        assert inventory_no_region.region is None
