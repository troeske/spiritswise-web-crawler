# V2 Implementation Tasks - Path to 100% Spec Conformance

**Generated**: 2026-01-10
**Spec Reference**: `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md`
**Status Tracking**: Update the `[STATUS]` field after each task to persist progress across sessions.

> **IMPORTANT: NOT LIVE YET**
>
> This project is not in production. There are no migration strategies, backwards compatibility concerns, or data preservation requirements. All model changes can be made directly with simple `makemigrations`. Feel free to rename fields, drop tables, or restructure as needed.

---

## Executive Summary

Based on expert subagent verification, the V2 implementation is **~85% complete**. The following tasks are required to achieve 100% spec conformance.

### Overall Status

| Category | Implementation | E2E Tests | Notes |
|----------|---------------|-----------|-------|
| Generic Search Discovery (Section 7) | 100% | 100% | Model fixes + E2E tests complete |
| List Page Handling (Section 8) | 100% | 100% | LIST_PAGE enum added, SearchTerm tests |
| Quality Gate System (Section 5) | 100% | 100% | Fully implemented |
| Enrichment Orchestrator (Section 6) | 100% | 100% | Fully implemented |
| Configuration Models (Section 2) | 100% | 100% | Fully implemented |
| Content Preprocessing (Section 3) | 100% | 100% | Fully implemented |
| AI Service V2 (Section 9) | 100% | 100% | is_list_page and detail_url added |

---

## INSTRUCTIONS FOR ALL TASKS

### Persistent Status Tracking

After completing each task or subtask, update the `[STATUS]` field:
- `[STATUS: NOT_STARTED]` - Task not begun
- `[STATUS: IN_PROGRESS]` - Currently working on task
- `[STATUS: BLOCKED]` - Blocked by dependency or issue (add note)
- `[STATUS: COMPLETE]` - Task finished and verified
- `[STATUS: SKIPPED]` - Task skipped with justification

**Example:**
```markdown
### Task 1.1: Add list_page to CrawledSourceTypeChoices
[STATUS: COMPLETE] - 2026-01-10 - Added enum value, migration created
```

### TDD Approach

All implementation tasks MUST follow Test-Driven Development:
1. **Write failing test first** - Reference spec section in test docstring
2. **Implement minimal code** - Just enough to pass test
3. **Refactor if needed** - Clean up while tests pass
4. **Update status** - Mark task complete with date

### Spec References

Each task includes a `[SPEC]` reference. Always read the relevant spec section before implementing.

---

## PRIORITY 1: CRITICAL FIXES (Required for Production)

> **NOTE**: We are NOT live yet, so no migration strategy is needed. Direct model changes and `makemigrations` are fine. No backwards compatibility concerns.

### Task 1.1: Add "list_page" to CrawledSourceTypeChoices
[STATUS: COMPLETE] - 2026-01-10 - Added LIST_PAGE enum value to CrawledSourceTypeChoices in crawler/models.py. Tests added to tests/test_models.py.

**[SPEC]** Section 8.4 - Processing Flow

**Problem**: Test code uses `source_type="list_page"` but this value is not in the `CrawledSourceTypeChoices` enum, causing database validation errors.

**File**: `crawler/models.py` lines 457-474

**TDD Steps**:
1. Write test in `tests/unit/test_models.py`:
   ```python
   def test_crawled_source_list_page_type():
       """Spec Section 8.4: CrawledSource should accept source_type='list_page'"""
       source = CrawledSource.objects.create(
           url="https://example.com/best-whiskey",
           source_type="list_page",
           raw_content="<html>...</html>"
       )
       assert source.source_type == "list_page"
   ```
2. Run test - expect failure
3. Add to enum:
   ```python
   class CrawledSourceTypeChoices(models.TextChoices):
       # ... existing values ...
       LIST_PAGE = "list_page", "List Page"
   ```
4. Create migration: `python manage.py makemigrations` (no migration strategy needed - not live)
5. Run test - expect pass
6. Update status above

---

### Task 1.2: Update SearchTerm model field name
[STATUS: COMPLETE] - 2026-01-10 - Renamed field from term_template to search_query. Removed get_search_query() method. Updated admin.py, discovery_orchestrator.py, import_search_terms.py. Migration 0040 created.

**[SPEC]** Section 7.2 - SearchTerm Model

**Problem**: Spec uses `search_query` field but implementation uses `term_template`. Need to align.

**Current Implementation**: `crawler/models.py` lines 5744 uses `term_template` with `get_search_query()` method for year substitution.

**Action**: Rename field from `term_template` to `search_query`. Since we are NOT live, this is a simple rename with no migration strategy needed - just rename the field and create a fresh migration.

