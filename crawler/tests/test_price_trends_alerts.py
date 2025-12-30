"""
Tests for Price Trend Calculation and Price Alerts.

Task Group 17: Price Trend Calculation & Alerts
These tests verify:
- 30-day trend calculation
- 90-day trend calculation
- Price stability score calculation
- Price alert creation and threshold checking

TDD: Tests written first before implementation.
"""

import pytest
from datetime import timedelta, date
from decimal import Decimal
from django.utils import timezone


class TestPriceTrendCalculation:
    """Tests for price trend calculation service."""

    def test_30_day_trend_rising(self, db):
        """30-day trend should be 'rising' when prices increase >5%."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
            PriceTrendChoices,
        )
        from crawler.services.price_trends import calculate_price_trends

        # Create a product
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/rising-product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="rising123",
            fingerprint="fingerprint_rising",
            name="Rising Price Whiskey",
        )

        now = timezone.now()
        base_price = Decimal("100.00")

        # Create price history with rising trend
        # First half of 30 days: lower prices
        for i in range(5):
            days_ago = 30 - (i * 3)  # Days 30, 27, 24, 21, 18
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=base_price,
                currency="EUR",
                price_eur=base_price,
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.com/product",
            )

        # Second half of 30 days: higher prices (>10% increase)
        higher_price = Decimal("115.00")  # 15% higher
        for i in range(5):
            days_ago = 15 - (i * 3)  # Days 15, 12, 9, 6, 3
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=higher_price,
                currency="EUR",
                price_eur=higher_price,
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.com/product",
            )

        # Calculate trends
        calculate_price_trends(product)
        product.refresh_from_db()

        assert product.price_trend_30d == PriceTrendChoices.RISING
        assert product.price_change_30d_pct is not None
        assert product.price_change_30d_pct > Decimal("5.0")

    def test_30_day_trend_stable(self, db):
        """30-day trend should be 'stable' when prices change -5% to 5%."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
            PriceTrendChoices,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/stable-product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="stable123",
            fingerprint="fingerprint_stable",
            name="Stable Price Whiskey",
        )

        now = timezone.now()
        base_price = Decimal("100.00")

        # Create stable price history (prices within 3% variance)
        for i in range(10):
            days_ago = 30 - (i * 3)
            # Small variance around base price
            variance = Decimal(str((i % 3) - 1))  # -1, 0, 1
            price = base_price + variance
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=price,
                currency="EUR",
                price_eur=price,
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.com/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        assert product.price_trend_30d == PriceTrendChoices.STABLE
        assert product.price_change_30d_pct is not None
        assert Decimal("-5.0") <= product.price_change_30d_pct <= Decimal("5.0")

    def test_30_day_trend_falling(self, db):
        """30-day trend should be 'falling' when prices decrease <-5%."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
            PriceTrendChoices,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/falling-product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="falling123",
            fingerprint="fingerprint_falling",
            name="Falling Price Whiskey",
        )

        now = timezone.now()

        # First half: higher prices
        higher_price = Decimal("120.00")
        for i in range(5):
            days_ago = 30 - (i * 3)
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=higher_price,
                currency="EUR",
                price_eur=higher_price,
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.com/product",
            )

        # Second half: lower prices (>10% decrease)
        lower_price = Decimal("100.00")  # ~17% lower
        for i in range(5):
            days_ago = 15 - (i * 3)
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=lower_price,
                currency="EUR",
                price_eur=lower_price,
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.com/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        assert product.price_trend_30d == PriceTrendChoices.FALLING
        assert product.price_change_30d_pct is not None
        assert product.price_change_30d_pct < Decimal("-5.0")


class TestPriceTrend90Day:
    """Tests for 90-day trend calculation."""

    def test_90_day_trend_calculation(self, db):
        """90-day trend should calculate from price history over 90 days."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
            PriceTrendChoices,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/90day-product",
            product_type=ProductType.PORT_WINE,
            raw_content="Test content",
            raw_content_hash="90day123",
            fingerprint="fingerprint_90day",
            name="90 Day Trend Port",
        )

        now = timezone.now()

        # Create 90 days of price history with rising trend
        # First 45 days (older): lower prices
        for i in range(10):
            days_ago = 90 - (i * 5)  # Days 90, 85, 80, ...
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="PT",
                price=Decimal("80.00"),
                currency="EUR",
                price_eur=Decimal("80.00"),
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.pt/product",
            )

        # Last 45 days (newer): higher prices
        for i in range(10):
            days_ago = 45 - (i * 5)  # Days 45, 40, 35, ...
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="PT",
                price=Decimal("100.00"),  # 25% higher
                currency="EUR",
                price_eur=Decimal("100.00"),
                observed_at=now - timedelta(days=days_ago),
                source_url="https://retailer.pt/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        assert product.price_trend_90d == PriceTrendChoices.RISING
        assert product.price_change_90d_pct is not None
        assert product.price_change_90d_pct > Decimal("5.0")


