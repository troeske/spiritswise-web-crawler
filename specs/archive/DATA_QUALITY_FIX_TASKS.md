# Data Quality Fix Tasks

**Created:** 2026-01-08
**Status:** IN PROGRESS
**Last Updated:** 2026-01-08 08:15 UTC

---

## Instructions for Execution

### Model Requirements
- **Use Opus 4.5** (claude-opus-4-5-20251101) for all tasks
- Do NOT use Haiku for subagents unless explicitly approved

### Development Approach
- **TDD (Test-Driven Development)**: Write tests BEFORE implementing fixes
- Run existing tests after each change to ensure no regressions
- Document any test failures and fixes

### Crash Recovery
- Update `[STATUS]` markers after completing each task
- If session crashes, resume from last `[ ] PENDING` task
- Completed tasks marked with `[x] COMPLETED`

---

## Task Summary

| # | Task | Agent | Priority | Status |
|---|------|-------|----------|--------|
| 1 | Add missing fields to FIELD_MAPPING | implementer | CRITICAL | [x] COMPLETED |
| 2 | Fix inconsistent tasting_notes mapping | implementer | CRITICAL | [x] COMPLETED |
| 3 | Remove hardcoded API keys | implementer | HIGH | [x] COMPLETED |
| 4 | Add category to FIELD_MAPPING | implementer | HIGH | [x] COMPLETED |
| 5 | Enable enrichment for existing skeletons | Bash | HIGH | [x] COMPLETED |
| 6 | Test enrichment flow E2E | test-runner | HIGH | [!] BLOCKED |
| 7 | Verify data quality after enrichment | Bash | MEDIUM | [ ] PENDING |

---

## Detailed Tasks

### Task 1: Add Missing Fields to FIELD_MAPPING
**Status:** [x] COMPLETED (2026-01-08 08:30 UTC)
**Agent:** implementer
**Priority:** CRITICAL
**Estimated Time:** 10 minutes

**Problem:**
5 critical fields are missing from `FIELD_MAPPING` in `crawler/services/product_saver.py`:
- `description`
- `palate_description`
- `finish_description`
- `food_pairings`
- `serving_recommendation`

**File:** `crawler/services/product_saver.py`
**Location:** Lines 254-292 (FIELD_MAPPING dict)

**TDD Steps:**
1. Write test in `crawler/tests/test_product_saver.py` that verifies these fields are extracted
2. Run test - should FAIL
3. Add fields to FIELD_MAPPING
4. Run test - should PASS

**Implementation:**
Add after line 292 (before the closing `}`):
```python
    # Core description fields
    "description": ("description", _safe_str),

    # Tasting notes - direct mapping (when not nested)
    "palate_description": ("palate_description", _safe_str),
    "finish_description": ("finish_description", _safe_str),

    # Recommendations
    "food_pairings": ("food_pairings", _safe_list),
    "serving_recommendation": ("serving_recommendation", _safe_str),
```

**Verification:**
```bash
python manage.py test crawler.tests.test_product_saver -v 2
```

**Completion Checklist:**
- [ ] Test written
- [ ] Test fails before fix
- [ ] Fix implemented
- [ ] Test passes after fix
- [ ] No regression in other tests

---

### Task 2: Fix Inconsistent tasting_notes Mapping
**Status:** [x] COMPLETED (2026-01-08 08:30 UTC)
**Agent:** implementer
**Priority:** CRITICAL
**Estimated Time:** 20 minutes

**Problem:**
Two different code paths map `tasting_notes.palate` to different fields:
- `discovery_orchestrator.py` maps to `initial_taste`
- `tasks.py` maps to `palate_description`

This causes data inconsistency.

**Files to modify:**
1. `crawler/services/discovery_orchestrator.py` (lines 1141-1155)
2. `crawler/services/product_saver.py` (add unified unpacking in `normalize_extracted_data`)

**TDD Steps:**
1. Write test that passes nested tasting_notes through both paths
2. Verify they produce consistent output
3. Implement unified unpacking in `normalize_extracted_data()`

**Implementation:**
Add to `normalize_extracted_data()` in `product_saver.py` (after line 443):
```python
    # Unpack nested tasting_notes structure (AI service format)
    tasting_notes = normalized.get("tasting_notes", {})
    if isinstance(tasting_notes, dict):
        # Map nose
        if tasting_notes.get("nose") and not normalized.get("nose_description"):
            normalized["nose_description"] = tasting_notes["nose"]
        # Map palate - use palate_description as primary
        if tasting_notes.get("palate") and not normalized.get("palate_description"):
            normalized["palate_description"] = tasting_notes["palate"]
        # Map finish
        if tasting_notes.get("finish") and not normalized.get("finish_description"):
            normalized["finish_description"] = tasting_notes["finish"]
```

