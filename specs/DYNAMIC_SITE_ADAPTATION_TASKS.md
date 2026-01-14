# Task 1: Dynamic Site Adaptation - Implementation Tasks

**Created:** 2026-01-14
**Status:** ✅ COMPLETE (2026-01-14)
**Parent Spec:** BACKLOG_IMPROVEMENTS.md
**Implementation:** 91 tests, 93% coverage

### Completion Summary

| Phase | Status | Tests |
|-------|--------|-------|
| Phase 1: Domain Intelligence Store | ✅ DONE | 17 |
| Phase 2: Heuristic Escalation | ✅ DONE | 25 |
| Phase 3: Adaptive Timeout | ✅ DONE | 11 |
| Phase 4: Smart Tier Selection | ✅ DONE | 10 |
| Phase 5: Feedback Recording | ✅ DONE | 11 |
| Phase 6: SmartRouter Integration | ✅ DONE | 17 |
| Phase 7: Testing & Validation | ✅ DONE | 93% coverage |
| Phase 8: Documentation | ✅ DONE | - |

---

## Decisions Made

| Decision | Choice | Notes |
|----------|--------|-------|
| Storage Backend | **Redis** | Already in stack (Celery uses it) |
| Competition Sites | **Hybrid** | Manual overrides + learning |
| Base Timeout | **20s** | Was 10s, too aggressive |
| Max Timeout | **60s** | Unchanged |
| Escalation Threshold | **50%** | Was 30%, escalate more quickly |
| Min Fetches Before Learning | **5** | Unchanged |
| Tier 3 Retry Period | **3 days** | Was 7 days, reduced |
| Profile TTL | **30 days** | Unchanged |
| Rollout Strategy | **Big Bang** | Not in production, no feature flags needed |

---

## Implementation Guidelines

### Code Quality Requirements

1. **TDD Approach:** Write tests BEFORE implementation code
2. **No Shortcuts:** Implement fully, no workarounds or TODO comments left behind
3. **Python Best Practices:**
   - Type hints on all functions
   - Docstrings for classes and public methods
   - Use dataclasses or Pydantic models
   - Follow PEP 8 naming conventions
4. **Django Best Practices:**
   - Use Django's cache framework for Redis access
   - Proper exception handling
   - Logging at appropriate levels
   - Settings in config files, not hardcoded
5. **Maintainability:**
   - Single responsibility principle
   - Clear separation of concerns
   - Comprehensive test coverage (>80%)

### Progress Tracking

- Update task status in this file after completing each task
- Use status: `TODO` → `IN_PROGRESS` → `DONE`
- Record blockers, decisions, and notes as you go
- Commit after each completed phase

---

## Phase 1: Domain Intelligence Store (Redis)

**Subagent:** `implementer`
**Duration:** 2-3 days

### Task 1.1: Create DomainProfile Model
**Status:** TODO
**File:** `crawler/fetchers/domain_intelligence.py`

**Tests to write first:**
```python
# tests/test_domain_intelligence.py
def test_domain_profile_defaults():
    """New profile has sensible defaults."""

def test_domain_profile_serialization():
    """Profile can be serialized to/from JSON."""

def test_domain_profile_from_dict():
    """Profile can be created from dict."""
```

**Implementation:**
```python
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
import json

@dataclass
class DomainProfile:
    domain: str
    # Performance metrics
    avg_response_time_ms: float = 0.0
    timeout_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    # Tier success rates (start optimistic)
    tier1_success_rate: float = 1.0
    tier2_success_rate: float = 1.0
    tier3_success_rate: float = 1.0
    # Behavior flags (learned)
    likely_js_heavy: bool = False
    likely_bot_protected: bool = False
    likely_slow: bool = False
    # Recommended settings
    recommended_tier: int = 1
    recommended_timeout_ms: int = 20000  # 20s base
    # Timestamps
    last_updated: Optional[datetime] = None
    last_successful_fetch: Optional[datetime] = None
    # Manual override (for competition sites)
    manual_override_tier: Optional[int] = None
    manual_override_timeout_ms: Optional[int] = None

    def to_json(self) -> str:
        """Serialize to JSON for Redis storage."""

    @classmethod
    def from_json(cls, json_str: str) -> "DomainProfile":
        """Deserialize from JSON."""
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Type hints complete
- [ ] Docstrings complete
- [ ] Handles datetime serialization correctly

---

### Task 1.2: Create DomainIntelligenceStore Class
**Status:** TODO
**File:** `crawler/fetchers/domain_intelligence.py`

**Tests to write first:**
```python
def test_store_get_nonexistent_domain():
    """Returns new profile for unknown domain."""

