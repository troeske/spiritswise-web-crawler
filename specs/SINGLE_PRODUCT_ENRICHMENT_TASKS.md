# Single Product Enrichment Flow - Task List

**Spec Reference:** `specs/SINGLE_PRODUCT_ENRICHMENT_SPEC.md`
**Created:** 2026-01-13
**Status:** In Progress

---

## Progress Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 0: Config Consolidation | 4 | 4 | Complete |
| Phase 1: Infrastructure | 5 | 5 | Complete |
| Phase 2: Duplicate Detection | 4 | 4 | Complete |
| Phase 3: Orchestrator Core | 5 | 5 | Complete |
| Phase 4: Refresh Enrichment | 4 | 4 | Complete |
| Phase 5: Integration | 4 | 4 | Complete |
| Phase 6: Testing | 4 | 4 | Complete |
| **Total** | **30** | **30** | **100%** |

---

## Phase 0: Config Consolidation (Prerequisite)

> **Why Phase 0?** Currently `ProductTypeConfig` and `PipelineConfig` have overlapping fields with different defaults. This causes confusion and inconsistency. Consolidating before building Single Product flow ensures all three flows use the same config.

### Task 0.1: Add V3 Fields to ProductTypeConfig
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.5

**Description:**
Add V3-specific fields from `PipelineConfig` to `ProductTypeConfig` model.

**Test First (Red):**
```python
# crawler/tests/unit/test_product_type_config.py
def test_product_type_config_has_v3_fields():
    from crawler.models import ProductTypeConfig

    # V3 limit fields
    assert hasattr(ProductTypeConfig, 'max_serpapi_searches')
    assert hasattr(ProductTypeConfig, 'max_sources_per_product')
    assert hasattr(ProductTypeConfig, 'max_enrichment_time_seconds')

    # V3 feature fields (moved from PipelineConfig)
    assert hasattr(ProductTypeConfig, 'awards_search_enabled')
    assert hasattr(ProductTypeConfig, 'awards_search_template')
    assert hasattr(ProductTypeConfig, 'members_only_detection_enabled')
    assert hasattr(ProductTypeConfig, 'members_only_patterns')
```

**Implementation:**
- [ ] Add fields to `ProductTypeConfig` model:
  - `awards_search_enabled` (BooleanField, default=True)
  - `awards_search_template` (CharField)
  - `members_only_detection_enabled` (BooleanField, default=True)
  - `members_only_patterns` (JSONField)
- [ ] Update defaults to V3 values:
  - `max_serpapi_searches`: 3 → 6
  - `max_sources_per_product`: 5 → 8
  - `max_enrichment_time_seconds`: 120 → 180
- [ ] Create migration

**Acceptance Criteria:**
- [ ] ProductTypeConfig has all V3 fields
- [ ] Defaults match V3 spec (6 searches, 8 sources, 180s)

---

### Task 0.2: Create Data Migration for Existing PipelineConfig Data
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.5

**Description:**
Migrate existing data from `PipelineConfig` to `ProductTypeConfig`.

**Test First (Red):**
```python
# crawler/tests/unit/test_config_migration.py
@pytest.mark.django_db
def test_pipeline_config_data_migrated():
    # Create ProductTypeConfig with old defaults
    ptc = ProductTypeConfig.objects.create(
        product_type="whiskey",
        max_serpapi_searches=3,  # Old default
    )

    # Create PipelineConfig with V3 values
    PipelineConfig.objects.create(
        product_type_config=ptc,
        max_serpapi_searches=6,
        awards_search_enabled=True,
    )

    # Run migration
    migrate_pipeline_config_data()

    # Verify data moved to ProductTypeConfig
    ptc.refresh_from_db()
    assert ptc.max_serpapi_searches == 6
    assert ptc.awards_search_enabled == True
```

**Implementation:**
- [ ] Create data migration function `migrate_pipeline_config_data()`
- [ ] For each PipelineConfig, copy fields to parent ProductTypeConfig
- [ ] Handle cases where ProductTypeConfig already has values (prefer PipelineConfig)
- [ ] Create Django migration file

**Acceptance Criteria:**
- [ ] All PipelineConfig data copied to ProductTypeConfig
- [ ] No data loss during migration

---

### Task 0.3: Update EnrichmentPipelineV3 to Use Consolidated Config
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.5

**Description:**
Update `EnrichmentPipelineV3._create_enrichment_session()` to read from consolidated `ProductTypeConfig`.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_enrichment_pipeline_v3.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_uses_v3_defaults():
    # Create ProductTypeConfig with V3 defaults
    ProductTypeConfig.objects.create(
        product_type="whiskey",
        max_serpapi_searches=6,
        max_sources_per_product=8,
        max_enrichment_time_seconds=180,
    )

    pipeline = EnrichmentPipelineV3()
    session = await pipeline._create_enrichment_session(
        product_type="whiskey",
        initial_data={"name": "Test"}
    )

    assert session.max_searches == 6
    assert session.max_sources == 8
    assert session.max_time_seconds == 180.0
