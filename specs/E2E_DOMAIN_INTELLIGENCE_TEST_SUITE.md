# E2E Test Suite: Domain Intelligence & Enrichment Flows

**Created:** 2026-01-14
**Status:** SPECIFICATION
**Purpose:** Comprehensive E2E testing for domain intelligence + all enrichment flows

---

## Overview

This specification defines a complete E2E test suite that validates:

1. **Domain Intelligence System** (newly implemented)
   - SmartRouter with adaptive tier selection
   - Heuristic escalation triggers
   - Feedback recording and learning
   - Adaptive timeouts

2. **Three Enrichment Flows**
   - Competition Discovery (IWSC, DWWA)
   - Generic Search Discovery (listicles)
   - Single Product Extraction

### Key Principles (per E2E_TEST_SPECIFICATION_V2.md)

1. **NO synthetic content** - All tests use real URLs from real sources
2. **NO mocking of external services** - Real API calls to OpenAI, SerpAPI, ScrapingBee
3. **NO data deletion** - All created products remain for verification
4. **NO shortcuts or workarounds** - Fix root causes, don't circumvent
5. **Full source tracking** - Every field traced to its source

---

## Part 1: Domain Intelligence E2E Tests

### Purpose

Validate that the new domain intelligence system correctly:
- Learns from fetch results (success/failure)
- Adapts tier selection based on domain profiles
- Applies heuristic escalation for soft failures
- Records feedback for continuous improvement

### Test 1.1: Domain Profile Learning (Cloudflare Sites)

**Objective:** Verify domain profile learning from Cloudflare-protected sites

**Real Test URLs:**
```python
CLOUDFLARE_PROTECTED_URLS = [
    "https://www.masterofmalt.com/",  # Known Cloudflare
    "https://www.totalwine.com/",     # Heavy protection
    "https://www.wine.com/",          # Rate limited
]
```

**Test Steps:**
1. Initialize SmartRouter with DomainIntelligenceStore (Redis)
2. Fetch each URL sequentially (3 requests each)
3. Verify domain profiles are updated:
   - `likely_bot_protected` flag set after Cloudflare detection
   - `tier3_success_rate` increases on Tier 3 success
   - `tier1_success_rate` decreases on Tier 1 failure
4. On 4th request, verify SmartTierSelector recommends higher tier
5. Verify FeedbackRecorder updated success rates

**Expected Results:**
```python
# After 3 fetches of Cloudflare site:
assert profile.likely_bot_protected == True
assert profile.tier1_success_rate < 0.5
assert profile.recommended_tier >= 2
```

**Acceptance Criteria:**
- [ ] Domain profiles persisted to Redis
- [ ] Cloudflare detection triggered `likely_bot_protected` flag
- [ ] Subsequent requests start at higher tier
- [ ] No hardcoded behavior - all learned

---

### Test 1.2: JavaScript-Heavy Site Detection

**Objective:** Verify JS-heavy site detection and Tier 2 escalation

**Real Test URLs:**
```python
JS_HEAVY_URLS = [
    "https://awards.decanter.com/DWWA/2024",  # JS-rendered content
    "https://www.whiskybase.com/whiskies",    # SPA-style
    "https://www.vivino.com/explore",          # React/Vue app
]
```

**Test Steps:**
1. Fetch each URL starting at Tier 1
2. Verify EscalationHeuristics detects JS placeholder content
3. Verify automatic escalation to Tier 2 (Playwright)
4. Verify FeedbackRecorder sets `likely_js_heavy` flag
5. On subsequent request, verify starts at Tier 2

**Expected Results:**
```python
# After JS detection:
assert profile.likely_js_heavy == True
assert "js" in escalation_result.reason.lower()
assert fetch_result.tier_used >= 2
```

**Acceptance Criteria:**
- [ ] JS placeholder content triggers escalation
- [ ] Profile updated with `likely_js_heavy=True`
- [ ] Subsequent fetches skip Tier 1

---

### Test 1.3: Adaptive Timeout Learning

**Objective:** Verify timeout adaptation for slow domains

**Real Test URLs:**
```python
SLOW_DOMAIN_URLS = [
    "https://www.whiskyadvocate.com/ratings-reviews/",  # Heavy pages
    "https://www.wine-searcher.com/",                   # Complex rendering
]
```

