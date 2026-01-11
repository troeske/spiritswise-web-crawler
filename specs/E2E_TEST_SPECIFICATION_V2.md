# E2E Test Specification - V2 Architecture

**Created**: 2026-01-09
**Status**: APPROVED

---

## Overview

This document specifies the End-to-End (E2E) tests for the V2 architecture. These tests use **real 3rd-party services** and **real web sources** to validate the complete product discovery and enrichment pipeline.

### Key Principles

1. **NO synthetic content** - All tests use real URLs from competition sites
2. **NO mocking of external services** - Real API calls to OpenAI, SerpAPI, ScrapingBee, Wayback
3. **NO data deletion** - All created products remain in database for manual verification
4. **FULL flow coverage** - Every flow and subflow must be exercised
5. **Source tracking verification** - All CrawledSource, ProductSource, ProductFieldSource records must be verifiable
6. **NO SHORTCUTS or WORKAROUNDS** - No test is allowed to implement a workaround or shortcut in case of timeout, errors 

---

## Configuration Requirements

### Required API Keys

All API keys are configured in the `.env` file:

```bash
# AI Enhancement Service (handles OpenAI calls internally)
AI_ENHANCEMENT_SERVICE_URL=<configured>
AI_ENHANCEMENT_SERVICE_TOKEN=<configured>

# SerpAPI - For enrichment search
SERPAPI_API_KEY=<configured>

# ScrapingBee - For JavaScript rendering
SCRAPINGBEE_API_KEY=<configured>

# Sentry - For error tracking
SENTRY_DSN=<configured>
```

**Verified**: All keys present in `.env` file ✓

### Database Configuration

- **Target**: Test Database (as specified)
- **Preservation**: Data MUST NOT be deleted after tests
- **Isolation**: Tests should use unique identifiers to track created records

### Estimated Costs

| Service | Estimated Calls | Estimated Cost |
|---------|-----------------|----------------|
| OpenAI GPT-4 | ~50-75 calls | $8-12 |
| SerpAPI | ~15-30 searches | $2-5 |
| ScrapingBee | ~50-75 renders | $3-5 |
| Wayback Machine | ~30-50 archives | Free (rate limited) |
| **Total** | | **$13-22** |

*Note: Reduced from original estimate due to 15 products instead of 30-45*

---

## Test Scope

### Competition Sources

| Source | Product Type | Year | Expected Products |
|--------|--------------|------|-------------------|
| IWSC | Whiskey | 2025 | 5 |
| SFWSC | Whiskey | 2025 | 5 |
| DWWA | Port Wine | 2025 | 5 |

**Total**: 15 products (10 whiskey + 5 port wine) - ALL will be enriched

### Product Types

- **Whiskey**: Single malt, bourbon, blended, rye, Irish, Japanese
- **Port Wine**: Tawny, Ruby, Vintage, LBV, White

---

## Flow Specifications

### Flow 1: Competition Discovery (IWSC)

**Objective**: Extract award-winning whiskey products from IWSC 2025

**Steps**:
1. Use CompetitionOrchestratorV2 to process IWSC competition URL
2. Extract 5 Gold/Silver medal winners (to match enrichment capacity)
3. For each product:
   - Extract via AIExtractorV2 → AIClientV2 → OpenAI
   - Assess quality via QualityGateV2
   - Create CrawledSource record with raw_content
   - Create DiscoveredProduct with proper status
   - Create ProductAward record with medal, year, competition
   - Link ProductSource for provenance
4. ALL products will be enriched (no queue - immediate enrichment)

**Expected Outputs**:
- 5 DiscoveredProduct records (whiskey)
- 5 ProductAward records (IWSC 2025)
- 5 CrawledSource records with source_url
- Quality status distribution (SKELETON/PARTIAL/COMPLETE)

**Verification Points**:
- [ ] All products have `name` field populated
- [ ] All products have `brand` field populated (or marked for enrichment)
- [ ] All products have `source_url` linking to IWSC
- [ ] Award records have correct `medal`, `competition`, `year`
- [ ] CrawledSource has `raw_content` stored
- [ ] Products with ABV have status >= PARTIAL
- [ ] All products have `palate_flavors` array populated (after enrichment)

---

### Flow 2: Competition Discovery (SFWSC)

**Objective**: Extract award-winning whiskey products from SFWSC 2025

**Required Product**: Must include "Frank August Kentucky Straight Bourbon"

