# V1 to V2 Architecture Migration

**Created**: 2026-01-11
**Status**: IN PROGRESS
**Goal**: Complete migration to V2 architecture and remove all V1 code

---

## Executive Summary

V2 components are fully implemented and have NO dependencies on V1. Production code still uses V1. This migration will:
1. Update production code to use V2 components
2. Update tests to use V2 components
3. Remove V1 files after verification

---

## Architecture Mapping

| V1 Component | V2 Replacement | Status |
|--------------|----------------|--------|
| `ai_client.py` | `ai_client_v2.py` | V2 Ready |
| `competition_orchestrator.py` | `competition_orchestrator_v2.py` | V2 Ready |
| `discovery_orchestrator.py` | `discovery_orchestrator_v2.py` | V2 Ready |
| `ai_extractor.py` | `ai_extractor_v2.py` | V2 Ready |
| (inline enrichment) | `enrichment_orchestrator_v2.py` | V2 Ready |
| (inline quality) | `quality_gate_v2.py` | V2 Ready |

---

## Phase 1: Production Code Migration

### Task 1.1: Migrate tasks.py Competition Functions
**Status**: [x] COMPLETE
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/tasks.py`

**Description**: Update all competition-related functions in tasks.py to use V2 components.

**Changes Required**:
```python
# FROM:
from crawler.services.competition_orchestrator import CompetitionOrchestrator

# TO:
from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2
```

**Functions to Update**:
- [x] `_crawl_competition_source()` (line ~305)
- [x] `enrich_skeletons()` (line ~744)
- [x] `run_competition_flow()` (line ~1264)

**Test Requirements**:
1. Write test that verifies CompetitionOrchestratorV2 is called
2. Write test that verifies V2 quality assessment is used
3. Write test that verifies tasting notes are extracted
4. Run existing competition tests to ensure no regression

**Progress Log**:
- [x] Tests written (crawler/tests/unit/test_tasks_v2_migration.py - 9 tests)
- [x] Code migrated (2026-01-11)
- [x] Tests passing (9/9 passed)
- [x] Reviewed

**Migration Details**:
- Added module-level import: `from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2`
- Updated `_crawl_competition_source()` to use `CompetitionOrchestratorV2()`
- Updated `enrich_skeletons()` to use `CompetitionOrchestratorV2()`
- Updated `run_competition_flow()` to use `CompetitionOrchestratorV2()` and `get_ai_client_v2()`
- Extended `CompetitionOrchestratorV2` with backward-compatible methods:
  - `run_competition_discovery()` - for parsing list pages and creating skeletons
  - `get_pending_skeletons_count()` - for checking enrichment status
  - `process_skeletons_for_enrichment()` - for enriching skeletons
  - Added `CompetitionDiscoveryResult` and `EnrichmentResult` dataclasses
- All 9 unit tests pass:
  - test_crawl_competition_source_uses_v2_orchestrator
  - test_enrich_skeletons_uses_v2_orchestrator
  - test_run_competition_flow_uses_v2_orchestrator
  - test_v2_orchestrator_uses_quality_gate_v2
  - test_v2_orchestrator_assess_quality_method_exists
  - test_ai_client_v2_fallback_schema_includes_tasting_notes
  - test_competition_extraction_result_can_hold_tasting_notes
  - test_tasks_module_has_v2_orchestrator_import
  - test_v1_orchestrator_not_imported
- All 18 existing competition orchestrator unit tests pass
- 5 competition pipeline tests fail due to pre-existing skeleton_manager product type detection issues (not related to V2 migration)

---

### Task 1.2: Migrate tasks.py Discovery Functions
**Status**: [x] COMPLETE
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/tasks.py`, `crawler/services/discovery_orchestrator_v2.py`

**Description**: Update all discovery-related functions in tasks.py to use V2 components.

**Changes Required**:
```python
# FROM:
from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

# TO:
from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2
```