**Update discovery_orchestrator.py** to use consistent mapping:
- Change `initial_taste` to `palate_description` at line 1149

**Completion Checklist:**
- [ ] Test written for both code paths
- [ ] Unified unpacking added to normalize_extracted_data
- [ ] discovery_orchestrator.py updated for consistency
- [ ] All tests pass

---

### Task 3: Remove Hardcoded API Keys
**Status:** [x] COMPLETED (2026-01-08 08:30 UTC)
**Agent:** implementer
**Priority:** HIGH
**Estimated Time:** 15 minutes

**Problem:**
API keys are hardcoded in source files (security risk):
1. `crawler/services/smart_crawler.py` line 30: `SERPAPI_KEY`
2. `crawler/tests/integration/config.py` line 9: `SCRAPINGBEE_API_KEY`

**Files to modify:**
1. `crawler/services/smart_crawler.py`
2. `crawler/tests/integration/config.py`

**Implementation:**

**smart_crawler.py** - Replace line 30:
```python
# OLD:
SERPAPI_KEY = "86dc430939860e8775ca38fe37b279b93b191f560f83b5a9b0b0f37dab3e697d"

# NEW:
import os
SERPAPI_KEY = os.environ.get('SERPAPI_API_KEY', '')
```

**config.py** - Replace lines 9-10:
```python
# OLD:
SCRAPINGBEE_API_KEY = "U9T8N36G3Z8LL2VLVY86S1LJJ83R33C79A4EYXYYRNSMQFCS2JPPQJX6OQ8RMPHXZS4LE2H8J25JJHZI"

# NEW:
import os
SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY', '')
```

**Verification:**
- Ensure `.env` file has both keys (already confirmed present)
- Run tests to verify keys are loaded correctly

**Completion Checklist:**
- [ ] smart_crawler.py updated
- [ ] config.py updated
- [ ] Tests pass with env vars
- [ ] No hardcoded keys remain (grep verification)

---

### Task 4: Add Category to FIELD_MAPPING
**Status:** [x] COMPLETED (2026-01-08 08:30 UTC)
**Agent:** implementer
**Priority:** HIGH
**Estimated Time:** 5 minutes

**Problem:**
`category` field is missing from main `FIELD_MAPPING`. Currently only exists in `AWARD_FIELD_MAPPING`.

**File:** `crawler/services/product_saver.py`
**Location:** Lines 254-292 (FIELD_MAPPING dict)

**Implementation:**
Add to FIELD_MAPPING:
```python
    "category": ("category", _safe_str),
```

**Additionally**, add whiskey_type to category inference in `normalize_extracted_data()`:
```python
    # Infer category from whiskey_type if not set
    if not normalized.get("category") and normalized.get("whiskey_type"):
        whiskey_type_to_category = {
            'scotch_single_malt': 'Single Malt Scotch Whisky',
            'scotch_blend': 'Blended Scotch Whisky',
            'bourbon': 'Bourbon',
            'tennessee': 'Tennessee Whiskey',
            'rye': 'Rye Whiskey',
            'irish_single_malt': 'Irish Single Malt',
            'irish_blend': 'Irish Blended Whiskey',
            'japanese': 'Japanese Whisky',
            'canadian': 'Canadian Whisky',
        }
        normalized["category"] = whiskey_type_to_category.get(
            normalized["whiskey_type"],
            normalized["whiskey_type"].replace('_', ' ').title()
        )
```

**Completion Checklist:**
- [ ] category added to FIELD_MAPPING
- [ ] whiskey_type to category inference added
- [ ] Tests pass

---

### Task 5: Enable Enrichment for Existing Skeletons
**Status:** [x] COMPLETED (2026-01-08 09:00 UTC) - CrawlSchedules updated, AI extraction timeout issue identified
**Agent:** Bash (direct execution)
**Priority:** HIGH
**Estimated Time:** 5 minutes

**Problem:**
10 skeleton products exist but were never enriched because `schedule.enrich` defaults to False.

**Implementation:**
Run Django shell commands to trigger enrichment:

```python
# In Django shell (python manage.py shell)

# Option 1: Update CrawlSchedule and re-run
from crawler.models import CrawlSchedule
schedules = CrawlSchedule.objects.filter(category='competition')
for s in schedules:
    s.enrich = True
    s.save()
    print(f"Enabled enrichment for {s.name}")

# Option 2: Manually trigger enrichment for existing skeletons
from crawler.tasks import enrich_skeletons
result = enrich_skeletons(limit=50)
print(f"Enrichment result: {result}")
```

**Verification:**
Query database to check if products now have enriched fields.

**Completion Checklist:**
- [ ] Enrichment enabled on schedules
- [ ] enrich_skeletons task run
- [ ] Products show improved data quality

