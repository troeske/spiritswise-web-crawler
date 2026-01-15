# Enrichment Improvement Spec

**Created:** 2026-01-14
**Purpose:** Consolidated specification for enrichment pipeline improvements, including performance analysis, architecture decisions, and implementation plans.

---

## Status Overview

| Task | Priority | Status | Key Finding |
|------|----------|--------|-------------|
| 4. AI Model Selection | P0 | **DONE** | Use gpt-4.1 for all extractions (no code changes) |
| 3. Schema Optimization | P0 | **DONE** | Full schema now sent to AI with enum validation |
| 1. Dynamic Site Adaptation | P1 | **DONE** | Domain intelligence with adaptive routing (91 tests) |
| 2. Caching Strategy | P2 | **PARKED** | User decision: complexity not worth it |

**Implementation order:** ~~Task 3~~ → ~~Task 4~~ → ~~Task 1~~ → Task 2 (parked)

**All priority tasks complete!**

---

## Performance Analysis (Jan 13 vs Jan 14 E2E Tests)

### Comparison Summary

| Product | Metric | Jan 13 | Jan 14 | Status |
|---------|--------|--------|--------|--------|
| **SMWS 1.292** | ECP | 0.0 | 10.17 | ✅ Fixed |
| | Fields | 16 | 15 | -1 |
| | Sources Used | 4 | 3 | -1 |
| | Sources Searched | 9 | 5 | -4 |
| | Has primary_cask | Yes | No | ❌ Lost |
| **GlenAllachie** | ECP | 0.0 | 16.95 | ✅ Fixed |
| | Fields | 21 | 21 | Same |
| | Sources Used | 6 | 6 | Same |
| | Sources Searched | 9 | 6 | -3 |
| | Has distillery | Yes | No | ❌ Lost |
| **Ballantines** | ECP | 0.0 | 25.42 | ✅ Fixed |
| | Fields | 16 | 29 | +13 |
| | Sources Used | 4 | 4 | Same |
| | Sources Searched | 12 | 4 | -8 |

### Key Findings

**Improvements:**
- ECP calculation now works (was stuck at 0.0 due to bug)
- Ballantines gained 13 new fields (mouthfeel, balance, images, etc.)

**Regressions:**
- SMWS lost primary_cask field (had ex-Bourbon, rum cask, Cognac)
- GlenAllachie lost distillery field (had "The GlenAllachie")
- Fewer sources searched across all products (4-8 fewer per product)
- Lost access to valuable sources: newmake.smwsa.com, scotchwhisky.com, whiskyshopusa.com, binnys.com

### Root Cause Analysis

#### Issue 1: CRAWLER_MAX_RETRIES = 0 in Test Settings

**Location:** `config/settings/test.py:75`

**Evidence:**
- SMWS: 9 to 5 sources searched
- GlenAllachie: 9 to 6 sources searched
- Ballantines: 12 to 4 sources searched

**Root Cause:** Tier 1 fails immediately with "after 0 attempts" for ANY network hiccup

**Impact:** HIGH - Missing enrichment data from reliable sources

**Fix:** Set to at least 2 for e2e tests:
```python
CRAWLER_MAX_RETRIES = 2  # Was 0, causing immediate failures
```

#### Issue 2: Lost Primary_Cask for SMWS

**Jan 13 had:** ["ex-Bourbon", "rum cask", "Cognac"]
**Jan 14 has:** Field missing entirely

**Root Cause:** Lost connection to sources that provided cask info:
- newmake.smwsa.com/collections/all-products - not searched Jan 14
- scotchwhisky.com/whiskypedia - not searched Jan 14

**Impact:** MEDIUM - Important whisky metadata lost

#### Issue 3: Lost Distillery for GlenAllachie

**Jan 13 had:** distillery = "The GlenAllachie"
**Jan 14 has:** distillery = null

**Root Cause:** Same sources used but distillery not extracted (AI variance or page content change)

**Impact:** LOW - Can be derived from brand name

#### Issue 4: Fewer Tasting Notes for Ballantines

