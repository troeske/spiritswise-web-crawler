# Generic Search Discovery V3 - Specification

**Version:** 1.0
**Created:** 2026-01-13
**Status:** Draft

## Table of Contents
1. [Overview](#1-overview)
2. [Learnings from Competition Flow](#2-learnings-from-competition-flow)
3. [Current State Analysis](#3-current-state-analysis)
4. [Target Architecture](#4-target-architecture)
5. [Feature Specifications](#5-feature-specifications)
6. [Data Models](#6-data-models)
7. [API Contracts](#7-api-contracts)
8. [Quality Gates](#8-quality-gates)
9. [Testing Strategy](#9-testing-strategy)
10. [Success Criteria](#10-success-criteria)

---

## 1. Overview

### 1.1 Purpose
Upgrade the Generic Search Discovery flow to match the maturity and reliability of the Competition Flow (IWSC), incorporating all learnings from E2E testing.

### 1.2 Goals
- Implement 2-step enrichment pipeline (producer → review sites)
- Add robust product match validation to prevent cross-contamination
- Implement category-specific quality requirements
- Add comprehensive source tracking and auditing
- Achieve 90%+ data quality for discovered products

### 1.4 Key Difference from Competition Flow

**Competition Flow (IWSC):**
- List page contains `detail_url` links to individual product pages
- Step 1 (detail page) extracts from authoritative competition site
- 3-step pipeline: Detail → Producer → Review Sites

**Generic Search Flow:**
- List pages are listicles/roundups (Forbes, VinePair, etc.)
- Products listed inline with brief descriptions, NO detail links
- External links go to retailers, not authoritative sources
- **2-step pipeline: Producer → Review Sites**

```
┌─────────────────────────────────────────────────────────────────────┐
│           GENERIC SEARCH vs COMPETITION FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  COMPETITION (IWSC):                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ List Page│ →  │ Detail   │ →  │ Producer │ →  │ Review   │      │
│  │ (awards) │    │ Page     │    │ Page     │    │ Sites    │      │
│  └──────────┘    │ (0.95)   │    │ (0.85)   │    │ (0.70)   │      │
│       ↓          └──────────┘    └──────────┘    └──────────┘      │
│  detail_url ✓                                                       │
│                                                                     │
│  GENERIC SEARCH:                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                      │
│  │ Listicle │ →  │ Producer │ →  │ Review   │                      │
│  │ (Forbes) │    │ Page     │    │ Sites    │                      │
│  └──────────┘    │ (0.85)   │    │ (0.70)   │                      │
│       ↓          └──────────┘    └──────────┘                      │
│  detail_url ✗                                                       │
│  (inline text)                                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Scope
- `DiscoveryOrchestratorV2` → `DiscoveryOrchestratorV3`
- Quality Gate V3 integration
- Source tracking improvements
- E2E test coverage matching competition flow

---

## 2. Learnings from Competition Flow

### 2.1 Architecture Patterns (COMP-LEARN-001)

**Competition Flow - 3-Step Pipeline (for reference):**
```
Step 1: Detail Page    → High confidence (0.95), single authoritative source
Step 2: Producer Page  → Search + filter for official brand sites (0.85+)
Step 3: Review Sites   → Multi-source with diminishing returns, stop at COMPLETE
```

**Generic Search Flow - 2-Step Pipeline (adapted):**
```
Step 1: Producer Page  → Search "{brand} {name} official" for brand sites (0.85+)
Step 2: Review Sites   → Multi-source enrichment, stop at COMPLETE (90% ECP)
```

**Why No Detail Page Step:**
- Generic search returns listicles (Forbes "Best Bourbons 2025")
- Products listed inline with brief text, no `detail_url` available
- External links point to retailers (Total Wine), not authoritative sources
- Skeleton extraction captures what's available on list page

**Key Insight:** Sequential funnel with early exit optimization reduces API costs while maintaining quality.

### 2.2 Product Match Validation (COMP-LEARN-002)

**Multi-level validation prevents cross-contamination:**
```python
Level 1: Brand matching (target vs extracted must overlap)
Level 2: Product type keywords (bourbon vs rye, single malt vs blended)
Level 3: Name token overlap (>= 30% required)
```

**Real-world example:** "Frank August Bourbon" enrichment rejected data from "Frank August Rye" page.

### 2.3 Category-Specific Requirements (COMP-LEARN-003)

**Exemptions for blended whiskies:**
- `primary_cask` - Not required (use dozens/hundreds of casks)
- `region` - Not required (source from multiple regions)

**Implementation:**
```python
CATEGORIES_NO_PRIMARY_CASK_REQUIRED = ["blended scotch whisky", "blended malt", ...]
CATEGORIES_NO_REGION_REQUIRED = ["blended scotch whisky", "blended grain whisky", ...]
```

### 2.4 Confidence-Based Data Merging (COMP-LEARN-004)

**Rule:** Higher confidence sources override lower confidence sources.
```python
IF new_confidence > existing_confidence:
    REPLACE field value
ELIF both are arrays:
    APPEND unique items
ELIF both are dicts:
    MERGE recursively
```

### 2.5 Type Normalization (COMP-LEARN-005)

**Post-extraction normalization ensures correct types:**
- Array fields: Convert comma-separated strings to arrays
- Integer fields: Parse numeric strings to integers
- Boolean fields: Convert "yes/no/true/false" strings

### 2.6 Field Derivation (COMP-LEARN-006)

**Derive missing fields from related fields:**
- `primary_cask` from `maturation_notes` using regex patterns
- `finishing_cask` from text containing "finish/finished/double matured"

### 2.7 Source Tracking (COMP-LEARN-007)

**Comprehensive tracking in EnrichmentResult:**
```python
sources_searched: List[str]    # All URLs attempted
sources_used: List[str]        # URLs that enriched data
sources_rejected: List[Dict]   # URLs rejected with reasons
```

### 2.8 Quality Gate V3 Status Hierarchy (COMP-LEARN-008)

```
REJECTED → SKELETON → PARTIAL → BASELINE → ENRICHED → COMPLETE
   (no name)  (name)    (6 fields) (13 fields) (+mouthfeel) (90% ECP)
```

**Key:** COMPLETE requires 90% ECP, not just "all fields present".

---

## 3. Current State Analysis

### 3.1 Capabilities
- SearchTerm-driven search execution
- SerpAPI integration for organic search
- SmartRouter tiered fetching (httpx → Playwright → ScrapingBee)
- AIClientV2 extraction with full/skeleton schemas
- Basic QualityGateV2 assessment

### 3.2 Critical Gaps

| Gap ID | Description | Impact | Priority |
|--------|-------------|--------|----------|
| GAP-001 | No 2-step enrichment pipeline | Lower data quality | P0 |
| GAP-002 | No product match validation | Cross-contamination risk | P0 |
| GAP-003 | No category-specific requirements | Blends stuck at PARTIAL | P1 |
| GAP-004 | No type normalization | Arrays returned as strings | P1 |
| GAP-005 | No field derivation | Missing cask info | P1 |
| GAP-006 | Basic source tracking only | Limited auditability | P2 |
| GAP-007 | No duplicate detection by content | Redundant processing | P2 |
| GAP-008 | No confidence-based merging | Lower quality wins | P1 |

---

## 4. Target Architecture

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    DiscoveryOrchestratorV3                       │
├─────────────────────────────────────────────────────────────────┤
│  SearchTermLoader → SerpAPIClient → URLValidator → ContentFetcher│
│         ↓                                              ↓         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 EnrichmentPipelineV3                         │ │
│  │  ┌──────────────┐   ┌────────────────┐                      │ │
│  │  │   Step 1     │ → │    Step 2      │                      │ │
│  │  │  Producer    │   │  Review Sites  │                      │ │
│  │  │  Page Search │   │  Multi-source  │                      │ │
│  │  └──────────────┘   └────────────────┘                      │ │
│  │            ↓                   ↓                            │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │              ProductMatchValidator                       │ │ │
│  │  │  - Brand matching                                        │ │ │
│  │  │  - Product type keywords                                 │ │ │
│  │  │  - Name token overlap                                    │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │            ↓                   ↓                            │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │              ConfidenceBasedMerger                       │ │ │
│  │  │  - Higher confidence wins                                │ │ │
│  │  │  - Array append unique                                   │ │ │
│  │  │  - Dict merge recursive                                  │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│         ↓                                                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   QualityGateV3                              │ │
│  │  - Category-specific requirements                            │ │
│  │  - 90% ECP for COMPLETE                                      │ │
│  │  - Status: SKELETON → PARTIAL → BASELINE → ENRICHED → COMPLETE│
│  └─────────────────────────────────────────────────────────────┘ │
│         ↓                                                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   SourceTracker                              │ │
│  │  - sources_searched, sources_used, sources_rejected          │ │
│  │  - Field provenance attribution                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

```
1. SearchTerm → SerpAPI → URL List (listicles, review sites)
2. URL → SmartRouter → HTML Content
3. Content → AIClientV2 → Extracted Products (skeleton from inline text)
4. For each extracted product:
   4.1 Step 1: Producer search "{brand} {name} official" → Filter official → Extract
   4.2 IF not COMPLETE: Step 2: Review sites → Multi-source → Stop at COMPLETE
5. Each extraction → ProductMatchValidator → Accept/Reject
6. Accepted data → ConfidenceBasedMerger → Merged product
7. Merged product → QualityGateV3 → Status assessment
8. All steps → SourceTracker → Audit trail
```

---

## 5. Feature Specifications

### 5.1 2-Step Enrichment Pipeline (FEAT-001)

**Reference:** COMP-LEARN-001

> **Note:** Generic search uses a 2-step pipeline (Producer → Review Sites) because
> search results are listicles with inline product text, not detail page links.
> See Section 1.4 for comparison with Competition Flow's 3-step pipeline.

#### 5.1.1 Step 1: Producer Page Search

**Purpose:** Find and extract from official brand/producer website.

**Input:**
- Product data (name, brand, producer) from skeleton extraction
- `product_type` for schema selection

**Process:**
1. Build search query: `"{brand} {name} official"`
2. Execute SerpAPI search
3. Filter URLs by priority:
   - Official sites (brand in domain)
   - Non-retailers
   - Retailers (deprioritized)
4. For top 3 matches:
   - Fetch and extract
   - Validate product match
   - If match: merge with confidence boost (+0.1, max 0.95)

**Output:**
- Extracted data dict
- Field confidences dict (0.85-0.95 for official sites)

**Exit Condition:** If status reaches COMPLETE after Step 1, skip Step 2.

#### 5.1.2 Step 2: Review Site Enrichment

**Purpose:** Fill remaining fields from review sites when producer page didn't reach COMPLETE.

**Input:**
- Current product data (after Step 1)
- Missing fields list
- EnrichmentConfig templates

**Process:**
1. Load EnrichmentConfigs ordered by priority
2. For each config:
   - Build search query from template
   - Execute search
   - For each URL (until limits):
     - Fetch and extract
     - Validate product match
     - If match: merge by confidence (0.70-0.80)
     - Update session tracking
   - Check exit conditions

**Exit Conditions:**
- Status reaches COMPLETE (90% ECP)
- Max searches exceeded (default 3)
- Max sources exceeded (default 5)
- Max time exceeded (default 120s)

### 5.2 Product Match Validation (FEAT-002)

**Reference:** COMP-LEARN-002

#### 5.2.1 Validation Levels

**Level 1: Brand Matching**
```python
def _validate_brand_match(target_brand: str, extracted_brand: str) -> Tuple[bool, str]:
    if not target_brand and not extracted_brand:
        return True, "both_empty"
    if not target_brand or not extracted_brand:
        return True, "one_empty_allowed"

    target_lower = target_brand.lower().strip()
    extracted_lower = extracted_brand.lower().strip()

    if target_lower in extracted_lower or extracted_lower in target_lower:
        return True, "brand_overlap"

    return False, f"brand_mismatch: target='{target_brand}', extracted='{extracted_brand}'"
```

**Level 2: Product Type Keywords**
```python
MUTUALLY_EXCLUSIVE_KEYWORDS = [
    ({"bourbon"}, {"rye", "corn whiskey"}),
    ({"single malt"}, {"blended", "blend"}),
    ({"scotch"}, {"irish", "japanese", "american"}),
    ({"vintage"}, {"lbv", "late bottled vintage"}),
    ({"tawny"}, {"ruby"}),
]

def _validate_product_type_keywords(target_data: Dict, extracted_data: Dict) -> Tuple[bool, str]:
    target_text = _build_keyword_text(target_data)
    extracted_text = _build_keyword_text(extracted_data)

    for group_a, group_b in MUTUALLY_EXCLUSIVE_KEYWORDS:
        target_has_a = any(kw in target_text for kw in group_a)
        extracted_has_b = any(kw in extracted_text for kw in group_b)

        if target_has_a and extracted_has_b:
            return False, f"product_type_mismatch: target has {group_a}, extracted has {group_b}"

    return True, "keywords_compatible"
```

**Level 3: Name Token Overlap**
```python
STOPWORDS = {"the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for"}
MIN_TOKEN_LENGTH = 3
MIN_OVERLAP_RATIO = 0.30

def _validate_name_overlap(target_name: str, extracted_name: str) -> Tuple[bool, str]:
    target_tokens = _tokenize(target_name)
    extracted_tokens = _tokenize(extracted_name)

    if not target_tokens or not extracted_tokens:
        return True, "insufficient_tokens"

    overlap = target_tokens.intersection(extracted_tokens)
    overlap_ratio = len(overlap) / max(len(target_tokens), len(extracted_tokens))

    if overlap_ratio >= MIN_OVERLAP_RATIO:
        return True, f"name_overlap_{overlap_ratio:.2f}"

    return False, f"name_mismatch: overlap={overlap_ratio:.2f}, tokens={overlap}"
```

### 5.3 Category-Specific Requirements (FEAT-003)

**Reference:** COMP-LEARN-003

Already implemented in `quality_gate_v3.py`. Ensure integration in discovery flow.

### 5.4 Type Normalization (FEAT-004)

**Reference:** COMP-LEARN-005

Already implemented in VPS `extractor_v2.py`. Ensure AI service is called correctly.

### 5.5 Field Derivation (FEAT-005)

**Reference:** COMP-LEARN-006

Already implemented in VPS `extractor_v2.py`. Ensure AI service is called correctly.

### 5.6 Source Tracking Enhancement (FEAT-006)

**Reference:** COMP-LEARN-007

#### 5.6.1 Enhanced DiscoveryResult

```python
@dataclass
class DiscoveryResultV3:
    success: bool
    product_data: Dict[str, Any]
    quality_status: str
    sources_searched: List[str]       # All URLs attempted
    sources_used: List[str]           # URLs that provided data
    sources_rejected: List[Dict]      # URLs rejected with reasons
    field_provenance: Dict[str, str]  # field_name → source_url
    enrichment_steps_completed: int   # 0-2 (producer page, review sites)
    status_progression: List[str]     # ["skeleton", "partial", "baseline"]
```

### 5.7 Duplicate Detection (FEAT-007)

#### 5.7.1 URL-Based Deduplication
```python
def _is_duplicate_url(url: str) -> bool:
    canonical_url = _canonicalize_url(url)
    return CrawledSource.objects.filter(url=canonical_url).exists()
```

#### 5.7.2 Content-Based Deduplication
```python
def _is_duplicate_content(content: str) -> bool:
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return CrawledSource.objects.filter(content_hash=content_hash).exists()
```

#### 5.7.3 Product-Based Deduplication
```python
def _is_duplicate_product(name: str, brand: str) -> Optional[UUID]:
    # Fuzzy match on name + exact match on brand
    return DiscoveredProduct.objects.filter(
        brand__iexact=brand,
        name__icontains=name.split()[0]  # First word match
    ).first()
```

---

## 6. Data Models

### 6.1 DiscoverySessionV3

```python
@dataclass
class DiscoverySessionV3:
    search_term: str
    product_type: str
    started_at: datetime

    # Tracking
    urls_searched: List[str] = field(default_factory=list)
    urls_fetched: List[str] = field(default_factory=list)
    urls_extracted: List[str] = field(default_factory=list)
    urls_rejected: List[Dict] = field(default_factory=list)

    # Products
    products_discovered: List[Dict] = field(default_factory=list)
    products_enriched: List[Dict] = field(default_factory=list)

    # Limits
    max_urls: int = 10
    max_products: int = 20
    max_time_seconds: float = 300.0
```

### 6.2 EnrichmentSessionV3

```python
@dataclass
class EnrichmentSessionV3:
    product_id: UUID
    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any]
    field_confidences: Dict[str, float]

    # 2-Step Tracking
    step_1_completed: bool = False  # Producer page search
    step_2_completed: bool = False  # Review site enrichment

    # Source Tracking
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict] = field(default_factory=list)

    # Status Tracking
    status_before: str = ""
    status_after: str = ""
    status_progression: List[str] = field(default_factory=list)

    # Fields
    fields_enriched: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Limits
    searches_performed: int = 0
    max_searches: int = 3
    max_sources: int = 5
    max_time_seconds: float = 120.0
    start_time: float = 0.0
```

---

## 7. API Contracts

### 7.1 DiscoveryOrchestratorV3

```python
class DiscoveryOrchestratorV3:
    async def discover_products(
        self,
        search_term: str,
        product_type: str,
        max_results: int = 10,
        save_to_db: bool = True,
    ) -> DiscoveryResultV3:
        """
        Execute full discovery pipeline for a search term.

        Args:
            search_term: Search query string
            product_type: Target product type (whiskey, port_wine)
            max_results: Maximum products to discover
            save_to_db: Whether to persist results

        Returns:
            DiscoveryResultV3 with products and tracking data
        """
        pass

    async def enrich_product(
        self,
        product_data: Dict[str, Any],
        product_type: str,
    ) -> EnrichmentResultV3:
        """
        Execute 2-step enrichment pipeline for a product.

        Step 1: Search for official producer/brand page
        Step 2: Search review sites (if still incomplete)

        Args:
            product_data: Initial product data (skeleton from listicle)
            product_type: Product type for schema selection

        Returns:
            EnrichmentResultV3 with enriched data and tracking
        """
        pass
```

### 7.2 ProductMatchValidator

```python
class ProductMatchValidator:
    def validate(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Validate that extracted data matches target product.

        Args:
            target_data: Original product data
            extracted_data: Data extracted from new source

        Returns:
            Tuple of (is_match: bool, reason: str)
        """
        pass
```

---

## 8. Quality Gates

### 8.1 Discovery Quality Gates

| Gate | Condition | Action |
|------|-----------|--------|
| DQ-001 | Extraction confidence < 0.3 | Reject product |
| DQ-002 | No name extracted | Reject product |
| DQ-003 | Name confidence < 0.5 | Flag for review |
| DQ-004 | Duplicate URL | Skip extraction |
| DQ-005 | Duplicate content hash | Skip extraction |

### 8.2 Enrichment Quality Gates

| Gate | Condition | Action |
|------|-----------|--------|
| EQ-001 | Product match fails | Reject source, log reason |
| EQ-002 | New confidence < existing | Keep existing value |
| EQ-003 | Status = COMPLETE | Stop enrichment |
| EQ-004 | Max searches reached | Stop enrichment |
| EQ-005 | Max time exceeded | Stop enrichment |

---

## 9. Testing Strategy

### 9.1 TDD Approach

All features must be implemented using Test-Driven Development:

1. **Write failing test first** - Define expected behavior
2. **Implement minimum code** - Make test pass
3. **Refactor** - Clean up while keeping tests green
4. **Document** - Update spec with implementation notes

### 9.2 Test Categories

#### 9.2.1 Unit Tests
- `ProductMatchValidator` - All validation levels
- `ConfidenceBasedMerger` - Merge logic
- `URLValidator` - URL filtering
- `DuplicateDetector` - Deduplication logic

#### 9.2.2 Integration Tests
- 2-step enrichment pipeline flow (producer → review sites)
- QualityGateV3 integration
- Source tracking persistence
- AI service integration

#### 9.2.3 E2E Tests
- Full discovery flow (search → extract → enrich → persist)
- Real URLs, real AI service
- Status progression verification
- Source audit trail verification

### 9.3 Test Data

Use real URLs from `tests/e2e/utils/real_urls.py`:
- Whiskey review sites
- Port wine retailers
- Competition pages
- Producer websites

---

## 10. Success Criteria

### 10.1 Functional Criteria

| ID | Criterion | Measurement |
|----|-----------|-------------|
| SC-001 | 2-step enrichment pipeline operational | Both steps execute correctly |
| SC-002 | Product match validation prevents cross-contamination | 0 wrong-product enrichments |
| SC-003 | Category exemptions work correctly | Blends reach BASELINE without region/cask |
| SC-004 | Confidence-based merging works | Higher confidence always wins |
| SC-005 | Source tracking complete | All sources logged with reasons |

### 10.2 Quality Criteria

| ID | Criterion | Target |
|----|-----------|--------|
| QC-001 | Products reaching BASELINE | >= 70% |
| QC-002 | Products reaching COMPLETE | >= 40% |
| QC-003 | Enrichment success rate | >= 80% |
| QC-004 | False positive rate (wrong product) | < 1% |
| QC-005 | E2E test pass rate | 100% |

### 10.3 Performance Criteria

| ID | Criterion | Target |
|----|-----------|--------|
| PC-001 | Single product enrichment time | < 60s |
| PC-002 | Search to first product time | < 30s |
| PC-003 | API calls per product | < 5 SerpAPI, < 3 AI |

---

## Appendix A: File References

| Component | File Path |
|-----------|-----------|
| Discovery Orchestrator V2 | `crawler/services/discovery_orchestrator_v2.py` |
| Enrichment Orchestrator V2 | `crawler/services/enrichment_orchestrator_v2.py` |
| Quality Gate V3 | `crawler/services/quality_gate_v3.py` |
| AI Client V2 | `crawler/services/ai_client_v2.py` |
| Source Tracker | `crawler/services/source_tracker.py` |
| Competition Flow Test | `tests/e2e/flows/test_iwsc_flow.py` |
| Generic Search Test | `tests/e2e/flows/test_generic_search_discovery.py` |

## Appendix B: Related Documents

- `specs/V1_TO_V2_MIGRATION_TASKS.md` - V2 migration status
- `specs/UNIFIED_PRODUCT_SAVE_REFACTORING.md` - Save pipeline spec
- `E2E_DATA_QUALITY_ANALYSIS.md` - Quality analysis results