**Functions to Update**:
- [x] `run_discovery_flow()` (line ~1237)

**Test Requirements**:
1. Write test that verifies DiscoveryOrchestratorV2 is called
2. Write test that product extraction uses V2 AI client
3. Write test that enrichment uses EnrichmentOrchestratorV2
4. Run existing discovery tests to ensure no regression

**Progress Log**:
- [x] Tests written (crawler/tests/unit/test_tasks_v2_migration.py - 6 new tests added)
- [x] Code migrated (2026-01-11)
- [x] Tests passing (15/15 passed)
- [x] Reviewed

**Migration Details**:
- Added module-level import: `from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2`
- Updated `run_discovery_flow()` to use `DiscoveryOrchestratorV2(schedule=schedule)`
- Extended `DiscoveryOrchestratorV2` with V1-compatible interface:
  - Added `schedule` parameter to `__init__` for backward compatibility
  - Added `run()` method that creates DiscoveryJob and processes search terms
  - Added `_get_search_terms()`, `_process_search_term()`, `_search()` methods
  - Added `_process_search_result()`, `_is_product_url()`, `_find_existing_product()` methods
  - Added `_extract_and_save_product_v2()` that uses V2 AI client for extraction
  - Added `_SerpAPIClient` helper class for V1 search compatibility
- All 15 unit tests pass:
  - test_run_discovery_flow_uses_v2_orchestrator
  - test_v1_discovery_orchestrator_not_imported
  - test_tasks_module_has_v2_discovery_orchestrator_import
  - test_v2_orchestrator_has_run_method
  - test_v2_orchestrator_accepts_schedule_parameter
  - test_no_v1_imports_remain

---

### Task 1.3: Migrate tasks.py AI Client Usage
**Status**: [x] COMPLETE (N/A - No V1 AI Client imports in tasks.py)
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/tasks.py`

**Description**: Replace all `get_ai_client()` V1 calls with `get_ai_client_v2()`.

**Changes Required**:
```python
# FROM:
from crawler.services.ai_client import get_ai_client

# TO:
from crawler.services.ai_client_v2 import get_ai_client_v2
```

**Verification**:
Grep verification shows NO V1 ai_client imports exist in tasks.py:
```bash
grep -n "from crawler.services.ai_client import" crawler/tasks.py
# Returns empty - NO V1 imports found
```

**Progress Log**:
- [x] Tests written (test_no_v1_imports_remain covers this)
- [x] Code migrated (2026-01-11) - N/A, no V1 imports existed
- [x] Tests passing
- [x] Reviewed

**Notes**: Task 1.3 was verified complete by design - tasks.py never imported the V1 AI client directly. AI client usage flows through the orchestrators which now use V2.

---

### Task 1.4: Migrate tasks.py AI Extractor Usage
**Status**: [x] COMPLETE (N/A - No V1 AI Extractor imports in tasks.py)
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/tasks.py`

**Description**: Replace all `AIExtractor` V1 usage with `AIExtractorV2`.

**Changes Required**:
```python
# FROM:
from crawler.discovery.extractors.ai_extractor import AIExtractor

# TO:
from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2, get_ai_extractor_v2
```

**Verification**:
Grep verification shows NO V1 ai_extractor imports exist in tasks.py:
```bash
grep -n "from crawler.discovery.extractors.ai_extractor import" crawler/tasks.py
# Returns empty - NO V1 imports found
```

**Progress Log**:
- [x] Tests written (test_no_v1_imports_remain covers this)
- [x] Code migrated (2026-01-11) - N/A, no V1 imports existed
- [x] Tests passing
- [x] Reviewed

**Notes**: Task 1.4 was verified complete by design - tasks.py never imported the V1 AI Extractor directly. AI extraction flows through the orchestrators which now use V2.

---

