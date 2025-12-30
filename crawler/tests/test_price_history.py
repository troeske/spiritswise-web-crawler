"""
Tests for PriceHistory model and price trend tracking.

Task Group 16: PriceHistory Model
These tests verify price history tracking with EUR normalization and time-series queries.

TDD: Tests written first before implementation.
"""

import pytest
from datetime import timedelta, date
from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg


class TestPriceHistoryCreation:
    """Tests for PriceHistory creation with required fields."""

    def test_price_history_creation_with_required_fields(self, db):
        """PriceHistory should be created with all required fields."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        # Create a product first
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="abc123",
            fingerprint="fingerprint123",
            name="Test Whiskey",
        )

        now = timezone.now()
        price_history = PriceHistory.objects.create(
            product=product,
            retailer="Whisky Exchange",
            retailer_country="UK",
            price=Decimal("89.99"),
            currency="GBP",
            price_eur=Decimal("104.50"),
            observed_at=now,
            source_url="https://whiskyexchange.com/test-whiskey",
        )

        assert price_history.id is not None
        assert price_history.product == product
        assert price_history.retailer == "Whisky Exchange"
        assert price_history.retailer_country == "UK"
        assert price_history.price == Decimal("89.99")
        assert price_history.currency == "GBP"
        assert price_history.price_eur == Decimal("104.50")
        assert price_history.observed_at == now
        assert price_history.source_url == "https://whiskyexchange.com/test-whiskey"

    def test_price_history_related_name(self, db):
        """DiscoveredProduct should access price history via related_name 'price_history_rel'."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product2",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="def456",
            fingerprint="fingerprint456",
            name="Test Whiskey 2",
        )

        now = timezone.now()
        price1 = PriceHistory.objects.create(
            product=product,
            retailer="Retailer A",
            retailer_country="UK",
            price=Decimal("50.00"),
            currency="GBP",
            price_eur=Decimal("58.00"),
            observed_at=now,
            source_url="https://retailera.com/product",
        )
        price2 = PriceHistory.objects.create(
            product=product,
            retailer="Retailer B",
            retailer_country="DE",
            price=Decimal("55.00"),
            currency="EUR",
            price_eur=Decimal("55.00"),
            observed_at=now,
            source_url="https://retailerb.de/product",
        )

        # Access via related_name (price_history_rel to avoid conflict with legacy JSONField)
        assert product.price_history_rel.count() == 2
        assert price1 in product.price_history_rel.all()
        assert price2 in product.price_history_rel.all()


class TestEURNormalization:
    """Tests for EUR normalization of prices."""

    def test_eur_normalization_stores_normalized_price(self, db):
        """price_eur should store the EUR-normalized price for comparison."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product3",
            product_type=ProductType.PORT_WINE,
            raw_content="Test content",
            raw_content_hash="ghi789",
            fingerprint="fingerprint789",
            name="Vintage Port",
        )

        # Create prices in different currencies with EUR normalization
        now = timezone.now()

        # USD price normalized to EUR
        usd_price = PriceHistory.objects.create(
            product=product,
            retailer="Total Wine",
            retailer_country="USA",
            price=Decimal("120.00"),
            currency="USD",
            price_eur=Decimal("110.00"),  # Normalized to EUR
            observed_at=now,
            source_url="https://totalwine.com/product",
        )

        # GBP price normalized to EUR
        gbp_price = PriceHistory.objects.create(
            product=product,
            retailer="Master of Malt",
            retailer_country="UK",
            price=Decimal("85.00"),
            currency="GBP",
            price_eur=Decimal("100.00"),  # Normalized to EUR
            observed_at=now,
            source_url="https://masterofmalt.com/product",
        )

        # EUR price (already in EUR)
        eur_price = PriceHistory.objects.create(
            product=product,
            retailer="Whisky.de",
            retailer_country="DE",
            price=Decimal("95.00"),
            currency="EUR",
            price_eur=Decimal("95.00"),  # Same as original
            observed_at=now,
            source_url="https://whisky.de/product",
        )

        # All prices can be compared via price_eur
        assert usd_price.price_eur == Decimal("110.00")
        assert gbp_price.price_eur == Decimal("100.00")
        assert eur_price.price_eur == Decimal("95.00")

        # Find cheapest in EUR
        min_price = product.price_history_rel.order_by("price_eur").first()
        assert min_price == eur_price

    def test_cross_currency_comparison(self, db):
        """Should be able to compare prices across currencies using price_eur."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product4",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="jkl012",
            fingerprint="fingerprint012",
            name="Japanese Whisky",
        )

        now = timezone.now()

        # JPY price
        PriceHistory.objects.create(
            product=product,
            retailer="Japanese Retailer",
            retailer_country="JP",
            price=Decimal("15000"),
            currency="JPY",
            price_eur=Decimal("100.00"),
            observed_at=now,
            source_url="https://jp-retailer.com/product",
        )

        # AUD price
        PriceHistory.objects.create(
            product=product,
            retailer="Dan Murphy's",
            retailer_country="AU",
            price=Decimal("180.00"),
            currency="AUD",
            price_eur=Decimal("105.00"),
            observed_at=now,
            source_url="https://danmurphys.com.au/product",
        )

        # Query average EUR price across all currencies
        avg_eur = product.price_history_rel.aggregate(avg=Avg("price_eur"))["avg"]
        assert abs(float(avg_eur) - 102.50) < 0.01