**Test Steps:**
1. Fetch each URL and record response times
2. Verify AdaptiveTimeout increases for slow responses
3. Simulate timeout (use very short timeout)
4. Verify profile updates `timeout_count` and `likely_slow`
5. Verify next request uses longer timeout

**Expected Results:**
```python
# After timeout:
assert profile.timeout_count >= 1
assert profile.recommended_timeout_ms > 20000  # > base timeout
# After 3 timeouts:
assert profile.likely_slow == True
```

**Acceptance Criteria:**
- [ ] Response times tracked in profile
- [ ] Timeout count incremented
- [ ] `likely_slow` flag set after 3 timeouts
- [ ] Progressive timeout increase (20s → 40s → 60s)

---

### Test 1.4: Manual Override Respect

**Objective:** Verify manual overrides take precedence

**Setup:**
```python
# Create source with manual override
source = CrawlerSource(
    name="Test Source",
    base_url="https://example.com",
    manual_tier_override=3,
    manual_timeout_override=45000,
)
```

**Test Steps:**
1. Create domain profile with learned tier=1
2. Create CrawlerSource with `manual_tier_override=3`
3. Fetch URL with source
4. Verify Tier 3 used despite profile suggesting Tier 1
5. Verify timeout uses manual override

**Expected Results:**
```python
assert fetch_result.tier_used == 3  # Manual override wins
assert timeout_used == 45000  # Manual override
```

**Acceptance Criteria:**
- [ ] Manual tier override takes precedence
- [ ] Manual timeout override takes precedence
- [ ] Profile recommendations ignored when override set

---

### Test 1.5: Feedback Loop Integration (Full Cycle)

**Objective:** Full cycle test of feedback loop

**Test Steps:**
1. Clear Redis (start fresh)
2. Fetch 10 URLs from mixed domains:
   - 3 static sites (should stay Tier 1)
   - 4 JS-heavy sites (should learn Tier 2)
   - 3 protected sites (should learn Tier 3)
3. Verify all profiles updated correctly
4. Re-fetch same 10 URLs
5. Verify improved tier selection on 2nd pass

**Expected Results:**
```python
# First pass: trial and error
first_pass_tier3_count = count(tier_used == 3)

# Second pass: learned behavior
second_pass_tier3_count = count(tier_used == 3)

# Should be same or fewer Tier 3 calls (learned lower tiers)
# Or same count if sites truly need Tier 3
assert second_pass_success_rate >= first_pass_success_rate
```

**Acceptance Criteria:**
- [ ] 10 domain profiles created
- [ ] Behavior flags set appropriately
- [ ] Second pass more efficient (fewer escalations)
- [ ] All profiles persisted to Redis

---

## Part 2: Competition Flow E2E Tests

### Test 2.1: IWSC Competition Discovery

**Objective:** Extract whiskey products from IWSC 2025

**Real Competition URL:**
```python
IWSC_2025_URL = "https://iwsc.net/results"
# Filter: 2024 results, Whisky category, Gold medals
```

**Test Steps:**
1. Fetch IWSC results page via SmartRouter
2. Verify domain intelligence applied (may need Tier 2/3)
3. Extract 5 Gold medal whiskey winners
4. For each product:
   - Create DiscoveredProduct
   - Create ProductAward (medal, year, competition)
   - Create CrawledSource with raw_content
   - Link ProductSource
5. Verify all domain profile feedback recorded

**Products to Capture (examples):**
- Kavalan (Taiwan)
- Arran (Scotland)
- GlenAllachie (Scotland)
- Ardbeg (Scotland)
- Laphroaig (Scotland)

**Expected Outputs:**
- 5 DiscoveredProduct records
- 5 ProductAward records (IWSC 2024/2025)
- 5 CrawledSource records
- Domain profile for iwsc.net updated

**Acceptance Criteria:**
- [ ] All 5 products extracted with name + brand
- [ ] Award records have correct metadata
- [ ] Source tracking complete
- [ ] Domain intelligence profile updated

---

### Test 2.2: DWWA Competition Discovery (Port Wine)

**Objective:** Extract port wines from DWWA 2024

**Real Competition URL:**
```python
DWWA_2024_URL = "https://awards.decanter.com/DWWA/2024"
# Known to require JS rendering (Tier 2)
```

**Test Steps:**
1. Fetch DWWA page (expect Tier 2 due to JS)
2. Verify EscalationHeuristics triggered for JS
3. Extract 5 Gold/Platinum port wines
4. Verify port-specific fields (style, vintage)
5. Verify domain profile marks awards.decanter.com as JS-heavy

