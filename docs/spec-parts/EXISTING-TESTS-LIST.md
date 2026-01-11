# Existing Tests in Unified Pipeline Test Directory

**Directory:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\tests\test_unified_pipeline\`

**Purpose:** This document lists all existing test files that will need to be deleted before implementing TDD properly.

---

## Summary

| File | Test Classes | Test Methods (approx) | Phase |
|------|-------------|----------------------|-------|
| `__init__.py` | 0 | 0 | - |
| `test_models.py` | 4 | 27 | Phase 1 |
| `test_health.py` | 6 | 31 | Phase 5 |
| `test_extractors.py` | 2 | 20 | Phase 4 |
| `test_collectors.py` | 6 | 22 | Phase 3 |
| `test_completeness.py` | 9 | 29 | Phase 2 |
| `test_api.py` | 12 | 32 | Phase 6 |
| `test_celery_tasks.py` | 4 | 18 | Phase 7 |
| `test_verification_pipeline.py` | 8 | 21 | Phase 8 |
| `test_documentation.py` | 6 | 26 | Phase 11 |
| `test_product_pipeline.py` | 16 | 43 | Phase 9 |
| `test_component_updates.py` | 10 | 26 | Phase 10 |

**Total: 12 files, 83 test classes, ~275 test methods**

---

## Detailed File Analysis

### 1. `__init__.py`
- **Test Classes:** 0
- **Test Methods:** 0
- **What it tests:** Package marker only (empty file)

---

### 2. `test_models.py`
- **Test Classes:** 4
- **Test Methods:** 27
- **What it tests:** Phase 1 - Unified Product Pipeline models

**Classes:**
1. `TestSourceHealthCheck` (11 tests)
   - Creating selector, yield, fingerprint, and known product health checks
   - Auto-set timestamps, default values, indexes

2. `TestSourceFingerprint` (4 tests)
   - Creating fingerprints, uniqueness constraint, auto-update timestamps

3. `TestAPICrawlJob` (10 tests)
   - Creating API crawl jobs, job_id uniqueness, status choices
   - Progress JSON field, elapsed_seconds calculation, indexes

4. `TestModelTableNames` (3 tests)
   - Verifying correct `db_table` names for all models

---

### 3. `test_health.py`
- **Test Classes:** 6
- **Test Methods:** 31
- **What it tests:** Phase 5 - Structural Change Detection

**Classes:**
1. `TestSelectorHealthChecker` (7 tests)
   - Source selectors configuration
   - Health check returns, healthy/unhealthy detection
   - Unknown source error handling

2. `TestYieldMonitor` (8 tests)
   - Initialization, page tracking
   - Abort after consecutive low-yield pages
   - Counter reset on healthy pages, summary data

3. `TestStructuralFingerprint` (9 tests)
   - Computing hashes, same/different structure detection
   - Ignoring text content changes, detecting attribute changes
   - Storing and retrieving fingerprints

4. `TestAlertHandler` (6 tests)
   - Alert severity levels, StructureAlert dataclass
   - Sending alerts to Sentry
   - Processing selector failures and fingerprint changes

5. `TestHealthModuleIntegration` (2 tests)
   - Module exports, full health check workflow

---

### 4. `test_extractors.py`
- **Test Classes:** 2
- **Test Methods:** 20
- **What it tests:** Phase 4 - AI Extractor

**Classes:**
1. `TestExtractionPrompts` (6 tests)
   - IWSC prompt placeholders and identification
   - DWWA prompt for port wine
   - General prompt structure

2. `TestAIExtractor` (14 tests)
   - Initialization with/without client
   - Prompt selection for different sources (IWSC, DWWA, general)
   - Extract method returns product data with metadata
   - Parsing JSON responses (including markdown-wrapped)
   - Content truncation for token limits

---

### 5. `test_collectors.py`
- **Test Classes:** 6
- **Test Methods:** 22
- **What it tests:** Phase 3 - URL Collectors

**Classes:**
1. `TestAwardDetailURL` (2 tests)
   - Dataclass creation with all/partial fields

2. `TestIWSCCollectorInit` (2 tests)
   - Competition name and base URL configuration

3. `TestIWSCCollectorProductTypeDetection` (7 tests)
   - Detecting port wine, whiskey, gin, vodka
   - Case insensitivity, unknown product types

4. `TestIWSCCollectorMedalExtraction` (5 tests)
   - Extracting gold/silver/bronze medals from image src
   - Extracting from alt text, handling missing medals

5. `TestIWSCCollectorParseListingPage` (3 tests)
   - Extracting detail URLs from cards
   - Skipping cards without links, empty results

6. `TestGetCollector` (3 tests)
   - Factory function, case insensitivity, unknown source errors

---

### 6. `test_completeness.py`
- **Test Classes:** 9
- **Test Methods:** 29
- **What it tests:** Phase 2 - Completeness Scoring

**Classes:**
1. `MockProduct` (helper class)
   - Mock product object for testing

2. `TestTastingProfileWeight` (4 tests)
   - Tasting profile = 40% of max score
   - Palate (20 pts), Nose (10 pts), Finish (10 pts)

3. `TestPalateRequiredForStatus` (4 tests)
   - Palate required for COMPLETE/VERIFIED status
   - Products without palate cannot be complete

4. `TestVerifiedRequirements` (2 tests)
   - VERIFIED requires source_count >= 2

5. `TestStatusThresholds` (3 tests)
   - Incomplete (0-29), Partial (30-59), Complete (60-79), Verified (80+)

6. `TestHasPalateDataFunction` (5 tests)
   - Detecting palate data from flavors, description, initial_taste
   - Single flavor not enough

7. `TestDetermineStatusFunction` (4 tests)
   - Respecting rejected/merged status
   - Score boundary testing

8. `TestCompletenessScoreCalculation` (4 tests)
   - Minimal vs high completeness products

9. `TestBackwardCompatibility` (2 tests)
   - Legacy determine_tier and get_missing_fields functions

---

### 7. `test_api.py`
- **Test Classes:** 12
- **Test Methods:** 32
- **What it tests:** Phase 6 - REST API Tests

**Classes:**
1. `TestAPIModuleExists` (4 tests)
   - API module structure (views, urls, throttling)

2. `TestThrottlingClasses` (4 tests)
   - ExtractionThrottle (50/hour), CrawlTriggerThrottle (10/hour)

3. `TestExtractFromURLEndpoint` (7 tests)
   - URL validation, single product extraction
   - Response structure, save_to_db option, authentication

4. `TestExtractFromURLsEndpoint` (4 tests)
   - Batch extraction, URL list validation, max 50 URLs

5. `TestExtractFromSearchEndpoint` (2 tests)
   - Query validation, search extraction response

6. `TestTriggerAwardCrawlEndpoint` (4 tests)
   - Source validation, async crawl job_id, health check

7. `TestGetCrawlStatusEndpoint` (2 tests)
   - Job not found, job status response

8. `TestListAwardSourcesEndpoint` (2 tests)
   - Sources list response, health status inclusion

9. `TestSourcesHealthEndpoint` (2 tests)
   - Health endpoint response, award_sites section

10. `TestAPIURLRouting` (4 tests)
    - URL route existence verification

---

### 8. `test_celery_tasks.py`
- **Test Classes:** 4
- **Test Methods:** 18
- **What it tests:** Phase 7 - Celery Tasks

**Classes:**
1. `TestTaskModuleStructure` (3 tests)
   - Task existence and Celery task decoration

2. `TestCheckSourceHealthTask` (5 tests)
   - Single source check, all sources check
   - Saving to DB, failure details, alert on critical failure

3. `TestVerifyKnownProductsTask` (6 tests)
   - Verifying known products, detailed results
   - Error handling, saving to DB, unknown source

4. `TestTriggerAwardCrawlTask` (6 tests)
   - Job status updates, collector usage
   - Progress tracking, completion marking

5. `TestCeleryBeatSchedule` (2 tests)
   - Health check and verification tasks in schedule

---

### 9. `test_verification_pipeline.py`
- **Test Classes:** 8
- **Test Methods:** 21
- **What it tests:** Phase 8 - Verification Pipeline

**Classes:**
1. `TestVerificationPipelineModuleExists` (3 tests)
   - Module and class existence

2. `TestVerificationResult` (2 tests)
   - Dataclass fields and conflict capture

3. `TestVerificationPipelineInit` (3 tests)
   - SmartCrawler creation, custom crawler/search client

4. `TestVerifyProductMethod` (5 tests)
   - Returns VerificationResult, searches for sources
   - Extracts from found URLs, updates source_count

5. `TestSearchAdditionalSources` (3 tests)
   - Using product name/brand, limiting results

6. `TestDataMerging` (4 tests)
   - Identical values, conflict detection
   - Majority value resolution, missing fields

7. `TestVerifiedFieldsTracking` (2 tests)
   - Fields verified by 2+ sources, matching values requirement

8. `TestProductStatusUpdate` (1 test)
   - Product reaching VERIFIED status

---

### 10. `test_documentation.py`
- **Test Classes:** 6
- **Test Methods:** 26
- **What it tests:** Phase 11 - API Documentation & Cleanup

**Classes:**
1. `TestOpenAPISchemaGeneration` (11 tests)
   - drf-spectacular settings
   - Schema/Swagger/ReDoc URL configuration
   - API view docstrings

2. `TestOpenAPISchemaContent` (3 tests)
   - Schema endpoint response, paths, info

3. `TestDeprecationWarnings` (6 tests)
   - Deprecation docstrings in legacy modules
   - Deprecation warnings on function calls

4. `TestDeprecatedCodeBackwardCompatibility` (4 tests)
   - Legacy parsers, skeleton_manager, enrichment_searcher still work

5. `TestDeprecationDocumentation` (3 tests)
   - Docstrings explain replacements

6. `TestAPIEndpointAnnotations` (3 tests)
   - Request body and parameter documentation

7. `TestSpecificationTagging` (2 tests)
   - API module and URLs docstrings

---

### 11. `test_product_pipeline.py`
- **Test Classes:** 16
- **Test Methods:** 43
- **What it tests:** Phase 9 - Product Pipeline

**Classes:**
1. `TestProductPipelineModuleExists` (3 tests)
   - Module and class existence

2. `TestPipelineResult` (3 tests)
   - Dataclass fields with success/error/product_id

3. `TestUnifiedProductPipelineInit` (3 tests)
   - Default dependencies, custom AI extractor/crawler

4. `TestProcessUrlMethod` (5 tests)
   - Returns PipelineResult, uses AI extractor
   - Calculates completeness, determines status, saves to DB

5. `TestProcessAwardPageMethod` (3 tests)
   - Returns PipelineResult, passes award context, adds award data

6. `TestStatusDetermination` (3 tests)
   - Incomplete without palate, complete with palate

7. `TestCompletenessScoreCalculation` (2 tests)
   - Full tasting profile, without tasting profile

8. `TestErrorHandling` (3 tests)
   - Extraction failure, empty extraction, invalid URL

9. `TestBrandResolution` (2 tests)
   - Creates brand if not exists, uses existing brand

10. `TestDeduplication` (1 test)
    - Detecting duplicate products

11. `TestPortWineProcessing` (2 tests)
    - Processing port wine, preserving style

12. `TestContextPassing` (1 test)
    - Context passed to extractor

13. `TestProductTypeDetection` (2 tests)
    - Extracted product type, fallback to context

14. `TestHasPalateData` (5 tests)
    - Detecting palate from description, flavors, initial_taste

15. `TestFingerprintComputation` (3 tests)
    - Consistent fingerprints, different for different data
    - Case insensitivity

---

### 12. `test_component_updates.py`
- **Test Classes:** 10
- **Test Methods:** 26
- **What it tests:** Phase 10 - Component Updates

**Classes:**
1. `TestCompetitionOrchestratorModuleUpdates` (4 tests)
   - Module import, run_with_collectors, check_source_health

2. `TestCompetitionOrchestratorHealthCheck` (3 tests)
   - Health check returns dict, includes selector status

3. `TestProductSaverModuleUpdates` (3 tests)
   - Module import, save_discovered_product, VERIFIABLE_FIELDS

4. `TestSmartCrawlerModuleUpdates` (2 tests)
   - Module and class existence

5. `TestSmartCrawlerExtractFromUrl` (4 tests)
   - extract_from_url method, ExtractionResult return
   - Auto-detect page type, handle list pages

6. `TestSmartCrawlerExtractFromUrlsParallel` (3 tests)
   - Parallel extraction, max_workers parameter

7. `TestSmartCrawlerPageTypeDetection` (3 tests)
   - detect_page_type method, single vs list detection

8. `TestComponentErrorHandling` (2 tests)
   - Orchestrator collector errors, SmartCrawler extraction failures

9. `TestProductSaverStatusModelDB` (6 tests - pytest.mark.django_db)
   - Initial status, completeness score, source_count, verified_fields

10. `TestCompetitionOrchestratorWithCollectorsDB` (2 tests - pytest.mark.django_db)
    - run_with_collectors uses collector, aborts on unhealthy source

11. `TestComponentIntegrationDB` (1 test - pytest.mark.django_db)
    - ProductSaver updates after SmartCrawler extraction

---

## Files to Delete for TDD

All 11 Python test files in this directory should be deleted to implement TDD properly:

1. `test_models.py`
2. `test_health.py`
3. `test_extractors.py`
4. `test_collectors.py`
5. `test_completeness.py`
6. `test_api.py`
7. `test_celery_tasks.py`
8. `test_verification_pipeline.py`
9. `test_documentation.py`
10. `test_product_pipeline.py`
11. `test_component_updates.py`

**Note:** Keep `__init__.py` as it's a package marker.

---

## Test Coverage by Phase

| Phase | File(s) | Description |
|-------|---------|-------------|
| Phase 1 | `test_models.py` | Database models (SourceHealthCheck, SourceFingerprint, APICrawlJob) |
| Phase 2 | `test_completeness.py` | Completeness scoring (40% tasting profile, palate required) |
| Phase 3 | `test_collectors.py` | URL collectors (AwardDetailURL, IWSCCollector) |
| Phase 4 | `test_extractors.py` | AI extractor and extraction prompts |
| Phase 5 | `test_health.py` | Structural change detection (selector health, yield monitor, fingerprint) |
| Phase 6 | `test_api.py` | REST API endpoints and throttling |
| Phase 7 | `test_celery_tasks.py` | Celery tasks (crawl, health check, verify) |
| Phase 8 | `test_verification_pipeline.py` | Multi-source verification pipeline |
| Phase 9 | `test_product_pipeline.py` | Unified product pipeline |
| Phase 10 | `test_component_updates.py` | Component updates (orchestrator, saver, SmartCrawler) |
| Phase 11 | `test_documentation.py` | API documentation and deprecation warnings |