class TestTimeSeriesQueries:
    """Tests for time-series queries on price history."""

    def test_time_series_query_by_product_and_retailer(self, db):
        """Should efficiently query price history by product, retailer, and time range."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product5",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="mno345",
            fingerprint="fingerprint345",
            name="Speyside Malt",
        )

        base_time = timezone.now()

        # Create price history over 90 days for one retailer
        retailer = "Whisky Exchange"
        for i in range(10):
            days_ago = i * 10
            PriceHistory.objects.create(
                product=product,
                retailer=retailer,
                retailer_country="UK",
                price=Decimal("100.00") + Decimal(i),  # Increasing price
                currency="GBP",
                price_eur=Decimal("116.00") + Decimal(i),
                observed_at=base_time - timedelta(days=days_ago),
                source_url=f"https://whiskyexchange.com/product?v={i}",
            )

        # Query last 30 days
        thirty_days_ago = base_time - timedelta(days=30)
        recent_prices = PriceHistory.objects.filter(
            product=product,
            retailer=retailer,
            observed_at__gte=thirty_days_ago,
        ).order_by("observed_at")

        # Should get 4 records (day 0, 10, 20, 30)
        assert recent_prices.count() == 4

        # Verify ordering (oldest first)
        prices_list = list(recent_prices)
        assert prices_list[0].observed_at < prices_list[-1].observed_at

    def test_query_by_observed_at_range(self, db):
        """Should support range queries on observed_at for batch processing."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product6",
            product_type=ProductType.PORT_WINE,
            raw_content="Test content",
            raw_content_hash="pqr678",
            fingerprint="fingerprint678",
            name="Vintage Port 2011",
        )

        base_time = timezone.now()

        # Create price history entries at different times
        for i in range(5):
            PriceHistory.objects.create(
                product=product,
                retailer=f"Retailer {i}",
                retailer_country="PT",
                price=Decimal("75.00"),
                currency="EUR",
                price_eur=Decimal("75.00"),
                observed_at=base_time - timedelta(days=i * 7),
                source_url=f"https://retailer{i}.pt/product",
            )

        # Range query
        start_date = base_time - timedelta(days=21)
        end_date = base_time - timedelta(days=7)

        range_prices = PriceHistory.objects.filter(
            observed_at__gte=start_date,
            observed_at__lte=end_date,
        )

        # Should get records from day 7, 14, 21
        assert range_prices.count() == 3