def test_store_save_and_retrieve():
    """Profile persists to Redis and can be retrieved."""

def test_store_ttl_applied():
    """Saved profiles have 30-day TTL."""

def test_store_handles_redis_unavailable():
    """Returns default profile if Redis fails."""
```

**Implementation:**
```python
from django.core.cache import caches
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class DomainIntelligenceStore:
    CACHE_ALIAS = "default"  # Use Django's cache framework
    KEY_PREFIX = "domain_intel:"
    TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

    def __init__(self):
        self.cache = caches[self.CACHE_ALIAS]

    def get_profile(self, domain: str) -> DomainProfile:
        """Get profile for domain, creating new one if not exists."""

    def save_profile(self, profile: DomainProfile) -> bool:
        """Save profile to Redis. Returns False if Redis unavailable."""

    def delete_profile(self, domain: str) -> bool:
        """Delete profile (for testing/admin)."""

    def _get_cache_key(self, domain: str) -> str:
        """Generate cache key for domain."""
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Uses Django cache framework (not raw redis-py)
- [ ] Graceful fallback when Redis unavailable
- [ ] Proper logging on errors

---

### Task 1.3: Add Redis Cache Configuration
**Status:** TODO
**File:** `config/settings/base.py`, `config/settings/development.py`, `config/settings/test.py`

**Tests to write first:**
```python
def test_cache_configuration_exists():
    """Django CACHES setting is properly configured."""
```

**Implementation:**

Update `config/settings/base.py`:
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "spiritswise",
        "TIMEOUT": 30 * 24 * 60 * 60,  # 30 days default
    }
}
```

Update `config/settings/test.py`:
```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}
```

**Acceptance Criteria:**
- [ ] Production uses Redis
- [ ] Tests use in-memory cache (fast, isolated)
- [ ] Environment variable for Redis URL

---

### Task 1.4: Create Migration for Competition Site Overrides
**Status:** TODO
**File:** `crawler/models.py`, new migration

**Tests to write first:**
```python
def test_crawler_source_has_override_fields():
    """CrawlerSource model has manual override fields."""
```

**Implementation:**
Add to `CrawlerSource` model:
```python
# Manual overrides for competition sites
manual_tier_override = models.IntegerField(
    null=True, blank=True,
    choices=[(1, "Tier 1"), (2, "Tier 2"), (3, "Tier 3")],
    help_text="Force specific tier for this source (competition sites)"
)
manual_timeout_override = models.IntegerField(
    null=True, blank=True,
    help_text="Force specific timeout in ms for this source"
)
```

**Acceptance Criteria:**
- [ ] Migration created and applied
- [ ] Fields nullable (most sources won't have overrides)
- [ ] Admin interface shows new fields

---

## Phase 2: Heuristic Escalation Triggers

**Subagent:** `implementer`
**Duration:** 2-3 days

### Task 2.1: Create EscalationHeuristics Class
**Status:** TODO
**File:** `crawler/fetchers/escalation_heuristics.py`

**Tests to write first:**
```python
def test_escalate_on_403():
    """403 status triggers immediate escalation."""

def test_escalate_on_429():
    """429 rate limit triggers escalation."""

def test_escalate_on_cloudflare():
    """Cloudflare challenge page triggers escalation."""

def test_escalate_on_captcha():
    """CAPTCHA page triggers escalation."""

def test_escalate_on_js_placeholder():
    """JS framework placeholder triggers escalation."""