class TestPriceStabilityScore:
    """Tests for price stability score calculation."""

    def test_stability_score_high_for_stable_prices(self, db):
        """Price stability score should be high (8-10) for very stable prices."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/very-stable",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="verystable123",
            fingerprint="fingerprint_verystable",
            name="Very Stable Whiskey",
        )

        now = timezone.now()

        # Create very stable prices (all same price)
        for i in range(10):
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=Decimal("75.00"),
                currency="EUR",
                price_eur=Decimal("75.00"),
                observed_at=now - timedelta(days=i * 3),
                source_url="https://retailer.com/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        # Very stable prices should have high stability score
        assert product.price_stability_score is not None
        assert product.price_stability_score >= 8

    def test_stability_score_low_for_volatile_prices(self, db):
        """Price stability score should be low (1-3) for volatile prices."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/volatile",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="volatile123",
            fingerprint="fingerprint_volatile",
            name="Volatile Price Whiskey",
        )

        now = timezone.now()

        # Create volatile prices with big swings
        prices = [50, 100, 60, 110, 55, 105, 65, 95, 70, 90]
        for i, price in enumerate(prices):
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=Decimal(str(price)),
                currency="EUR",
                price_eur=Decimal(str(price)),
                observed_at=now - timedelta(days=i * 3),
                source_url="https://retailer.com/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        # Volatile prices should have low stability score
        assert product.price_stability_score is not None
        assert product.price_stability_score <= 4