```

**Implementation:**
- [ ] Update `_create_enrichment_session()` to read V3 fields from ProductTypeConfig
- [ ] Remove any references to PipelineConfig in EnrichmentPipelineV3
- [ ] Ensure fallback to V3 defaults if ProductTypeConfig not found

**Acceptance Criteria:**
- [ ] EnrichmentPipelineV3 uses consolidated config
- [ ] V3 defaults (6, 8, 180) are used

---

### Task 0.4: Deprecate PipelineConfig Model
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.5

**Description:**
Mark `PipelineConfig` as deprecated and update any remaining references.

**Test First (Red):**
```python
# crawler/tests/unit/test_pipeline_config_deprecated.py
def test_pipeline_config_deprecated():
    import warnings
    from crawler.models import PipelineConfig

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Any usage should trigger deprecation warning
        _ = PipelineConfig._meta.verbose_name
        assert any("deprecated" in str(warning.message).lower() for warning in w)
```

**Implementation:**
- [ ] Add deprecation warning to PipelineConfig class
- [ ] Update `EnrichmentOrchestratorV3` to use ProductTypeConfig
- [ ] Search codebase for any remaining PipelineConfig references
- [ ] Update fixtures to remove PipelineConfig data (move to ProductTypeConfig)
- [ ] Add comment documenting removal timeline

**Acceptance Criteria:**
- [ ] Deprecation warning on PipelineConfig usage
- [ ] No active code paths use PipelineConfig
- [ ] All flows use consolidated ProductTypeConfig

---

## Phase 1: Infrastructure Setup

### Task 1.1: Add SINGLE_PRODUCT to ScheduleCategory
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.1

**Description:**
Add `SINGLE_PRODUCT = "single_product", "Single Product Enrichment"` to the ScheduleCategory enum.

**Test First (Red):**
```python
# crawler/tests/unit/test_schedule_category.py
def test_single_product_category_exists():
    from crawler.models import ScheduleCategory
    assert hasattr(ScheduleCategory, 'SINGLE_PRODUCT')
    assert ScheduleCategory.SINGLE_PRODUCT.value == "single_product"
```

**Implementation:**
- [ ] Add enum value to `crawler/models.py:ScheduleCategory`
- [ ] Create migration if needed
- [ ] Verify admin displays new category

**Acceptance Criteria:**
- [ ] Unit test passes
- [ ] Django admin shows new category option

---

### Task 1.2: Extend CrawlSchedule.config for Single Product Options
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.3

**Description:**
Document and validate the config schema for SINGLE_PRODUCT schedules.

**Test First (Red):**
```python
# crawler/tests/unit/test_crawl_schedule_config.py
def test_single_product_config_defaults():
    config = get_single_product_config_defaults()
    assert config["focus_recent_reviews"] == True
    assert config["max_review_age_days"] == 365
    assert config["skip_if_enriched_within_days"] == 30
```

**Implementation:**
- [ ] Create `get_single_product_config_defaults()` utility
- [ ] Add config validation in CrawlSchedule.clean()
- [ ] Document config options in docstring

**Acceptance Criteria:**
- [ ] Config defaults function works
- [ ] Invalid configs raise ValidationError

---

### Task 1.3: Create SingleProductResult Dataclass
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 7.1

**Description:**
Create the `SingleProductResult` dataclass for tracking individual product processing results.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_result.py
def test_single_product_result_defaults():
    result = SingleProductResult(success=True)
    assert result.is_new_product == True
    assert result.match_method == "none"
    assert result.match_confidence == 0.0
    assert result.fields_enriched == []
```

**Implementation:**
- [ ] Create dataclass in `crawler/services/single_product_orchestrator.py`
- [ ] Include all fields from spec Section 7.1
- [ ] Add `to_dict()` method for serialization

**Acceptance Criteria:**
- [ ] Dataclass instantiates with correct defaults
- [ ] Serialization works for JSON export

---

### Task 1.4: Create SingleProductJobResult Dataclass
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 7.2

**Description:**
Create the `SingleProductJobResult` dataclass for tracking job-level results.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_job_result.py
def test_single_product_job_result_aggregation():
    result = SingleProductJobResult(
        job_id=uuid4(),
        schedule_id=uuid4(),
    )
    result.add_result(SingleProductResult(success=True, is_new_product=True))
    result.add_result(SingleProductResult(success=True, is_new_product=False))
    assert result.products_processed == 2
    assert result.products_new == 1
    assert result.products_existing == 1
