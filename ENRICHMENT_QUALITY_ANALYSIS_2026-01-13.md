# Enrichment Quality Analysis - IWSC Competition Flow

**Date:** 2026-01-13
**Analyst:** Claude
**Purpose:** Compare morning enrichment results with evening test results and identify quality regressions

---

## Files Compared

| File | Time | Source |
|------|------|--------|
| `enriched_products_2026-01-13_110104.json` | 11:01 AM | Morning run (high quality) |
| `iwsc_competition_flow_2026-01-13_222840.json` | 10:28 PM | Evening test run (after consolidation) |

---

## Summary of Findings

### Critical Bug Identified

**EnrichmentOrchestratorV3 uses QualityGateV2 instead of V3 for status assessment**

Location: `crawler/services/enrichment_orchestrator_v3.py`

The `_assess_status()` method is inherited from V2 and calls `self._get_quality_gate()` which:
1. Checks `if self.quality_gate is None` - but V3 stores its gate in `_quality_gate_v3`
2. Creates `get_quality_gate_v2()` instead of V3

**Result:**
- Enrichment reports `status_after: baseline` (from QualityGateV2)
- Post-enrichment test assessment shows `status: skeleton` (from QualityGateV3)
- This mismatch causes confusion in status reporting

---

## Detailed Comparison

### Morning Results (11:01 AM) - HIGH QUALITY

**Product 1: SMWS 1.292 Rhythms Of The Soul**
```
Fields Enriched: 16
ABV: 59.1
Volume: 700ml
Tasting Notes: RICH
- nose_description: "Delicious burnt caramel and hints of violets..."
- palate_description: "The palate bursts with anise, spearmint, kumquat..."
- finish_description: "A delightful finish lingers with honey and spice"
- primary_aromas: ["burnt caramel", "violets"]
- palate_flavors: ["anise", "spearmint", "kumquat", "shortbread", ...]
- primary_cask: ["ex-Bourbon", "rum cask", "Cognac"]
Sources Used: 4 successful extractions
```

**Product 2: GlenAllachie 10 YO Batch 12**
```
Fields Enriched: 21
ABV: 59.7
Volume: 700ml
Price: £74.99 GBP
Distillery: The GlenAllachie
Batch Number: Batch 12
Tasting Notes: EXTREMELY RICH
- nose_description: 150+ words of detailed tasting notes
- primary_aromas: 16 distinct aromas identified
- palate_flavors: 13 distinct flavors
- finish_flavors: 8 distinct notes
- color_description: "deep chestnut hue"
- images: Product image URL captured
Sources Used: 6 successful extractions
```

**Product 3: Ballantine's 10 YO**
```
Fields Enriched: 16
ABV: 40.0
Volume: 750ml
Tasting Notes: RICH
- Detailed nose, palate, finish descriptions
- 18 primary aromas, 20 palate flavors, 17 finish flavors
- peated: false, peat_level: "unpeated"
Sources Used: 4 successful extractions
Sources Rejected: 1 (brand mismatch detection working)
```

### Evening Results (10:28 PM) - DEGRADED

**Product 1: SMWS 1.292**
```
Status Reported by Enrichment: skeleton -> baseline
Status by QualityGateV3: skeleton (12% completeness)
Fields Enriched (reported): 15
Sources Used: 2
Searches Performed: 3
```

**Product 2: GlenAllachie 10 YO**
```
Status Reported by Enrichment: skeleton -> baseline
Status by QualityGateV3: skeleton (21% completeness)
Fields Enriched (reported): 24
Sources Used: 3
Searches Performed: 3
```

**Product 3: Ballantine's 10 YO**
```
Status Reported by Enrichment: skeleton -> baseline
Status by QualityGateV3: skeleton (21% completeness)
Fields Enriched (reported): 25
Sources Used: 3
Searches Performed: 3
```

---

## Key Differences

### 1. Output Format Difference
- Morning: `enriched_products_*.json` contains final enriched `product_data`
- Evening: `iwsc_competition_flow_*.json` test recorder format - `products` array only shows initial extraction, not enriched data

**Impact:** Cannot directly compare final product data from evening run

