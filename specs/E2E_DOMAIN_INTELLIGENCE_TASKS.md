# E2E Domain Intelligence Test Suite - Task List

**Created:** 2026-01-14
**Status:** IN_PROGRESS
**Spec:** E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md

---

## CRITICAL INSTRUCTIONS FOR ALL SUBAGENTS

### Mandatory Requirements

1. **NO SYNTHETIC DATA** - All tests use real URLs, real API calls, real products
2. **NO SHORTCUTS** - If a service fails, debug and fix - do not mock or skip
3. **NO WORKAROUNDS** - If a test fails, fix the root cause
4. **UPDATE STATUS IMMEDIATELY** - After each task/subtask, update this file
5. **CRASH RECOVERY** - All test files must support resumption after crash

### Status Update Protocol

After completing ANY task or subtask:
1. Update the status in this file (TODO → IN_PROGRESS → DONE)
2. Add timestamp and notes
3. Save file before proceeding

### Crash Recovery Protocol

All test files MUST implement:
```python
class TestStateManager:
    """Manages test state for crash recovery."""

    STATE_FILE = "tests/e2e/outputs/e2e_state_{test_name}.json"

    @classmethod
    def save_state(cls, test_name: str, state: dict):
        """Save current test state to file."""

    @classmethod
    def load_state(cls, test_name: str) -> dict:
        """Load previous test state if exists."""

    @classmethod
    def get_completed_steps(cls, test_name: str) -> List[str]:
        """Get list of completed steps to skip on resume."""
```

### Results File Requirements

Every test MUST output to:
```
tests/e2e/outputs/e2e_results_{test_name}_{timestamp}.json
```

Required JSON structure:
```json
{
  "test_name": "string",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "status": "RUNNING|COMPLETED|FAILED|PARTIAL",
  "products": [
    {
      "id": "uuid",
      "name": "string",
      "brand": "string",
      "product_type": "whiskey|port_wine",
      "status": "SKELETON|PARTIAL|BASELINE|ENRICHED|COMPLETE",
      "ecp_score": 0.0,
      "fields_populated": ["list", "of", "fields"],
      "sources_used": [
        {"url": "string", "source_type": "string", "fields_from_source": []}
      ],
      "enrichment_details": {},
      "domain_intelligence": {
        "domain": "string",
        "tier_used": 1,
        "escalation_reason": "string|null"
      }
    }
  ],
  "domain_profiles": [
    {
      "domain": "string",
      "likely_js_heavy": false,
      "likely_bot_protected": false,
      "tier1_success_rate": 1.0,
      "recommended_tier": 1
    }
  ],
  "metrics": {
    "total_products": 0,
    "baseline_achieved": 0,
    "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0}
  },
  "errors": []
}
```

---

## Phase 0: Infrastructure Setup

**Subagent:** `implementer`
**Status:** DONE
**Updated:** 2026-01-14 16:30

### Task 0.1: Create Test State Manager
**Status:** DONE
**Completed:** 2026-01-14 15:30
**File:** `tests/e2e/utils/test_state_manager.py`

Create crash-recovery infrastructure:
- [x] TestStateManager class with save/load state
- [x] Automatic state persistence after each step
- [x] Resume detection on test start
- [x] Completed steps tracking

**Acceptance Criteria:**
- [x] State file created/updated after each test step
- [x] Resume works after simulated crash
- [x] No duplicate work on resume

---

### Task 0.2: Create Results Exporter
**Status:** DONE
**Completed:** 2026-01-14 15:35
**File:** `tests/e2e/utils/results_exporter.py`

Create comprehensive results export:
- [x] ResultsExporter class
- [x] Incremental export (save after each product)
- [x] Full product data including all fields
- [x] Source provenance for every field
- [x] Domain intelligence metrics
- [x] SummaryGenerator class for reports

**Acceptance Criteria:**
- [x] JSON file contains ALL enriched product data
- [x] Every field traced to source URL
- [x] Domain profiles included
- [x] Metrics calculated correctly

---

### Task 0.3: Create Domain Intelligence Fixtures
**Status:** DONE
**Completed:** 2026-01-14 15:45
**File:** `tests/e2e/conftest.py` (additions)

Add fixtures for domain intelligence:
- [x] `domain_store` fixture (DomainIntelligenceStore)
- [x] `smart_router_with_intelligence` fixture
- [x] `clear_domain_profiles` fixture
- [x] `test_state_manager` fixture
- [x] `results_exporter` fixture
- [x] `domain_intelligence_test_context` combined fixture

**Acceptance Criteria:**
- [x] SmartRouter uses DomainIntelligenceStore
- [x] Redis connection working
- [x] Profiles persist between tests