```

**Implementation:**
- [ ] Create dataclass in `crawler/services/single_product_orchestrator.py`
- [ ] Add `add_result()` method for aggregation
- [ ] Add timing calculation on finalize

**Acceptance Criteria:**
- [ ] Job result correctly aggregates individual results
- [ ] Timing tracked correctly

---

### Task 1.5: Add Celery Task Skeleton
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 8.1

**Description:**
Create the Celery task `run_single_product_job` that will be triggered by the scheduler.

**Test First (Red):**
```python
# crawler/tests/unit/test_tasks_single_product.py
@pytest.mark.django_db
def test_run_single_product_job_task_exists():
    from crawler.tasks import run_single_product_job
    assert callable(run_single_product_job)
    assert run_single_product_job.name == "crawler.tasks.run_single_product_job"
```

**Implementation:**
- [ ] Add task to `crawler/tasks.py`
- [ ] Implement skeleton that calls orchestrator
- [ ] Add proper error handling and retries

**Acceptance Criteria:**
- [ ] Task is registered in Celery
- [ ] Task handles schedule/job lookup

---

## Phase 2: Duplicate Detection Enhancement

### Task 2.1: Create ProductMatcher Service
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 4.1, 6.2

**Description:**
Create a shared `ProductMatcher` service that wraps duplicate detection for all flows.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_product_matcher.py
@pytest.mark.django_db
async def test_product_matcher_finds_gtin_match():
    # Create existing product with GTIN
    existing = await create_discovered_product(gtin="1234567890123")

    matcher = ProductMatcher()
    product, method, confidence = await matcher.find_match(
        {"gtin": "1234567890123", "name": "Test Product"},
        product_type="whiskey"
    )

    assert product.id == existing.id
    assert method == "gtin"
    assert confidence == 1.0
```

**Implementation:**
- [ ] Create `crawler/services/product_matcher.py`
- [ ] Implement `find_match()` with 3-level pipeline
- [ ] Implement `find_or_create()` convenience method
- [ ] Add logging for match decisions

**Acceptance Criteria:**
- [ ] GTIN matching works (confidence 1.0)
- [ ] Fingerprint matching works (confidence 0.95)
- [ ] Fuzzy name matching works with threshold

---

### Task 2.2: Add Fuzzy Name Matching with Brand Filter
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 4.1

**Description:**
Enhance fuzzy name matching to consider brand as a filter for better accuracy.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_product_matcher.py
@pytest.mark.django_db
async def test_fuzzy_match_same_brand():
    # Create "Macallan 18" by "The Macallan"
    existing = await create_discovered_product(
        name="Macallan 18 Year Old Sherry Oak",
        brand="The Macallan"
    )

    matcher = ProductMatcher()
    product, method, confidence = await matcher.find_match(
        {"name": "The Macallan 18", "brand": "The Macallan"},
        product_type="whiskey"
    )

    assert product.id == existing.id
    assert method == "fuzzy_name"
    assert confidence >= 0.85

async def test_fuzzy_match_different_brand_no_match():
    # Create "Macallan 18" by "The Macallan"
    existing = await create_discovered_product(
        name="Macallan 18",
        brand="The Macallan"
    )

    matcher = ProductMatcher()
    product, method, confidence = await matcher.find_match(
        {"name": "Macallan 18", "brand": "Glenfiddich"},  # Wrong brand!
        product_type="whiskey"
    )

    assert product is None  # Should not match due to brand mismatch
```

**Implementation:**
- [ ] Add brand-aware fuzzy matching
- [ ] Weight brand match in confidence calculation
- [ ] Add product_type filter to narrow candidates

**Acceptance Criteria:**
- [ ] Same brand boosts confidence
- [ ] Different brand lowers confidence significantly
- [ ] Product type filters candidates

---

### Task 2.3: Integrate ProductMatcher into Competition Flow
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 6.1

**Description:**
Refactor Competition flow to use shared ProductMatcher.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_competition_orchestrator_v2.py
@pytest.mark.django_db
async def test_competition_uses_product_matcher():
    # Create existing product
    existing = await create_discovered_product(name="Test Whiskey", brand="TestBrand")

    orchestrator = CompetitionOrchestratorV2(product_matcher=ProductMatcher())
    result = await orchestrator.process_award(
        award_data={"name": "Test Whiskey", "brand": "TestBrand", "medal": "Gold"}
    )

    # Should have matched existing product
    assert result.product_id == existing.id
    assert result.is_update == True
```

**Implementation:**
- [ ] Inject ProductMatcher into CompetitionOrchestratorV2
- [ ] Use matcher instead of direct duplicate checks
- [ ] Ensure backward compatibility

