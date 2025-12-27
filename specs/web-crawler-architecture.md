# Web Crawler Architecture Specification

> Version: 1.0.0
> Created: 2025-12-27
> Status: Approved for Implementation
> Author: AI Enhancement Engine Team

## Executive Summary

This document specifies the architecture for a state-of-the-art web crawler system designed to build the most comprehensive whiskey and port wine information database. The crawler integrates with the existing AI Enhancement Service to provide automated product discovery, extraction, and enrichment.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack Evaluation](#2-technology-stack-evaluation)
3. [3rd-Party Services Analysis](#3-3rd-party-services-analysis)
4. [Database Models](#4-database-models)
5. [Pipeline Architecture](#5-pipeline-architecture)
6. [Source Configuration](#6-source-configuration)
7. [Keyword Management](#7-keyword-management)
8. [Scalability Considerations](#8-scalability-considerations)
9. [Cost Estimates](#9-cost-estimates)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Architecture Overview

### 1.1 System Context Diagram

```
+---------------------------------------------------------------------+
|                        EXTERNAL WORLD                                |
|  +------------------+  +------------------+  +------------------+    |
|  | Whiskey Sources  |  | Port Wine Sources|  | Pricing Sources  |    |
|  | - Review Sites   |  | - Review Sites   |  | - DACH Retailers |    |
|  | - Competitions   |  | - Producers      |  | - International  |    |
|  | - News           |  | - Competitions   |  |                  |    |
|  +--------+---------+  +--------+---------+  +--------+---------+    |
+-----------|----------------------|----------------------|------------+
            |                      |                      |
            v                      v                      v
+---------------------------------------------------------------------+
|                      WEB CRAWLER LAYER                               |
|                                                                      |
|  +----------------+  +------------------+  +--------------------+    |
|  | URL Frontier   |  | Content Fetcher  |  | Rate Limiter       |    |
|  | (Redis Queue)  |  | (httpx/Playwright)|  | (per-domain)       |    |
|  +-------+--------+  +--------+---------+  +---------+----------+    |
|          |                    |                      |               |
|          v                    v                      v               |
|  +----------------+  +------------------+  +--------------------+    |
|  | Robots.txt     |  | Content Parser   |  | Proxy Rotator      |    |
|  | Compliance     |  | (BeautifulSoup)  |  | (optional)         |    |
|  +----------------+  +--------+---------+  +--------------------+    |
+-------------------------------|--------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
|                   AI ENHANCEMENT SERVICE                             |
|                                                                      |
|  POST /api/v1/enhance/from-crawler/                                  |
|  - Type Detection -> Extraction -> Enrichment                        |
|                                                                      |
+-------------------------------|--------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
|                   PRODUCT PROCESSING                                 |
|                                                                      |
|  +------------------+  +------------------+  +------------------+    |
|  | Deduplication    |  | Product Matcher  |  | Storage Layer    |    |
|  | (fingerprinting) |  | (fuzzy matching) |  | (PostgreSQL)     |    |
|  +------------------+  +------------------+  +------------------+    |
+---------------------------------------------------------------------+
```

### 1.2 Design Principles

1. **Database-Driven Configuration**: All sources and keywords managed via Django Admin
2. **Polite Crawling**: Strict robots.txt compliance and rate limiting
3. **Ethical Scraping**: Respect ToS, implement reasonable delays
4. **Resilient Architecture**: Graceful degradation, retry policies, circuit breakers
5. **Observable System**: Comprehensive logging, metrics, and alerting
6. **Cost-Effective**: Minimize 3rd-party API calls, cache aggressively

### 1.3 Deployment Architecture

```
+-------------------------------------------------------------------------+
|                        HETZNER VPS (CCX33)                               |
|  +------------------------------------------------------------------+   |
|  |                         Docker Compose                            |   |
|  |                                                                   |   |
|  |  +-------------+  +-------------+  +-------------+  +-----------+ |   |
|  |  | Django API  |  | Celery      |  | Celery Beat |  | Redis     | |   |
|  |  | (gunicorn)  |  | Workers (4) |  | (scheduler) |  | (broker)  | |   |
|  |  +-------------+  +-------------+  +-------------+  +-----------+ |   |
|  |                                                                   |   |
|  |  +---------------------------+  +----------------------------+   |   |
|  |  | PostgreSQL                |  | Playwright (headless)      |   |   |
|  |  | (web_crawler_db)          |  | (for JS-rendered content)  |   |   |
|  |  +---------------------------+  +----------------------------+   |   |
|  +------------------------------------------------------------------+   |
+-------------------------------------------------------------------------+
```

---

## 2. Technology Stack Evaluation

### 2.1 Crawler Frameworks Comparison

| Framework | Type | Pros | Cons | Verdict |
|-----------|------|------|------|---------|
| **Scrapy** | Python | Mature, async, middleware system, wide adoption | Steep learning curve, complex for simple cases | Good for scale |
| **Crawlee** | Node.js | Modern, auto-scaling, browser integration | Not Python ecosystem | Not recommended |
| **httpx + asyncio** | Python | Lightweight, async, easy integration | Manual queue management | **Recommended** |
| **Apache Nutch** | Java | Enterprise-scale, distributed | Overkill, Java ecosystem | Not recommended |
| **StormCrawler** | Java | Real-time, Elasticsearch native | Java ecosystem, complex | Not recommended |

**Recommendation**: Use **httpx + asyncio** for simplicity and Django integration, with optional Scrapy for complex sites.

### 2.2 Headless Browser Solutions

| Solution | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Playwright** | Multi-browser, modern API, Python support | Heavy resource usage | **Recommended** |
| **Puppeteer** | Chrome-focused, mature | Node.js only | Not recommended |
| **Selenium** | Wide browser support | Slow, outdated | Not recommended |

**Recommendation**: Use **Playwright** for JavaScript-rendered content.

### 2.3 Content Parsing Libraries

| Library | Use Case | Recommendation |
|---------|----------|----------------|
| **BeautifulSoup4** | HTML parsing | **Recommended** |
| **lxml** | Fast XML/HTML parsing | Use with BeautifulSoup |
| **Readability** | Article extraction | For news content |
| **trafilatura** | Web text extraction | For clean text |

### 2.4 Selected Technology Stack

```python
# requirements.txt additions for crawler
httpx[http2]==0.27.0        # Async HTTP client with HTTP/2
beautifulsoup4==4.12.3      # HTML parsing
lxml==5.1.0                 # Fast parser backend
playwright==1.40.0          # Headless browser
robotsparser==0.0.6         # robots.txt parsing
aioredis==2.0.1             # Async Redis for URL queue
fuzzywuzzy==0.18.0          # Fuzzy string matching
python-Levenshtein==0.25.0  # Fast Levenshtein distance
trafilatura==1.6.3          # Web content extraction
```

---

## 3. 3rd-Party Services Analysis

### 3.1 Proxy Services

| Service | Pricing | Features | Recommendation |
|---------|---------|----------|----------------|
| **Bright Data** | $15/GB residential | Largest pool, geo-targeting | For high-volume |
| **ScraperAPI** | $49/mo for 100k requests | Simple API, JS rendering | **Recommended start** |
| **Oxylabs** | $15/GB residential | Reliable, enterprise | For scale |
| **SmartProxy** | $12.5/GB residential | Cost-effective | Budget option |

**Initial Recommendation**: Start with **ScraperAPI** ($49/mo) for simplicity. Upgrade to Bright Data if needed.

**Decision**: Defer proxy service until needed. Start with direct requests + rate limiting.

### 3.2 CAPTCHA Solving Services

| Service | Pricing | Recommendation |
|---------|---------|----------------|
| **2Captcha** | $3/1000 CAPTCHAs | If needed |
| **Anti-Captcha** | $2/1000 CAPTCHAs | Budget option |

**Decision**: Not required initially. Most whiskey/wine sites don't use CAPTCHAs. Implement if blocked.

### 3.3 Web Scraping APIs (Managed Services)

| Service | Pricing | Features | Recommendation |
|---------|---------|----------|----------------|
| **Apify** | $49/mo starter | Actor marketplace, scheduling | For complex sites |
| **ScrapingBee** | $49/mo for 150k requests | JS rendering included | Simple alternative |
| **Zyte (Scrapinghub)** | Custom pricing | Enterprise, Scrapy cloud | For scale |

**Decision**: Build custom crawler first. Consider Apify for specific difficult sources.

### 3.4 Search APIs

| Service | Pricing | Features | Recommendation |
|---------|---------|----------|----------------|
| **SerpAPI** | $75/mo for 5000 searches | Google, Bing, etc. | **Recommended** |
| **Google Custom Search** | $5/1000 queries (first 100 free) | Official, limited | For specific queries |
| **Bing Search API** | $7/1000 transactions | Good coverage | Alternative |

**Recommendation**: Use **SerpAPI** for product discovery searches. Budget: ~$75/month.

### 3.5 Content Extraction APIs

| Service | Pricing | Features | Recommendation |
|---------|---------|----------|----------------|
| **Diffbot** | $299/mo | Auto extraction, knowledge graph | Overkill |
| **Import.io** | Custom | Legacy | Not recommended |

**Decision**: Use AI Enhancement Service for extraction (already built). No additional service needed.

### 3.6 Monitoring Services

| Service | Pricing | Features | Recommendation |
|---------|---------|----------|----------------|
| **Sentry** | Free tier available | Error tracking | **Recommended** |
| **Datadog** | $15/host/mo | Full observability | For scale |

**Recommendation**: Use **Sentry** (free tier) for error tracking. Consider Datadog later.

### 3.7 Build vs. Buy Summary

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Core Crawler | **Build** | Custom control, Django integration |
| Proxy Rotation | **Defer** | Not needed initially |
| CAPTCHA Solving | **Defer** | Not needed for target sites |
| Search Discovery | **Buy (SerpAPI)** | $75/mo, valuable for discovery |
| Content Extraction | **Use existing** | AI Enhancement Service |
| Monitoring | **Buy (Sentry)** | Free tier, essential |

---

## 4. Database Models

### 4.1 Django Models

```python
# ai_enhancement_engine/models.py (additions for web crawler)

from django.db import models
from django.utils import timezone
import uuid


class ProductType(models.TextChoices):
    """Product types supported by the crawler."""
    WHISKEY = 'whiskey', 'Whiskey'
    PORT_WINE = 'port_wine', 'Port Wine'
    GIN = 'gin', 'Gin'
    RUM = 'rum', 'Rum'
    TEQUILA = 'tequila', 'Tequila'
    VODKA = 'vodka', 'Vodka'
    BRANDY = 'brandy', 'Brandy'
    SAKE = 'sake', 'Sake'


class SourceCategory(models.TextChoices):
    """Categories of content sources."""
    REVIEW = 'review', 'Review Site'
    RETAILER = 'retailer', 'Retailer'
    PRODUCER = 'producer', 'Producer Website'
    COMPETITION = 'competition', 'Competition/Awards'
    NEWS = 'news', 'News/Blog'
    DATABASE = 'database', 'Product Database'


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
        default=list,
        help_text="List of product types: ['whiskey', 'port_wine']"
    )
    category = models.CharField(
        max_length=20,
        choices=SourceCategory.choices,
        help_text="Type of source"
    )

    # Crawl Configuration
    is_active = models.BooleanField(default=True, help_text="Enable/disable crawling")
    priority = models.IntegerField(
        default=5,
        help_text="1-10, higher = more important"
    )
    crawl_frequency_hours = models.IntegerField(
        default=24,
        help_text="How often to crawl (hours)"
    )
    rate_limit_requests_per_minute = models.IntegerField(
        default=10,
        help_text="Max requests per minute to this domain"
    )

    # Technical Requirements
    requires_javascript = models.BooleanField(
        default=False,
        help_text="Requires headless browser"
    )
    requires_proxy = models.BooleanField(
        default=False,
        help_text="Requires proxy rotation"
    )
    requires_authentication = models.BooleanField(
        default=False,
        help_text="Requires login"
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom HTTP headers"
    )

    # URL Patterns
    product_url_patterns = models.JSONField(
        default=list,
        help_text="Regex patterns for product URLs"
    )
    pagination_pattern = models.CharField(
        max_length=200,
        blank=True,
        help_text="URL pattern for pagination (e.g., ?page={page})"
    )
    sitemap_url = models.URLField(
        blank=True,
        help_text="Sitemap URL if available"
    )

    # Compliance
    robots_txt_compliant = models.BooleanField(
        default=True,
        help_text="Checked robots.txt compliance"
    )
    tos_compliant = models.BooleanField(
        default=True,
        help_text="Checked Terms of Service compliance"
    )
    compliance_notes = models.TextField(
        blank=True,
        help_text="Notes on compliance requirements"
    )

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
        db_table = 'crawler_sources'
        ordering = ['-priority', 'name']
        indexes = [
            models.Index(fields=['is_active', 'next_crawl_at']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

    def update_next_crawl_time(self):
        """Calculate next crawl time based on frequency."""
        from datetime import timedelta
        self.last_crawl_at = timezone.now()
        self.next_crawl_at = timezone.now() + timedelta(hours=self.crawl_frequency_hours)
        self.save(update_fields=['last_crawl_at', 'next_crawl_at'])


class SearchContext(models.TextChoices):
    """Context for keyword searches."""
    NEW_RELEASE = 'new_release', 'New Release'
    REVIEW = 'review', 'Review'
    COMPETITION = 'competition', 'Competition/Award'
    PRICING = 'pricing', 'Pricing Intelligence'
    GENERAL = 'general', 'General Discovery'


class CrawlerKeyword(models.Model):
    """
    Keywords for product discovery searches.

    Used with search APIs (SerpAPI) and site-specific searches.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keyword = models.CharField(max_length=200, help_text="Search keyword or phrase")

    # Classification
    product_types = models.JSONField(
        default=list,
        help_text="Applicable product types: ['whiskey', 'port_wine']"
    )
    search_context = models.CharField(
        max_length=20,
        choices=SearchContext.choices,
        default=SearchContext.GENERAL,
        help_text="Context for this keyword"
    )

    # Configuration
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=5,
        help_text="1-10, higher = search more frequently"
    )
    search_frequency_hours = models.IntegerField(
        default=168,  # Weekly
        help_text="How often to search (hours)"
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
        db_table = 'crawler_keywords'
        ordering = ['-priority', 'keyword']
        unique_together = ['keyword', 'search_context']
        indexes = [
            models.Index(fields=['is_active', 'next_search_at']),
            models.Index(fields=['search_context']),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.search_context})"


class CrawlJobStatus(models.TextChoices):
    """Status of a crawl job."""
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class CrawlJob(models.Model):
    """
    Tracks individual crawl job executions.

    Created when a source crawl is initiated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.CASCADE,
        related_name='crawl_jobs'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=CrawlJobStatus.choices,
        default=CrawlJobStatus.PENDING
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
        db_table = 'crawl_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source', 'created_at']),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.source.name} ({self.status})"

    @property
    def duration_seconds(self):
        """Calculate job duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class CrawledURL(models.Model):
    """
    Tracks all URLs that have been crawled.

    Used for deduplication and incremental crawling.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=2000, unique=True, db_index=True)
    url_hash = models.CharField(max_length=64, unique=True, db_index=True)

    source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        related_name='crawled_urls'
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
        db_table = 'crawled_urls'
        indexes = [
            models.Index(fields=['source', 'is_product_page']),
            models.Index(fields=['was_processed']),
        ]

    def __str__(self):
        return self.url[:100]

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """Compute SHA-256 hash of URL."""
        import hashlib
        return hashlib.sha256(url.encode()).hexdigest()


class DiscoveredProduct(models.Model):
    """
    Products discovered by the crawler, pending review.

    Temporary storage before integration with inventory management.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source Information
    source = models.ForeignKey(
        CrawlerSource,
        on_delete=models.SET_NULL,
        null=True,
        related_name='discovered_products'
    )
    source_url = models.URLField(max_length=2000)
    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )

    # Product Identification
    fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash for deduplication"
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
        choices=[
            ('pending', 'Pending Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('duplicate', 'Duplicate'),
            ('merged', 'Merged'),
        ],
        default='pending'
    )

    # Matching
    matched_product_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of matched existing product"
    )
    match_confidence = models.FloatField(null=True, blank=True)

    # Metadata
    discovered_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'discovered_products'
        ordering = ['-discovered_at']
        indexes = [
            models.Index(fields=['status', 'discovered_at']),
            models.Index(fields=['product_type', 'status']),
            models.Index(fields=['fingerprint']),
        ]

    def __str__(self):
        name = self.extracted_data.get('name', 'Unknown')
        return f"{name} ({self.product_type})"

    @staticmethod
    def compute_fingerprint(extracted_data: dict) -> str:
        """Compute fingerprint for deduplication."""
        import hashlib
        import json

        # Use key identifying fields
        key_fields = {
            'name': extracted_data.get('name', '').lower().strip(),
            'brand': extracted_data.get('brand', '').lower().strip(),
            'product_type': extracted_data.get('product_type', ''),
            'volume_ml': extracted_data.get('volume_ml'),
            'abv': extracted_data.get('abv'),
        }

        # Add type-specific fields
        if extracted_data.get('product_type') == 'whiskey':
            key_fields['age_statement'] = extracted_data.get('age_statement')
            key_fields['distillery'] = extracted_data.get('distillery', '').lower()
        elif extracted_data.get('product_type') == 'port_wine':
            key_fields['style'] = extracted_data.get('style', '').lower()
            key_fields['harvest_year'] = extracted_data.get('harvest_year')

        fingerprint_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
```

### 4.2 Entity Relationship Diagram

```
+-------------------+       +-------------------+       +-------------------+
| CrawlerSource     |       | CrawlJob          |       | CrawledURL        |
+-------------------+       +-------------------+       +-------------------+
| id (UUID PK)      |<---+  | id (UUID PK)      |       | id (UUID PK)      |
| name              |    |  | source (FK)       |------>| url               |
| slug              |    |  | status            |       | url_hash          |
| base_url          |    |  | started_at        |       | source (FK)       |
| product_types[]   |    |  | completed_at      |       | is_product_page   |
| category          |    |  | pages_crawled     |       | was_processed     |
| is_active         |    |  | products_found    |       | last_crawled_at   |
| priority          |    |  | errors_count      |       | content_hash      |
| rate_limit        |    |  +-------------------+       +-------------------+
| requires_js       |    |          |                           |
| last_crawl_at     |    |          v                           |
| next_crawl_at     |    |  +-------------------+               |
+-------------------+    |  | DiscoveredProduct |<--------------+
        |                |  +-------------------+
        |                +->| id (UUID PK)      |
        |                   | source (FK)       |
        v                   | crawl_job (FK)    |
+-------------------+       | fingerprint       |
| CrawlerKeyword    |       | product_type      |
+-------------------+       | raw_content       |
| id (UUID PK)      |       | extracted_data    |
| keyword           |       | enriched_data     |
| product_types[]   |       | status            |
| search_context    |       | matched_product_id|
| is_active         |       +-------------------+
| priority          |
| last_searched_at  |
+-------------------+
```

---

## 5. Pipeline Architecture

### 5.1 Crawler Pipeline Flow

```
+------------------------------------------------------------------------------+
|                           CRAWLER PIPELINE                                    |
+------------------------------------------------------------------------------+

1. SCHEDULING LAYER
   +----------------+     +----------------+     +----------------+
   | Celery Beat    | --> | Job Scheduler  | --> | URL Frontier   |
   | (periodic)     |     | - Check due    |     | (Redis Queue)  |
   +----------------+     |   sources      |     | - Priority     |
                          | - Create jobs  |     |   based        |
                          +----------------+     +----------------+
                                                        |
                                                        v
2. FETCHING LAYER
   +----------------+     +----------------+     +----------------+
   | Rate Limiter   | --> | Content        | --> | Robots.txt     |
   | - Per domain   |     | Fetcher        |     | Checker        |
   | - Token bucket |     | - httpx        |     | - Cache rules  |
   +----------------+     | - Playwright   |     +----------------+
                          +----------------+
                                 |
                                 v
3. PARSING LAYER
   +----------------+     +----------------+     +----------------+
   | HTML Parser    | --> | Content        | --> | Link Extractor |
   | - BeautifulSoup|     | Extractor      |     | - Product URLs |
   | - trafilatura  |     | - Text content |     | - Pagination   |
   +----------------+     +----------------+     +----------------+
                                 |
                                 v
4. ENHANCEMENT LAYER
   +----------------+     +----------------+     +----------------+
   | AI Enhancement | --> | Output         | --> | Fingerprint    |
   | Service        |     | Validator      |     | Generator      |
   | /from-crawler  |     | - Schema check |     | - Dedup hash   |
   +----------------+     +----------------+     +----------------+
                                 |
                                 v
5. STORAGE LAYER
   +----------------+     +----------------+     +----------------+
   | Deduplication  | --> | Product        | --> | PostgreSQL     |
   | - Fingerprint  |     | Matcher        |     | - Store new    |
   |   lookup       |     | - Fuzzy match  |     | - Queue review |
   +----------------+     +----------------+     +----------------+
```

### 5.2 URL Frontier (Redis Queue)

```python
# crawlers/url_frontier.py

import redis
import json
from datetime import datetime
from typing import Optional, Dict, Any


class URLFrontier:
    """
    Redis-based URL frontier with priority queue.

    Uses sorted sets for priority ordering.
    """

    QUEUE_KEY = "crawler:url_frontier"
    SEEN_KEY = "crawler:seen_urls"
    DOMAIN_RATE_KEY = "crawler:domain_rate:{domain}"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def add_url(
        self,
        url: str,
        priority: int = 5,
        source_id: str = None,
        metadata: Dict = None
    ) -> bool:
        """Add URL to frontier if not already seen."""
        url_hash = self._hash_url(url)

        # Check if already seen
        if self.redis.sismember(self.SEEN_KEY, url_hash):
            return False

        # Add to seen set
        self.redis.sadd(self.SEEN_KEY, url_hash)

        # Create URL entry
        entry = {
            "url": url,
            "source_id": source_id,
            "added_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Add to priority queue (higher priority = lower score = fetched first)
        score = 10 - priority  # Invert for sorted set
        self.redis.zadd(
            self.QUEUE_KEY,
            {json.dumps(entry): score}
        )

        return True

    def get_next_url(self) -> Optional[Dict[str, Any]]:
        """Get highest priority URL from frontier."""
        # Pop from sorted set
        result = self.redis.zpopmin(self.QUEUE_KEY, count=1)
        if result:
            entry_json, score = result[0]
            return json.loads(entry_json)
        return None

    def check_rate_limit(self, domain: str, requests_per_minute: int) -> bool:
        """Check if domain rate limit allows request."""
        key = self.DOMAIN_RATE_KEY.format(domain=domain)
        current = self.redis.incr(key)

        if current == 1:
            # First request, set expiry
            self.redis.expire(key, 60)

        return current <= requests_per_minute

    def get_queue_size(self) -> int:
        """Get current frontier size."""
        return self.redis.zcard(self.QUEUE_KEY)

    def _hash_url(self, url: str) -> str:
        """Hash URL for deduplication."""
        import hashlib
        return hashlib.sha256(url.encode()).hexdigest()
```

### 5.3 Content Fetcher

```python
# crawlers/content_fetcher.py

import httpx
from playwright.async_api import async_playwright
from typing import Optional, Dict, Tuple
import asyncio
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class ContentFetcher:
    """
    Async content fetcher with JavaScript rendering support.
    """

    DEFAULT_HEADERS = {
        "User-Agent": "SpiritsWise-Crawler/1.0 (+https://spiritswise.com/crawler)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        proxy_url: Optional[str] = None
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxy_url = proxy_url
        self._http_client = None
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.DEFAULT_HEADERS,
            follow_redirects=True,
            http2=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def fetch(
        self,
        url: str,
        requires_javascript: bool = False,
        custom_headers: Optional[Dict] = None
    ) -> Tuple[str, int, Dict]:
        """
        Fetch URL content.

        Returns: (content, status_code, headers)
        """
        headers = {**self.DEFAULT_HEADERS, **(custom_headers or {})}

        for attempt in range(self.max_retries):
            try:
                if requires_javascript:
                    return await self._fetch_with_browser(url)
                else:
                    return await self._fetch_with_httpx(url, headers)

            except Exception as e:
                logger.warning(
                    f"Fetch attempt {attempt + 1} failed for {url}: {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    async def _fetch_with_httpx(
        self,
        url: str,
        headers: Dict
    ) -> Tuple[str, int, Dict]:
        """Fetch using httpx (no JS)."""
        response = await self._http_client.get(url, headers=headers)
        return response.text, response.status_code, dict(response.headers)

    async def _fetch_with_browser(
        self,
        url: str
    ) -> Tuple[str, int, Dict]:
        """Fetch using Playwright (with JS rendering)."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True
            )

        page = await self._browser.new_page()
        try:
            response = await page.goto(url, wait_until="networkidle")
            content = await page.content()
            return content, response.status, {}
        finally:
            await page.close()
```

### 5.4 Integration with AI Enhancement Service

```python
# crawlers/ai_integration.py

import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AIEnhancementClient:
    """
    Client for AI Enhancement Service integration.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 60.0  # AI enhancement can take up to 15s
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def enhance_from_crawler(
        self,
        content: str,
        source_url: str,
        product_type_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send crawled content to AI Enhancement Service.

        POST /api/v1/enhance/from-crawler/
        """
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "content": content,
            "source_url": source_url
        }
        if product_type_hint:
            payload["product_type_hint"] = product_type_hint

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/enhance/from-crawler/",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def batch_enhance(
        self,
        items: list[Dict]
    ) -> str:
        """
        Submit batch enhancement request.

        Returns job_id for status tracking.
        """
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/enhance/batch/",
                json={"items": items},
                headers=headers
            )
            response.raise_for_status()
            return response.json()["job_id"]
```

### 5.5 Error Handling & Retry Policies

```python
# crawlers/error_handling.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of crawl errors."""
    NETWORK = "network"          # Connection issues
    HTTP_CLIENT = "http_client"  # 4xx errors
    HTTP_SERVER = "http_server"  # 5xx errors
    PARSING = "parsing"          # Content parsing failures
    RATE_LIMIT = "rate_limit"    # Rate limited
    BLOCKED = "blocked"          # IP blocked/CAPTCHA
    TIMEOUT = "timeout"          # Request timeout
    UNKNOWN = "unknown"          # Other errors


@dataclass
class RetryPolicy:
    """Retry configuration for error categories."""
    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float
    exponential_base: float = 2.0


# Default retry policies by error category
RETRY_POLICIES = {
    ErrorCategory.NETWORK: RetryPolicy(
        max_retries=5,
        base_delay_seconds=2,
        max_delay_seconds=60
    ),
    ErrorCategory.HTTP_SERVER: RetryPolicy(
        max_retries=3,
        base_delay_seconds=5,
        max_delay_seconds=120
    ),
    ErrorCategory.RATE_LIMIT: RetryPolicy(
        max_retries=3,
        base_delay_seconds=60,
        max_delay_seconds=300
    ),
    ErrorCategory.TIMEOUT: RetryPolicy(
        max_retries=2,
        base_delay_seconds=10,
        max_delay_seconds=60
    ),
    ErrorCategory.HTTP_CLIENT: RetryPolicy(
        max_retries=0,  # Don't retry 4xx
        base_delay_seconds=0,
        max_delay_seconds=0
    ),
    ErrorCategory.BLOCKED: RetryPolicy(
        max_retries=0,  # Don't retry blocks
        base_delay_seconds=0,
        max_delay_seconds=0
    ),
}


def categorize_error(exception: Exception, status_code: Optional[int] = None) -> ErrorCategory:
    """Categorize an error for retry policy lookup."""
    if status_code:
        if status_code == 429:
            return ErrorCategory.RATE_LIMIT
        elif 400 <= status_code < 500:
            return ErrorCategory.HTTP_CLIENT
        elif 500 <= status_code < 600:
            return ErrorCategory.HTTP_SERVER

    error_name = type(exception).__name__.lower()

    if "timeout" in error_name:
        return ErrorCategory.TIMEOUT
    elif "connection" in error_name or "network" in error_name:
        return ErrorCategory.NETWORK

    return ErrorCategory.UNKNOWN


def calculate_retry_delay(
    category: ErrorCategory,
    attempt: int
) -> float:
    """Calculate delay before next retry attempt."""
    policy = RETRY_POLICIES.get(category, RETRY_POLICIES[ErrorCategory.UNKNOWN])

    if attempt >= policy.max_retries:
        return -1  # No more retries

    delay = policy.base_delay_seconds * (policy.exponential_base ** attempt)
    return min(delay, policy.max_delay_seconds)
```

---

## 6. Source Configuration

### 6.1 Whiskey Sources

See `fixtures/whiskey_sources.json` for complete database entries.

#### 6.1.1 Review Sites

| Source | URL | Category | robots.txt | Notes |
|--------|-----|----------|------------|-------|
| The Whisky Exchange | thewhiskyexchange.com | Retailer | Restrictive | Product pages blocked, use sitemap |
| Master of Malt | masterofmalt.com | Retailer | Rate limited (429) | Requires proxy |
| Whisky Advocate | whiskyadvocate.com | Review | Blocks AI bots | Standard crawler OK |
| Whiskybase | whiskybase.com | Database | Blocks (403) | Requires proxy |
| Distiller | distiller.com | Review | Permissive | Good source |
| Scotchwhisky.com | scotchwhisky.com | Review | Permissive | Good source |

#### 6.1.2 Competition/Awards

| Source | URL | Category | Notes |
|--------|-----|----------|-------|
| IWSC | iwsc.net | Competition | Annual results |
| World Whiskies Awards | worldwhiskiesawards.com | Competition | Annual results |
| SF World Spirits | sfspiritscomp.com | Competition | Annual results |

#### 6.1.3 DACH Retailers

| Source | URL | Country | Notes |
|--------|-----|---------|-------|
| Whisky.de | whisky.de | Germany | Large catalog, permissive |
| Weinquelle | weinquelle.com | Germany | Wine and spirits |
| Whisky Exchange CH | thewhiskyexchange.ch | Switzerland | Swiss prices |

### 6.2 Port Wine Sources

See `fixtures/port_wine_sources.json` for complete database entries.

#### 6.2.1 Review Sites

| Source | URL | Category | robots.txt | Notes |
|--------|-----|----------|------------|-------|
| Wine Spectator | winespectator.com | Review | Blocks AI bots | Standard crawler OK |
| Decanter | decanter.com | Review | Permissive | Good source |
| JancisRobinson | jancisrobinson.com | Review | Subscription required |
| Cellar Tracker | cellartracker.com | Database | Community reviews |

#### 6.2.2 Producer Sites

| Source | URL | Category | Notes |
|--------|-----|----------|-------|
| Taylor's | taylor.pt | Producer | Permissive |
| Graham's | grahams-port.com | Producer | Content signals, permissive |
| Fonseca | fonseca.pt | Producer | Permissive |
| Symington | symington.com | Producer | Multiple brands |
| Niepoort | niepoort.pt | Producer | Permissive |
| Quinta do Noval | quintadonoval.com | Producer | Permissive |

#### 6.2.3 Competition/Awards

| Source | URL | Category | Notes |
|--------|-----|----------|-------|
| Decanter WWA | decanter.com/awards | Competition | Annual results |
| IWC | internationalwinechallenge.com | Competition | Annual results |

---

## 7. Keyword Management

### 7.1 Whiskey Keywords

See `fixtures/whiskey_keywords.json` for complete database entries.

#### 7.1.1 Product Discovery Keywords

| Category | Keywords | Context |
|----------|----------|---------|
| Type | single malt, blended malt, bourbon, rye whiskey, irish whiskey, japanese whisky | General |
| Release | new release, limited edition, special release, distillery exclusive | New Release |
| Style | cask strength, single cask, cask finish, peated, heavily peated | General |

#### 7.1.2 Age Statement Keywords

| Keywords | Context |
|----------|---------|
| 10 year, 12 year, 15 year, 18 year, 21 year, 25 year, 30 year | General |
| no age statement, NAS | General |

#### 7.1.3 Region Keywords

| Keywords | Context |
|----------|---------|
| Speyside, Islay, Highland, Lowland, Campbeltown, Islands | General |
| Kentucky bourbon, Tennessee whiskey | General |

#### 7.1.4 Awards Keywords

| Keywords | Context |
|----------|---------|
| gold medal, silver medal, best in class, whisky of the year | Competition |
| 90+ points, 95+ points, award winning, top rated | Review |

#### 7.1.5 Pricing Keywords (DACH)

| Keywords | Context |
|----------|---------|
| whisky preis, whisky kaufen, whisky online shop | Pricing |
| single malt preis, bourbon preis | Pricing |

### 7.2 Port Wine Keywords

See `fixtures/port_wine_keywords.json` for complete database entries.

#### 7.2.1 Style Keywords

| Keywords | Context |
|----------|---------|
| vintage port, tawny port, ruby port, LBV, late bottled vintage | General |
| colheita, crusted port, white port, rose port | General |
| 10 year tawny, 20 year tawny, 30 year tawny, 40 year tawny | General |

#### 7.2.2 Vintage Keywords

| Keywords | Context |
|----------|---------|
| 2022 vintage port, 2021 vintage, 2020 vintage, 2019, 2018, 2017, 2016, 2015, 2011, 2007, 2003, 2000 | General |
| declared vintage, vintage declaration | New Release |

#### 7.2.3 Producer Keywords

| Keywords | Context |
|----------|---------|
| Taylor's port, Graham's port, Fonseca port, Dow's port, Warre's port | General |
| Sandeman, Cockburn's, Croft, Niepoort, Quinta do Noval, Nacional | General |

#### 7.2.4 Awards Keywords

| Keywords | Context |
|----------|---------|
| gold medal port, best port wine, 95+ points | Competition |
| vintage of the year, port of the year | Competition |

---

## 8. Scalability Considerations

### 8.1 Horizontal Scaling

```
                    +------------------+
                    | Load Balancer    |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v---------+ +-------v--------+ +-------v--------+
| Crawler Worker 1 | | Crawler Worker 2| | Crawler Worker N|
| - 2 async tasks  | | - 2 async tasks | | - 2 async tasks |
+--------+---------+ +--------+--------+ +--------+-------+
         |                    |                   |
         +--------------------+-------------------+
                              |
                    +---------v---------+
                    | Redis Cluster     |
                    | - URL Frontier    |
                    | - Rate Limiting   |
                    | - Task Queue      |
                    +-------------------+
```

### 8.2 Capacity Planning

| Metric | Current (Phase 2) | Scale Target |
|--------|-------------------|--------------|
| URLs/hour | 1,000 | 10,000 |
| Products/day | 500 | 5,000 |
| Celery Workers | 4 | 16 |
| Storage (monthly) | 10 GB | 100 GB |
| API Calls/month | 10,000 | 100,000 |

### 8.3 Performance Optimization

1. **Connection Pooling**: httpx connection pool for each domain
2. **Async Processing**: Full async pipeline with asyncio
3. **Batch AI Enhancement**: Group requests to AI service
4. **Incremental Crawling**: Track content hashes, skip unchanged pages
5. **Sitemap-First**: Use sitemaps when available for efficiency

---

## 9. Cost Estimates

### 9.1 Monthly Operating Costs

| Item | Provider | Cost/Month | Notes |
|------|----------|------------|-------|
| VPS (shared) | Hetzner CCX33 | $0 | Already provisioned |
| Search API | SerpAPI | $75 | 5,000 searches |
| Proxy (if needed) | ScraperAPI | $49 | 100k requests |
| AI Enhancement | OpenAI | ~$50 | 1,000 products @ $0.05 |
| Monitoring | Sentry | $0 | Free tier |
| **Total (base)** | | **$125** | Without proxy |
| **Total (with proxy)** | | **$174** | With proxy |

### 9.2 Cost per Product

| Component | Cost/Product | Notes |
|-----------|--------------|-------|
| Search (SerpAPI) | $0.015 | $75/5000 searches |
| Fetch (direct) | ~$0 | Own infrastructure |
| Fetch (proxy) | $0.0005 | If needed |
| AI Enhancement | $0.05 | GPT-4 tokens |
| **Total** | **$0.065-0.07** | |

### 9.3 ROI Analysis

- **Break-even**: 2,000 products/month to justify tooling investment
- **Target**: 5,000+ products/month for cost-effectiveness
- **Value Add**: Manual data entry estimated at $2-5/product

---

## 10. Implementation Roadmap

### Phase 2a: Foundation (Week 1-2)

- [ ] Add crawler models to Django
- [ ] Create Django Admin interface
- [ ] Implement URL Frontier (Redis)
- [ ] Implement Content Fetcher (httpx)
- [ ] Add robots.txt compliance
- [ ] Create fixtures from research

### Phase 2b: Core Crawler (Week 3-4)

- [ ] Implement rate limiter
- [ ] Implement retry policies
- [ ] Add Playwright integration (JS rendering)
- [ ] Integrate AI Enhancement Service
- [ ] Implement product fingerprinting
- [ ] Add deduplication logic

### Phase 2c: Whiskey Crawler (Week 5-6)

- [ ] Configure whiskey sources
- [ ] Create source-specific parsers
- [ ] Implement search API integration (SerpAPI)
- [ ] Add Celery Beat scheduling
- [ ] Test with production sources

### Phase 2d: Port Wine Crawler (Week 7-8)

- [ ] Configure port wine sources
- [ ] Create source-specific parsers
- [ ] Add vintage detection logic
- [ ] Test with production sources
- [ ] Monitoring and alerting setup

### Phase 2e: Production Ready (Week 9-10)

- [ ] Load testing
- [ ] Performance optimization
- [ ] Documentation
- [ ] Deployment automation
- [ ] Handover and training

---

## Appendix A: Django Admin Configuration

```python
# ai_enhancement_engine/admin.py (additions)

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CrawlerSource, CrawlerKeyword, CrawlJob,
    CrawledURL, DiscoveredProduct
)


@admin.register(CrawlerSource)
class CrawlerSourceAdmin(admin.ModelAdmin):
    """Admin interface for crawler sources."""

    list_display = [
        'name', 'category', 'is_active', 'priority',
        'rate_limit_requests_per_minute', 'last_crawl_at',
        'total_products_found', 'status_badge'
    ]
    list_filter = ['is_active', 'category', 'requires_javascript', 'requires_proxy']
    search_fields = ['name', 'base_url']
    readonly_fields = ['last_crawl_at', 'next_crawl_at', 'created_at', 'updated_at']
    ordering = ['-priority', 'name']

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'base_url', 'category', 'product_types')
        }),
        ('Crawl Configuration', {
            'fields': (
                'is_active', 'priority', 'crawl_frequency_hours',
                'rate_limit_requests_per_minute'
            )
        }),
        ('Technical Requirements', {
            'fields': (
                'requires_javascript', 'requires_proxy',
                'requires_authentication', 'custom_headers'
            ),
            'classes': ('collapse',)
        }),
        ('URL Patterns', {
            'fields': (
                'product_url_patterns', 'pagination_pattern', 'sitemap_url'
            ),
            'classes': ('collapse',)
        }),
        ('Compliance', {
            'fields': (
                'robots_txt_compliant', 'tos_compliant', 'compliance_notes'
            )
        }),
        ('Status', {
            'fields': (
                'last_crawl_at', 'next_crawl_at', 'last_crawl_status',
                'total_products_found'
            )
        }),
        ('Metadata', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    actions = ['trigger_crawl', 'disable_sources', 'enable_sources']

    def status_badge(self, obj):
        if not obj.is_active:
            color = 'gray'
            text = 'Disabled'
        elif obj.last_crawl_status == 'completed':
            color = 'green'
            text = 'OK'
        elif obj.last_crawl_status == 'failed':
            color = 'red'
            text = 'Failed'
        else:
            color = 'orange'
            text = 'Pending'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    status_badge.short_description = 'Status'

    def trigger_crawl(self, request, queryset):
        # Trigger crawl for selected sources
        for source in queryset:
            # Create crawl job via Celery
            pass
        self.message_user(request, f"Triggered crawl for {queryset.count()} sources")
    trigger_crawl.short_description = "Trigger crawl now"

    def disable_sources(self, request, queryset):
        queryset.update(is_active=False)
    disable_sources.short_description = "Disable selected sources"

    def enable_sources(self, request, queryset):
        queryset.update(is_active=True)
    enable_sources.short_description = "Enable selected sources"


@admin.register(CrawlerKeyword)
class CrawlerKeywordAdmin(admin.ModelAdmin):
    """Admin interface for crawler keywords."""

    list_display = [
        'keyword', 'search_context', 'is_active', 'priority',
        'last_searched_at', 'total_results_found'
    ]
    list_filter = ['is_active', 'search_context', 'product_types']
    search_fields = ['keyword']
    ordering = ['-priority', 'keyword']

    actions = ['trigger_search', 'disable_keywords', 'enable_keywords']


@admin.register(CrawlJob)
class CrawlJobAdmin(admin.ModelAdmin):
    """Admin interface for crawl jobs."""

    list_display = [
        'id', 'source', 'status', 'pages_crawled',
        'products_found', 'errors_count', 'created_at', 'duration'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['source__name']
    readonly_fields = [
        'created_at', 'started_at', 'completed_at',
        'pages_crawled', 'products_found', 'products_new',
        'products_updated', 'errors_count', 'error_details'
    ]
    ordering = ['-created_at']

    def duration(self, obj):
        if obj.duration_seconds:
            return f"{obj.duration_seconds:.1f}s"
        return "-"
    duration.short_description = 'Duration'


@admin.register(DiscoveredProduct)
class DiscoveredProductAdmin(admin.ModelAdmin):
    """Admin interface for discovered products."""

    list_display = [
        'product_name', 'product_type', 'source', 'status',
        'extraction_confidence', 'discovered_at'
    ]
    list_filter = ['status', 'product_type', 'source']
    search_fields = ['extracted_data']
    readonly_fields = [
        'fingerprint', 'raw_content', 'raw_content_hash',
        'extracted_data', 'enriched_data', 'discovered_at'
    ]
    ordering = ['-discovered_at']

    actions = ['approve_products', 'reject_products', 'mark_duplicate']

    def product_name(self, obj):
        return obj.extracted_data.get('name', 'Unknown')
    product_name.short_description = 'Name'

    def approve_products(self, request, queryset):
        queryset.update(status='approved', reviewed_at=timezone.now())
    approve_products.short_description = "Approve selected products"

    def reject_products(self, request, queryset):
        queryset.update(status='rejected', reviewed_at=timezone.now())
    reject_products.short_description = "Reject selected products"
```

---

## Appendix B: Open Questions

1. **Proxy Necessity**: Defer proxy integration until we encounter blocking?
   - **Recommendation**: Yes, start without proxy

2. **Search API Priority**: Should we prioritize SerpAPI integration?
   - **Recommendation**: Yes, valuable for product discovery

3. **Real-time vs. Batch**: Should products be processed in real-time or batched?
   - **Recommendation**: Batch during crawl, real-time for small volumes

4. **Content Storage**: Store full HTML or just extracted content?
   - **Recommendation**: Store both for debugging, expire raw after 30 days

5. **Duplicate Threshold**: What fuzzy match score indicates a duplicate?
   - **Recommendation**: 90%+ similarity = likely duplicate, manual review

---

## Appendix C: Compliance Checklist

- [ ] Verify robots.txt for each source before crawling
- [ ] Implement reasonable request delays (min 2 seconds between requests)
- [ ] Identify crawler via User-Agent string
- [ ] Honor Retry-After headers
- [ ] Respect Terms of Service
- [ ] Provide contact information in User-Agent
- [ ] Monitor for 429/503 responses and back off
- [ ] Do not circumvent access controls
- [ ] Document compliance status for each source

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-27 | AI Enhancement Team | Initial specification |
