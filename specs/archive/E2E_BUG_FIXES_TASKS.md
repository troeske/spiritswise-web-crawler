# E2E Bug Fixes Task List

**Created:** 2026-01-08
**Status:** COMPLETE
**MVP Focus:** Whiskey and Port Wine only

## Summary

E2E testing exposed 3 critical bugs in the competition crawler pipeline that cause non-product data (wine producer names) to be saved as whiskey products. This task list tracks fixes using TDD approach.

---

## Bug Overview

| Bug | Severity | Component | Status |
|-----|----------|-----------|--------|
| 1. IWSC Parser extracts producer names | HIGH | parsers.py | COMPLETE |
| 2. Silent product_type override to whiskey | HIGH | product_saver.py | COMPLETE |
| 3. No rejection of non-MVP product types | MEDIUM | skeleton_manager.py | COMPLETE |

---

## Task 1: Fix Silent Product Type Override

**Priority:** P0 - Critical (must fix first, affects all other flows)
**Subagent:** `implementer`
**Status:** COMPLETE
**Files:**
- `crawler/services/product_saver.py`
- `crawler/tests/unit/test_product_saver.py`

### Problem
When `product_type` is not in ProductType enum (e.g., "wine", "unknown"), the code silently overrides to "whiskey" instead of rejecting/logging.

```python
# Current buggy code (lines 2112-2114):
valid_types = [pt.value for pt in ProductType]
if product_type not in valid_types:
    product_type = ProductType.WHISKEY  # Silent override!
```