**Acceptance Criteria:**
- [ ] Competition flow uses ProductMatcher
- [ ] Existing tests still pass

---

### Task 2.4: Integrate ProductMatcher into Generic Search Flow
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 6.1

**Description:**
Refactor Generic Search flow to use shared ProductMatcher.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_discovery_orchestrator_v2.py
@pytest.mark.django_db
async def test_discovery_uses_product_matcher():
    # Create existing product
    existing = await create_discovered_product(name="Test Whiskey", brand="TestBrand")

    orchestrator = DiscoveryOrchestratorV2(product_matcher=ProductMatcher())
    result = await orchestrator.extract_single_product(
        url="https://example.com/product",
        product_type="whiskey"
    )

    # Should have matched existing product
    assert result.product_id == existing.id
```

**Implementation:**
- [ ] Inject ProductMatcher into DiscoveryOrchestratorV2
- [ ] Use matcher for duplicate detection
- [ ] Ensure backward compatibility

**Acceptance Criteria:**
- [ ] Discovery flow uses ProductMatcher
- [ ] Existing tests still pass

---

## Phase 3: Single Product Orchestrator Core

### Task 3.1: Create SingleProductOrchestrator Class
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 8.2

**Description:**
Create the main orchestrator class with dependency injection.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
def test_orchestrator_initialization():
    orchestrator = SingleProductOrchestrator()
    assert orchestrator.ai_client is not None
    assert orchestrator.quality_gate is not None
    assert orchestrator.product_matcher is not None
    assert orchestrator.enrichment_pipeline is not None
```

**Implementation:**
- [ ] Create `crawler/services/single_product_orchestrator.py`
- [ ] Implement `__init__` with dependency injection
- [ ] Add lazy initialization for expensive components

**Acceptance Criteria:**
- [ ] Orchestrator initializes with all dependencies
- [ ] Dependencies can be mocked for testing

---

### Task 3.2: Implement Product Search & Discovery
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 2.1 (Step 2a/2b)

**Description:**
Implement the search step that discovers relevant URLs for a product using SerpAPI.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
@pytest.mark.asyncio
async def test_search_for_product_sources(mock_serpapi):
    mock_serpapi.search.return_value = [
        "https://www.themacallan.com/whisky/18-years-old",
        "https://www.whiskyadvocate.com/macallan-18-review",
        "https://www.masterofmalt.com/whiskies/macallan-18",
    ]

    orchestrator = SingleProductOrchestrator(serpapi=mock_serpapi)

    urls = await orchestrator._search_for_product(
        name="Macallan 18",
        brand="The Macallan",
        product_type="whiskey",
        focus_recent=False
    )

    assert len(urls) >= 1
    mock_serpapi.search.assert_called()

@pytest.mark.asyncio
async def test_search_for_product_recent_focus(mock_serpapi):
    orchestrator = SingleProductOrchestrator(serpapi=mock_serpapi)

    await orchestrator._search_for_product(
        name="Macallan 18",
        brand="The Macallan",
        product_type="whiskey",
        focus_recent=True  # Should add year filters
    )

    # Verify search query includes current/previous year (dynamic)
    from datetime import datetime
    current_year = str(datetime.now().year)
    previous_year = str(datetime.now().year - 1)

    call_args = mock_serpapi.search.call_args
    query = call_args[0][0]
    assert current_year in query or previous_year in query
```

**Implementation:**
- [ ] Implement `_search_for_product()` method
- [ ] Build search query: `"{name} {brand} official"` for new products
- [ ] Build search query: `"{name} {brand} review 2024 2025"` for refresh
- [ ] Call SerpAPI and return discovered URLs
- [ ] Filter/prioritize URLs (official sites first)

**Acceptance Criteria:**
- [ ] Successfully discovers URLs via SerpAPI
- [ ] Recent focus adds year filters to query
- [ ] URLs are prioritized (official > reviews > retailers)

---

### Task 3.3: Implement process_product_entry Method
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 2.1, 8.2

**Description:**
Implement the main entry point for processing a single product entry (name/brand/product_type).

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_process_product_entry_new_product(mock_dependencies):
    orchestrator = SingleProductOrchestrator(**mock_dependencies)

    result = await orchestrator.process_product_entry(
        product_entry={"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
        config={}
    )

    assert result.success == True
    assert result.is_new_product == True
    assert result.product_id is not None
    assert result.product_name == "Macallan 18"
    assert result.status_after in ["partial", "baseline", "enriched", "complete"]

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_process_product_entry_existing_product(mock_dependencies):
    # Create existing product
    existing = await create_discovered_product(name="Macallan 18", brand="The Macallan")

    orchestrator = SingleProductOrchestrator(**mock_dependencies)
    result = await orchestrator.process_product_entry(
        product_entry={"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
        config={"focus_recent_reviews": True}
    )

    assert result.success == True
    assert result.is_new_product == False
    assert result.product_id == existing.id
    assert result.match_method in ["gtin", "fingerprint", "fuzzy_name"]
```