### 2. ECP Calculation
- Morning: `ecp_total: 0.0` for all products (ECP not calculated or field groups missing)
- Evening: Same - `ecp_total: 0.0` or not calculated

**Impact:** COMPLETE status (90% ECP) is never achievable if ECP calculation is broken

### 3. QualityGate Version Mismatch
- Morning: Unknown which QualityGate was used for status_after
- Evening: EnrichmentOrchestratorV3 uses V2's `_assess_status()` -> QualityGateV2
- Evening Test: Uses QualityGateV3 for verification

**Impact:** Inconsistent status reporting between enrichment and verification

### 4. HTTP 403 Errors
Evening run shows many 403 errors:
- whiskybase.com: 403
- reddit.com: 403
- smws.com: 403
- ballantines.com: 403

**Impact:** Fewer sources successfully fetched = less enrichment data

### 5. Fixture Loading Warning
```
WARNING: Could not load whiskey_pipeline_v3.json:
Error deserializing object: string indices must be integers, not 'str'
```

**Impact:** V3 pipeline config not loaded, may affect field definitions

---

## Root Causes

### Bug 1: QualityGate Version in V3 Orchestrator
**File:** `crawler/services/enrichment_orchestrator_v3.py`

```python
class EnrichmentOrchestratorV3(EnrichmentOrchestratorV2):
    def __init__(self, ...):
        # Does NOT call super().__init__()
        self._quality_gate_v3 = quality_gate  # Stored here

    # MISSING: Override of _get_quality_gate()
    # Inherited from V2:
    # def _get_quality_gate(self):
    #     if self.quality_gate is None:  # This attr doesn't exist in V3!
    #         self.quality_gate = get_quality_gate_v2()  # Creates V2!
    #     return self.quality_gate
```

### Bug 2: ECP Not Calculated
ECP calculation requires FieldGroup definitions in database. If `whiskey_pipeline_v3.json` fixture fails to load, no field groups exist -> ECP always 0.

### Bug 3: HTTP 403 Blocking
More websites blocking bot traffic in evening run, reducing enrichment quality.

---

## Recommendations

### CRITICAL - Must Fix Before Production

1. **Override `_get_quality_gate()` in EnrichmentOrchestratorV3**
   ```python
   def _get_quality_gate(self) -> QualityGateV3:
       """Override V2's method to return V3 quality gate."""
       if self._quality_gate_v3 is None:
           self._quality_gate_v3 = get_quality_gate_v3()
       return self._quality_gate_v3
   ```

2. **Fix whiskey_pipeline_v3.json fixture**
   - Investigate the deserialization error
   - Ensure FieldGroup definitions load correctly
   - Verify ECP calculation works with loaded field groups

### HIGH PRIORITY

3. **Update test output format**
   - Evening test should export enriched product data in same format as morning
   - Add `enriched_products_*.json` export to `test_iwsc_flow.py`

4. **Add integration test for QualityGate version**
   - Verify EnrichmentOrchestratorV3 uses QualityGateV3
   - Test status consistency between enrichment and verification

### MEDIUM PRIORITY

5. **Investigate 403 errors**
   - Some may be temporary (rate limiting)
   - Consider adding retry with delay
   - Review user-agent and request headers

---

## Verification Steps After Fixes

1. Run `test_iwsc_flow.py` and verify:
   - `status_after` from enrichment matches post-enrichment QualityGateV3 assessment
   - ECP is calculated (non-zero for enriched products)
   - Enriched product data is exported

2. Compare enrichment quality metrics:
   - Fields enriched count
   - Sources successfully used
   - Final status level achieved

---

## Files to Modify

| File | Change Required |
|------|-----------------|
| `crawler/services/enrichment_orchestrator_v3.py` | Add `_get_quality_gate()` override |
| `crawler/fixtures/whiskey_pipeline_v3.json` | Fix deserialization issue |
| `tests/e2e/flows/test_iwsc_flow.py` | Add enriched product export |

---

## Approval Required

**DO NOT implement any changes without user approval.**

This analysis identifies the bugs and recommends fixes. Please review and approve before proceeding.
