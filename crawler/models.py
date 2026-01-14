"""
Django models for Web Crawler System.

Models: CrawlerSource, CrawlerKeyword, CrawlJob, CrawledURL, DiscoveredProduct,
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


class CrawlJobStatus(models.TextChoices):
    """Status of a crawl job."""

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class DiscoveredProductStatus(models.TextChoices):
    """
    Status of a discovered product - based on completeness and verification.

    Status Model:
    - INCOMPLETE: Score 0-29, missing critical data (no palate profile)
    - PARTIAL: Score 30-59, has basic info but no tasting profile
    - COMPLETE: Score 60-79, has tasting profile (at least palate)
    - VERIFIED: Score 80-100, multi-source verified with full tasting
    - REJECTED: Not a valid product
    - MERGED: Merged into another product

    Note: A product CANNOT reach COMPLETE or VERIFIED without palate tasting data.
    """

    INCOMPLETE = "incomplete", "Incomplete"
    PARTIAL = "partial", "Partial"
    COMPLETE = "complete", "Complete"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    MERGED = "merged", "Merged"

    # Legacy status values - kept for migration compatibility
    PENDING = "pending", "Pending Review (Legacy)"
    APPROVED = "approved", "Approved (Legacy)"
    DUPLICATE = "duplicate", "Duplicate (Legacy)"
    SKELETON = "skeleton", "Skeleton (Legacy)"


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
# Task Group 6: CrawledSource Choices
# ============================================================


class CrawledSourceTypeChoices(models.TextChoices):
    """
    Task Group 6: Source type choices for CrawledSource.

    Classifies the type of crawled page:
    - award_page: Award/competition results page
    - review_article: Review article page
    - retailer_page: Retailer product listing page
    - distillery_page: Distillery product page
    - news_article: News or press article
    - list_page: List page with multiple products (e.g., "Best Whiskey 2026" articles)
    """

    AWARD_PAGE = "award_page", "Award Page"
    REVIEW_ARTICLE = "review_article", "Review Article"
    RETAILER_PAGE = "retailer_page", "Retailer Page"
    DISTILLERY_PAGE = "distillery_page", "Distillery Page"
    NEWS_ARTICLE = "news_article", "News Article"
    LIST_PAGE = "list_page", "List Page"


class ExtractionStatusChoices(models.TextChoices):
    """
    Task Group 6: Extraction status choices for CrawledSource.

    Tracks the processing status of a crawled page:
    - pending: Not yet processed
    - processed: Successfully processed
    - failed: Processing failed
    - needs_review: Requires manual review
    """

    PENDING = "pending", "Pending"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    NEEDS_REVIEW = "needs_review", "Needs Review"


class WaybackStatusChoices(models.TextChoices):
    """
    Task Group 6: Wayback Machine archive status choices.

    Tracks the Wayback Machine archival status:
    - pending: Archive not yet attempted
    - saved: Successfully archived
    - failed: Archival failed
    - not_applicable: Not applicable for archival
    """

    PENDING = "pending", "Pending"
    SAVED = "saved", "Saved"
    FAILED = "failed", "Failed"
    NOT_APPLICABLE = "not_applicable", "Not Applicable"


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
# ============================================================


class FieldTypeChoices(models.TextChoices):
    """
    V2 Architecture: Field type choices for FieldDefinition.

    Defines the data type of a field for AI extraction:
    - string: Short text value
    - text: Long text value
    - integer: Whole number
    - decimal: Decimal number
    - boolean: True/False value
    - array: List of values
    - object: Nested object structure
    """

    STRING = "string", "String"
    TEXT = "text", "Text (long)"
    INTEGER = "integer", "Integer"
    DECIMAL = "decimal", "Decimal"
    BOOLEAN = "boolean", "Boolean"
    ARRAY = "array", "Array"
    OBJECT = "object", "Object"


class FieldGroupChoices(models.TextChoices):
    """
    V2 Architecture: Field group choices for FieldDefinition.

    Organizes fields into logical groups for display and extraction:
    - core: Core product identification fields
    - tasting_appearance: Visual/color tasting notes
    - tasting_nose: Aroma/nose tasting notes
    - tasting_palate: Palate/flavor tasting notes
    - tasting_finish: Finish tasting notes
    - tasting_overall: Overall assessment
    - production: Production/manufacturing details
    - cask: Cask/maturation information
    - related: Related data (awards, prices, ratings)
    - type_specific: Type-specific fields (whiskey, port, etc.)
    """

    CORE = "core", "Core Product"
    TASTING_APPEARANCE = "tasting_appearance", "Tasting - Appearance"
    TASTING_NOSE = "tasting_nose", "Tasting - Nose"
    TASTING_PALATE = "tasting_palate", "Tasting - Palate"
    TASTING_FINISH = "tasting_finish", "Tasting - Finish"
    TASTING_OVERALL = "tasting_overall", "Tasting - Overall"
    PRODUCTION = "production", "Production"
    CASK = "cask", "Cask/Maturation"
    RELATED = "related", "Related Data"
    TYPE_SPECIFIC = "type_specific", "Type Specific"


class TargetModelChoices(models.TextChoices):
    """
    V2 Architecture: Target model choices for FieldDefinition.

    Specifies which Django model a field maps to:
    - DiscoveredProduct: Main product model
    - WhiskeyDetails: Whiskey-specific details
    - PortWineDetails: Port wine-specific details
    - ProductAward: Award records
    - ProductPrice: Price records
    - ProductRating: Rating records
    """

    DISCOVERED_PRODUCT = "DiscoveredProduct", "DiscoveredProduct"
    WHISKEY_DETAILS = "WhiskeyDetails", "WhiskeyDetails"
    PORT_WINE_DETAILS = "PortWineDetails", "PortWineDetails"
    PRODUCT_AWARD = "ProductAward", "ProductAward"
    PRODUCT_PRICE = "ProductPrice", "ProductPrice"
    PRODUCT_RATING = "ProductRating", "ProductRating"


class ProductTypeConfig(models.Model):
    """
    V2 Architecture: Configuration for a product type (whiskey, port_wine, gin, etc.)

    Top-level configuration that defines how a product type is handled by
    the crawler and AI service. All product type knowledge is stored here
    rather than in code.

    Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2.1
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
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
    version = models.CharField(
        max_length=20,
        default="1.0",
        help_text="Configuration version for tracking changes",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this product type configuration",
    )

    # Valid categories for this product type
    categories = models.JSONField(
        default=list,
        help_text='Valid categories: ["bourbon", "scotch", "rye"]',
    )

    # ============================================
    # Enrichment Limits (V3 defaults - consolidated from PipelineConfig)
    # ============================================

    max_sources_per_product = models.IntegerField(
        default=8,
        help_text="Maximum sources to fetch per product (V3: increased from 5)",
    )
    max_serpapi_searches = models.IntegerField(
        default=6,
        help_text="Maximum SerpAPI searches per product (V3: increased from 3)",
    )
    max_enrichment_time_seconds = models.IntegerField(
        default=180,
        help_text="Maximum enrichment time in seconds (V3: increased from 120)",
    )

    # ============================================
    # Awards Search (V3 feature - moved from PipelineConfig)
    # ============================================

    awards_search_enabled = models.BooleanField(
        default=True,
        help_text="Enable dedicated awards search (Step 4 in V3 pipeline)",
    )
    awards_search_template = models.CharField(
        max_length=500,
        default="{name} {brand} awards medals competition winner",
        help_text="Search template for awards discovery",
    )

    # ============================================
    # Members-Only Site Detection (V3 feature - moved from PipelineConfig)
    # ============================================

    members_only_detection_enabled = models.BooleanField(
        default=True,
        help_text="Enable content analysis for members-only/paywall sites",
    )
    members_only_patterns = models.JSONField(
        default=list,
        help_text="Regex patterns to detect members-only sites (login forms, paywalls)",
    )

    # ============================================
    # ECP (Enrichment Completion Percentage) Settings - moved from PipelineConfig
    # ============================================

    ecp_complete_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=90.0,
        help_text="ECP percentage required for COMPLETE status (V3 default: 90%)",
    )

    # ============================================
    # Status Thresholds (V3 JSON structure) - moved from PipelineConfig
    # ============================================

    status_thresholds = models.JSONField(
        default=dict,
        help_text="Status requirements per level (skeleton, partial, baseline, enriched, complete)",
    )

    # ============================================
    # Timestamps
    # ============================================

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="User who last updated this configuration",
    )

    class Meta:
        db_table = "product_type_config"
        verbose_name = "Product Type Configuration"
        verbose_name_plural = "Product Type Configurations"
        ordering = ["product_type"]

    def __str__(self):
        return f"{self.display_name} ({self.product_type})"


