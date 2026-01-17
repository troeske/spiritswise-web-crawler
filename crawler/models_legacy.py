"""
Django models for Web Crawler System.

Models: CrawlerSource, CrawlerKeyword, Job, CrawledURL, DiscoveredProduct,
        CrawledArticle, ArticleProductMention, CrawlCost, CrawlError

These models support the database-driven crawler configuration system
as specified in specs/web-crawler-architecture.md
"""

import uuid
import hashlib
import json
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import logging

# V3 Quality Gate imports - lazy loaded to avoid circular imports
_quality_gate_v3 = None
_ProductStatus = None


def _get_quality_gate_v3():
    """Lazy load QualityGateV3 to avoid circular imports."""
    global _quality_gate_v3
    if _quality_gate_v3 is None:
        from crawler.services.quality_gate_v3 import QualityGateV3
        _quality_gate_v3 = QualityGateV3()
    return _quality_gate_v3


def _get_product_status():
    """Lazy load ProductStatus to avoid circular imports."""
    global _ProductStatus
    if _ProductStatus is None:
        from crawler.services.quality_gate_v3 import ProductStatus
        _ProductStatus = ProductStatus
    return _ProductStatus

# Schema-driven fingerprint - lazy loaded to avoid circular imports
_schema_fingerprint_module = None


def _get_schema_fingerprint():
    """Lazy load schema_fingerprint module to avoid circular imports."""
    global _schema_fingerprint_module
    if _schema_fingerprint_module is None:
        from crawler.services import schema_fingerprint
        _schema_fingerprint_module = schema_fingerprint
    return _schema_fingerprint_module





class ProductType(models.TextChoices):
    """Product types supported by the crawler."""

    WHISKEY = "whiskey", "Whiskey"
    PORT_WINE = "port_wine", "Port Wine"
    GIN = "gin", "Gin"
    RUM = "rum", "Rum"
    TEQUILA = "tequila", "Tequila"
    VODKA = "vodka", "Vodka"
    BRANDY = "brandy", "Brandy"
    SAKE = "sake", "Sake"


class SourceCategory(models.TextChoices):
    """Categories of content sources."""

    REVIEW = "review", "Review Site"
    RETAILER = "retailer", "Retailer"
    PRODUCER = "producer", "Producer Website"
    COMPETITION = "competition", "Competition/Awards"
    NEWS = "news", "News/Blog"
    DATABASE = "database", "Product Database"


class SearchContext(models.TextChoices):
    """Context for keyword searches."""

    NEW_RELEASE = "new_release", "New Release"
    REVIEW = "review", "Review"
    COMPETITION = "competition", "Competition/Award"
    PRICING = "pricing", "Pricing Intelligence"
    GENERAL = "general", "General Discovery"


# CrawlJobStatus REMOVED - replaced by JobStatus (see line ~6439)


class DiscoveredProductStatus(models.TextChoices):
    """
    Status of a discovered product - V3 enrichment pipeline status hierarchy.

    V3 Status Hierarchy (lowest to highest):
    - REJECTED: Not a valid product or missing required field (name)
    - SKELETON: Has name only, minimal data
    - PARTIAL: Has basic required fields (name, brand, abv, etc.)
    - BASELINE: All required fields met, has core tasting profile
    - ENRICHED: Baseline + mouthfeel + advanced fields satisfied
    - COMPLETE: 90%+ ECP threshold reached

    Special statuses:
    - VERIFIED: Multi-source verified (highest quality)
    - MERGED: Merged into another product

    V3 Spec Reference: ENRICHMENT_PIPELINE_V3_SPEC.md Section 2 & 6.1
    """

    # V3 Status Hierarchy (in ascending order)
    REJECTED = "rejected", "Rejected"
    SKELETON = "skeleton", "Skeleton"
    INCOMPLETE = "incomplete", "Incomplete"  # Alias for SKELETON for backward compat
    PARTIAL = "partial", "Partial"
    BASELINE = "baseline", "Baseline"  # V3: All required fields met
    ENRICHED = "enriched", "Enriched"  # V3: Baseline + advanced fields
    COMPLETE = "complete", "Complete"  # V3: 90%+ ECP threshold
    VERIFIED = "verified", "Verified"  # Multi-source verified
    MERGED = "merged", "Merged"

    # Legacy status values - kept for migration compatibility
    PENDING = "pending", "Pending Review (Legacy)"
    APPROVED = "approved", "Approved (Legacy)"
    DUPLICATE = "duplicate", "Duplicate (Legacy)"


class AgeGateType(models.TextChoices):
    """Types of age gate mechanisms."""

    NONE = "none", "None"
    COOKIE = "cookie", "Cookie-based"
    CLICK = "click", "Click confirmation"
    FORM = "form", "Form submission"


class DiscoveryMethod(models.TextChoices):
    """Methods by which sources are discovered."""

    HUB = "hub", "Hub and Spoke"
    SEARCH = "search", "Search Discovery"
    COMPETITION = "competition", "Competition/Award"
    MANUAL = "manual", "Manually Added"


class DiscoverySource(models.TextChoices):
    """Sources of product discovery."""

    COMPETITION = "competition", "Competition/Award"
    HUB_SPOKE = "hub_spoke", "Hub and Spoke"
    SEARCH = "search", "Search Discovery"
    DIRECT = "direct", "Direct Crawl"


class MentionType(models.TextChoices):
    """Types of product mentions in articles."""

    REVIEW = "review", "Full Review"
    MENTION = "mention", "Brief Mention"
    COMPARISON = "comparison", "Comparison"
    RECOMMENDATION = "recommendation", "Recommendation"
    AWARD = "award", "Award/Recognition"


class CostService(models.TextChoices):
    """External services with associated costs."""

    SERPAPI = "serpapi", "SerpAPI"
    SCRAPINGBEE = "scrapingbee", "ScrapingBee"
    OPENAI = "openai", "OpenAI"


class ErrorType(models.TextChoices):
    """Types of crawl errors."""

    CONNECTION = "connection", "Connection Error"
    TIMEOUT = "timeout", "Timeout"
    BLOCKED = "blocked", "Blocked/403"
    AGE_GATE = "age_gate", "Age Gate Failed"
    RATE_LIMIT = "rate_limit", "Rate Limited"
    PARSE = "parse", "Parse Error"
    API = "api", "API Error"
    UNKNOWN = "unknown", "Unknown Error"




# ============================================================
# Task Group 20: Demand Signal & Market Positioning Choices
# ============================================================


class TrendDirectionChoices(models.TextChoices):
    """
    Task Group 20: Trend direction choices for demand signals.

    Indicates the direction of popularity/demand trend:
    - rising: Increasing demand/popularity
    - stable: Steady demand/popularity
    - declining: Decreasing demand/popularity
    """

    RISING = "rising", "Rising"
    STABLE = "stable", "Stable"
    DECLINING = "declining", "Declining"


class PriceTierChoices(models.TextChoices):
    """
    Task Group 20: Price tier choices for market positioning.

    Categories based on retail price positioning:
    - budget: Entry level, typically under $25
    - value: Good value, typically $25-50
    - mid_range: Mid-market, typically $50-100
    - premium: Premium quality, typically $100-200
    - ultra_premium: High-end, typically $200-500
    - luxury: Ultra-luxury/collector, typically $500+
    """

    BUDGET = "budget", "Budget"
    VALUE = "value", "Value"
    MID_RANGE = "mid_range", "Mid-Range"
    PREMIUM = "premium", "Premium"
    ULTRA_PREMIUM = "ultra_premium", "Ultra-Premium"
    LUXURY = "luxury", "Luxury"


class TargetAudienceChoices(models.TextChoices):
    """
    Task Group 20: Target audience choices for market positioning.

    Categories based on intended consumer profile:
    - beginner: New to spirits, seeking approachable options
    - casual: Occasional drinker, price-conscious
    - enthusiast: Passionate hobbyist, seeks quality
    - collector: Focused on rare/limited editions
    - investor: Views spirits as investment assets
    """

    BEGINNER = "beginner", "Beginner"
    CASUAL = "casual", "Casual"
    ENTHUSIAST = "enthusiast", "Enthusiast"
    COLLECTOR = "collector", "Collector"
    INVESTOR = "investor", "Investor"


# ============================================================
# Task Group 21: Stock Level Choices for ProductAvailability
# ============================================================


class StockLevelChoices(models.TextChoices):
    """
    Task Group 21: Stock level choices for ProductAvailability.

    Indicates the stock status at a retailer:
    - in_stock: Product is available for purchase
    - low_stock: Limited quantity remaining
    - out_of_stock: Currently unavailable
    - pre_order: Available for pre-order before release
    - discontinued: No longer being sold/produced
    """

    IN_STOCK = "in_stock", "In Stock"
    LOW_STOCK = "low_stock", "Low Stock"
    OUT_OF_STOCK = "out_of_stock", "Out of Stock"
    PRE_ORDER = "pre_order", "Pre-Order"
    DISCONTINUED = "discontinued", "Discontinued"


# ============================================================
# Task Group 22: CategoryInsight Trending Direction Choices
# ============================================================


class CategoryTrendingDirectionChoices(models.TextChoices):
    """
    Task Group 22: Trending direction choices for CategoryInsight.

    Indicates the market health and trend direction for a category:
    - hot: Very strong growth, high demand
    - rising: Positive trend, increasing interest
    - stable: Steady market, no significant change
    - declining: Negative trend, decreasing interest
    - cold: Weak market, low demand
    """

    HOT = "hot", "Hot"
    RISING = "rising", "Rising"
    STABLE = "stable", "Stable"
    DECLINING = "declining", "Declining"
    COLD = "cold", "Cold"


# ============================================================
# Task Group 23: PurchaseRecommendation Choice Enums
# ============================================================


class RecommendationTierChoices(models.TextChoices):
    """
    Task Group 23: Recommendation tier choices for PurchaseRecommendation.

    Indicates the urgency/priority of the purchase recommendation:
    - must_stock: Critical item to have in inventory
    - recommended: Strongly suggested for inventory
    - consider: Worth evaluating for inventory
    - watch: Monitor for future consideration
    - skip: Not recommended for current inventory
    """

    MUST_STOCK = "must_stock", "Must Stock"
    RECOMMENDED = "recommended", "Recommended"
    CONSIDER = "consider", "Consider"
    WATCH = "watch", "Watch"
    SKIP = "skip", "Skip"


class MarginPotentialChoices(models.TextChoices):
    """
    Task Group 23: Margin potential choices for PurchaseRecommendation.

    Indicates the expected profit margin level:
    - low: Low margin potential (<15%)
    - medium: Medium margin potential (15-25%)
    - high: High margin potential (25-40%)
    - premium: Premium margin potential (>40%)
    """

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    PREMIUM = "premium", "Premium"


class TurnoverEstimateChoices(models.TextChoices):
    """
    Task Group 23: Turnover estimate choices for PurchaseRecommendation.

    Indicates the expected inventory turnover speed:
    - slow: Slow turnover (>90 days)
    - moderate: Moderate turnover (30-90 days)
    - fast: Fast turnover (14-30 days)
    - very_fast: Very fast turnover (<14 days)
    """

    SLOW = "slow", "Slow"
    MODERATE = "moderate", "Moderate"
    FAST = "fast", "Fast"
    VERY_FAST = "very_fast", "Very Fast"


class RiskLevelChoices(models.TextChoices):
    """
    Task Group 23: Risk level choices for PurchaseRecommendation.

    Indicates the risk level associated with stocking the product:
    - low: Low risk (established product, stable demand)
    - medium: Medium risk (newer product, moderate demand uncertainty)
    - high: High risk (niche product, volatile demand, high investment)
    """

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class OutcomeChoices(models.TextChoices):
    """
    Task Group 23: Outcome choices for PurchaseRecommendation tracking.

    Indicates the actual outcome after acting on a recommendation:
    - success: Recommendation led to successful sales/profit
    - moderate: Recommendation had moderate success
    - poor: Recommendation did not perform as expected
    """

    SUCCESS = "success", "Success"
    MODERATE = "moderate", "Moderate"
    POOR = "poor", "Poor"


# ============================================================
# Task Group 25: European Market Choice Enums
# ============================================================


class OriginRegionChoices(models.TextChoices):
    """
    Task Group 25: Origin region choices for European market focus.

    Indicates the geographic origin of the product for import classification:
    - eu: European Union (domestic for EU retailers)
    - uk: United Kingdom (post-Brexit import complexity)
    - usa: United States of America
    - japan: Japan (premium import market)
    - rest_of_world: All other regions
    """

    EU = "eu", "European Union"
    UK = "uk", "United Kingdom"
    USA = "usa", "United States"
    JAPAN = "japan", "Japan"
    REST_OF_WORLD = "rest_of_world", "Rest of World"


class ImportComplexityChoices(models.TextChoices):
    """
    Task Group 25: Import complexity choices for European market.

    Indicates the import complexity and regulatory burden for German retailers:
    - eu_domestic: Within EU, no customs, minimal paperwork
    - uk_post_brexit: UK imports with Brexit-related complexity
    - usa_import: US imports with standard import procedures
    - japan_import: Japan imports, typically premium spirits
    - other_import: All other international imports
    """

    EU_DOMESTIC = "eu_domestic", "EU Domestic"
    UK_POST_BREXIT = "uk_post_brexit", "UK Post-Brexit"
    USA_IMPORT = "usa_import", "USA Import"
    JAPAN_IMPORT = "japan_import", "Japan Import"
    OTHER_IMPORT = "other_import", "Other Import"


# ============================================================
# Task Group 5: DiscoverySourceConfig Choices
# ============================================================


class SourceTypeChoices(models.TextChoices):
    """
    Task Group 5: Source type choices for DiscoverySourceConfig.

    Classifies the type of content source:
    - award_competition: Award/competition results pages
    - review_blog: Whiskey/spirit review sites
    - retailer: Online retailer product pages
    - distillery_official: Official distillery websites
    - news_outlet: News and press outlets
    - aggregator: Aggregator sites that collect data from multiple sources
    """

    AWARD_COMPETITION = "award_competition", "Award/Competition"
    REVIEW_BLOG = "review_blog", "Review/Blog"
    RETAILER = "retailer", "Retailer"
    DISTILLERY_OFFICIAL = "distillery_official", "Distillery Official"
    NEWS_OUTLET = "news_outlet", "News Outlet"
    AGGREGATOR = "aggregator", "Aggregator"


class CrawlFrequencyChoices(models.TextChoices):
    """
    Task Group 5: Crawl frequency choices for DiscoverySourceConfig.

    Defines how often a source should be crawled:
    - daily: Crawl once per day
    - weekly: Crawl once per week
    - monthly: Crawl once per month
    - on_demand: Only crawl when manually triggered
    """

    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    ON_DEMAND = "on_demand", "On Demand"


class CrawlStrategyChoices(models.TextChoices):
    """
    Task Group 5: Crawl strategy choices for DiscoverySourceConfig.

    Defines the crawl strategy to use:
    - simple: Basic HTTP requests
    - js_render: JavaScript rendering required
    - stealth: Stealth mode with premium proxies
    - manual: Manual crawling required
    """

    SIMPLE = "simple", "Simple"
    JS_RENDER = "js_render", "JS Render"
    STEALTH = "stealth", "Stealth"
    MANUAL = "manual", "Manual"


# ============================================================
# Task Group 6: CrawledSource REMOVED - replaced by CrawledPage
# CrawledSourceTypeChoices, ExtractionStatusChoices, WaybackStatusChoices REMOVED
# ============================================================


# ============================================================
# Task Group 28: AlertRule Choice Enums
# ============================================================


class AlertConditionChoices(models.TextChoices):
    """
    Task Group 28: Condition choices for AlertRule.

    Defines how the metric should be evaluated against the threshold:
    - below: Trigger when metric falls below threshold
    - above: Trigger when metric exceeds threshold
    - equals: Trigger when metric equals threshold
    - changed_by: Trigger when metric changes by more than threshold percentage
    """

    BELOW = "below", "Below"
    ABOVE = "above", "Above"
    EQUALS = "equals", "Equals"
    CHANGED_BY = "changed_by", "Changed By"


class AlertSeverityChoices(models.TextChoices):
    """
    Task Group 28: Severity level choices for AlertRule.

    Defines the severity/urgency of the alert:
    - info: Informational, no action required
    - warning: Warning, should be reviewed
    - critical: Critical, immediate attention required
    """

    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class NotificationChannelChoices(models.TextChoices):
    """
    Task Group 28: Notification channel choices for AlertRule.

    Defines where alert notifications should be sent:
    - email: Send alert via email
    - slack: Send alert to Slack channel
    - sentry: Log alert to Sentry
    """

    EMAIL = "email", "Email"
    SLACK = "slack", "Slack"
    SENTRY = "sentry", "Sentry"