**Steps**:
1. Use CompetitionOrchestratorV2 to process SFWSC competition URL
2. Extract 5 Double Gold/Gold medal winners (to match enrichment capacity)
3. For each product:
   - Extract via AIExtractorV2 → AIClientV2 → OpenAI
   - Assess quality via QualityGateV2
   - Create CrawledSource record with raw_content
   - Create DiscoveredProduct with proper status
   - Create ProductAward record with medal, year, competition
   - Link ProductSource for provenance
4. Focus on bourbon and American whiskey categories

**Expected Outputs**:
- 5 DiscoveredProduct records (whiskey, bourbon category)
- 5 ProductAward records (SFWSC 2025)
- Proper deduplication if same product won multiple awards

**Verification Points**:
- [ ] Bourbon products have `product_category` = "bourbon"
- [ ] American whiskey origin detected
- [ ] No duplicate products (same name + brand)
- [ ] "Frank August Kentucky Straight Bourbon" is captured
- [ ] All products have `palate_flavors` array populated (after enrichment)

---

### Flow 3: Competition Discovery (DWWA)

**Objective**: Extract award-winning port wines from DWWA 2025

**Steps**:
1. Use CompetitionOrchestratorV2 to process DWWA competition URL
2. Extract 5 Gold/Silver medal port wines (to match enrichment capacity)
3. For each product:
   - Extract via AIExtractorV2 → AIClientV2 → OpenAI
   - Use port_wine product type and schema
   - Assess quality via QualityGateV2
   - Create CrawledSource record with raw_content
   - Create DiscoveredProduct with proper status
   - Create ProductAward record with medal, year, competition
   - Link ProductSource for provenance
4. Extract port-specific fields (style, vintage, sweetness)
5. ALL products will be enriched (no queue - immediate enrichment)

**Expected Outputs**:
- 5 DiscoveredProduct records (port_wine)
- 5 ProductAward records (DWWA 2025)
- 5 CrawledSource records with source_url
- PortWineDetails records with style information

**Verification Points**:
- [ ] Products have `product_type` = "port_wine"
- [ ] Port style (tawny, ruby, vintage, etc.) detected
- [ ] Vintage year extracted where applicable
- [ ] Producer/house name extracted
- [ ] All products have `palate_flavors` array populated (after enrichment)

---

### Flow 4: Enrichment Pipeline (Whiskey)

**Objective**: Enrich ALL whiskey products using SerpAPI search

**Steps**:
1. Enrich ALL whiskey products from Flows 1 and 2 (10 total)
2. For each product:
   - Use EnrichmentOrchestratorV2 to search for additional sources
   - Execute SerpAPI search queries (tasting notes, ABV, production info)
   - Fetch top 3-5 search results via ScrapingBee
   - Extract data from each source via AIClientV2
   - Merge data with confidence-based priority
   - Update product status based on new fields
3. Track all sources used for enrichment

**Expected Outputs**:
- ALL 10 whiskey products enriched
- Updated products with additional fields (tasting notes, ABV, palate_flavors, etc.)
- Multiple CrawledSource records per product (competition + enrichment sources)
- ProductFieldSource records showing field provenance
- Status progression (SKELETON → PARTIAL → COMPLETE)

**Verification Points**:
- [ ] ALL 10 whiskey products have been enriched
- [ ] Enrichment sources are different from competition source
- [ ] Field confidences tracked for each source
- [ ] Higher confidence values take priority in merge
- [ ] ProductFieldSource records link fields to correct sources
- [ ] Status improved after enrichment
- [ ] All products have `palate_flavors` array populated

---

### Flow 5: Enrichment Pipeline (Port Wine)

**Objective**: Enrich ALL port wine products

**Steps**:
1. Enrich ALL port wine products from Flow 3 (5 total)
2. For each product:
   - Use EnrichmentOrchestratorV2 to search for additional sources
   - Execute SerpAPI search queries (tasting notes, producer info, vintage notes)
   - Fetch top 3-5 search results via ScrapingBee
   - Extract data from each source via AIClientV2
   - Merge data with confidence-based priority
   - Update product status based on new fields
3. Search for port-specific information (producer history, vintage notes, sweetness level)
4. Track all sources used for enrichment

**Expected Outputs**:
- ALL 5 port wine products enriched
- Updated products with additional fields (tasting notes, palate_flavors, producer details)
- Multiple CrawledSource records per product (competition + enrichment sources)
- ProductFieldSource records showing field provenance
- Status progression (SKELETON → PARTIAL → COMPLETE)

**Verification Points**:
- [ ] ALL 5 port wine products have been enriched
- [ ] Enrichment sources are different from competition source
- [ ] Field confidences tracked for each source
- [ ] ProductFieldSource records link fields to correct sources
- [ ] Status improved after enrichment
- [ ] All products have `palate_flavors` array populated
- [ ] Port-specific fields populated (style, vintage, sweetness)

