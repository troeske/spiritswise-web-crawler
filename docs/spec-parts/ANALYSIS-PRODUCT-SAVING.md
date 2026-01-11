# Analysis: Product Saving to DiscoveredProduct

## Executive Summary

The codebase has a **well-designed unified product saving system** through `save_discovered_product()` in `crawler/services/product_saver.py`. This function properly saves data to **individual columns** and creates related records (awards, ratings, images) in separate tables.

However, there are **legacy JSON blob fields** that are still being populated during saves, creating a **dual-write pattern** that should be deprecated.

---

## Save Paths Identified

### 1. Primary Save Path: `save_discovered_product()` (GOOD)

**Location:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\services\product_saver.py`

**Called By:**
- `ContentProcessor._save_product()` (content_processor.py line 1778)
- `DiscoveryOrchestrator._save_product()` (discovery_orchestrator.py line 917)
- `CompetitionOrchestrator.run_with_collectors()` (competition_orchestrator.py line 307)
- `SkeletonProductManager.create_skeleton_product()` (skeleton_manager.py line 181)
- `SkeletonProductManager.mark_skeleton_enriched()` (skeleton_manager.py line 468)

**Behavior - GOOD:**
- Extracts individual fields using `FIELD_MAPPING` (lines 238-276)
- Populates tasting profile fields: `nose_description`, `palate_flavors`, `primary_aromas`, etc.
- Creates `WhiskeyDetails` / `PortWineDetails` records for spirit-specific fields
- Creates `ProductAward`, `ProductRating`, `ProductImage` records
- Creates `ProductSource` and `ProductFieldSource` provenance records
- Calculates `completeness_score` and updates `status`

**Behavior - BAD (Dual-Write):**
```python
# Lines 1742-1743 in product_saver.py
"extracted_data": normalized_data,
"enriched_data": {},
```
The function still writes `extracted_data` and `enriched_data` JSON blobs.

---

### 2. ContentProcessor Flow (GOOD - Uses Unified Save)

**Location:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\services\content_processor.py`

**Flow:**
1. `process()` calls AI Enhancement Service
2. `_save_product()` delegates to `save_discovered_product()`
3. After save, updates `enriched_data` JSON for merging (lines 1803-1813)

**Issue:** After unified save, it still merges data into `enriched_data` JSON:
```python
# Lines 1803-1813
if not save_result.created:
    enriched_data = product.enriched_data or {}
    enriched_data = {
        **enriched_data,
        **result.enrichment,
        "additional_sources": enriched_data.get("additional_sources", []) + [url],
    }
    product.enriched_data = enriched_data
```

---

### 3. DiscoveryOrchestrator Flow (GOOD - Uses Unified Save)

**Location:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\services\discovery_orchestrator.py`

**Flow:**
1. `_process_search_result()` or `_process_list_page()` finds products
2. `_extract_and_save_product()` or `_enrich_product_from_list()` calls `_save_product()`
3. `_save_product()` (lines 876-938) calls `save_discovered_product()`

**Pre-processing - GOOD:**
- `_normalize_data_for_save()` (lines 940-1054) converts JSON blobs to individual fields:
  - `taste_profile` JSON -> `nose_description`, `initial_taste`, `final_notes`, `palate_flavors`
  - `tasting_notes` JSON -> same individual fields
  - Single `rating`/`score` -> `ratings` list for ProductRating records

---

### 4. CompetitionOrchestrator Flow (GOOD - Uses Unified Save)

**Location:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\services\competition_orchestrator.py`

**Flow:**
1. `run_with_collectors()` uses collectors + AI extractors
2. Adds award data to extracted_data
3. Calls `save_discovered_product()` directly (line 307)

**Proper Award Handling:**
```python
# Lines 303-313
extracted['medal'] = url_info.medal_hint
extracted['competition'] = source.upper()
extracted['year'] = year

save_result = save_discovered_product(
    extracted_data=extracted,
    ...
)
```

---

### 5. SkeletonProductManager Flow (DEPRECATED - Uses Unified Save)

