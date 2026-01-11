# Data Quality Improvement Tasks

## Overview
Fix the discovery/extraction pipeline to ensure comprehensive product data collection.
The current pipeline extracts only ~10% of required fields (only `initial_taste` populated).

## Task Status Tracking
| Task | Status | Subagent | Completed At |
|------|--------|----------|--------------|
| Task 1: SPEC | ✅ COMPLETED | spec-writer | 2026-01-07 |
| Task 2: RESEARCH | ✅ COMPLETED | Explore | 2026-01-07 |
| Task 3: FIX Rich AI Data | ✅ COMPLETED | implementer | 2026-01-07 |
| Task 4: FIX Field Mapping | ✅ COMPLETED | implementer | 2026-01-07 |
| Task 5: IMPLEMENT Quality Threshold | ✅ COMPLETED | implementer | 2026-01-07 |
| Task 6: IMPLEMENT Source Tracking | ✅ COMPLETED | implementer | 2026-01-07 |
| Task 7: IMPLEMENT Search Limit | ✅ COMPLETED | implementer | 2026-01-07 |
| Task 8: TEST Competition Flow | ✅ COMPLETED | implementation-verifier | 2026-01-07 |
| Task 9: TEST E2E Quality | ✅ COMPLETED | implementation-verifier | 2026-01-07 |

---

## Task 1: SPEC - Define Comprehensive Product Data Requirements
**Subagent:** `spec-writer`
**Priority:** CRITICAL - Must complete before other tasks

### Objective
Define what product data a comprehensive consumer-focused spirits database MUST contain.

### Context
- Target users: Consumers researching spirits for understanding and buying decisions
- Product types: Whiskey (bourbon, scotch, rye, etc.) and Port Wine
- Use cases:
  - Understanding product characteristics (taste, aroma, finish)
  - Comparing products
  - Making purchase decisions
  - Learning about production/background

### Deliverables
1. **Required Fields** (must have before stopping search):
   - Core identity fields
   - Tasting profile fields (nose, palate, finish)
   - Production details
   - Pricing/availability indicators

2. **Optional Fields** (nice to have):
   - Historical information
   - Expert reviews
   - Food pairings

3. **Minimum Data Quality Threshold**:
   - Define which fields constitute a "complete" product
   - Define "incomplete" vs "partial" vs "complete" status

4. **Search Termination Criteria**:
   - When to stop searching for more data
   - Maximum URLs to crawl per product (safety limit)

---

## Task 2: RESEARCH - API Rate Limits and Timeouts
**Subagent:** `Explore` (research mode)
**Priority:** HIGH

### Objective
Determine our actual rate limits for ScrapingBee and SerpAPI accounts and define optimal timeout configurations.

### Research Items
1. **ScrapingBee**:
   - Check `crawler/tests/integration/config.py` for API credentials
   - Look up our plan limits (requests/month, concurrent requests)
   - Recommended timeout per request
   - Rate limiting strategy (requests per minute)

2. **SerpAPI**:
   - Check config for API credentials
   - Look up our plan limits (searches/month)
   - Recommended timeout per search
   - Rate limiting strategy

3. **AI Enhancement Service**:
   - Current timeout (15s based on code)
   - Optimal content size to avoid timeouts

### Deliverables
- Configuration recommendations document
- Update to config files with proper timeout/rate limit settings

---

## Task 3: FIX - Revert Broken "Rich AI Data" Optimization
**Subagent:** `implementer`
**Priority:** CRITICAL

### Location
`crawler/services/discovery_orchestrator.py` lines 1759-1774

### Problem
Added code that skips secondary searches when "rich data" exists, but:
- The data from list pages is NOT rich
- This skips the crucial step that gets real tasting data from official sources

### Fix
Remove the "STRATEGY 1b" block that was added. Products should ALWAYS go through enrichment unless they meet the minimum data quality threshold (defined in Task 1).

---

## Task 4: FIX - Field Mapping in _normalize_data_for_save
**Subagent:** `implementer`
**Priority:** CRITICAL

### Location
`crawler/services/discovery_orchestrator.py` function `_normalize_data_for_save` (line 958)