**Jan 13 finish_flavors:** 17 items (peat smoke, raisins, oak, vanilla, coffee, chocolate, mango, salt, malt, fudge, wet earth, wood ash, smoke, licorice, spice, etc.)
**Jan 14 finish_flavors:** 7 items (sweet, refreshing, tannins, green fruits, leaves, wood, cooked vegetables)

**Root Cause:** Different sources provided data:
- Jan 13: connosr.com, leivine.com (whisky review sites with detailed notes)
- Jan 14: ballantines.com, whiskybase.com (official/database sites with sparse notes)

**Impact:** MEDIUM - Less detailed tasting profile despite more fields

### Site-Specific Issues Identified

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| Reddit URLs always fail | 100% failure | Block in URL discovery |
| WhiskyBase timeouts | Frequent Tier 2 timeout | Use domcontentloaded, 45s timeout |
| SMWS.com returns wrong product | Unreliable | Remove from enrichment sources |
| Lost quality sources | Data regression | Increase retries (fix CRAWLER_MAX_RETRIES) |

### Priority Actions Table

| Priority | Action | Impact | Effort | Addresses |
|----------|--------|--------|--------|-----------|
| P0 | Set CRAWLER_MAX_RETRIES=2 | High | Low | Source coverage |
| P1 | Block Reddit URLs | Medium | Low | 100% failure rate |
| P1 | Deprioritize smws.com | Medium | Low | Wrong product returns |
| P2 | WhiskyBase timeout config | Medium | Medium | Playwright timeouts |
| P2 | Add extraction field emphasis | Medium | Medium | AI variance |

---

## Task 1: Dynamic Site Adaptation

**Status:** ✅ COMPLETE (2026-01-14)
**Priority:** P1
**Task List:** [specs/DYNAMIC_SITE_ADAPTATION_TASKS.md](specs/DYNAMIC_SITE_ADAPTATION_TASKS.md)

### Implementation Summary

**Completed Components:**
- **Domain Intelligence Store** (Redis-backed) - 17 tests
- **Heuristic Escalation Triggers** - 25 tests (Cloudflare, CAPTCHA, JS placeholder detection)
- **Adaptive Timeout Strategy** - 11 tests (progressive 20s→40s→60s)
- **Smart Tier Selection** - 10 tests (cost-optimized starting tier)
- **Feedback Recording** - 11 tests (EMA-based learning)
- **SmartRouter Integration** - 17 tests (full integration)

**Total: 91 tests, 93% coverage**

**Key Files Created:**
- `crawler/fetchers/domain_intelligence.py` - DomainProfile dataclass + Redis store
- `crawler/fetchers/escalation_heuristics.py` - Cloudflare/CAPTCHA/JS detection
- `crawler/fetchers/adaptive_timeout.py` - Progressive timeout strategy
- `crawler/fetchers/smart_tier_selector.py` - Cost-optimized tier selection
- `crawler/fetchers/feedback_recorder.py` - EMA-based learning from results

**SmartRouter Updated:**
- Injects DomainIntelligenceStore for adaptive behavior
- Uses SmartTierSelector for intelligent starting tier
- Uses AdaptiveTimeout for domain-specific timeouts
- Uses EscalationHeuristics for soft failure detection
- Uses FeedbackRecorder to learn from fetch results

### Decisions Made

| Decision | Choice |
|----------|--------|
| Storage Backend | Redis (already in stack) |
| Competition Sites | Hybrid (manual overrides + learning) |
| Base Timeout | 20s |
| Max Timeout | 60s |
| Escalation Threshold | 50% (escalate if tier success < 50%) |
| Tier 3 Retry Period | 3 days |
| Profile TTL | 30 days |
| Rollout Strategy | Big Bang |

### Problem

Storing lists of "good" or "bad" sites with specific behaviors (timeouts, wait strategies) makes the implementation brittle. Sites inevitably change, and hardcoded lists become outdated quickly.

### Requirements
- Design a generic escalation process that does NOT depend on fixed/outdated site info
- Only competition sites (IWSC, DWWA, etc.) warrant constant manual adaptation
- All other sites should be handled dynamically

