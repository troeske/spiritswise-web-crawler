"""
Task Group 21: ProductAvailability Model Tests

Tests for the ProductAvailability model which tracks product stock across retailers.
This model enables real-time availability monitoring and price change detection.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save, post_delete
from crawler.models import (
    DiscoveredProduct,
    ProductAvailability,
    ProductType,
    StockLevelChoices,
)
from crawler.signals import (
    update_product_availability_aggregates_on_save,
    update_product_availability_aggregates_on_delete,
)


class TestProductAvailabilityCreation(TestCase):
    """Test ProductAvailability model creation and basic functionality."""

    def setUp(self):
        """Create a base product for availability testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_availability_creation(self):
        """
        Test that ProductAvailability can be created with required fields.

        Required fields: product, retailer, retailer_url, retailer_country,
        in_stock, stock_level, price, currency, last_checked
        """
        now = timezone.now()
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="Total Wine & More",
            retailer_url="https://totalwine.com/glenfiddich-12",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("49.99"),
            currency="USD",
            last_checked=now,
        )

        availability.refresh_from_db()
        assert availability.product_id == self.product.id
        assert availability.retailer == "Total Wine & More"
        assert availability.retailer_url == "https://totalwine.com/glenfiddich-12"
        assert availability.retailer_country == "USA"
        assert availability.in_stock is True
        assert availability.stock_level == "in_stock"
        assert availability.price == Decimal("49.99")
        assert availability.currency == "USD"
        assert availability.last_checked is not None

    def test_availability_fk_relationship(self):
        """
        Test that ProductAvailability has correct FK relationship to DiscoveredProduct.

        related_name should be 'availability' on the product side.
        """
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="Whisky Exchange",
            retailer_url="https://thewhiskyexchange.com/product",
            retailer_country="UK",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("42.50"),
            currency="GBP",
            last_checked=timezone.now(),
        )

        # Test related_name access
        assert self.product.availability.count() == 1
        assert self.product.availability.first() == availability


class TestStockLevelChoices(TestCase):
    """Test stock_level field choices validation."""

    def setUp(self):
        """Create a base product for stock level testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/stock-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_stock_level_choices(self):
        """
        Test all stock_level choices are accepted:
        in_stock, low_stock, out_of_stock, pre_order, discontinued
        """
        stock_levels = [
            (StockLevelChoices.IN_STOCK, "in_stock"),
            (StockLevelChoices.LOW_STOCK, "low_stock"),
            (StockLevelChoices.OUT_OF_STOCK, "out_of_stock"),
            (StockLevelChoices.PRE_ORDER, "pre_order"),
            (StockLevelChoices.DISCONTINUED, "discontinued"),
        ]

        for idx, (choice, expected_value) in enumerate(stock_levels):
            availability = ProductAvailability.objects.create(
                product=self.product,
                retailer=f"Retailer_{idx}",
                retailer_url=f"https://example.com/{expected_value}",
                retailer_country="USA",
                in_stock=(choice == StockLevelChoices.IN_STOCK or choice == StockLevelChoices.LOW_STOCK),
                stock_level=choice,
                price=Decimal("50.00"),
                currency="USD",
                last_checked=timezone.now(),
            )
            availability.refresh_from_db()
            assert availability.stock_level == expected_value, f"Expected {expected_value}, got {availability.stock_level}"


class TestPriceChangeTracking(TestCase):
    """Test price change tracking functionality."""

    def setUp(self):
        """Create a base product for price tracking testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/price-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_price_change_tracking_fields(self):
        """
        Test price_changed and previous_price fields for tracking price changes.

        price_changed: BooleanField default False
        previous_price: DecimalField nullable
        """
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="MasterofMalt",
            retailer_url="https://masterofmalt.com/product",
            retailer_country="UK",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("55.00"),
            currency="GBP",
            last_checked=timezone.now(),
            price_changed=False,
            previous_price=None,
        )

        availability.refresh_from_db()
        assert availability.price_changed is False
        assert availability.previous_price is None

        # Simulate price change
        availability.previous_price = availability.price
        availability.price = Decimal("59.99")
        availability.price_changed = True
        availability.save()

        availability.refresh_from_db()
        assert availability.price == Decimal("59.99")
        assert availability.previous_price == Decimal("55.00")
        assert availability.price_changed is True

    def test_multi_currency_price_fields(self):
        """
        Test price_usd and price_eur nullable fields for normalized comparison.
        """
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="Whisky Auction",
            retailer_url="https://whiskyauction.com/product",
            retailer_country="UK",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("45.00"),
            currency="GBP",
            price_usd=Decimal("57.15"),
            price_eur=Decimal("52.65"),
            last_checked=timezone.now(),
        )

        availability.refresh_from_db()
        assert availability.price == Decimal("45.00")
        assert availability.currency == "GBP"
        assert availability.price_usd == Decimal("57.15")
        assert availability.price_eur == Decimal("52.65")

    def test_price_fields_nullable(self):
        """
        Test that price_usd and price_eur can be null.
        """
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="Local Shop",
            retailer_url="https://localshop.com/product",
            retailer_country="Germany",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("42.99"),
            currency="EUR",
            last_checked=timezone.now(),
            # price_usd and price_eur not set
        )

        availability.refresh_from_db()
        assert availability.price_usd is None
        assert availability.price_eur is None