### Task 1.5: Migrate product_pipeline.py
**Status**: [x] COMPLETE
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/services/product_pipeline.py`

**Description**: Update ProductPipeline to use V2 components.

**Changes Required**:
```python
# FROM:
from crawler.discovery.extractors.ai_extractor import AIExtractor
from crawler.services.ai_client import AIEnhancementClient

# TO:
from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2, get_ai_extractor_v2
from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2
```

**Test Requirements**:
1. Write test verifying V2 extractor is used
2. Write test verifying V2 client is used
3. Run existing pipeline tests

**Progress Log**:
- [x] Tests written (crawler/tests/unit/test_product_pipeline_v2.py - 12 tests)
- [x] Code migrated (2026-01-11)
- [x] Tests passing (12/12 passed)
- [x] Reviewed

**Migration Details**:
- Updated `__init__` to use `get_ai_extractor_v2()` instead of `AIExtractor()`
- Updated `__init__` to use `get_ai_client_v2()` instead of `AIEnhancementClient()`
- Added docstring noting V2 migration date and benefits
- All 12 unit tests pass including:
  - test_imports_ai_extractor_v2
  - test_default_extractor_is_v2_type
  - test_extractor_extract_called_with_url_and_context
  - test_smart_crawler_uses_v2_client
  - test_ai_client_v2_imported_not_v1
  - test_palate_fields_extracted
  - test_nose_fields_extracted
  - test_finish_fields_extracted
  - test_completeness_scoring_with_full_tasting_profile
  - test_status_requires_palate_for_complete
  - test_status_complete_with_palate_data
  - test_full_pipeline_with_v2_mocks

---

### Task 1.6: Migrate run_competition_pipeline.py Command
**Status**: [x] COMPLETE
**Subagent**: `implementer`
**TDD**: Required
**Files**: `crawler/management/commands/run_competition_pipeline.py`

**Description**: Update management command to use CompetitionOrchestratorV2.

**Changes Required**:
```python
# FROM:
from crawler.services.competition_orchestrator import CompetitionOrchestrator