### Recommended Approach: Hybrid Heuristic + Feedback Loop

Combines:
1. **Heuristic rules** for fast, cheap initial decisions
2. **Feedback loop** for learning from success/failure patterns over time
3. **Progressive escalation** with adaptive timeouts

### Current Implementation Analysis

**SmartRouter.fetch() Workflow:**
```
1. Check if source.requires_tier3 == True -> Skip to Tier 3
2. Check if force_tier is specified -> Use that tier
3. Otherwise, start at Tier 1 and iterate through tiers 1-3:
   - Try current tier
   - If success, check for age gate (content < 500 chars OR keywords)
   - If age gate detected -> escalate to next tier
   - If fetch failed -> escalate to next tier
4. On Tier 3 success -> mark source.requires_tier3 = True permanently
```

**What's Currently Hardcoded:**

| Item | Current Value | Location |
|------|---------------|----------|
| Timeout | 30 seconds (all tiers) | `smart_router.py` line 78 |
| Age gate content threshold | 500 characters | `age_gate.py` line 70 |
| Age gate keywords | 16 phrases | `age_gate.py` lines 20-37 |
| Retry count | 3 attempts | `tier1_httpx.py` line 75 |
| requires_tier3 flag | Permanent once set | `smart_router.py` line 344 |

**Identified Weaknesses:**
1. No learning mechanism - success/failure history not used for routing
2. No timeout adaptation - same 30s for all sites
3. Limited bot detection - only 403 and Cloudflare patterns
4. No JavaScript detection - always tries Tier 1 first
5. requires_tier3 is permanent but sites change

### Proposed Components

#### Component 1: Domain Intelligence Store (Redis-backed)

```python
@dataclass
class DomainProfile:
    domain: str
    avg_response_time_ms: float = 0
    timeout_count: int = 0
    success_count: int = 0
    tier1_success_rate: float = 1.0
    tier2_success_rate: float = 1.0
    tier3_success_rate: float = 1.0
    likely_js_heavy: bool = False
    likely_bot_protected: bool = False
    likely_slow: bool = False
    recommended_tier: int = 1
    recommended_timeout_ms: int = 15000
    last_updated: datetime
    last_successful_fetch: datetime
```

Storage: Redis with 30-day TTL per domain

#### Component 2: Heuristic Escalation Triggers

```python
class EscalationHeuristics:
    @staticmethod
    def should_escalate(response, content, domain_profile):
        # Hard triggers (always escalate)
        if response.status_code == 403:  # Blocked
            return True, "blocked_403"
        if response.status_code == 429:  # Rate limited
            return True, "rate_limited_429"

        # Soft triggers (check content)
        if is_cloudflare_challenge(content):
            return True, "cloudflare_challenge"
        if is_captcha_page(content):
            return True, "captcha_detected"
        if is_javascript_placeholder(content):
            return True, "js_placeholder"

        # Learned triggers (from domain history)
        if domain_profile.tier1_success_rate < 0.3:
            return True, "low_historical_success"

        return False, None
```

#### Component 3: Adaptive Timeout Strategy

```python
class AdaptiveTimeout:
    BASE_TIMEOUT_MS = 10000  # Start at 10s (aggressive)
    MAX_TIMEOUT_MS = 60000   # Cap at 60s

    @classmethod
    def get_timeout(cls, domain_profile, attempt):
        # Progressive increase: 10s -> 20s -> 40s
        base = domain_profile.recommended_timeout_ms if domain_profile.success_count > 5 else cls.BASE_TIMEOUT_MS
        timeout = base * (2 ** attempt)
        if domain_profile.likely_slow:
            timeout = min(timeout * 2, cls.MAX_TIMEOUT_MS)
        return min(timeout, cls.MAX_TIMEOUT_MS)
```

#### Component 4: Smart Tier Selection