class TestLastCheckedUpdates(TestCase):
    """Test last_checked field functionality."""

    def setUp(self):
        """Create a base product for last_checked testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/checked-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_last_checked_storage(self):
        """
        Test that last_checked DateTimeField stores correctly.
        """
        check_time = timezone.now()
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="BevMo",
            retailer_url="https://bevmo.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("39.99"),
            currency="USD",
            last_checked=check_time,
        )

        availability.refresh_from_db()
        # Compare with some tolerance for microseconds
        time_diff = abs((availability.last_checked - check_time).total_seconds())
        assert time_diff < 1  # Within 1 second

    def test_last_checked_update(self):
        """
        Test that last_checked can be updated for re-checks.
        """
        initial_time = timezone.now() - timedelta(hours=1)
        availability = ProductAvailability.objects.create(
            product=self.product,
            retailer="ReserveBar",
            retailer_url="https://reservebar.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("89.99"),
            currency="USD",
            last_checked=initial_time,
        )

        # Update last_checked
        new_check_time = timezone.now()
        availability.last_checked = new_check_time
        availability.save()

        availability.refresh_from_db()
        assert availability.last_checked > initial_time


class TestAvailabilityAggregationSignal(TestCase):
    """Test signal that updates DiscoveredProduct aggregates on ProductAvailability changes."""

    @classmethod
    def setUpClass(cls):
        """Connect signals before tests."""
        super().setUpClass()
        # Manually connect signals for this test class
        post_save.connect(
            update_product_availability_aggregates_on_save,
            sender=ProductAvailability,
            dispatch_uid="test_availability_save",
        )
        post_delete.connect(
            update_product_availability_aggregates_on_delete,
            sender=ProductAvailability,
            dispatch_uid="test_availability_delete",
        )

    @classmethod
    def tearDownClass(cls):
        """Disconnect signals after tests."""
        post_save.disconnect(
            update_product_availability_aggregates_on_save,
            sender=ProductAvailability,
            dispatch_uid="test_availability_save",
        )
        post_delete.disconnect(
            update_product_availability_aggregates_on_delete,
            sender=ProductAvailability,
            dispatch_uid="test_availability_delete",
        )
        super().tearDownClass()

    def setUp(self):
        """Create a base product for aggregation testing."""
        self.product = DiscoveredProduct.objects.create(
            source_url="https://example.com/aggregation-test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

    def test_retailer_count_updates_on_save(self):
        """
        Test that DiscoveredProduct.retailer_count updates when ProductAvailability is saved.
        """
        assert self.product.retailer_count == 0

        # Add first availability
        ProductAvailability.objects.create(
            product=self.product,
            retailer="Retailer A",
            retailer_url="https://a.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("50.00"),
            currency="USD",
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.retailer_count == 1

        # Add second availability
        ProductAvailability.objects.create(
            product=self.product,
            retailer="Retailer B",
            retailer_url="https://b.com/product",
            retailer_country="USA",
            in_stock=False,
            stock_level=StockLevelChoices.OUT_OF_STOCK,
            price=Decimal("55.00"),
            currency="USD",
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.retailer_count == 2

    def test_in_stock_count_updates(self):
        """
        Test that DiscoveredProduct.in_stock_count updates based on in_stock=True count.
        """
        assert self.product.in_stock_count == 0

        # Add in-stock availability
        avail1 = ProductAvailability.objects.create(
            product=self.product,
            retailer="In Stock Retailer",
            retailer_url="https://instock.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("45.00"),
            currency="USD",
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.in_stock_count == 1

        # Add out-of-stock availability
        ProductAvailability.objects.create(
            product=self.product,
            retailer="Out of Stock Retailer",
            retailer_url="https://outofstock.com/product",
            retailer_country="USA",
            in_stock=False,
            stock_level=StockLevelChoices.OUT_OF_STOCK,
            price=Decimal("50.00"),
            currency="USD",
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.retailer_count == 2
        assert self.product.in_stock_count == 1

    def test_price_aggregates_update(self):
        """
        Test that avg_price_usd, min_price_usd, max_price_usd update on save.
        """
        # Add first availability with USD price
        ProductAvailability.objects.create(
            product=self.product,
            retailer="Price Test A",
            retailer_url="https://a.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("50.00"),
            currency="USD",
            price_usd=Decimal("50.00"),
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.min_price_usd == Decimal("50.00")
        assert self.product.max_price_usd == Decimal("50.00")

        # Add second availability with different price
        ProductAvailability.objects.create(
            product=self.product,
            retailer="Price Test B",
            retailer_url="https://b.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("70.00"),
            currency="USD",
            price_usd=Decimal("70.00"),
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.min_price_usd == Decimal("50.00")
        assert self.product.max_price_usd == Decimal("70.00")
        assert self.product.avg_price_usd == Decimal("60.00")

    def test_aggregates_update_on_delete(self):
        """
        Test that DiscoveredProduct aggregates update when ProductAvailability is deleted.
        """
        # Add two availabilities
        avail1 = ProductAvailability.objects.create(
            product=self.product,
            retailer="Delete Test A",
            retailer_url="https://a.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("40.00"),
            currency="USD",
            price_usd=Decimal("40.00"),
            last_checked=timezone.now(),
        )
        avail2 = ProductAvailability.objects.create(
            product=self.product,
            retailer="Delete Test B",
            retailer_url="https://b.com/product",
            retailer_country="USA",
            in_stock=True,
            stock_level=StockLevelChoices.IN_STOCK,
            price=Decimal("60.00"),
            currency="USD",
            price_usd=Decimal("60.00"),
            last_checked=timezone.now(),
        )

        self.product.refresh_from_db()
        assert self.product.retailer_count == 2
        assert self.product.in_stock_count == 2

        # Delete one availability
        avail1.delete()

        self.product.refresh_from_db()
        assert self.product.retailer_count == 1
        assert self.product.in_stock_count == 1
        assert self.product.min_price_usd == Decimal("60.00")
        assert self.product.max_price_usd == Decimal("60.00")
