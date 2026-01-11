# Spec Implementation Gap Analysis - Task List

**Created:** 2026-01-06
**Purpose:** Address all identified gaps in the Unified Product Discovery Flow implementation
**Approach:** TDD (Test-Driven Development) - Write failing tests FIRST, then implement
**Validation:** All integration/E2E tests MUST use VPS AI Service (api.spiritswise.tech) and real URLs

---

## Executive Summary

### Identified Gaps:
1. **Missing Collectors:** DWWACollector, SFWSCCollector, WWACollector (75% of collectors missing)
2. **Untested Flows:** All three flows lack end-to-end integration tests with real VPS
3. **Unverified Pipeline:** Completeness scoring, status transitions, verification pipeline not tested with real data

### Spec References:
- `docs/FLOW_COMPARISON_ANALYSIS.md` - Master spec (3330 lines)
- `docs/spec-parts/01-CRITICAL-REQUIREMENTS.md` - Critical requirements
- `docs/spec-parts/02-04-FLOW-ANALYSIS-PROBLEMS.md` - Flow analysis & collectors
- `docs/spec-parts/05-UNIFIED-ARCHITECTURE.md` - Unified pipeline architecture
- `docs/spec-parts/07-VERIFICATION-PIPELINE.md` - Multi-source verification
- `docs/spec-parts/08-IMPLEMENTATION-PLAN.md` - Implementation details

---

## Task Group 1: Missing URL Collectors

### Task 1.1: Implement DWWACollector (Playwright) - COMPLETE
**Priority:** CRITICAL (Required for Port Wine discovery)
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 1.5 (lines 385-714)
**Assigned Agent:** `implementer`
**Status:** COMPLETE (2026-01-06)

**TDD Approach:**
1. Write failing tests in `tests/collectors/test_dwwa_collector.py`:
   - `test_collector_uses_playwright_for_js_rendering`
   - `test_applies_fortified_filter_for_port_wines`
   - `test_extracts_detail_urls_from_listing`
   - `test_detects_port_style_from_card_text`
   - `test_handles_pagination_or_infinite_scroll`
   - `test_collects_urls_for_non_portuguese_port_wines` (South Africa, Australia)