class FieldDefinition(models.Model):
    """
    V2 Architecture: Field definition for extraction schema with model mapping.

    Defines a field that can be extracted by the AI service, including:
    - AI extraction instructions (description, examples, allowed values)
    - Model mapping (which Django model/field to store the extracted data)

    Fields with null product_type_config are shared/base fields for all product types.

    Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2.2
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship - null means shared/base field for all product types
    product_type_config = models.ForeignKey(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name="fields",
        null=True,
        blank=True,
        help_text="Null = shared/base field for all product types",
    )

    # Field identity
    field_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Field name used in extraction schema",
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Human-readable field name",
    )
    field_group = models.CharField(
        max_length=50,
        choices=FieldGroupChoices.choices,
        default=FieldGroupChoices.CORE,
        help_text="Logical group for organizing fields",
    )

    # ============================================
    # AI Extraction Schema (sent to AI Service)
    # ============================================

    field_type = models.CharField(
        max_length=20,
        choices=FieldTypeChoices.choices,
        help_text="Data type of the field",
    )
    item_type = models.CharField(
        max_length=20,
        blank=True,
        help_text="For arrays: type of items (string, object)",
    )
    description = models.TextField(
        help_text="Description for AI extraction - be specific and clear!",
    )
    examples = models.JSONField(
        default=list,
        help_text='Examples help AI understand: ["Ardbeg 10", "Glenfiddich 18"]',
    )
    allowed_values = models.JSONField(
        default=list,
        blank=True,
        help_text='For enums: ["gold", "silver", "bronze"]',
    )
    item_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="Schema for object/array items (awards, ratings, etc.)",
    )

    format_hint = models.TextField(
        blank=True,
        null=True,
        help_text="Format specification for AI extraction (e.g., 'YYYY-YYYY for date ranges')",
    )

    # ============================================
    # Model Mapping (where to store extracted data)
    # ============================================

    target_model = models.CharField(
        max_length=100,
        choices=TargetModelChoices.choices,
        help_text="Django model where this field is stored",
    )
    target_field = models.CharField(
        max_length=100,
        help_text="Field name in the target model",
    )

    # ============================================
    # Field Derivation (for array fields)
    # ============================================
    derive_from = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Field name to derive this array field from (e.g., 'finish_flavors' derives from 'finish_description'). "
                  "When set, AI will extract individual items from the prose description.",
    )

    # Ordering and status
    sort_order = models.IntegerField(
        default=0,
        help_text="Order within field group (lower = first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this field definition",
    )

    class Meta:
        db_table = "field_definition"
        ordering = ["field_group", "sort_order", "field_name"]
        unique_together = [["product_type_config", "field_name"]]
        verbose_name = "Field Definition"
        verbose_name_plural = "Field Definitions"

    def __str__(self):
        type_name = self.product_type_config.product_type if self.product_type_config else "shared"
        return f"{self.field_name} ({type_name})"

    def to_extraction_schema(self) -> dict:
        """
        Convert field definition to schema dict for AI extraction.

        Returns a dictionary suitable for inclusion in the extraction_schema
        sent to the AI service. Includes:
        - name: Field name for reference
        - type: Data type (string, integer, array, etc.)
        - description: Detailed description for AI
        - examples: Sample values (if defined)
        - derive_from: Source field for derivation (if defined)
        - derive_instruction: Human-readable derivation instruction
        - allowed_values: Valid enum values (if defined)
        - enum_instruction: Constraint instruction for enums
        - item_schema: Schema for nested objects (if defined)
        - format_hint: Format specification (if defined)
        """
        schema = {
            "name": self.field_name,
            "type": self.field_type,
            "description": self.description,
        }

        # Add examples if present
        if self.examples:
            schema["examples"] = self.examples

        # Add derive_from with instruction if present
        if self.derive_from:
            schema["derive_from"] = self.derive_from
            schema["derive_instruction"] = (
                f"If {self.field_name} is not explicitly found, "
                f"derive by parsing the {self.derive_from} field"
            )

        # Add allowed_values with enum instruction if present
        if self.allowed_values:
            schema["allowed_values"] = self.allowed_values
            schema["enum_instruction"] = (
                f"MUST be one of: {', '.join(str(v) for v in self.allowed_values)}"
            )

        # Add item_type for arrays
        if self.item_type:
            schema["item_type"] = self.item_type

        # Add item_schema for nested types
        if self.item_schema:
            schema["item_schema"] = self.item_schema

        # Add format_hint if present
        if self.format_hint:
            schema["format_hint"] = self.format_hint

        return schema

    @classmethod
    def get_schema_for_product_type(
        cls,
        product_type: str,
        include_common: bool = True,
    ) -> list[dict]:
        """
        Get extraction schema for a product type.

        Retrieves all field definitions relevant to a specific product type,
        converts them to extraction schema format, and returns as a list.

        Args:
            product_type: Product type identifier (e.g., "whiskey", "port_wine")
            include_common: Whether to include common/shared fields (default True)

        Returns:
            List of schema dicts ready for AI service extraction
        """
        # Get fields specific to this product type via ProductTypeConfig
        type_specific_fields = cls.objects.filter(
            product_type_config__product_type=product_type,
            is_active=True,
        )

        if include_common:
            # Get common/shared fields (product_type_config is null)
            common_fields = cls.objects.filter(
                product_type_config__isnull=True,
                is_active=True,
            )
            # Combine both querysets
            all_fields = common_fields | type_specific_fields
        else:
            all_fields = type_specific_fields

        # Convert to schema format and return as list
        return [field.to_extraction_schema() for field in all_fields.distinct()]


class QualityGateConfig(models.Model):
    """
    V3 Architecture: Quality gate thresholds for a product type.

    Defines the requirements for each product status level:
    - SKELETON: Has name only
    - PARTIAL: Has basic product information
    - BASELINE: Has core tasting profile and production data (formerly COMPLETE)
    - ENRICHED: Has advanced tasting and cask information
    - COMPLETE: Has 90%+ of all enrichable fields (ECP threshold)

    V3 Logic (simplified, no any-of):
        SKELETON = ALL skeleton_required_fields
        PARTIAL = ALL partial_required_fields
        BASELINE = ALL baseline_required_fields + (ANY baseline_or_fields satisfied)
        ENRICHED = BASELINE + ALL enriched_required_fields + (ANY enriched_or_fields satisfied)
        COMPLETE = ECP >= 90%

    Spec Reference: ENRICHMENT_PIPELINE_V3_SPEC.md Section 2 & 6.1
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product_type_config = models.OneToOneField(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name="quality_gates",
        help_text="Product type this quality gate applies to",
    )

    # ============================================
    # SKELETON: Has name only
    # ============================================

    skeleton_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL of these. Example: ["name"]',
    )

    # ============================================
    # PARTIAL: Has basic product information
    # V3: No any-of logic, ALL fields required
    # ============================================

    partial_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL. V3: ["name", "brand", "abv", "region", "country", "category"]',
    )

    # V2 Legacy fields - kept for migration, not used in V3
    partial_any_of_count = models.IntegerField(
        default=0,
        help_text="DEPRECATED in V3 - not used",
    )
    partial_any_of_fields = models.JSONField(
        default=list,
        help_text="DEPRECATED in V3 - not used",
    )

    # ============================================
    # BASELINE: Has core tasting profile (formerly COMPLETE)
    # V3: No any-of logic, ALL required + OR fields
    # ============================================

    baseline_required_fields = models.JSONField(
        default=list,
        help_text='V3: Must have ALL. Replaces complete_required_fields.',
    )
    baseline_or_fields = models.JSONField(
        default=list,
        help_text='V3: List of field pairs where either satisfies. Example: [["indication_age", "harvest_year"]]',
    )
    baseline_or_field_exceptions = models.JSONField(
        default=dict,
        help_text='V3: Conditions to waive OR requirements. Example: {"style": ["ruby", "reserve_ruby"]}',
    )

    # V2 Legacy fields - kept for migration, not used in V3
    complete_required_fields = models.JSONField(
        default=list,
        help_text="DEPRECATED in V3 - use baseline_required_fields",
    )
    complete_any_of_count = models.IntegerField(
        default=0,
        help_text="DEPRECATED in V3 - not used",
    )
    complete_any_of_fields = models.JSONField(
        default=list,
        help_text="DEPRECATED in V3 - not used",
    )

    # ============================================
    # ENRICHED: Has advanced tasting and cask info
    # V3: Required fields + OR fields (no any-of)
    # ============================================

    enriched_required_fields = models.JSONField(
        default=list,
        help_text='V3: Must have ALL. Example: ["mouthfeel"]',
    )
    enriched_or_fields = models.JSONField(
        default=list,
        help_text='V3: List of field pairs where either satisfies. Example: [["complexity", "overall_complexity"]]',
    )

    # V2 Legacy fields - kept for migration, not used in V3
    enriched_any_of_count = models.IntegerField(
        default=0,
        help_text="DEPRECATED in V3 - not used",
    )
    enriched_any_of_fields = models.JSONField(
        default=list,
        help_text="DEPRECATED in V3 - not used",
    )

    class Meta:
        db_table = "quality_gate_config"
        verbose_name = "Quality Gate Configuration"
        verbose_name_plural = "Quality Gate Configurations"

    def __str__(self):
        return f"Quality Gates for {self.product_type_config.product_type}"