**Products to Capture:**
- Taylor's (various Tawny/Vintage)
- Graham's (Port)
- Cockburn's (Port)
- Fonseca (Port)
- Sandeman (Port)

**Expected Outputs:**
- 5 DiscoveredProduct records (port_wine type)
- Port-specific fields: style, vintage, sweetness
- Domain profile: `likely_js_heavy=True`

**Acceptance Criteria:**
- [ ] Products have `product_type=port_wine`
- [ ] Port style detected (tawny, ruby, vintage)
- [ ] Domain profile updated for JS-heavy
- [ ] Tier 2 (Playwright) used for extraction

---

## Part 3: Generic Search Discovery E2E Tests

### Test 3.1: Whiskey Listicle Discovery

**Objective:** Discover products from listicle search results

**Search Query:**
```python
SEARCH_QUERY = "best bourbon whiskey 2025 recommendations"
```

**Test Steps:**
1. Execute SerpAPI search (real API call)
2. Fetch top 3 organic results via SmartRouter
3. Track domain profiles for each site
4. Extract products from listicle pages
5. Verify product validation (no cross-contamination)
6. Enrich top 3 products via 2-step pipeline:
   - Step 1: Producer page search
   - Step 2: Review site search

**Expected Sources:**
- Forbes, VinePair, Whiskey Advocate
- Multiple domains → multiple domain profiles

**Expected Outputs:**
- 5+ products extracted from listicles
- Domain profiles for 3+ domains
- 3 products enriched
- ECP scores calculated

**Acceptance Criteria:**
- [ ] SerpAPI search executed (real)
- [ ] Multiple domains fetched
- [ ] Domain intelligence applied per domain
- [ ] Products extracted and validated
- [ ] >= 30% reach BASELINE status

---

### Test 3.2: Port Wine Listicle Discovery

**Objective:** Discover port wines from search results

**Search Query:**
```python
SEARCH_QUERY = "best vintage port wine 2025 recommendations"
```

**Test Steps:**
1. Execute SerpAPI search
2. Fetch top 3 results
3. Extract port wine products
4. Validate port-specific fields
5. Enrich via 2-step pipeline

**Expected Outputs:**
- 3-5 port wine products
- Port-specific fields populated
- Domain profiles for wine sites

**Acceptance Criteria:**
- [ ] Port wines correctly identified
- [ ] Style/vintage extracted
- [ ] Domain profiles updated

---

## Part 4: Single Product Extraction E2E Tests

### Test 4.1: Direct Product Page - Whiskey

**Objective:** Extract single product from direct URL

**Real Test URLs:**
```python
SINGLE_PRODUCT_URLS_WHISKEY = [
    "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
    "https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old",
    "https://www.whiskyshop.com/buffalo-trace-bourbon",
]
```

**Test Steps:**
1. For each URL:
   - Fetch via SmartRouter (record tier used)
   - Extract product via AIClientV2
   - Create DiscoveredProduct
   - Track domain profile
2. Verify field extraction quality
3. Verify domain profiles updated

**Expected Results:**
- 3 products with complete whiskey fields
- ABV, brand, name, description populated
- Domain profiles for 3 domains

**Acceptance Criteria:**
- [ ] Products have ABV extracted
- [ ] Products have tasting notes
- [ ] Domain profiles reflect site behavior

---

### Test 4.2: Direct Product Page - Port Wine

**Objective:** Extract port wine from direct URL

**Real Test URLs:**
```python
SINGLE_PRODUCT_URLS_PORT = [
    "https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port",
    "https://www.vivino.com/taylors-10-year-old-tawny-port/w/1",
]
```

**Test Steps:**
1. Fetch each URL (track escalation behavior)
2. Extract port wine fields
3. Verify style, vintage, sweetness
4. Verify domain profile updates

**Acceptance Criteria:**
- [ ] Port wine type detected
- [ ] Style (tawny, ruby) extracted
- [ ] Domain profiles updated

---

## Part 5: Integration Test - Full Pipeline with Domain Intelligence

### Test 5.1: Complete Pipeline Test

**Objective:** Full E2E test exercising all components