```python
class SmartTierSelector:
    @staticmethod
    def select_starting_tier(domain_profile):
        if domain_profile.success_count >= 10:
            if domain_profile.tier3_success_rate > 0.8 and domain_profile.tier1_success_rate < 0.2:
                return 3
            if domain_profile.tier2_success_rate > 0.8 and domain_profile.tier1_success_rate < 0.3:
                return 2
        if domain_profile.likely_js_heavy:
            return 2
        if domain_profile.likely_bot_protected:
            return 3
        return 1  # Default: always try Tier 1 first (cheapest)
```

#### Component 5: Feedback Recording

Record fetch results to improve future decisions:
- Update success rates per tier
- Update behavior flags based on escalation reasons
- Update recommended timeout based on response time

#### Component 6: Tier 3 Flag Auto-Reset

Try lower tiers again after 7 days for `requires_tier3` sources (sites change).

### Implementation Plan

| Phase | Description | Duration |
|-------|-------------|----------|
| 1 | Domain Intelligence Store (Redis) | 2-3 days |
| 2 | Heuristic Escalation | 2-3 days |
| 3 | Adaptive Timeouts | 1-2 days |
| 4 | Smart Tier Selection | 1-2 days |
| 5 | Feedback Loop | 1-2 days |
| 6 | Testing and Validation | 2-3 days |
| **Total** | | **10-15 days** |

### Metrics to Track

1. Tier Distribution: % of fetches at each tier (goal: minimize Tier 3)
2. First-Attempt Success Rate: % that succeed without escalation
3. Average Response Time: Per domain, per tier
4. Cost Efficiency: ScrapingBee API calls / successful fetch
5. False Escalation Rate: Unnecessary escalations to higher tiers

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Redis unavailable | Fallback to current static behavior |
| Cold start (no domain data) | Conservative defaults, learn quickly |
| Feedback loop oscillation | Dampening via exponential moving average |
| Over-aggressive timeouts | Floor of 10s, learn from failures |
| Profile data becomes stale | 30-day TTL, periodic refresh |

---

## Task 2: Evaluate Caching Strategy

**Status:** PARKED
**Priority:** P2
**User Decision:** Complexity not worth it

User feels caching is a double-edged sword and not worth the complexity at this time.

---

## Task 3: Optimize AI Schema and Field Definitions

**Status:** ✅ COMPLETE (2026-01-14)
**Priority:** P0 (High Impact)
**Task List:** [specs/SCHEMA_OPTIMIZATION_TASKS.md](specs/SCHEMA_OPTIMIZATION_TASKS.md)

### Implementation Summary

**Completed:**
- Full schema (descriptions, examples, derive_from, allowed_values) now sent to AI service
- Database (base_fields.json) is single source of truth - no more hardcoded FIELD_DESCRIPTIONS
- Enum validation in response processing with case-insensitive matching
- Comprehensive test coverage (33 unit tests, 9 integration tests)

**Key Changes:**
- `FieldDefinition.to_extraction_schema()` - returns complete field definitions
- `FieldDefinition.get_schema_for_product_type()` - filters by product type
- `AIClientV2._get_default_schema()` - now returns full schema dicts
- `AIClientV2._validate_enum_fields()` - validates and normalizes enum values
- Added `format_hint` field to FieldDefinition model

**Files Modified:**
- `crawler/models.py` - FieldDefinition schema methods
- `crawler/services/ai_client_v2.py` - Full schema support + enum validation
- `crawler/fixtures/base_fields.json` - Added format_hint, missing fields
- `ai_enhancement_engine/prompts/v2_builder.py` - External schema support (deprecated internal)
- `ai_enhancement_engine/prompts/v2_extraction_prompts.py` - External schema support

### Problem

The AI extraction quality depends heavily on:
1. The schema passed to the AI service
2. The field definitions and descriptions
3. How well the AI understands what we want

### Architecture Overview

The schema system has **three layers** with duplication issues:

1. **Database Schema** (`crawler/fixtures/base_fields.json`) - 76 fields, comprehensive
2. **AI Service Prompt Builder** (`ai_enhancement_engine/prompts/v2_builder.py`) - ~80 fields, different
3. **Extraction Prompts** (`ai_enhancement_engine/prompts/v2_extraction_prompts.py`) - ~60 fields, another variation