### Requirements
1. For MVP, only accept `whiskey` and `port_wine` as valid product types
2. If product_type is invalid, **reject the product** (return error, don't save)
3. Log a warning when rejecting invalid product types
4. Return a clear error in ProductSaveResult

### TDD Tests to Write First
```python
# In test_product_saver.py

def test_rejects_invalid_product_type_wine():
    """Should reject products with product_type='wine'."""
    result = save_discovered_product(
        extracted_data={"name": "Test Wine"},
        source_url="http://example.com",
        product_type="wine",
        discovery_source="competition",
    )
    assert result.created is False
    assert result.error is not None
    assert "invalid product type" in result.error.lower()

def test_rejects_invalid_product_type_unknown():
    """Should reject products with product_type='unknown'."""
    result = save_discovered_product(
        extracted_data={"name": "Unknown Product"},
        source_url="http://example.com",
        product_type="unknown",
        discovery_source="competition",
    )
    assert result.created is False
    assert result.error is not None

def test_accepts_whiskey_product_type():
    """Should accept whiskey products."""
    result = save_discovered_product(
        extracted_data={"name": "Glenfiddich 12"},
        source_url="http://example.com",
        product_type="whiskey",
        discovery_source="search",
    )
    assert result.created is True
    assert result.product.product_type == "whiskey"

def test_accepts_port_wine_product_type():
    """Should accept port wine products."""
    result = save_discovered_product(
        extracted_data={"name": "Taylor's Vintage Port"},
        source_url="http://example.com",
        product_type="port_wine",
        discovery_source="search",
    )
    assert result.created is True
    assert result.product.product_type == "port_wine"
```

### Implementation Steps
- [x] Write failing TDD tests (4 tests above)
- [x] Modify ProductSaveResult to include optional `error` field
- [x] Update validation logic to reject non-MVP types
- [x] Add logging for rejected products
- [x] Run tests, verify passing
- [x] Update this task list

### Progress
- [x] Tests written
- [x] Implementation complete
- [x] All tests passing (13 tests)
- [ ] Code reviewed

### Implementation Summary
1. Added `MVP_VALID_PRODUCT_TYPES` constant at module level containing only `['whiskey', 'port_wine']`
2. Added optional `error` field to `ProductSaveResult` dataclass (defaults to `None`)
3. Added validation at the start of `save_discovered_product()` that rejects non-MVP product types
4. Returns `ProductSaveResult(product=None, created=False, error=...)` for invalid types
5. Logs warning with product name and URL when rejecting invalid product types

---

## Task 2: Fix Skeleton Manager Type Detection

**Priority:** P1 - High
**Subagent:** `implementer`
**Files:**
- `crawler/discovery/competitions/skeleton_manager.py`
- `crawler/tests/unit/test_skeleton_manager.py`

### Problem
`_determine_product_type()` returns "wine" or "unknown" for non-spirit products, but these values are not valid ProductType values and get silently converted to "whiskey".

### Requirements
1. For MVP, only return `whiskey` or `port_wine` from type detection
2. If product doesn't match whiskey or port wine keywords, return `None` (reject)
3. Skip creating skeleton products for non-MVP types
4. Log skipped products for debugging

### TDD Tests to Write First
```python
# In test_skeleton_manager.py

def test_determine_type_returns_none_for_wine():
    """Wine products should return None (not valid for MVP)."""
    manager = SkeletonProductManager()
    result = manager._determine_product_type({
        "product_name": "Winery Gurjaani 2024",
        "category": "General",
    })
    assert result is None

def test_determine_type_returns_none_for_unknown():
    """Unknown products should return None."""
    manager = SkeletonProductManager()
    result = manager._determine_product_type({
        "product_name": "Random Company LLC",
        "category": "General",
    })
    assert result is None

def test_determine_type_returns_whiskey():
    """Whiskey products should return 'whiskey'."""
    manager = SkeletonProductManager()
    result = manager._determine_product_type({
        "product_name": "Glenfiddich 12 Year Single Malt",
        "category": "Scotch Whisky",
    })
    assert result == "whiskey"

def test_determine_type_returns_port_wine():
    """Port products should return 'port_wine'."""
    manager = SkeletonProductManager()
    result = manager._determine_product_type({
        "product_name": "Taylor's 20 Year Tawny Port",
        "category": "Port",
    })
    assert result == "port_wine"

def test_create_skeleton_skips_non_mvp_types():
    """Should not create skeleton for wine products."""
    manager = SkeletonProductManager()
    # Should raise or return None for wine products
    with pytest.raises(ValueError) as exc_info:
        manager.create_skeleton_product({
            "product_name": "Winery Gurjaani 2024",
            "category": "General",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Bronze",
        })
    assert "not supported for MVP" in str(exc_info.value).lower()
```

### Implementation Steps
- [x] Write failing TDD tests (5 tests above)
- [x] Update `_determine_product_type()` to return None for non-MVP types
- [x] Update `create_skeleton_product()` to check for None and raise ValueError
- [x] Add logging for skipped products
- [x] Run tests, verify passing
- [x] Update this task list

### Progress
- [x] Tests written
- [x] Implementation complete
- [x] All tests passing
- [ ] Code reviewed

---

## Task 3: Improve IWSC Parser Validation

**Priority:** P2 - Medium
**Subagent:** `implementer`
**Files:**
- `crawler/discovery/competitions/parsers.py`
- `crawler/tests/unit/test_competition_parsers.py`

### Problem
The IWSC parser extracts whatever text is in `.c-card--listing__title` without validating if it's an actual product name. Producer/company names like "Winery Gurjaani 2024" get extracted as product names.

### Requirements
1. Add validation to reject obvious non-product patterns
2. Reject entries containing "winery", "distillery", "company", "ltd", "llc" without actual product names
3. Reject entries that are just years (e.g., "2024")
4. Log rejected entries for debugging
5. Consider the entry invalid if it doesn't contain spirit-related keywords

### TDD Tests to Write First
```python
# In test_competition_parsers.py

def test_iwsc_parser_rejects_winery_names():
    """Parser should skip entries that are just winery names."""
    parser = IWSCParser()
    html = '''
    <div class="c-card--listing">
        <div class="c-card--listing__title">Winery Gurjaani 2024</div>
        <div class="c-card--listing__awards-wrapper">
            <img src="iwsc2024-bronze-medal.png" alt="Bronze">
        </div>
    </div>
    '''
    results = parser.parse(html, 2024)
    assert len(results) == 0

def test_iwsc_parser_rejects_company_names():
    """Parser should skip entries that are company names."""
    parser = IWSCParser()
    html = '''
    <div class="c-card--listing">
        <div class="c-card--listing__title">Spirits Company LLC</div>
    </div>
    '''
    results = parser.parse(html, 2024)
    assert len(results) == 0

def test_iwsc_parser_accepts_whiskey_products():
    """Parser should accept valid whiskey product names."""
    parser = IWSCParser()
    html = '''
    <div class="c-card--listing">
        <div class="c-card--listing__title">Glenfiddich 12 Year Old Single Malt Scotch Whisky</div>
        <div class="c-card--listing__awards-wrapper">
            <img src="iwsc2024-gold-95-medal.png" alt="Gold">
        </div>
    </div>
    '''
    results = parser.parse(html, 2024)
    assert len(results) == 1
    assert results[0]["product_name"] == "Glenfiddich 12 Year Old Single Malt Scotch Whisky"

def test_iwsc_parser_accepts_port_products():
    """Parser should accept valid port wine product names."""
    parser = IWSCParser()
    html = '''
    <div class="c-card--listing">
        <div class="c-card--listing__title">Taylor's 20 Year Old Tawny Port</div>
        <div class="c-card--listing__awards-wrapper">
            <img src="iwsc2024-gold-medal.png" alt="Gold">
        </div>
    </div>
    '''
    results = parser.parse(html, 2024)
    assert len(results) == 1
    assert "port" in results[0]["product_name"].lower()
```

### Implementation Steps
- [x] Write failing TDD tests (4 tests above)
- [x] Add `_is_valid_product_name()` helper method
- [x] Add `_contains_mvp_keywords()` helper method
- [x] Update parse() to filter out invalid entries
- [x] Add logging for filtered entries
- [x] Run tests, verify passing
- [x] Update this task list

### Progress
- [x] Tests written
- [x] Implementation complete
- [x] All tests passing
- [ ] Code reviewed

---

## Task 4: Update Competition Orchestrator Filtering

**Priority:** P2 - Medium
**Subagent:** `implementer`
**Files:**
- `crawler/services/competition_orchestrator.py`
- `crawler/tests/unit/test_competition_orchestrator.py`

### Problem
The `_filter_awards_by_product_type()` method uses keyword matching but doesn't effectively filter out wine products from whiskey searches.

### Requirements
1. Enhance keyword filtering to be more strict
2. Add negative keywords (words that indicate NOT whiskey/port)
3. Track and report filtered count in CompetitionDiscoveryResult
4. Log details of filtered products

### TDD Tests to Write First
```python
# In test_competition_orchestrator.py

def test_filter_removes_wine_products():
    """Should filter out wine products when searching for whiskey."""
    orchestrator = CompetitionOrchestrator()
    awards = [
        {"product_name": "Glenfiddich 12", "category": "Whisky"},
        {"product_name": "Winery Gurjaani", "category": "Wine"},
        {"product_name": "Taylor's Port", "category": "Port"},
    ]
    filtered = orchestrator._filter_awards_by_product_type(
        awards, ["whiskey", "port_wine"]
    )
    assert len(filtered) == 2
    names = [a["product_name"] for a in filtered]
    assert "Winery Gurjaani" not in names

def test_filter_uses_negative_keywords():
    """Should filter products with negative keywords like 'winery'."""
    orchestrator = CompetitionOrchestrator()
    awards = [
        {"product_name": "Calligraphy Winery 2024", "category": "General"},
    ]
    filtered = orchestrator._filter_awards_by_product_type(
        awards, ["whiskey"]
    )
    assert len(filtered) == 0
```

### Implementation Steps
- [x] Write failing TDD tests (2 tests above)
- [x] Add negative keywords list (winery, vineyard, wine cellar, etc.)
- [x] Update `_filter_awards_by_product_type()` to check negative keywords
- [x] Update CompetitionDiscoveryResult to track filtered count
- [x] Add logging for filtered products
- [x] Run tests, verify passing
- [x] Update this task list

### Progress
- [x] Tests written
- [x] Implementation complete
- [x] All tests passing
- [ ] Code reviewed

---

## Task 5: Add E2E Test Validation

**Priority:** P3 - Low (after other fixes)
**Subagent:** `implementer`
**Status:** COMPLETE
**Files:**
- `crawler/management/commands/run_e2e_test.py`

### Problem
E2E test doesn't validate that created products are actually valid whiskey/port products.

### Requirements
1. Add validation step after competition discovery
2. Check that all created products have valid product_type
3. Check that product names don't contain obvious non-product patterns
4. Report validation failures in E2E output
5. Add data quality metrics to E2E summary

### Implementation Steps
- [x] Add `_validate_products()` helper method
- [x] Add validation after competition flow
- [x] Update summary output with validation results
- [x] Update this task list

### Progress
- [x] Implementation complete
- [ ] Code reviewed

### Implementation Summary
1. Added `VALID_MVP_TYPES` constant at module level: `['whiskey', 'port_wine']`
2. Added `REJECT_PATTERNS` constant for non-product patterns: `['winery', 'vineyard', 'wine cellar', 'company', 'ltd', 'llc', 'inc']`
3. Added `_validate_products()` method that:
   - Queries all DiscoveredProducts in the database
   - Checks each product has valid product_type (whiskey or port_wine)
   - Checks product names don't contain reject patterns
   - Returns validation results dict with counts, issues found, and quality score
4. Added `_print_validation_results()` method for detailed validation output
5. Updated `run_synchronous()` to call validation after discovery flows
6. Updated `_print_summary()` to include data quality metrics section
7. Updated `show_status()` to include validation results

---

## Execution Order

1. **Task 1** (P0): Fix product_saver.py validation first - this is the root cause - **COMPLETE**
2. **Task 2** (P1): Fix skeleton_manager type detection - prevents bad data at source - **COMPLETE**
3. **Task 3** (P2): Improve IWSC parser - catches issues earlier in pipeline - **COMPLETE**
4. **Task 4** (P2): Update orchestrator filtering - additional safety layer - **COMPLETE**
5. **Task 5** (P3): Add E2E validation - prevents regression - **COMPLETE**

---

## Commands for Subagent

### Running Tests
```bash
cd spiritswise-web-crawler
pytest crawler/tests/unit/test_product_saver.py -v
pytest crawler/tests/unit/test_skeleton_manager.py -v
pytest crawler/tests/unit/test_competition_parsers.py -v
pytest crawler/tests/unit/test_competition_orchestrator.py -v
```

### Running E2E Test After Fixes
```bash
cd spiritswise-web-crawler
python manage.py clear_crawled_data --confirm
python manage.py run_e2e_test --setup
python manage.py run_e2e_test --flow competition --competition iwsc --sync --limit 20
python manage.py run_e2e_test --status
```

---

## Change Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-01-08 | Initial | Created | Bug analysis from E2E test |
| 2026-01-08 | Task 2 | COMPLETE | Fixed skeleton_manager type detection with TDD (14 tests) |
| 2026-01-08 | Task 3 | COMPLETE | Added MVP keyword validation to IWSCParser with TDD (19 tests) |
| 2026-01-08 | Task 4 | COMPLETE | Enhanced competition_orchestrator filtering with negative keywords (18 tests) |
| 2026-01-08 | Task 1 | COMPLETE | Fixed product_saver silent override with TDD (13 tests). Added MVP_VALID_PRODUCT_TYPES constant, error field to ProductSaveResult, and early validation/rejection |
| 2026-01-08 | Task 5 | COMPLETE | Added E2E test validation with _validate_products() method, quality metrics, and detailed output |
| 2026-01-09 | Task 3 Fix | COMPLETE | Relaxed parser validation - no longer requires MVP keywords in product name (26 tests). Real products like "Glenfiddich 12" now accepted. |
| 2026-01-09 | IWSC URL | IN PROGRESS | Updated to `type=3` for spirits. First page shows vodka/brandy, not whiskey. Need pagination or specific whiskey URL. |
| 2026-01-09 | Discovery | PENDING | AI extraction returns empty for list pages. Needs dedicated list extraction endpoint or lighter validation. |

---

## New Issues Discovered (2026-01-09)

### Issue 1: IWSC URL Doesn't Return Whiskey on First Page

**Problem:** The IWSC URL `https://iwsc.net/results/search?type=3` returns all spirits, but the first page shows vodka/brandy products, not whiskey.

**Evidence:** E2E test found 4 valid spirit products, but all were vodka (correctly rejected as non-MVP).

**Potential Solutions:**
1. Paginate through IWSC results to find whiskey
2. Use IWSC's whiskey-specific category filter (if available)
3. Search for `&q=whisky` (currently returns no results due to JS rendering)

### Issue 2: Discovery Flow AI Extraction Returns Empty

**Problem:** The `_extract_list_products()` method returns empty arrays for list pages like "Best Port Wine 2024".

**Root Cause:** The AI Enhancement Service `/from-crawler/` endpoint is designed for single product extraction, not list pages. List pages don't have required fields (tasting notes, etc.).

**Potential Solutions:**
1. Create lightweight "product discovery" prompt (just names, brands, links)
2. Add dedicated `/extract-list/` API endpoint
3. Relax validation requirements for discovery mode