class TestAggregationFunctions:
    """Tests for aggregation functions on price history."""

    def test_aggregate_min_max_avg_prices(self, db):
        """Should support aggregation functions for price analysis."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )
        from django.db.models import Min, Max, Avg

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product7",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="stu901",
            fingerprint="fingerprint901",
            name="Highland Single Malt",
        )

        now = timezone.now()

        # Create varied price history
        prices = [80, 95, 90, 85, 100]
        for i, price in enumerate(prices):
            PriceHistory.objects.create(
                product=product,
                retailer=f"Retailer {i}",
                retailer_country="UK",
                price=Decimal(str(price)),
                currency="GBP",
                price_eur=Decimal(str(price * 1.16)),  # Simple conversion
                observed_at=now - timedelta(days=i),
                source_url=f"https://retailer{i}.uk/product",
            )

        # Aggregate queries
        aggregates = product.price_history_rel.aggregate(
            min_eur=Min("price_eur"),
            max_eur=Max("price_eur"),
            avg_eur=Avg("price_eur"),
        )

        assert aggregates["min_eur"] == Decimal("92.80")  # 80 * 1.16
        assert aggregates["max_eur"] == Decimal("116.00")  # 100 * 1.16
        expected_avg = sum(p * 1.16 for p in prices) / len(prices)
        assert abs(float(aggregates["avg_eur"]) - expected_avg) < 0.01

    def test_group_by_retailer_aggregation(self, db):
        """Should support grouping by retailer for price comparison."""
        from crawler.models import (
            PriceHistory,
            DiscoveredProduct,
            ProductType,
        )
        from django.db.models import Avg

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product8",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="vwx234",
            fingerprint="fingerprint234",
            name="Islay Malt",
        )

        now = timezone.now()

        # Multiple prices from two retailers
        for i in range(3):
            PriceHistory.objects.create(
                product=product,
                retailer="Retailer A",
                retailer_country="UK",
                price=Decimal("50.00") + Decimal(i * 2),
                currency="GBP",
                price_eur=Decimal("58.00") + Decimal(i * 2),
                observed_at=now - timedelta(days=i),
                source_url=f"https://retailera.uk/product?v={i}",
            )
            PriceHistory.objects.create(
                product=product,
                retailer="Retailer B",
                retailer_country="DE",
                price=Decimal("55.00") + Decimal(i * 3),
                currency="EUR",
                price_eur=Decimal("55.00") + Decimal(i * 3),
                observed_at=now - timedelta(days=i),
                source_url=f"https://retailerb.de/product?v={i}",
            )

        # Group by retailer
        by_retailer = (
            product.price_history_rel
            .values("retailer")
            .annotate(avg_price=Avg("price_eur"))
            .order_by("retailer")
        )

        retailer_dict = {r["retailer"]: r["avg_price"] for r in by_retailer}

        # Retailer A: (58, 60, 62) / 3 = 60
        assert abs(float(retailer_dict["Retailer A"]) - 60.0) < 0.01
        # Retailer B: (55, 58, 61) / 3 = 58
        assert abs(float(retailer_dict["Retailer B"]) - 58.0) < 0.01


class TestPriceTrendFields:
    """Tests for price trend fields on DiscoveredProduct."""

    def test_price_trend_fields_exist_on_discovered_product(self, db):
        """DiscoveredProduct should have price trend fields."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product9",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="yza567",
            fingerprint="fingerprint567",
            name="Lowland Malt",
            # Price trend fields
            price_trend_30d="stable",
            price_change_30d_pct=Decimal("2.5"),
            price_trend_90d="rising",
            price_change_90d_pct=Decimal("8.3"),
            lowest_price_ever_eur=Decimal("45.00"),
            lowest_price_date=date(2024, 6, 15),
            highest_price_ever_eur=Decimal("65.00"),
            highest_price_date=date(2025, 1, 10),
            price_stability_score=7,
        )

        product.refresh_from_db()

        assert product.price_trend_30d == "stable"
        assert product.price_change_30d_pct == Decimal("2.5")
        assert product.price_trend_90d == "rising"
        assert product.price_change_90d_pct == Decimal("8.3")
        assert product.lowest_price_ever_eur == Decimal("45.00")
        assert product.lowest_price_date == date(2024, 6, 15)
        assert product.highest_price_ever_eur == Decimal("65.00")
        assert product.highest_price_date == date(2025, 1, 10)
        assert product.price_stability_score == 7

    def test_price_trend_choices_validation(self, db):
        """price_trend fields should accept valid choices: rising, stable, falling."""
        from crawler.models import DiscoveredProduct, ProductType, PriceTrendChoices

        for trend_value in [
            PriceTrendChoices.RISING,
            PriceTrendChoices.STABLE,
            PriceTrendChoices.FALLING,
        ]:
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/trend-{trend_value}",
                product_type=ProductType.WHISKEY,
                raw_content="Test content",
                raw_content_hash=f"trend{trend_value}",
                fingerprint=f"fingerprint_trend_{trend_value}",
                name=f"Trend Test {trend_value}",
                price_trend_30d=trend_value,
                price_trend_90d=trend_value,
            )
            assert product.price_trend_30d == trend_value
            assert product.price_trend_90d == trend_value

    def test_price_stability_score_validation(self, db):
        """price_stability_score should be validated in 1-10 range."""
        from crawler.models import DiscoveredProduct, ProductType
        from django.core.exceptions import ValidationError

        # Fields to exclude from validation (FK fields and JSONFields with blank=False)
        exclude_fields = ["source", "crawl_job", "extracted_data", "enriched_data"]

        # Valid scores
        for score in [1, 5, 10]:
            product = DiscoveredProduct(
                source_url=f"https://example.com/stability-{score}",
                product_type=ProductType.WHISKEY,
                raw_content="Test content",
                raw_content_hash=f"stability{score}",
                fingerprint=f"fingerprint_stability_{score}",
                name=f"Stability Test {score}",
                price_stability_score=score,
                extracted_data={},
                enriched_data={},
            )
            # Should not raise
            product.full_clean(exclude=exclude_fields)
            product.save()

        # Invalid scores (0 and 11)
        for invalid_score in [0, 11]:
            product = DiscoveredProduct(
                source_url=f"https://example.com/invalid-stability-{invalid_score}",
                product_type=ProductType.WHISKEY,
                raw_content="Test content",
                raw_content_hash=f"invalid{invalid_score}",
                fingerprint=f"fingerprint_invalid_{invalid_score}",
                name=f"Invalid Stability {invalid_score}",
                price_stability_score=invalid_score,
                extracted_data={},
                enriched_data={},
            )
            with pytest.raises(ValidationError) as exc_info:
                product.full_clean(exclude=exclude_fields)
            # Verify the error is for price_stability_score, not other fields
            assert "price_stability_score" in str(exc_info.value)