def test_escalate_on_low_success_rate():
    """Domain with <50% tier success triggers escalation."""

def test_no_escalate_on_success():
    """Successful fetch with content doesn't escalate."""

def test_returns_reason():
    """Escalation returns machine-readable reason."""
```

**Implementation:**
```python
from dataclasses import dataclass
from typing import Tuple, Optional
import re

@dataclass
class EscalationResult:
    should_escalate: bool
    reason: Optional[str] = None

class EscalationHeuristics:
    # Escalation threshold - escalate if success rate below this
    SUCCESS_RATE_THRESHOLD = 0.50  # 50% (was 30%)

    @classmethod
    def should_escalate(
        cls,
        status_code: int,
        content: str,
        domain_profile: "DomainProfile",
        current_tier: int,
    ) -> EscalationResult:
        """Determine if we should escalate to next tier."""

    @staticmethod
    def is_cloudflare_challenge(content: str) -> bool:
        """Detect Cloudflare challenge pages."""

    @staticmethod
    def is_captcha_page(content: str) -> bool:
        """Detect CAPTCHA challenges."""

    @staticmethod
    def is_javascript_placeholder(content: str) -> bool:
        """Detect JS framework placeholder pages."""

    @staticmethod
    def is_empty_or_loading(content: str) -> bool:
        """Detect empty/loading pages (better than <500 chars)."""
```

**Acceptance Criteria:**
- [ ] All 8+ tests pass
- [ ] Each detection method is independent and testable
- [ ] Returns structured EscalationResult with reason
- [ ] Threshold configurable via class attribute

---

### Task 2.2: Implement Detection Methods
**Status:** TODO
**File:** `crawler/fetchers/escalation_heuristics.py`

**Tests to write first:**
```python
# Cloudflare detection
def test_detect_cloudflare_browser_check():
    """Detects 'Checking your browser' page."""

def test_detect_cloudflare_cf_chl():
    """Detects cf_chl challenge token."""

# CAPTCHA detection
def test_detect_recaptcha():
    """Detects Google reCAPTCHA."""

def test_detect_hcaptcha():
    """Detects hCaptcha."""

def test_detect_turnstile():
    """Detects Cloudflare Turnstile."""

# JS placeholder detection
def test_detect_nextjs_placeholder():
    """Detects Next.js empty root."""

def test_detect_react_placeholder():
    """Detects React empty root."""

def test_detect_vue_placeholder():
    """Detects Vue empty app."""

def test_detect_noscript_warning():
    """Detects 'JavaScript required' messages."""
```

**Implementation details:**
- Cloudflare indicators: `cf-browser-verification`, `cf_chl_opt`, `Checking your browser`, `_cf_chl_tk`
- CAPTCHA indicators: `g-recaptcha`, `h-captcha`, `cf-turnstile`
- JS framework indicators: `id="__next"`, `id="root"`, `id="app"` with low text ratio
- Loading indicators: `Loading...`, `Please enable JavaScript`, `<noscript>`

**Acceptance Criteria:**
- [ ] All detection tests pass
- [ ] No false positives on normal pages
- [ ] Detection is fast (no complex parsing)

---

## Phase 3: Adaptive Timeout Strategy

**Subagent:** `implementer`
**Duration:** 1-2 days

### Task 3.1: Create AdaptiveTimeout Class
**Status:** TODO
**File:** `crawler/fetchers/adaptive_timeout.py`

**Tests to write first:**
```python
def test_base_timeout_for_unknown_domain():
    """Unknown domain gets 20s base timeout."""

def test_progressive_timeout_increase():
    """Timeout doubles on each attempt: 20s -> 40s -> 60s."""

def test_max_timeout_cap():
    """Timeout never exceeds 60s."""

def test_learned_timeout_used():
    """Domain with history uses learned timeout."""

def test_slow_domain_multiplier():
    """Domains marked slow get 2x timeout."""

def test_update_profile_after_success():
    """Success updates avg response time and recommended timeout."""