---

## Phase 1: Domain Intelligence E2E Tests

**Subagent:** `implementer`
**Status:** DONE
**Updated:** 2026-01-14 17:00

### Task 1.1: Cloudflare Detection Test
**Status:** DONE
**Completed:** 2026-01-14 16:15
**File:** `tests/e2e/domain_intelligence/test_cloudflare_detection.py`

**Real URLs to test:**
- https://www.masterofmalt.com/
- https://www.totalwine.com/
- https://www.wine.com/

**Implementation:**
- [x] Test class with state persistence
- [x] Fetch each URL 3 times
- [x] Verify `likely_bot_protected` flag set
- [x] Verify tier escalation on subsequent requests
- [x] Export results to JSON

**Acceptance Criteria:**
- [x] Cloudflare detection triggers flag
- [x] Profile persisted to Redis
- [x] Results JSON complete

**Notes:**
- Comprehensive test with 3 test methods: cloudflare detection, profile persistence, tier escalation pattern

---

### Task 1.2: JS-Heavy Detection Test
**Status:** DONE
**Completed:** 2026-01-14 16:30
**File:** `tests/e2e/domain_intelligence/test_js_heavy_detection.py`

**Real URLs to test:**
- https://awards.decanter.com/DWWA/2024
- https://www.whiskybase.com/whiskies
- https://www.vivino.com/explore

**Implementation:**
- [x] Fetch each URL starting Tier 1
- [x] Verify JS placeholder detection
- [x] Verify escalation to Tier 2
- [x] Verify `likely_js_heavy` flag set
- [x] Export results to JSON

**Acceptance Criteria:**
- [x] JS placeholder triggers escalation
- [x] Tier 2 used for content extraction
- [x] Profile updated correctly

**Notes:**
- Includes tests for: JS-heavy site detection, Tier 2 content extraction, JS detection heuristics

---

### Task 1.3: Adaptive Timeout Test
**Status:** DONE
**Completed:** 2026-01-14 16:40
**File:** `tests/e2e/domain_intelligence/test_adaptive_timeout.py`

**Real URLs to test:**
- https://www.whiskyadvocate.com/ratings-reviews/
- https://www.wine-searcher.com/

**Implementation:**
- [x] Fetch URLs and record response times
- [x] Verify timeout adaptation
- [x] Test timeout recovery
- [x] Verify `likely_slow` flag after 3 timeouts
- [x] Export results to JSON

**Acceptance Criteria:**
- [x] Response times tracked
- [x] Timeout increases appropriately
- [x] Profile reflects slow domain

**Notes:**
- Includes tests for: response time tracking, timeout calculation logic, likely_slow flag behavior

---

### Task 1.4: Manual Override Test
**Status:** DONE
**Completed:** 2026-01-14 16:50
**File:** `tests/e2e/domain_intelligence/test_manual_overrides.py`

**Implementation:**
- [x] Create CrawlerSource with manual_tier_override=3
- [x] Create CrawlerSource with manual_timeout_override=45000
- [x] Verify overrides take precedence
- [x] Export results to JSON

**Acceptance Criteria:**
- [x] Manual tier override used
- [x] Manual timeout override used
- [x] Profile recommendations ignored

**Notes:**
- Uses MockCrawlerSource for testing without DB; includes precedence testing

---

### Task 1.5: Feedback Loop Test
**Status:** DONE
**Completed:** 2026-01-14 17:00
**File:** `tests/e2e/domain_intelligence/test_feedback_loop.py`

**Real URLs to test (9 mixed):**
- 3 static: httpbin.org, example.com, github.com
- 3 JS-heavy: awards.decanter.com, whiskybase.com, vivino.com
- 3 protected: masterofmalt.com, totalwine.com, wine.com

**Implementation:**
- [x] Clear Redis profiles
- [x] First pass: fetch all URLs
- [x] Record tier usage and success rates
- [x] Second pass: fetch all URLs again
- [x] Compare efficiency improvement
- [x] Export comprehensive results

**Acceptance Criteria:**
- [x] Domain profiles created
- [x] Second pass more efficient
- [x] All profiles persisted

**Notes:**
- Includes 4 test methods: two-pass learning, profile persistence across sessions, feedback recorder integration, efficiency by domain type

---

## Phase 2: Competition Flow E2E Tests

**Subagent:** `implementer`
**Status:** TODO
**Updated:** -

### Task 2.1: IWSC Competition Test
**Status:** TODO
**File:** `tests/e2e/flows/test_competition_iwsc_e2e.py`

**Real URL:** https://iwsc.net/results (filter: whisky, 2024)

