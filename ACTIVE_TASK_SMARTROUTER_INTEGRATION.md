# Active Task: SmartRouter Integration in EnrichmentOrchestratorV3

**Created:** 2026-01-14 00:10
**Status:** IN PROGRESS
**Approach:** TDD (Test Driven Development)

---

## Objective

Override `_fetch_and_extract()` in EnrichmentOrchestratorV3 to use SmartRouter instead of direct httpx. This will enable automatic tier escalation to ScrapingBee for 403 errors.

---

## Task List

### Phase 1: Write Tests First (TDD)
- [x] Task 1.1: Write test for SmartRouter integration in V3
- [x] Task 1.2: Write test for tier escalation on 403 error
- [x] Task 1.3: Write test for ScrapingBee fallback

### Phase 2: Implement
- [x] Task 2.1: Override `_fetch_and_extract()` in V3 (COMPLETE)
- [x] Task 2.2: Initialize SmartRouter in V3 `__init__`
- [x] Task 2.3: Handle SmartRouter response format

### Phase 3: Verify
- [x] Task 3.1: Run unit tests (26 passed)
- [x] Task 3.2: Run competition e2e test (5 passed in 13 min)
- [x] Task 3.3: Compare results with previous run (consistent)

### Phase 4: Commit
- [ ] Task 4.1: Commit changes
- [ ] Task 4.2: Update CURRENT_TASKS.md

---

## Progress Log

### 2026-01-14 00:10 - Started
- Created this task file
- Starting Phase 1: Write tests first

---

## Files to Modify

| File | Change |
|------|--------|
| `crawler/tests/unit/services/test_enrichment_orchestrator_v3.py` | Add SmartRouter tests |
| `crawler/services/enrichment_orchestrator_v3.py` | Override `_fetch_and_extract()` |

---

## Reference

SmartRouter location: `crawler/fetchers/smart_router.py`
- Tier 1: httpx (fast, free)
- Tier 2: Playwright (JavaScript)
- Tier 3: ScrapingBee (blocked sites, 403 errors)