**Test Flow:**
```
1. Clear Redis domain profiles (fresh start)
2. Execute Competition Flow (IWSC - 5 products)
   - Track domain profile for iwsc.net
3. Execute Competition Flow (DWWA - 5 products)
   - Track domain profile for awards.decanter.com
4. Execute Generic Search (whiskey - 5 products)
   - Track domain profiles for search result sites
5. Execute Single Product (3 products)
   - Track domain profiles for product sites
6. Verify domain profiles:
   - iwsc.net: Behavior detected
   - awards.decanter.com: JS-heavy flagged
   - masterofmalt.com: Protection level detected
7. Enrich all products (18 total)
8. Generate report with:
   - Product quality metrics
   - Domain intelligence metrics
   - Tier usage distribution
```

**Expected Metrics:**
```python
expected_metrics = {
    "total_products": 18,
    "products_enriched": 18,
    "domain_profiles_created": 8-12,
    "tier_distribution": {
        "tier_1_pct": ">30%",  # Static sites
        "tier_2_pct": "30-50%",  # JS-heavy
        "tier_3_pct": "<30%",  # Protected
    },
    "baseline_achievement_rate": ">=30%",
    "cross_contamination": 0,
}
```

**Acceptance Criteria:**
- [ ] 18 products created
- [ ] 8-12 domain profiles in Redis
- [ ] Tier usage reflects domain characteristics
- [ ] No cross-contamination
- [ ] Report generated with metrics

---

## Test Execution Configuration

### Required Services

| Service | Purpose | Required |
|---------|---------|----------|
| AI Enhancement Service | Product extraction | Yes |
| SerpAPI | Search queries | Yes |
| ScrapingBee | Tier 3 fetching | Yes |
| Redis | Domain profiles | Yes |
| PostgreSQL | Product storage | Yes |

### Environment Variables

```bash
# Required in .env
AI_ENHANCEMENT_SERVICE_URL=<url>
AI_ENHANCEMENT_SERVICE_TOKEN=<token>
SERPAPI_API_KEY=<key>
SCRAPINGBEE_API_KEY=<key>
REDIS_URL=redis://localhost:6379/0
```

### Estimated Costs

| Test Part | SerpAPI | ScrapingBee | AI Calls | Est. Cost |
|-----------|---------|-------------|----------|-----------|
| Part 1 | 0 | 30-40 | 0 | $2-3 |
| Part 2 | 0 | 10-15 | 15-20 | $3-4 |
| Part 3 | 4-6 | 15-20 | 20-30 | $4-6 |
| Part 4 | 0 | 5-10 | 5-10 | $1-2 |
| Part 5 | 4-6 | 40-60 | 50-70 | $8-12 |
| **Total** | 8-12 | 100-145 | 90-130 | **$18-27** |

### Execution Commands

```bash
# Run full suite
pytest tests/e2e/test_domain_intelligence_e2e.py -v --tb=long -s

# Run Part 1 only (Domain Intelligence)
pytest tests/e2e/test_domain_intelligence_e2e.py::TestDomainIntelligenceE2E -v -s

# Run Part 2 only (Competition)
pytest tests/e2e/test_domain_intelligence_e2e.py::TestCompetitionFlowE2E -v -s

# Run Part 3 only (Generic Search)
pytest tests/e2e/test_domain_intelligence_e2e.py::TestGenericSearchE2E -v -s

# Run Part 4 only (Single Product)
pytest tests/e2e/test_domain_intelligence_e2e.py::TestSingleProductE2E -v -s

# Run Part 5 only (Full Pipeline)
pytest tests/e2e/test_domain_intelligence_e2e.py::TestFullPipelineE2E -v -s
```

### Expected Duration

| Part | Duration |
|------|----------|
| Part 1: Domain Intelligence | 15-20 min |
| Part 2: Competition | 10-15 min |
| Part 3: Generic Search | 15-20 min |
| Part 4: Single Product | 5-10 min |
| Part 5: Full Pipeline | 30-45 min |
| **Total** | **1.5-2 hours** |

---

## Output Report Format

### Report Location
```
specs/E2E_DOMAIN_INTELLIGENCE_RESULTS.md
tests/e2e/outputs/domain_intelligence_e2e_YYYY-MM-DD_HHMMSS.json
```

### Report Contents