```

**Implementation:**
```python
class AdaptiveTimeout:
    BASE_TIMEOUT_MS = 20000    # 20s (was 10s)
    MAX_TIMEOUT_MS = 60000     # 60s
    MIN_FETCHES_FOR_LEARNING = 5

    @classmethod
    def get_timeout(
        cls,
        domain_profile: DomainProfile,
        attempt: int,  # 0-indexed
    ) -> int:
        """Calculate timeout in ms for this attempt."""

    @classmethod
    def update_profile_after_fetch(
        cls,
        profile: DomainProfile,
        response_time_ms: int,
        success: bool,
    ) -> DomainProfile:
        """Update profile based on fetch result."""
```

**Acceptance Criteria:**
- [ ] All 6 tests pass
- [ ] Progressive increase: 20s → 40s → 60s (capped)
- [ ] Uses exponential moving average for learned timeout
- [ ] Respects manual overrides

---

## Phase 4: Smart Tier Selection

**Subagent:** `implementer`
**Duration:** 1-2 days

### Task 4.1: Create SmartTierSelector Class
**Status:** TODO
**File:** `crawler/fetchers/smart_tier_selector.py`

**Tests to write first:**
```python
def test_new_domain_starts_tier1():
    """Unknown domain starts at cheapest tier."""

def test_js_heavy_starts_tier2():
    """Domain marked JS-heavy starts at Tier 2."""

def test_bot_protected_starts_tier3():
    """Domain marked bot-protected starts at Tier 3."""

def test_learned_tier_selection():
    """Domain with 10+ fetches uses learned optimal tier."""

def test_manual_override_respected():
    """Manual tier override takes precedence."""

def test_tier3_retry_after_3_days():
    """Sources marked requires_tier3 retry lower after 3 days."""
```

**Implementation:**
```python
class SmartTierSelector:
    MIN_FETCHES_FOR_CONFIDENCE = 10
    TIER3_RETRY_DAYS = 3  # Was 7

    @classmethod
    def select_starting_tier(
        cls,
        domain_profile: DomainProfile,
        source: Optional["CrawlerSource"] = None,
    ) -> int:
        """Choose optimal starting tier for domain."""

    @classmethod
    def should_retry_lower_tier(
        cls,
        source: "CrawlerSource",
        domain_profile: DomainProfile,
    ) -> bool:
        """Check if we should try lower tiers for a tier3 source."""
```

**Acceptance Criteria:**
- [ ] All 6 tests pass
- [ ] Manual overrides from CrawlerSource respected
- [ ] 3-day retry period for tier3 sources
- [ ] Clear logging of tier selection reason

---

## Phase 5: Feedback Recording

**Subagent:** `implementer`
**Duration:** 1-2 days

### Task 5.1: Create FeedbackRecorder Class
**Status:** TODO
**File:** `crawler/fetchers/feedback_recorder.py`

**Tests to write first:**
```python
def test_record_success_updates_rate():
    """Successful fetch updates tier success rate."""

def test_record_failure_updates_rate():
    """Failed fetch updates tier success rate."""

def test_escalation_reason_sets_flags():
    """Escalation reasons update behavior flags."""

def test_timeout_increments_count():
    """Timeout increments timeout_count."""

def test_multiple_timeouts_marks_slow():
    """3+ timeouts marks domain as likely_slow."""

def test_rate_uses_exponential_average():
    """Success rate uses EMA, not simple average."""
```

**Implementation:**
```python
class FeedbackRecorder:
    EMA_ALPHA = 0.3  # Weight for new observations
    SLOW_THRESHOLD = 3  # Timeouts before marking slow

    @classmethod
    async def record_fetch_result(
        cls,
        store: DomainIntelligenceStore,
        domain: str,
        tier_used: int,
        success: bool,
        response_time_ms: int,
        escalation_reason: Optional[str] = None,
    ) -> DomainProfile:
        """Record fetch result and update domain profile."""

    @staticmethod
    def update_success_rate(
        current_rate: float,
        success: bool,
        alpha: float = 0.3,
    ) -> float:
        """Update rate using exponential moving average."""
