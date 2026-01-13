# Generic Search Discovery V3 - Task List

**Spec Reference:** `specs/GENERIC_SEARCH_V3_SPEC.md`
**Created:** 2026-01-13
**Last Updated:** 2026-01-13

---

## IMPORTANT: Subagent Instructions

### Progress Recording
**ALL subagents MUST update this file after completing each task:**
1. Change task status from `[ ]` to `[x]`
2. Add completion timestamp
3. Add brief notes on implementation
4. Record any issues or blockers encountered

This protects against conversation crashes and context compaction.

### TDD Methodology
**ALL implementation tasks MUST follow TDD:**
1. Write failing test first (RED)
2. Implement minimum code to pass (GREEN)
3. Refactor while keeping tests green (REFACTOR)
4. Commit with test and implementation together

### Status Legend
- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Completed
- `[!]` - Blocked
- `[-]` - Skipped/Not applicable

---

## Phase 1: Foundation (P0 - Critical)

### Task 1.1: Product Match Validator
**Spec Reference:** Section 5.2 (FEAT-002)
**Assigned To:** `implementer` subagent
**Priority:** P0
**Estimated Complexity:** Medium

#### Description
Create `ProductMatchValidator` class with 3-level validation to prevent enrichment cross-contamination.

#### Subtasks
- [ ] **1.1.1** Create test file `crawler/tests/unit/services/test_product_match_validator.py`
  - Test brand matching (overlap, mismatch, empty cases)
  - Test product type keywords (bourbon vs rye, single malt vs blended)
  - Test name token overlap (>= 30% threshold)
  - Test full validation pipeline
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.1.2** Create `crawler/services/product_match_validator.py`
  - Implement `_validate_brand_match()` per spec
  - Implement `_validate_product_type_keywords()` with MUTUALLY_EXCLUSIVE_KEYWORDS
  - Implement `_validate_name_overlap()` with tokenization
  - Implement main `validate()` method
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.1.3** Add integration test with real product data
  - Test with Frank August Bourbon vs Rye scenario
  - Test with GlenAllachie Single Malt vs Blended scenario
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Correctly rejects "Frank August Rye" when enriching "Frank August Bourbon"
- [ ] Correctly accepts data from same product on different sites

---

### Task 1.2: Confidence-Based Merger
**Spec Reference:** Section 2.4 (COMP-LEARN-004)
**Assigned To:** `implementer` subagent
**Priority:** P0
**Estimated Complexity:** Medium

#### Description
Create `ConfidenceBasedMerger` class that merges extracted data based on confidence scores.

#### Subtasks
- [ ] **1.2.1** Create test file `crawler/tests/unit/services/test_confidence_merger.py`
  - Test higher confidence wins
  - Test array append unique
  - Test dict merge recursive
  - Test None value handling
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.2.2** Create `crawler/services/confidence_merger.py`
  - Implement `merge()` method per spec
  - Handle all field types (string, array, dict, int, float)
  - Track which fields were enriched
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.2.3** Add integration test with real extraction data
  - Test merging detail page (0.95) with review site (0.7)
  - Verify higher confidence data retained
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Detail page data (0.95) not overwritten by review site (0.7)
- [ ] Arrays correctly merged without duplicates

---

### Task 1.3: 3-Step Enrichment Pipeline
**Spec Reference:** Section 5.1 (FEAT-001)
**Assigned To:** `implementer` subagent
**Priority:** P0
**Estimated Complexity:** High

#### Description
Implement the 3-step enrichment pipeline in `EnrichmentOrchestratorV3`.