class EnrichmentConfig(models.Model):
    """
    V2 Architecture: Enrichment search templates for a product type.

    Defines search templates used for progressive enrichment when a product
    is missing data. Templates specify how to search for additional sources
    and which fields they target.

    Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2.4
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product_type_config = models.ForeignKey(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name="enrichment_templates",
        help_text="Product type this enrichment config applies to",
    )

    # Template identity
    template_name = models.CharField(
        max_length=50,
        help_text='Template identifier (e.g., "tasting_notes")',
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable template name",
    )

    # Search template with placeholders
    search_template = models.CharField(
        max_length=500,
        help_text='Use placeholders: "{name} {brand} tasting notes review"',
    )

    # What fields this search targets
    target_fields = models.JSONField(
        default=list,
        help_text='Fields this enriches: ["nose_description", "palate_description"]',
    )

    # Priority and status
    priority = models.IntegerField(
        default=5,
        help_text="1-10, higher priority = search first when fields missing",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this enrichment template",
    )

    class Meta:
        db_table = "enrichment_config"
        ordering = ["-priority"]
        verbose_name = "Enrichment Configuration"
        verbose_name_plural = "Enrichment Configurations"

    def __str__(self):
        return f"{self.template_name} ({self.product_type_config.product_type})"


class PipelineConfig(models.Model):
    """
    V3 Architecture: Pipeline configuration for a product type.

    Stores product-type specific pipeline settings including:
    - Search budget (max_serpapi_searches, max_sources_per_product)
    - Awards search settings
    - Members-only site detection settings
    - Status thresholds (JSON for flexibility)
    - ECP (Enrichment Completion Percentage) settings

    Spec Reference: ENRICHMENT_PIPELINE_V3_SPEC.md Section 6.1
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product_type_config = models.OneToOneField(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name="pipeline_config",
        help_text="Product type this pipeline config applies to",
    )

    # ============================================
    # Search Budget (V3 increased defaults)
    # ============================================

    max_serpapi_searches = models.IntegerField(
        default=6,
        help_text="Maximum SerpAPI searches per product (V3: increased from 3)",
    )
    max_sources_per_product = models.IntegerField(
        default=8,
        help_text="Maximum sources to fetch per product (V3: increased from 5)",
    )
    max_enrichment_time_seconds = models.IntegerField(
        default=180,
        help_text="Maximum enrichment time in seconds (V3: increased from 120)",
    )

    # ============================================
    # Awards Search (always runs per V3 spec)
    # ============================================

    awards_search_enabled = models.BooleanField(
        default=True,
        help_text="Enable dedicated awards search (Step 4 in V3 pipeline)",
    )
    awards_search_template = models.CharField(
        max_length=500,
        default="{name} {brand} awards medals competition winner",
        help_text="Search template for awards discovery",
    )

    # ============================================
    # Members-Only Site Detection (V3 feature)
    # ============================================

    members_only_detection_enabled = models.BooleanField(
        default=True,
        help_text="Enable content analysis for members-only/paywall sites",
    )
    members_only_patterns = models.JSONField(
        default=list,
        help_text="Regex patterns to detect members-only sites (login forms, paywalls)",
    )

    # ============================================
    # Status Thresholds (V3 JSON structure)
    # ============================================

    status_thresholds = models.JSONField(
        default=dict,
        help_text="Status requirements per level (skeleton, partial, baseline, enriched, complete)",
    )

    # ============================================
    # ECP (Enrichment Completion Percentage) Settings
    # ============================================

    ecp_complete_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=90.0,
        help_text="ECP percentage required for COMPLETE status (V3 default: 90%)",
    )

    # ============================================
    # Timestamps
    # ============================================

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pipeline_config"
        verbose_name = "Pipeline Configuration"
        verbose_name_plural = "Pipeline Configurations"

    def __str__(self):
        return f"Pipeline Config for {self.product_type_config.product_type}"