### CRITICAL ISSUE: Schema Duplication

**Problem:** Field definitions exist in THREE places with different content.

**Example of Inconsistency (ABV field):**

| Location | Description |
|----------|-------------|
| `base_fields.json` | "Alcohol percentage (0-80). Look for: ABV, Alcohol by Volume, Alcohol Content, Alc./Vol., Alc/Vol, Vol%, % Vol, % vol. For Proof (US), divide by 2..." |
| `v2_builder.py` | "Alcohol by volume percentage (e.g., 40.0 for 40%)" |
| `v2_extraction_prompts.py` | "Alcohol percentage (0-80). Look for: ABV, Alcohol by Volume, Proof (divide by 2), Vol%, Alc./Vol., Alkoholgehalt" |

**Impact:** The database schema (best quality) is NOT being sent to the AI service! The AI service uses its own hardcoded descriptions.

### CRITICAL ISSUE: Schema Not Sent to AI Service

**Problem:** `ai_client_v2.py` only sends field NAMES to the AI service, not descriptions:

```python
# In _get_default_schema():
field_names = list(fields.values_list("field_name", flat=True).distinct())
return field_names  # Only names, not full schema!
```

**Current Flow:**
```
Crawler → ai_client_v2.py → sends ["name", "brand", "abv", ...]
AI Service → uses its own FIELD_DESCRIPTIONS to build prompt
```

**Should Be:**
```
Crawler → ai_client_v2.py → sends [{name, type, description, examples}, ...]
AI Service → uses provided schema directly
```

### Fields Needing Improvements

| Field | Issue | Recommendation |
|-------|-------|----------------|
| `age_statement` | Type is "string" but examples show integers | Change type to "integer" or clarify |
| `category` | Ambiguous - overlaps with whiskey_type/style | Add explicit examples |
| `vintage` | Not defined in base_fields.json | Add field definition |
| `cask_type` / `primary_cask` | Naming inconsistency | Consolidate naming |
| `finish_cask` / `finishing_cask` | Naming inconsistency | Consolidate naming |

### Action Items

#### High Priority (Do First)
1. **Single Source of Truth**: Remove `FIELD_DESCRIPTIONS` from AI service, pass database schema directly
2. **Send Full Schema**: Modify `_get_default_schema()` to include descriptions, examples, derive_from
3. **Add Missing Fields**: Add `vintage`, `producer`, `cask_type` to base_fields.json

#### Medium Priority
4. **Consolidate Field Names**: Align v2_builder.py names with base_fields.json
5. **Add Format Specs**: Add explicit formats for dates, ranges, arrays
6. **Enum Enforcement**: Add strict enum validation in prompts

#### Lower Priority
7. **Reduce Multi-Product Schema**: Trim to 15-18 fields
8. **Add Item Count Guidance**: Specify array length expectations
9. **Create Test Suite**: Validate extraction consistency

### Files Involved

| File | Location | Purpose |
|------|----------|---------|
| `ai_client_v2.py` | `crawler/services/` | Client that calls AI service, loads schema from DB |
| `base_fields.json` | `crawler/fixtures/` | 76 field definitions (primary source of truth) |
| `models.py` | `crawler/` | `FieldDefinition` model with `to_extraction_schema()` |
| `v2_builder.py` | `ai_enhancement_engine/prompts/` | Builds prompts with domain context |
| `v2_extraction_prompts.py` | `ai_enhancement_engine/prompts/` | Alternative prompt builder |

---

## Task 4: AI Model Selection and Cost Analysis

**Status:** DECISION MADE
**Priority:** P0

### Decision: Use gpt-4.1 for All Extractions

**Rationale:** Quality and depth of data is the product. Compared to manual labor costs, AI extraction cost is negligible.

**Cost Perspective:**

| Method | Cost per Product | Comparison |
|--------|------------------|------------|
| Manual data entry | $3.75 - $12.50 | (15-30 min @ $15-25/hr) |
| AI extraction (gpt-4.1) | ~$0.04 | **100-300x cheaper** |

### Current Configuration (No Changes Needed)

