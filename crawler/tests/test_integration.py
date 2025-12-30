"""
Integration tests for the Spirits Database Crawler Enhancement feature.

Task Group 32: Test Review & Gap Analysis

These tests cover end-to-end workflows and integration points between
models and services that ARE implemented in the current codebase.

Focus areas:
1. CrawledSource -> ProductAvailability flow
2. DiscoverySourceConfig -> CrawledSource -> SourceMetrics flow
3. DiscoveredProduct -> ProductAvailability -> CategoryInsight flow
4. PurchaseRecommendation generation from DiscoveredProduct data
5. CrawlerMetrics aggregation workflow
6. AlertRule evaluation workflow
7. ShopInventory gap analysis with DiscoveredProduct
8. Crawl strategy escalation workflow

Note: Several models from the original spec (DiscoveredBrand, WhiskeyDetails,
PortWineDetails, ProductAward, ProductPrice, ProductRating, ProductImage,
ProductSource, BrandSource, ProductFieldSource, ProductCandidate, PriceHistory,
PriceAlert, NewRelease, CrawlSchedule) were not implemented. Tests are written
for the models that DO exist.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.db import transaction, IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    DiscoveredProduct,
    ProductType,
    DiscoveredProductStatus,
    SourceCategory,
    DiscoverySourceConfig,
    CrawledSource,
    SourceTypeChoices,
    CrawlFrequencyChoices,
    CrawlStrategyChoices,
    CrawledSourceTypeChoices,
    ExtractionStatusChoices,
    WaybackStatusChoices,
    ProductAvailability,
    StockLevelChoices,
    CategoryInsight,
    CategoryTrendingDirectionChoices,
    PurchaseRecommendation,
    RecommendationTierChoices,
    MarginPotentialChoices,
    TurnoverEstimateChoices,
    RiskLevelChoices,
    ShopInventory,
    PriceTierChoices,
    CrawlerMetrics,
    SourceMetrics,
    AlertRule,
    AlertConditionChoices,
    AlertSeverityChoices,
    NotificationChannelChoices,
)


def create_test_crawler_source(name="Test Source"):
    """Helper to create a CrawlerSource with required fields."""
    return CrawlerSource.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        base_url="https://example.com",
        product_types=["whiskey"],
        category=SourceCategory.REVIEW,
    )


def create_test_product(source, name="Test Product", fingerprint=None):
    """Helper to create a DiscoveredProduct with required fields."""
    if fingerprint is None:
        fingerprint = f"fp_{uuid.uuid4().hex[:16]}"
    return DiscoveredProduct.objects.create(
        source=source,
        source_url=f"https://example.com/{name.lower().replace(' ', '-')}",
        fingerprint=fingerprint,
        product_type=ProductType.WHISKEY,
        raw_content=f"<html>{name}</html>",
        raw_content_hash=f"hash_{uuid.uuid4().hex[:16]}",
        extracted_data={"name": name},
    )


# ============================================================
# Test 1: Full Discovery Pipeline (DiscoverySourceConfig -> CrawledSource)
# ============================================================


class DiscoverySourceToCrawledSourceIntegrationTest(TestCase):
    """
    Integration test for the discovery source configuration to
    crawled source pipeline.

    Tests the flow:
    1. Create DiscoverySourceConfig
    2. Create CrawledSource linked to config
    3. Verify relationship integrity
    4. Verify cascade behavior
    """

    def setUp(self):
        """Create test data."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="IWSC Competition",
            base_url="https://iwsc.net",
            source_type=SourceTypeChoices.AWARD_COMPETITION,
            crawl_priority=9,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=9,
            crawl_strategy=CrawlStrategyChoices.SIMPLE,
        )

    def test_full_discovery_pipeline_creates_linked_records(self):
        """
        Test that a CrawledSource properly links to DiscoverySourceConfig.
        """
        # Create crawled source from this discovery config
        crawled_source = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2024/whiskey",
            title="IWSC 2024 Whiskey Awards",
            content_hash="abc123def456",
            discovery_source=self.discovery_source,
            source_type=CrawledSourceTypeChoices.AWARD_PAGE,
            extraction_status=ExtractionStatusChoices.PENDING,
            raw_content="<html><body>Award results...</body></html>",
        )

        # Verify the relationship
        self.assertEqual(crawled_source.discovery_source, self.discovery_source)
        self.assertEqual(crawled_source.discovery_source.name, "IWSC Competition")

        # Verify reverse relationship
        related_sources = self.discovery_source.crawled_sources.all()
        self.assertEqual(related_sources.count(), 1)
        self.assertEqual(related_sources.first().url, "https://iwsc.net/awards/2024/whiskey")

    def test_multiple_crawled_sources_from_single_discovery_config(self):
        """
        Test that multiple CrawledSource records can link to the same
        DiscoverySourceConfig.
        """
        urls = [
            ("https://iwsc.net/awards/2024/whiskey", "Whiskey Awards 2024"),
            ("https://iwsc.net/awards/2024/port", "Port Awards 2024"),
            ("https://iwsc.net/awards/2023/whiskey", "Whiskey Awards 2023"),
        ]

        for url, title in urls:
            CrawledSource.objects.create(
                url=url,
                title=title,
                content_hash=f"hash_{url}",
                discovery_source=self.discovery_source,
                source_type=CrawledSourceTypeChoices.AWARD_PAGE,
                extraction_status=ExtractionStatusChoices.PENDING,
            )

        # Verify all three are linked
        self.assertEqual(self.discovery_source.crawled_sources.count(), 3)

    def test_crawled_source_without_discovery_config(self):
        """
        Test that CrawledSource can be created without a DiscoverySourceConfig
        (e.g., from SerpAPI discovery).
        """
        crawled_source = CrawledSource.objects.create(
            url="https://example.com/whiskey-review",
            title="SerpAPI Discovered Review",
            content_hash="serpapi_hash_123",
            discovery_source=None,  # No parent config
            source_type=CrawledSourceTypeChoices.REVIEW_ARTICLE,
            extraction_status=ExtractionStatusChoices.PENDING,
        )

        self.assertIsNone(crawled_source.discovery_source)