class FieldGroup(models.Model):
    """
    V3 Architecture: Field group definition for ECP calculation.

    Defines groups of fields for Enrichment Completion Percentage (ECP)
    calculation. Each group has a key, display name, and list of fields.

    Groups are product-type specific and used to track enrichment progress
    by category (e.g., tasting_nose, cask_info, whiskey_details).

    Spec Reference: ENRICHMENT_PIPELINE_V3_SPEC.md Section 6.2
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product_type_config = models.ForeignKey(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name="field_groups",
        help_text="Product type this field group belongs to",
    )

    # Group identity
    group_key = models.CharField(
        max_length=50,
        help_text="Unique key for this group (e.g., 'tasting_nose', 'cask_info')",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable name for display",
    )

    # Fields in this group
    fields = models.JSONField(
        default=list,
        help_text="List of field names in this group",
    )

    # Ordering and status
    sort_order = models.IntegerField(
        default=0,
        help_text="Display order (lower = first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this field group",
    )

    class Meta:
        db_table = "field_group"
        ordering = ["sort_order"]
        unique_together = [["product_type_config", "group_key"]]
        verbose_name = "Field Group"
        verbose_name_plural = "Field Groups"

    def __str__(self):
        return f"{self.group_key} ({self.product_type_config.product_type})"


# ============================================================
# Unified Crawler Scheduling (replaces separate scheduling models)
# ============================================================


class ScheduleCategory(models.TextChoices):
    """Categories of crawl schedules."""

    COMPETITION = "competition", "Competition/Awards"
    DISCOVERY = "discovery", "Discovery Search"
    RETAILER = "retailer", "Retailer Monitoring"


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


class CrawlJob(models.Model):
    """
    Tracks individual crawl job executions.

    Created when a source crawl is initiated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Legacy: Link to CrawlerSource (for backward compatibility)
    source = models.ForeignKey(
        CrawlerSource, on_delete=models.CASCADE, related_name="crawl_jobs",
        null=True, blank=True,  # Made optional for unified scheduling
    )

    # New: Link to unified CrawlSchedule
    schedule = models.ForeignKey(
        "CrawlSchedule", on_delete=models.CASCADE, related_name="jobs",
        null=True, blank=True,  # Optional during transition
    )

    # Status
    status = models.CharField(
        max_length=20, choices=CrawlJobStatus.choices, default=CrawlJobStatus.PENDING
    )

    # Timing
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Metrics
    pages_crawled = models.IntegerField(default=0)
    products_found = models.IntegerField(default=0)
    products_new = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)

    # Auto-Queue Metrics
    links_discovered = models.IntegerField(default=0)
    links_queued = models.IntegerField(default=0)

    # Error Details
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)

    # Results
    results_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crawl_jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def __str__(self):
        name = self.schedule.name if self.schedule else (self.source.name if self.source else "Unknown")
        return f"Job {self.id} - {name} ({self.status})"

    @property
    def duration_seconds(self):
        """Calculate job duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def start(self):
        """Mark job as started."""
        self.status = CrawlJobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def complete(self, success: bool = True, error_message: str = None):
        """Mark job as completed or failed."""
        self.status = CrawlJobStatus.COMPLETED if success else CrawlJobStatus.FAILED
        self.completed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=["status", "completed_at", "error_message"])

        # Update source stats (legacy path)
        if self.source:
            self.source.last_crawl_status = self.status
            self.source.total_products_found += self.products_new
            self.source.update_next_crawl_time()


class CrawledURL(models.Model):
    """
    Tracks all URLs that have been crawled.

    Used for deduplication and incremental crawling.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=2000, unique=True, db_index=True)
    url_hash = models.CharField(max_length=64, unique=True, db_index=True)

    source = models.ForeignKey(
        CrawlerSource, on_delete=models.SET_NULL, null=True, related_name="crawled_urls"
    )

    # Status
    is_product_page = models.BooleanField(default=False)
    was_processed = models.BooleanField(default=False)
    processing_status = models.CharField(max_length=20, blank=True)

    # Timing
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    last_modified_at = models.DateTimeField(null=True, blank=True)

    # Content
    content_hash = models.CharField(max_length=64, blank=True)
    content_changed = models.BooleanField(default=False)

    class Meta:
        db_table = "crawled_urls"
        indexes = [
            models.Index(fields=["source", "is_product_page"]),
            models.Index(fields=["was_processed"]),
        ]

    def __str__(self):
        return self.url[:100]

    def save(self, *args, **kwargs):
        """Automatically compute URL hash before saving."""
        if not self.url_hash:
            self.url_hash = self.compute_url_hash(self.url)
        super().save(*args, **kwargs)

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """Compute SHA-256 hash of URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def update_content(self, content: str):
        """Update content hash and detect changes."""
        new_hash = self.compute_content_hash(content)
        self.content_changed = self.content_hash != new_hash
        self.content_hash = new_hash
        self.last_crawled_at = timezone.now()
        self.save(update_fields=["content_hash", "content_changed", "last_crawled_at"])


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
        CrawlJob, on_delete=models.SET_NULL, null=True, related_name="products"
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




    # Raw Data
    raw_content = models.TextField(help_text="Original HTML/text")
    raw_content_hash = models.CharField(max_length=64)

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

    # Task 2.3: Awards data for competition-discovered products
    awards = models.JSONField(
        default=list,
        blank=True,
        help_text="Competition awards data: [{'competition': 'IWSC', 'year': 2024, 'medal': 'Gold'}]",
    )

    # Phase 1: Model Expansion - New fields for comprehensive product data
    # REMOVED: taste_profile JSON blob per spec - use individual tasting profile columns instead

    # Product Images (JSONField)
    images = models.JSONField(
        default=list,
        blank=True,
        help_text="Product images: [{url, type, source, width, height}]",
    )

    # Ratings from various sources (JSONField)
    ratings = models.JSONField(
        default=list,
        blank=True,
        help_text="Ratings: [{source, score, max_score, reviewer, date, url}]",
    )

    # Press/Article Mentions (JSONField) - named press_mentions to avoid conflict with FK relation
    press_mentions = models.JSONField(
        default=list,
        blank=True,
        help_text="Article mentions: [{url, title, source, date, snippet, mention_type}]",
    )

    # Mention Count (IntegerField)
    mention_count = models.IntegerField(
        default=0,
        help_text="Total number of press/article mentions",
    )
    # Counter fields for related data tables
    award_count = models.IntegerField(
        default=0,
        help_text="Total number of awards for this product",
    )
    price_count = models.IntegerField(
        default=0,
        help_text="Total number of price observations",
    )
    rating_count = models.IntegerField(
        default=0,
        help_text="Total number of ratings",
    )


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

    # Price History (JSONField)
    price_history = models.JSONField(
        default=list,
        blank=True,
        help_text="Historical prices: [{price, currency, retailer, url, date}]",
    )

    # Current Best Price
    best_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Current best price found",
    )
    best_price_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency of best price",
    )
    best_price_retailer = models.CharField(
        max_length=255,
        blank=True,
        help_text="Retailer with best price",
    )
    best_price_url = models.URLField(
        max_length=2000,
        blank=True,
        help_text="URL to best price",
    )
    best_price_updated = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the best price was last updated",
    )

    # Matching
    matched_product_id = models.UUIDField(
        null=True, blank=True, help_text="ID of matched existing product"
    )
    match_confidence = models.FloatField(null=True, blank=True)

    # ============================================================
    # Task Group 20: Demand Signal & Market Positioning Fields
    # ============================================================

    # Demand Signal Fields
    trend_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Calculated popularity score (1-100)",
    )
    trend_direction = models.CharField(
        max_length=10,
        choices=TrendDirectionChoices.choices,
        blank=True,
        null=True,
        help_text="Trend direction: rising, stable, declining",
    )
    buzz_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Social media + press mention intensity (1-100)",
    )
    search_interest = models.IntegerField(
        blank=True,
        null=True,
        help_text="Google Trends search interest score",
    )
    is_limited_edition = models.BooleanField(
        default=False,
        help_text="Whether this is a limited edition release",
    )
    is_allocated = models.BooleanField(
        default=False,
        help_text="Whether distribution is allocated/restricted",
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

    # Market Positioning Fields
    price_tier = models.CharField(
        max_length=20,
        choices=PriceTierChoices.choices,
        blank=True,
        null=True,
        help_text="Price tier: budget, value, mid_range, premium, ultra_premium, luxury",
    )
    target_audience = models.CharField(
        max_length=20,
        choices=TargetAudienceChoices.choices,
        blank=True,
        null=True,
        help_text="Target audience: beginner, casual, enthusiast, collector, investor",
    )
    availability_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Availability score (1-10, 10=widely available, 1=extremely rare)",
    )

    # Aggregated Availability Fields
    retailer_count = models.IntegerField(
        default=0,
        help_text="Number of retailers carrying this product",
    )
    in_stock_count = models.IntegerField(
        default=0,
        help_text="Number of retailers with product in stock",
    )
    avg_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average price across retailers (USD)",
    )
    min_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Minimum price found (USD)",
    )
    max_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Maximum price found (USD)",
    )
    price_volatility = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price volatility metric (standard deviation)",
    )

    # ============================================================
    # Task Group 25: European Market Fields
    # ============================================================

    # EUR Pricing Fields
    primary_currency = models.CharField(
        max_length=3,
        default="EUR",
        help_text="Primary currency for this product (ISO 4217)",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Normalized price in EUR for comparison",
    )
    price_includes_vat = models.BooleanField(
        default=True,
        help_text="Whether price includes VAT (EU retail prices typically include VAT)",
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="VAT rate percentage (e.g., 19.00 for Germany)",
    )
    price_excl_vat = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price excluding VAT",
    )

    # Import/Availability Fields
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
    eu_available = models.BooleanField(
        default=False,
        help_text="Whether product is available in the EU market",
    )
    german_available = models.BooleanField(
        default=False,
        help_text="Whether product is available in the German market",
    )
    estimated_landed_cost_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated landed cost in EUR including duties and shipping",
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
    missing_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="List of missing field names for enrichment prioritization",
    )
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

    # ============================================================
    # Conflict Detection Fields
    # ============================================================

    has_conflicts = models.BooleanField(
        default=False,
        help_text="Whether this product has conflicting data from multiple sources",
    )
    conflict_details = models.JSONField(
        blank=True,
        null=True,
        help_text="Details of conflicting data: {'field': 'abv', 'values': [...]}",
    )

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
    members_only_sites_detected = models.JSONField(
        default=list,
        help_text="V3: URLs detected as members-only/paywall during enrichment",
    )
    awards_search_completed = models.BooleanField(
        default=False,
        help_text="V3: Whether dedicated awards search (Step 4) was performed",
    )

    # ============================================================
    # V3: Enrichment Source Tracking Fields
    # Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.6.2
    # ============================================================

    enrichment_sources_searched = models.JSONField(
        default=list,
        blank=True,
        help_text="V3: All URLs searched/attempted during enrichment",
    )

    enrichment_sources_used = models.JSONField(
        default=list,
        blank=True,
        help_text="V3: URLs that successfully contributed data during enrichment",
    )

    enrichment_sources_rejected = models.JSONField(
        default=list,
        blank=True,
        help_text="V3: URLs rejected during enrichment with reasons [{url, reason, timestamp}]",
    )

    field_provenance = models.JSONField(
        default=dict,
        blank=True,
        help_text="V3: Mapping of field_name -> source_url for audit trail",
    )

    enrichment_steps_completed = models.IntegerField(
        default=0,
        help_text="V3: Number of enrichment steps completed (0-2 for generic search)",
    )

    last_enrichment_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="V3: Timestamp of last enrichment attempt",
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
            models.Index(fields=["mention_count"]),
            # Task Group 20: Demand signal and market positioning indexes
            models.Index(fields=["trend_score"]),
            models.Index(fields=["price_tier"]),
            models.Index(fields=["availability_score"]),
            # Task Group 25: European market indexes
            models.Index(fields=["origin_region"]),
            models.Index(fields=["german_available"]),
            models.Index(fields=["german_market_fit"]),
        ]

    def __str__(self):
        return f"{self.name or 'Unknown'} ({self.product_type})"

    def save(self, *args, **kwargs):
        """Automatically compute fingerprint, content hash, completeness and status before saving."""
        if not self.raw_content_hash and self.raw_content:
            self.raw_content_hash = hashlib.sha256(self.raw_content.encode()).hexdigest()
        if not self.fingerprint and self.name:
            self.fingerprint = self.compute_fingerprint_from_fields()

        # Auto-update completeness score and status (unless explicitly skipped)
        skip_status_update = kwargs.pop("skip_status_update", False)
        if not skip_status_update:
            # Avoid infinite recursion by checking if we're updating specific fields
            update_fields = kwargs.get("update_fields")
            if update_fields is None or "completeness_score" not in update_fields:
                self.completeness_score = self.calculate_completeness_score()
                # Don't override rejected/merged/skeleton status
                if self.status not in (
                    DiscoveredProductStatus.REJECTED,
                    DiscoveredProductStatus.MERGED,
                    DiscoveredProductStatus.SKELETON,
                ):
                    self.status = self.determine_status()

        super().save(*args, **kwargs)

    def compute_fingerprint_from_fields(self) -> str:
        """Compute fingerprint for deduplication based on model fields."""
        # Use key identifying fields from model columns (not JSON blobs)
        brand_name = self.brand.name if self.brand else ""
        key_fields = {
            "name": str(self.name or "").lower().strip(),
            "brand": str(brand_name).lower().strip(),
            "product_type": self.product_type or "",
            "volume_ml": self.volume_ml,
            "abv": float(self.abv) if self.abv else None,
        }

        # Add type-specific fields
        if self.product_type == "whiskey":
            key_fields["age_statement"] = self.age_statement
            # Get distillery from WhiskeyDetails if exists
            if hasattr(self, 'whiskey_details') and self.whiskey_details:
                key_fields["distillery"] = str(self.whiskey_details.distillery or "").lower()
        elif self.product_type == "port_wine":
            # Get style and harvest_year from PortWineDetails if exists
            if hasattr(self, 'port_details') and self.port_details:
                key_fields["style"] = str(self.port_details.style or "").lower()
                key_fields["harvest_year"] = self.port_details.harvest_year

        fingerprint_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    @staticmethod
    def compute_fingerprint(data: dict) -> str:
        """Compute fingerprint from a dict (for compatibility during migration)."""
        key_fields = {
            "name": str(data.get("name", "")).lower().strip(),
            "brand": str(data.get("brand", "")).lower().strip(),
            "product_type": data.get("product_type", ""),
            "volume_ml": data.get("volume_ml"),
            "abv": data.get("abv"),
        }

        product_type = data.get("product_type", "")
        if product_type == "whiskey":
            key_fields["age_statement"] = data.get("age_statement")
            key_fields["distillery"] = str(data.get("distillery", "")).lower()
        elif product_type == "port_wine":
            key_fields["style"] = str(data.get("style", "")).lower()
            key_fields["harvest_year"] = data.get("harvest_year")

        fingerprint_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

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
        """Add an article/press mention and update count."""
        if self.press_mentions is None:
            self.press_mentions = []
        # Check for duplicate by URL
        existing_urls = [m.get("url") for m in self.press_mentions]
        if mention.get("url") not in existing_urls:
            self.press_mentions.append(mention)
            self.mention_count = len(self.press_mentions)
            self.save(update_fields=["press_mentions", "mention_count"])

    def add_rating(self, rating: dict) -> None:
        """Add a rating if not already present from same source."""
        if self.ratings is None:
            self.ratings = []
        existing_sources = [r.get("source") for r in self.ratings]
        if rating.get("source") not in existing_sources:
            self.ratings.append(rating)
            self.save(update_fields=["ratings"])

    def update_best_price(self, price: float, currency: str, retailer: str, url: str) -> None:
        """Update best price if this is lower than current."""
        price_decimal = Decimal(str(price))
        if self.best_price is None or price_decimal < self.best_price:
            self.best_price = price_decimal
            self.best_price_currency = currency
            self.best_price_retailer = retailer
            self.best_price_url = url
            self.save(update_fields=[
                "best_price",
                "best_price_currency",
                "best_price_retailer",
                "best_price_url",
            ])

    def add_image(self, image: dict) -> None:
        """Add an image if URL not already present."""
        if self.images is None:
            self.images = []
        existing_urls = [i.get("url") for i in self.images]
        if image.get("url") not in existing_urls:
            self.images.append(image)
            self.save(update_fields=["images"])

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
        # ============================================================

        # Pricing (5 points)
        if self.best_price:
            score += 5

        # Images (5 points)
        if self.images and len(self.images) > 0:
            score += 5

        # Ratings (5 points)
        if self.ratings and len(self.ratings) > 0:
            score += 5

        # Awards (5 points)
        if self.awards and len(self.awards) > 0:
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

    def determine_status(self) -> str:
        """
        Determine product status based on completeness and tasting data.

        Key rule: COMPLETE/VERIFIED requires palate tasting profile.

        Returns one of: incomplete, partial, complete, verified, rejected, merged
        """
        # Don't change rejected/merged status
        if self.status in (
            DiscoveredProductStatus.REJECTED,
            DiscoveredProductStatus.MERGED,
        ):
            return self.status

        score = self.completeness_score or self.calculate_completeness_score()
        has_palate = self.has_palate_data()

        # Cannot be COMPLETE or VERIFIED without palate data
        if not has_palate:
            if score >= 30:
                return DiscoveredProductStatus.PARTIAL
            return DiscoveredProductStatus.INCOMPLETE

        # With palate data, status based on score
        if score >= 80:
            return DiscoveredProductStatus.VERIFIED
        elif score >= 60:
            return DiscoveredProductStatus.COMPLETE
        elif score >= 30:
            return DiscoveredProductStatus.PARTIAL
        else:
            return DiscoveredProductStatus.INCOMPLETE

    def update_completeness(self, save: bool = True) -> None:
        """
        Recalculate completeness score and update status.

        Args:
            save: If True, saves the model after updating
        """
        self.completeness_score = self.calculate_completeness_score()
        self.status = self.determine_status()

        if save:
            self.save(update_fields=["completeness_score", "status"])

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
        CrawlJob,
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
# Task Group 6: CrawledSource Model
# ============================================================


class CrawledSource(models.Model):
    """
    Task Group 6: Stores crawled article/page data.

    Stores metadata and raw content for crawled pages, enabling
    deduplication, extraction tracking, and Wayback Machine archival.

    Key features:
    - URL uniqueness enforcement
    - Content hash for deduplication
    - Extraction status tracking
    - Wayback Machine URL storage
    - Crawl attempt tracking
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identification
    url = models.URLField(
        max_length=2000,
        unique=True,
        db_index=True,
        help_text="URL of the crawled page (unique)",
    )
    title = models.CharField(
        max_length=500,
        help_text="Title of the crawled page",
    )

    # Deduplication
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of raw content for deduplication",
    )

    # Relationships
    discovery_source = models.ForeignKey(
        DiscoverySourceConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawled_sources",
        help_text="Discovery source this page came from (optional)",
    )

    # Classification
    source_type = models.CharField(
        max_length=30,
        choices=CrawledSourceTypeChoices.choices,
        help_text="Type of crawled page: award_page, review_article, etc.",
    )

    # Processing
    extraction_status = models.CharField(
        max_length=20,
        choices=ExtractionStatusChoices.choices,
        default=ExtractionStatusChoices.PENDING,
        help_text="Processing status: pending, processed, failed, needs_review",
    )

    # Raw Content
    raw_content = models.TextField(
        blank=True,
        null=True,
        help_text="Raw HTML content of the page",
    )
    raw_content_cleared = models.BooleanField(
        default=False,
        help_text="Whether raw content has been cleared after processing",
    )

    # Preprocessed Content (V2 Architecture)
    preprocessed_content = models.TextField(
        blank=True,
        null=True,
        help_text="Preprocessed/cleaned content for AI extraction (93% token savings)",
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

    # Wayback Machine
    wayback_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Wayback Machine archive URL",
    )
    wayback_saved_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the page was saved to Wayback Machine",
    )
    wayback_status = models.CharField(
        max_length=20,
        choices=WaybackStatusChoices.choices,
        default=WaybackStatusChoices.PENDING,
        help_text="Wayback archival status: pending, saved, failed, not_applicable",
    )

    # Crawl Tracking
    crawl_attempts = models.IntegerField(
        default=0,
        help_text="Number of crawl attempts for this URL",
    )
    last_crawl_error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message from last failed crawl attempt",
    )
    crawl_strategy_used = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Crawl strategy used for successful crawl",
    )
    detected_obstacles = models.JSONField(
        blank=True,
        null=True,
        help_text="Obstacles detected during crawling",
    )

    # Timestamps
    crawled_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this page was crawled",
    )

    class Meta:
        db_table = "crawled_source"
        ordering = ["-crawled_at"]
        indexes = [
            # Index for URL uniqueness and lookup
            models.Index(fields=["url"]),
            # Index for content_hash dedup queries
            models.Index(fields=["content_hash"]),
            # Index for batch processing (status + crawled_at)
            models.Index(fields=["extraction_status", "crawled_at"]),
            # Index for per-source queries
            models.Index(fields=["discovery_source", "crawled_at"]),
            # Index for Wayback job processing
            models.Index(fields=["wayback_status"]),
        ]
        verbose_name = "Crawled Source"
        verbose_name_plural = "Crawled Sources"

    def __str__(self):
        return f"{self.title[:50]}... ({self.extraction_status})"

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()


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
# Task Group 3: Spirit-Type Extension Models
# ============================================================