# ============================================================
# Task Group 19: Completeness Scoring Choices
# ============================================================


class CompletenessScoreTierChoices(models.TextChoices):
    """
    Task Group 19: Completeness tier choices for DiscoveredProduct.

    Indicates the data completeness level of a product:
    - complete: All required fields filled (90-100%)
    - good: Most fields filled (70-89%)
    - partial: Some fields filled (40-69%)
    - skeleton: Minimal data (0-39%)
    """

    COMPLETE = "complete", "Complete"
    GOOD = "good", "Good"
    PARTIAL = "partial", "Partial"
    SKELETON = "skeleton", "Skeleton"


# ============================================================
# Task Group 3: Spirit-Type Extension Choices
# ============================================================


class WhiskeyTypeChoices(models.TextChoices):
    """
    Task Group 3: Whiskey type choices for WhiskeyDetails.

    Classifies the type of whiskey.
    """
    SCOTCH_SINGLE_MALT = "scotch_single_malt", "Scotch Single Malt"
    SCOTCH_BLEND = "scotch_blend", "Scotch Blend"
    BOURBON = "bourbon", "Bourbon"
    TENNESSEE = "tennessee", "Tennessee"
    RYE = "rye", "Rye"
    IRISH_SINGLE_POT = "irish_single_pot", "Irish Single Pot Still"
    IRISH_SINGLE_MALT = "irish_single_malt", "Irish Single Malt"
    IRISH_BLEND = "irish_blend", "Irish Blend"
    JAPANESE = "japanese", "Japanese"
    CANADIAN = "canadian", "Canadian"
    INDIAN = "indian", "Indian"
    TAIWANESE = "taiwanese", "Taiwanese"
    AUSTRALIAN = "australian", "Australian"
    AMERICAN_SINGLE_MALT = "american_single_malt", "American Single Malt"
    WORLD_WHISKEY = "world_whiskey", "World Whiskey"


class PortStyleChoices(models.TextChoices):
    """
    Task Group 3: Port wine style choices for PortWineDetails.
    """
    RUBY = "ruby", "Ruby"
    TAWNY = "tawny", "Tawny"
    WHITE = "white", "White"
    ROSE = "rose", "Rose"
    LBV = "lbv", "Late Bottled Vintage (LBV)"
    VINTAGE = "vintage", "Vintage"
    COLHEITA = "colheita", "Colheita"
    CRUSTED = "crusted", "Crusted"
    SINGLE_QUINTA = "single_quinta", "Single Quinta"
    GARRAFEIRA = "garrafeira", "Garrafeira"


class MedalChoices(models.TextChoices):
    """
    Task Group 4: Medal choices for awards.
    """
    DOUBLE_GOLD = "double_gold", "Double Gold"
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"
    BRONZE = "bronze", "Bronze"
    BEST_IN_CLASS = "best_in_class", "Best in Class"
    CATEGORY_WINNER = "category_winner", "Category Winner"


class ImageTypeChoices(models.TextChoices):
    """
    Task Group 4: Image type choices for ProductImage.
    """
    BOTTLE = "bottle", "Bottle"
    LABEL = "label", "Label"
    PACKAGING = "packaging", "Packaging"
    LIFESTYLE = "lifestyle", "Lifestyle"


class MatchStatusChoices(models.TextChoices):
    """
    Task Group 12: Match status choices for ProductCandidate.
    """
    PENDING = "pending", "Pending"
    MATCHED = "matched", "Matched"
    NEW_PRODUCT = "new_product", "New Product"
    NEEDS_REVIEW = "needs_review", "Needs Review"

# Alias for tests that use ProductCandidateMatchStatus
ProductCandidateMatchStatus = MatchStatusChoices



class ReleaseStatusChoices(models.TextChoices):
    """
    Task Group 18: Release status choices for NewRelease.
    """
    RUMORED = "rumored", "Rumored"
    ANNOUNCED = "announced", "Announced"
    PRE_ORDER = "pre_order", "Pre-Order"
    RELEASED = "released", "Released"
    CANCELLED = "cancelled", "Cancelled"


class PriceAlertTypeChoices(models.TextChoices):
    """
    Task Group 17: Alert type choices for PriceAlert.
    """
    PRICE_DROP = "price_drop", "Price Drop"
    PRICE_SPIKE = "price_spike", "Price Spike"
    NEW_LOW = "new_low", "New Low"
    BACK_IN_STOCK = "back_in_stock", "Back in Stock"


class PriceTrendChoices(models.TextChoices):
    """
    Task Group 16: Price trend choices.
    """
    RISING = "rising", "Rising"
    STABLE = "stable", "Stable"
    FALLING = "falling", "Falling"


class PeatLevelChoices(models.TextChoices):
    """
    Task Group 3: Peat level choices for WhiskeyDetails.
    """
    UNPEATED = "unpeated", "Unpeated"
    LIGHTLY_PEATED = "lightly_peated", "Lightly Peated"
    MEDIUM_PEATED = "medium_peated", "Medium Peated"
    HEAVILY_PEATED = "heavily_peated", "Heavily Peated"


class DouroSubregionChoices(models.TextChoices):
    """
    Task Group 3: Douro subregion choices for PortWineDetails.
    """
    BAIXO_CORGO = "baixo_corgo", "Baixo Corgo"
    CIMA_CORGO = "cima_corgo", "Cima Corgo"
    DOURO_SUPERIOR = "douro_superior", "Douro Superior"


# Alias for tests that use DiscoverySourceTypeChoices
DiscoverySourceTypeChoices = SourceTypeChoices


# ============================================================
# V2 Architecture: Configuration Models
# Spec: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2
#
# Note: FieldTypeChoices, FieldGroupChoices, TargetModelChoices removed.
# Field definitions now managed via ProductTypeSchema.schema JSON field.
# ============================================================
#
# Note: The following models have been REMOVED as part of the database cleanup:
#
# - ProductTypeConfig: Removed in migration 0060_remove_legacy_config_models
#   All configuration now managed via ProductTypeSchema model
#
# - FieldDefinition: Removed in migration 0055_remove_field_definition
#   Field definitions now in ProductTypeSchema.schema JSON field
#
# - QualityGateConfig: Removed in migration 0056_remove_quality_gate_config
#   Quality gates now in ProductTypeSchema.schema['quality_gates']
#
# - EnrichmentConfig: Removed in migration 0060_remove_legacy_config_models
#   Enrichment templates now in ProductTypeSchema.schema['enrichment_templates']
#
# - PipelineConfig: Removed in migration 0060_remove_legacy_config_models
#   Pipeline settings now in ProductTypeSchema.schema
#
# - FieldGroup: Removed in migration 0060_remove_legacy_config_models
#   Field groups now in ProductTypeSchema.schema['field_groups']
#
# All services should now use ProductTypeSchema and ConfigService to access
# configuration. See:
# - crawler/models/product_type_schema.py (or ProductTypeSchema in this file)
# - crawler/services/config_service.py
#
# ============================================================


# ============================================================
# Unified Crawler Scheduling (replaces separate scheduling models)
# ============================================================


class ScheduleCategory(models.TextChoices):
    """Categories of crawl schedules."""

    COMPETITION = "competition", "Competition/Awards"
    DISCOVERY = "discovery", "Discovery Search"
    RETAILER = "retailer", "Retailer Monitoring"
    SINGLE_PRODUCT = "single_product", "Single Product Extraction"


class ScheduleFrequency(models.TextChoices):
    """Frequency options for scheduling."""

    HOURLY = "hourly", "Hourly"
    EVERY_6_HOURS = "every_6_hours", "Every 6 Hours"
    EVERY_12_HOURS = "every_12_hours", "Every 12 Hours"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Bi-weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"