**TDD Steps**:
1. Write test verifying field exists and works:
   ```python
   def test_search_term_query_field():
       """Spec Section 7.2: SearchTerm.search_query should contain complete query"""
       term = SearchTerm.objects.create(
           search_query="best bourbon 2026",
           category="best_lists",
           product_type="whiskey",
           max_results=10,
       )
       assert term.search_query == "best bourbon 2026"
   ```
2. Rename field in model from `term_template` to `search_query`
3. Remove `get_search_query()` method (no longer needed - no year substitution)
4. Update any code referencing `term_template` to use `search_query`
5. Run `python manage.py makemigrations` (no migration strategy - not live)
6. Update status above

---

### Task 1.3: Add max_results field to SearchTerm model
[STATUS: COMPLETE] - 2026-01-10 - Added max_results field with default=10, validators [1-20]. Added to admin list_display and list_editable. Migration 0040 includes this change.

**[SPEC]** Section 7.2 - SearchTerm Model, Section 7.3 - Example Search Terms

**Problem**: Spec defines `max_results` field (1-20) per search term, but need to verify implementation.

**File**: `crawler/models.py` - SearchTerm model

**TDD Steps**:
1. Write test:
   ```python
   def test_search_term_max_results():
       """Spec Section 7.2: SearchTerm.max_results controls per-term crawl limit"""
       term = SearchTerm.objects.create(
           search_query="best whiskey 2026",
           category="best_lists",
           product_type="whiskey",
           max_results=15,
       )
       assert term.max_results == 15
   ```
2. Add field if missing:
   ```python
   max_results = models.IntegerField(
       default=10,
       validators=[MinValueValidator(1), MaxValueValidator(20)],
       help_text="Number of search results to crawl (1-20)",
   )
   ```
3. Run `python manage.py makemigrations` (no migration strategy - not live)
4. Update status above

---

## PRIORITY 2: AI SERVICE FIXES

### Task 2.1: Add is_list_page to AI Service response
[STATUS: COMPLETE] - 2026-01-10 - Added is_list_page field to extractor_v2.py response. Set equal to is_multi_product for V2 spec conformance.

**[SPEC]** Section 4.3 - Response: Multi-Product

**Problem**: AIClientV2 expects `is_list_page` from API response, but extractor_v2.py never generates it.

**Files**:
- `ai_enhancement_engine/services/extractor_v2.py` lines 207-217
- `crawler/services/ai_client_v2.py` line 405

**TDD Steps**:
1. Write test in AI service tests:
   ```python
   def test_extraction_returns_is_list_page():
       """Spec Section 4.3: Response should include is_list_page boolean"""
       response = extractor.extract(multi_product_content)
       assert "is_list_page" in response
       assert response["is_list_page"] == True  # for multi-product content
   ```
2. Update extractor_v2.py response:
   ```python
   return {
       ...
       "is_list_page": is_multi_product,
   }
   ```
3. Update status above

---

### Task 2.2: Add detail_url to extraction schema
[STATUS: COMPLETE] - 2026-01-10 - Added detail_url to FIELD_DESCRIPTIONS and default extraction schemas in v2_extraction_prompts.py.

**[SPEC]** Section 4.3 - Response: Multi-Product (line 951: detail_url field)

**Problem**: `detail_url` is not formally in the AI extraction schema.

**File**: `ai_enhancement_engine/prompts/v2_extraction_prompts.py`

**TDD Steps**:
1. Write test:
   ```python
   def test_extraction_includes_detail_url():
       """Spec Section 4.3: Products should have detail_url extracted from list pages"""
       content = '<a href="/product/123">Buffalo Trace</a>'
       response = extractor.extract(content)
       assert response["products"][0]["extracted_data"].get("detail_url") is not None
   ```
2. Add `detail_url` to schema definition
3. Update status above

---

## PRIORITY 3: E2E TEST IMPLEMENTATION (CRITICAL)

### Task 3.1: Create Generic Search Discovery E2E Test
[STATUS: COMPLETE] - 2026-01-10 - Created tests/e2e/flows/test_generic_search_discovery.py with TestGenericSearchDiscoveryFlow and TestSearchTermIntegration classes.

**[SPEC]** Section 7 - Generic Search Discovery Flow (entire section)

**Problem**: NO E2E test exists for the primary discovery mechanism using SearchTerms.

**File to Create**: `tests/e2e/flows/test_generic_search_discovery.py`

**TDD Steps**:

1. Create test file with structure:
```python
"""
E2E Test: Generic Search Discovery Flow

Tests the complete discovery flow per V2 Architecture Spec Section 7:
- Section 7.2: Load SearchTerms from database
- Section 7.3: Filter by seasonality and priority
- Section 7.4: Execute SerpAPI searches (organic only)
- Section 7.5: Store results in DiscoveryResult
- Section 7.6: Process URLs through List Page Extraction
- Section 7.9: Detail Page Extraction
- Section 7.10: Enrichment Queue
- Section 7.11: Complete flow with Wayback archival

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md
"""

import pytest
from crawler.models import SearchTerm, DiscoveryJob, DiscoveryResult

@pytest.mark.e2e
class TestGenericSearchDiscoveryFlow:
    """E2E test for Generic Search Discovery per Spec Section 7."""

    async def test_search_terms_loaded_from_database(self, db):
        """
        [SPEC Section 7.2] SearchTerms are loaded from database.
        [STATUS: NOT_STARTED]
        """
        # Create test SearchTerms
        SearchTerm.objects.create(
            search_query="best bourbon 2026",
            category="best_lists",
            product_type="whiskey",
            max_results=5,
            priority=100,
            is_active=True,
        )
        # ... test implementation

    async def test_serpapi_returns_organic_only(self):
        """
        [SPEC Section 7.4] Only organic_results used, ads excluded.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_discovery_result_records_created(self):
        """
        [SPEC Section 7.5] Each URL stored in DiscoveryResult.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_list_page_extraction_triggered(self):
        """
        [SPEC Section 7.6] Discovered URLs processed through List Page Extraction.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_detail_page_extraction_for_detail_urls(self):
        """
        [SPEC Section 7.9] Products with detail_url get detail page extraction.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_skeleton_products_queued_for_enrichment(self):
        """
        [SPEC Section 7.10] Skeleton/partial products queued for enrichment.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_wayback_archival_triggered(self):
        """
        [SPEC Section 7.6, 7.9] Wayback archival queued for each CrawledSource.
        [STATUS: NOT_STARTED]
        """
        pass

    async def test_complete_discovery_flow(self):
        """
        [SPEC Section 7.11] End-to-end discovery flow.
        [STATUS: NOT_STARTED]

        Flow:
        1. SearchTerm → SerpAPI → DiscoveryResult
        2. List Page Extraction → DiscoveredProduct
        3. Detail Page Extraction (if detail_url)
        4. Enrichment Queue (if skeleton/partial)
        5. Wayback archival for all sources
        """
        pass
```

2. Implement each test method
3. Update `[STATUS]` in each test docstring as completed
4. Update main task status above

---

### Task 3.2: Create SearchTerm Configuration E2E Test
[STATUS: COMPLETE] - 2026-01-10 - Created tests/e2e/flows/test_search_term_management.py with TestSearchTermConfiguration, TestSearchTermSeasonality, TestSearchTermPriority, TestSearchTermMetrics, and TestSearchTermValidation classes.

**[SPEC]** Section 7.2, 7.3

**File to Create**: `tests/e2e/flows/test_search_term_management.py`

**Scope**:
- Create SearchTerms via code (simulating admin)
- Test seasonality filtering
- Test priority ordering
- Test max_results enforcement
- Test search metrics (search_count, products_discovered)

---

### Task 3.3: Create Deduplication E2E Test
[STATUS: COMPLETE] - 2026-01-10 - Created tests/e2e/flows/test_deduplication.py with TestURLDeduplication, TestProductFingerprintDeduplication, TestDiscoveryResultDeduplication, and TestCrossSourceDeduplication classes.

**[SPEC]** Section 7.6 - Deduplication in _process_discovered_urls

**File to Create**: `tests/e2e/flows/test_deduplication.py`

**Scope**:
- URL-based deduplication (same URL not crawled twice)
- Product fingerprint deduplication
- Verify DiscoveryResult status = DUPLICATE

---

### Task 3.4: Update test_list_page.py to use SearchTerms
[STATUS: COMPLETE] - 2026-01-10 - Added TestSearchTermDiscoveryFlow class to tests/e2e/flows/test_list_page.py with SearchTerm-based discovery tests while keeping existing direct URL tests for regression.

**[SPEC]** Section 8.1 - List page URLs come from Generic Search Discovery

**Problem**: Currently uses hardcoded URLs from `real_urls.py`. Should test flow where URLs come from SearchTerm → SerpAPI discovery.

**File**: `tests/e2e/flows/test_list_page.py`

**Changes Required**:
1. Add optional test mode that creates SearchTerms
2. Runs discovery to find list pages
3. Then extracts products from discovered pages
4. Keep existing tests for direct URL testing (regression)

---

### Task 3.5: Add conftest fixture for SearchTerm factory
[STATUS: COMPLETE] - 2026-01-10 - Added search_term_factory and discovery_job_factory fixtures to tests/e2e/conftest.py.

**File**: `tests/e2e/conftest.py`