class WhiskeyDetails(models.Model):
    """
    Task Group 3: Extended details for whiskey products.

    OneToOne relationship with DiscoveredProduct for whiskey-specific fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # OneToOne relationship
    product = models.OneToOneField(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='whiskey_details',
        help_text="The product these details belong to",
    )

    # Classification (REMOVED: whiskey_country, whiskey_region - use DiscoveredProduct.country/region)
    whiskey_type = models.CharField(
        max_length=30,
        choices=WhiskeyTypeChoices.choices,
        help_text="Type of whiskey",
    )

    # Production
    distillery = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
        help_text="Distillery name - indexed per spec",
    )
    mash_bill = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Grain composition",
    )

    # Cask Information (REMOVED: cask_type, cask_finish - use DiscoveredProduct.primary_cask/finishing_cask)
    cask_strength = models.BooleanField(
        default=False,
        help_text="Whether this is a cask strength release",
    )
    single_cask = models.BooleanField(
        default=False,
        help_text="Whether this is from a single cask",
    )
    cask_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Cask number for single cask releases",
    )

    # Vintage/Batch Info
    vintage_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of distillation",
    )
    bottling_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of bottling",
    )
    batch_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Batch number",
    )

    # Peat
    peated = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether this whiskey is peated",
    )
    peat_level = models.CharField(
        max_length=20,
        choices=PeatLevelChoices.choices,
        blank=True,
        null=True,
        help_text="Level of peat: unpeated, lightly, heavily",
    )
    peat_ppm = models.IntegerField(
        blank=True,
        null=True,
        help_text="Phenol PPM measurement for peat level",
    )

    # Production Methods (spec uses positive naming)
    natural_color = models.BooleanField(
        blank=True,
        null=True,
        help_text="No E150a color added (True = natural color)",
    )
    non_chill_filtered = models.BooleanField(
        blank=True,
        null=True,
        help_text="Non-chill filtered (True = NCF)",
    )

    class Meta:
        db_table = "whiskey_details"
        verbose_name = "Whiskey Details"
        verbose_name_plural = "Whiskey Details"

    def __str__(self):
        return f"Whiskey Details for {self.product}"


class PortWineDetails(models.Model):
    """
    Task Group 3: Extended details for port wine products.

    OneToOne relationship with DiscoveredProduct for port-specific fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # OneToOne relationship
    product = models.OneToOneField(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='port_details',
        help_text="The product these details belong to",
    )

    # Style
    style = models.CharField(
        max_length=30,
        choices=PortStyleChoices.choices,
        help_text="Port wine style: ruby, tawny, vintage, LBV, etc.",
    )
    indication_age = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Age indication (e.g., '20 Year', '10 Year')",
    )

    # Vintage Information
    harvest_year = models.IntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Year of harvest/vintage - indexed per spec",
    )
    bottling_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of bottling",
    )

    # Production
    grape_varieties = models.JSONField(
        default=list,
        blank=True,
        help_text="Grape varieties used",
    )
    quinta = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Quinta (estate) name",
    )
    douro_subregion = models.CharField(
        max_length=20,
        choices=DouroSubregionChoices.choices,
        blank=True,
        null=True,
        help_text="Douro subregion",
    )
    producer_house = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Port house/producer name - indexed per spec",
    )

    # Aging
    aging_vessel = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Type of vessel used for aging",
    )

    # Serving
    decanting_required = models.BooleanField(
        default=False,
        help_text="Whether decanting is recommended",
    )
    drinking_window = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Optimal drinking window (e.g., '2025-2060')",
    )

    class Meta:
        db_table = "port_wine_details"
        verbose_name = "Port Wine Details"
        verbose_name_plural = "Port Wine Details"

    def __str__(self):
        return f"Port Details for {self.product}"


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
    Task Group 7: Junction table linking products to crawled sources.

    Tracks which CrawledSource contributed to which DiscoveredProduct
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
        CrawledSource,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="The source that mentioned this product",
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
    Task Group 7: Junction table linking brands to crawled sources.

    Tracks which CrawledSource mentioned which DiscoveredBrand.
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
        CrawledSource,
        on_delete=models.CASCADE,
        related_name='brands',
        help_text="The source that mentioned this brand",
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

    Tracks which source contributed each field value to a product,
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
        CrawledSource,
        on_delete=models.CASCADE,
        related_name='field_extractions',
        help_text="The source that provided this field value",
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
        CrawledSource,
        on_delete=models.CASCADE,
        related_name='product_candidates',
        help_text="Source this candidate was extracted from",
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