class CrawlSchedule(models.Model):
    """
    Unified scheduling model for all crawler flows.

    Replaces both CrawlerSource (for scheduling) and DiscoverySchedule.
    Category determines which orchestrator handles the schedule:
    - COMPETITION: CompetitionOrchestrator
    - DISCOVERY: DiscoveryOrchestrator
    - RETAILER: Future retailer monitoring
    """

    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # Category determines which orchestrator handles this schedule
    category = models.CharField(
        max_length=20,
        choices=ScheduleCategory.choices,
        default=ScheduleCategory.DISCOVERY,
        db_index=True,
    )

    # ============================================
    # SCHEDULING CONFIGURATION
    # ============================================

    is_active = models.BooleanField(default=True, db_index=True)
    frequency = models.CharField(
        max_length=20,
        choices=ScheduleFrequency.choices,
        default=ScheduleFrequency.DAILY,
    )
    priority = models.IntegerField(
        default=5,
        help_text="Higher priority schedules run first (1-10)",
    )

    # Scheduling timestamps
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True, db_index=True)

    # ============================================
    # SEARCH CONFIGURATION (Used by all categories)
    # ============================================

    search_terms = models.JSONField(
        default=list,
        help_text="""
        For COMPETITION: List of competition identifiers with years
            e.g., ["iwsc:2024", "iwsc:2025", "wwa:2024"]
        For DISCOVERY: List of search queries
            e.g., ["best single malt whisky 2024", "award winning bourbon"]
        """,
    )

    max_results_per_term = models.IntegerField(
        default=10,
        help_text="Maximum results to process per search term",
    )

    # ============================================
    # FILTERING CONFIGURATION
    # ============================================

    product_types = models.JSONField(
        default=list,
        help_text="Filter to specific product types: ['whiskey', 'port_wine', etc.]",
    )

    exclude_domains = models.JSONField(
        default=list,
        help_text="Domains to exclude from results",
    )

    # ============================================
    # COMPETITION-SPECIFIC CONFIGURATION
    # ============================================

    # Base URL for competition sites (only used for COMPETITION category)
    base_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Base URL for competition results page (COMPETITION only)",
    )

    # Compliance flags (for direct URL crawling)
    robots_txt_compliant = models.BooleanField(default=True)
    tos_compliant = models.BooleanField(default=True)

    # ============================================
    # QUOTA & LIMITS
    # ============================================

    daily_quota = models.IntegerField(
        default=100,
        help_text="Maximum API calls per day for this schedule",
    )

    monthly_quota = models.IntegerField(
        default=2000,
        help_text="Maximum API calls per month for this schedule",
    )

    # ============================================
    # ENRICHMENT CONFIGURATION
    # ============================================

    enrich = models.BooleanField(
        default=False,
        help_text="Run verification pipeline on extracted products",
    )

    # ============================================
    # TRACKING & METADATA
    # ============================================

    total_runs = models.IntegerField(default=0)
    total_products_found = models.IntegerField(default=0)
    total_products_new = models.IntegerField(default=0)
    total_products_duplicate = models.IntegerField(default=0)
    total_products_verified = models.IntegerField(default=0)
    total_errors = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Additional configuration (extensible)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional category-specific configuration",
    )

    class Meta:
        db_table = "crawl_schedule"
        ordering = ["-priority", "name"]
        indexes = [
            models.Index(fields=["is_active", "next_run"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def calculate_next_run(self):
        """Calculate the next run time based on frequency."""
        from datetime import timedelta

        base_time = self.last_run or timezone.now()

        frequency_deltas = {
            ScheduleFrequency.HOURLY: timedelta(hours=1),
            ScheduleFrequency.EVERY_6_HOURS: timedelta(hours=6),
            ScheduleFrequency.EVERY_12_HOURS: timedelta(hours=12),
            ScheduleFrequency.DAILY: timedelta(days=1),
            ScheduleFrequency.WEEKLY: timedelta(weeks=1),
            ScheduleFrequency.BIWEEKLY: timedelta(weeks=2),
            ScheduleFrequency.MONTHLY: timedelta(days=30),
            ScheduleFrequency.QUARTERLY: timedelta(days=90),
        }

        delta = frequency_deltas.get(self.frequency, timedelta(days=1))
        return base_time + delta

    def update_next_run(self):
        """Update next_run after a successful run."""
        self.last_run = timezone.now()
        self.next_run = self.calculate_next_run()
        self.total_runs += 1
        self.save(update_fields=["last_run", "next_run", "total_runs"])

    def record_run_stats(self, products_found: int, products_new: int,
                         products_duplicate: int, errors: int,
                         products_verified: int = 0):
        """Record statistics from a completed run."""
        self.total_products_found += products_found
        self.total_products_new += products_new
        self.total_products_duplicate += products_duplicate
        self.total_products_verified += products_verified
        self.total_errors += errors
        self.save(update_fields=[
            "total_products_found", "total_products_new",
            "total_products_duplicate", "total_products_verified", "total_errors"
        ])

    def get_product_entries(self):
        """
        Get product entries for SINGLE_PRODUCT category schedules.

        For SINGLE_PRODUCT schedules, search_terms contains a list of product
        entry dictionaries with name, brand, product_type, etc.

        Returns:
            List of product entry dictionaries
        """
        if self.category != ScheduleCategory.SINGLE_PRODUCT:
            return []
        return self.search_terms or []

    def get_single_product_config(self):
        """
        Get single product configuration from the config field.

        Returns:
            Dictionary with single product configuration options:
            - skip_if_enriched_within_days: Days to skip re-enrichment (default: 30)
            - max_sources_per_product: Max sources to search (default: 5)
        """
        config = self.config or {}
        return {
            'skip_if_enriched_within_days': config.get('skip_if_enriched_within_days', 30),
            'max_sources_per_product': config.get('max_sources_per_product', 5),
        }


class CrawlerSource(models.Model):
    """
    Configuration for a crawlable content source.

    Managed via Django Admin for easy updates without code changes.
    """

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text="Human-readable name")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-safe identifier")
    base_url = models.URLField(help_text="Base URL of the source")

    # Classification
    product_types = models.JSONField(
        default=list, help_text="List of product types: ['whiskey', 'port_wine']"
    )
    category = models.CharField(
        max_length=20, choices=SourceCategory.choices, help_text="Type of source"
    )

    # Crawl Configuration
    is_active = models.BooleanField(default=True, help_text="Enable/disable crawling")
    priority = models.IntegerField(default=5, help_text="1-10, higher = more important")
    crawl_frequency_hours = models.IntegerField(
        default=24, help_text="How often to crawl (hours)"
    )
    rate_limit_requests_per_minute = models.IntegerField(
        default=10, help_text="Max requests per minute to this domain"
    )

    # Technical Requirements
    requires_javascript = models.BooleanField(
        default=False, help_text="Requires headless browser"
    )
    requires_proxy = models.BooleanField(default=False, help_text="Requires proxy rotation")
    requires_authentication = models.BooleanField(default=False, help_text="Requires login")
    custom_headers = models.JSONField(
        default=dict, blank=True, help_text="Custom HTTP headers"
    )

    # Task 2.2: Age Gate Configuration
    age_gate_type = models.CharField(
        max_length=20,
        choices=AgeGateType.choices,
        default=AgeGateType.NONE,
        help_text="Type of age gate mechanism used by this source",
    )
    age_gate_cookies = models.JSONField(
        default=dict,
        blank=True,
        help_text="Domain-specific cookies for age gate bypass",
    )
    requires_tier3 = models.BooleanField(
        default=False,
        help_text="Marks ScrapingBee requirement (Tier 3 fetching)",
    )
    discovery_method = models.CharField(
        max_length=20,
        choices=DiscoveryMethod.choices,
        default=DiscoveryMethod.MANUAL,
        help_text="How this source was discovered",
    )

    # URL Patterns
    product_url_patterns = models.JSONField(
        default=list, help_text="Regex patterns for product URLs"
    )
    pagination_pattern = models.CharField(
        max_length=200, blank=True, help_text="URL pattern for pagination (e.g., ?page={page})"
    )
    sitemap_url = models.URLField(blank=True, help_text="Sitemap URL if available")

    # Auto-Queue Configuration
    auto_discover_links = models.BooleanField(
        default=True,
        help_text="Automatically discover and queue links from crawled pages",
    )
    max_crawl_depth = models.IntegerField(
        default=3,
        help_text="Maximum depth to follow links (0 = base URL only)",
    )
    max_pages = models.IntegerField(
        default=100,
        help_text="Maximum pages to crawl per job",
    )

    # Compliance
    robots_txt_compliant = models.BooleanField(
        default=True, help_text="Checked robots.txt compliance"
    )
    tos_compliant = models.BooleanField(
        default=True, help_text="Checked Terms of Service compliance"
    )
    compliance_notes = models.TextField(blank=True, help_text="Notes on compliance requirements")

    # Manual Overrides for Adaptive Fetching
    # Used for competition sites (IWSC, DWWA) or known problematic domains
    manual_tier_override = models.IntegerField(
        null=True,
        blank=True,
        choices=[(1, "Tier 1 - httpx"), (2, "Tier 2 - Playwright"), (3, "Tier 3 - ScrapingBee")],
        help_text="Force specific tier for this source (overrides adaptive selection)",
    )
    manual_timeout_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Force specific timeout in milliseconds for this source",
    )

    # Status Tracking
    last_crawl_at = models.DateTimeField(null=True, blank=True)
    next_crawl_at = models.DateTimeField(null=True, blank=True)
    last_crawl_status = models.CharField(max_length=20, blank=True)
    total_products_found = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="Internal notes")

    def save(self, *args, **kwargs):
        if not kwargs.pop("raw", False):
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "crawler_sources"
        ordering = ["-priority", "name"]
        indexes = [
            models.Index(fields=["is_active", "next_crawl_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["discovery_method"]),
            models.Index(fields=["requires_tier3"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

    def update_next_crawl_time(self):
        """Calculate next crawl time based on frequency."""
        from datetime import timedelta

        self.last_crawl_at = timezone.now()
        self.next_crawl_at = timezone.now() + timedelta(hours=self.crawl_frequency_hours)
        self.save(update_fields=["last_crawl_at", "next_crawl_at"])

    def is_due_for_crawl(self) -> bool:
        """Check if source is due for crawling."""
        if not self.is_active:
            return False
        if self.next_crawl_at is None:
            return True
        return timezone.now() >= self.next_crawl_at


class CrawlerKeyword(models.Model):
    """
    Keywords for product discovery searches.

    Used with search APIs (SerpAPI) and site-specific searches.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keyword = models.CharField(max_length=200, help_text="Search keyword or phrase")

    # Classification
    product_types = models.JSONField(
        default=list, help_text="Applicable product types: ['whiskey', 'port_wine']"
    )
    search_context = models.CharField(
        max_length=20,
        choices=SearchContext.choices,
        default=SearchContext.GENERAL,
        help_text="Context for this keyword",
    )

    # Configuration
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=5, help_text="1-10, higher = search more frequently")
    search_frequency_hours = models.IntegerField(
        default=168, help_text="How often to search (hours)"  # Weekly
    )

    # Tracking
    last_searched_at = models.DateTimeField(null=True, blank=True)
    next_search_at = models.DateTimeField(null=True, blank=True)
    total_results_found = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not kwargs.pop("raw", False):
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "crawler_keywords"
        ordering = ["-priority", "keyword"]
        unique_together = ["keyword", "search_context"]
        indexes = [
            models.Index(fields=["is_active", "next_search_at"]),
            models.Index(fields=["search_context"]),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.search_context})"

    def update_next_search_time(self):
        """Calculate next search time based on frequency."""
        from datetime import timedelta

        self.last_searched_at = timezone.now()
        self.next_search_at = timezone.now() + timedelta(hours=self.search_frequency_hours)
        self.save(update_fields=["last_searched_at", "next_search_at"])


# CrawlJob REMOVED - replaced by unified Job model (see JobType.CRAWL)
# CrawledURL REMOVED - replaced by unified CrawledPage model


class DiscoveredProduct(models.Model):
    """
    Products discovered by the crawler, pending review.

    Temporary storage before integration with inventory management.
    Supports comprehensive product data collection for the multi-pronged
    product discovery system.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source Information
    source = models.ForeignKey(
        CrawlerSource, on_delete=models.SET_NULL, null=True, related_name="discovered_products"
    )
    source_url = models.URLField(max_length=2000)
    crawl_job = models.ForeignKey(
        "Job", on_delete=models.SET_NULL, null=True, related_name="products"
    )

    # Product Identification
    fingerprint = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Hash for deduplication - must be unique per spec",
    )
    product_type = models.CharField(max_length=20, choices=ProductType.choices)

    # Product Basic Info
    name = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Product name - indexed per spec",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Product description",
    )
    abv = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        db_index=True,
        help_text="Alcohol by volume percentage 0-80%",
    )
    age_statement = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Age statement (e.g., '12', '18', 'NAS')",
    )
    volume_ml = models.IntegerField(
        blank=True,
        null=True,
        help_text="Bottle volume in milliliters",
    )
    region = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
        help_text="Product region (e.g., Speyside, Kentucky)",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Country of origin",
    )
    # Task Group 13: GTIN for product matching
    gtin = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        db_index=True,
        help_text="Global Trade Item Number (barcode) for exact product matching",
    )




    # Raw Data - REMOVED (DATABASE CLEANUP)
    # raw_content and raw_content_hash moved to Wayback archiving via EnrichmentSource

    # Extraction confidence (REMOVED: extracted_data, enriched_data JSON blobs per spec)
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Extraction confidence 0.00-1.00",
    )

    # Status - based on completeness and verification
    status = models.CharField(
        max_length=20,
        choices=DiscoveredProductStatus.choices,
        default=DiscoveredProductStatus.INCOMPLETE,
        help_text="Product status: incomplete, partial, complete, verified, rejected, merged",
    )

    # Task 2.3: Discovery source tracking (single source - legacy)
    discovery_source = models.CharField(
        max_length=20,
        choices=DiscoverySource.choices,
        default=DiscoverySource.DIRECT,
        help_text="How this product was discovered",
    )

    # JSON Blob Fields - REMOVED (DATABASE CLEANUP)
    # awards -> ProductAward model (awards_rel)
    # images -> ProductImage model (images_rel)
    # ratings -> ProductRating model (ratings_rel)

    # Press/Article Mentions (JSONField) - named press_mentions to avoid conflict with FK relation
    press_mentions = models.JSONField(
        default=list,
        blank=True,
        help_text="Article mentions: [{url, title, source, date, snippet, mention_type}]",
    )

    # Counter Fields - REMOVED (DATABASE CLEANUP)
    # mention_count -> product.product_sources.count()
    # award_count -> product.awards_rel.count()
    # price_count -> product.prices.count()
    # rating_count -> product.ratings_rel.count()


    # Discovery Sources (JSONField) - tracks multiple discovery methods
    discovery_sources = models.JSONField(
        default=list,
        blank=True,
        help_text="Sources that discovered this product: ['competition', 'serpapi', 'hub_crawl']",
    )

    # ============================================================
    # Multi-Source Verification Fields
    # ============================================================

    source_count = models.IntegerField(
        default=1,
        help_text="Number of unique sources this product data was collected from",
    )
    verified_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Fields verified by multiple sources: ['name', 'abv', 'palate_description']",
    )

    # Task Group 1: Brand relationship
    brand = models.ForeignKey(
        'DiscoveredBrand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Brand this product belongs to",
    )
    # RECT-011: Bottler field for independent bottlings
    bottler = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Independent bottler name (e.g., Gordon & MacPhail)",
    )

    # Price History - REMOVED (DATABASE CLEANUP)
    # price_history -> ProductPrice model (prices)
    # best_price* -> calculated from ProductPrice.objects.filter(product=p).order_by('price').first()
    # matched_product_id, match_confidence -> removed (matching leads to enrichment)

    # ============================================================
    # Task Group 20: Demand Signal & Market Positioning Fields
    # PARTIALLY REMOVED (DATABASE CLEANUP)
    # trend_score, trend_direction, buzz_score, search_interest, is_allocated -> ProductTrend
    # price_tier -> calculated from ProductPrice
    # ============================================================

    # Kept demand signal fields
    is_limited_edition = models.BooleanField(
        default=False,
        help_text="Whether this is a limited edition release",
    )
    batch_size = models.IntegerField(
        blank=True,
        null=True,
        help_text="Number of bottles in batch/release",
    )
    release_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of release (for limited editions)",
    )
    target_audience = models.CharField(
        max_length=20,
        choices=TargetAudienceChoices.choices,
        blank=True,
        null=True,
        help_text="Target audience: beginner, casual, enthusiast, collector, investor",
    )
    # Availability & Pricing Aggregate Fields - REMOVED (DATABASE CLEANUP)
    # availability_score, retailer_count, in_stock_count -> ProductAvailability
    # avg_price_usd, min_price_usd, max_price_usd, price_volatility -> calculated from ProductPrice

    # ============================================================
    # Task Group 25: European Market Fields
    # ============================================================

    # EUR Pricing Fields - PARTIALLY REMOVED (DATABASE CLEANUP)
    # price_eur, price_includes_vat, vat_rate, price_excl_vat -> derive from retailer_country on ProductPrice
    # eu_available, german_available -> ProductAvailability
    # estimated_landed_cost_eur -> calculated from avg_price + shipping + duty
    primary_currency = models.CharField(
        max_length=3,
        default="EUR",
        help_text="Primary currency for this product (ISO 4217)",
    )

    # Import/Availability Fields - kept
    origin_region = models.CharField(
        max_length=20,
        choices=OriginRegionChoices.choices,
        blank=True,
        null=True,
        help_text="Geographic origin region: eu, uk, usa, japan, rest_of_world",
    )
    import_complexity = models.CharField(
        max_length=20,
        choices=ImportComplexityChoices.choices,
        blank=True,
        null=True,
        help_text="Import complexity: eu_domestic, uk_post_brexit, usa_import, japan_import, other_import",
    )

    # EU Regulatory Fields
    eu_label_compliant = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether product has EU-compliant labeling",
    )
    contains_allergens = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether product contains allergens requiring disclosure",
    )
    organic_certified = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether product has organic certification",
    )
    bottle_size_ml = models.IntegerField(
        blank=True,
        null=True,
        help_text="Bottle size in milliliters (700ml spirits, 750ml wine typical in EU)",
    )
    alcohol_duty_category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Alcohol duty category for tax purposes",
    )

    # German Market Fit Field
    german_market_fit = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="German market fit score (1-10, based on price, availability, preferences)",
    )

    # German Language Fields
    name_de = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="German name if different from English name",
    )
    description_de = models.TextField(
        blank=True,
        null=True,
        help_text="German description/tasting notes",
    )

    # ============================================================
    # Task Group 19: Completeness Scoring Fields
    # ============================================================

    completeness_score = models.IntegerField(
        blank=True,
        null=True,
        help_text="Completeness score 1-100 based on filled fields",
    )
    completeness_tier = models.CharField(
        max_length=20,
        choices=CompletenessScoreTierChoices.choices,
        blank=True,
        null=True,
        help_text="Completeness tier: complete, good, partial, skeleton",
    )
    # missing_fields - REMOVED (DATABASE CLEANUP) - calculated by comparing populated fields to schema
    enrichment_priority = models.IntegerField(
        blank=True,
        null=True,
        help_text="Enrichment priority score 1-10 (10=highest priority)",
    )

    # ============================================================
    # Product Category & Classification Fields
    # ============================================================

    category = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Sub-category like 'Single Malt', 'Bourbon', 'Blended'",
    )

    # ============================================================
    # Cask/Maturation Fields
    # ============================================================

    primary_cask = models.JSONField(
        default=list,
        blank=True,
        help_text="List of primary cask types (e.g., ['ex-bourbon', 'american_oak'])",
    )
    finishing_cask = models.JSONField(
        default=list,
        blank=True,
        help_text="List of finishing cask types (e.g., ['sherry', 'oloroso'])",
    )
    wood_type = models.JSONField(
        default=list,
        blank=True,
        help_text="List of wood types (e.g., ['american_oak', 'european_oak'])",
    )
    cask_treatment = models.JSONField(
        default=list,
        blank=True,
        help_text="List of cask treatments (e.g., ['charred', 'toasted'])",
    )
    maturation_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed maturation/aging notes",
    )

    # Conflict Detection Fields - REMOVED (DATABASE CLEANUP)
    # has_conflicts, conflict_details -> ProductConflict model

    # ============================================================
    # Tasting Profile: Appearance/Visual Fields
    # ============================================================

    color_description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of color (e.g., 'Deep amber with golden highlights')",
    )
    color_intensity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Color intensity rating 1-10",
    )
    clarity = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Clarity description (e.g., 'brilliant', 'hazy')",
    )
    viscosity = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Viscosity description (e.g., 'light', 'medium', 'oily')",
    )

    # ============================================================
    # Tasting Profile: Nose/Aroma Fields
    # ============================================================

    nose_description = models.TextField(
        blank=True,
        null=True,
        help_text="Overall nose/aroma description",
    )
    primary_aromas = models.JSONField(
        default=list,
        blank=True,
        help_text="List of primary aroma notes (e.g., ['vanilla', 'honey', 'oak'])",
    )
    primary_intensity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Primary aroma intensity rating 1-10",
    )
    secondary_aromas = models.JSONField(
        default=list,
        blank=True,
        help_text="List of secondary aroma notes (e.g., ['citrus', 'floral'])",
    )
    aroma_evolution = models.TextField(
        blank=True,
        null=True,
        help_text="How aromas evolve over time in the glass",
    )

    # ============================================================
    # Tasting Profile: Palate Fields
    # ============================================================

    palate_flavors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of palate flavor notes (e.g., ['vanilla', 'toffee', 'cinnamon'])",
    )
    initial_taste = models.TextField(
        blank=True,
        null=True,
        help_text="Initial taste/first impression on palate",
    )
    mid_palate_evolution = models.TextField(
        blank=True,
        null=True,
        help_text="How flavors develop mid-palate",
    )
    flavor_intensity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Flavor intensity rating 1-10",
    )
    complexity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Flavor complexity rating 1-10",
    )
    mouthfeel = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Mouthfeel description (e.g., 'oily', 'creamy', 'thin')",
    )
    palate_description = models.TextField(
        blank=True,
        null=True,
        help_text="Overall palate description combining initial taste, evolution, and mouthfeel",
    )

    # ============================================================
    # Tasting Profile: Finish Fields
    # ============================================================

    finish_length = models.IntegerField(
        blank=True,
        null=True,
        help_text="Finish length rating 1-10",
    )
    warmth = models.IntegerField(
        blank=True,
        null=True,
        help_text="Warmth/heat rating 1-10",
    )
    dryness = models.IntegerField(
        blank=True,
        null=True,
        help_text="Dryness rating 1-10",
    )
    finish_flavors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of finish flavor notes (e.g., ['oak', 'spice', 'tobacco'])",
    )
    finish_evolution = models.TextField(
        blank=True,
        null=True,
        help_text="How finish evolves and fades",
    )
    final_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Final lingering notes after finish",
    )
    finish_description = models.TextField(
        blank=True,
        null=True,
        help_text="Overall finish description combining length, warmth, and lingering notes",
    )

    # ============================================================
    # Tasting Profile: Overall Assessment Fields
    # ============================================================

    balance = models.IntegerField(
        blank=True,
        null=True,
        help_text="Overall balance rating 1-10",
    )
    overall_complexity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Overall complexity rating 1-10",
    )
    uniqueness = models.IntegerField(
        blank=True,
        null=True,
        help_text="Uniqueness/distinctiveness rating 1-10",
    )
    drinkability = models.IntegerField(
        blank=True,
        null=True,
        help_text="Drinkability/accessibility rating 1-10",
    )
    price_quality_ratio = models.IntegerField(
        blank=True,
        null=True,
        help_text="Price-quality ratio rating 1-10",
    )
    experience_level = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Recommended experience level (e.g., 'beginner', 'enthusiast', 'expert')",
    )
    serving_recommendation = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Serving recommendation (e.g., 'neat', 'on the rocks', 'cocktail')",
    )
    food_pairings = models.TextField(
        blank=True,
        null=True,
        help_text="Recommended food pairings",
    )

    # ============================================================
    # V3: Enrichment Completion Percentage (ECP) Fields
    # Spec Reference: ENRICHMENT_PIPELINE_V3_SPEC.md Section 3.2
    # ============================================================

    enrichment_completion = models.JSONField(
        default=dict,
        help_text="V3: ECP by field group with missing field lists",
    )
    ecp_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        db_index=True,
        help_text="V3: Total ECP percentage (0-100). 90%+ = COMPLETE status",
    )
    # V3 Enrichment Source Tracking Fields - REMOVED (DATABASE CLEANUP)
    # members_only_sites_detected -> EnrichmentSource with status='members_only'
    # awards_search_completed -> query ProductAward.objects.filter(product=p).exists()
    # enrichment_sources_searched/used/rejected -> EnrichmentSource model
    # field_provenance -> ProductFieldSourceV2 model

    # Kept fields (still needed)
    enrichment_steps_completed = models.IntegerField(
        default=0,
        help_text="V3: Number of enrichment steps completed (0-2 for generic search)",
    )

    last_enrichment_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="V3: Timestamp of last enrichment attempt",
    )

    # ============================================================
    # Dynamic Product Schema: Type-Specific Data
    # Spec Reference: DYNAMIC_PRODUCT_SCHEMA_SPEC.md Section 1
    # ============================================================

    type_specific_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Product-type-specific fields stored as JSON (whiskey_type, distillery, style, etc.)",
    )

    # Metadata
    discovered_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "discovered_products"
        ordering = ["-discovered_at"]
        indexes = [
            models.Index(fields=["status", "discovered_at"]),
            models.Index(fields=["product_type", "status"]),
            models.Index(fields=["fingerprint"]),
            models.Index(fields=["gtin"]),
            models.Index(fields=["discovery_source"]),
            # Indexes for removed fields removed (DATABASE CLEANUP):
            # mention_count, trend_score, price_tier, availability_score, german_available
            # Task Group 25: European market indexes - kept
            models.Index(fields=["origin_region"]),
            models.Index(fields=["german_market_fit"]),
        ]

    def __str__(self):
        return f"{self.name or 'Unknown'} ({self.product_type})"

    def save(self, *args, **kwargs):
        """Automatically compute fingerprint, content hash, completeness and status before saving."""
        # Remove deprecated skip_status_update parameter (V3 always uses Quality Gate)
        # Kept for backwards compatibility with existing callers
        kwargs.pop("skip_status_update", None)

        # raw_content_hash auto-generation removed (DATABASE CLEANUP) - field removed
        if not self.fingerprint and self.name:
            self.fingerprint = self.compute_fingerprint_from_fields()

        # Auto-update completeness score and status using V3 Quality Gate
        # Avoid infinite recursion by checking if we're updating specific fields
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "completeness_score" not in update_fields:
            self.completeness_score = self.calculate_completeness_score()
            # determine_status() now handles REJECTED/MERGED preservation internally
            self.status = self.determine_status()

        super().save(*args, **kwargs)

    def compute_fingerprint_from_fields(self) -> str:
        """Compute fingerprint for deduplication using schema-driven fields.
        
        DATABASE CLEANUP SPEC: Task 13.2 - Product-Agnostic Code Refactoring
        Uses schema_fingerprint module instead of hardcoded product-type logic.
        """
        schema_fp = _get_schema_fingerprint()
        return schema_fp.compute_fingerprint_from_product(self)

    @staticmethod
    def compute_fingerprint(data: dict) -> str:
        """Compute fingerprint from a dict using schema-driven fields.
        
        DATABASE CLEANUP SPEC: Task 13.2 - Product-Agnostic Code Refactoring
        Uses schema_fingerprint module instead of hardcoded product-type logic.
        """
        schema_fp = _get_schema_fingerprint()
        return schema_fp.compute_fingerprint_from_dict(data)

    def check_duplicate(self) -> bool:
        """Check if a product with the same fingerprint already exists."""
        return (
            DiscoveredProduct.objects.filter(fingerprint=self.fingerprint)
            .exclude(id=self.id)
            .exists()
        )

    def approve(self, reviewer: str = None):
        """Approve the discovered product."""
        self.status = DiscoveredProductStatus.APPROVED
        self.reviewed_at = timezone.now()
        if reviewer:
            self.reviewed_by = reviewer
        self.save(update_fields=["status", "reviewed_at", "reviewed_by"])

    def reject(self, reviewer: str = None):
        """Reject the discovered product."""
        self.status = DiscoveredProductStatus.REJECTED
        self.reviewed_at = timezone.now()
        if reviewer:
            self.reviewed_by = reviewer
        self.save(update_fields=["status", "reviewed_at", "reviewed_by"])

    def mark_duplicate(self, matched_id: uuid.UUID = None):
        """Mark product as duplicate."""
        self.status = DiscoveredProductStatus.DUPLICATE
        if matched_id:
            self.matched_product_id = matched_id
        self.save(update_fields=["status", "matched_product_id"])

    # Phase 1: Helper Methods for new fields

    def add_discovery_source(self, source: str) -> None:
        """Add a discovery source if not already present."""
        if self.discovery_sources is None:
            self.discovery_sources = []
        if source not in self.discovery_sources:
            self.discovery_sources.append(source)
            self.save(update_fields=["discovery_sources"])

    def add_press_mention(self, mention: dict) -> None:
        """Add an article/press mention."""
        if self.press_mentions is None:
            self.press_mentions = []
        # Check for duplicate by URL
        existing_urls = [m.get("url") for m in self.press_mentions]
        if mention.get("url") not in existing_urls:
            self.press_mentions.append(mention)
            # mention_count field removed (DATABASE CLEANUP) - count via product_sources.count()
            self.save(update_fields=["press_mentions"])

    # add_rating, update_best_price, add_image methods REMOVED (DATABASE CLEANUP)
    # Use ProductRating, ProductPrice, ProductImage models and product_saver functions instead

    def update_taste_profile(self, profile: dict) -> None:
        """Merge taste profile data into individual columns."""
        update_fields = []

        # Map profile fields to individual columns
        field_mappings = {
            "nose": ("primary_aromas", list),
            "palate": ("palate_flavors", list),
            "finish": ("finish_flavors", list),
            "overall_notes": ("notes", str),
            "nose_description": ("nose_description", str),
            "palate_description": ("palate_description", str),
            "finish_description": ("finish_description", str),
        }

        for profile_key, (model_field, field_type) in field_mappings.items():
            if profile_key in profile and profile[profile_key]:
                if field_type == list:
                    # Merge arrays
                    current_value = getattr(self, model_field, None) or []
                    new_values = profile[profile_key]
                    merged = list(set(current_value) | set(new_values))
                    setattr(self, model_field, merged)
                else:
                    # Only set text fields if not already set
                    if not getattr(self, model_field, None):
                        setattr(self, model_field, profile[profile_key])
                update_fields.append(model_field)

        if update_fields:
            self.save(update_fields=update_fields)

    # ============================================================
    # Completeness & Status Calculation Methods
    # ============================================================

    def calculate_completeness_score(self) -> int:
        """
        Calculate product data completeness score (0-100).

        Scoring weights:
        - Identification: 15 points (name + brand)
        - Basic info: 15 points (type + ABV + description)
        - Tasting profile: 40 points (palate 20, nose 10, finish 10)
        - Enrichment: 20 points (price, images, ratings, awards)
        - Verification bonus: 10 points (multi-source)

        Note: Tasting profile is heavily weighted - cannot reach COMPLETE without palate.
        """
        score = 0

        # ============================================================
        # IDENTIFICATION (15 points max)
        # ============================================================
        if self.name:
            score += 10
        if self.brand_id:
            score += 5

        # ============================================================
        # BASIC PRODUCT INFO (15 points max)
        # ============================================================
        if self.product_type:
            score += 5
        if self.abv:
            score += 5
        # Check for description in the individual column
        if self.description:
            score += 5

        # ============================================================
        # TASTING PROFILE (40 points max) - CRITICAL
        # ============================================================

        # Palate (20 points) - MANDATORY for COMPLETE status
        palate_score = 0
        if self.palate_flavors and len(self.palate_flavors) >= 2:
            palate_score += 10
        if self.palate_description or self.initial_taste:
            palate_score += 5
        if self.mid_palate_evolution:
            palate_score += 3
        if self.mouthfeel:
            palate_score += 2
        score += min(palate_score, 20)

        # Nose (10 points)
        nose_score = 0
        if self.nose_description:
            nose_score += 5
        if self.primary_aromas and len(self.primary_aromas) >= 2:
            nose_score += 5
        score += min(nose_score, 10)

        # Finish (10 points)
        finish_score = 0
        if self.finish_description or self.final_notes:
            finish_score += 5
        if self.finish_flavors and len(self.finish_flavors) >= 2:
            finish_score += 3
        if self.finish_length:
            finish_score += 2
        score += min(finish_score, 10)

        # ============================================================
        # ENRICHMENT DATA (20 points max)
        # Uses related models (DATABASE CLEANUP - Phase 4)
        # ============================================================

        # Pricing (5 points) - via ProductPrice model
        if self.prices.exists():
            score += 5

        # Images (5 points) - via ProductImage model
        if self.images_rel.exists():
            score += 5

        # Ratings (5 points) - via ProductRating model
        if self.ratings_rel.exists():
            score += 5

        # Awards (5 points) - via ProductAward model
        if self.awards_rel.exists():
            score += 5

        # ============================================================
        # VERIFICATION BONUS (10 points max)
        # ============================================================
        if self.source_count >= 2:
            score += 5
        if self.source_count >= 3:
            score += 5

        return min(score, 100)

    def has_palate_profile(self) -> bool:
        """Check if product has mandatory palate tasting data (for scoring - needs 2+ flavors)."""
        return bool(
            (self.palate_flavors and len(self.palate_flavors) >= 2)
            or self.palate_description
            or self.initial_taste
        )

    def has_palate_data(self) -> bool:
        """
        Check if product has ANY palate tasting data (for status determination).

        Different from has_palate_profile() which requires 2+ flavors for scoring.
        For STATUS, any palate data counts.
        """
        return bool(
            (self.palate_flavors and len(self.palate_flavors) > 0)
            or self.palate_description
            or self.initial_taste
        )

    def has_nose_profile(self) -> bool:
        """Check if product has nose/aroma profile."""
        return bool(
            self.nose_description
            or (self.primary_aromas and len(self.primary_aromas) >= 2)
        )

    def has_finish_profile(self) -> bool:
        """Check if product has finish profile."""
        return bool(
            self.finish_description
            or (self.finish_flavors and len(self.finish_flavors) >= 2)
        )

    def has_complete_tasting(self) -> bool:
        """Check if product has all three tasting components."""
        return (
            self.has_palate_profile()
            and self.has_nose_profile()
            and self.has_finish_profile()
        )

    def _build_assessment_data(self) -> dict:
        """
        Build a dict with all fields needed for V3 quality gate assessment.

        Returns:
            Dict containing product data for quality assessment
        """
        # Extract brand name from FK relationship
        brand_name = None
        if self.brand:
            brand_name = self.brand.name

        # Build assessment data with all V3 required fields
        data = {
            "name": self.name,
            "brand": brand_name,
            "abv": float(self.abv) if self.abv is not None else None,
            "region": self.region,
            "country": self.country,
            "category": self.category,
            "volume_ml": self.volume_ml,
            "description": self.description,
            "age_statement": self.age_statement,
            # Tasting profile fields
            "primary_aromas": self.primary_aromas if self.primary_aromas else [],
            "finish_flavors": self.finish_flavors if self.finish_flavors else [],
            "palate_flavors": self.palate_flavors if self.palate_flavors else [],
            "mouthfeel": self.mouthfeel,
            "complexity": self.complexity,
            "overall_complexity": self.overall_complexity,
            # Cask/maturation fields
            "primary_cask": self.primary_cask if self.primary_cask else [],
            "finishing_cask": self.finishing_cask if self.finishing_cask else [],
            "maturation_notes": self.maturation_notes,
        }

        # Add style field from type_specific_data if it exists (for port wine)
        if self.type_specific_data and isinstance(self.type_specific_data, dict):
            if "style" in self.type_specific_data:
                data["style"] = self.type_specific_data["style"]

        # Filter out None values and empty lists/dicts for cleaner assessment
        # But keep falsy values like 0 or False
        cleaned_data = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned_data[key] = value

        return cleaned_data

    def determine_status(self) -> str:
        """
        Determine product status using V3 Quality Gate.

        V3 Status Hierarchy (lowest to highest):
            REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE

        Returns:
            Status string from DiscoveredProductStatus
        """
        # Preserve REJECTED and MERGED status - these are manually set
        if self.status in (
            DiscoveredProductStatus.REJECTED,
            DiscoveredProductStatus.MERGED,
        ):
            return self.status

        # Get V3 Quality Gate (lazy loaded to avoid circular imports)
        quality_gate = _get_quality_gate_v3()
        ProductStatus = _get_product_status()

        # Build assessment data from model fields
        assessment_data = self._build_assessment_data()

        # Get current ECP if available (may be updated separately)
        current_ecp = float(self.ecp_total) if self.ecp_total else None

        # Assess using V3 Quality Gate
        assessment = quality_gate.assess(
            extracted_data=assessment_data,
            product_type=self.product_type or "whiskey",
            product_category=self.category,
            ecp_total=current_ecp
        )

        # Update ecp_total if assessment calculated it
        if assessment.ecp_total and assessment.ecp_total > 0:
            self.ecp_total = assessment.ecp_total

        # Map ProductStatus enum to DiscoveredProductStatus string
        status_mapping = {
            ProductStatus.REJECTED: DiscoveredProductStatus.REJECTED,
            ProductStatus.SKELETON: DiscoveredProductStatus.SKELETON,
            ProductStatus.PARTIAL: DiscoveredProductStatus.PARTIAL,
            ProductStatus.BASELINE: DiscoveredProductStatus.BASELINE,
            ProductStatus.ENRICHED: DiscoveredProductStatus.ENRICHED,
            ProductStatus.COMPLETE: DiscoveredProductStatus.COMPLETE,
        }

        return status_mapping.get(assessment.status, DiscoveredProductStatus.SKELETON)

    def update_completeness(self, save: bool = True) -> None:
        """
        Recalculate completeness score and update status using V3 Quality Gate.

        The completeness_score is kept for backwards compatibility.
        Status determination now uses the V3 Quality Gate via determine_status().

        Args:
            save: If True, saves the model after updating
        """
        # Calculate legacy completeness score for backwards compatibility
        self.completeness_score = self.calculate_completeness_score()

        # Use V3 Quality Gate for status determination
        self.status = self.determine_status()

        if save:
            # Include ecp_total since determine_status() may update it
            self.save(update_fields=["completeness_score", "status", "ecp_total"])

    def get_missing_for_complete(self) -> list:
        """Get list of fields needed to reach COMPLETE status."""
        missing = []

        if not self.has_palate_profile():
            missing.append("palate_profile")

        if not self.name:
            missing.append("name")

        if not self.abv:
            missing.append("abv")

        return missing

    def get_missing_for_verified(self) -> list:
        """Get list of fields needed to reach VERIFIED status."""
        missing = self.get_missing_for_complete()

        if not self.has_nose_profile():
            missing.append("nose_profile")

        if not self.has_finish_profile():
            missing.append("finish_profile")

        if self.source_count < 2:
            missing.append("multi_source_verification")

        return missing

    def get_missing_critical_fields(self) -> list:
        """
        Get list of missing critical tasting fields.

        Spec: Especially palate, nose, finish.
        Returns list of missing field categories.
        """
        missing = []

        # Palate missing when no palate_flavors AND no palate_description AND no initial_taste
        if not (self.palate_flavors or self.palate_description or self.initial_taste):
            missing.append("palate")

        # Nose missing when no nose_description AND no primary_aromas
        if not (self.nose_description or self.primary_aromas):
            missing.append("nose")

        # Finish missing when no finish_description AND no finish_flavors
        if not (self.finish_description or self.finish_flavors):
            missing.append("finish")

        return missing

    def mark_field_verified(self, field_name: str) -> None:
        """
        Mark a field as verified (confirmed by 2+ sources).

        Args:
            field_name: Name of the field to mark as verified
        """
        if self.verified_fields is None:
            self.verified_fields = []

        if field_name not in self.verified_fields:
            self.verified_fields = list(self.verified_fields) + [field_name]

    def values_match(self, val1, val2) -> bool:
        """
        Compare two values for verification matching.

        Handles different types:
        - Decimals: Compare numerically
        - Strings: Case-insensitive comparison
        - Lists: Order-independent comparison

        Returns True if values are considered matching.
        """
        from decimal import Decimal

        if val1 is None or val2 is None:
            return val1 == val2

        # Decimal comparison
        if isinstance(val1, Decimal) or isinstance(val2, Decimal):
            try:
                return Decimal(str(val1)) == Decimal(str(val2))
            except (ValueError, TypeError):
                return False

        # String comparison (case-insensitive)
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.lower().strip() == val2.lower().strip()

        # List comparison (order-independent)
        if isinstance(val1, list) and isinstance(val2, list):
            return sorted(val1) == sorted(val2)

        # Default: direct comparison
        return val1 == val2


