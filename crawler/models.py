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
from django.db import models
from django.utils import timezone


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
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Internal notes")

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
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

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

    # Task 2.3: Discovery source tracking
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

    # Matching
    matched_product_id = models.UUIDField(
        null=True, blank=True, help_text="ID of matched existing product"
    )
    match_confidence = models.FloatField(null=True, blank=True)

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
            models.Index(fields=["discovery_source"]),
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
        related_name="article_mentions",
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