```

**Acceptance Criteria:**
- [ ] All 6 tests pass
- [ ] Uses EMA for smooth rate updates
- [ ] Sets behavior flags based on escalation reasons
- [ ] Properly handles async context

---

## Phase 6: SmartRouter Integration

**Subagent:** `implementer`
**Duration:** 2-3 days

### Task 6.1: Refactor SmartRouter to Use New Components
**Status:** TODO
**File:** `crawler/fetchers/smart_router.py`

**Tests to write first:**
```python
def test_smart_router_uses_domain_profile():
    """SmartRouter fetches domain profile before routing."""

def test_smart_router_uses_adaptive_timeout():
    """SmartRouter uses adaptive timeout instead of fixed."""

def test_smart_router_uses_smart_tier():
    """SmartRouter uses SmartTierSelector for starting tier."""

def test_smart_router_uses_heuristics():
    """SmartRouter uses EscalationHeuristics for escalation."""

def test_smart_router_records_feedback():
    """SmartRouter records result via FeedbackRecorder."""

def test_smart_router_respects_manual_override():
    """Manual override from CrawlerSource is respected."""

def test_smart_router_fallback_on_redis_failure():
    """Router works with defaults if Redis unavailable."""
```

**Implementation approach:**
1. Inject DomainIntelligenceStore dependency
2. Replace hardcoded timeout with AdaptiveTimeout
3. Replace fixed starting tier with SmartTierSelector
4. Replace escalation logic with EscalationHeuristics
5. Add FeedbackRecorder call after each fetch
6. Maintain backward compatibility with existing interface

**Acceptance Criteria:**
- [ ] All 7 tests pass
- [ ] Existing SmartRouter tests still pass
- [ ] No change to public API
- [ ] Proper dependency injection
- [ ] Fallback behavior works

---

### Task 6.2: Update SmartRouter.fetch() Method
**Status:** TODO
**File:** `crawler/fetchers/smart_router.py`

**Key changes:**
```python
async def fetch(
    self,
    url: str,
    source: Optional[CrawlerSource] = None,
    force_tier: Optional[int] = None,
) -> FetchResult:
    domain = extract_domain(url)

    # 1. Get domain intelligence
    profile = self.store.get_profile(domain)

    # 2. Check for manual override
    if source and source.manual_tier_override:
        starting_tier = source.manual_tier_override
        timeout_ms = source.manual_timeout_override or profile.recommended_timeout_ms
    else:
        # 3. Smart tier selection
        starting_tier = SmartTierSelector.select_starting_tier(profile, source)
        timeout_ms = AdaptiveTimeout.get_timeout(profile, attempt=0)

    # 4. Execute fetch with escalation
    for tier in range(starting_tier, 4):  # tiers 1-3
        timeout_ms = AdaptiveTimeout.get_timeout(profile, attempt=tier-starting_tier)

        result = await self._fetch_tier(tier, url, timeout_ms)

        if result.success:
            # Check for soft failures via heuristics
            escalation = EscalationHeuristics.should_escalate(
                result.status_code, result.content, profile, tier
            )
            if escalation.should_escalate:
                # Record and continue to next tier
                await FeedbackRecorder.record_fetch_result(
                    self.store, domain, tier, False, result.response_time_ms,
                    escalation.reason
                )
                continue

            # Success - record and return
            await FeedbackRecorder.record_fetch_result(
                self.store, domain, tier, True, result.response_time_ms
            )
            return result
        else:
            # Hard failure - record and escalate
            await FeedbackRecorder.record_fetch_result(
                self.store, domain, tier, False, result.response_time_ms,
                "fetch_failed"
            )

    # All tiers failed
    return FetchResult(success=False, ...)