2. Implement `crawler/discovery/collectors/dwwa_collector.py`
3. Tests MUST pass with real Decanter website (https://awards.decanter.com)

**Acceptance Criteria:**
- [x] Playwright launches headless browser
- [x] Navigates to DWWA and waits for JS render
- [x] Applies "Fortified" category filter
- [x] Extracts detail page URLs with medal hints
- [x] Detects port styles (tawny, ruby, vintage, LBV, colheita)
- [x] Handles non-Portuguese port wines (Cape Port, Australian fortified)
- [x] All tests pass with real DWWA website (24/24 tests passed)

**Implementation Details from Spec:**
```python
class DWWACollector:
    """
    Collects Port/Fortified wine detail page URLs from Decanter World Wine Awards.
    Requires Playwright for JavaScript rendering.
    """
    BASE_URL = "https://awards.decanter.com"

    async def collect(self, year: int) -> List[AwardDetailURL]:
        # 1. Launch Playwright headless browser
        # 2. Navigate to DWWA/{year}
        # 3. Apply "Fortified" filter
        # 4. Paginate through results
        # 5. Extract detail page URLs
```

**Completed Files:**
- `tests/collectors/test_dwwa_collector.py` - 24 tests
- `crawler/discovery/collectors/dwwa_collector.py` - Implementation
- `crawler/discovery/collectors/__init__.py` - Updated exports
- `crawler/discovery/collectors/base_collector.py` - Updated factory

---

### Task 1.2: Implement SFWSCCollector
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 1.4
**Assigned Agent:** `implementer`

**TDD Approach:**
1. Write failing tests in `tests/test_sfwsc_collector.py`:
   - `test_extracts_urls_from_tasting_alliance_results`
   - `test_filters_whiskey_categories`
   - `test_extracts_medal_and_score_hints`
   - `test_handles_pagination`
2. Implement `crawler/discovery/collectors/sfwsc_collector.py`
3. Tests MUST pass with real SF World Spirits Competition website

**Acceptance Criteria:**
- [ ] Parses thetastingalliance.com/results/ pages
- [ ] Extracts whiskey product detail URLs
- [ ] Captures medal type and score hints
- [ ] All tests pass with real SFWSC website

---

### Task 1.3: Implement WWACollector
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 1.4
**Assigned Agent:** `implementer`

**TDD Approach:**
1. Write failing tests in `tests/test_wwa_collector.py`:
   - `test_extracts_urls_from_world_whiskies_awards`
   - `test_filters_by_year_and_category`
   - `test_extracts_winner_details`
   - `test_handles_category_pages`
2. Implement `crawler/discovery/collectors/wwa_collector.py`
3. Tests MUST pass with real World Whiskies Awards website

**Acceptance Criteria:**
- [ ] Parses worldwhiskiesawards.com/winners pages
- [ ] Extracts whiskey product detail URLs
- [ ] Captures award category (World's Best, etc.)
- [ ] All tests pass with real WWA website

---

## Task Group 2: Award/Competition Flow Integration Tests

### Task 2.1: IWSCCollector Integration Tests with Real URLs
**Priority:** CRITICAL
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 1.4 (lines 144-346)
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_iwsc_flow.py`:
   - `test_collects_real_urls_from_iwsc_2024`
   - `test_collects_real_urls_from_iwsc_2025`
   - `test_extracts_whiskey_detail_urls`
   - `test_extracts_port_wine_detail_urls` (Fortified category)
   - `test_medal_hints_match_actual_awards`
2. All tests use real IWSC website (https://www.iwsc.net)
3. Verify collected URLs are valid and accessible

**Acceptance Criteria:**
- [ ] Collector returns 50+ valid URLs from IWSC 2024
- [ ] Port wines identified via Fortified/Wine category
- [ ] Medal hints (Gold, Silver, Bronze) extracted correctly
- [ ] All URLs are reachable (HTTP 200)

---

### Task 2.2: AI Extraction from Award Detail Pages
**Priority:** CRITICAL
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 1.4, `08-IMPLEMENTATION-PLAN.md` Section 8.3
**Assigned Agent:** `implementation-verifier`

**Requirements:**
- Must use VPS AI Service: `https://api.spiritswise.tech/api/v1/enhance/from-crawler/`
- Must use real IWSC detail page URLs

**TDD Approach:**
1. Create `tests/integration/test_award_ai_extraction.py`:
   - `test_extracts_product_name_from_iwsc_detail`
   - `test_extracts_medal_and_score`
   - `test_extracts_tasting_notes_if_available`
   - `test_extracts_producer_and_country`
   - `test_extracts_category_details` (age, style)
   - `test_whiskey_type_normalized_correctly`
   - `test_port_wine_style_extracted` (tawny, ruby, etc.)
2. Use real IWSC detail pages (e.g., /results/detail/157656/...)
3. Verify AI service extracts all available fields

**Acceptance Criteria:**
- [ ] AI extracts product name with >90% accuracy
- [ ] AI extracts tasting notes when available on page
- [ ] AI returns correct product_type (whiskey or port_wine)
- [ ] Extraction completes within 30 seconds
- [ ] All tests use VPS AI service (not mocks)

---

### Task 2.3: Full Award Flow End-to-End Test
**Priority:** CRITICAL
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Sections 1-2, `05-UNIFIED-ARCHITECTURE.md` Section 5.2
**Assigned Agent:** `implementation-verifier`

**Requirements:**
- Real IWSC website
- VPS AI Service
- Real database writes

**TDD Approach:**
1. Create `tests/e2e/test_award_flow_e2e.py`:
   - `test_full_iwsc_whiskey_discovery_flow`:
     1. IWSCCollector collects URLs from real IWSC
     2. AIExtractor extracts from detail pages via VPS
     3. ProductCandidate created with award data
     4. UnifiedProductPipeline processes candidate
     5. DiscoveredProduct saved to database
     6. ProductAward record created
     7. Completeness score calculated correctly
     8. Status set based on data completeness
   - `test_full_iwsc_port_wine_discovery_flow`:
     1. Same flow but for Fortified/Port category
     2. PortWineDetails created (not WhiskeyDetails)
     3. Port style extracted (tawny, ruby, etc.)

**Acceptance Criteria:**
- [ ] Full flow completes without errors
- [ ] DiscoveredProduct has correct data in individual columns (not JSON blob)
- [ ] ProductAward linked to product with competition/year/medal
- [ ] WhiskeyDetails or PortWineDetails created based on product type
- [ ] Completeness score reflects actual data completeness
- [ ] Status is INCOMPLETE/PARTIAL (not COMPLETE without palate)

---

## Task Group 3: Generic Search List Page Flow Integration Tests

### Task 3.1: List Page Multi-Product Extraction
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2.2 (lines 779-831), `08-IMPLEMENTATION-PLAN.md` Section 8.3
**Assigned Agent:** `implementation-verifier`

**Requirements:**
- VPS AI Service for list extraction
- Real blog/review URLs (e.g., whiskyadvocate.com, thewhiskyexchange.com blog)

**TDD Approach:**
1. Create `tests/integration/test_list_extraction.py`:
   - `test_extracts_multiple_products_from_top_10_article`
   - `test_extracts_product_names_and_links`
   - `test_extracts_ratings_if_present`
   - `test_handles_pages_without_direct_links`
   - `test_limits_extraction_to_reasonable_count` (max 20)
2. Use real "Top 10 Whiskey" type articles
3. Verify AI identifies all products on page

**Acceptance Criteria:**
- [ ] AI extracts 3-20 products from list page
- [ ] Product names accurately match page content
- [ ] Direct product links extracted when available
- [ ] Ratings/scores extracted when present
- [ ] All tests use VPS AI service

---

### Task 3.2: List Page Enrichment Flow
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2.2, `08-IMPLEMENTATION-PLAN.md` Section 8.4
**Assigned Agent:** `implementation-verifier`

**Requirements:**
- VPS AI Service
- Real URLs
- SerpAPI for products without links (can be mocked for cost control)

**TDD Approach:**
1. Create `tests/integration/test_list_enrichment.py`:
   - `test_enriches_product_with_direct_link`:
     1. Extract product from list page
     2. If direct_product_link present, crawl it
     3. AI extracts full details from product page
     4. Merge into ProductCandidate
   - `test_enriches_product_via_search_when_no_link`:
     1. Extract product without link
     2. SerpAPI search triggers
     3. Best result crawled and extracted
   - `test_saves_partial_product_when_enrichment_fails`

**Acceptance Criteria:**
- [ ] Products with links are enriched immediately
- [ ] Products without links trigger search
- [ ] Partial products saved with available data
- [ ] Enrichment source tracked

---

### Task 3.3: Full List Page Flow End-to-End Test
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2, `05-UNIFIED-ARCHITECTURE.md`
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/e2e/test_list_flow_e2e.py`:
   - `test_full_list_page_discovery_flow`:
     1. Fetch real blog/review article
     2. AI extracts multiple products
     3. Each product enriched (link or search)
     4. All products processed through pipeline
     5. DiscoveredProducts saved to database
     6. Deduplication works correctly

**Acceptance Criteria:**
- [ ] Multiple products extracted and saved
- [ ] Each product has source_url tracking
- [ ] Duplicates detected and merged
- [ ] discovery_source = "ai_list_extraction"

---

## Task Group 4: Single Product Flow Integration Tests

### Task 4.1: SmartRouter Multi-Tier Fetching
**Priority:** HIGH
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2.3 (lines 833-897)
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_smart_router.py`:
   - `test_tier1_httpx_fetches_simple_pages`
   - `test_tier2_playwright_handles_js_rendered_pages`
   - `test_tier3_scrapingbee_handles_blocked_sites`
   - `test_escalates_on_age_gate_detection`
   - `test_marks_domain_requires_tier3_on_success`
2. Use real URLs that require different tiers

**Acceptance Criteria:**
- [ ] Tier 1 works for simple static pages
- [ ] Tier 2 renders JavaScript content
- [ ] Age gate detection triggers escalation
- [ ] Domain `requires_tier3` flag persisted

---

### Task 4.2: ContentProcessor with VPS AI Service
**Priority:** CRITICAL (Partially done, needs expansion)
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2.3
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Expand `tests/test_real_ai_integration.py`:
   - `test_extracts_full_tasting_profile` (nose, palate, finish)
   - `test_extracts_whiskey_details` (distillery, peat_level, cask_type)
   - `test_extracts_port_wine_details` (style, vintage, producer_house)
   - `test_extracts_awards_from_product_page`
   - `test_extracts_ratings_from_product_page`
   - `test_extracts_images_from_product_page`
   - `test_handles_sparse_content_pages`
   - `test_handles_multi_product_pages`
2. All tests MUST use VPS AI Service
3. Use real product page URLs (thewhiskyexchange.com, masterofmalt.com)

**Acceptance Criteria:**
- [ ] Full tasting profile extracted when available
- [ ] Product-type-specific details extracted
- [ ] Multi-product response handling works
- [ ] Sparse content pages use title/h1 fallback

---

### Task 4.3: Full Single Product Flow End-to-End Test
**Priority:** CRITICAL
**Spec Reference:** `02-04-FLOW-ANALYSIS-PROBLEMS.md` Section 2.3, `05-UNIFIED-ARCHITECTURE.md`
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/e2e/test_single_product_flow_e2e.py`:
   - `test_full_whiskey_product_extraction`:
     1. Real whiskey product URL
     2. SmartRouter fetches content
     3. trafilatura cleans HTML
     4. VPS AI extracts all fields
     5. ProductCandidate created
     6. Pipeline processes candidate
     7. DiscoveredProduct + WhiskeyDetails saved
     8. Completeness calculated
     9. Status determined
   - `test_full_port_wine_product_extraction`:
     1. Same flow for port wine
     2. PortWineDetails created
     3. Port-specific fields extracted

**Acceptance Criteria:**
- [ ] Full flow completes end-to-end
- [ ] All data in individual columns (not JSON blobs)
- [ ] WhiskeyDetails/PortWineDetails correctly populated
- [ ] Provenance tracked (ProductFieldSource)

---

## Task Group 5: Completeness Scoring & Status Model

### Task 5.1: Completeness Score Calculation Integration Test
**Priority:** CRITICAL
**Spec Reference:** `05-UNIFIED-ARCHITECTURE.md` Section 5.3 (lines 112-179)
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_completeness_scoring.py`:
   - `test_tasting_profile_worth_40_points`:
     - Palate (20 pts): palate_flavors (10) + palate_description (5) + mid_palate (3) + mouthfeel (2)
     - Nose (10 pts): nose_description (5) + primary_aromas (5)
     - Finish (10 pts): finish_description (5) + finish_flavors (3) + finish_length (2)
   - `test_identification_worth_15_points`:
     - name (10) + brand (5)
   - `test_basic_info_worth_15_points`:
     - product_type (5) + abv (5) + description (5)
   - `test_enrichment_worth_20_points`:
     - best_price (5) + images (5) + ratings (5) + awards (5)
   - `test_verification_worth_10_points`:
     - source_count >= 2 (5) + source_count >= 3 (5)
   - `test_total_is_exactly_100_points`
2. Use real products extracted via VPS AI service

**Acceptance Criteria:**
- [ ] Tasting profile = 40% of score
- [ ] Scores calculated correctly for real products
- [ ] Score matches spec exactly

---

### Task 5.2: Status Determination Integration Test
**Priority:** CRITICAL
**Spec Reference:** `05-UNIFIED-ARCHITECTURE.md` Section 5.3 (lines 181-209)
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_status_determination.py`:
   - `test_incomplete_for_score_0_to_29`
   - `test_partial_for_score_30_to_59`
   - `test_partial_when_score_70_but_no_palate` (CRITICAL)
   - `test_complete_requires_palate_AND_score_60_plus`
   - `test_verified_requires_palate_nose_finish_and_sources`
   - `test_verified_requires_score_80_plus`
2. Use real products with varying completeness

**Acceptance Criteria:**
- [ ] Product with score=70 but no palate stays PARTIAL
- [ ] Product with palate + score=65 becomes COMPLETE
- [ ] Product with full tasting + 2 sources + score=85 becomes VERIFIED
- [ ] Status determination matches spec exactly

---

## Task Group 6: Multi-Source Verification Pipeline

### Task 6.1: Verification Pipeline Search Integration
**Priority:** HIGH
**Spec Reference:** `07-VERIFICATION-PIPELINE.md` Section 7.1
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_verification_search.py`:
   - `test_searches_for_tasting_notes_when_missing`:
     - Query: "{name} tasting notes review"
   - `test_searches_for_pricing_when_missing`:
     - Query: "{name} buy price"
   - `test_limits_searches_to_target_sources` (3)
   - `test_skips_excluded_domains` (social, news)
2. Can use mocked SerpAPI for cost control
3. URL extraction and crawling must use real VPS

**Acceptance Criteria:**
- [ ] Targeted searches based on missing fields
- [ ] Maximum 3 sources searched
- [ ] Excluded domains filtered

---

### Task 6.2: Verification Pipeline Extraction Integration
**Priority:** HIGH
**Spec Reference:** `07-VERIFICATION-PIPELINE.md` Section 7.1
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_verification_extraction.py`:
   - `test_extracts_from_additional_sources`
   - `test_increments_source_count_on_success`
   - `test_handles_extraction_failures_gracefully`
   - `test_passes_product_context_to_ai`
2. Use VPS AI Service for extraction

**Acceptance Criteria:**
- [ ] Extraction from 2nd/3rd sources works
- [ ] source_count incremented correctly
- [ ] Failures don't crash pipeline

---

### Task 6.3: Verification Pipeline Field Matching
**Priority:** HIGH
**Spec Reference:** `07-VERIFICATION-PIPELINE.md` Section 7.1 (lines 76-100)
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_verification_matching.py`:
   - `test_verifies_field_when_2_sources_match`:
     - Same ABV from 2 sources -> field verified
   - `test_adds_missing_field_from_new_source`:
     - Missing palate filled from 2nd source
   - `test_logs_conflict_when_values_differ`:
     - Different ABV values -> conflict logged
   - `test_verified_fields_list_updated`
2. Use real extracted data from VPS

**Acceptance Criteria:**
- [ ] Matching values verify field
- [ ] Missing fields filled
- [ ] Conflicts logged (not overwritten)
- [ ] verified_fields list accurate

---

### Task 6.4: Full Verification Pipeline End-to-End Test
**Priority:** HIGH
**Spec Reference:** `07-VERIFICATION-PIPELINE.md`
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/e2e/test_verification_e2e.py`:
   - `test_product_reaches_verified_status`:
     1. Initial extraction from source 1
     2. Verification pipeline searches for sources
     3. Extract from source 2
     4. Fields verified where values match
     5. source_count = 2
     6. Completeness recalculated
     7. Status = VERIFIED (if criteria met)
   - `test_product_stays_partial_without_palate`:
     1. Even with 3 sources
     2. If no palate data found
     3. Status remains PARTIAL

**Acceptance Criteria:**
- [ ] Product with multi-source verification reaches VERIFIED
- [ ] Product without palate stays PARTIAL regardless of sources
- [ ] verified_fields accurately tracks which fields verified

---

## Task Group 7: Data Model Integrity

### Task 7.1: No JSON Blobs Verification
**Priority:** CRITICAL
**Spec Reference:** `01-CRITICAL-REQUIREMENTS.md` Requirement 3
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_no_json_blobs.py`:
   - `test_name_saved_to_column_not_json`
   - `test_abv_saved_to_column_not_json`
   - `test_tasting_notes_saved_to_columns_not_json`
   - `test_awards_saved_to_product_award_records`
   - `test_deprecated_fields_are_empty`:
     - extracted_data should be {} or removed
     - enriched_data should be {} or removed
     - taste_profile should be {} or removed
2. Use real extraction pipeline

**Acceptance Criteria:**
- [ ] All searchable fields in individual columns
- [ ] JSON fields only for arrays (palate_flavors, primary_aromas)
- [ ] Deprecated JSON blobs empty

---

### Task 7.2: Model Split Verification
**Priority:** HIGH
**Spec Reference:** `01-CRITICAL-REQUIREMENTS.md` Requirement 4
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_model_split.py`:
   - `test_whiskey_creates_whiskey_details`:
     - distillery, peated, peat_level, mash_bill fields
   - `test_port_wine_creates_port_wine_details`:
     - style, quinta, harvest_year, grape_varieties fields
   - `test_common_fields_on_discovered_product`:
     - name, brand, abv, tasting fields on main model
2. Extract real products via VPS

**Acceptance Criteria:**
- [ ] WhiskeyDetails linked to whiskey products
- [ ] PortWineDetails linked to port wine products
- [ ] No whiskey fields on port wine and vice versa

---

## Task Group 8: Cross-Flow Integration

### Task 8.1: All Three Flows Produce Same Output Format
**Priority:** HIGH
**Spec Reference:** `05-UNIFIED-ARCHITECTURE.md` Section 5.2
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_unified_output.py`:
   - `test_award_flow_produces_product_candidate`
   - `test_list_flow_produces_product_candidate`
   - `test_single_flow_produces_product_candidate`
   - `test_all_candidates_have_same_structure`
   - `test_all_flows_use_same_pipeline`:
     - Deduplication
     - Completeness check
     - Smart enrichment
     - Save product

**Acceptance Criteria:**
- [ ] All flows produce ProductCandidate
- [ ] All flows use UnifiedProductPipeline
- [ ] Output format is identical regardless of source

---

### Task 8.2: Deduplication Across Flows
**Priority:** HIGH
**Spec Reference:** `05-UNIFIED-ARCHITECTURE.md` Section 5.2 Step 1
**Assigned Agent:** `implementation-verifier`

**TDD Approach:**
1. Create `tests/integration/test_cross_flow_dedup.py`:
   - `test_same_product_from_award_and_search_merges`:
     1. Extract "Ardbeg 10" from IWSC
     2. Extract "Ardbeg 10" from search
     3. Only one DiscoveredProduct exists
     4. Both sources tracked
   - `test_fingerprint_matching_works_across_flows`
   - `test_name_matching_works_across_flows`

**Acceptance Criteria:**
- [ ] Same product from different flows = one record
- [ ] discovery_sources tracks all sources
- [ ] Awards from both sources merged

---

## Execution Order

### Phase 1: Missing Collectors (Tasks 1.1-1.3)
**Estimated:** 3 task executions
**Blocker for:** Task Groups 2, 3
**Progress:** 1/3 complete (Task 1.1 DONE)

### Phase 2: Award Flow Integration (Tasks 2.1-2.3)
**Estimated:** 3 task executions
**Depends on:** Phase 1 complete

### Phase 3: Single Product Flow (Tasks 4.1-4.3)
**Estimated:** 3 task executions
**Can run parallel to:** Phase 2

### Phase 4: List Page Flow (Tasks 3.1-3.3)
**Estimated:** 3 task executions
**Depends on:** Phase 3 complete

### Phase 5: Completeness & Status (Tasks 5.1-5.2)
**Estimated:** 2 task executions
**Depends on:** Phases 2-4 complete

### Phase 6: Verification Pipeline (Tasks 6.1-6.4)
**Estimated:** 4 task executions
**Depends on:** Phase 5 complete

### Phase 7: Data Integrity (Tasks 7.1-7.2)
**Estimated:** 2 task executions
**Can run parallel to:** Phase 6

### Phase 8: Cross-Flow Integration (Tasks 8.1-8.2)
**Estimated:** 2 task executions
**Depends on:** All previous phases

---

## Total Tasks: 22
## Completed: 1 (Task 1.1)
## Remaining: 21

---

## VPS Configuration Requirements

All integration and E2E tests MUST use:
- **AI Service URL:** `https://api.spiritswise.tech/api/v1/enhance/from-crawler/`
- **Authentication:** Bearer token from `AI_ENHANCEMENT_SERVICE_TOKEN`
- **Environment Variable:** `RUN_VPS_TESTS=true`

---

## Test Naming Convention

```
tests/
├── integration/
│   ├── test_iwsc_flow.py
│   ├── test_award_ai_extraction.py
│   ├── test_list_extraction.py
│   ├── test_list_enrichment.py
│   ├── test_smart_router.py
│   ├── test_completeness_scoring.py
│   ├── test_status_determination.py
│   ├── test_verification_search.py
│   ├── test_verification_extraction.py
│   ├── test_verification_matching.py
│   ├── test_no_json_blobs.py
│   ├── test_model_split.py
│   ├── test_unified_output.py
│   └── test_cross_flow_dedup.py
├── e2e/
│   ├── test_award_flow_e2e.py
│   ├── test_list_flow_e2e.py
│   ├── test_single_product_flow_e2e.py
│   └── test_verification_e2e.py
└── collectors/
    ├── test_dwwa_collector.py  <-- COMPLETE (24 tests)
    ├── test_sfwsc_collector.py
    └── test_wwa_collector.py
```

---

## Success Criteria

All tasks complete when:
1. [x] Task 1.1 - DWWACollector complete (24/24 tests passed)
2. [ ] All 22 tasks have passing tests
3. [ ] All tests use VPS AI Service (not mocks)
4. [ ] All tests use real URLs
5. [ ] Total test count: ~100+ new integration/E2E tests
6. [ ] All three flows verified working end-to-end
7. [ ] Completeness scoring matches spec exactly
8. [ ] Status model enforces palate requirement
9. [ ] Multi-source verification reaches VERIFIED status

---

*Document created: 2026-01-06*
*Last updated: 2026-01-06 (Task 1.1 complete)*
*Based on gap analysis of FLOW_COMPARISON_ANALYSIS.md spec*
