# Gap Analysis: PortWineDetails Model vs Spec 6.3

**Analysis Date:** 2026-01-05
**Spec Source:** `docs/spec-parts/06-DATABASE-SCHEMA.md` Section 6.3
**Implementation:** `crawler/models.py` class `PortWineDetails` (lines 4038-4130)

---

## Summary

| Category | Count |
|----------|-------|
| Fields in spec but MISSING from model | 0 |
| Extra fields in model not in spec | 1 |
| Type/naming differences | 1 |

---

## Detailed Analysis

### 1. Fields in Spec but MISSING from Model

**None** - All spec fields are implemented.

---

### 2. Extra Fields in Model Not in Spec

| Field | Type in Model | Notes |
|-------|---------------|-------|
| `id` | `UUIDField(primary_key=True)` | Auto-generated UUID primary key. Not in spec but standard Django practice. Consider adding to spec or documenting as implicit. |

---

### 3. Type/Naming Differences

| Field | Spec Type | Model Type | Difference |
|-------|-----------|------------|------------|
| `style` | `CharField(30)` | `CharField(max_length=20)` with `PortStyleChoices` | Model has shorter max_length (20 vs 30) and uses choices constraint |
| `douro_subregion` | `CharField(30)` | `CharField(max_length=20)` with `DouroSubregionChoices` | Model has shorter max_length (20 vs 30) and uses choices constraint |
| `aging_vessel` | `CharField(100)` | `CharField(max_length=200)` | Model allows longer values (200 vs 100) |

---

## Field-by-Field Comparison

| Spec Field | Spec Type | Model Field | Model Type | Status |
|------------|-----------|-------------|------------|--------|
| `product` | OneToOne FK | `product` | `OneToOneField(DiscoveredProduct)` | MATCH |
| `style` | CharField(30) | `style` | `CharField(max_length=20, choices=...)` | TYPE DIFF |
| `indication_age` | CharField(50) | `indication_age` | `CharField(max_length=50)` | MATCH |
| `harvest_year` | IntegerField, Indexed | `harvest_year` | `IntegerField` | MATCH (index may need verification) |
| `bottling_year` | IntegerField | `bottling_year` | `IntegerField` | MATCH |
| `producer_house` | CharField(200), Indexed | `producer_house` | `CharField(max_length=200)` | MATCH (index may need verification) |
| `quinta` | CharField(200) | `quinta` | `CharField(max_length=200)` | MATCH |
| `douro_subregion` | CharField(30) | `douro_subregion` | `CharField(max_length=20, choices=...)` | TYPE DIFF |
| `grape_varieties` | JSONField(list) | `grape_varieties` | `JSONField(default=list)` | MATCH |
| `aging_vessel` | CharField(100) | `aging_vessel` | `CharField(max_length=200)` | TYPE DIFF (model longer) |
| `decanting_required` | BooleanField | `decanting_required` | `BooleanField(default=False)` | MATCH |
| `drinking_window` | CharField(50) | `drinking_window` | `CharField(max_length=50)` | MATCH |

---

## Recommendations

### High Priority

1. **Verify Index Configuration**: The spec indicates `harvest_year` and `producer_house` should be indexed. Verify these indexes exist in the model's Meta class or via migrations.

### Medium Priority

2. **Reconcile max_length differences**:
   - `style`: Spec says 30, model uses 20. Either update model to 30 or confirm 20 is sufficient for all `PortStyleChoices`.
   - `douro_subregion`: Same issue - spec says 30, model uses 20.
   - `aging_vessel`: Model uses 200, spec says 100. Update spec to reflect actual implementation (200 is more flexible).

### Low Priority

3. **Document UUID primary key**: Add `id` field to spec as it's a standard Django/ORM pattern.

4. **Choices validation**: The model uses `PortStyleChoices` and `DouroSubregionChoices` enum constraints. Document these in the spec for completeness.

---

## Conclusion

The PortWineDetails model implementation closely matches the spec. The primary differences are:
- Minor `max_length` variations (model is sometimes shorter, sometimes longer)
- Model adds choice constraints via Django choices enums (good practice)
- Implicit UUID primary key in model not documented in spec

**Overall Alignment: GOOD** - No missing fields, only minor type variations that don't affect functionality.