```

**Acceptance Criteria:**
- [ ] Fetch flow uses all new components
- [ ] Feedback recorded for every attempt
- [ ] Escalation reasons logged
- [ ] Manual overrides respected

---

### Task 6.3: Remove Old Hardcoded Logic
**Status:** TODO
**File:** `crawler/fetchers/smart_router.py`

**Remove/Replace:**
- [ ] Hardcoded 30s timeout → AdaptiveTimeout
- [ ] Fixed starting tier → SmartTierSelector
- [ ] Permanent `requires_tier3` flag → Domain profile
- [ ] Simple <500 char check → EscalationHeuristics

**Acceptance Criteria:**
- [ ] No hardcoded timeout values remain
- [ ] No hardcoded tier decisions remain
- [ ] All escalation goes through heuristics

---

## Phase 7: Testing & Validation

**Subagent:** `test-runner`
**Duration:** 2-3 days

### Task 7.1: Unit Test Coverage
**Status:** TODO

**Requirements:**
- [ ] >80% coverage for all new modules
- [ ] All edge cases covered
- [ ] Mock Redis in unit tests

**Test files to create:**
- `tests/test_domain_intelligence.py`
- `tests/test_escalation_heuristics.py`
- `tests/test_adaptive_timeout.py`
- `tests/test_smart_tier_selector.py`
- `tests/test_feedback_recorder.py`

---

### Task 7.2: Integration Tests
**Status:** TODO

**Requirements:**
- [ ] Test full SmartRouter flow with real Redis
- [ ] Test fallback behavior when Redis unavailable
- [ ] Test manual override behavior

**Test file:** `tests/test_smart_router_integration.py`

---

### Task 7.3: E2E Validation
**Status:** TODO

**Requirements:**
- [ ] Run enrichment on test products
- [ ] Compare metrics with baseline
- [ ] Validate tier usage distribution

---

## Phase 8: Documentation & Cleanup

**Subagent:** `implementer`
**Duration:** 1 day

### Task 8.1: Update README
**Status:** TODO

Add section on adaptive fetching system.

---

### Task 8.2: Update BACKLOG_IMPROVEMENTS.md
**Status:** TODO

Mark Task 1 as COMPLETE with implementation notes.

---

### Task 8.3: Clean Up Temporary Files
**Status:** TODO

Remove any debug/test files created during implementation.

---

## Progress Summary

| Phase | Tasks | Status | Completed |
|-------|-------|--------|-----------|
| 1. Domain Intelligence Store | 4 | TODO | 0/4 |
| 2. Heuristic Escalation | 2 | TODO | 0/2 |
| 3. Adaptive Timeout | 1 | TODO | 0/1 |
| 4. Smart Tier Selection | 1 | TODO | 0/1 |
| 5. Feedback Recording | 1 | TODO | 0/1 |
| 6. SmartRouter Integration | 3 | TODO | 0/3 |
| 7. Testing & Validation | 3 | TODO | 0/3 |
| 8. Documentation | 3 | TODO | 0/3 |
| **TOTAL** | **18** | **TODO** | **0/18** |

---

## Notes & Decisions Log

Record any decisions, blockers, or changes during implementation here:

| Date | Note |
|------|------|
| 2026-01-14 | Task list created with TDD approach |
| | Redis already in stack (Celery uses redis://localhost:6379/1) |
| | Using django-redis cache framework for storage |

---

## Files to Create/Modify

### New Files
- `crawler/fetchers/domain_intelligence.py`
- `crawler/fetchers/escalation_heuristics.py`
- `crawler/fetchers/adaptive_timeout.py`
- `crawler/fetchers/smart_tier_selector.py`
- `crawler/fetchers/feedback_recorder.py`
- `tests/test_domain_intelligence.py`
- `tests/test_escalation_heuristics.py`
- `tests/test_adaptive_timeout.py`
- `tests/test_smart_tier_selector.py`
- `tests/test_feedback_recorder.py`
- `tests/test_smart_router_integration.py`

### Modified Files
- `crawler/fetchers/smart_router.py` - Major refactor
- `crawler/models.py` - Add override fields to CrawlerSource
- `config/settings/base.py` - Add CACHES config
- `config/settings/development.py` - Add CACHES config
- `config/settings/test.py` - Add in-memory CACHES