---

### Flow 6: Single Product Page Extraction

**Objective**: Test direct product page extraction via DiscoveryOrchestratorV2

**Steps**:
1. Use 5 direct product page URLs (not competition pages)
   - e.g., Master of Malt, Wine-Searcher, Whisky Advocate
2. Extract each via DiscoveryOrchestratorV2.extract_single_product()
3. Assess quality and determine enrichment need

**Expected Outputs**:
- 5 DiscoveredProduct records from direct pages
- Quality assessment for each
- Source tracking for direct URLs

**Verification Points**:
- [ ] Products extracted without competition context
- [ ] Source type = "product_page" (not "competition")
- [ ] Full field extraction attempted

---

### Flow 7: List Page Extraction

**Objective**: Test list page extraction (e.g., "Best Whiskeys 2025" articles)

**Mode A: Direct URL Mode (Regression)**

**Steps**:
1. Use 2-3 list page URLs (e.g., Forbes best whiskeys, Wine Enthusiast top picks)
2. Extract via DiscoveryOrchestratorV2.extract_list_products()
3. Create skeleton products for each listed item
4. Follow detail URLs where available

**Expected Outputs**:
- Multiple skeleton products per list page
- Detail URLs captured for follow-up
- Source tracking for list pages

**Verification Points**:
- [ ] Multiple products from single source URL
- [ ] `detail_url` field populated for products with links
- [ ] Skeleton status for incomplete products

**Mode B: SearchTerm Discovery Mode (V2 Spec Section 7)**

**Objective**: Test complete Generic Search Discovery flow

**Spec Reference**: `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md` - Section 7

**Steps**:
1. Create SearchTerms in database with `search_query`, `max_results`, `priority`, `is_active`
2. Execute SerpAPI search for each active SearchTerm (respects `max_results`)
3. Filter organic results only (ads excluded per Section 7.4)
4. Create DiscoveryResult records for each discovered URL
5. Fetch discovered list pages via SmartRouter/ScrapingBee
6. Extract products via AIClientV2 with `is_list_page=True` response
7. Create skeleton products with `detail_url` field
8. Create CrawledSource records with `source_type="list_page"`
9. Track SearchTerm metrics (`search_count`, `products_discovered`, `last_searched`)
10. Apply URL deduplication via CrawledURL model
11. Apply product fingerprint deduplication

**Expected Outputs**:
- SearchTerm records with updated metrics
- DiscoveryResult records with status (SUCCESS/DUPLICATE/SKIPPED)
- CrawledSource records with `source_type="list_page"`
- Skeleton products with extracted `detail_url` where available
- No duplicate products (fingerprint deduplication)

**Verification Points**:
- [ ] SearchTerm.search_query field used (not term_template)
- [ ] SearchTerm.max_results limits per-term crawl count
- [ ] SearchTerm.priority ordering respected (lower = higher priority)
- [ ] Only organic_results from SerpAPI (ads excluded)
- [ ] SearchTerm metrics updated (search_count, products_discovered, last_searched)
- [ ] Seasonal terms filtered via is_in_season() method
- [ ] CrawledSource has source_type="list_page"
- [ ] AI response includes is_list_page=True for multi-product pages
- [ ] detail_url field extracted where links present
- [ ] URL deduplication prevents recrawling same URL
- [ ] Product fingerprint deduplication prevents duplicates

**Test Files**:
- `tests/e2e/flows/test_list_page.py` - TestSearchTermDiscoveryFlow class
- `tests/e2e/flows/test_generic_search_discovery.py` - Full discovery tests
- `tests/e2e/flows/test_search_term_management.py` - SearchTerm configuration tests
- `tests/e2e/flows/test_deduplication.py` - URL and fingerprint deduplication tests

---

### Flow 8: Wayback Machine Archival

**Objective**: Archive all source URLs to Wayback Machine

**Steps**:
1. For all CrawledSource records created in previous flows
2. Submit to Wayback Machine via WaybackService
3. Wait for confirmation and store archive URL
4. Update wayback_status field

**Expected Outputs**:
- All CrawledSource records have `wayback_url` populated
- All have `wayback_status` = "saved"
- All have `wayback_saved_at` timestamp

**Verification Points**:
- [ ] Archive URLs are valid and accessible
- [ ] Original content preserved at archive URL
- [ ] Rate limiting respected (no failures due to throttling)

---

### Flow 9: Source Tracking Verification

**Objective**: Verify complete source-to-product linkage

