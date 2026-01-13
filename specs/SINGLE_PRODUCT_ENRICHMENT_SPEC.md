# Single Product Enrichment Flow Specification

**Version:** 1.0
**Created:** 2026-01-13
**Status:** Draft

---

## 1. Overview

### 1.1 Purpose

The Single Product Enrichment Flow enables targeted enrichment of individual products, triggered by crawler schedule entries with category `SINGLE_PRODUCT`. This flow handles two scenarios:

1. **New Product**: Product URL doesn't match any existing DiscoveredProduct → Create and enrich
2. **Existing Product**: Product matches existing DiscoveredProduct → Enrich existing data with focus on recent reviews

### 1.2 Key Requirements

- Integrate with existing CrawlSchedule/CrawlJob infrastructure
- Reuse shared code blocks from Competition and Generic Search flows
- Implement a reusable "Enrich Existing Product" sub-flow applicable to all three discovery flows
- Track source provenance and confidence scores
- Support both whiskey and port_wine product types

### 1.3 Integration Points

| Component | Usage |
|-----------|-------|
| `CrawlSchedule` | Stores single product URLs in `search_terms` field |
| `CrawlJob` | Tracks individual job execution |
| `DiscoveredProduct` | Product storage with fingerprint deduplication |
| `EnrichmentPipelineV3` | 2-step enrichment (producer page + SerpAPI-discovered review sites) |
| `EnrichmentConfig` | Defines search query templates for dynamic site discovery |
| `SerpAPI` | Discovers relevant URLs dynamically based on search queries |
| `DuplicateDetector` | GTIN, fingerprint, and fuzzy name matching |
| `QualityGateV3` | Status assessment and ECP calculation |

### 1.4 Enrichment Site Discovery (Important Clarification)

Review/enrichment sites are **NOT hardcoded**. They are discovered dynamically via SerpAPI search:

```
┌─────────────────────────────────────────────────────────────────┐
│ EnrichmentConfig (database)                                     │
│   search_template: "{name} {brand} tasting notes review"        │
│   target_fields: ["nose_description", "palate_description",     │
│                   "finish_description", "palate_flavors",       │
│                   "primary_aromas", "finish_flavors"]           │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼ Build query with product data
┌─────────────────────────────────────────────────────────────────┐
│ Search Query: "Macallan 18 The Macallan tasting notes review"   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼ SerpAPI search
┌─────────────────────────────────────────────────────────────────┐
│ Discovered URLs (dynamic, not hardcoded):                       │
│   • https://www.whiskyadvocate.com/macallan-18-review          │
│   • https://www.masterofmalt.com/whiskies/macallan-18          │
│   • https://www.thewhiskyexchange.com/p/12345/macallan-18      │
│   • https://scotchnoob.com/2024/macallan-18-sherry-oak         │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼ Fetch & extract from each URL
┌─────────────────────────────────────────────────────────────────┐
│ AIClientV2.extract() for each discovered URL                    │
│ ProductMatchValidator ensures data matches target product       │
│ ConfidenceBasedMerger merges fields from multiple sources       │
└─────────────────────────────────────────────────────────────────┘
```

**Key Point**: The `EnrichmentConfig` defines the **search query pattern**, not the actual sites. SerpAPI returns different URLs each time based on current search rankings.

---

## 2. Architecture

