# Gap Analysis: WhiskeyDetails Model (Spec 6.2 vs Implementation)

## Summary

This document analyzes the gap between the WhiskeyDetails specification in section 6.2 of the database schema spec and the current implementation in `crawler/models.py`.

---

## 1. Fields in Spec but MISSING from Model

| Spec Field | Type | Notes |
|------------|------|-------|
| `peat_ppm` | IntegerField | Phenol PPM measurement |
| `natural_color` | BooleanField | No E150a (spec uses positive naming) |
| `non_chill_filtered` | BooleanField | NCF (spec uses positive naming) |

**Count: 3 missing fields**

---

## 2. Extra Fields in Model NOT in Spec

| Model Field | Type | Notes |
|-------------|------|-------|
| `id` | UUIDField | Primary key (implicit in Django, not in spec) |
| `whiskey_country` | CharField(100) | Country of origin (duplicates DiscoveredProduct.country?) |
| `whiskey_region` | CharField(100) | Region (duplicates DiscoveredProduct.region?) |
| `cask_type` | CharField(200) | Primary cask type used |
| `cask_finish` | CharField(200) | Finishing cask if any |
| `chill_filtered` | BooleanField | Inverse of spec's `non_chill_filtered` |
| `color_added` | BooleanField | Inverse of spec's `natural_color` |

**Count: 7 extra fields (2 are semantic inversions, 2 are potential duplicates)**

---

## 3. Type/Naming Differences

| Spec Field | Spec Type | Model Field | Model Type | Issue |
|------------|-----------|-------------|------------|-------|
| `non_chill_filtered` | BooleanField | `chill_filtered` | BooleanField | **Inverted semantics**: Spec uses positive (`non_chill_filtered=True` means NCF), model uses negative (`chill_filtered=True` means filtered). Logic must be inverted when mapping. |
| `natural_color` | BooleanField | `color_added` | BooleanField | **Inverted semantics**: Spec uses positive (`natural_color=True` means no E150a), model uses negative (`color_added=True` means E150a added). Logic must be inverted when mapping. |

---

## 4. Field-by-Field Comparison

### Fields Present in Both (Matching)

| Field | Spec Type | Model Type | Status |
|-------|-----------|------------|--------|
| `product` | OneToOne FK | OneToOneField | OK |
| `whiskey_type` | CharField(30) | CharField(30) | OK |
| `distillery` | CharField(200) | CharField(200) | OK |
| `mash_bill` | CharField(200) | CharField(200) | OK |
| `cask_strength` | BooleanField | BooleanField | OK |
| `single_cask` | BooleanField | BooleanField | OK |
| `cask_number` | CharField(50) | CharField(50) | OK |
| `vintage_year` | IntegerField | IntegerField | OK |
| `bottling_year` | IntegerField | IntegerField | OK |
| `batch_number` | CharField(50) | CharField(50) | OK |
| `peated` | BooleanField | BooleanField | OK |
| `peat_level` | CharField(20) | CharField(20) | OK |

**Count: 12 matching fields**

---

## 5. Recommendations

### High Priority

1. **Add `peat_ppm` field** - Missing data point for detailed peat information
   ```python
   peat_ppm = models.IntegerField(
       blank=True,
       null=True,
       help_text="Phenol PPM measurement",
   )
   ```

### Medium Priority

2. **Semantic alignment decision** - Choose ONE approach for boolean fields:
   - **Option A**: Keep model as-is (`chill_filtered`, `color_added`) and document the inversion
   - **Option B**: Change model to match spec (`non_chill_filtered`, `natural_color`) for consistency
   - **Recommendation**: Option B for spec compliance, but requires migration and code updates

### Low Priority (Review Needed)

3. **Review duplicate fields** - `whiskey_country` and `whiskey_region` may duplicate `DiscoveredProduct.country` and `DiscoveredProduct.region`. Determine if whiskey-specific country/region is needed (e.g., for blends from multiple regions).

4. **Review cask fields** - `cask_type` and `cask_finish` in model vs `primary_cask`, `finishing_cask`, `wood_type`, `cask_treatment` in `DiscoveredProduct` spec (section 6.1). May need alignment or clarification of where cask info should live.

---

## 6. Compliance Score

| Metric | Count |
|--------|-------|
| Spec fields total | 15 |
| Matching fields | 12 |
| Missing fields | 3 |
| Extra fields (model-only) | 7 |
| Semantic inversions | 2 |

**Compliance: 80% (12/15 spec fields present)**

---

## 7. Source Files

- **Spec**: `docs/spec-parts/06-DATABASE-SCHEMA.md` (Section 6.2, lines 108-127)
- **Implementation**: `crawler/models.py` (class WhiskeyDetails, lines 3909-4035)