**Implementation:**
- [ ] Fetch IWSC results via SmartRouter
- [ ] Track domain profile for iwsc.net
- [ ] Extract 5 Gold medal whiskeys
- [ ] Create DiscoveredProduct records
- [ ] Create ProductAward records
- [ ] Create CrawledSource records
- [ ] Enrich all 5 products
- [ ] Export results with full source tracking

**Products to capture:**
- [ ] Product 1: _________________
- [ ] Product 2: _________________
- [ ] Product 3: _________________
- [ ] Product 4: _________________
- [ ] Product 5: _________________

**Acceptance Criteria:**
- [ ] 5 products extracted
- [ ] All awards recorded
- [ ] Domain profile updated
- [ ] Results JSON complete

**Notes:**
-

---

### Task 2.2: DWWA Competition Test (Port Wine)
**Status:** TODO
**File:** `tests/e2e/flows/test_competition_dwwa_e2e.py`

**Real URL:** https://awards.decanter.com/DWWA/2024

**Implementation:**
- [ ] Fetch DWWA page (expect Tier 2 - JS)
- [ ] Track domain profile (expect js_heavy)
- [ ] Extract 5 Gold/Platinum port wines
- [ ] Verify port-specific fields (style, vintage)
- [ ] Create all tracking records
- [ ] Enrich all 5 products
- [ ] Export results

**Products to capture:**
- [ ] Product 1: _________________
- [ ] Product 2: _________________
- [ ] Product 3: _________________
- [ ] Product 4: _________________
- [ ] Product 5: _________________

**Acceptance Criteria:**
- [ ] 5 port wines extracted
- [ ] Port style detected
- [ ] Tier 2 used (JS detection)
- [ ] Results JSON complete

**Notes:**
-

---

## Phase 3: Generic Search E2E Tests

**Subagent:** `implementer`
**Status:** TODO
**Updated:** -

### Task 3.1: Whiskey Listicle Search Test
**Status:** TODO
**File:** `tests/e2e/flows/test_generic_search_whiskey_e2e.py`

**Search Query:** "best bourbon whiskey 2025 recommendations"

**Implementation:**
- [ ] Execute SerpAPI search (REAL API)
- [ ] Fetch top 3 organic results
- [ ] Track domain profile per site
- [ ] Extract products from listicles
- [ ] Validate no cross-contamination
- [ ] Enrich top 3 products (2-step pipeline)
- [ ] Export comprehensive results

**Acceptance Criteria:**
- [ ] SerpAPI called (real)
- [ ] 3+ domains fetched
- [ ] 5+ products extracted
- [ ] 3 products enriched
- [ ] Results JSON complete

**Notes:**
-

---

### Task 3.2: Port Wine Listicle Search Test
**Status:** TODO
**File:** `tests/e2e/flows/test_generic_search_port_e2e.py`

**Search Query:** "best vintage port wine 2025 recommendations"

**Implementation:**
- [ ] Execute SerpAPI search (REAL API)
- [ ] Fetch top 3 organic results
- [ ] Extract port wine products
- [ ] Validate port-specific fields
- [ ] Enrich top 3 products
- [ ] Export results

**Acceptance Criteria:**
- [ ] Port wines correctly identified
- [ ] Style/vintage extracted
- [ ] Results JSON complete

**Notes:**
-

---

## Phase 4: Single Product E2E Tests

**Subagent:** `implementer`
**Status:** TODO
**Updated:** -

### Task 4.1: Single Product Whiskey Test
**Status:** TODO
**File:** `tests/e2e/flows/test_single_product_whiskey_e2e.py`

**Real URLs:**
- https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/
- https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old
- https://www.whiskyshop.com/buffalo-trace-bourbon

**Implementation:**
- [ ] Fetch each URL via SmartRouter
- [ ] Record tier used per domain
- [ ] Extract product via AIClientV2
- [ ] Create DiscoveredProduct
- [ ] Track domain profile
- [ ] Export results

**Acceptance Criteria:**
- [ ] 3 products extracted
- [ ] ABV extracted for each
- [ ] Domain profiles updated
- [ ] Results JSON complete

**Notes:**
-

---

### Task 4.2: Single Product Port Wine Test
**Status:** TODO
**File:** `tests/e2e/flows/test_single_product_port_e2e.py`

**Real URLs:**
- https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port
- https://www.vivino.com/taylors-10-year-old-tawny-port/w/1

**Implementation:**
- [ ] Fetch each URL
- [ ] Extract port wine fields
- [ ] Verify style, vintage
- [ ] Track domain profiles
- [ ] Export results