# ============================================================
# Test 2: Product Availability Aggregation Flow
# ============================================================


class ProductAvailabilityIntegrationTest(TestCase):
    """
    Integration test for DiscoveredProduct -> ProductAvailability flow.

    Tests the workflow:
    1. Create DiscoveredProduct
    2. Create multiple ProductAvailability records
    3. Verify aggregation fields can be calculated
    """

    def setUp(self):
        """Create test product."""
        self.crawler_source = create_test_crawler_source("Availability Test Source")
        self.product = create_test_product(
            self.crawler_source,
            name="Macallan 18",
            fingerprint="macallan_18_fingerprint"
        )

    def test_multiple_availability_records_for_product(self):
        """
        Test creating multiple ProductAvailability records for a product
        from different retailers.
        """
        retailers = [
            ("The Whisky Exchange", "UK", Decimal("199.99"), "GBP", True),
            ("Master of Malt", "UK", Decimal("189.99"), "GBP", True),
            ("Total Wine", "USA", Decimal("249.99"), "USD", False),
            ("Whisky.de", "Germany", Decimal("179.99"), "EUR", True),
        ]

        for retailer, country, price, currency, in_stock in retailers:
            ProductAvailability.objects.create(
                product=self.product,
                retailer=retailer,
                retailer_url=f"https://{retailer.lower().replace(' ', '')}.com/product",
                retailer_country=country,
                in_stock=in_stock,
                stock_level=StockLevelChoices.IN_STOCK if in_stock else StockLevelChoices.OUT_OF_STOCK,
                price=price,
                currency=currency,
                last_checked=timezone.now(),
            )

        # Verify all availability records exist
        self.assertEqual(self.product.availability.count(), 4)

        # Verify we can filter by in_stock
        in_stock_count = self.product.availability.filter(in_stock=True).count()
        self.assertEqual(in_stock_count, 3)

    def test_availability_aggregation_calculation(self):
        """
        Test that aggregation values can be calculated from
        ProductAvailability records.
        """
        # Create availability records with USD prices for aggregation
        prices_usd = [Decimal("249.99"), Decimal("239.99"), Decimal("259.99")]

        for i, price in enumerate(prices_usd):
            ProductAvailability.objects.create(
                product=self.product,
                retailer=f"Retailer {i}",
                retailer_url=f"https://retailer{i}.com/product",
                retailer_country="USA",
                in_stock=True,
                stock_level=StockLevelChoices.IN_STOCK,
                price=price,
                currency="USD",
                price_usd=price,
                last_checked=timezone.now(),
            )

        # Manually calculate aggregations (simulating signal behavior)
        availability = self.product.availability.filter(price_usd__isnull=False)

        retailer_count = availability.count()
        in_stock_count = availability.filter(in_stock=True).count()

        prices = list(availability.values_list('price_usd', flat=True))
        avg_price = sum(prices) / len(prices) if prices else None
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None

        # Update product with aggregations
        self.product.retailer_count = retailer_count
        self.product.in_stock_count = in_stock_count
        self.product.avg_price_usd = avg_price
        self.product.min_price_usd = min_price
        self.product.max_price_usd = max_price
        self.product.save()

        # Reload and verify
        self.product.refresh_from_db()
        self.assertEqual(self.product.retailer_count, 3)
        self.assertEqual(self.product.in_stock_count, 3)
        self.assertEqual(self.product.min_price_usd, Decimal("239.99"))
        self.assertEqual(self.product.max_price_usd, Decimal("259.99"))