class TestMinMaxPriceTracking:
    """Tests for lowest/highest price ever tracking."""

    def test_updates_min_max_prices(self, db):
        """Should update lowest/highest price ever and dates."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )
        from crawler.services.price_trends import calculate_price_trends

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/minmax",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="minmax123",
            fingerprint="fingerprint_minmax",
            name="MinMax Test Whiskey",
        )

        now = timezone.now()

        # Create price history with known min and max
        prices_with_dates = [
            (Decimal("100.00"), now - timedelta(days=30)),
            (Decimal("50.00"), now - timedelta(days=20)),   # Lowest
            (Decimal("75.00"), now - timedelta(days=10)),
            (Decimal("150.00"), now - timedelta(days=5)),   # Highest
            (Decimal("90.00"), now - timedelta(days=1)),
        ]

        for price, obs_at in prices_with_dates:
            PriceHistory.objects.create(
                product=product,
                retailer="Test Retailer",
                retailer_country="UK",
                price=price,
                currency="EUR",
                price_eur=price,
                observed_at=obs_at,
                source_url="https://retailer.com/product",
            )

        calculate_price_trends(product)
        product.refresh_from_db()

        assert product.lowest_price_ever_eur == Decimal("50.00")
        assert product.highest_price_ever_eur == Decimal("150.00")
        assert product.lowest_price_date is not None
        assert product.highest_price_date is not None


class TestPriceAlertModel:
    """Tests for PriceAlert model."""

    def test_price_alert_creation(self, db):
        """Should create PriceAlert with all required fields."""
        from crawler.models import (
            PriceAlert,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/alert-product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="alert123",
            fingerprint="fingerprint_alert",
            name="Alert Test Whiskey",
        )

        alert = PriceAlert.objects.create(
            product=product,
            alert_type="price_drop",
            threshold_value=Decimal("75.00"),
            triggered_value=Decimal("65.00"),
            retailer="Whisky Exchange",
        )

        assert alert.id is not None
        assert alert.product == product
        assert alert.alert_type == "price_drop"
        assert alert.threshold_value == Decimal("75.00")
        assert alert.triggered_value == Decimal("65.00")
        assert alert.retailer == "Whisky Exchange"
        assert alert.acknowledged is False
        assert alert.acknowledged_by is None
        assert alert.acknowledged_at is None
        assert alert.created_at is not None

    def test_price_alert_types(self, db):
        """Should support all alert types: price_drop, price_spike, new_low, back_in_stock."""
        from crawler.models import (
            PriceAlert,
            PriceAlertTypeChoices,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/alert-types",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="alerttypes123",
            fingerprint="fingerprint_alerttypes",
            name="Alert Types Whiskey",
        )

        alert_types = [
            PriceAlertTypeChoices.PRICE_DROP,
            PriceAlertTypeChoices.PRICE_SPIKE,
            PriceAlertTypeChoices.NEW_LOW,
            PriceAlertTypeChoices.BACK_IN_STOCK,
        ]

        for alert_type in alert_types:
            alert = PriceAlert.objects.create(
                product=product,
                alert_type=alert_type,
                triggered_value=Decimal("100.00"),
            )
            assert alert.alert_type == alert_type

    def test_price_alert_related_name(self, db):
        """Product should access alerts via related_name 'price_alerts'."""
        from crawler.models import (
            PriceAlert,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/alert-related",
            product_type=ProductType.PORT_WINE,
            raw_content="Test content",
            raw_content_hash="alertrelated123",
            fingerprint="fingerprint_alertrelated",
            name="Alert Related Port",
        )

        alert1 = PriceAlert.objects.create(
            product=product,
            alert_type="price_drop",
            triggered_value=Decimal("50.00"),
        )
        alert2 = PriceAlert.objects.create(
            product=product,
            alert_type="new_low",
            triggered_value=Decimal("45.00"),
        )

        assert product.price_alerts.count() == 2
        assert alert1 in product.price_alerts.all()
        assert alert2 in product.price_alerts.all()


class TestPriceAlertThresholdChecking:
    """Tests for price alert threshold checking."""

    def test_threshold_fields_on_discovered_product(self, db):
        """DiscoveredProduct should have price_alert_threshold_eur and price_alert_triggered."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/threshold-test",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="threshold123",
            fingerprint="fingerprint_threshold",
            name="Threshold Test Whiskey",
            price_alert_threshold_eur=Decimal("50.00"),
            price_alert_triggered=False,
        )

        product.refresh_from_db()

        assert product.price_alert_threshold_eur == Decimal("50.00")
        assert product.price_alert_triggered is False

    def test_alert_created_when_threshold_crossed(self, db):
        """Alert should be created when a new price crosses the threshold."""
        from crawler.models import (
            PriceHistory,
            PriceAlert,
            DiscoveredProduct,
            ProductType,
        )
        from crawler.services.price_trends import check_price_alerts

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/cross-threshold",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="crossthreshold123",
            fingerprint="fingerprint_crossthreshold",
            name="Cross Threshold Whiskey",
            price_alert_threshold_eur=Decimal("60.00"),
            price_alert_triggered=False,
        )

        # Create a price below threshold
        now = timezone.now()
        price_history = PriceHistory.objects.create(
            product=product,
            retailer="Test Retailer",
            retailer_country="UK",
            price=Decimal("55.00"),
            currency="EUR",
            price_eur=Decimal("55.00"),
            observed_at=now,
            source_url="https://retailer.com/product",
        )

        # Check for alerts
        check_price_alerts(product, price_history)
        product.refresh_from_db()

        # Alert should have been created
        assert product.price_alert_triggered is True
        assert PriceAlert.objects.filter(product=product, alert_type="price_drop").exists()

        alert = PriceAlert.objects.get(product=product, alert_type="price_drop")
        assert alert.threshold_value == Decimal("60.00")
        assert alert.triggered_value == Decimal("55.00")
        assert alert.retailer == "Test Retailer"

    def test_new_low_alert_created(self, db):
        """Alert should be created when price is new all-time low."""
        from crawler.models import (
            PriceHistory,
            PriceAlert,
            DiscoveredProduct,
            ProductType,
        )
        from crawler.services.price_trends import check_price_alerts

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/new-low",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="newlow123",
            fingerprint="fingerprint_newlow",
            name="New Low Whiskey",
            lowest_price_ever_eur=Decimal("70.00"),
        )

        # Create a price that's a new low
        now = timezone.now()
        price_history = PriceHistory.objects.create(
            product=product,
            retailer="New Low Retailer",
            retailer_country="DE",
            price=Decimal("60.00"),
            currency="EUR",
            price_eur=Decimal("60.00"),
            observed_at=now,
            source_url="https://retailer.de/product",
        )

        check_price_alerts(product, price_history)

        # New low alert should have been created
        assert PriceAlert.objects.filter(product=product, alert_type="new_low").exists()

        alert = PriceAlert.objects.get(product=product, alert_type="new_low")
        assert alert.triggered_value == Decimal("60.00")
        assert alert.retailer == "New Low Retailer"