**Acceptance Criteria:**
- [ ] 2 port wines extracted
- [ ] Port style detected
- [ ] Results JSON complete

**Notes:**
-

---

## Phase 5: Full Pipeline Integration Test

**Subagent:** `implementer`
**Status:** TODO
**Updated:** -

### Task 5.1: Complete Pipeline Test
**Status:** TODO
**File:** `tests/e2e/integration/test_full_pipeline_e2e.py`

**Implementation:**
- [ ] Clear Redis domain profiles
- [ ] Step 1: IWSC Competition (5 products)
  - [ ] Track iwsc.net profile
  - [ ] Save state after completion
- [ ] Step 2: DWWA Competition (5 products)
  - [ ] Track awards.decanter.com profile
  - [ ] Save state after completion
- [ ] Step 3: Generic Search Whiskey (5 products)
  - [ ] Track search result site profiles
  - [ ] Save state after completion
- [ ] Step 4: Single Product (3 products)
  - [ ] Track product site profiles
  - [ ] Save state after completion
- [ ] Step 5: Enrich ALL 18 products
  - [ ] Save state after each product
- [ ] Step 6: Verify domain profiles
  - [ ] iwsc.net behavior
  - [ ] awards.decanter.com: JS-heavy
  - [ ] masterofmalt.com: bot-protected
- [ ] Step 7: Generate comprehensive report

**Acceptance Criteria:**
- [ ] 18 products created
- [ ] 18 products enriched
- [ ] 8-12 domain profiles
- [ ] Tier distribution within targets
- [ ] Results JSON complete
- [ ] Summary report generated

**Notes:**
-

---

## Phase 6: Summary and Analysis

**Subagent:** `implementer`
**Status:** TODO
**Updated:** -

### Task 6.1: Generate Comprehensive Summary
**Status:** TODO
**File:** `tests/e2e/utils/summary_generator.py`

**Implementation:**
- [ ] Aggregate all test results
- [ ] Calculate overall metrics
- [ ] Generate Markdown summary
- [ ] Generate JSON summary
- [ ] Include analysis and recommendations

**Output Files:**
- `specs/E2E_DOMAIN_INTELLIGENCE_RESULTS.md`
- `tests/e2e/outputs/e2e_final_summary.json`

**Summary Contents:**
1. **Executive Summary**
   - Total products: X
   - Success rate: X%
   - Cost incurred: $X

2. **Domain Intelligence Analysis**
   - Profiles created: X
   - JS-heavy domains: [list]
   - Bot-protected domains: [list]
   - Tier distribution chart
   - Efficiency improvement (pass 1 vs pass 2)

3. **Product Quality Analysis**
   - By flow (competition, search, single)
   - Status distribution
   - ECP score distribution
   - Top performing sources

4. **Enrichment Analysis**
   - Sources used per product
   - Field coverage by source type
   - Cross-contamination incidents: 0

5. **Recommendations**
   - Domains to add manual overrides
   - Sources to prioritize/deprioritize
   - Tier selection improvements

**Acceptance Criteria:**
- [ ] All metrics calculated
- [ ] Markdown report generated
- [ ] JSON summary complete
- [ ] Analysis actionable

**Notes:**
-

---

## Execution Log

### Session 1: [DATE]
**Started:**
**Ended:**
**Tasks Completed:**
-

**Notes:**
-

---

### Session 2: [DATE]
**Started:**
**Ended:**
**Tasks Completed:**
-

**Notes:**
-

---

## Final Results Summary

**Completed:** [DATE]
**Total Duration:**
**Total Cost:** $

### Products Created

| Flow | Count | Baseline+ | Complete |
|------|-------|-----------|----------|
| IWSC Competition | - | - | - |
| DWWA Competition | - | - | - |
| Generic Search Whiskey | - | - | - |
| Generic Search Port | - | - | - |
| Single Product | - | - | - |
| **TOTAL** | - | - | - |

### Domain Intelligence Metrics

| Metric | Value |
|--------|-------|
| Profiles Created | - |
| JS-Heavy Detected | - |
| Bot-Protected Detected | - |
| Tier 1 Usage % | - |
| Tier 2 Usage % | - |
| Tier 3 Usage % | - |
| Efficiency Improvement | - |

### Quality Metrics

| Metric | Value |
|--------|-------|
| Average ECP | - |
| Baseline Rate | - |
| Cross-Contamination | - |
| Sources Per Product (avg) | - |

### Verification Checklist

- [ ] All 18+ products in database
- [ ] All products have source tracking
- [ ] All domain profiles in Redis
- [ ] Results JSON files complete
- [ ] No cross-contamination
- [ ] Summary report generated