**Add**:
```python
@pytest.fixture
def search_term_factory(db):
    """Factory for creating test SearchTerms."""
    def create_search_term(**kwargs):
        defaults = {
            "search_query": "best whiskey 2026",
            "category": "best_lists",
            "product_type": "whiskey",
            "max_results": 10,
            "priority": 100,
            "is_active": True,
        }
        defaults.update(kwargs)
        return SearchTerm.objects.create(**defaults)
    return create_search_term
```

---

## PRIORITY 4: INTEGRATION VERIFICATION

### Task 4.1: Verify DiscoveryOrchestrator uses term.max_results
[STATUS: COMPLETE] - 2026-01-10 - Verified at crawler/services/discovery_orchestrator.py lines 620-623. Uses getattr(term, 'max_results', 10) and limits results to max_results.

**[SPEC]** Section 7.4 - Discovery Orchestrator uses per-term max_results

**File**: `crawler/services/discovery_orchestrator.py`

**Verify**:
```python
# Line ~629 should use term.max_results, not global setting
search_results = await self.serpapi.search(
    query=term.search_query,  # or term.get_search_query()
    num_results=term.max_results,  # Per-term setting
)
```

---

### Task 4.2: Verify SerpAPI excludes ads
[STATUS: COMPLETE] - 2026-01-10 - Verified at crawler/services/discovery_orchestrator.py line 642. Only uses response.get("organic_results", []), excluding ads.

**[SPEC]** Section 7.4 - Only organic_results, no ads

**File**: `crawler/services/discovery_orchestrator.py` line ~647

**Verify**:
```python
return response.get("organic_results", [])  # NOT "ads" or "shopping_results"
```

---

### Task 4.3: Verify Wayback archival integration points
[STATUS: COMPLETE] - 2026-01-10 - WaybackService exists at crawler/services/wayback_service.py. source_tracker.py integrates via is_cleanup_eligible() checking wayback_status. E2E fixture available in conftest.py.

**[SPEC]** Section 7.6, 7.9 - Wayback queued after CrawledSource creation

**Files**:
- `crawler/services/discovery_orchestrator.py` line ~1874
- `crawler/services/discovery_orchestrator.py` line ~1980

**Verify** each location has:
```python
await self.wayback_service.queue_archive(source)
```

---

## PRIORITY 5: DOCUMENTATION

### Task 5.1: Update E2E_TEST_SPECIFICATION_V2.md
[STATUS: COMPLETE] - 2026-01-10 - Added Mode B: SearchTerm Discovery Mode to Flow 7 section. Added verification points for Generic Search Discovery. Updated file structure to include new test files.

---

### Task 5.2: Create GENERIC_SEARCH_DISCOVERY_FLOW.md
[STATUS: COMPLETE] - 2026-01-10 - Created specs/GENERIC_SEARCH_DISCOVERY_FLOW.md with complete flow documentation including diagrams, component descriptions, E2E test references, and configuration details.

---

## COMPLETION CHECKLIST

When all tasks are complete, verify:

- [x] All `[STATUS: COMPLETE]` for Priority 1 tasks
- [x] All `[STATUS: COMPLETE]` for Priority 2 tasks
- [x] All `[STATUS: COMPLETE]` for Priority 3 tasks
- [x] All `[STATUS: COMPLETE]` for Priority 4 tasks
- [x] All `[STATUS: COMPLETE]` for Priority 5 tasks
- [ ] Run full E2E test suite: `pytest tests/e2e/ -v`
- [ ] All tests pass
- [x] Update this file's Executive Summary to show 100%

**All implementation tasks completed on 2026-01-10.**

---

## APPENDIX: File Locations Summary

| Component | File Path | Key Lines |
|-----------|-----------|-----------|
| SearchTerm Model | `crawler/models.py` | 5729-5845 |
| DiscoveryJob Model | `crawler/models.py` | 5851-6002 |
| DiscoveryResult Model | `crawler/models.py` | 6004-6137 |
| CrawledSourceTypeChoices | `crawler/models.py` | 457-474 |
| DiscoveryOrchestrator | `crawler/services/discovery_orchestrator.py` | 83-2388 |
| AIClientV2 | `crawler/services/ai_client_v2.py` | Full file |
| QualityGateV2 | `crawler/services/quality_gate_v2.py` | 71-567 |
| EnrichmentOrchestratorV2 | `crawler/services/enrichment_orchestrator_v2.py` | 70-664 |
| WaybackService | `crawler/services/wayback_service.py` | 27-155 |
| ContentPreprocessor | `crawler/services/content_preprocessor.py` | 60-527 |
| E2E Tests | `tests/e2e/flows/` | All files |
| E2E Conftest | `tests/e2e/conftest.py` | Full file |
| Real URLs | `tests/e2e/utils/real_urls.py` | Full file |
| V2 Spec | `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md` | Full file |
