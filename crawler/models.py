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
    """Status of a discovered product."""

    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    DUPLICATE = "duplicate", "Duplicate"
    MERGED = "merged", "Merged"
    # Task 2.3: Added skeleton status for competition-discovered products
    SKELETON = "skeleton", "Skeleton (needs enrichment)"


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
    """

    AWARD_PAGE = "award_page", "Award Page"
    REVIEW_ARTICLE = "review_article", "Review Article"
    RETAILER_PAGE = "retailer_page", "Retailer Page"
    DISTILLERY_PAGE = "distillery_page", "Distillery Page"
    NEWS_ARTICLE = "news_article", "News Article"


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
    source = models.ForeignKey(
        CrawlerSource, on_delete=models.CASCADE, related_name="crawl_jobs"
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
        return f"Job {self.id} - {self.source.name} ({self.status})"

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

        # Update source stats
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
        max_length=64, db_index=True, help_text="Hash for deduplication"
    )
    product_type = models.CharField(max_length=20, choices=ProductType.choices)
    # Product Basic Info (denormalized from extracted_data for querying)
    name = models.CharField(
        max_length=500,
        blank=True,
        help_text="Product name (denormalized)",
    )
    abv = models.FloatField(
        blank=True,
        null=True,
        help_text="Alcohol by volume percentage",
    )
    age_statement = models.IntegerField(
        blank=True,
        null=True,
        help_text="Age statement in years",
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
        help_text="Product region (e.g., Speyside, Kentucky)",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
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

    # Extracted Data (from AI Enhancement Service)
    extracted_data = models.JSONField(default=dict)
    enriched_data = models.JSONField(default=dict)
    extraction_confidence = models.FloatField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=DiscoveredProductStatus.choices,
        default=DiscoveredProductStatus.PENDING,
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

    # Taste Profile (JSONField)
    taste_profile = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tasting notes: nose, palate, finish, flavor_tags, overall_notes",
    )

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
        name = self.extracted_data.get("name", "Unknown")
        return f"{name} ({self.product_type})"

    def save(self, *args, **kwargs):
        """Automatically compute fingerprint and content hash before saving."""
        if not self.raw_content_hash and self.raw_content:
            self.raw_content_hash = hashlib.sha256(self.raw_content.encode()).hexdigest()
        if not self.fingerprint and self.extracted_data:
            self.fingerprint = self.compute_fingerprint(self.extracted_data)
        super().save(*args, **kwargs)

    @staticmethod
    def compute_fingerprint(extracted_data: dict) -> str:
        """Compute fingerprint for deduplication based on key fields."""
        # Use key identifying fields
        key_fields = {
            "name": str(extracted_data.get("name", "")).lower().strip(),
            "brand": str(extracted_data.get("brand", "")).lower().strip(),
            "product_type": extracted_data.get("product_type", ""),
            "volume_ml": extracted_data.get("volume_ml"),
            "abv": extracted_data.get("abv"),
        }

        # Add type-specific fields
        product_type = extracted_data.get("product_type", "")
        if product_type == "whiskey":
            key_fields["age_statement"] = extracted_data.get("age_statement")
            key_fields["distillery"] = str(extracted_data.get("distillery", "")).lower()
        elif product_type == "port_wine":
            key_fields["style"] = str(extracted_data.get("style", "")).lower()
            key_fields["harvest_year"] = extracted_data.get("harvest_year")

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
        """Merge taste profile data."""
        current = self.taste_profile or {}

        # Merge array fields (nose, palate, finish, flavor_tags)
        for key in ["nose", "palate", "finish", "flavor_tags"]:
            if key in profile:
                existing = set(current.get(key, []))
                new = set(profile.get(key, []))
                current[key] = list(existing | new)

        # Set overall_notes only if not already set
        if "overall_notes" in profile and not current.get("overall_notes"):
            current["overall_notes"] = profile["overall_notes"]

        self.taste_profile = current
        self.save(update_fields=["taste_profile"])


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
            # Using nulls_distinct=False to treat NULL values as equal for uniqueness
            models.UniqueConstraint(
                fields=["product_type", "sub_category", "region", "country"],
                name="unique_category_insight",
                nulls_distinct=False,
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

    # Classification
    whiskey_type = models.CharField(
        max_length=30,
        choices=WhiskeyTypeChoices.choices,
        help_text="Type of whiskey",
    )
    whiskey_country = models.CharField(
        max_length=100,
        help_text="Country of origin",
    )
    whiskey_region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Region within country (e.g., Speyside, Kentucky)",
    )

    # Production
    distillery = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Distillery name",
    )
    mash_bill = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Grain composition",
    )

    # Cask Information
    cask_type = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Primary cask type used",
    )
    cask_finish = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Finishing cask if any",
    )
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
        help_text="Level of peat",
    )

    # Production Methods
    chill_filtered = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether chill filtration was used",
    )
    color_added = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether color (E150a) was added",
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
        max_length=20,
        choices=PortStyleChoices.choices,
        help_text="Port wine style",
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
        help_text="Year of harvest/vintage",
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
        help_text="Port house/producer name",
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
# Task Group 15: CrawlSchedule Model
# ============================================================


class CrawlSchedule(models.Model):
    """
    Task Group 15: Crawl scheduling with adaptive backoff.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source
    source = models.ForeignKey(
        DiscoverySourceConfig,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Discovery source this schedule is for",
    )

    # Timing
    next_run = models.DateTimeField(
        help_text="When the next crawl should run",
    )
    last_run = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the last crawl ran",
    )
    last_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Status of the last crawl",
    )

    # Backoff
    consecutive_errors = models.IntegerField(
        default=0,
        help_text="Number of consecutive errors",
    )
    current_backoff_hours = models.IntegerField(
        default=0,
        help_text="Current backoff in hours",
    )

    # Priority
    priority_boost = models.IntegerField(
        default=0,
        help_text="Priority boost for this schedule",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schedule is active",
    )

    class Meta:
        db_table = "crawl_schedule"
        ordering = ["next_run"]
        indexes = [
            models.Index(fields=["next_run", "is_active"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Crawl Schedule"
        verbose_name_plural = "Crawl Schedules"

    def __str__(self):
        return f"Schedule for {self.source} - Next: {self.next_run}"


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