### 2.1 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    CrawlSchedule (category=single_product)       │
│                    search_terms: [                               │
│                      {"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
│                      {"name": "Glenfiddich 21", "brand": "Glenfiddich", "product_type": "whiskey"}
│                    ]                                             │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼ For each product entry
┌─────────────────────────────────────────────────────────────────┐
│                    SingleProductOrchestrator                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Step 1: Duplicate Detection (check before searching)     │   │
│  │   - DuplicateDetector.find_match(name, brand, product_type)  │
│  │   - Returns: (existing_product, match_confidence)        │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                  │
│              ┌────────────────┴────────────────┐                 │
│              │                                 │                 │
│              ▼                                 ▼                 │
│  ┌───────────────────────┐       ┌──────────────────────────┐   │
│  │ NEW PRODUCT           │       │ EXISTING PRODUCT         │   │
│  │                       │       │                          │   │
│  │ Step 2a: Search       │       │ Step 2b: Refresh Search  │   │
│  │ - SerpAPI: "{name}    │       │ - SerpAPI: "{name}       │   │
│  │   {brand} official"   │       │   {brand} review         │   │
│  │ - SerpAPI: "{name}    │       │   {current_year}         │   │
│  │   {brand} review"     │       │   {previous_year}"       │   │
│  │                       │       │                          │   │
│  │ Step 3a: Extract      │       │ Step 3b: Extract         │   │
│  │ - Fetch discovered    │       │ - Fetch discovered       │   │
│  │   URLs                │       │   URLs                   │   │
│  │ - AIClientV2.extract  │       │ - AIClientV2.extract     │   │
│  │ - Full schema         │       │ - Target refresh fields  │   │
│  │                       │       │                          │   │
│  │ Step 4a: Create       │       │ Step 4b: Merge           │   │
│  │ - Create DP record    │       │ - Merge with existing    │   │
│  │ - Run EnrichmentPipelineV3   │ - Confidence-based merge │   │
│  └───────────────────────┘       └──────────────────────────┘   │
│                               │                                  │
│                               ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Step 5: Save & Track                                     │   │
│  │   - Update DiscoveredProduct                             │   │
│  │   - Record source provenance                             │   │
│  │   - Update CrawlJob stats                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Dependencies

```
SingleProductOrchestrator
    ├── SerpAPI (product search & discovery)
    ├── SmartRouter (fetching discovered URLs)
    ├── AIClientV2 (extraction)
    ├── DuplicateDetector (matching)
    ├── QualityGateV3 (assessment)
    ├── EnrichmentPipelineV3 (enrichment)
    │       └── ProductTypeConfig (enrichment limits: max_sources, max_searches)
    ├── ConfidenceBasedMerger (field merging)
    ├── SourceTracker (provenance)
    └── ProductSaver (database persistence)
```

---

## 3. Schedule Configuration

### 3.1 ScheduleCategory Extension

Add new category to `ScheduleCategory` enum:

```python
class ScheduleCategory(models.TextChoices):
    COMPETITION = "competition", "Competition/Awards"
    DISCOVERY = "discovery", "Discovery Search"
    RETAILER = "retailer", "Retailer Monitoring"
    SINGLE_PRODUCT = "single_product", "Single Product Enrichment"  # NEW
```

### 3.2 CrawlSchedule Configuration

For `SINGLE_PRODUCT` category, `search_terms` contains product identifiers (name, brand, product_type):

```json
{
  "name": "Premium Whiskey Products",
  "category": "single_product",
  "search_terms": [
    {"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
    {"name": "Glenfiddich 21 Year Old", "brand": "Glenfiddich", "product_type": "whiskey"},
    {"name": "Lagavulin 16", "brand": "Lagavulin", "product_type": "whiskey"}
  ],
  "enrich": true,
  "frequency": "weekly",
  "config": {
    "focus_recent_reviews": true,
    "max_review_age_days": 365,
    "skip_if_enriched_within_days": 30
  }
}
```

### 3.3 Config Options (CrawlSchedule.config)

These options are specific to the Single Product flow and stored in `CrawlSchedule.config`:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `focus_recent_reviews` | bool | true | Prioritize recent reviews for existing products |
| `max_review_age_days` | int | 365 | Only consider reviews within this age |
| `skip_if_enriched_within_days` | int | 30 | Skip products enriched recently |
| `force_re_extraction` | bool | false | Re-extract even if product exists |

### 3.4 Enrichment Limits (from ProductTypeConfig)

Enrichment resource limits are **NOT** stored in `CrawlSchedule`. They come from `ProductTypeConfig` to maintain consistency across all three flows (Competition, Generic Search, Single Product):

```python
# Loaded by EnrichmentPipelineV3._create_enrichment_session()
config = ProductTypeConfig.objects.get(product_type="whiskey")
```

| Field | V3 Default | Description |
|-------|------------|-------------|
| `max_sources_per_product` | 8 | Max source URLs to fetch per product |
| `max_serpapi_searches` | 6 | Max SerpAPI searches per product |
| `max_enrichment_time_seconds` | 180 | Max time for enrichment |
| `awards_search_enabled` | true | Enable dedicated awards search |
| `awards_search_template` | "{name} {brand} awards..." | Awards search query template |
| `members_only_detection_enabled` | true | Detect members-only sites |

**Why this design?**
- Consistency: All flows use the same limits for the same product type
- Centralized control: Change limits in one place, affects all flows
- Cost control: SerpAPI usage is product-type specific, not schedule-specific

### 3.5 Config Consolidation (Required Refactor)

**Current Issue:** Two overlapping config models exist:
- `ProductTypeConfig` - Base config with lower limits (3 searches, 5 sources)
- `PipelineConfig` - V3 extension with higher limits (6 searches, 8 sources)

**Resolution:** Consolidate into single `ProductTypeConfig` model:

```python
# BEFORE: Two models with overlapping fields
ProductTypeConfig.max_serpapi_searches = 3        # Old default
PipelineConfig.max_serpapi_searches = 6           # V3 default (separate model)

# AFTER: Single model with V3 defaults
ProductTypeConfig.max_serpapi_searches = 6        # Consolidated
ProductTypeConfig.awards_search_enabled = True    # Moved from PipelineConfig
ProductTypeConfig.members_only_detection = True   # Moved from PipelineConfig
```

**Migration Steps:**
1. Add V3 fields to `ProductTypeConfig` (awards, members-only detection)
2. Update defaults to V3 values (6 searches, 8 sources, 180s)
3. Update `EnrichmentPipelineV3` to use consolidated fields
4. Deprecate `PipelineConfig` model
5. Create data migration to move existing PipelineConfig data

---

## 4. Duplicate Detection Strategy

### 4.1 Matching Pipeline

```python
async def find_matching_product(
    extracted_data: Dict[str, Any],
    product_type: str,
) -> Tuple[Optional[DiscoveredProduct], str, float]:
    """
    Find existing product matching extracted data.

    Returns:
        (product, match_method, confidence)
        - product: DiscoveredProduct or None
        - match_method: "gtin" | "fingerprint" | "fuzzy_name" | "none"
        - confidence: 0.0-1.0
    """
    # Level 1: GTIN match (highest confidence)
    if gtin := extracted_data.get("gtin"):
        if product := await match_by_gtin(gtin):
            return product, "gtin", 1.0

    # Level 2: Fingerprint match
    fingerprint = compute_fingerprint(extracted_data)
    if product := await match_by_fingerprint(fingerprint):
        return product, "fingerprint", 0.95

    # Level 3: Fuzzy name match
    if name := extracted_data.get("name"):
        brand = extracted_data.get("brand")
        product, confidence = await match_by_fuzzy_name(
            name, brand, product_type
        )
        if product and confidence >= 0.85:
            return product, "fuzzy_name", confidence

    return None, "none", 0.0
```

### 4.2 Confidence Thresholds

| Threshold | Range | Action |
|-----------|-------|--------|
| HIGH | >= 0.85 | Auto-match, enrich existing product |
| MEDIUM | 0.65-0.84 | Flag for review, proceed with caution |
| LOW | < 0.65 | Create as new product |

---

## 5. Enrichment Strategies

### 5.1 New Product Enrichment

Uses standard `EnrichmentPipelineV3` 2-step flow:

**Step 1: Producer Page (SerpAPI Search)**
```
Query: "{brand} {name} official"
Example: "The Macallan Macallan 18 official"
    ↓ SerpAPI returns dynamic URLs
Discovered: https://www.themacallan.com/whisky/18-years-old
    ↓ Fetch & Extract
Result: Official product data (confidence: 0.85-0.95)
```

**Step 2: Review Sites (SerpAPI Search via EnrichmentConfig templates)**
```
EnrichmentConfig templates (from database):
  - "{name} {brand} tasting notes review"
  - "{name} distillery information production"
  - "{name} {brand} production mash bill cask"

For each template:
    ↓ Build query with product data
Query: "Macallan 18 The Macallan tasting notes review"
    ↓ SerpAPI returns dynamic URLs (not hardcoded!)
Discovered URLs vary by search ranking:
  - whiskyadvocate.com/...
  - scotchnoob.com/...
  - masterofmalt.com/...
    ↓ Fetch & Extract from each
    ↓ ProductMatchValidator ensures correct product
    ↓ ConfidenceBasedMerger combines data
Result: Enriched tasting profile (confidence: 0.7-0.85)
```

### 5.2 Existing Product Enrichment (Refresh)

Modified flow focusing on **recent** data. Uses SerpAPI with time-focused search queries:

```python
class RefreshEnrichmentConfig:
    """Configuration for refreshing existing product data."""

    # Search query templates emphasizing recency (sent to SerpAPI)
    # These are NOT hardcoded URLs - they produce dynamic results
    # {current_year} and {previous_year} are resolved at runtime
    search_templates = [
        "{name} {brand} review {current_year} {previous_year}",  # → Recent reviews
        "{name} tasting notes latest",                            # → Latest content
        "{name} {brand} awards {current_year}",                   # → Recent awards
    ]

    @staticmethod
    def resolve_year_placeholders(template: str) -> str:
        """Replace {current_year} and {previous_year} with actual years."""
        from datetime import datetime
        current_year = datetime.now().year
        return template.replace(
            "{current_year}", str(current_year)
        ).replace(
            "{previous_year}", str(current_year - 1)
        )

    # Fields to always attempt to update
    refresh_priority_fields = [
        "awards",           # New awards may have been won
        "ratings",          # Aggregated ratings change
        "prices",           # Prices fluctuate
        "primary_aromas",   # More reviews = better tasting profile
        "palate_flavors",
        "finish_flavors",
    ]

    # Fields to preserve if already high confidence
    preserve_if_confident = [
        "name",             # Don't change core identity
        "brand",
        "abv",              # Rarely changes
        "volume_ml",
        "age_statement",
    ]
```

### 5.3 Merge Strategy for Existing Products

```python
async def merge_with_existing(
    existing_data: Dict[str, Any],
    existing_confidences: Dict[str, float],
    new_data: Dict[str, Any],
    new_confidences: Dict[str, float],
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Merge new extraction with existing product data.

    Rules:
    1. Higher confidence wins for conflicting fields
    2. Arrays (aromas, flavors) are union-merged with deduplication
    3. Preserved fields only updated if new confidence > existing + threshold
    4. New fields always added
    """
```

---

## 6. Shared Code Blocks

### 6.1 Reusable Components

These components should be extracted/shared across all three flows:

| Component | Location | Used By |
|-----------|----------|---------|
| `SmartRouter` | `crawler/fetchers/smart_router.py` | All flows |
| `AIClientV2` | `crawler/services/ai_client_v2.py` | All flows |
| `QualityGateV3` | `crawler/services/quality_gate_v3.py` | All flows |
| `DuplicateDetector` | `crawler/services/duplicate_detector.py` | All flows |
| `ConfidenceBasedMerger` | `crawler/services/confidence_merger.py` | All flows |
| `EnrichmentPipelineV3` | `crawler/services/enrichment_pipeline_v3.py` | All flows |
| `SourceTracker` | `crawler/services/source_tracker.py` | All flows |
| `ProductSaver` | `crawler/services/product_saver.py` | All flows |

### 6.2 New Shared Components

```python
# crawler/services/product_matcher.py
class ProductMatcher:
    """
    Shared duplicate detection across all discovery flows.
    Wraps DuplicateDetector with flow-specific configuration.
    """

    async def find_or_create(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        source_url: str,
    ) -> Tuple[DiscoveredProduct, bool]:
        """
        Returns (product, is_new)
        """

# crawler/services/refresh_enricher.py
class RefreshEnricher:
    """
    Handles re-enrichment of existing products.
    Used by all flows when product already exists.
    """

    async def refresh_product(
        self,
        existing_product: DiscoveredProduct,
        new_extraction: Dict[str, Any],
        focus_recent: bool = True,
    ) -> EnrichmentResultV3:
        """
        Refresh existing product with new data and recent reviews.
        """
```

---

## 7. Data Models

### 7.1 SingleProductResult

```python
@dataclass
class SingleProductResult:
    """Result from single product processing."""

    success: bool
    product_id: Optional[UUID] = None
    product_name: str = ""

    # Match status
    is_new_product: bool = True
    match_method: str = "none"  # gtin|fingerprint|fuzzy_name|none
    match_confidence: float = 0.0

    # Quality progression
    status_before: str = ""
    status_after: str = ""
    ecp_before: float = 0.0
    ecp_after: float = 0.0

    # Enrichment tracking
    enrichment_completed: bool = False
    fields_enriched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Timing
    extraction_time_seconds: float = 0.0
    enrichment_time_seconds: float = 0.0
    total_time_seconds: float = 0.0

    # Error handling
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
```

### 7.2 SingleProductJobResult

```python
@dataclass
class SingleProductJobResult:
    """Result from processing all products in a single job."""

    job_id: UUID
    schedule_id: UUID

    # Counts
    products_processed: int = 0
    products_new: int = 0
    products_existing: int = 0
    products_enriched: int = 0
    products_failed: int = 0

    # Individual results
    results: List[SingleProductResult] = field(default_factory=list)

    # Timing
    start_time: datetime = None
    end_time: datetime = None
    duration_seconds: float = 0.0

    # Status
    success: bool = True
    errors: List[str] = field(default_factory=list)
```

---

## 8. API & Entry Points

### 8.1 Celery Task

```python
# crawler/tasks.py

@shared_task(bind=True, max_retries=3)
def run_single_product_job(self, schedule_id: str, job_id: str):
    """
    Process all product URLs in a single product schedule.

    Triggered by scheduler when CrawlSchedule.next_run <= now()
    and category == SINGLE_PRODUCT.
    """
    schedule = CrawlSchedule.objects.get(id=schedule_id)
    job = CrawlJob.objects.get(id=job_id)

    orchestrator = SingleProductOrchestrator()
    result = asyncio.run(orchestrator.process_schedule(schedule, job))

    # Update job and schedule stats
    job.complete(result)
    schedule.record_run_stats(result)

    return result.to_dict()
```

### 8.2 Orchestrator Interface

```python
class SingleProductOrchestrator:
    """Orchestrates single product discovery and enrichment."""

    async def process_schedule(
        self,
        schedule: CrawlSchedule,
        job: CrawlJob,
    ) -> SingleProductJobResult:
        """Process all URLs in schedule.search_terms."""

    async def process_single_url(
        self,
        url: str,
        product_type: str,
        config: Dict[str, Any],
    ) -> SingleProductResult:
        """Process a single product URL."""

    async def refresh_existing_product(
        self,
        product: DiscoveredProduct,
        new_data: Dict[str, Any],
        focus_recent: bool = True,
    ) -> SingleProductResult:
        """Refresh an existing product with new data."""
```

---

## 9. Error Handling

### 9.1 Error Categories

| Category | Handling | Retry |
|----------|----------|-------|
| Fetch Error | Log, skip URL, continue | Yes (3x) |
| Extraction Error | Log, skip URL, continue | Yes (3x) |
| Duplicate Ambiguity | Flag for review, skip enrichment | No |
| Enrichment Error | Save partial data, log | Yes (2x) |
| Database Error | Rollback, retry job | Yes (3x) |

### 9.2 Partial Success

Jobs track partial success:
- Individual URL failures don't fail the whole job
- Results include per-URL success/failure status
- Schedule stats updated even on partial failure

---

## 10. Monitoring & Metrics

### 10.1 Tracked Metrics

```python
# CrawlJob metrics
job.products_processed = total_urls
job.products_new = new_count
job.products_duplicate = existing_count
job.products_verified = enriched_count
job.errors = error_count

# CrawlSchedule cumulative metrics
schedule.total_runs += 1
schedule.total_products_found += total_urls
schedule.total_products_new += new_count
schedule.total_products_duplicate += existing_count
schedule.total_products_verified += enriched_count
schedule.total_errors += error_count
```

### 10.2 Logging

```python
logger.info(
    "SingleProduct processed: url=%s, is_new=%s, match=%s (%.2f), "
    "status=%s->%s, ecp=%.1f%%->%.1f%%, time=%.1fs",
    url, is_new, match_method, match_confidence,
    status_before, status_after, ecp_before, ecp_after, total_time
)
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

- `test_single_product_orchestrator.py` - Core orchestrator logic
- `test_product_matcher.py` - Duplicate detection
- `test_refresh_enricher.py` - Existing product refresh
- `test_merge_strategies.py` - Data merging logic

### 11.2 Integration Tests

- `test_single_product_flow.py` - Full flow with mocked external services
- `test_schedule_integration.py` - CrawlSchedule → Job → Orchestrator

### 11.3 E2E Tests

- `test_single_product_e2e.py` - Full flow with real external services

---

## 12. Migration Path

### 12.1 Database Migration

```python
# 0045_add_single_product_schedule.py

def forwards(apps, schema_editor):
    # Update ScheduleCategory choices to include SINGLE_PRODUCT
    pass  # Handled by Django migrations on model change
```

### 12.2 Backward Compatibility

- Existing schedules unaffected
- New category only processed by new task handler
- Shared components remain compatible with existing flows

---

## 13. References

- **ENRICHMENT_PIPELINE_V3_SPEC.md** - 2-step enrichment pipeline
- **GENERIC_SEARCH_V3_SPEC.md** - Generic search discovery flow
- **DUPLICATE_CRAWLING_FIXES.md** - Deduplication strategy
- **crawler/models.py:1374-1585** - CrawlSchedule model
- **crawler/services/enrichment_pipeline_v3.py** - EnrichmentPipelineV3
- **crawler/services/duplicate_detector.py** - DuplicateDetector