class CrawledArticle(models.Model):
    """
    Task 2.4: Editorial content discovered by the crawler.

    Skeleton model for content preservation - full functionality deferred to Phase 4.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source Information
    source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        related_name="crawled_articles",
    )
    original_url = models.URLField(max_length=2000, unique=True, db_index=True)

    # Content Metadata
    title = models.CharField(max_length=500, blank=True)
    author = models.CharField(max_length=200, blank=True)
    published_date = models.DateField(null=True, blank=True)

    # Extracted Content (populated by future AI processing)
    summary_bullets = models.JSONField(
        default=list,
        blank=True,
        help_text="Summary bullet points extracted from article",
    )
    extracted_tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags/categories extracted from article",
    )
    sentiment_score = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sentiment analysis results: {'overall': 0.8, 'products': {...}}",
    )

    # Content Preservation (functionality deferred)
    local_snapshot_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to local HTML snapshot",
    )
    wayback_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Wayback Machine archive URL",
    )
    is_original_live = models.BooleanField(
        default=True,
        help_text="Whether the original URL is still accessible",
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the original URL was checked for availability",
    )

    # Metadata
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crawled_articles"
        ordering = ["-discovered_at"]
        indexes = [
            models.Index(fields=["source", "discovered_at"]),
            models.Index(fields=["is_original_live"]),
            models.Index(fields=["published_date"]),
        ]

    def __str__(self):
        return self.title[:100] if self.title else self.original_url[:100]


class ArticleProductMention(models.Model):
    """
    Task 2.5: Links articles to products they mention.

    Skeleton model - full functionality deferred to Phase 4.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    article = models.ForeignKey(
        CrawledArticle,
        on_delete=models.CASCADE,
        related_name="product_mentions",
    )
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="article_mentions_rel",  # Changed to avoid conflict with press_mentions field
    )

    # Mention Details
    mention_type = models.CharField(
        max_length=20,
        choices=MentionType.choices,
        default=MentionType.MENTION,
        help_text="Type of product mention",
    )
    rating_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rating given in article (e.g., 92.5)",
    )
    rating_scale = models.CharField(
        max_length=20,
        blank=True,
        help_text="Rating scale used (e.g., '100', 'A-F', '5 stars')",
    )
    excerpt = models.TextField(
        blank=True,
        help_text="Relevant excerpt mentioning the product",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_product_mentions"
        unique_together = ["article", "product"]
        indexes = [
            models.Index(fields=["article"]),
            models.Index(fields=["product"]),
            models.Index(fields=["mention_type"]),
        ]

    def __str__(self):
        return f"{self.article} -> {self.product} ({self.mention_type})"


class CrawlCost(models.Model):
    """
    Task 2.6: Tracks API usage costs for budget monitoring.

    Records costs for SerpAPI, ScrapingBee, and OpenAI API calls.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Service Information
    service = models.CharField(
        max_length=20,
        choices=CostService.choices,
        help_text="External service used",
    )
    cost_cents = models.IntegerField(
        help_text="Cost in cents (USD)",
    )

    # Job Association
    crawl_job = models.ForeignKey(
        "Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="costs",
    )

    # Usage Details
    request_count = models.IntegerField(
        default=1,
        help_text="Number of API requests",
    )

    # Timing
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "crawl_costs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["service", "timestamp"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["crawl_job"]),
        ]

    def __str__(self):
        return f"{self.service}: ${self.cost_cents / 100:.2f} at {self.timestamp}"


class CrawlError(models.Model):
    """
    Task 2.7: Persistent error logging for crawl failures.

    Provides detailed context for debugging and monitoring.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source Information
    source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        related_name="errors",
    )
    url = models.URLField(max_length=2000, help_text="URL that caused the error")

    # Error Details
    error_type = models.CharField(
        max_length=20,
        choices=ErrorType.choices,
        help_text="Category of error",
    )
    message = models.TextField(help_text="Error message")
    stack_trace = models.TextField(blank=True, help_text="Full stack trace if available")

    # Request Context
    tier_used = models.IntegerField(
        null=True,
        blank=True,
        help_text="Fetching tier used (1, 2, or 3)",
    )
    response_status = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP response status code",
    )
    response_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="HTTP response headers",
    )

    # Timing and Resolution
    timestamp = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this error has been resolved",
    )

    class Meta:
        db_table = "crawl_errors"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["source", "timestamp"]),
            models.Index(fields=["error_type", "timestamp"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["resolved"]),
        ]

    def __str__(self):
        return f"{self.error_type}: {self.message[:50]}... ({self.timestamp})"