**Location:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\crawler\discovery\competitions\skeleton_manager.py`

**Status:** Module is marked DEPRECATED (line 5). Recommends using `save_discovered_product()` directly.

**Flow:**
1. `create_skeleton_product()` builds extracted_data dict
2. Calls `save_discovered_product()` (line 181)
3. Overrides status to `SKELETON` after save

**Issue - Status Override:**
```python
# Lines 193-196
product.status = DiscoveredProductStatus.SKELETON
product.discovery_source = DiscoverySource.COMPETITION
product.fingerprint = fingerprint
```
This could conflict with the status calculated by `save_discovered_product()`.

---

## JSON Blob Fields Analysis

### Fields in DiscoveredProduct Model

| Field | Type | Status | Recommendation |
|-------|------|--------|----------------|
| `extracted_data` | JSONField | ACTIVE (dual-write) | Deprecate - move to individual columns |
| `enriched_data` | JSONField | ACTIVE (dual-write) | Deprecate - use ProductSource records |
| `taste_profile` | JSONField | ACTIVE | Deprecate - use individual tasting columns |
| `awards` | JSONField | LEGACY | Already migrated to ProductAward table |
| `images` | JSONField | LEGACY | Already migrated to ProductImage table |
| `ratings` | JSONField | LEGACY | Already migrated to ProductRating table |
| `price_history` | JSONField | ACTIVE | Consider ProductPrice table |
| `press_mentions` | JSONField | ACTIVE | Consider ArticleMention table |
| `discovery_sources` | JSONField | ACTIVE | OK - list of strings |
| `verified_fields` | JSONField | ACTIVE | OK - list of field names |
| `conflict_details` | JSONField | ACTIVE | OK - conflict metadata |

### Individual Tasting Columns (GOOD)

The model has proper individual columns for tasting profile:

**Appearance:**
- `color_description`, `color_intensity`, `clarity`, `viscosity`

**Nose:**
- `nose_description`, `primary_aromas`, `primary_intensity`, `secondary_aromas`, `aroma_evolution`

**Palate:**
- `palate_flavors`, `initial_taste`, `mid_palate_evolution`, `flavor_intensity`, `complexity`, `mouthfeel`, `palate_description`

**Finish:**
- `finish_length`, `warmth`, `dryness`, `finish_flavors`, `finish_evolution`, `final_notes`, `finish_description`

---

## What Needs to Change

### High Priority

1. **Remove dual-write to `extracted_data` JSON**
   - File: `product_saver.py` lines 1742
   - Change: Stop populating `extracted_data` on new saves
   - Impact: May break code reading from `extracted_data` instead of individual columns

2. **Remove dual-write to `enriched_data` JSON**
   - File: `product_saver.py` line 1743
   - File: `content_processor.py` lines 1803-1813
   - Change: Stop populating `enriched_data`, use ProductSource records instead

3. **Stop using `taste_profile` JSON**
   - File: `discovery_orchestrator.py` `_normalize_data_for_save()` already converts
   - Ensure NO code writes to `taste_profile` JSON directly
   - Search for any code using `product.taste_profile =` or `update_taste_profile()`

### Medium Priority

4. **Deprecate skeleton status override**
   - File: `skeleton_manager.py` lines 193-196
   - Let `save_discovered_product()` handle status consistently

5. **Audit all `product.save()` calls**
   - Ensure individual column updates, not JSON blob updates

### Low Priority

6. **Migrate remaining JSON fields to tables**
   - `price_history` -> ProductPrice table
   - `press_mentions` -> ArticleMention table

---

## Summary Table: Save Paths

| Save Path | Location | Uses Individual Columns | Uses JSON Blobs | Status |
|-----------|----------|-------------------------|-----------------|--------|
| `save_discovered_product()` | product_saver.py | YES (tasting, brand, etc.) | YES (extracted_data, enriched_data) | PARTIAL - needs cleanup |
| `ContentProcessor._save_product()` | content_processor.py | YES (via unified save) | YES (enriched_data merge) | PARTIAL - needs cleanup |
| `DiscoveryOrchestrator._save_product()` | discovery_orchestrator.py | YES (via unified save) | NO (normalizes first) | GOOD |
| `CompetitionOrchestrator.run_with_collectors()` | competition_orchestrator.py | YES (via unified save) | MINIMAL | GOOD |
| `SkeletonProductManager.create_skeleton_product()` | skeleton_manager.py | YES (via unified save) | MINIMAL | DEPRECATED |

---

## Tasting Profile Field Population

### Fields Populated by `save_discovered_product()` (GOOD)

From `FIELD_MAPPING` in product_saver.py:

```python
# Nose/Aroma (lines 255-259)
"nose_description": ("nose_description", _safe_str),
"primary_aromas": ("primary_aromas", _safe_list),
"primary_intensity": ("primary_intensity", _safe_int),
"secondary_aromas": ("secondary_aromas", _safe_list),
"aroma_evolution": ("aroma_evolution", _safe_str),

# Palate (lines 262-268)
"palate_flavors": ("palate_flavors", _safe_list),
"initial_taste": ("initial_taste", _safe_str),
"mid_palate_evolution": ("mid_palate_evolution", _safe_str),
"flavor_intensity": ("flavor_intensity", _safe_int),
"complexity": ("complexity", _safe_int),
"mouthfeel": ("mouthfeel", _safe_str),

# Finish (lines 271-276)
"finish_length": ("finish_length", _safe_int),
"warmth": ("warmth", _safe_int),
"dryness": ("dryness", _safe_int),
"finish_flavors": ("finish_flavors", _safe_list),
"finish_evolution": ("finish_evolution", _safe_str),
"final_notes": ("final_notes", _safe_str),
```

These fields ARE being properly populated when the AI enhancement returns them.

---

## Conclusion

The architecture is fundamentally sound:
- **Individual columns exist** for all tasting profile fields
- **Unified save function exists** and populates individual columns
- **Related tables exist** (ProductAward, ProductRating, ProductImage)
- **All major save paths** route through `save_discovered_product()`

The main issue is **dual-write to JSON blobs** that should be deprecated:
1. `extracted_data` - still being written
2. `enriched_data` - still being written
3. `taste_profile` - potentially still being written

Recommendation: Create a migration to:
1. Stop dual-write in `save_discovered_product()`
2. Audit all code that reads from JSON blobs
3. Update readers to use individual columns
4. Eventually drop JSON blob fields