#### Subtasks
- [ ] **1.3.1** Create test file `crawler/tests/unit/services/test_enrichment_pipeline_v3.py`
  - Test Step 1: Detail page extraction
  - Test Step 2: Producer page search and filter
  - Test Step 3: Review site enrichment
  - Test early exit when COMPLETE reached
  - Test limit enforcement (max_searches, max_sources, max_time)
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.3.2** Implement `_extract_from_detail_page()` in enrichment_orchestrator_v3.py
  - Resolve relative URLs
  - Fetch via SmartRouter
  - Extract with full schema
  - Apply 0.95 confidence floor
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.3.3** Implement `_search_and_extract_producer_page()`
  - Build search query "{brand} {name} official"
  - Filter URLs by priority (official > non-retailer > retailer)
  - Validate product match before accepting
  - Apply confidence boost (+0.1)
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.3.4** Implement `_enrich_from_review_sites()`
  - Load EnrichmentConfigs by priority
  - Execute search with templates
  - Iterate sources until limits/COMPLETE
  - Validate product match for each source
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **1.3.5** Implement main `enrich_product()` orchestration
  - Execute steps sequentially
  - Check status after each step
  - Early exit if COMPLETE
  - Track all sources
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Pipeline stops after Step 1 if COMPLETE reached
- [ ] Product match validation prevents wrong product data
- [ ] All sources tracked (searched, used, rejected)

---

## Phase 2: Quality Integration (P1 - High)

### Task 2.1: Quality Gate V3 Integration
**Spec Reference:** Section 2.8 (COMP-LEARN-008)
**Assigned To:** `implementer` subagent
**Priority:** P1
**Estimated Complexity:** Medium

#### Description
Integrate QualityGateV3 with discovery and enrichment flows.

#### Subtasks
- [ ] **2.1.1** Create test file `crawler/tests/unit/services/test_discovery_quality_integration.py`
  - Test status assessment after extraction
  - Test category-specific requirements
  - Test 90% ECP threshold for COMPLETE
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.1.2** Update `DiscoveryOrchestratorV3` to use QualityGateV3
  - Replace QualityGateV2 calls with V3
  - Pass product_category to assessment
  - Track status progression
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.1.3** Update `EnrichmentOrchestratorV3` to use QualityGateV3
  - Assess before each enrichment step
  - Check for COMPLETE (90% ECP) for early exit
  - Record status_before and status_after
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Blended whiskies reach BASELINE without region/primary_cask
- [ ] COMPLETE status requires 90% ECP

---

### Task 2.2: Source Tracking Enhancement
**Spec Reference:** Section 5.6 (FEAT-006)
**Assigned To:** `implementer` subagent
**Priority:** P1
**Estimated Complexity:** Medium

#### Description
Enhance source tracking with comprehensive audit trail.

#### Subtasks
- [ ] **2.2.1** Create test file `crawler/tests/unit/services/test_source_tracking_v3.py`
  - Test sources_searched tracking
  - Test sources_used tracking
  - Test sources_rejected with reasons
  - Test field_provenance tracking
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.2.2** Create `DiscoveryResultV3` dataclass
  - Add all tracking fields per spec Section 5.6.1
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.2.3** Update `EnrichmentSessionV3` dataclass
  - Add 3-step tracking fields
  - Add field_provenance dict
  - Add status_progression list
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.2.4** Implement field provenance tracking
  - Record source URL for each enriched field
  - Export in results
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Can trace each field back to source URL
- [ ] All rejected sources have reasons logged

---

### Task 2.3: Duplicate Detection
**Spec Reference:** Section 5.7 (FEAT-007)
**Assigned To:** `implementer` subagent
**Priority:** P1
**Estimated Complexity:** Medium

#### Description
Implement duplicate detection to prevent redundant processing.

#### Subtasks
- [ ] **2.3.1** Create test file `crawler/tests/unit/services/test_duplicate_detector.py`
  - Test URL-based deduplication
  - Test content hash deduplication
  - Test product name/brand fuzzy matching
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.3.2** Create `crawler/services/duplicate_detector.py`
  - Implement `_canonicalize_url()`
  - Implement `is_duplicate_url()`
  - Implement `is_duplicate_content()`
  - Implement `find_duplicate_product()`
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **2.3.3** Integrate with discovery flow
  - Check URL before fetching
  - Check content after fetching
  - Check product after extraction
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Same URL not fetched twice
- [ ] Same content not extracted twice

---

## Phase 3: E2E Testing (P1 - High)

### Task 3.1: E2E Test Framework
**Spec Reference:** Section 9 (Testing Strategy)
**Assigned To:** `implementer` subagent
**Priority:** P1
**Estimated Complexity:** High

#### Description
Create comprehensive E2E test matching competition flow quality.