# ============================================================
# Task Group 21: ProductAvailability Model
# ============================================================


class ProductAvailability(models.Model):
    """
    Task Group 21: Tracks product availability across retailers.

    Enables real-time stock monitoring, price change detection, and
    aggregated availability metrics on DiscoveredProduct.

    This model stores the current availability status at each retailer,
    supporting multi-currency prices and price change tracking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="availability",
        help_text="The product this availability record is for",
    )

    # Retailer information
    retailer = models.CharField(
        max_length=200,
        help_text="Name of the retailer",
    )
    retailer_url = models.URLField(
        help_text="URL to the product page on the retailer's site",
    )
    retailer_country = models.CharField(
        max_length=100,
        help_text="Country where the retailer is based",
    )

    # Stock status
    in_stock = models.BooleanField(
        help_text="Whether the product is currently in stock",
    )
    stock_level = models.CharField(
        max_length=20,
        choices=StockLevelChoices.choices,
        help_text="Stock level: in_stock, low_stock, out_of_stock, pre_order, discontinued",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Current price in the retailer's currency",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)",
    )
    price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to USD for comparison",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to EUR for comparison",
    )

    # Tracking
    last_checked = models.DateTimeField(
        help_text="When this availability was last checked",
    )

    # Price change detection
    price_changed = models.BooleanField(
        default=False,
        help_text="Whether the price changed since last check",
    )
    previous_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Previous price before the last change",
    )

    class Meta:
        db_table = "product_availability"
        ordering = ["-last_checked"]
        indexes = [
            # Index for lookups by product and retailer
            models.Index(fields=["product", "retailer"]),
            # Index for finding stale records that need re-checking
            models.Index(fields=["last_checked"]),
            # Index for filtering by stock level
            models.Index(fields=["stock_level"]),
        ]
        verbose_name = "Product Availability"
        verbose_name_plural = "Product Availabilities"

    def __str__(self):
        return f"{self.retailer} - {self.product} ({self.stock_level})"


# ============================================================
# Task Group 22: CategoryInsight Model
# ============================================================


class CategoryInsight(models.Model):
    """
    Task Group 22: Aggregates market data by category.

    Provides category-level market insights including total products,
    award statistics, pricing metrics, and trending direction.
    Enables market trend analysis and category health monitoring.

    Unique constraint on (product_type, sub_category, region, country)
    allows tracking insights at different geographic granularities.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Category identification
    product_type = models.CharField(
        max_length=50,
        help_text="Product type: whiskey, port_wine, etc.",
    )
    sub_category = models.CharField(
        max_length=100,
        help_text="Sub-category: bourbon, scotch_single_malt, tawny, etc.",
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Geographic region (e.g., Islay, Kentucky)",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country (e.g., Scotland, USA, Japan)",
    )

    # Product counts
    total_products = models.IntegerField(
        help_text="Total number of products in this category",
    )
    products_with_awards = models.IntegerField(
        help_text="Number of products with at least one award",
    )

    # Pricing metrics
    avg_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Average price in USD across category",
    )
    median_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Median price in USD across category",
    )
    avg_price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Average price in EUR across category",
    )

    # Rating metrics
    avg_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average rating across rated products in category",
    )

    # Market trend indicators
    trending_direction = models.CharField(
        max_length=10,
        choices=CategoryTrendingDirectionChoices.choices,
        help_text="Market trend: hot, rising, stable, declining, cold",
    )
    market_growth = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Year-over-year growth indicator (e.g., '+15% YoY')",
    )
    avg_price_change_30d = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average price change in the last 30 days",
    )

    # Timestamp
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this insight was last updated",
    )

    class Meta:
        db_table = "category_insight"
        ordering = ["-updated_at"]
        indexes = [
            # Index for category lookups
            models.Index(fields=["product_type", "sub_category"]),
            # Index for trending analysis
            models.Index(fields=["trending_direction"]),
        ]
        constraints = [
            # Unique constraint on the combination of product_type, sub_category, region, country
            # Note: nulls_distinct=False requires Django 4.1+, removed for compatibility
            models.UniqueConstraint(
                fields=["product_type", "sub_category", "region", "country"],
                name="unique_category_insight",
            ),
        ]
        verbose_name = "Category Insight"
        verbose_name_plural = "Category Insights"

    def __str__(self):
        parts = [self.product_type, self.sub_category]
        if self.region:
            parts.append(self.region)
        if self.country:
            parts.append(self.country)
        return " - ".join(parts)


# ============================================================
# Task Group 23: PurchaseRecommendation Model
# ============================================================


class PurchaseRecommendation(models.Model):
    """
    Task Group 23: Captures AI-generated purchasing recommendations.

    This model stores AI-generated recommendations for inventory purchases,
    including scoring factors, business factors, and suggestions.
    Enables tracking of recommendation outcomes for ML improvement.

    Key features:
    - Recommendation tiers (must_stock, recommended, consider, watch, skip)
    - Multi-factor scoring (demand, quality, value, uniqueness, trend)
    - Business factors (category gap fill, complements existing)
    - Actionable suggestions (quantity, price, margin, reorder threshold)
    - Outcome tracking for ML feedback loop
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="recommendations",
        help_text="The product this recommendation is for",
    )

    # Core recommendation
    recommendation_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Overall recommendation score (1-100)",
    )
    recommendation_tier = models.CharField(
        max_length=20,
        choices=RecommendationTierChoices.choices,
        help_text="Recommendation tier: must_stock, recommended, consider, watch, skip",
    )
    recommendation_reason = models.TextField(
        help_text="AI-generated explanation for the recommendation",
    )

    # Scoring factors (each 1-10)
    demand_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Demand/popularity score (1-10)",
    )
    quality_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Quality/ratings score (1-10)",
    )
    value_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Value for money score (1-10)",
    )
    uniqueness_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Product uniqueness score (1-10)",
    )
    trend_score_factor = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Trend/momentum score (1-10)",
    )

    # Business factors
    category_gap_fill = models.BooleanField(
        default=False,
        help_text="Whether this product fills a gap in inventory category",
    )
    complements_existing = models.BooleanField(
        default=False,
        help_text="Whether this product complements existing inventory",
    )

    # Business metrics
    margin_potential = models.CharField(
        max_length=10,
        choices=MarginPotentialChoices.choices,
        blank=True,
        null=True,
        help_text="Margin potential: low, medium, high, premium",
    )
    turnover_estimate = models.CharField(
        max_length=15,
        choices=TurnoverEstimateChoices.choices,
        blank=True,
        null=True,
        help_text="Turnover estimate: slow, moderate, fast, very_fast",
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevelChoices.choices,
        blank=True,
        null=True,
        help_text="Risk level: low, medium, high",
    )

    # Actionable suggestions
    suggested_quantity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Suggested quantity to purchase",
    )
    suggested_retail_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Suggested retail price",
    )
    estimated_margin_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated margin percentage",
    )
    reorder_threshold = models.IntegerField(
        blank=True,
        null=True,
        help_text="Suggested reorder threshold quantity",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the recommendation was created",
    )
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the recommendation expires (null = never)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the recommendation is currently active",
    )

    # Outcome tracking
    acted_upon = models.BooleanField(
        default=False,
        help_text="Whether the recommendation was acted upon",
    )
    outcome = models.CharField(
        max_length=10,
        choices=OutcomeChoices.choices,
        blank=True,
        null=True,
        help_text="Outcome after acting: success, moderate, poor",
    )

    class Meta:
        db_table = "purchase_recommendation"
        ordering = ["-recommendation_score", "-created_at"]
        indexes = [
            # Index for ranking recommendations by score
            models.Index(fields=["recommendation_score"]),
            # Index for filtering by tier
            models.Index(fields=["recommendation_tier"]),
            # Index for cleanup of expired recommendations
            models.Index(fields=["expires_at"]),
            # Index for active queries
            models.Index(fields=["is_active"]),
        ]
        verbose_name = "Purchase Recommendation"
        verbose_name_plural = "Purchase Recommendations"

    def __str__(self):
        return f"{self.product} - {self.recommendation_tier} (Score: {self.recommendation_score})"


# ============================================================
# Task Group 24: ShopInventory Model
# ============================================================


class ShopInventory(models.Model):
    """
    Task Group 24: Tracks shop's owned inventory.

    This model represents the actual inventory a shop owns. It can be
    linked to DiscoveredProduct for comparison analysis, enabling:
    - Gap analysis between owned inventory and market offerings
    - Stock management with reorder points
    - Category-level inventory insights

    Key features:
    - Optional link to DiscoveredProduct (matched_product)
    - Reuses PriceTierChoices from Task Group 20
    - Stock management fields (current_stock, reorder_point, monthly_sales_avg)
    - Active/inactive status for discontinued items
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product identification
    product_name = models.CharField(
        max_length=255,
        help_text="Name of the product in shop inventory",
    )

    # Link to DiscoveredProduct (optional)
    matched_product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shop_inventory",
        help_text="Matched DiscoveredProduct for comparison (optional)",
    )

    # Product categorization
    product_type = models.CharField(
        max_length=50,
        help_text="Product type: whiskey, port_wine, etc.",
    )
    sub_category = models.CharField(
        max_length=100,
        help_text="Sub-category: bourbon, scotch_single_malt, tawny, etc.",
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Geographic region (e.g., Islay, Kentucky)",
    )

    # Market positioning (reuses PriceTierChoices from Task Group 20)
    price_tier = models.CharField(
        max_length=20,
        choices=PriceTierChoices.choices,
        help_text="Price tier: budget, value, mid_range, premium, ultra_premium, luxury",
    )

    # Stock management
    current_stock = models.IntegerField(
        help_text="Current quantity in stock",
    )
    reorder_point = models.IntegerField(
        help_text="Stock level at which to reorder",
    )
    monthly_sales_avg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average monthly sales quantity",
    )

    # Tracking
    last_restocked = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the item was last restocked",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this inventory item is active (not discontinued)",
    )

    class Meta:
        db_table = "shop_inventory"
        ordering = ["product_name"]
        indexes = [
            # Index for FK lookups
            models.Index(fields=["matched_product"]),
            # Index for gap analysis queries
            models.Index(fields=["product_type", "sub_category"]),
            # Index for active items filtering
            models.Index(fields=["is_active"]),
        ]
        verbose_name = "Shop Inventory"
        verbose_name_plural = "Shop Inventory Items"

    def __str__(self):
        return f"{self.product_name} (Stock: {self.current_stock})"

    @property
    def needs_reorder(self) -> bool:
        """Check if stock is at or below reorder point."""
        return self.current_stock <= self.reorder_point


# ============================================================
# Task Group 26: CrawlerMetrics Model
# ============================================================