```python
# extractor_v2.py line 281
model = getattr(settings, "OPENAI_MODEL", None) or "gpt-4.1"
```

### Model Pricing Reference (January 2026)

| Model | Input (per 1M) | Output (per 1M) | Context | Quality |
|-------|----------------|-----------------|---------|---------|
| **gpt-4.1** | $2.00 | $8.00 | 1M tokens | Excellent |
| gpt-4.1-mini | $0.40 | $1.60 | 1M tokens | Very Good |
| gpt-4.1-nano | $0.10 | $0.40 | 1M tokens | Good |
| gpt-4o | $2.50 | $10.00 | 128K tokens | Excellent |
| gpt-4o-mini | $0.15 | $0.60 | 128K tokens | Good |

### Full Enrichment Cost Breakdown

#### Service Pricing Reference

| Service | Unit | Cost |
|---------|------|------|
| SerpAPI | 1 search | $0.015 |
| ScrapingBee | 15 credits (JS + premium) | ~$0.05 |
| OpenAI gpt-4.1 | 8K in / 1.5K out | ~$0.028 |

#### Cost by Enrichment Stage

| Stage | Min | Typical | Max |
|-------|-----|---------|-----|
| **New → Baseline** | $0.13 | $0.27 | $0.48 |
| **Baseline → Complete** | $0.16 | $0.30 | $0.51 |
| **New → Complete** | $0.22 | $0.36 | $0.73 |

#### Service Distribution (Typical Full Enrichment: ~$0.36)

```
SerpAPI (25%)       [========         ] $0.09
AI Extraction (47%) [===============  ] $0.17
Fetching (28%)      [=========        ] $0.10
```

#### Monthly Volume Projections

**At 1,000 products/month:**
| Scenario | Cost/Product | Monthly | Annual |
|----------|--------------|---------|--------|
| New → Baseline | $0.27 | $270 | $3,240 |
| New → Complete | $0.36 | $360 | $4,320 |

**At 10,000 products/month:**
| Scenario | Cost/Product | Monthly | Annual |
|----------|--------------|---------|--------|
| New → Baseline | $0.27 | $2,700 | $32,400 |
| New → Complete | $0.36 | $3,600 | $43,200 |

---

## Implementation Priorities

### Immediate (P0)

1. **Fix CRAWLER_MAX_RETRIES** in `config/settings/test.py`
   ```python
   CRAWLER_MAX_RETRIES = 2  # Was 0
   ```

2. **Schema Unification** (Task 3)
   - Modify `_get_default_schema()` to return full field definitions
   - Remove hardcoded `FIELD_DESCRIPTIONS` from AI service
   - Single source of truth = database

### Short-term (P1)

3. **Site-Specific Fixes**
   - Block Reddit URLs in URL discovery
   - Deprioritize smws.com (returns wrong products)
   - Configure WhiskyBase timeouts

4. **Dynamic Site Adaptation** (Task 1)
   - Implement Domain Intelligence Store
   - Heuristic escalation triggers
   - Adaptive timeouts

### Parked (P2)

5. **Caching Strategy** (Task 2) - Per user decision

---

## Appendix: File Locations

| Component | File | Key Lines |
|-----------|------|-----------|
| SmartRouter | `crawler/fetchers/smart_router.py` | 78, 344 |
| Tier 1 | `crawler/fetchers/tier1_httpx.py` | 75, 260 |
| Tier 2 | `crawler/fetchers/tier2_playwright.py` | - |
| Tier 3 | `crawler/fetchers/tier3_scrapingbee.py` | 36, 81 |
| Age Gate | `crawler/fetchers/age_gate.py` | 20-37, 70, 117-146 |
| AI Client | `crawler/services/ai_client_v2.py` | _get_default_schema() |
| Field Defs | `crawler/fixtures/base_fields.json` | 76 fields |
| Test Config | `config/settings/test.py` | 75 |
| V2 Builder | `ai_enhancement_engine/prompts/v2_builder.py` | FIELD_DESCRIPTIONS |
| Extractor | `ai_enhancement_engine/core/extractor_v2.py` | 281 |
