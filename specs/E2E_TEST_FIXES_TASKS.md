# E2E Test Fixes Task List

This document tracks the tasks needed to fix the 3 failing E2E tests identified during the Domain Intelligence E2E test suite execution.

## Summary of Failures

| Test | File | Error | Root Cause | Status |
|------|------|-------|------------|--------|
| test_js_detection_heuristics | test_js_heavy_detection.py | `'EscalationResult' object has no attribute 'recommended_tier'` | Missing attribute in dataclass | **FIXED** |
| test_profile_persistence | test_cloudflare_detection.py | `profile.total_fetches == 0` | Domain key mismatch (www. prefix) | **FIXED** |
| test_single_product_extraction_all_sites | test_single_product_whiskey_e2e.py | `HTTP 400: {'extraction_schema': {'0': ['Not a valid string.']...}}` | Schema format + MAX_RETRIES=0 | **FIXED** |

---

## Task 1: Add `recommended_tier` to EscalationResult

**Status**: [x] COMPLETED

### Problem
The `EscalationResult` dataclass in `crawler/fetchers/escalation_heuristics.py` only has `should_escalate` and `reason` attributes, but the test at `tests/e2e/domain_intelligence/test_js_heavy_detection.py:408` expects `recommended_tier`.

### Fix Applied
Added `recommended_tier: Optional[int] = None` to `EscalationResult` dataclass and updated all return statements in `should_escalate()` to populate `recommended_tier=current_tier + 1` when escalation is recommended.

### Files Modified
1. `crawler/fetchers/escalation_heuristics.py` - Added attribute to dataclass and updated all return statements

### Acceptance Criteria
- [x] `EscalationResult` has `recommended_tier` attribute
- [x] `EscalationHeuristics.should_escalate()` sets `recommended_tier` when escalation is recommended
- [x] `test_js_detection_heuristics` passes

---

## Task 2: Fix Domain Profile Persistence After Fetch

**Status**: [x] COMPLETED

### Problem
After a successful fetch via `SmartRouter.fetch()`, the domain profile's `success_count` and `failure_count` were not being found. The test checked `profile.total_fetches > 0` but got 0.

### Root Cause Found
Domain key mismatch: `extract_domain()` returned `www.masterofmalt.com` but the test was checking for `masterofmalt.com`. The profile was saved under the `www.` key but retrieved with the non-www key.

### Fix Applied
Updated `extract_domain()` in `crawler/fetchers/smart_router.py` to strip the `www.` prefix for consistent domain key generation:
```python
if domain.startswith("www."):
    domain = domain[4:]
```

### Files Modified
1. `crawler/fetchers/smart_router.py` - `extract_domain()` now strips `www.` prefix

### Acceptance Criteria
- [x] After `SmartRouter.fetch()` completes, `profile.total_fetches > 0`
- [x] Profile changes persist across `get_profile()` calls
- [x] `test_profile_persistence` passes

---

## Task 3: Fix AI Client V2 extraction_schema Format

**Status**: [x] COMPLETED

### Problem
Two issues:
1. The AI Enhancement Service API returns HTTP 400 because it expects `extraction_schema` to be a list of strings (field names), but the client was sending a list of dictionaries (full schema objects).
2. `CRAWLER_MAX_RETRIES = 0` in test settings meant Tier 1 made 0 attempts, always failing immediately.

### Fix Applied
1. Updated `_build_request()` in `crawler/services/ai_client_v2.py` to convert schema dicts to field names:
```python
if extraction_schema and isinstance(extraction_schema[0], dict):
    api_schema = [field.get("name") for field in extraction_schema if field.get("name")]
```

2. Updated `config/settings/test.py` to set `CRAWLER_MAX_RETRIES = 1` (at least 1 attempt needed)

### Files Modified
1. `crawler/services/ai_client_v2.py` - `_build_request()` converts schema dicts to field names
2. `config/settings/test.py` - Changed `CRAWLER_MAX_RETRIES` from 0 to 1

### Acceptance Criteria
- [x] `extraction_schema` sent in correct format
- [x] API accepts the request (no HTTP 400)
- [x] Products are successfully extracted
- [x] `test_single_product_extraction_all_sites` passes

---

## Final Test Results

All 3 previously failing tests now pass:

```
tests/e2e/domain_intelligence/test_js_heavy_detection.py::TestJSHeavyDetection::test_js_detection_heuristics PASSED
tests/e2e/domain_intelligence/test_cloudflare_detection.py::TestCloudflareDetection::test_profile_persistence PASSED
tests/e2e/flows/test_single_product_whiskey_e2e.py::TestSingleProductWhiskeyE2E::test_single_product_extraction_all_sites PASSED
```

E2E Test Suite: **23/23 tests passing (100%)**