class CrawlerMetrics(models.Model):
    """
    Task Group 26: Daily aggregate metrics for crawler operations.

    Tracks daily aggregate metrics for monitoring crawler health,
    extraction success rates, API usage, and performance metrics.
    Enables trend analysis and quota management.

    Key features:
    - One record per day (unique date constraint)
    - Crawl metrics (pages crawled, succeeded, failed, success rate)
    - Extraction metrics (products extracted, created, merged, flagged)
    - Quality metrics (completeness, confidence, conflicts, duplicates)
    - API usage tracking (SerpAPI, ScrapingBee, AI Enhancement, Wayback)
    - Performance metrics (crawl time, extraction time, queue depth)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Date (unique - one record per day)
    date = models.DateField(
        unique=True,
        help_text="Date for this metrics record (one per day)",
    )

    # Crawl Metrics
    pages_crawled = models.IntegerField(
        default=0,
        help_text="Total pages crawled on this date",
    )
    pages_succeeded = models.IntegerField(
        default=0,
        help_text="Pages successfully crawled",
    )
    pages_failed = models.IntegerField(
        default=0,
        help_text="Pages that failed to crawl",
    )
    crawl_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Crawl success rate percentage (succeeded/crawled * 100)",
    )

    # Extraction Metrics
    products_extracted = models.IntegerField(
        default=0,
        help_text="Total products extracted from crawled pages",
    )
    products_created = models.IntegerField(
        default=0,
        help_text="New products created in database",
    )
    products_merged = models.IntegerField(
        default=0,
        help_text="Products merged with existing records",
    )
    products_flagged_review = models.IntegerField(
        default=0,
        help_text="Products flagged for manual review",
    )
    extraction_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Extraction success rate percentage",
    )

    # Quality Metrics
    avg_completeness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average completeness score for extracted products (1-100)",
    )
    avg_confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average extraction confidence score (0.00-1.00)",
    )
    conflicts_detected = models.IntegerField(
        default=0,
        help_text="Number of data conflicts detected",
    )
    duplicates_merged = models.IntegerField(
        default=0,
        help_text="Number of duplicate records merged",
    )

    # API Usage
    serpapi_queries = models.IntegerField(
        default=0,
        help_text="Number of SerpAPI queries made",
    )
    scrapingbee_requests = models.IntegerField(
        default=0,
        help_text="Number of ScrapingBee requests made",
    )
    ai_enhancement_calls = models.IntegerField(
        default=0,
        help_text="Number of AI enhancement API calls",
    )
    wayback_saves = models.IntegerField(
        default=0,
        help_text="Number of pages archived to Wayback Machine",
    )

    # Performance Metrics
    avg_crawl_time_ms = models.IntegerField(
        blank=True,
        null=True,
        help_text="Average crawl time per page in milliseconds",
    )
    avg_extraction_time_ms = models.IntegerField(
        blank=True,
        null=True,
        help_text="Average extraction time per page in milliseconds",
    )
    queue_depth = models.IntegerField(
        default=0,
        help_text="Queue depth at end of day",
    )

    class Meta:
        db_table = "crawler_metrics"
        ordering = ["-date"]
        indexes = [
            # Index for unique date and trend queries
            models.Index(fields=["date"]),
        ]
        verbose_name = "Crawler Metrics"
        verbose_name_plural = "Crawler Metrics"

    def __str__(self):
        return f"Metrics for {self.date} - {self.pages_crawled} pages crawled"


# ============================================================
# Task Group 5: DiscoverySourceConfig Model
# ============================================================


class DiscoverySourceConfig(models.Model):
    """
    Task Group 5: Configuration model for discovery sources.

    Stores configuration for crawl sources used in the product discovery
    pipeline. Enables admin-managed source configuration with crawl
    strategy auto-detection and reliability scoring.

    Key features:
    - Source type classification (award_competition, review_blog, retailer, etc.)
    - Crawl configuration (priority, frequency, rate limiting)
    - Crawl strategy auto-detection (simple, js_render, stealth, manual)
    - Reliability scoring for conflict resolution
    - Authentication and custom header support
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identification
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique name for this discovery source",
    )
    base_url = models.URLField(
        help_text="Base URL of the discovery source",
    )

    # Classification
    source_type = models.CharField(
        max_length=30,
        choices=SourceTypeChoices.choices,
        help_text="Type of source: award_competition, review_blog, retailer, etc.",
    )

    # Crawl Configuration
    crawl_priority = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Crawl priority (1-10, higher = more important)",
    )
    crawl_frequency = models.CharField(
        max_length=20,
        choices=CrawlFrequencyChoices.choices,
        help_text="How often to crawl: daily, weekly, monthly, on_demand",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this source is active for crawling",
    )
    reliability_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Reliability score for conflict resolution (1-10, higher = more reliable)",
    )

    # Access Configuration
    requires_authentication = models.BooleanField(
        default=False,
        help_text="Whether authentication is required to access this source",
    )
    rate_limit_delay = models.IntegerField(
        default=1,
        help_text="Delay between requests in seconds",
    )

    # Crawl Strategy
    crawl_strategy = models.CharField(
        max_length=20,
        choices=CrawlStrategyChoices.choices,
        default=CrawlStrategyChoices.SIMPLE,
        help_text="Crawl strategy: simple, js_render, stealth, manual",
    )
    detected_obstacles = models.JSONField(
        blank=True,
        null=True,
        help_text="Detected obstacles during crawling (age gates, CAPTCHAs, etc.)",
    )
    strategy_confirmed = models.BooleanField(
        default=False,
        help_text="Whether the crawl strategy has been confirmed as working",
    )
    custom_headers = models.JSONField(
        blank=True,
        null=True,
        help_text="Custom HTTP headers for requests",
    )

    # Metadata
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes about this source",
    )
    last_crawled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this source was last crawled",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this source was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this source was last updated",
    )

    class Meta:
        db_table = "discovery_source_config"
        ordering = ["-crawl_priority", "name"]
        indexes = [
            # Index for unique name lookup
            models.Index(fields=["name"]),
            # Index for base_url lookup
            models.Index(fields=["base_url"]),
            # Index for scheduler queries (active + priority)
            models.Index(fields=["is_active", "crawl_priority"]),
            # Index for source_type filtering
            models.Index(fields=["source_type"]),
        ]
        verbose_name = "Discovery Source Config"
        verbose_name_plural = "Discovery Source Configs"

    def __str__(self):
        return f"{self.name} ({self.source_type})"


# ============================================================
# Task Group 6: CrawledSource Model REMOVED - replaced by CrawledPage
# ============================================================


# ============================================================
# Task Group 27: SourceMetrics Model
# ============================================================


class SourceMetrics(models.Model):
    """
    Task Group 27: Per-source daily metrics for crawler operations.

    Tracks daily metrics per discovery source for monitoring source health,
    crawl success rates, product discovery rates, and error patterns.
    Enables per-source analysis and health monitoring.

    Key features:
    - One record per (date, discovery_source) pair (unique constraint)
    - Crawl metrics (pages crawled, succeeded)
    - Product discovery metrics (products found, avg per page)
    - Confidence tracking (average confidence score)
    - Error tracking (JSONField for error types and counts)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Date
    date = models.DateField(
        help_text="Date for this metrics record",
    )

    # Discovery Source (FK)
    discovery_source = models.ForeignKey(
        DiscoverySourceConfig,
        on_delete=models.CASCADE,
        related_name="metrics",
        help_text="Discovery source this metrics record is for",
    )

    # Crawl Metrics
    pages_crawled = models.IntegerField(
        default=0,
        help_text="Total pages crawled from this source on this date",
    )
    pages_succeeded = models.IntegerField(
        default=0,
        help_text="Pages successfully crawled from this source",
    )

    # Product Discovery Metrics
    products_found = models.IntegerField(
        default=0,
        help_text="Products found from this source on this date",
    )
    avg_products_per_page = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average products found per page",
    )

    # Confidence Metrics
    avg_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average extraction confidence score (0.00-1.00)",
    )

    # Error Tracking
    errors = models.JSONField(
        default=list,
        help_text="Error types and counts: [{'type': 'connection_timeout', 'count': 5}, ...]",
    )

    class Meta:
        db_table = "source_metrics"
        ordering = ["-date"]
        indexes = [
            # Index for date queries
            models.Index(fields=["date"]),
        ]
        constraints = [
            # Unique constraint on (date, discovery_source)
            models.UniqueConstraint(
                fields=["date", "discovery_source"],
                name="unique_source_metrics_date_source",
            ),
        ]
        verbose_name = "Source Metrics"
        verbose_name_plural = "Source Metrics"

    def __str__(self):
        return f"Metrics for {self.discovery_source.name} on {self.date}"


# ============================================================
# Task Group 28: AlertRule Model
# ============================================================


class AlertRule(models.Model):
    """
    Task Group 28: Configurable alert rules for crawler metrics monitoring.

    Enables configurable alerting based on crawler metrics with condition
    choices, severity levels, and cooldown behavior to prevent alert spam.

    Key features:
    - Condition-based triggers (below, above, equals, changed_by)
    - Severity levels (info, warning, critical)
    - Notification channels (email, slack, sentry)
    - Cooldown period to prevent alert fatigue
    - Window hours for time-based metric evaluation
    - Active/inactive toggle for rule management
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Rule identification
    name = models.CharField(
        max_length=200,
        help_text="Descriptive name for this alert rule",
    )

    # Metric to monitor
    metric = models.CharField(
        max_length=100,
        help_text="Name of the metric to monitor (e.g., 'crawl_success_rate', 'queue_depth')",
    )

    # Condition and threshold
    condition = models.CharField(
        max_length=20,
        choices=AlertConditionChoices.choices,
        help_text="Condition: below, above, equals, changed_by",
    )
    threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Threshold value for the condition",
    )

    # Time window for evaluation
    window_hours = models.IntegerField(
        default=24,
        help_text="Time window in hours for metric evaluation",
    )

    # Severity and notification
    severity = models.CharField(
        max_length=10,
        choices=AlertSeverityChoices.choices,
        help_text="Severity level: info, warning, critical",
    )
    notification_channel = models.CharField(
        max_length=10,
        choices=NotificationChannelChoices.choices,
        default=NotificationChannelChoices.SENTRY,
        help_text="Notification channel: email, slack, sentry",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this alert rule is active",
    )

    # Cooldown to prevent alert spam
    cooldown_hours = models.IntegerField(
        default=4,
        help_text="Minimum hours between repeated alerts for this rule",
    )
    last_triggered = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this alert was last triggered",
    )

    class Meta:
        db_table = "alert_rule"
        ordering = ["name"]
        indexes = [
            # Index for active rule queries
            models.Index(fields=["is_active"]),
            # Index for metric lookup
            models.Index(fields=["metric"]),
        ]
        verbose_name = "Alert Rule"
        verbose_name_plural = "Alert Rules"

    def __str__(self):
        return f"{self.name} ({self.severity})"


# ============================================================
# Task Group 1: DiscoveredBrand Model
# ============================================================


class DiscoveredBrand(models.Model):
    """
    Task Group 1: Brand information discovered during crawling.

    Stores information about brands/distilleries/producers discovered
    during the crawling process.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    name = models.CharField(
        max_length=200,
        help_text="Brand name",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        help_text="URL-safe identifier",
    )

    # Location
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country of origin",
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Region within country",
    )
    headquarters_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country where headquarters is located",
    )

    # Details
    official_website = models.URLField(
        blank=True,
        null=True,
        help_text="Official brand website",
    )
    founded_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year the brand was founded",
    )

    # Statistics
    product_count = models.IntegerField(
        default=0,
        help_text="Number of products from this brand",
    )
    award_count = models.IntegerField(
        default=0,
        help_text="Total awards won by the brand",
    )
    mention_count = models.IntegerField(
        default=0,
        help_text="Number of source mentions",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovered_brand"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["country"]),
        ]
        verbose_name = "Discovered Brand"
        verbose_name_plural = "Discovered Brands"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            self.slug = base_slug
            # Ensure uniqueness
            counter = 1
            while DiscoveredBrand.objects.filter(slug=self.slug).exclude(id=self.id).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


# ============================================================
# Dynamic Product Schema: ProductTypeSchema Model
# Spec Reference: DYNAMIC_PRODUCT_SCHEMA_SPEC.md Section 2
# ============================================================


class ProductTypeSchema(models.Model):
    """
    Single source of truth for product type schema definitions.

    This model stores the complete schema for each product type, including:
    - Base fields common to all products
    - Type-specific fields with validation rules
    - Derive-from rules for automatic field derivation
    - Extraction hints for AI service

    Spec Reference: DYNAMIC_PRODUCT_SCHEMA_SPEC.md Section 2
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product_type = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Product type identifier (e.g., 'whiskey', 'port_wine')",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable name for display",
    )
    schema = models.JSONField(
        default=dict,
        help_text="Complete schema definition including base_fields, type_specific_fields, extraction_hints",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schema is active for extraction",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_type_schema"
        verbose_name = "Product Type Schema"
        verbose_name_plural = "Product Type Schemas"
        ordering = ["product_type"]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.display_name} ({self.product_type}) [{status}]"


# ============================================================
# Task Group 3: Spirit-Type Extension Models
# REMOVED: WhiskeyDetails and PortWineDetails migrated to type_specific_data
# See DATABASE_CLEANUP_SPEC.md Phase 1
# ============================================================


# ============================================================
# Task Group 4: Related Data Tables (Awards, Prices, Ratings, Images)
# ============================================================


class ProductAward(models.Model):
    """
    Task Group 4: Awards won by products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='awards_rel',
        help_text="The product that won this award",
    )

    # Award Details
    competition = models.CharField(
        max_length=200,
        help_text="Competition/award name",
    )
    competition_country = models.CharField(
        max_length=100,
        help_text="Country where competition is held",
    )
    year = models.IntegerField(
        help_text="Year the award was given",
    )
    medal = models.CharField(
        max_length=20,
        choices=MedalChoices.choices,
        help_text="Medal/award level",
    )
    award_category = models.CharField(
        max_length=200,
        help_text="Category within the competition",
    )

    # Optional Details
    score = models.IntegerField(
        blank=True,
        null=True,
        help_text="Score given (if applicable)",
    )
    award_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to award page",
    )
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to medal/certificate image",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_award"
        ordering = ["-year", "competition"]
        indexes = [
            models.Index(fields=["product", "year"]),
            models.Index(fields=["competition"]),
        ]
        verbose_name = "Product Award"
        verbose_name_plural = "Product Awards"

    def __str__(self):
        return f"{self.product} - {self.competition} {self.year} ({self.medal})"


class BrandAward(models.Model):
    """
    Task Group 4: Awards won by brands.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.CASCADE,
        related_name='awards',
        help_text="The brand that won this award",
    )

    # Award Details
    competition = models.CharField(
        max_length=200,
        help_text="Competition/award name",
    )
    competition_country = models.CharField(
        max_length=100,
        help_text="Country where competition is held",
    )
    year = models.IntegerField(
        help_text="Year the award was given",
    )
    medal = models.CharField(
        max_length=20,
        choices=MedalChoices.choices,
        help_text="Medal/award level",
    )
    award_category = models.CharField(
        max_length=200,
        help_text="Category within the competition",
    )

    # Optional Details
    score = models.IntegerField(
        blank=True,
        null=True,
        help_text="Score given (if applicable)",
    )
    award_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to award page",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "brand_award"
        ordering = ["-year", "competition"]
        indexes = [
            models.Index(fields=["brand", "year"]),
            models.Index(fields=["competition"]),
        ]
        verbose_name = "Brand Award"
        verbose_name_plural = "Brand Awards"

    def __str__(self):
        return f"{self.brand} - {self.competition} {self.year} ({self.medal})"


class ProductPrice(models.Model):
    """
    Task Group 4: Price observations for products across retailers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='prices',
        help_text="The product this price is for",
    )

    # Retailer Details
    retailer = models.CharField(
        max_length=200,
        help_text="Retailer name",
    )
    retailer_country = models.CharField(
        max_length=100,
        help_text="Retailer's country",
    )
    url = models.URLField(
        help_text="URL to product page at retailer",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in original currency",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO 4217 currency code",
    )
    price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to USD",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to EUR",
    )

    # Stock
    in_stock = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether product is in stock",
    )

    # Timing
    date_observed = models.DateField(
        help_text="Date the price was observed",
    )

    class Meta:
        db_table = "product_price"
        ordering = ["-date_observed"]
        indexes = [
            models.Index(fields=["product", "retailer"]),
            models.Index(fields=["date_observed"]),
        ]
        verbose_name = "Product Price"
        verbose_name_plural = "Product Prices"

    def __str__(self):
        return f"{self.product} - {self.retailer}: {self.currency} {self.price}"


class ProductRating(models.Model):
    """
    Task Group 4: Ratings from various sources for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='ratings_rel',
        help_text="The product this rating is for",
    )

    # Source
    source = models.CharField(
        max_length=200,
        help_text="Rating source/platform name",
    )
    source_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country of the rating source",
    )

    # Rating
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Rating score",
    )
    max_score = models.IntegerField(
        help_text="Maximum possible score (e.g., 100, 5)",
    )

    # Optional Details
    reviewer = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Reviewer name",
    )
    review_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to full review",
    )
    date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of the rating",
    )
    review_count = models.IntegerField(
        blank=True,
        null=True,
        help_text="Number of reviews (for aggregate scores)",
    )

    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_rating"
        ordering = ["-score"]
        indexes = [
            models.Index(fields=["product", "source"]),
        ]
        verbose_name = "Product Rating"
        verbose_name_plural = "Product Ratings"

    def __str__(self):
        return f"{self.product} - {self.source}: {self.score}/{self.max_score}"