# TO:
from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2
```

**Notes**:
- Check if `ensure_competition_sources_exist()` and `COMPETITION_SOURCES` need migration
- These may be shared utilities or need V2 equivalents

**Test Requirements**:
1. Write test that command instantiates V2 orchestrator
2. Test command execution with mock data
3. Verify backward compatibility of command interface

**Progress Log**:
- [x] Tests written (crawler/tests/unit/test_run_competition_pipeline_v2.py - 8 tests)
- [x] Code migrated (2026-01-11)
- [x] Tests passing (8/8 passed)
- [x] Reviewed

**Migration Details**:
- Updated imports to use `CompetitionOrchestratorV2` from `competition_orchestrator_v2`
- Added `COMPETITION_SOURCES` and `ensure_competition_sources_exist()` to V2 module
- Added `get_skeleton_statistics()` method to `CompetitionOrchestratorV2`
- Fixed `by_competition` key access (V2 uses `competition` not `awards__0__competition`)
- All 8 unit tests pass:
  - test_command_uses_v2_orchestrator
  - test_command_imports_v2_not_v1
  - test_command_stats_uses_v2_or_shared_utilities
  - test_command_help_works
  - test_command_handles_async_v2
  - test_statistics_instantiates_v2
  - test_competition_sources_available
  - test_ensure_competition_sources_exist_available
- Command `python manage.py run_competition_pipeline --help` works correctly
- All 24 existing competition V2 tests still pass

---

## Phase 2: API Views Migration

### Task 2.1: Audit and Migrate API Views
**Status**: [ ] NOT STARTED
**Subagent**: `Explore` then `implementer`
**TDD**: Required
**Files**: `crawler/api/views.py`

**Description**: Check all API views for V1 component usage and migrate to V2.

**Steps**:
1. Grep views.py for V1 imports
2. Identify which views use V1 orchestrators/clients
3. Update to V2 equivalents
4. Verify API response format compatibility

**Test Requirements**:
1. Write API tests for each migrated endpoint
2. Verify response schema unchanged
3. Test error handling

**Progress Log**:
- [ ] Audit complete
- [ ] Migration plan documented
- [ ] Tests written
- [ ] Code migrated
- [ ] Tests passing

---

## Phase 3: Test Suite Migration

### Task 3.1: Migrate Unit Tests to V2
**Status**: [ ] NOT STARTED
**Subagent**: `implementer`
**TDD**: N/A (updating tests themselves)
**Files**: `crawler/tests/unit/test_competition_orchestrator.py`, `crawler/tests/unit/test_ai_*.py`

**Description**: Update unit tests that import V1 components.

**Tests to Update**:
- [ ] `test_competition_orchestrator.py`
- [ ] Any tests importing from `ai_client.py` (V1)
- [ ] Any tests importing from `ai_extractor.py` (V1)

**Progress Log**:
- [ ] Tests identified
- [ ] Tests updated
- [ ] All tests passing

---

### Task 3.2: Migrate Integration Tests to V2
**Status**: [ ] NOT STARTED
**Subagent**: `implementer`
**TDD**: N/A
**Files**: `crawler/tests/integration/test_*.py`, `tests/test_competition_*.py`

**Description**: Update integration tests to use V2 components.

**Tests to Update**:
- [ ] `test_ai_service_integration_v2.py` - May need V1 references removed
- [ ] `tests/test_competition_pipeline.py`
- [ ] `tests/test_competition_task_integration.py`

**Progress Log**:
- [ ] Tests identified
- [ ] Tests updated
- [ ] All tests passing

---

## Phase 4: V1 Code Removal

### Task 4.1: Verify No V1 Dependencies Remain
**Status**: [ ] NOT STARTED
**Subagent**: `Explore`
**TDD**: N/A

**Description**: Before removing V1 files, verify NO code imports them.

**Verification Steps**:
```bash
# Run these greps - all should return empty
grep -r "from crawler.services.ai_client import" --include="*.py"
grep -r "from crawler.services.competition_orchestrator import" --include="*.py"
grep -r "from crawler.services.discovery_orchestrator import" --include="*.py"
grep -r "from crawler.discovery.extractors.ai_extractor import" --include="*.py"
```

**Progress Log**:
- [ ] ai_client.py imports: NONE
- [ ] competition_orchestrator.py imports: NONE
- [ ] discovery_orchestrator.py imports: NONE
- [ ] ai_extractor.py imports: NONE

---

### Task 4.2: Remove V1 Files
**Status**: [ ] NOT STARTED
**Subagent**: `Bash`
**TDD**: N/A
**Prerequisite**: Task 4.1 must show ZERO imports

**Files to Remove**:
- [ ] `crawler/services/ai_client.py`
- [ ] `crawler/services/competition_orchestrator.py`
- [ ] `crawler/services/discovery_orchestrator.py`
- [ ] `crawler/discovery/extractors/ai_extractor.py`

**Verification**:
1. Run full test suite after removal
2. Verify no import errors
3. Verify E2E tests pass

**Progress Log**:
- [ ] Files removed
- [ ] Tests passing
- [ ] No import errors

---

### Task 4.3: Remove V1-Specific Tests
**Status**: [ ] NOT STARTED
**Subagent**: `Bash`
**TDD**: N/A

**Description**: Remove tests that only test removed V1 code.

**Evaluation Criteria**:
- If test ONLY tests V1 code → Remove
- If test compares V1 vs V2 → Keep or convert to V2-only
- If test tests shared utilities → Keep

**Progress Log**:
- [ ] Tests evaluated
- [ ] V1-only tests removed
- [ ] Test suite passes

---

## Phase 5: Code Cleanup

### Task 5.1: Remove "_v2" Suffixes (Optional)
**Status**: [ ] NOT STARTED
**Subagent**: `implementer`
**TDD**: Required

**Description**: After V1 removal, rename V2 files to remove "_v2" suffix.

**Renames**:
- `ai_client_v2.py` → `ai_client.py`
- `competition_orchestrator_v2.py` → `competition_orchestrator.py`
- `discovery_orchestrator_v2.py` → `discovery_orchestrator.py`
- `enrichment_orchestrator_v2.py` → `enrichment_orchestrator.py`
- `ai_extractor_v2.py` → `ai_extractor.py`
- `quality_gate_v2.py` → `quality_gate.py`

**Notes**: This is a large refactor affecting many imports. Consider if worth the churn.

**Progress Log**:
- [ ] Decision made: RENAME / KEEP_V2_SUFFIX
- [ ] If renaming: all imports updated
- [ ] Tests passing

---

### Task 5.2: Update Documentation
**Status**: [ ] NOT STARTED
**Subagent**: `Bash` or manual
**TDD**: N/A

**Description**: Update any documentation referencing V1 architecture.

**Files to Check**:
- [ ] README.md
- [ ] docs/*.md
- [ ] specs/*.md (except this file)
- [ ] Code comments mentioning V1

**Progress Log**:
- [ ] Documentation updated
- [ ] No V1 references remain

---

## Execution Order

```
Phase 1 (Production) ──┬── Task 1.1 (Competition) ✓ COMPLETE
                       ├── Task 1.2 (Discovery) ✓ COMPLETE
                       ├── Task 1.3 (AI Client) ✓ COMPLETE (N/A)
                       ├── Task 1.4 (AI Extractor) ✓ COMPLETE (N/A)
                       ├── Task 1.5 (ProductPipeline) ✓ COMPLETE
                       └── Task 1.6 (Management Command) ✓ COMPLETE
                            │
                            ▼
