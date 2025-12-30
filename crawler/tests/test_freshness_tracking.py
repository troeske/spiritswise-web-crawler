"""
Tests for freshness tracking fields and utilities.

Task Group 14: Freshness Tracking Fields
These tests verify the freshness tracking system for DiscoveredProduct data.

TDD: Tests written first before implementation.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


class TestFreshnessFieldDefaults:
    """Tests for freshness field default values on DiscoveredProduct."""

    def test_freshness_datetime_fields_default_to_null(self, db):
        """Freshness datetime fields should default to null."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product1",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-defaults",
        )

        assert product.last_price_check is None
        assert product.last_availability_check is None
        assert product.last_enrichment is None

    def test_data_freshness_score_defaults_to_100(self, db):
        """Data freshness score should default to 100 (fresh) for new products."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product2",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-score",
        )

        # New products should be considered fresh (score of 100)
        assert product.data_freshness_score == 100

    def test_needs_refresh_defaults_to_false(self, db):
        """needs_refresh should default to False."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product3",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-refresh",
        )

        assert product.needs_refresh is False


class TestFreshnessFieldStorage:
    """Tests for freshness field storage and retrieval."""

    def test_last_price_check_stores_datetime(self, db):
        """last_price_check should store datetime correctly."""
        from crawler.models import DiscoveredProduct, ProductType

        now = timezone.now()
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product4",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-price-check",
            last_price_check=now,
        )

        product.refresh_from_db()
        # Compare with precision to avoid microsecond differences
        assert product.last_price_check is not None
        assert abs((product.last_price_check - now).total_seconds()) < 1

    def test_freshness_fields_persist_correctly(self, db):
        """All freshness fields should persist through database reload."""
        from crawler.models import DiscoveredProduct, ProductType

        now = timezone.now()
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product5",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-persist",
            last_price_check=now,
            last_availability_check=now - timedelta(days=2),
            last_enrichment=now - timedelta(days=5),
            data_freshness_score=75,
            needs_refresh=True,
        )

        reloaded = DiscoveredProduct.objects.get(pk=product.pk)

        assert reloaded.last_price_check is not None
        assert reloaded.last_availability_check is not None
        assert reloaded.last_enrichment is not None
        assert reloaded.data_freshness_score == 75
        assert reloaded.needs_refresh is True


class TestFreshnessScoreCalculation:
    """Tests for freshness score calculation utility."""

    def test_calculate_freshness_score_with_no_timestamps(self):
        """Freshness score calculation should return 100 for new product with no timestamps."""
        from crawler.utils.freshness import calculate_freshness_score

        # Simulate a product dict with no timestamps
        product_data = {
            "last_price_check": None,
            "last_availability_check": None,
            "last_enrichment": None,
        }

        score = calculate_freshness_score(product_data)

        # New products with no data should be considered needing refresh (low score)
        # but if all timestamps are None, we return 100 as "fresh" since there's nothing stale
        assert score == 100

    def test_calculate_freshness_score_with_recent_data(self):
        """Freshness score should be high for recently updated data."""
        from crawler.utils.freshness import calculate_freshness_score

        now = timezone.now()
        product_data = {
            "last_price_check": now - timedelta(days=1),  # 1 day ago (fresh)
            "last_availability_check": now - timedelta(days=1),  # 1 day ago (fresh)
            "last_enrichment": now - timedelta(days=3),  # 3 days ago (fresh)
        }

        score = calculate_freshness_score(product_data)

        # With all recent data, score should be high (above 80)
        assert score >= 80

    def test_calculate_freshness_score_with_stale_price(self):
        """Freshness score should decrease when price data is stale (7-30 days)."""
        from crawler.utils.freshness import calculate_freshness_score

        now = timezone.now()
        product_data = {
            "last_price_check": now - timedelta(days=14),  # 14 days ago (stale)
            "last_availability_check": now - timedelta(days=1),  # 1 day ago (fresh)
            "last_enrichment": now - timedelta(days=3),  # 3 days ago (fresh)
        }

        score = calculate_freshness_score(product_data)

        # With stale price (35% weight), score should be moderate
        assert 50 <= score <= 85

    def test_calculate_freshness_score_with_critical_data(self):
        """Freshness score should be low when data is critical (>30 days for price)."""
        from crawler.utils.freshness import calculate_freshness_score

        now = timezone.now()
        product_data = {
            "last_price_check": now - timedelta(days=45),  # 45 days ago (critical)
            "last_availability_check": now - timedelta(days=20),  # 20 days ago (critical)
            "last_enrichment": now - timedelta(days=100),  # 100 days ago (stale)
        }

        score = calculate_freshness_score(product_data)

        # With critical data on multiple fields, score should be low
        assert score <= 50