class ProductImage(models.Model):
    """
    Task Group 4: Images for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='images_rel',
        help_text="The product this image belongs to",
    )

    # Image Details
    url = models.URLField(
        help_text="URL to the image",
    )
    image_type = models.CharField(
        max_length=20,
        choices=ImageTypeChoices.choices,
        help_text="Type of image",
    )
    source = models.CharField(
        max_length=200,
        help_text="Source of the image",
    )

    # Dimensions
    width = models.IntegerField(
        blank=True,
        null=True,
        help_text="Image width in pixels",
    )
    height = models.IntegerField(
        blank=True,
        null=True,
        help_text="Image height in pixels",
    )

    # Status
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary image",
    )

    class Meta:
        db_table = "product_image"
        ordering = ["-is_primary"]
        indexes = [
            models.Index(fields=["product"]),
        ]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product} - {self.image_type}"


# ============================================================
# Task Group 7: Junction Tables (ProductSource, BrandSource)
# ============================================================


class ProductSource(models.Model):
    """
    Task Group 7: Junction table linking products to crawled pages.

    Tracks which CrawledPage contributed to which DiscoveredProduct
    with extraction metadata.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='product_sources',
        help_text="The product",
    )
    source = models.ForeignKey(
        "CrawledPage",
        on_delete=models.CASCADE,
        related_name='products',
        help_text="The page that mentioned this product",
    )

    # Extraction Metadata
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for extraction (0.0-1.0)",
    )
    fields_extracted = models.JSONField(
        blank=True,
        default=list,
        help_text="List of field names extracted from this source",
    )

    # Mention Details
    mention_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Type of mention",
    )
    mention_count = models.IntegerField(
        default=1,
        help_text="Number of times mentioned in this source",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_source"
        unique_together = ["product", "source"]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Source"
        verbose_name_plural = "Product Sources"

    def __str__(self):
        return f"{self.product} <- {self.source}"


class BrandSource(models.Model):
    """
    Task Group 7: Junction table linking brands to crawled pages.

    Tracks which CrawledPage mentioned which DiscoveredBrand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.CASCADE,
        related_name='sources',
        help_text="The brand",
    )
    source = models.ForeignKey(
        "CrawledPage",
        on_delete=models.CASCADE,
        related_name='brands',
        help_text="The page that mentioned this brand",
    )

    # Extraction Metadata
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for extraction (0.0-1.0)",
    )

    # Mention Details
    mention_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Type of mention",
    )
    mention_count = models.IntegerField(
        default=1,
        help_text="Number of times mentioned in this source",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "brand_source"
        unique_together = ["brand", "source"]
        indexes = [
            models.Index(fields=["brand"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Brand Source"
        verbose_name_plural = "Brand Sources"

    def __str__(self):
        return f"{self.brand} <- {self.source}"


# ============================================================
# Task Group 8: Per-Field Provenance Tracking
# ============================================================


class ProductFieldSource(models.Model):
    """
    Task Group 8: Per-field provenance tracking for products.

    Tracks which page contributed each field value to a product,
    enabling detailed provenance tracking and conflict detection.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='field_sources',
        help_text="The product",
    )
    source = models.ForeignKey(
        "CrawledPage",
        on_delete=models.CASCADE,
        related_name='field_extractions',
        help_text="The page that provided this field value",
    )

    # Field Information
    field_name = models.CharField(
        max_length=100,
        help_text="Name of the field",
    )
    extracted_value = models.TextField(
        help_text="The extracted value (stored as string)",
    )

    # Confidence
    confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for this extraction (0.0-1.0)",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_field_source"
        unique_together = ["product", "field_name", "source"]
        indexes = [
            models.Index(fields=["product", "field_name"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Field Source"
        verbose_name_plural = "Product Field Sources"

    def __str__(self):
        return f"{self.product}.{self.field_name} <- {self.source}"


# ============================================================
# Task Group 12: ProductCandidate Staging Model
# ============================================================


class ProductCandidate(models.Model):
    """
    Task Group 12: Staging model for product candidates during deduplication.

    Stores extracted product mentions before they are matched to existing
    products or created as new products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Names
    raw_name = models.CharField(
        max_length=500,
        help_text="Original extracted product name",
    )
    normalized_name = models.CharField(
        max_length=500,
        help_text="Normalized product name for matching",
    )

    # Source
    source = models.ForeignKey(
        "CrawledPage",
        on_delete=models.CASCADE,
        related_name='product_candidates',
        help_text="Source page this candidate was extracted from",
    )

    # Extracted Data
    extracted_data = models.JSONField(
        default=dict,
        help_text="All extracted data for this product",
    )

    # Match Status
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatusChoices.choices,
        default=MatchStatusChoices.PENDING,
        help_text="Current matching status",
    )

    # Match Results
    matched_product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_candidates',
        help_text="Matched existing product (if any)",
    )
    match_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text="Confidence of the match (0.0-1.0)",
    )
    match_method = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Method used for matching (gtin, fingerprint, fuzzy, ai)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_candidate"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["match_status"]),
            models.Index(fields=["normalized_name"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Candidate"
        verbose_name_plural = "Product Candidates"

    def __str__(self):
        return f"{self.raw_name} ({self.match_status})"


# ============================================================
# Task Group 15: CrawlSchedule Model - REPLACED by unified CrawlSchedule
# See line ~726 for the new unified scheduling model
# ============================================================


# ============================================================
# Task Group 16: PriceHistory Model
# ============================================================


class PriceHistory(models.Model):
    """
    Task Group 16: Historical price tracking for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='price_history_records',
        help_text="The product",
    )

    # Retailer
    retailer = models.CharField(
        max_length=200,
        help_text="Retailer name",
    )
    retailer_country = models.CharField(
        max_length=100,
        help_text="Retailer's country",
    )

    # Price
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in original currency",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO 4217 currency code",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to EUR",
    )

    # Timing
    observed_at = models.DateTimeField(
        help_text="When this price was observed",
    )
    source_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL where price was observed",
    )

    class Meta:
        db_table = "price_history"
        ordering = ["-observed_at"]
        indexes = [
            models.Index(fields=["product", "retailer"]),
            models.Index(fields=["observed_at"]),
        ]
        verbose_name = "Price History"
        verbose_name_plural = "Price History Records"

    def __str__(self):
        return f"{self.product} - {self.retailer}: {self.currency} {self.price} ({self.observed_at})"


# ============================================================
# Task Group 17: PriceAlert Model
# ============================================================


class PriceAlert(models.Model):
    """
    Task Group 17: Price alerts for significant price changes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='price_alerts',
        help_text="The product",
    )

    # Alert Details
    alert_type = models.CharField(
        max_length=20,
        choices=PriceAlertTypeChoices.choices,
        help_text="Type of alert",
    )
    threshold_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Threshold that triggered the alert",
    )
    triggered_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Actual value that triggered the alert",
    )
    retailer = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Retailer where price change was detected",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    # Acknowledgment
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether this alert has been acknowledged",
    )
    acknowledged_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Who acknowledged this alert",
    )
    acknowledged_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this alert was acknowledged",
    )

    class Meta:
        db_table = "price_alert"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["alert_type"]),
            models.Index(fields=["acknowledged"]),
        ]
        verbose_name = "Price Alert"
        verbose_name_plural = "Price Alerts"

    def __str__(self):
        return f"{self.product} - {self.alert_type}"


# ============================================================
# Task Group 18: NewRelease Model
# ============================================================


class NewRelease(models.Model):
    """
    Task Group 18: Tracking new and upcoming product releases.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product Link (optional - may not exist yet)
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='new_releases',
        help_text="Linked product if it exists",
    )

    # Release Information
    name = models.CharField(
        max_length=500,
        help_text="Product name",
    )
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='new_releases',
        help_text="Brand if known",
    )
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        help_text="Type of product",
    )

    # Status
    release_status = models.CharField(
        max_length=20,
        choices=ReleaseStatusChoices.choices,
        help_text="Current release status",
    )

    # Dates
    announced_date = models.DateField(
        blank=True,
        null=True,
        help_text="When the release was announced",
    )
    expected_release_date = models.DateField(
        blank=True,
        null=True,
        help_text="Expected release date",
    )
    actual_release_date = models.DateField(
        blank=True,
        null=True,
        help_text="Actual release date",
    )

    # Pricing
    expected_price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Expected price in EUR",
    )

    # Limited Edition Info
    limited_edition = models.BooleanField(
        default=False,
        help_text="Whether this is a limited edition",
    )
    expected_bottle_count = models.IntegerField(
        blank=True,
        null=True,
        help_text="Expected number of bottles",
    )

    # Interest Metrics
    hype_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text="Calculated hype/interest score (1-100)",
    )

    # Sources
    source_urls = models.JSONField(
        default=list,
        help_text="URLs where this release was mentioned",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the release",
    )

    # Tracking
    is_tracked = models.BooleanField(
        default=True,
        help_text="Whether to continue tracking this release",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "new_release"
        ordering = ["-expected_release_date"]
        indexes = [
            models.Index(fields=["release_status"]),
            models.Index(fields=["product_type"]),
            models.Index(fields=["expected_release_date"]),
            models.Index(fields=["is_tracked"]),
        ]
        verbose_name = "New Release"
        verbose_name_plural = "New Releases"

    def __str__(self):
        return f"{self.name} ({self.release_status})"


# =============================================================================
# GENERIC SEARCH DISCOVERY MODELS
# =============================================================================
# These models support the automated product discovery system via SerpAPI
# searches with configurable terms managed through Django Admin.
# See: specs/GENERIC_SEARCH_DISCOVERY_FLOW.md
# =============================================================================


class SearchTermCategory(models.TextChoices):
    """Categories of search terms."""

    BEST_LISTS = "best_lists", "Best Lists"
    AWARDS = "awards", "Awards & Recognition"
    NEW_RELEASES = "new_releases", "New Releases"
    STYLE = "style", "Style & Flavor"
    VALUE = "value", "Value & Price"
    REGIONAL = "regional", "Regional/Type"
    SEASONAL = "seasonal", "Seasonal"


class SearchTermProductType(models.TextChoices):
    """Product types for search terms."""

    WHISKEY = "whiskey", "Whiskey"
    PORT_WINE = "port_wine", "Port Wine"
    BOTH = "both", "Both"


# DiscoveryJobStatus REMOVED - replaced by JobStatus (see JobType.DISCOVERY)


# ScheduleFrequency moved to line ~713 as part of unified scheduling
# DiscoveryResultStatus REMOVED - replaced by CrawledPageStatus


class SearchTerm(models.Model):
    """
    Configurable search term for product discovery.

    Admins add complete search queries directly (no template substitution).
    Examples:
    - "best whisky 2026"
    - "top 10 bourbon 2026"

    Managed via Django Admin for easy configuration without code changes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core fields
    search_query = models.CharField(
        max_length=200,
        help_text="Complete search query to execute.",
    )
    category = models.CharField(
        max_length=50,
        choices=SearchTermCategory.choices,
        help_text="Category of the search term for organization and filtering.",
    )
    product_type = models.CharField(
        max_length=20,
        choices=SearchTermProductType.choices,
        help_text="Product type this search term targets.",
    )
    max_results = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Number of search results to crawl (1-20).",
    )

    # Priority and status
    priority = models.IntegerField(
        default=100,
        help_text="Lower number = higher priority. Terms are processed in priority order.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active terms are used in discovery jobs.",
    )

    # Seasonality (optional)
    seasonal_start_month = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Start month for seasonal terms (1-12). Leave blank for year-round.",
    )
    seasonal_end_month = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="End month for seasonal terms (1-12). Leave blank for year-round.",
    )

    # Statistics (read-only, updated by discovery jobs)
    search_count = models.IntegerField(
        default=0,
        help_text="Number of times this term has been searched.",
    )
    products_discovered = models.IntegerField(
        default=0,
        help_text="Number of new products discovered using this term.",
    )
    last_searched = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this term was last used in a search.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_search_term"
        ordering = ["priority", "-products_discovered"]
        indexes = [
            models.Index(fields=["is_active", "priority"]),
            models.Index(fields=["category"]),
            models.Index(fields=["product_type"]),
        ]
        verbose_name = "Search Term"
        verbose_name_plural = "Search Terms"

    def __str__(self):
        return f"{self.search_query} ({self.category})"

    def is_in_season(self) -> bool:
        """
        Check if this term is currently in season.

        Returns:
            bool: True if in season or not seasonal.
        """
        if self.seasonal_start_month is None or self.seasonal_end_month is None:
            return True

        from datetime import date
        current_month = date.today().month

        if self.seasonal_start_month <= self.seasonal_end_month:
            # Normal range (e.g., March-June)
            return self.seasonal_start_month <= current_month <= self.seasonal_end_month
        else:
            # Wrapping range (e.g., November-February)
            return current_month >= self.seasonal_start_month or current_month <= self.seasonal_end_month


# DiscoverySchedule REMOVED - replaced by unified CrawlSchedule model (see line ~726)
# DiscoveryJob REMOVED - replaced by unified Job model with JobType.DISCOVERY
# DiscoveryResult REMOVED - replaced by unified CrawledPage model


class QuotaUsage(models.Model):
    """
    Tracks API quota usage per month.

    Phase 6: Quota Management
    Records usage for SerpAPI, ScrapingBee, and AI services.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # API identification
    api_name = models.CharField(
        max_length=50,
        help_text="Name of the API (serpapi, scrapingbee, ai_service).",
    )
    month = models.CharField(
        max_length=7,
        help_text="Month key in YYYY-MM format.",
    )

    # Usage tracking
    current_usage = models.IntegerField(
        default=0,
        help_text="Number of API calls used this month.",
    )
    monthly_limit = models.IntegerField(
        default=1000,
        help_text="Maximum calls allowed this month.",
    )

    # Metadata
    last_used = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the API was last called.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "quota_usage"
        unique_together = ["api_name", "month"]
        ordering = ["-month", "api_name"]
        verbose_name = "Quota Usage"
        verbose_name_plural = "Quota Usage"

    def __str__(self):
        return f"{self.api_name} ({self.month}): {self.current_usage}/{self.monthly_limit}"

    @property
    def remaining(self) -> int:
        """Get remaining quota."""
        return max(0, self.monthly_limit - self.current_usage)

    @property
    def usage_percentage(self) -> float:
        """Get usage as percentage."""
        if self.monthly_limit == 0:
            return 100.0
        return (self.current_usage / self.monthly_limit) * 100

# ============================================================
# Unified Product Pipeline Models - Phase 1
# ============================================================


class SourceHealthCheck(models.Model):
    """
    Track health check results for crawl sources.

    Unified Pipeline Phase 1: Source health monitoring
    Tracks selector health, yield monitoring, fingerprint checks,
    and known product verification.
    """

    CHECK_TYPE_CHOICES = [
        ("selector", "Selector Health"),
        ("yield", "Yield Monitoring"),
        ("fingerprint", "Structural Fingerprint"),
        ("known_product", "Known Product Verification"),
    ]

    source = models.CharField(
        max_length=50,
        help_text="Source identifier (e.g., 'iwsc', 'sfwsc').",
    )
    check_type = models.CharField(
        max_length=20,
        choices=CHECK_TYPE_CHOICES,
        help_text="Type of health check performed.",
    )
    is_healthy = models.BooleanField(
        help_text="Whether the health check passed.",
    )
    details = models.JSONField(
        default=dict,
        help_text="Detailed health check results and metrics.",
    )
    checked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the health check was performed.",
    )

    class Meta:
        db_table = "source_health_check"
        indexes = [
            models.Index(fields=["source", "check_type"]),
            models.Index(fields=["checked_at"]),
        ]
        verbose_name = "Source Health Check"
        verbose_name_plural = "Source Health Checks"

    def __str__(self):
        status = "OK" if self.is_healthy else "FAIL"
        return f"{self.source} [{self.check_type}]: {status}"


class SourceFingerprint(models.Model):
    """
    Store structural fingerprints for sources.

    Unified Pipeline Phase 1: Source structure tracking
    Used to detect when source page structures change,
    which may indicate selectors need updating.
    """

    source = models.CharField(
        max_length=50,
        unique=True,
        help_text="Source identifier (e.g., 'iwsc', 'sfwsc').",
    )
    fingerprint = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of page structure elements.",
    )
    sample_url = models.URLField(
        help_text="URL used to generate the fingerprint.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the fingerprint was last updated.",
    )

    class Meta:
        db_table = "source_fingerprint"
        verbose_name = "Source Fingerprint"
        verbose_name_plural = "Source Fingerprints"

    def __str__(self):
        return f"{self.source}: {self.fingerprint[:12]}..."


class APICrawlJob(models.Model):
    """
    Track API-triggered crawl jobs.

    Unified Pipeline Phase 1: API job tracking
    Records crawl jobs initiated via the REST API,
    including status, progress, and execution details.
    """

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    job_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique job identifier (UUID).",
    )
    source = models.CharField(
        max_length=50,
        help_text="Source identifier (e.g., 'iwsc', 'sfwsc').",
    )
    year = models.IntegerField(
        help_text="Competition year to crawl.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="queued",
        help_text="Current job status.",
    )
    progress = models.JSONField(
        default=dict,
        help_text="Progress details: {total, processed, errors}.",
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if job failed.",
    )
    celery_task_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Celery task ID for background processing.",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job started execution.",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job completed.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the job was created.",
    )

    class Meta:
        db_table = "api_crawl_job"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["source", "year"]),
        ]
        verbose_name = "API Crawl Job"
        verbose_name_plural = "API Crawl Jobs"

    def __str__(self):
        return f"{self.source}/{self.year} [{self.status}]"

    @property
    def elapsed_seconds(self) -> int:
        """Calculate elapsed time in seconds."""
        if not self.started_at:
            return 0
        end = self.completed_at or timezone.now()
        return int((end - self.started_at).total_seconds())
# ============================================================
# DATABASE CLEANUP SPEC: New Models - Phase 1
# Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4
# ============================================================


