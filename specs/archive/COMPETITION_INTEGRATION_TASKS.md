# Competition Pipeline Integration Tasks

**Goal:** Integrate competition discovery pipeline into standard crawler flow

**Started:** 2025-12-28
**Status:** In Progress

---

## Phase 1: Test Setup (TDD)

- [x] 1.1 Write test for competition source detection in crawl_source
- [x] 1.2 Write test for competition orchestrator being called for competition sources
- [x] 1.3 Write test for enrich_skeletons periodic task
- [x] 1.4 Write test for process_enrichment_queue periodic task

## Phase 2: Implementation

- [x] 2.1 Modify crawl_source to detect competition sources
- [x] 2.2 Integrate CompetitionOrchestrator into crawl_source
- [x] 2.3 Add enrich_skeletons periodic task
- [x] 2.4 Add process_enrichment_queue periodic task
- [x] 2.5 Update Celery beat schedule for new periodic tasks

## Phase 3: Verification

- [x] 3.1 Run all tests and verify they pass (117 tests passing)
- [x] 3.2 Commit changes

---

## Progress Log

### 2025-12-28 20:XX - Started
- Created task tracking file
- Beginning TDD approach

### 2025-12-28 21:XX - Implementation Complete
- Added competition source detection to crawl_source
- Added _crawl_competition_source helper function
- Added enrich_skeletons periodic task
- Added process_enrichment_queue periodic task
- Updated Celery beat schedule with enrichment tasks
- Added enrichment queue routing

### 2025-12-28 21:XX - All Tests Passing
- Fixed test mock paths (patch at source module, not import location)
- All 117 tests passing
- Ready for commit

