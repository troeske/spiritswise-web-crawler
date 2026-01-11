# Unified Architecture Proposal

> **Source:** Extracted from `FLOW_COMPARISON_ANALYSIS.md` lines 1112-1317

---

## 5. Unified Architecture Proposal

### 5.1 Design Principles

1. **Single Code Path** - All discovery flows converge to one processing pipeline
2. **Uniform Data Format** - Common intermediate representation
3. **Smart Enrichment** - Only enrich what's missing
4. **Clear Status Model** - Status reflects completeness, not origin
5. **Unified Deduplication** - One implementation, used everywhere

### 5.2 Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTRACTION LAYER                                │
│  (Different extractors for different sources - KEEP SPECIALIZED)        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ Competition     │  │ AI List         │  │ AI Single       │         │
│  │ Parser          │  │ Extractor       │  │ Extractor       │         │
│  │ (BeautifulSoup) │  │ (LLM)           │  │ (LLM)           │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           └────────────────────┼────────────────────┘                   │
│                                │                                        │
│                                ▼                                        │
│                    ┌─────────────────────┐                             │
│                    │  ProductCandidate   │  ◄── Uniform intermediate   │
│                    │  (dataclass)        │      format                  │
│                    └─────────────────────┘                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PROCESSING PIPELINE                               │
│  (Single unified pipeline for ALL products)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Step 1: DEDUPLICATION                                          │   │
│  │  • Single implementation                                        │   │
│  │  • Check fingerprint, name, GTIN                                │   │
│  │  • If duplicate → merge data into existing                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Step 2: COMPLETENESS CHECK                                     │   │
│  │  • Calculate completeness score (0-100)                         │   │
│  │  • Based on which fields are populated                          │   │
│  │  • Has name? Has tasting? Has price? Has image?                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Step 3: SMART ENRICHMENT (if needed)                           │   │
│  │  • Only if completeness < threshold                             │   │
│  │  • Only search for MISSING fields                               │   │
│  │  • Strategy A: Direct link available → crawl it                 │   │
│  │  • Strategy B: No link → targeted SerpAPI search                │   │
│  │  • Strategy C: Skip enrichment if sufficient data               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Step 4: SAVE PRODUCT                                           │   │
│  │  • Single save_discovered_product() call                        │   │
│  │  • Creates all related records (awards, ratings, etc.)          │   │
│  │  • Creates provenance records                                   │   │
│  │  • Sets status based on completeness score                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  DiscoveredProduct with:                                               │
│  • status based on completeness (INCOMPLETE/PENDING/COMPLETE)          │
│  • completeness_score (0-100)                                          │
│  • All related records (WhiskeyDetails, ProductAward, etc.)            │
│  • Provenance tracking (which source provided which field)             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 New Status Model

**Replace** SKELETON/PENDING/APPROVED/REJECTED **with**:

| Status | Completeness Score | Requirements |
|--------|-------------------|--------------|
| `INCOMPLETE` | 0-29 | Missing critical data, no palate profile |
| `PARTIAL` | 30-59 | Has basic data but no tasting profile |
| `COMPLETE` | 60-79 | **HAS palate tasting profile** |
| `VERIFIED` | 80-100 | Full tasting + multi-source verified |
| `REJECTED` | N/A | Marked as not a valid product |
| `MERGED` | N/A | Merged into another product |

**CRITICAL:** A product CANNOT reach COMPLETE or VERIFIED without palate tasting data, regardless of score.

**Completeness Score Calculation (Tasting = 40%):**
```python
def calculate_completeness(product: ProductCandidate) -> int:
    score = 0

    # ============================================================
    # IDENTIFICATION (15 points max)
    # ============================================================
    if product.name: score += 10
    if product.brand: score += 5

    # ============================================================
    # BASIC PRODUCT INFO (15 points max)
    # ============================================================
    if product.product_type: score += 5
    if product.abv: score += 5
    if product.description: score += 5

    # ============================================================
    # TASTING PROFILE (40 points max) - CRITICAL
    # ============================================================

    # Palate (20 points) - MANDATORY for COMPLETE
    palate_score = 0
    if product.palate_flavors and len(product.palate_flavors) >= 2:
        palate_score += 10
    if product.palate_description or product.initial_taste:
        palate_score += 5
    if product.mid_palate_evolution:
        palate_score += 3
    if product.mouthfeel:
        palate_score += 2
    score += min(palate_score, 20)

    # Nose (10 points)
    nose_score = 0
    if product.nose_description:
        nose_score += 5
    if product.primary_aromas and len(product.primary_aromas) >= 2:
        nose_score += 5
    score += min(nose_score, 10)

    # Finish (10 points)
    finish_score = 0
    if product.finish_description or product.final_notes:
        finish_score += 5
    if product.finish_flavors and len(product.finish_flavors) >= 2:
        finish_score += 3
    if product.finish_length:
        finish_score += 2
    score += min(finish_score, 10)

    # ============================================================
    # ENRICHMENT DATA (20 points max)
    # ============================================================
    if product.best_price: score += 5
    if product.has_images: score += 5
    if product.has_ratings: score += 5
    if product.has_awards: score += 5

    # ============================================================
    # VERIFICATION BONUS (10 points max)
    # ============================================================
    if product.source_count >= 2: score += 5
    if product.source_count >= 3: score += 5

    return min(score, 100)


def determine_status(product) -> str:
    """
    Determine status based on score AND palate profile.

    KEY RULE: Cannot be COMPLETE/VERIFIED without palate data.
    """
    score = product.completeness_score
    has_palate = bool(
        (product.palate_flavors and len(product.palate_flavors) >= 2) or
        product.palate_description or
        product.initial_taste
    )

    # Cannot be COMPLETE or VERIFIED without palate data
    if not has_palate:
        if score >= 30:
            return "partial"
        return "incomplete"

    # With palate data, status based on score
    if score >= 80:
        return "verified"
    elif score >= 60:
        return "complete"
    elif score >= 30:
        return "partial"
    else:
        return "incomplete"
```

---