#### Subtasks
- [ ] **3.1.1** Create `tests/e2e/flows/test_generic_search_v3.py`
  - Mirror structure of `test_iwsc_flow.py`
  - Setup fixtures for configs
  - Implement async test infrastructure
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.1.2** Implement search and extraction tests
  - Test real search term execution
  - Test URL filtering
  - Test multi-product extraction
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.1.3** Implement enrichment pipeline tests
  - Test 3-step pipeline with real URLs
  - Test product match validation
  - Test status progression tracking
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.1.4** Implement verification tests
  - Verify all products have required fields
  - Verify source tracking complete
  - Verify no cross-contamination
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.1.5** Implement export and reporting
  - Export results to JSON (like competition flow)
  - Include full audit trail
  - Record test metrics
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] E2E test passes with real URLs
- [ ] >= 70% products reach BASELINE
- [ ] 0 cross-contamination incidents
- [ ] Full audit trail exported

---

### Task 3.2: Test Data and Fixtures
**Spec Reference:** Section 9.3
**Assigned To:** `implementer` subagent
**Priority:** P1
**Estimated Complexity:** Low

#### Description
Create test data and fixtures for E2E testing.

#### Subtasks
- [ ] **3.2.1** Add whiskey search terms to fixtures
  - "best single malt scotch 2025"
  - "bourbon whiskey reviews"
  - "Japanese whisky recommendations"
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.2.2** Add port wine search terms to fixtures
  - "best vintage port wine"
  - "tawny port reviews"
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **3.2.3** Update real_urls.py with test URLs
  - Add producer page URLs
  - Add review site URLs
  - Add retailer URLs (for deprioritization testing)
  - **Status:**
  - **Completed:**
  - **Notes:**

#### Acceptance Criteria
- [ ] All fixture files created
- [ ] Tests can load fixtures successfully

---

## Phase 4: Documentation and Cleanup (P2 - Medium)

### Task 4.1: Code Documentation
**Assigned To:** `implementer` subagent
**Priority:** P2
**Estimated Complexity:** Low

#### Subtasks
- [ ] **4.1.1** Add docstrings to all new classes and methods
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **4.1.2** Update API documentation
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **4.1.3** Add inline comments for complex logic
  - **Status:**
  - **Completed:**
  - **Notes:**

---

### Task 4.2: Cleanup and Refactoring
**Assigned To:** `implementer` subagent
**Priority:** P2
**Estimated Complexity:** Low

#### Subtasks
- [ ] **4.2.1** Remove deprecated V2 code if applicable
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **4.2.2** Consolidate duplicate logic
  - **Status:**
  - **Completed:**
  - **Notes:**

- [ ] **4.2.3** Update imports and exports in `__init__.py`
  - **Status:**
  - **Completed:**
  - **Notes:**

---

## Progress Summary

| Phase | Total Tasks | Completed | In Progress | Blocked |
|-------|-------------|-----------|-------------|---------|
| Phase 1 | 15 | 0 | 0 | 0 |
| Phase 2 | 12 | 0 | 0 | 0 |
| Phase 3 | 8 | 0 | 0 | 0 |
| Phase 4 | 6 | 0 | 0 | 0 |
| **Total** | **41** | **0** | **0** | **0** |

**Last Updated:** 2026-01-13
**Updated By:** Initial creation

---

## Execution Log

### Session: [DATE]
**Agent:** [AGENT_ID]
**Tasks Worked:** [TASK_IDS]
**Status:**
**Notes:**

---

## Blockers and Issues

| Issue ID | Description | Blocking Tasks | Status | Resolution |
|----------|-------------|----------------|--------|------------|
| - | - | - | - | - |

---

## Notes for Subagents

### Before Starting Work
1. Read the full spec: `specs/GENERIC_SEARCH_V3_SPEC.md`
2. Read this task list and identify your assigned tasks
3. Check the execution log for context from previous sessions

### During Work
1. Update task status as you work (`[ ]` → `[~]` → `[x]`)
2. Record any blockers immediately
3. Follow TDD strictly - tests first!

### After Completing Tasks
1. Mark all completed tasks with `[x]`
2. Add completion timestamp and notes
3. Update the Progress Summary table
4. Add entry to Execution Log
5. Commit changes to both code and this file

### If Conversation Crashes
1. Read the Execution Log to understand what was done
2. Check task statuses to see what's complete
3. Resume from the last incomplete task