**Steps**:
1. For each DiscoveredProduct created:
   - Query ProductSource records
   - Query ProductFieldSource records
   - Verify CrawledSource linkage
2. Generate source provenance report

**Expected Outputs**:
- Complete source chain for each product
- Field-level provenance for enriched products

**Verification Points**:
- [ ] Every product has at least 1 ProductSource
- [ ] Enriched products have multiple ProductSource records
- [ ] ProductFieldSource tracks which source provided which field
- [ ] extraction_confidence values are realistic (0.5-1.0)

---

### Flow 10: Quality Progression Verification

**Objective**: Verify quality status progression through pipeline

**Steps**:
1. Track status changes for 10 products through pipeline
2. Verify status progression: SKELETON → PARTIAL → COMPLETE

**Expected Outputs**:
- Status progression log for each product
- Final status distribution

**Verification Points**:
- [ ] No products remain REJECTED (unless genuinely invalid)
- [ ] Products with ABV are at least PARTIAL
- [ ] Products with ABV + description + tasting notes are COMPLETE
- [ ] Enriched products improved in status

---

## Data Preservation

### CRITICAL: Do NOT Delete Test Data

After E2E tests complete:

1. **Products remain in database** - All DiscoveredProduct records persist
2. **Sources remain in database** - All CrawledSource records persist
3. **Awards remain in database** - All ProductAward records persist
4. **Linkages remain in database** - All ProductSource, ProductFieldSource records persist
5. **Raw content preserved** - CrawledSource.raw_content NOT cleared

### Test Data Identification

All test-created records will be tagged with:
- `created_at` timestamps within test execution window
- Specific competition year (2025)
- Traceable source URLs

### Manual Verification Checklist

After tests complete, manually verify:

1. **Product Count**:
   - [ ] 10 whiskey products exist (5 IWSC + 5 SFWSC)
   - [ ] 5 port wine products exist (5 DWWA)
   - [ ] "Frank August Kentucky Straight Bourbon" is present

2. **Award Count**:
   - [ ] 5 IWSC 2025 awards
   - [ ] 5 SFWSC 2025 awards
   - [ ] 5 DWWA 2025 awards

3. **Palate Flavors**:
   - [ ] All 15 products have `palate_flavors` array populated

4. **Source Tracking**:
   - [ ] Each product has >= 1 CrawledSource
   - [ ] ALL enriched products have >= 2 CrawledSource
   - [ ] CrawledSource.raw_content contains HTML

5. **Wayback Archival**:
   - [ ] Most CrawledSource have wayback_url
   - [ ] Archive URLs return HTTP 200

6. **Field Provenance**:
   - [ ] ProductFieldSource records exist for enriched fields
   - [ ] confidence values present and reasonable

---

## Test Execution

### Implementation Guidelines

**Use Expert Subagents**: Use specialized subagents for:
- `implementer` agent for writing test code files
- `test-runner` agent for executing tests and analyzing failures
- `Explore` agent for codebase exploration when needed

**Crash Recovery & Persistence**:
1. After completing each flow implementation, update the status tracking file
2. Status file location: `specs/E2E_EXECUTION_STATUS.md`
3. Before starting work, always check the status file for current progress
4. Reference this spec (`specs/E2E_TEST_SPECIFICATION_V2.md`) for requirements
5. All progress must be recorded BEFORE moving to next task

**Status Tracking Format**:
```markdown
## E2E Implementation Status
- [ ] Test structure and conftest created
- [ ] Flow 1: IWSC Competition - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 2: SFWSC Competition - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 3: DWWA Competition - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 4: Whiskey Enrichment - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 5: Port Wine Enrichment - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 6: Single Product - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 7: List Page - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 8: Wayback Archival - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 9: Source Tracking Verification - NOT STARTED | IN PROGRESS | COMPLETE
- [ ] Flow 10: Quality Progression - NOT STARTED | IN PROGRESS | COMPLETE
```

### Prerequisites

1. Ensure all API keys are configured (verified in `.env`)
2. Verify AI Enhancement Service is running
3. Check database connectivity
4. Estimate ~1.5-2 hours for full test suite

### Execution Command

```bash
# Run full E2E test suite
python -m pytest tests/e2e/test_v2_complete_flow.py -v --tb=long -s

# Run specific flow
python -m pytest tests/e2e/test_v2_complete_flow.py::TestIWSCCompetitionFlow -v -s
```

### Expected Duration