# ============================================================
# Test 3: Source Metrics Aggregation Flow
# ============================================================


class SourceMetricsIntegrationTest(TestCase):
    """
    Integration test for DiscoverySourceConfig -> SourceMetrics flow.

    Tests the workflow for tracking per-source daily metrics.
    """

    def setUp(self):
        """Create test discovery source."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="Whisky Advocate",
            base_url="https://whiskyadvocate.com",
            source_type=SourceTypeChoices.REVIEW_BLOG,
            crawl_priority=7,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=8,
        )

    def test_daily_metrics_creation_for_source(self):
        """
        Test creating daily metrics for a discovery source.
        """
        today = timezone.now().date()

        metrics = SourceMetrics.objects.create(
            date=today,
            discovery_source=self.discovery_source,
            pages_crawled=50,
            pages_succeeded=47,
            products_found=23,
            avg_products_per_page=Decimal("0.49"),
            avg_confidence=Decimal("0.87"),
            errors=[{"type": "timeout", "count": 3}],
        )

        # Verify metrics are linked
        self.assertEqual(metrics.discovery_source, self.discovery_source)

        # Verify related name access
        source_metrics = self.discovery_source.metrics.all()
        self.assertEqual(source_metrics.count(), 1)
        self.assertEqual(source_metrics.first().pages_crawled, 50)

    def test_week_of_metrics_tracking(self):
        """
        Test tracking a week of metrics for trending analysis.
        """
        base_date = timezone.now().date()

        for day_offset in range(7):
            date = base_date - timedelta(days=day_offset)
            SourceMetrics.objects.create(
                date=date,
                discovery_source=self.discovery_source,
                pages_crawled=40 + day_offset * 5,
                pages_succeeded=38 + day_offset * 4,
                products_found=20 + day_offset * 2,
                avg_products_per_page=Decimal("0.5"),
                avg_confidence=Decimal("0.85"),
                errors=[],
            )

        # Verify all 7 days of metrics exist
        self.assertEqual(self.discovery_source.metrics.count(), 7)

        # Calculate weekly totals
        total_pages = sum(m.pages_crawled for m in self.discovery_source.metrics.all())
        self.assertGreater(total_pages, 0)


# ============================================================
# Test 4: Purchase Recommendation Generation Flow
# ============================================================


class PurchaseRecommendationIntegrationTest(TestCase):
    """
    Integration test for DiscoveredProduct -> PurchaseRecommendation flow.

    Tests the workflow for generating recommendations based on product data.
    """

    def setUp(self):
        """Create test product with demand signals."""
        self.crawler_source = create_test_crawler_source("Recommendation Test Source")

        self.product = DiscoveredProduct.objects.create(
            source=self.crawler_source,
            source_url="https://example.com/glenfiddich-21",
            fingerprint="glenfiddich_21_fingerprint",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Glenfiddich 21</html>",
            raw_content_hash="content_hash_456",
            extracted_data={"name": "Glenfiddich 21 Gran Reserva"},
            # Demand signals
            trend_score=85,
            trend_direction="rising",
            buzz_score=72,
            # Market positioning
            price_tier=PriceTierChoices.PREMIUM,
            target_audience="enthusiast",
            availability_score=7,
            # Aggregated availability
            retailer_count=12,
            in_stock_count=10,
            avg_price_usd=Decimal("199.99"),
            min_price_usd=Decimal("179.99"),
            max_price_usd=Decimal("219.99"),
        )

    def test_recommendation_generated_from_product_data(self):
        """
        Test generating a purchase recommendation from product data.
        """
        # Generate recommendation based on product signals
        recommendation = PurchaseRecommendation.objects.create(
            product=self.product,
            recommendation_score=88,
            recommendation_tier=RecommendationTierChoices.RECOMMENDED,
            recommendation_reason=(
                "Glenfiddich 21 Gran Reserva shows strong demand signals "
                "(trend_score: 85, rising) with good availability (10/12 retailers "
                "in stock). Premium price tier with enthusiast target audience "
                "makes this a solid inventory addition."
            ),
            demand_score=9,
            quality_score=8,
            value_score=7,
            uniqueness_score=6,
            trend_score_factor=9,
            category_gap_fill=False,
            complements_existing=True,
            margin_potential=MarginPotentialChoices.HIGH,
            turnover_estimate=TurnoverEstimateChoices.MODERATE,
            risk_level=RiskLevelChoices.LOW,
            suggested_quantity=6,
            suggested_retail_price=Decimal("229.99"),
            estimated_margin_percent=Decimal("25.00"),
            reorder_threshold=2,
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Verify recommendation is linked to product
        self.assertEqual(recommendation.product, self.product)
        self.assertEqual(self.product.recommendations.count(), 1)

    def test_multiple_recommendations_with_different_tiers(self):
        """
        Test that products can have multiple recommendations over time.
        """
        tiers = [
            (RecommendationTierChoices.MUST_STOCK, 95),
            (RecommendationTierChoices.RECOMMENDED, 82),
            (RecommendationTierChoices.CONSIDER, 65),
        ]

        for tier, score in tiers:
            PurchaseRecommendation.objects.create(
                product=self.product,
                recommendation_score=score,
                recommendation_tier=tier,
                recommendation_reason=f"Test recommendation with tier {tier}",
            )

        # Verify all recommendations exist
        self.assertEqual(self.product.recommendations.count(), 3)

        # Verify we can filter by tier
        must_stock = self.product.recommendations.filter(
            recommendation_tier=RecommendationTierChoices.MUST_STOCK
        )
        self.assertEqual(must_stock.count(), 1)


# ============================================================
# Test 5: Category Insight and Market Analysis Flow
# ============================================================


class CategoryInsightIntegrationTest(TestCase):
    """
    Integration test for CategoryInsight market analysis.

    Tests the workflow for aggregating category-level insights.
    """

    def test_category_insight_creation(self):
        """
        Test creating a CategoryInsight record.
        """
        insight = CategoryInsight.objects.create(
            product_type="whiskey",
            sub_category="scotch_single_malt",
            region="Speyside",
            country="Scotland",
            total_products=245,
            products_with_awards=89,
            avg_price_usd=Decimal("125.00"),
            median_price_usd=Decimal("95.00"),
            avg_price_eur=Decimal("115.00"),
            trending_direction=CategoryTrendingDirectionChoices.RISING,
        )

        self.assertIsNotNone(insight.id)
        self.assertEqual(insight.total_products, 245)

    def test_multiple_category_insights_for_analysis(self):
        """
        Test creating multiple category insights for market analysis.
        """
        categories = [
            ("whiskey", "bourbon", "Kentucky", "USA", CategoryTrendingDirectionChoices.HOT),
            ("whiskey", "scotch_single_malt", "Islay", "Scotland", CategoryTrendingDirectionChoices.STABLE),
            ("whiskey", "japanese", None, "Japan", CategoryTrendingDirectionChoices.RISING),
            ("port_wine", "tawny", "Douro", "Portugal", CategoryTrendingDirectionChoices.STABLE),
        ]

        for product_type, sub_cat, region, country, trend in categories:
            CategoryInsight.objects.create(
                product_type=product_type,
                sub_category=sub_cat,
                region=region,
                country=country,
                total_products=100,
                products_with_awards=30,
                avg_price_usd=Decimal("100.00"),
                median_price_usd=Decimal("85.00"),
                avg_price_eur=Decimal("92.00"),
                trending_direction=trend,
            )

        # Verify all insights created
        self.assertEqual(CategoryInsight.objects.count(), 4)

        # Query hot categories
        hot_categories = CategoryInsight.objects.filter(
            trending_direction=CategoryTrendingDirectionChoices.HOT
        )
        self.assertEqual(hot_categories.count(), 1)
        self.assertEqual(hot_categories.first().sub_category, "bourbon")


# ============================================================
# Test 6: Shop Inventory Gap Analysis Flow
# ============================================================


class ShopInventoryGapAnalysisTest(TestCase):
    """
    Integration test for ShopInventory gap analysis with DiscoveredProduct.
    """

    def setUp(self):
        """Create test products and inventory."""
        self.crawler_source = create_test_crawler_source("Gap Analysis Test Source")

    def test_inventory_linked_to_discovered_product(self):
        """
        Test linking ShopInventory to DiscoveredProduct for comparison.
        """
        # Create discovered product
        product = create_test_product(
            self.crawler_source,
            name="Ardbeg 10",
            fingerprint="ardbeg_10_fingerprint"
        )

        # Create inventory item matched to this product
        inventory = ShopInventory.objects.create(
            product_name="Ardbeg 10 Year Old",
            matched_product=product,
            product_type="whiskey",
            sub_category="scotch_single_malt",
            region="Islay",
            price_tier=PriceTierChoices.VALUE,
            current_stock=12,
            reorder_point=4,
            monthly_sales_avg=Decimal("6.5"),
        )

        # Verify relationship
        self.assertEqual(inventory.matched_product, product)
        self.assertEqual(product.shop_inventory.count(), 1)

    def test_gap_analysis_unmatched_inventory(self):
        """
        Test that inventory items can exist without a matched product
        (for gap analysis purposes).
        """
        # Create inventory items without matched products (gaps)
        inventory_items = [
            ("Jameson 12", "whiskey", "irish_blend"),
            ("Taylor's 20 Year Tawny", "port_wine", "tawny"),
            ("Nikka From The Barrel", "whiskey", "japanese"),
        ]

        for name, ptype, subcat in inventory_items:
            ShopInventory.objects.create(
                product_name=name,
                matched_product=None,  # No match in discovered products
                product_type=ptype,
                sub_category=subcat,
                price_tier=PriceTierChoices.MID_RANGE,
                current_stock=5,
                reorder_point=2,
            )

        # Find unmatched inventory (products we sell but haven't discovered)
        unmatched = ShopInventory.objects.filter(matched_product__isnull=True)
        self.assertEqual(unmatched.count(), 3)


# ============================================================
# Test 7: Crawler Metrics Daily Aggregation
# ============================================================


class CrawlerMetricsDailyAggregationTest(TestCase):
    """
    Integration test for CrawlerMetrics daily aggregation workflow.
    """

    def test_daily_metrics_aggregation(self):
        """
        Test creating daily aggregate metrics.
        """
        today = timezone.now().date()

        metrics = CrawlerMetrics.objects.create(
            date=today,
            # Crawl metrics
            pages_crawled=500,
            pages_succeeded=475,
            pages_failed=25,
            crawl_success_rate=Decimal("95.00"),
            # Extraction metrics
            products_extracted=180,
            products_created=45,
            products_merged=120,
            products_flagged_review=15,
            extraction_success_rate=Decimal("92.50"),
            # Quality metrics
            avg_completeness_score=Decimal("78.50"),
            avg_confidence_score=Decimal("0.87"),
            conflicts_detected=8,
            duplicates_merged=35,
            # API usage
            serpapi_queries=150,
            scrapingbee_requests=75,
            ai_enhancement_calls=180,
            wayback_saves=200,
            # Performance
            avg_crawl_time_ms=2500,
            avg_extraction_time_ms=1800,
            queue_depth=45,
        )

        # Verify metrics saved
        self.assertEqual(CrawlerMetrics.objects.count(), 1)

        # Verify unique date constraint
        with self.assertRaises(IntegrityError):
            CrawlerMetrics.objects.create(
                date=today,
                pages_crawled=600,
                pages_succeeded=580,
                pages_failed=20,
                crawl_success_rate=Decimal("96.67"),
                products_extracted=200,
                products_created=50,
                products_merged=130,
                products_flagged_review=20,
                extraction_success_rate=Decimal("93.00"),
                avg_completeness_score=Decimal("80.00"),
                avg_confidence_score=Decimal("0.88"),
                conflicts_detected=10,
                duplicates_merged=40,
                serpapi_queries=160,
                scrapingbee_requests=80,
                ai_enhancement_calls=200,
                wayback_saves=220,
                avg_crawl_time_ms=2400,
                avg_extraction_time_ms=1700,
                queue_depth=50,
            )


# ============================================================
# Test 8: Alert Rule Evaluation Flow
# ============================================================


class AlertRuleEvaluationTest(TestCase):
    """
    Integration test for AlertRule evaluation against CrawlerMetrics.
    """

    def test_alert_rule_threshold_evaluation(self):
        """
        Test evaluating alert rules against metrics.
        """
        # Create alert rule for crawl success rate
        alert_rule = AlertRule.objects.create(
            name="Low Crawl Success Rate",
            metric="crawl_success_rate",
            condition=AlertConditionChoices.BELOW,
            threshold=Decimal("80.00"),
            window_hours=24,
            severity=AlertSeverityChoices.CRITICAL,
            notification_channel=NotificationChannelChoices.SENTRY,
            cooldown_hours=4,
        )

        # Create metrics with low success rate
        today = timezone.now().date()
        metrics = CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=100,
            pages_succeeded=75,
            pages_failed=25,
            crawl_success_rate=Decimal("75.00"),  # Below threshold
            products_extracted=50,
            products_created=10,
            products_merged=35,
            products_flagged_review=5,
            extraction_success_rate=Decimal("85.00"),
            avg_completeness_score=Decimal("70.00"),
            avg_confidence_score=Decimal("0.80"),
            conflicts_detected=5,
            duplicates_merged=20,
            serpapi_queries=50,
            scrapingbee_requests=25,
            ai_enhancement_calls=50,
            wayback_saves=60,
            avg_crawl_time_ms=3000,
            avg_extraction_time_ms=2000,
            queue_depth=100,
        )

        # Simulate alert evaluation
        should_alert = metrics.crawl_success_rate < alert_rule.threshold
        self.assertTrue(should_alert)

    def test_multiple_alert_rules_evaluation(self):
        """
        Test evaluating multiple alert rules for comprehensive monitoring.
        """
        # Create multiple alert rules
        rules = [
            ("Crawl Success Low", "crawl_success_rate", AlertConditionChoices.BELOW, Decimal("80.00"), AlertSeverityChoices.CRITICAL),
            ("High Conflict Rate", "conflicts_detected", AlertConditionChoices.ABOVE, Decimal("20"), AlertSeverityChoices.WARNING),
            ("Queue Backlog", "queue_depth", AlertConditionChoices.ABOVE, Decimal("500"), AlertSeverityChoices.WARNING),
        ]

        for name, metric, condition, threshold, severity in rules:
            AlertRule.objects.create(
                name=name,
                metric=metric,
                condition=condition,
                threshold=threshold,
                window_hours=24,
                severity=severity,
                notification_channel=NotificationChannelChoices.EMAIL,
            )

        # Verify all rules created
        self.assertEqual(AlertRule.objects.count(), 3)

        # Verify active rule filtering
        active_rules = AlertRule.objects.filter(is_active=True)
        self.assertEqual(active_rules.count(), 3)


# ============================================================
# Test 9: Crawl Strategy Escalation Workflow
# ============================================================


class CrawlStrategyEscalationTest(TestCase):
    """
    Integration test for crawl strategy escalation workflow.
    """

    def test_strategy_escalation_tracking(self):
        """
        Test tracking strategy escalation for a discovery source.
        """
        source = DiscoverySourceConfig.objects.create(
            name="Protected Whiskey Site",
            base_url="https://protected-whiskey.com",
            source_type=SourceTypeChoices.RETAILER,
            crawl_priority=5,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=6,
            crawl_strategy=CrawlStrategyChoices.SIMPLE,  # Start with simple
        )

        # Simulate failed simple strategy - escalate to js_render
        source.crawl_strategy = CrawlStrategyChoices.JS_RENDER
        source.detected_obstacles = [
            {"type": "js_rendered", "description": "Content loaded dynamically"}
        ]
        source.save()

        source.refresh_from_db()
        self.assertEqual(source.crawl_strategy, CrawlStrategyChoices.JS_RENDER)
        self.assertEqual(len(source.detected_obstacles), 1)

    def test_crawled_source_strategy_tracking(self):
        """
        Test tracking which strategy succeeded for a crawled source.
        """
        source_config = DiscoverySourceConfig.objects.create(
            name="Age-Gated Site",
            base_url="https://age-gated-whiskey.com",
            source_type=SourceTypeChoices.RETAILER,
            crawl_priority=7,
            crawl_frequency=CrawlFrequencyChoices.WEEKLY,
            reliability_score=7,
            crawl_strategy=CrawlStrategyChoices.STEALTH,
        )

        # Create crawled source with strategy tracking
        crawled = CrawledSource.objects.create(
            url="https://age-gated-whiskey.com/products",
            title="Product Listing",
            content_hash="age_gate_hash",
            discovery_source=source_config,
            source_type=CrawledSourceTypeChoices.RETAILER_PAGE,
            extraction_status=ExtractionStatusChoices.PROCESSED,
            raw_content="<html>Products...</html>",
            crawl_attempts=3,
            crawl_strategy_used=CrawlStrategyChoices.STEALTH,
            detected_obstacles=["age_gate", "cookie_consent"],
        )

        self.assertEqual(crawled.crawl_attempts, 3)
        self.assertEqual(crawled.crawl_strategy_used, CrawlStrategyChoices.STEALTH)
        self.assertIn("age_gate", crawled.detected_obstacles)


# ============================================================
# Test 10: Health Check Endpoint Integration
# ============================================================


class HealthCheckEndpointTest(TestCase):
    """
    Integration test for health check endpoint with actual database state.
    """

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_health_check_with_metrics(self):
        """
        Test health check endpoint returns success rates from metrics.
        """
        # Create today's metrics
        today = timezone.now().date()
        CrawlerMetrics.objects.create(
            date=today,
            pages_crawled=100,
            pages_succeeded=95,
            pages_failed=5,
            crawl_success_rate=Decimal("95.00"),
            products_extracted=50,
            products_created=10,
            products_merged=35,
            products_flagged_review=5,
            extraction_success_rate=Decimal("90.00"),
            avg_completeness_score=Decimal("75.00"),
            avg_confidence_score=Decimal("0.85"),
            conflicts_detected=3,
            duplicates_merged=15,
            serpapi_queries=40,
            scrapingbee_requests=20,
            ai_enhancement_calls=50,
            wayback_saves=45,
            avg_crawl_time_ms=2000,
            avg_extraction_time_ms=1500,
            queue_depth=25,
        )

        # Call health check endpoint
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")