class EnrichmentSourceStatus(models.TextChoices):
    """Status of an enrichment source."""
    USED = "used", "Used"
    REJECTED = "rejected", "Rejected"
    MEMBERS_ONLY = "members_only", "Members Only"
    SEARCHED = "searched", "Searched"
    FAILED = "failed", "Failed"


class EnrichmentStepType(models.TextChoices):
    """Type of enrichment step."""
    DISCOVERY = "discovery", "Discovery Source"
    TASTING_NOTES = "tasting_notes", "Tasting Notes Search"
    AWARDS = "awards", "Awards Search"
    PRICING = "pricing", "Pricing Search"
    ENRICHMENT = "enrichment", "General Enrichment"


class ConflictStatus(models.TextChoices):
    """Status of a product conflict."""
    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"
    IGNORED = "ignored", "Ignored"


class ConflictResolutionMethod(models.TextChoices):
    """Method used to resolve a conflict."""
    HIGHEST_CONFIDENCE = "highest_confidence", "Highest Confidence"
    MOST_RECENT = "most_recent", "Most Recent"
    SOURCE_PRIORITY = "source_priority", "Source Priority"
    MANUAL = "manual", "Manual"


class TrendDirection(models.TextChoices):
    """Direction of trend."""
    RISING = "rising", "Rising"
    STABLE = "stable", "Stable"
    DECLINING = "declining", "Declining"


class EnrichmentSource(models.Model):
    """
    DATABASE CLEANUP SPEC: Track all sources used during product enrichment.

    Replaces multiple JSON blob fields:
    - enrichment_sources_used
    - enrichment_sources_rejected
    - enrichment_sources_searched
    - members_only_sites_detected

    Key Features:
    - step_number=0 for discovery source
    - step_number>0 for enrichment steps
    - step_number=-1 for rejected/searched-only sources
    - status tracks used/rejected/members_only/searched
    - Per-field extraction via ProductFieldSourceV2

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.1
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="enrichment_sources",
        help_text="The product this source contributed to",
    )

    # Source identification
    url = models.URLField(
        max_length=2000,
        help_text="URL of the source page",
    )
    domain = models.CharField(
        max_length=255,
        help_text="Domain extracted from URL for querying",
    )

    # Step tracking
    step_number = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Step number: 0=discovery, >0=enrichment step, -1=rejected/searched",
    )
    step_type = models.CharField(
        max_length=30,
        choices=EnrichmentStepType.choices,
        help_text="Type of enrichment step: discovery, tasting_notes, awards, pricing, enrichment",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=EnrichmentSourceStatus.choices,
        help_text="Status: used, rejected, members_only, searched, failed",
    )

    # Rejection tracking
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for rejection if status=rejected",
    )

    # Extraction confidence
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        blank=True,
        null=True,
        help_text="Overall confidence of extraction from this source (0.0-1.0)",
    )

    # Wayback Machine archiving
    wayback_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Wayback Machine archive URL",
    )
    wayback_archived_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the page was archived to Wayback Machine",
    )

    # Timestamps
    crawled_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this source was crawled",
    )

    class Meta:
        db_table = "enrichment_source"
        ordering = ["step_number", "-crawled_at"]
        indexes = [
            models.Index(fields=["product", "step_number"]),
            models.Index(fields=["domain"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Enrichment Source"
        verbose_name_plural = "Enrichment Sources"

    def __str__(self):
        return f"{self.product} <- {self.domain} (step {self.step_number}, {self.status})"

    def get_fields_extracted(self) -> list:
        """Get list of field names extracted from this source."""
        return list(
            self.field_sources.values_list("field_name", flat=True)
        )


class ProductFieldSourceV2(models.Model):
    """
    DATABASE CLEANUP SPEC: Per-field provenance tracking linked to EnrichmentSource.

    Tracks which EnrichmentSource contributed each field value, enabling:
    - Detailed provenance tracking
    - Conflict detection across sources
    - Per-field confidence scoring

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.5
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to EnrichmentSource (not CrawledSource)
    enrichment_source = models.ForeignKey(
        EnrichmentSource,
        on_delete=models.CASCADE,
        related_name="field_sources",
        help_text="The enrichment source that provided this field value",
    )

    # Field information
    field_name = models.CharField(
        max_length=100,
        help_text="Name of the field (e.g., nose_description, abv)",
    )
    extracted_value = models.TextField(
        help_text="The extracted value (stored as string/JSON)",
    )

    # Confidence
    confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for this extraction (0.0-1.0)",
    )

    # Whether this value was used (vs rejected in conflict)
    is_current_value = models.BooleanField(
        default=True,
        help_text="Whether this is the current value used on the product",
    )

    # Timestamps
    extracted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this field was extracted",
    )

    class Meta:
        db_table = "product_field_source_v2"
        indexes = [
            models.Index(fields=["enrichment_source"]),
            models.Index(fields=["field_name"]),
        ]
        verbose_name = "Product Field Source V2"
        verbose_name_plural = "Product Field Sources V2"

    def __str__(self):
        return f"{self.enrichment_source.product}.{self.field_name} <- {self.enrichment_source.domain}"


class ProductAvailabilityTimeSeries(models.Model):
    """
    DATABASE CLEANUP SPEC: Time-series availability tracking.

    Replaces snapshot fields on DiscoveredProduct:
    - availability_score
    - retailer_count

    Allows tracking availability over time for trend analysis.

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.2
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="availability_history",
        help_text="The product this availability record is for",
    )

    # Aggregated availability metrics
    availability_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Overall availability score (1-10)",
    )
    retailer_count = models.IntegerField(
        default=0,
        help_text="Number of retailers carrying the product",
    )
    in_stock_count = models.IntegerField(
        default=0,
        help_text="Number of retailers with in-stock status",
    )

    # Regional availability
    eu_available = models.BooleanField(
        default=False,
        help_text="Whether product is available in EU market",
    )
    german_available = models.BooleanField(
        default=False,
        help_text="Whether product is available in German market",
    )

    # Timestamp
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this availability snapshot was recorded",
    )

    class Meta:
        db_table = "product_availability_time_series"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["product", "recorded_at"]),
        ]
        verbose_name = "Product Availability (Time Series)"
        verbose_name_plural = "Product Availability (Time Series)"

    def __str__(self):
        return f"{self.product} - Score: {self.availability_score} ({self.recorded_at.date()})"


class ProductTrend(models.Model):
    """
    DATABASE CLEANUP SPEC: Time-series trend tracking.

    Replaces snapshot fields on DiscoveredProduct:
    - trend_score
    - trend_direction
    - buzz_score
    - is_allocated

    Allows tracking trend metrics over time.

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.3
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="trend_history",
        help_text="The product this trend record is for",
    )

    # Trend metrics
    trend_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Overall trend score (1-100)",
    )
    trend_direction = models.CharField(
        max_length=20,
        choices=TrendDirection.choices,
        help_text="Trend direction: rising, stable, declining",
    )

    # Buzz/hype metrics
    buzz_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text="Buzz/hype score (1-100)",
    )
    search_interest = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text="Search interest score (1-100)",
    )

    # Allocation status
    is_allocated = models.BooleanField(
        default=False,
        help_text="Whether product is allocated/limited distribution",
    )

    # Timestamp
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this trend snapshot was recorded",
    )

    class Meta:
        db_table = "product_trend"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["product", "recorded_at"]),
        ]
        verbose_name = "Product Trend"
        verbose_name_plural = "Product Trends"

    def __str__(self):
        return f"{self.product} - Score: {self.trend_score} ({self.trend_direction}) ({self.recorded_at.date()})"


class ProductConflict(models.Model):
    """
    DATABASE CLEANUP SPEC: Conflict detection and resolution workflow.

    Replaces JSON fields on DiscoveredProduct:
    - has_conflicts
    - conflict_details

    Provides structured conflict tracking with resolution workflow.

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.4
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product relationship
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name="conflicts",
        help_text="The product with conflicting data",
    )

    # Conflict details
    field_name = models.CharField(
        max_length=100,
        help_text="Name of the field with conflict",
    )
    source_values = models.JSONField(
        help_text="All values from different sources: [{'source_url': ..., 'value': ..., 'confidence': ...}]",
    )
    current_value = models.TextField(
        help_text="The current value set on the product",
    )

    # Status and resolution
    status = models.CharField(
        max_length=20,
        choices=ConflictStatus.choices,
        default=ConflictStatus.PENDING,
        help_text="Conflict status: pending, resolved, ignored",
    )
    resolution_method = models.CharField(
        max_length=30,
        choices=ConflictResolutionMethod.choices,
        blank=True,
        null=True,
        help_text="How the conflict was resolved",
    )
    resolved_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Who resolved the conflict (system or user)",
    )
    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the conflict was resolved",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the conflict was detected",
    )

    class Meta:
        db_table = "product_conflict"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "field_name"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Product Conflict"
        verbose_name_plural = "Product Conflicts"

    def __str__(self):
        return f"{self.product}.{self.field_name} ({self.status})"


class JobType(models.TextChoices):
    """Type of job."""
    DISCOVERY = "discovery", "Discovery"
    CRAWL = "crawl", "Crawl"
    ENRICHMENT = "enrichment", "Enrichment"
    COMPETITION = "competition", "Competition"


class JobStatus(models.TextChoices):
    """Status of a job."""
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class Job(models.Model):
    """
    DATABASE CLEANUP SPEC: Unified Job model.

    Consolidates CrawlJob + DiscoveryJob into single model with job_type discriminator.

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.6
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Schedule relationship (optional for legacy source-only jobs)
    schedule = models.ForeignKey(
        "CrawlSchedule",
        on_delete=models.CASCADE,
        related_name="unified_jobs",
        null=True,
        blank=True,
        help_text="The schedule that triggered this job (optional for legacy jobs)",
    )

    # Job type discriminator
    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        help_text="Type of job: discovery, crawl, enrichment, competition",
    )

    # Optional relationships (depend on job_type)
    crawler_source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unified_jobs",
        help_text="Crawler source (for crawl jobs)",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        help_text="Current job status",
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Common metrics
    urls_processed = models.IntegerField(default=0)
    products_found = models.IntegerField(default=0)
    products_new = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    products_duplicates = models.IntegerField(default=0)
    products_failed = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)

    # Flexible metrics JSONField (for job-type specific metrics)
    metrics = models.JSONField(
        default=dict,
        help_text="Job-type specific metrics (serpapi_calls, scrapingbee_calls, etc.)",
    )

    # Error details
    error_message = models.TextField(blank=True)
    error_log = models.TextField(blank=True)

    class Meta:
        db_table = "job"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["job_type", "status"]),
            models.Index(fields=["schedule", "created_at"]),
        ]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"

    def __str__(self):
        return f"Job {self.id} - {self.job_type} ({self.status})"

    @property
    def duration_seconds(self) -> int:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        elif self.started_at:
            return int((timezone.now() - self.started_at).total_seconds())
        return 0

    def start(self):
        """Mark job as started/running."""
        self.status = JobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def complete(self, success: bool = True, error_message: str = None):
        """Mark job as completed or failed."""
        self.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        self.completed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=["status", "completed_at", "error_message"])

        # Update source stats for crawl jobs
        if self.job_type == JobType.CRAWL and self.crawler_source:
            self.crawler_source.last_crawl_status = self.status
            self.crawler_source.total_products_found += self.products_new
            self.crawler_source.update_next_crawl_time()

    def log_error(self, error: str):
        """Append an error to the error log."""
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.error_log:
            self.error_log += f"\n[{timestamp}] {error}"
        else:
            self.error_log = f"[{timestamp}] {error}"
        self.errors_count += 1
        self.save(update_fields=["error_log", "errors_count"])


class CrawledPageStatus(models.TextChoices):
    """Status of a crawled page."""
    PENDING = "pending", "Pending"
    CRAWLED = "crawled", "Crawled"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class CrawledPageDiscoveryMethod(models.TextChoices):
    """How the page was discovered."""
    CRAWL = "crawl", "Crawl"
    SEARCH = "search", "Search"
    MANUAL = "manual", "Manual"
    ENRICHMENT = "enrichment", "Enrichment"


class CrawledPageType(models.TextChoices):
    """Type of crawled page."""
    PRODUCT = "product", "Product"
    REVIEW = "review", "Review"
    ARTICLE = "article", "Article"
    AWARD = "award", "Award"
    LISTING = "listing", "Listing"
    SEARCH_RESULT = "search_result", "Search Result"
    OTHER = "other", "Other"


class CrawledPage(models.Model):
    """
    DATABASE CLEANUP SPEC: Unified URL tracking model.

    Consolidates CrawledURL + CrawledSource + DiscoveryResult into single model.

    Spec Reference: DATABASE_CLEANUP_SPEC.md Section 4.7
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # URL identification (unique)
    url = models.URLField(
        max_length=2000,
        unique=True,
        db_index=True,
        help_text="URL of the page (unique)",
    )
    url_hash = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        help_text="SHA-256 hash of URL for indexing",
    )
    domain = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Domain extracted from URL",
    )

    # Discovery method
    discovery_method = models.CharField(
        max_length=20,
        choices=CrawledPageDiscoveryMethod.choices,
        help_text="How this page was discovered: crawl, search, manual, enrichment",
    )

    # Optional relationships
    crawler_source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawled_pages",
        help_text="Crawler source (if discovery_method=crawl)",
    )
    search_term = models.ForeignKey(
        "SearchTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawled_pages",
        help_text="Search term (if discovery_method=search)",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawled_pages",
        help_text="Job that crawled this page",
    )

    # Page classification
    page_type = models.CharField(
        max_length=20,
        choices=CrawledPageType.choices,
        default=CrawledPageType.OTHER,
        help_text="Type of page: product, review, article, award, listing, search_result, other",
    )
    is_product_page = models.BooleanField(
        default=False,
        help_text="Whether this page contains product information",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=CrawledPageStatus.choices,
        default=CrawledPageStatus.PENDING,
        help_text="Processing status: pending, crawled, processed, failed, skipped",
    )

    # Search result metadata (if discovery_method=search)
    search_title = models.CharField(
        max_length=500,
        blank=True,
        help_text="Title from search results",
    )
    search_snippet = models.TextField(
        blank=True,
        help_text="Snippet from search results",
    )
    search_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in search results (1 = first)",
    )

    # Content tracking
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of content for change detection",
    )
    word_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Word count of extracted content",
    )

    # Wayback Machine
    wayback_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Wayback Machine archive URL",
    )
    wayback_archived_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the page was archived",
    )

    # Product linkage (for discovery workflow - from DiscoveryResult)
    product = models.ForeignKey(
        "DiscoveredProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawled_pages",
        help_text="Product discovered from this page, if any",
    )
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw extracted product data from crawl/search",
    )
    is_duplicate = models.BooleanField(
        default=False,
        help_text="Whether this URL led to a duplicate product",
    )
    is_new_product = models.BooleanField(
        default=False,
        help_text="Whether this URL led to a new product",
    )
    crawl_success = models.BooleanField(
        default=False,
        help_text="Whether the URL was successfully crawled",
    )
    extraction_success = models.BooleanField(
        default=False,
        help_text="Whether product extraction succeeded",
    )
    content_changed = models.BooleanField(
        default=False,
        help_text="Whether content changed since last crawl",
    )

    # Content storage (from CrawledSource)
    title = models.CharField(
        max_length=500,
        blank=True,
        help_text="Title of the page",
    )
    raw_content = models.TextField(
        blank=True,
        null=True,
        help_text="Raw HTML content of the page",
    )
    raw_content_cleared = models.BooleanField(
        default=False,
        help_text="Whether raw content has been cleared after processing",
    )
    preprocessed_content = models.TextField(
        blank=True,
        null=True,
        help_text="Preprocessed/cleaned content for AI extraction",
    )
    preprocessed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the content was preprocessed",
    )
    cleanup_eligible = models.BooleanField(
        default=False,
        help_text="Whether raw content can be cleared (extraction processed AND wayback saved)",
    )

    # Timestamps
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    last_processed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)
    crawl_attempts = models.IntegerField(default=0)

    class Meta:
        db_table = "crawled_page"
        ordering = ["-first_seen_at"]
        indexes = [
            models.Index(fields=["domain", "status"]),
            models.Index(fields=["crawler_source", "status"]),
            models.Index(fields=["search_term", "status"]),
            models.Index(fields=["job"]),
            models.Index(fields=["page_type"]),
        ]
        verbose_name = "Crawled Page"
        verbose_name_plural = "Crawled Pages"

    def __str__(self):
        return f"{self.domain} - {self.page_type} ({self.status})"

    def save(self, *args, **kwargs):
        """Auto-compute url_hash and domain before saving."""
        if not self.url_hash and self.url:
            self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()
        if not self.domain and self.url:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            self.domain = parsed.netloc
        super().save(*args, **kwargs)