| Flow | Estimated Time |
|------|----------------|
| IWSC Competition (5 products) | 8-12 min |
| SFWSC Competition (5 products) | 8-12 min |
| DWWA Competition (5 products) | 8-12 min |
| Whiskey Enrichment (10 products) | 15-20 min |
| Port Wine Enrichment (5 products) | 8-12 min |
| Single Product | 8-10 min |
| List Page | 8-10 min |
| Wayback Archival | 15-20 min (rate limited) |
| Verification | 5-10 min |
| **Total** | **~1.5-2 hours** |

---

## Output Report

### Report Location

After E2E tests complete, a Markdown report will be generated:

```
specs/E2E_TEST_RESULTS_V2.md
```

### Report Contents

1. **Summary Statistics**
   - Total products created by type
   - Total sources crawled
   - Total awards recorded
   - Quality status distribution

2. **Per-Flow Results**
   - Products created
   - Errors encountered
   - Duration
   - API calls made

3. **Product Details**
   - Name, brand, ABV for each product
   - Quality status
   - Source URLs
   - Award information

4. **Source Tracking Summary**
   - CrawledSource count
   - ProductSource linkages
   - Wayback archival status

5. **Verification Checklist Results**
   - Pass/fail for each verification point

---

## Files to Delete (Previous E2E Tests)

The following files will be deleted before implementing new E2E tests:

### crawler/tests/e2e/
- test_award_discovery_e2e.py
- test_data_quality_e2e.py
- test_error_recovery_e2e.py
- test_generic_search_e2e.py
- test_multi_product_e2e.py
- test_port_wine_e2e.py
- test_real_api_e2e.py
- test_regression_suite.py

### tests/e2e/
- test_award_flow_e2e.py
- test_complete_e2e_flow.py
- test_list_flow_e2e.py
- test_scheduler_full_e2e.py
- test_single_product_flow_e2e.py
- test_verification_e2e.py

### scripts/e2e/
- e2e_data_quality_test.py
- e2e_medal_winners_test.py
- e2e_unified_scheduler_test.py
- run_e2e_flows.py
- run_e2e_test.py

### crawler/tests/test_unified_pipeline/
- test_e2e.py

### Other
- scripts/debug/test_real_e2e.py
- crawler/management/commands/run_e2e_test.py
- crawler/discovery/tests/e2e/ (entire directory)

---

## New E2E Test Structure

### File: tests/e2e/test_v2_complete_flow.py

```
tests/e2e/
├── __init__.py
├── conftest.py                       # Shared fixtures, API clients, factories
├── test_v2_complete_flow.py          # Main orchestrator test
├── flows/
│   ├── __init__.py
│   ├── test_iwsc_flow.py             # IWSC competition flow
│   ├── test_sfwsc_flow.py            # SFWSC competition flow
│   ├── test_dwwa_flow.py             # DWWA competition flow
│   ├── test_enrichment_flow.py       # Enrichment pipeline
│   ├── test_single_product.py        # Single product extraction
│   ├── test_list_page.py             # List page extraction (both modes)
│   ├── test_generic_search_discovery.py  # Generic Search Discovery (V2 Section 7)
│   ├── test_search_term_management.py    # SearchTerm configuration tests
│   ├── test_deduplication.py         # URL and fingerprint deduplication
│   ├── test_wayback_flow.py          # Wayback archival
│   └── test_verification.py          # Source tracking verification
└── utils/
    ├── __init__.py
    ├── real_urls.py                  # Real competition URLs
    ├── report_generator.py           # Markdown report generation
    └── data_verifier.py              # Data verification utilities
```

---

## Questions for Clarification

Please confirm the following before I proceed:

1. **Competition URLs**: Should I use the official competition result pages, or do you have specific URLs you want tested?
-> official result pages

2. **Specific Products**: Are there specific products/brands you want to ensure are captured (e.g., "must include Glenfiddich 18")?
-> Frank August Kentucky straight burboun

3. **Error Handling**: If a competition site is temporarily unavailable, should tests retry or skip that flow?
-> no, wait a little bit and try again

4. **Rate Limiting**: Should tests pause between API calls, and if so, what delays?
-> only rate limit if necessary and for proper etiquette

5. **Parallel Execution**: Should flows run sequentially (safer) or in parallel (faster)?
-> if it does nut hurt the result go parallel

---

## Approval

Please review this specification and confirm:

- [x] Database target confirmed (Test Database)
- [x] API key configuration understood -> .env file
- [x] Cost estimates acceptable (~$25-45)
- [x] Flow coverage complete
- [x] Data preservation requirements clear
- [x] File deletion list approved
- [x] Report format acceptable

Once approved, I will:
1. Delete all previous E2E test files
2. Implement the new E2E test suite
3. Execute tests and generate report
