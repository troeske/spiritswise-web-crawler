# Current Tasks - Spiritswise Web Crawler

**Last Updated:** 2026-01-14 10:30
**Purpose:** This file tracks the current active tasks to prevent confusion after conversation compacting or restarts.

---

## ACTIVE TASK

**None** - All tasks complete. Awaiting new instructions.

---

## BACKLOG (Prioritized Improvements)

See **BACKLOG_IMPROVEMENTS.md** for consolidated improvement spec including:
- Performance analysis (Jan 13 vs Jan 14 E2E comparison)
- Root cause analysis
- Detailed implementation plans
- Full cost breakdown

| # | Task | Priority | Status | Tasks |
|---|------|----------|--------|-------|
| 4 | AI Model Selection | P0 | **DONE** (use gpt-4.1) | No code changes |
| 3 | Schema Optimization | P0 | **TODO** | [20 tasks](specs/SCHEMA_OPTIMIZATION_TASKS.md) |
| 1 | Dynamic Site Adaptation | P1 | **TODO** | [18 tasks](specs/DYNAMIC_SITE_ADAPTATION_TASKS.md) |
| 2 | Caching Strategy | P2 | **PARKED** | - |

**Implementation order:** Task 3 (20 tasks, 5-7 days) → Task 1 (18 tasks, 10-15 days) → Task 2 (parked)

---

## JUST COMPLETED (2026-01-14 Morning)

### SmartRouter Integration in V3
**Status:** COMPLETE
**Commits:** 263a1a4, e60486f (pushed to remote)
**Task File:** ACTIVE_TASK_SMARTROUTER_INTEGRATION.md

**Changes:**
1. Override _fetch_and_extract() in V3 to use SmartRouter
2. Automatic tier escalation: httpx -> Playwright -> ScrapingBee
3. Fixes 403 blocking issues by falling back to ScrapingBee
4. Fixed ExtractedProductV2 attribute naming (extracted_data vs data)

**Test Results:**
- 26 unit tests passed
- E2E tests passed (14 min)

**Enrichment Improvements (Before -> After SmartRouter):**
| Product | ECP Before | ECP After | Improvement |
|---------|------------|-----------|-------------|
| SMWS 1.292 | 10.17% | 10.17% | Same ECP, 3x more sources |
| GlenAllachie 10 YO | 11.86% | 16.95% | +43% ECP |
| Ballantine's 10 YO | 10.17% | 25.42% | +150% ECP |

**File size increased 75%** due to richer data (more tasting notes, images, prices)

---

## PREVIOUSLY COMPLETED (2026-01-13 Night)

### Enrichment Quality Investigation & Fixes
**Status:** COMPLETE
**Analysis:** See ENRICHMENT_COMPARISON_2026-01-13.md

**Fixes Implemented:**
1. **QualityGate V3 Override** - EnrichmentOrchestratorV3 now correctly uses V3 quality gate
2. **FieldGroups Creation** - Programmatic creation after ProductTypeConfig (fixture was wrong format)
3. **HTTP Headers Update** - Chrome/131 + full browser headers to avoid 403 blocking
4. **Rate Limiting** - 0.5-1.5s random delay between requests

**Results:**
- ECP now calculated (was always 0.0 before)
- GlenAllachie: 31 fields (up from 21), 5 awards discovered, ECP 28.81%
- Significantly improved enrichment quality

### Config Consolidation (Earlier)
**Status:** COMPLETE
**Commits:** bdbff45, 26565fe

---

## DO NOT WORK ON (Already Complete/Outdated)

- IWSC Detail Page + Producer Page Extraction - NOT a current task
- ENRICHMENT_PIPELINE_V3_TASKS.md - Phase 2 was completed days ago
- SINGLE_PRODUCT_ENRICHMENT_TASKS.md - All 30/30 tasks complete
- Any task not listed in ACTIVE TASK section above

---

## How to Use This File

1. **Before starting work:** Read this file to understand current context
2. **After completing a task:** Update the ACTIVE TASK section
3. **After conversation compacting:** Check this file FIRST before doing anything
4. **If confused about what to do:** Ask the user - do NOT pick up old tasks from spec files