class TestNeedsRefreshFlagLogic:
    """Tests for needs_refresh flag logic."""

    def test_needs_refresh_set_true_when_score_below_threshold(self, db):
        """needs_refresh should be True when freshness score is below threshold."""
        from crawler.models import DiscoveredProduct, ProductType
        from crawler.utils.freshness import update_product_freshness

        now = timezone.now()
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product6",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-needs-refresh",
            last_price_check=now - timedelta(days=45),  # Critical
            last_availability_check=now - timedelta(days=20),  # Critical
            data_freshness_score=100,
            needs_refresh=False,
        )

        # Call the update utility
        update_product_freshness(product)

        product.refresh_from_db()
        # With critical data, needs_refresh should be True
        assert product.needs_refresh is True

    def test_needs_refresh_set_false_when_score_high(self, db):
        """needs_refresh should be False when freshness score is high."""
        from crawler.models import DiscoveredProduct, ProductType
        from crawler.utils.freshness import update_product_freshness

        now = timezone.now()
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product7",
            raw_content="<html>test</html>",
            product_type=ProductType.WHISKEY,
            fingerprint="test-fingerprint-no-refresh",
            last_price_check=now - timedelta(days=1),  # Fresh
            last_availability_check=now - timedelta(days=1),  # Fresh
            data_freshness_score=50,
            needs_refresh=True,
        )

        # Call the update utility
        update_product_freshness(product)

        product.refresh_from_db()
        # With fresh data, needs_refresh should be False
        assert product.needs_refresh is False


class TestFreshnessThresholdsByDataType:
    """Tests for freshness thresholds by data type."""

    def test_price_freshness_threshold_fresh(self):
        """Price data less than 7 days old should be considered fresh."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=5)

        level = get_data_freshness_level("price", last_check)

        assert level == "fresh"

    def test_price_freshness_threshold_stale(self):
        """Price data 7-30 days old should be considered stale."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=15)

        level = get_data_freshness_level("price", last_check)

        assert level == "stale"

    def test_price_freshness_threshold_critical(self):
        """Price data more than 30 days old should be considered critical."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=45)

        level = get_data_freshness_level("price", last_check)

        assert level == "critical"

    def test_availability_freshness_threshold_fresh(self):
        """Availability data less than 3 days old should be considered fresh."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=2)

        level = get_data_freshness_level("availability", last_check)

        assert level == "fresh"

    def test_availability_freshness_threshold_stale(self):
        """Availability data 3-14 days old should be considered stale."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=7)

        level = get_data_freshness_level("availability", last_check)

        assert level == "stale"

    def test_ratings_freshness_threshold_fresh(self):
        """Ratings data less than 30 days old should be considered fresh."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=15)

        level = get_data_freshness_level("ratings", last_check)

        assert level == "fresh"

    def test_awards_freshness_threshold_fresh(self):
        """Awards data less than 90 days old should be considered fresh."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=60)

        level = get_data_freshness_level("awards", last_check)

        assert level == "fresh"

    def test_product_details_freshness_threshold_fresh(self):
        """Product details less than 180 days old should be considered fresh."""
        from crawler.utils.freshness import get_data_freshness_level

        now = timezone.now()
        last_check = now - timedelta(days=100)

        level = get_data_freshness_level("product_details", last_check)

        assert level == "fresh"
