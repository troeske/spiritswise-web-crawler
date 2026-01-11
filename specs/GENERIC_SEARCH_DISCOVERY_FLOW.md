# Generic Search Discovery Flow

**Created**: 2026-01-10
**Status**: IMPLEMENTED
**Spec Reference**: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md - Section 7

---

## Overview

The Generic Search Discovery flow enables automatic discovery of new product sources via search engine queries. This replaces manual URL curation with an automated pipeline that discovers high-quality list pages, extracts products, and tracks provenance.

---

## Flow Diagram

```
┌─────────────────┐
│  SearchTerm DB  │
│  (search_query, │
│  max_results,   │
│  priority)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Discovery      │────▶│  SerpAPI        │
│  Orchestrator   │     │  (organic only) │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  DiscoveryResult│
│  (URL, status)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  URL Dedup      │────▶│  CrawledURL     │
│  Check          │     │  (url_hash)     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  SmartRouter    │────▶│  Page Content   │
│  Fetch          │     │                 │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  AI Extraction  │────▶│  is_list_page   │
│  (AIClientV2)   │     │  detail_url     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Fingerprint    │────▶│  DiscoveredProd │
│  Dedup          │     │  (skeleton)     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  CrawledSource  │
│  source_type=   │
│  "list_page"    │
└─────────────────┘
```

---

## Components

### 1. SearchTerm Model (Section 7.2)

The SearchTerm model defines what to search for:

```python
class SearchTerm(models.Model):
    # Core Fields
    search_query = models.CharField(max_length=200)
    category = models.CharField(choices=SearchTermCategory.choices)
    product_type = models.CharField(choices=SearchTermProductType.choices)

    # Execution Control
    max_results = models.IntegerField(default=10, validators=[Min(1), Max(20)])
    priority = models.IntegerField(default=100)  # Lower = higher priority
    is_active = models.BooleanField(default=True)

    # Seasonality
    seasonal_start_month = models.IntegerField(null=True, validators=[Min(1), Max(12)])
    seasonal_end_month = models.IntegerField(null=True, validators=[Min(1), Max(12)])

    # Metrics
    search_count = models.IntegerField(default=0)
    products_discovered = models.IntegerField(default=0)
    last_searched = models.DateTimeField(null=True)

    def is_in_season(self) -> bool:
        """Check if term is in season for current month."""
        if not self.seasonal_start_month or not self.seasonal_end_month:
            return True  # Year-round term

        current_month = datetime.now().month
        if self.seasonal_start_month <= self.seasonal_end_month:
            return self.seasonal_start_month <= current_month <= self.seasonal_end_month
        else:
            # Wraps around year (e.g., Nov-Feb)
            return current_month >= self.seasonal_start_month or current_month <= self.seasonal_end_month
```

### 2. SearchTerm Categories

| Category | Description | Example Queries |
|----------|-------------|-----------------|
| `best_lists` | "Best of" articles | "best bourbon 2026", "top scotch whisky" |
| `awards` | Competition results | "whiskey awards 2026", "IWSC gold" |
| `new_releases` | Recent launches | "new bourbon release 2026" |
| `style` | Category-specific | "best single malt", "tawny port" |
| `value` | Price-focused | "best budget whiskey", "affordable bourbon" |
| `regional` | Geographic focus | "Japanese whisky", "Kentucky bourbon" |
| `seasonal` | Holiday/seasonal | "holiday whiskey gifts", "winter port" |

### 3. Priority Ordering (Section 7.3)

SearchTerms are processed in priority order:
- Lower priority number = higher importance
- Default priority: 100
- Secondary sort: `-products_discovered` (most productive first)

```python
# Query with proper ordering
terms = SearchTerm.objects.filter(
    is_active=True
).order_by('priority', '-products_discovered')
```

### 4. SerpAPI Integration (Section 7.4)

The DiscoveryOrchestrator executes searches via SerpAPI:

```python
def _execute_search(self, term: SearchTerm) -> List[Dict]:
    """Execute SerpAPI search, returning organic results only."""
    response = self.serpapi_client.search(term.search_query)

    # Only use organic_results (ads excluded per spec)
    organic = response.get("organic_results", [])

    # Respect term.max_results limit
    return organic[:term.max_results]
```

**Key Points**:
- Only `organic_results` are used (ads excluded)
- `num` parameter set to `term.max_results`
- Search count and last_searched updated after each search

### 5. URL Deduplication (Section 7.6)

Before crawling a discovered URL, check if already processed:

```python
class CrawledURL(models.Model):
    url = models.URLField(max_length=2048)
    url_hash = models.CharField(max_length=64, unique=True)  # SHA-256
    created_at = models.DateTimeField(auto_now_add=True)

def is_duplicate_url(url: str) -> bool:
    """Check if URL already crawled."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return CrawledURL.objects.filter(url_hash=url_hash).exists()
```

### 6. AI Extraction Response

The AI service response includes list page detection:

```python
{
    "success": True,
    "is_multi_product": True,
    "is_list_page": True,  # Indicates list page detected
    "products": [
        {
            "extracted_data": {
                "name": "Buffalo Trace Bourbon",
                "brand": "Buffalo Trace",
                "detail_url": "/products/buffalo-trace",  # Link to product page
                ...
            },
            "confidence": 0.85,
            ...
        }
    ]
}
```

### 7. CrawledSource Type

List pages are stored with `source_type="list_page"`:

```python
class CrawledSourceTypeChoices(models.TextChoices):
    AWARD_PAGE = "award_page", "Award Page"
    PRODUCT_PAGE = "product_page", "Product Page"
    LIST_PAGE = "list_page", "List Page"  # Generic search discovery
    ...
```

### 8. Product Fingerprint Deduplication

Products are deduplicated via fingerprint hash:

```python
class DiscoveredProduct(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)

    @staticmethod
    def compute_fingerprint(extracted_data: dict) -> str:
        """Compute fingerprint from key fields."""
        key_data = json.dumps({
            "name": extracted_data.get("name", "").lower().strip(),
            "brand": extracted_data.get("brand", "").lower().strip(),
            "product_type": extracted_data.get("product_type", ""),
        }, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()
```

---

## Discovery Result Status

```python
class DiscoveryResultStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    DUPLICATE = "duplicate", "Duplicate"  # URL already crawled
```

---

## E2E Tests

The following test files verify this flow:

| File | Purpose |
|------|---------|
| `test_generic_search_discovery.py` | Complete discovery pipeline |
| `test_search_term_management.py` | SearchTerm CRUD and configuration |
| `test_deduplication.py` | URL and fingerprint deduplication |
| `test_list_page.py` | TestSearchTermDiscoveryFlow class |

### Key Test Scenarios

1. **SearchTerm Configuration**
   - Create with all fields
   - Validate max_results bounds (1-20)
   - Validate seasonal months (1-12)
   - Verify priority ordering

2. **Seasonality Filtering**
   - Year-round terms always in season
   - Current month terms in season
   - Out-of-season terms filtered
   - Wrapping ranges (Nov-Feb)

3. **Search Execution**
   - SerpAPI returns organic only
   - max_results respected
   - Metrics updated after search

4. **Deduplication**
   - URL hash uniqueness enforced
   - Duplicate URLs marked as DUPLICATE
   - Product fingerprint prevents duplicates

5. **AI Response**
   - is_list_page flag present
   - detail_url extracted from links
   - Multiple products from single page

---

## Metrics Tracking

SearchTerm metrics are updated during execution:

```python
# After search execution
term.search_count += 1
term.last_searched = timezone.now()

# After product extraction
term.products_discovered += len(extracted_products)

term.save()
```

Aggregate metrics query:

```python
from django.db.models import Sum

totals = SearchTerm.objects.filter(
    product_type="whiskey"
).aggregate(
    total_searches=Sum("search_count"),
    total_products=Sum("products_discovered"),
)
```

---

## Configuration

### Environment Variables

```bash
# SerpAPI for search
SERPAPI_API_KEY=<your-key>

# AI Enhancement Service for extraction
AI_ENHANCEMENT_SERVICE_URL=https://api.spiritswise.tech
AI_ENHANCEMENT_SERVICE_TOKEN=<your-token>

# ScrapingBee for JS rendering (optional)
SCRAPINGBEE_API_KEY=<your-key>
```

### Default Values

| Field | Default | Description |
|-------|---------|-------------|
| max_results | 10 | Results to crawl per search |
| priority | 100 | Execution order (lower = first) |
| is_active | True | Whether term is used |
| search_count | 0 | Number of executions |
| products_discovered | 0 | Total products found |

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| SerpAPI rate limit | Retry with exponential backoff |
| Fetch failure | Mark DiscoveryResult as FAILED |
| AI extraction failure | Log error, continue with next URL |
| Duplicate URL | Mark DiscoveryResult as DUPLICATE |
| Duplicate fingerprint | Update existing product, link new source |

---

## Related Documentation

- [CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md](CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md) - Section 7
- [E2E_TEST_SPECIFICATION_V2.md](E2E_TEST_SPECIFICATION_V2.md) - Flow 7
- [V2_IMPLEMENTATION_TASKS.md](V2_IMPLEMENTATION_TASKS.md) - Implementation tasks