### Problem
AI returns data in `enrichment` dict that isn't being mapped:
```python
{
    'enrichment': {
        'tasting_notes': {'nose': ..., 'palate': ..., 'finish': ...},
        'flavor_profile': [...],      # NOT mapped to palate_flavors
        'food_pairings': [...],       # NOT mapped to food_pairings
        'serving_suggestion': '...'   # NOT mapped to serving_recommendation
    }
}
```

### Fix
1. Unpack `enrichment` dict if present
2. Map fields correctly:
   - `enrichment.flavor_profile` → `palate_flavors`
   - `enrichment.food_pairings` → `food_pairings`
   - `enrichment.serving_suggestion` → `serving_recommendation`
   - `enrichment.tasting_notes.nose` → `nose_description`
   - `enrichment.tasting_notes.palate` → `palate_description` (not just initial_taste)
   - `enrichment.tasting_notes.finish` → `finish_description`

---

## Task 5: IMPLEMENT - Minimum Data Quality Threshold
**Subagent:** `implementer`
**Priority:** HIGH

### Objective
Implement configurable data quality threshold that determines when a product has "enough" data.

### Implementation
1. Create `ProductDataQualityChecker` class or function
2. Define required fields based on Task 1 spec
3. Add `is_complete()` method to check if product meets threshold
4. Only skip secondary enrichment if `is_complete()` returns True

### Configuration
```python
MINIMUM_REQUIRED_FIELDS = {
    'whiskey': {
        'required': ['name', 'abv', 'whiskey_type'],
        'tasting_required': 2,  # At least 2 of: nose, palate, finish
        'palate_flavors_min': 3,  # At least 3 flavor tags
    },
    'port_wine': {
        'required': ['name', 'abv', 'port_style'],
        'tasting_required': 2,
        'palate_flavors_min': 3,
    }
}
```

---

## Task 6: IMPLEMENT - Source URL Tracking
**Subagent:** `implementer`
**Priority:** MEDIUM

### Objective
Track which URLs contributed data to each product in `discovery_sources` field.

### Implementation
1. When saving product, record source URL
2. When enriching product, append new source URLs
3. Structure: `[{"url": "...", "fields_extracted": [...], "crawled_at": "..."}]`

---

## Task 7: IMPLEMENT - Search Depth Limit (Safety Switch)
**Subagent:** `implementer`
**Priority:** HIGH

### Objective
Prevent endless searches by limiting URLs crawled per product.

### Implementation
```python
MAX_URLS_PER_PRODUCT = 10  # Safety limit
MAX_SERPAPI_SEARCHES_PER_PRODUCT = 3
MAX_ENRICHMENT_TIME_SECONDS = 300  # 5 minute timeout per product
```

### Logic
1. Track URLs crawled per product
2. Track SerpAPI searches per product
3. Stop enrichment when:
   - Product meets data quality threshold, OR
   - Hit MAX_URLS_PER_PRODUCT, OR
   - Hit MAX_SERPAPI_SEARCHES_PER_PRODUCT, OR
   - Hit MAX_ENRICHMENT_TIME_SECONDS
4. Mark product as "partial" if limits hit before completion

---

## Task 8: TEST - Competition Flow
**Subagent:** `implementation-verifier`
**Priority:** HIGH

### Objective
Test IWSC, SFWSC, and World Whiskies Awards flows end-to-end.

### Test Cases
1. IWSC 2024 - Extract top 5 whiskey winners with full data
2. IWSC 2024 - Extract top 5 port wine winners with full data
3. SFWSC 2024 - Extract winners with full data
4. Verify data quality meets threshold from Task 5

---

## Task 9: TEST - Full E2E Data Quality Verification
**Subagent:** `implementation-verifier`
**Priority:** HIGH

### Objective
Run complete E2E test and verify products meet data quality threshold.

### Success Criteria
- Products have ABV populated
- Products have at least 3 palate_flavors
- Products have nose OR palate OR finish description
- Products have source_url and discovery_sources populated
- No "partial" products due to missing critical data

---

## Execution Order
1. Task 1 (SPEC) - Defines requirements for all other tasks
2. Task 2 (RESEARCH) - Needed for timeout/rate limit configs
3. Tasks 3, 4 (FIX) - Can run in parallel
4. Tasks 5, 6, 7 (IMPLEMENT) - After fixes, can run in parallel
5. Tasks 8, 9 (TEST) - After all implementations