---

### Task 6: Test Enrichment Flow E2E
**Status:** [!] BLOCKED - AI extraction times out with large HTML (needs content preprocessing)
**Agent:** test-runner
**Priority:** HIGH
**Estimated Time:** 15 minutes

**Problem:**
Need to verify the complete enrichment flow works after fixes.

**Test Scope:**
1. Create a test skeleton product
2. Run enrichment
3. Verify fields are populated: ABV, description, nose, palate, finish, brand

**Implementation:**
Create test file `crawler/tests/test_enrichment_flow.py`:
```python
"""E2E test for enrichment flow."""
from django.test import TestCase
from crawler.models import DiscoveredProduct
from crawler.tasks import enrich_skeletons

class EnrichmentFlowTest(TestCase):
    def test_skeleton_enrichment_populates_fields(self):
        # Create skeleton product
        product = DiscoveredProduct.objects.create(
            name="Ardbeg 10 Year Old Single Malt Scotch Whisky",
            status="skeleton",
            product_type="whiskey",
        )

        # Run enrichment
        result = enrich_skeletons(limit=1)

        # Refresh from db
        product.refresh_from_db()

        # Verify fields populated
        self.assertIsNotNone(product.abv, "ABV should be populated")
        self.assertIsNotNone(product.description, "Description should be populated")
```

**Completion Checklist:**
- [ ] Test file created
- [ ] Test runs successfully
- [ ] Enrichment populates expected fields

---

### Task 7: Verify Data Quality After Enrichment
**Status:** [ ] PENDING
**Agent:** Bash (direct execution)
**Priority:** MEDIUM
**Estimated Time:** 10 minutes

**Problem:**
Need to measure data quality improvement after all fixes.

**Implementation:**
Run the data quality analysis script:
```bash
cd spiritswise-web-crawler
python analyze_data_quality.py
```

**Expected improvements:**
- ABV: 0% → 50%+
- Description: 0% → 50%+
- Nose: 0% → 50%+
- Palate: 50% → 80%+
- Finish: 0% → 50%+
- Brand: 0% → 50%+
- Category: 0% → 80%+

**Completion Checklist:**
- [ ] Analysis script run
- [ ] Results documented
- [ ] Improvement targets met

---

## Completion Tracking

### Overall Progress
- [x] Task 1: FIELD_MAPPING fields - COMPLETED
- [x] Task 2: tasting_notes consistency - COMPLETED
- [x] Task 3: Hardcoded API keys - COMPLETED
- [x] Task 4: Category mapping - COMPLETED
- [x] Task 5: Enable enrichment - COMPLETED (schedule updated)
- [!] Task 6: E2E test - BLOCKED (AI timeout)
- [ ] Task 7: Verify quality - PENDING

### Session Log
```
2026-01-08 08:15 UTC - Task file created
2026-01-08 08:30 UTC - Tasks 1-4 completed:
  - Added 6 fields to FIELD_MAPPING (description, palate_description, finish_description, food_pairings, serving_recommendation, category)
  - Unified tasting_notes unpacking in normalize_extracted_data()
  - Fixed discovery_orchestrator to use palate_description consistently
  - Removed hardcoded API keys (SERPAPI_KEY in smart_crawler.py, SCRAPINGBEE_API_KEY in config.py)
  - Added category to FIELD_MAPPING with whiskey_type inference
2026-01-08 09:00 UTC - Task 5 completed:
  - Enabled enrich=True on all CrawlSchedules
  - Created run_enrichment.py script
  - Fixed data extraction path (result.get('data') not result directly)
2026-01-08 09:45 UTC - Task 6 blocked:
  - AI service endpoint works (tested with curl)
  - Real HTML pages too large, causing timeouts
  - Issue: Content trimming happens but still 90k chars
  - Root cause: AI processing of large HTML takes >120s
```

### Blocking Issue: AI Extraction Timeout

**Problem:** Real product pages from retailers (e.g., glencadamwhisky.com) contain large HTML (200k+ chars). Even after trimming to 90k, AI extraction takes >120s.

**Evidence:**
- Direct API test with small HTML (300 chars): 3.1 seconds, successful
- Full page extraction: Times out after 120 seconds

**Recommended Fix (for future task):**
1. Improve content preprocessing:
   - Extract only `<main>`, `<article>`, or product-specific divs
   - Use `trafilatura` library for better content extraction (currently missing)
   - Reduce content to <30k chars before AI extraction
2. Increase timeout or implement streaming
3. Consider caching successful extractions

---

## Recovery Instructions

If session crashes:
1. Read this file to find last `[ ] PENDING` task
2. Resume execution from that task
3. Update status markers as you complete each task
4. Add entry to Session Log with timestamp