**Implementation:**
- [ ] Implement full `process_product_entry()` flow:
  1. Check for existing product via ProductMatcher
  2. If new: search via SerpAPI, extract, create, enrich
  3. If existing: search for recent data, extract, merge
- [ ] Call `_search_for_product()` with appropriate focus
- [ ] Fetch and extract from discovered URLs
- [ ] Call enrichment pipeline or refresh enricher
- [ ] Save results
- [ ] Return SingleProductResult

**Acceptance Criteria:**
- [ ] New products are discovered, created, and enriched
- [ ] Existing products are found and refreshed with recent data
- [ ] Results include all tracking data

---

### Task 3.4: Implement process_schedule Method
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 8.2

**Description:**
Implement the method that processes all product entries in a schedule's search_terms.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_process_schedule_multiple_products(mock_dependencies):
    schedule = await create_crawl_schedule(
        category="single_product",
        search_terms=[
            {"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
            {"name": "Glenfiddich 21", "brand": "Glenfiddich", "product_type": "whiskey"},
            {"name": "Lagavulin 16", "brand": "Lagavulin", "product_type": "whiskey"},
        ]
    )
    job = await create_crawl_job(schedule=schedule)

    orchestrator = SingleProductOrchestrator(**mock_dependencies)
    result = await orchestrator.process_schedule(schedule, job)

    assert result.products_processed == 3
    assert len(result.results) == 3
    assert result.success == True
```

**Implementation:**
- [ ] Implement `process_schedule()` method
- [ ] Parse search_terms as list of product entries
- [ ] Iterate through product entries
- [ ] Call `process_product_entry()` for each
- [ ] Handle partial failures (continue on individual errors)
- [ ] Aggregate results into SingleProductJobResult
- [ ] Track timing

**Acceptance Criteria:**
- [ ] All product entries in search_terms are processed
- [ ] Partial failures don't fail entire job
- [ ] Results aggregated correctly

---

### Task 3.5: Implement Skip Logic for Recently Enriched Products
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 3.3

**Description:**
Implement logic to skip products that were enriched recently based on config.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_skip_recently_enriched(mock_dependencies):
    # Create existing product enriched 10 days ago
    existing = await create_discovered_product(
        name="Test", brand="Test",
        last_enrichment_at=timezone.now() - timedelta(days=10)
    )

    orchestrator = SingleProductOrchestrator(**mock_dependencies)
    result = await orchestrator.process_single_url(
        url="https://example.com/existing-product",
        product_type="whiskey",
        config={"skip_if_enriched_within_days": 30}
    )

    # Should skip enrichment
    assert result.success == True
    assert result.enrichment_completed == False
    assert "skipped_recent_enrichment" in result.warnings

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_enrich_if_not_recent(mock_dependencies):
    # Create existing product enriched 60 days ago
    existing = await create_discovered_product(
        name="Test", brand="Test",
        last_enrichment_at=timezone.now() - timedelta(days=60)
    )

    orchestrator = SingleProductOrchestrator(**mock_dependencies)
    result = await orchestrator.process_single_url(
        url="https://example.com/existing-product",
        product_type="whiskey",
        config={"skip_if_enriched_within_days": 30}
    )

    # Should enrich
    assert result.enrichment_completed == True
```

**Implementation:**
- [ ] Check `last_enrichment_at` field on existing products
- [ ] Compare with `skip_if_enriched_within_days` config
- [ ] Skip enrichment if within window
- [ ] Add warning to result

**Acceptance Criteria:**
- [ ] Recently enriched products are skipped
- [ ] Old products are re-enriched
- [ ] Warnings track skipped products

---

## Phase 4: Refresh Enrichment for Existing Products

### Task 4.1: Create RefreshEnricher Service
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 5.2, 6.2

**Description:**
Create the `RefreshEnricher` service that handles re-enrichment of existing products with focus on recent data.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_refresh_enricher.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_refresh_enricher_recent_reviews():
    existing = await create_discovered_product(
        name="Test Whiskey",
        brand="TestBrand",
        primary_aromas=["vanilla", "oak"]
    )

    refresher = RefreshEnricher()
    result = await refresher.refresh_product(
        existing_product=existing,
        new_extraction={"primary_aromas": ["vanilla", "oak", "honey"]},
        focus_recent=True
    )

    # Should have merged aromas
    assert "honey" in result.product_data["primary_aromas"]
    assert result.fields_enriched == ["primary_aromas"]
```

**Implementation:**
- [ ] Create `crawler/services/refresh_enricher.py`
- [ ] Implement `refresh_product()` method
- [ ] Use recent-focused search templates
- [ ] Merge with existing data using ConfidenceBasedMerger

**Acceptance Criteria:**
- [ ] Existing data is preserved
- [ ] New data is merged appropriately
- [ ] Recent reviews are prioritized

---

### Task 4.2: Implement Recent Review Search Templates
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 5.2

**Description:**
Create search templates that focus on recent reviews and data.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_refresh_enricher.py
def test_recent_review_search_templates():
    from crawler.services.refresh_enricher import get_recent_search_templates

    templates = get_recent_search_templates(2025)
    assert any("2024" in t or "2025" in t for t in templates)
    assert any("latest" in t.lower() for t in templates)
    assert any("recent" in t.lower() for t in templates)
```

**Implementation:**
- [ ] Create search templates with year filters
- [ ] Include "latest", "recent", "new" keywords
- [ ] Support configurable year range

**Acceptance Criteria:**
- [ ] Templates include current/recent years
- [ ] Templates prioritize recent content

---

### Task 4.3: Implement Confidence-Aware Merge for Refresh
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 5.3

**Description:**
Implement merge logic that respects existing confidence scores and preserves high-confidence fields.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_refresh_enricher.py
@pytest.mark.asyncio
async def test_preserve_high_confidence_fields():
    existing_data = {"name": "Macallan 18", "abv": 43.0}
    existing_confidences = {"name": 0.95, "abv": 0.90}

    new_data = {"name": "The Macallan 18 Years", "abv": 43.0, "awards": ["Gold"]}
    new_confidences = {"name": 0.80, "abv": 0.80, "awards": 0.85}

    refresher = RefreshEnricher()
    merged, confidences = await refresher._merge_with_existing(
        existing_data, existing_confidences,
        new_data, new_confidences
    )

    # Name should be preserved (existing confidence higher)
    assert merged["name"] == "Macallan 18"
    # Awards should be added (new field)
    assert merged["awards"] == ["Gold"]

@pytest.mark.asyncio
async def test_merge_array_fields():
    existing_data = {"primary_aromas": ["vanilla", "oak"]}
    new_data = {"primary_aromas": ["oak", "honey", "spice"]}

    refresher = RefreshEnricher()
    merged, _ = await refresher._merge_with_existing(
        existing_data, {"primary_aromas": 0.7},
        new_data, {"primary_aromas": 0.8}
    )

    # Should union-merge arrays
    assert set(merged["primary_aromas"]) == {"vanilla", "oak", "honey", "spice"}
```

**Implementation:**
- [ ] Compare confidence scores for conflicting fields
- [ ] Implement array union-merge with deduplication
- [ ] Apply preservation rules for identity fields
- [ ] Track which fields were updated

**Acceptance Criteria:**
- [ ] High-confidence fields preserved
- [ ] Arrays merged correctly
- [ ] New fields always added

---

### Task 4.4: Integrate RefreshEnricher into SingleProductOrchestrator
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 2.1

**Description:**
Wire up RefreshEnricher for the "existing product" branch in the orchestrator.

**Test First (Red):**
```python
# crawler/tests/unit/services/test_single_product_orchestrator.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_orchestrator_uses_refresh_enricher(mock_dependencies):
    existing = await create_discovered_product(
        name="Test Whiskey",
        brand="TestBrand",
        status="partial",
        ecp_total=25.0
    )

    orchestrator = SingleProductOrchestrator(**mock_dependencies)
    result = await orchestrator.process_single_url(
        url="https://example.com/existing",
        product_type="whiskey",
        config={"focus_recent_reviews": True}
    )

    assert result.is_new_product == False
    assert result.ecp_after > result.ecp_before
```

**Implementation:**
- [ ] Inject RefreshEnricher into orchestrator
- [ ] Call refresh_product() for existing products
- [ ] Pass config options (focus_recent_reviews, etc.)

**Acceptance Criteria:**
- [ ] Existing products use RefreshEnricher
- [ ] Config options respected

---

## Phase 5: Integration & Task Wiring

### Task 5.1: Integrate Celery Task with Orchestrator
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 8.1

**Description:**
Complete the Celery task to call orchestrator and handle results.

**Test First (Red):**
```python
# crawler/tests/unit/test_tasks_single_product.py
@pytest.mark.django_db
def test_run_single_product_job_success(mock_orchestrator):
    schedule = create_crawl_schedule(
        category="single_product",
        search_terms=["https://example.com/product"]
    )
    job = create_crawl_job(schedule=schedule)

    with patch('crawler.tasks.SingleProductOrchestrator', return_value=mock_orchestrator):
        result = run_single_product_job(str(schedule.id), str(job.id))

    assert result["success"] == True
    job.refresh_from_db()
    assert job.status == "completed"
```

**Implementation:**
- [ ] Complete task implementation
- [ ] Handle async orchestrator call
- [ ] Update job status on completion
- [ ] Update schedule stats
- [ ] Handle errors with retry

**Acceptance Criteria:**
- [ ] Task successfully calls orchestrator
- [ ] Job and schedule updated with stats
- [ ] Errors trigger retries

---

### Task 5.2: Add Schedule Dispatcher for SINGLE_PRODUCT
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 8.1

**Description:**
Update the schedule dispatcher to route SINGLE_PRODUCT schedules to the new task.

**Test First (Red):**
```python
# crawler/tests/unit/test_schedule_dispatcher.py
@pytest.mark.django_db
def test_dispatcher_routes_single_product():
    schedule = create_crawl_schedule(category="single_product")

    task = get_task_for_schedule(schedule)

    assert task == run_single_product_job
```

**Implementation:**
- [ ] Update dispatcher logic in `check_due_sources` or equivalent
- [ ] Route SINGLE_PRODUCT to `run_single_product_job`
- [ ] Ensure existing routes unchanged

**Acceptance Criteria:**
- [ ] SINGLE_PRODUCT schedules routed correctly
- [ ] Other categories unaffected

---

### Task 5.3: Update CrawlJob to Track Single Product Metrics
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 10.1

**Description:**
Ensure CrawlJob model tracks single product specific metrics.

**Test First (Red):**
```python
# crawler/tests/unit/test_crawl_job_metrics.py
@pytest.mark.django_db
def test_crawl_job_records_single_product_stats():
    job = create_crawl_job()

    result = SingleProductJobResult(
        job_id=job.id,
        schedule_id=job.schedule_id,
        products_processed=5,
        products_new=3,
        products_existing=2,
        products_enriched=4,
    )

    job.complete_with_result(result)
    job.refresh_from_db()

    assert job.products_processed == 5
    assert job.products_new == 3
    assert job.products_duplicate == 2
    assert job.products_verified == 4
```

**Implementation:**
- [ ] Add method to record result on CrawlJob
- [ ] Map SingleProductJobResult fields to CrawlJob fields
- [ ] Update status appropriately

**Acceptance Criteria:**
- [ ] Job tracks all relevant metrics
- [ ] Status updated correctly

---

### Task 5.4: Update CrawlSchedule Stats Recording
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 10.1

**Description:**
Ensure CrawlSchedule accumulates stats from single product jobs.

**Test First (Red):**
```python
# crawler/tests/unit/test_crawl_schedule_stats.py
@pytest.mark.django_db
def test_schedule_accumulates_stats():
    schedule = create_crawl_schedule(
        total_runs=5,
        total_products_found=100
    )

    result = SingleProductJobResult(
        products_processed=10,
        products_new=6,
        products_existing=4,
    )

    schedule.record_run_stats(result)
    schedule.refresh_from_db()

    assert schedule.total_runs == 6
    assert schedule.total_products_found == 110
    assert schedule.total_products_new == 6  # Incremented
```

**Implementation:**
- [ ] Extend `record_run_stats()` for SingleProductJobResult
- [ ] Accumulate stats correctly
- [ ] Update next_run timestamp

**Acceptance Criteria:**
- [ ] Stats accumulated correctly
- [ ] Works for all result types

---

## Phase 6: Testing

### Task 6.1: Create Unit Test Suite
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 11.1

**Description:**
Create comprehensive unit test coverage for all new components.

**Test Files:**
- [ ] `crawler/tests/unit/services/test_single_product_orchestrator.py`
- [ ] `crawler/tests/unit/services/test_product_matcher.py`
- [ ] `crawler/tests/unit/services/test_refresh_enricher.py`
- [ ] `crawler/tests/unit/test_tasks_single_product.py`

**Coverage Requirements:**
- [ ] > 80% line coverage for new code
- [ ] All public methods tested
- [ ] Error cases tested

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Coverage meets threshold

---

### Task 6.2: Create Integration Test Suite
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 11.2

**Description:**
Create integration tests with mocked external services.

**Test File:** `tests/e2e/flows/test_single_product_flow.py`

**Scenarios:**
- [ ] New product creation and enrichment
- [ ] Existing product detection and refresh
- [ ] Multiple URLs in single schedule
- [ ] Error handling and partial failures
- [ ] Skip recently enriched products

**Acceptance Criteria:**
- [ ] All integration tests pass
- [ ] Tests cover main flow paths

---

### Task 6.3: Create E2E Test with Real Services
**Status:** Complete
**Subagent:** `implementer`
**TDD:** Yes
**Spec Reference:** Section 11.3

**Description:**
Create E2E test that hits real external services.

**Test File:** `tests/e2e/flows/test_single_product_e2e.py`

**Scenarios:**
- [ ] Real product URL extraction
- [ ] Real SerpAPI search
- [ ] Real AI extraction
- [ ] Full enrichment flow

**Acceptance Criteria:**
- [ ] E2E test passes with real services
- [ ] Results exported to JSON

---

### Task 6.4: Verify Shared Code Doesn't Break Existing Flows
**Status:** Complete
**Subagent:** `test-runner`
**TDD:** N/A
**Spec Reference:** Section 12.2

**Description:**
Run all existing test suites to ensure shared code changes don't break Competition or Generic Search flows.

**Test Suites:**
- [ ] `pytest tests/e2e/flows/test_competition_flow.py`
- [ ] `pytest tests/e2e/flows/test_generic_search_v3_e2e.py`
- [ ] `pytest crawler/tests/unit/services/test_competition_orchestrator_v2.py`
- [ ] `pytest crawler/tests/unit/services/test_discovery_orchestrator_v2.py`

**Acceptance Criteria:**
- [ ] All existing tests pass
- [ ] No regressions introduced

---

## Task Dependencies

```
Phase 1 (Infrastructure)
    └── Task 1.1 (ScheduleCategory)
    └── Task 1.2 (Config)
    └── Task 1.3 (Result dataclass)
    └── Task 1.4 (JobResult dataclass)
    └── Task 1.5 (Celery task skeleton)

Phase 2 (Duplicate Detection) - depends on Phase 1
    └── Task 2.1 (ProductMatcher) - core component
        └── Task 2.2 (Fuzzy matching) - enhancement
        └── Task 2.3 (Competition integration) - parallel
        └── Task 2.4 (Discovery integration) - parallel

Phase 3 (Orchestrator) - depends on Phase 2.1
    └── Task 3.1 (Class skeleton)
        └── Task 3.2 (Fetch & Extract)
        └── Task 3.3 (process_single_url) - depends on 3.2
        └── Task 3.4 (process_schedule) - depends on 3.3
        └── Task 3.5 (Skip logic) - depends on 3.3

Phase 4 (Refresh Enrichment) - depends on Phase 3.3
    └── Task 4.1 (RefreshEnricher)
        └── Task 4.2 (Search templates)
        └── Task 4.3 (Merge logic)
        └── Task 4.4 (Integration) - depends on 4.1-4.3

Phase 5 (Integration) - depends on Phase 3, 4
    └── Task 5.1 (Celery task complete)
    └── Task 5.2 (Dispatcher)
    └── Task 5.3 (Job metrics)
    └── Task 5.4 (Schedule stats)

Phase 6 (Testing) - depends on all phases
    └── Task 6.1 (Unit tests) - parallel with development
    └── Task 6.2 (Integration tests)
    └── Task 6.3 (E2E tests)
    └── Task 6.4 (Regression tests)
```

---

## Subagent Assignment Summary

| Task | Subagent | Rationale |
|------|----------|-----------|
| 1.1-1.5 | `implementer` | Infrastructure code with TDD |
| 2.1-2.4 | `implementer` | Service implementation with TDD |
| 3.1-3.5 | `implementer` | Core orchestrator with TDD |
| 4.1-4.4 | `implementer` | Refresh enricher with TDD |
| 5.1-5.4 | `implementer` | Integration wiring with TDD |
| 6.1-6.3 | `implementer` | Test implementation |
| 6.4 | `test-runner` | Run existing test suites |

---

## Checkpoint Commands

After each phase, run verification:

```bash
# Phase 1 verification
pytest crawler/tests/unit/test_schedule_category.py -v
pytest crawler/tests/unit/test_crawl_schedule_config.py -v

# Phase 2 verification
pytest crawler/tests/unit/services/test_product_matcher.py -v

# Phase 3 verification
pytest crawler/tests/unit/services/test_single_product_orchestrator.py -v

# Phase 4 verification
pytest crawler/tests/unit/services/test_refresh_enricher.py -v

# Phase 5 verification
pytest crawler/tests/unit/test_tasks_single_product.py -v

# Phase 6 verification (full suite)
pytest tests/e2e/flows/test_single_product_flow.py -v
pytest tests/e2e/flows/test_single_product_e2e.py -v --tb=short

# Regression verification
pytest tests/e2e/flows/test_competition_flow.py -v
pytest tests/e2e/flows/test_generic_search_v3_e2e.py -v
```