Phase 2 (API) ─────────── Task 2.1 (Views)
                            │
                            ▼
Phase 3 (Tests) ───────┬── Task 3.1 (Unit Tests)
                       └── Task 3.2 (Integration Tests)
                            │
                            ▼
Phase 4 (Removal) ─────┬── Task 4.1 (Verify No Deps)
                       ├── Task 4.2 (Remove V1 Files)
                       └── Task 4.3 (Remove V1 Tests)
                            │
                            ▼
Phase 5 (Cleanup) ─────┬── Task 5.1 (Rename Files - Optional)
                       └── Task 5.2 (Update Docs)
```

---

## Current Progress Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 1: Production | 6 | 6 | COMPLETE |
| Phase 2: API | 1 | 0 | NOT STARTED |
| Phase 3: Tests | 2 | 0 | NOT STARTED |
| Phase 4: Removal | 3 | 0 | NOT STARTED |
| Phase 5: Cleanup | 2 | 0 | NOT STARTED |
| **TOTAL** | **14** | **6** | **43%** |

---

## Subagent Assignment Summary

| Task | Subagent | Reason |
|------|----------|--------|
| 1.1-1.6 | `implementer` | Code changes with TDD |
| 2.1 | `Explore` → `implementer` | Audit first, then implement |
| 3.1-3.2 | `implementer` | Test updates |
| 4.1 | `Explore` | Verification only |
| 4.2-4.3 | `Bash` | File operations |
| 5.1 | `implementer` | Large refactor with TDD |
| 5.2 | `Bash` or manual | Documentation |

---

## Recovery Instructions

If conversation crashes or compacts:
1. Read this file: `specs/V1_TO_V2_MIGRATION_TASKS.md`
2. Check "Progress Log" sections for each task
3. Resume from first uncompleted task
4. Update progress logs as you complete steps

---

## Notes

- V2 components have ZERO dependencies on V1 (verified)
- All E2E tests use V2 and pass
- SmartRouter, SerpAPIClient, ContentPreprocessor are shared utilities (keep)
- EnrichmentOrchestratorV2 already has product validation fix
- AIClientV2 already has tasting notes in fallback schema
- Tasks 1.3 and 1.4 were N/A - tasks.py never directly imported V1 AI client or extractor