class DiscoveryJobStatus(models.TextChoices):
    """Status of a discovery job."""

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


# ScheduleFrequency moved to line ~713 as part of unified scheduling


class DiscoveryResultStatus(models.TextChoices):
    """Status of a discovery result."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    DUPLICATE = "duplicate", "Duplicate"


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
# Old DiscoverySchedule was here from lines 4972-5133


class DiscoveryJob(models.Model):
    """
    Tracks execution of a discovery job.

    A job represents a single run of the discovery process, which:
    1. Processes multiple search terms
    2. Crawls search results
    3. Extracts and saves products
    4. Tracks metrics and errors

    Note: This is used internally by DiscoveryOrchestrator.
    For scheduled jobs, see CrawlJob with CrawlSchedule.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to unified CrawlSchedule (optional - replaces old DiscoverySchedule FK)
    crawl_schedule = models.ForeignKey(
        "CrawlSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_jobs",
        help_text="The unified schedule that triggered this job, if any.",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=DiscoveryJobStatus.choices,
        default=DiscoveryJobStatus.PENDING,
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    # Metrics - Search Terms
    search_terms_total = models.IntegerField(
        default=0,
        help_text="Total search terms to process.",
    )
    search_terms_processed = models.IntegerField(
        default=0,
        help_text="Search terms processed so far.",
    )

    # Metrics - URLs
    urls_found = models.IntegerField(
        default=0,
        help_text="Total URLs found in search results.",
    )
    urls_crawled = models.IntegerField(
        default=0,
        help_text="URLs successfully crawled.",
    )
    urls_skipped = models.IntegerField(
        default=0,
        help_text="URLs skipped (duplicates, blocked domains, etc.).",
    )

    # Metrics - Products
    products_found = models.IntegerField(
        default=0,
        help_text="Total products identified.",
    )
    products_new = models.IntegerField(
        default=0,
        help_text="New products added to database.",
    )
    products_updated = models.IntegerField(
        default=0,
        help_text="Existing products updated.",
    )
    products_duplicates = models.IntegerField(
        default=0,
        help_text="Products skipped as duplicates.",
    )
    products_failed = models.IntegerField(
        default=0,
        help_text="Products that failed extraction.",
    )

    # Metrics - Review
    products_needs_review = models.IntegerField(
        default=0,
        help_text="Products flagged for human review.",
    )

    # Quota Tracking
    serpapi_calls_used = models.IntegerField(
        default=0,
        help_text="Number of SerpAPI calls made.",
    )
    scrapingbee_calls_used = models.IntegerField(
        default=0,
        help_text="Number of ScrapingBee calls made.",
    )
    ai_calls_used = models.IntegerField(
        default=0,
        help_text="Number of AI Enhancement calls made.",
    )

    # Error Tracking
    error_count = models.IntegerField(
        default=0,
        help_text="Number of errors encountered.",
    )
    error_log = models.TextField(
        blank=True,
        help_text="Detailed error log.",
    )

    class Meta:
        db_table = "discovery_job"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["crawl_schedule", "started_at"]),
        ]
        verbose_name = "Discovery Job"
        verbose_name_plural = "Discovery Jobs"

    def __str__(self):
        return f"Job {self.id} ({self.status}) - {self.products_new} new products"

    @property
    def duration_seconds(self) -> int:
        """Get job duration in seconds."""
        if self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return int((timezone.now() - self.started_at).total_seconds())

    @property
    def success_rate(self) -> float:
        """Get product extraction success rate."""
        total = self.products_new + self.products_failed
        if total == 0:
            return 0.0
        return self.products_new / total

    def log_error(self, error: str):
        """Append an error to the error log."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.error_log:
            self.error_log += f"\n[{timestamp}] {error}"
        else:
            self.error_log = f"[{timestamp}] {error}"
        self.error_count += 1


class DiscoveryResult(models.Model):
    """
    Individual result from a discovery job.

    Each result represents one URL that was found and processed,
    tracking whether it led to a new product, duplicate, or failure.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    job = models.ForeignKey(
        DiscoveryJob,
        on_delete=models.CASCADE,
        related_name="results",
        help_text="The job this result belongs to.",
    )
    search_term = models.ForeignKey(
        SearchTerm,
        on_delete=models.SET_NULL,
        null=True,
        related_name="results",
        help_text="The search term that found this result.",
    )
    product = models.ForeignKey(
        DiscoveredProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_results",
        help_text="The product discovered, if any.",
    )

    # Source Information
    source_url = models.URLField(
        help_text="URL that was crawled.",
    )
    source_domain = models.CharField(
        max_length=100,
        help_text="Domain of the source URL.",
    )
    source_title = models.CharField(
        max_length=500,
        blank=True,
        help_text="Title from search results.",
    )
    search_rank = models.IntegerField(
        help_text="Position in search results (1 = first).",
    )

    # Product Information
    product_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of product found, if any.",
    )
    is_new_product = models.BooleanField(
        default=False,
        help_text="Whether this was a new product.",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=DiscoveryResultStatus.choices,
        default=DiscoveryResultStatus.PENDING,
        help_text="Current status of this result.",
    )

    # Status Flags (legacy, kept for detailed tracking)
    crawl_success = models.BooleanField(
        default=False,
        help_text="Whether the URL was successfully crawled.",
    )
    extraction_success = models.BooleanField(
        default=False,
        help_text="Whether product extraction succeeded.",
    )
    is_duplicate = models.BooleanField(
        default=False,
        help_text="Whether this was identified as a duplicate.",
    )
    needs_review = models.BooleanField(
        default=False,
        help_text="Whether this needs human review.",
    )

    # Error Information
    error_message = models.TextField(
        blank=True,
        help_text="Error message if crawl/extraction failed.",
    )

    # Extracted Data (from SmartCrawler)
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw extracted product data from SmartCrawler.",
    )

    # SmartCrawler Details
    final_source_url = models.URLField(
        blank=True,
        null=True,
        help_text="Final URL used after SmartCrawler fallback.",
    )
    source_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Source type: primary, official_brand, trusted_retailer, other.",
    )
    name_match_score = models.FloatField(
        default=0.0,
        help_text="Name similarity score from SmartCrawler.",
    )

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "discovery_result"
        ordering = ["job", "search_rank"]
        indexes = [
            models.Index(fields=["job", "is_new_product"]),
            models.Index(fields=["source_domain"]),
            models.Index(fields=["needs_review"]),
        ]
        verbose_name = "Discovery Result"
        verbose_name_plural = "Discovery Results"

    def __str__(self):
        status = "NEW" if self.is_new_product else ("DUP" if self.is_duplicate else "FAIL")
        return f"[{status}] {self.product_name or self.source_url[:50]}"


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