1. **Domain Intelligence Metrics**
   ```json
   {
     "domain_profiles_created": 12,
     "domains_by_behavior": {
       "static": ["httpbin.org"],
       "js_heavy": ["awards.decanter.com", "vivino.com"],
       "bot_protected": ["masterofmalt.com", "totalwine.com"]
     },
     "tier_usage_distribution": {
       "tier_1": 35,
       "tier_2": 45,
       "tier_3": 20
     },
     "average_response_times_ms": {
       "tier_1": 1200,
       "tier_2": 4500,
       "tier_3": 8000
     },
     "escalation_reasons": {
       "cloudflare_challenge": 8,
       "js_placeholder": 12,
       "http_403": 5
     }
   }
   ```

2. **Product Metrics**
   ```json
   {
     "total_products": 18,
     "by_flow": {
       "competition": 10,
       "generic_search": 5,
       "single_product": 3
     },
     "status_distribution": {
       "skeleton": 2,
       "partial": 5,
       "baseline": 8,
       "enriched": 2,
       "complete": 1
     },
     "ecp_average": 42.5,
     "cross_contamination_count": 0
   }
   ```

3. **Per-Product Details**
   ```json
   {
     "products": [
       {
         "name": "Ardbeg 10 Year Old",
         "brand": "Ardbeg",
         "status": "BASELINE",
         "ecp": 65.5,
         "sources_used": 3,
         "domain_profile_used": "masterofmalt.com",
         "tier_used": 3,
         "fields_populated": ["abv", "description", "nose_description", "palate_flavors"]
       }
     ]
   }
   ```

4. **Verification Results**
   - [ ] All domain profiles created
   - [ ] All products have source tracking
   - [ ] No cross-contamination
   - [ ] Tier distribution within expected range
   - [ ] >= 30% products at BASELINE

---

## Files to Create

### Test File Structure

```
tests/e2e/
├── test_domain_intelligence_e2e.py     # Main orchestrator
├── domain_intelligence/
│   ├── __init__.py
│   ├── test_cloudflare_detection.py    # Part 1.1
│   ├── test_js_heavy_detection.py      # Part 1.2
│   ├── test_adaptive_timeout.py        # Part 1.3
│   ├── test_manual_overrides.py        # Part 1.4
│   └── test_feedback_loop.py           # Part 1.5
├── flows/
│   ├── test_competition_with_intelligence.py  # Part 2
│   ├── test_generic_search_with_intelligence.py  # Part 3
│   └── test_single_product_with_intelligence.py  # Part 4
└── integration/
    └── test_full_pipeline_e2e.py       # Part 5
```

### Utility Modules

```python
# tests/e2e/utils/domain_intelligence_helpers.py

async def get_domain_profile(store, domain: str) -> DomainProfile:
    """Retrieve domain profile from store."""

async def verify_domain_flags(profile: DomainProfile, expected: dict) -> bool:
    """Verify domain profile flags match expectations."""

def calculate_tier_distribution(fetch_results: List) -> dict:
    """Calculate tier usage distribution from fetch results."""

def generate_domain_intelligence_report(profiles: List, results: List) -> dict:
    """Generate report data for domain intelligence metrics."""
```

---

## Adaptation from Existing Tests

### Files to Modify

1. **test_generic_search_v3_e2e.py**
   - Add DomainIntelligenceStore initialization
   - Track domain profiles after each fetch
   - Add domain intelligence metrics to output

2. **test_iwsc_flow.py / test_dwwa_flow.py**
   - Add domain profile verification
   - Track tier usage per competition

3. **test_single_product_e2e_flow.py**
   - Add domain intelligence tracking
   - Verify profile updates after fetch

### New Fixtures Required

```python
# tests/e2e/conftest.py additions

@pytest.fixture(scope="session")
def domain_store():
    """Create DomainIntelligenceStore connected to Redis."""
    from crawler.fetchers.domain_intelligence import DomainIntelligenceStore
    store = DomainIntelligenceStore()
    yield store

@pytest.fixture(scope="session")
def smart_router_with_intelligence(domain_store, redis_client):
    """SmartRouter with domain intelligence enabled."""
    from crawler.fetchers.smart_router import SmartRouter
    router = SmartRouter(
        redis_client=redis_client,
        domain_store=domain_store,
    )
    yield router

@pytest.fixture
def clear_domain_profiles(domain_store):
    """Clear all domain profiles before test."""
    # Clear Redis keys for domain profiles
    pass
```

---

## Approval Checklist

- [ ] Real URLs approved for testing
- [ ] Cost estimate acceptable (~$18-27)
- [ ] Test duration acceptable (~1.5-2 hours)
- [ ] Domain intelligence metrics defined
- [ ] Report format approved
- [ ] File structure approved
