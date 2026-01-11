# Gap Analysis: Database Schema (06-DATABASE-SCHEMA.md)

**Analysis Date:** 2026-01-05
**Spec File:** `docs/spec-parts/06-DATABASE-SCHEMA.md`
**Implementation File:** `crawler/models.py`

---

## Summary

| Category | Count |
|----------|-------|
| Fields in spec but MISSING from model | **2** |
| Fields in model marked DEPRECATED in spec | **3** |
| Type mismatches | **4** |
| Missing indexes | **7** |
| Additional implementation issues | **6** |

---

## 1. Fields in Spec but MISSING from Model

### 1.1 DiscoveredProduct - Missing Fields

| Spec Field | Spec Type | Status | Notes |
|------------|-----------|--------|-------|
| `description` | TextField | **MISSING** | General product description field not present |

### 1.2 WhiskeyDetails - Missing Fields

| Spec Field | Spec Type | Status | Notes |
|------------|-----------|--------|-------|
| `peat_ppm` | IntegerField | **MISSING** | Phenol PPM measurement for peat level |

---

## 2. Fields in Model Marked DEPRECATED in Spec

The spec explicitly marks these fields as **DEPRECATED** with instructions to "migrate data then remove":

| Field | Type | Spec Status | Implementation Status |
|-------|------|-------------|----------------------|
| `extracted_data` | JSONField | **DEPRECATED** | Still exists (line 1357) |
| `enriched_data` | JSONField | **DEPRECATED** | Still exists (line 1358) |
| `taste_profile` | JSONField | **DEPRECATED** | Still exists (line 1387-1391) |

**Migration Required:** The spec states these JSON blob fields should be migrated to individual columns. The individual tasting profile columns exist (color_description, nose_description, etc.), but the deprecated JSON fields are still present and likely still in use.

---

## 3. Type Mismatches

### 3.1 DiscoveredProduct Type Mismatches

| Field | Spec Type | Implementation Type | Issue |
|-------|-----------|---------------------|-------|
| `abv` | DecimalField(4,1) | FloatField | Spec requires DecimalField for precision (line 1313) |
| `extraction_confidence` | DecimalField(3,2) | FloatField | Spec requires DecimalField for 0.00-1.00 precision (line 1359) |
| `age_statement` | CharField(20) | IntegerField | Spec allows "12", "NAS" strings; impl only allows integers (line 1318) |
| `fingerprint` | CharField(64) + **Unique** | CharField(64) + db_index | Spec requires unique constraint; impl only has index (line 1303-1305) |

### 3.2 WhiskeyDetails Type Mismatches

| Field | Spec Type | Implementation Type | Issue |
|-------|-----------|---------------------|-------|
| `natural_color` | BooleanField | `color_added` BooleanField | Naming inversion - spec uses positive `natural_color`, impl uses negative `color_added` (line 4023-4026) |
| `non_chill_filtered` | BooleanField | `chill_filtered` BooleanField | Naming inversion - spec uses positive `non_chill_filtered`, impl uses negative `chill_filtered` (line 4018-4021) |

---

## 4. Missing Indexes

### 4.1 DiscoveredProduct - Missing Indexes per Spec

| Field | Spec Requirement | Implementation Status |
|-------|------------------|----------------------|
| `name` | "Required, indexed" | **NO db_index** - no index defined (line 1308-1312) |
| `brand` | "Indexed" | **NO explicit index** - FK creates implicit index but spec may want compound |
| `abv` | "0-80%, indexed" | **NO db_index** (line 1313-1317) |
| `country` | "Indexed" | **NO db_index** (line 1334-1339) |
| `region` | "Indexed" | **NO db_index** (line 1328-1333) |

### 4.2 WhiskeyDetails - Missing Indexes per Spec

| Field | Spec Requirement | Implementation Status |
|-------|------------------|----------------------|
| `distillery` | "Indexed" | **NO db_index** (line 3944-3948) |

### 4.3 PortWineDetails - Missing Indexes per Spec

| Field | Spec Requirement | Implementation Status |
|-------|------------------|----------------------|
| `harvest_year` | "Indexed" | **NO db_index** (line 4069-4073) |
| `producer_house` | "Indexed" | **NO db_index** (line 4099-4102) |

---

## 5. Additional Issues Found

### 5.1 WhiskeyDetails - Extra Fields Not in Spec

These fields exist in implementation but are NOT in spec:

| Field | Implementation Type | Notes |
|-------|---------------------|-------|
| `whiskey_country` | CharField(100) | Not in spec - country is on DiscoveredProduct |
| `whiskey_region` | CharField(100) | Not in spec - region is on DiscoveredProduct |
| `cask_type` | CharField(200) | Not in spec - use primary_cask on DiscoveredProduct |
| `cask_finish` | CharField(200) | Not in spec - use finishing_cask on DiscoveredProduct |

### 5.2 Clarity/Viscosity Choice Constraints

| Field | Spec Choices | Implementation |
|-------|--------------|----------------|
| `clarity` | crystal_clear, slight_haze, cloudy | CharField(50) - no choices defined |
| `viscosity` | light, medium, full_bodied, syrupy | CharField(50) - no choices defined |
| `mouthfeel` | light_crisp, medium_balanced, full_rich, etc. | CharField(50) - no choices defined |

### 5.3 PortWineDetails - Style Field Max Length

| Field | Spec Type | Implementation Type | Issue |
|-------|-----------|---------------------|-------|
| `style` | CharField(30) | CharField(20) | Max length too short (line 4056-4059) |

---

## 6. Detailed Field-by-Field Comparison

### 6.1 DiscoveredProduct - Identification Fields

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `name` | CharField(500), indexed | CharField(500), blank=True | **MISSING INDEX** |
| `brand` | FK to DiscoveredBrand, indexed | FK to DiscoveredBrand, null=True | OK (implicit FK index) |
| `gtin` | CharField(14), indexed | CharField(14), db_index=True | OK |
| `fingerprint` | CharField(64), unique, indexed | CharField(64), db_index=True | **NOT UNIQUE** |

### 6.2 DiscoveredProduct - Basic Product Info Fields

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `product_type` | CharField(20) | CharField(20) | OK |
| `category` | CharField(100) | CharField(200), null=True | OK (impl more generous) |
| `abv` | DecimalField(4,1), indexed | FloatField | **TYPE MISMATCH, NO INDEX** |
| `volume_ml` | IntegerField | IntegerField | OK |
| `description` | TextField | - | **MISSING** |
| `age_statement` | CharField(20) | IntegerField | **TYPE MISMATCH** |
| `country` | CharField(100), indexed | CharField(100), null=True | **MISSING INDEX** |
| `region` | CharField(100), indexed | CharField(200), null=True | **MISSING INDEX** |
| `bottler` | CharField(100) | CharField(200), null=True | OK (impl more generous) |

### 6.3 DiscoveredProduct - Tasting Profile: Appearance

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `color_description` | TextField | TextField | OK |
| `color_intensity` | IntegerField | IntegerField | OK |
| `clarity` | CharField(20) with choices | CharField(50), no choices | **NO CHOICES** |
| `viscosity` | CharField(20) with choices | CharField(50), no choices | **NO CHOICES** |

### 6.4 DiscoveredProduct - Tasting Profile: Nose

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `nose_description` | TextField | TextField | OK |
| `primary_aromas` | JSONField(list) | JSONField(list) | OK |
| `primary_intensity` | IntegerField | IntegerField | OK |
| `secondary_aromas` | JSONField(list) | JSONField(list) | OK |
| `aroma_evolution` | TextField | TextField | OK |

### 6.5 DiscoveredProduct - Tasting Profile: Palate

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `initial_taste` | TextField | TextField | OK |
| `mid_palate_evolution` | TextField | TextField | OK |
| `palate_flavors` | JSONField(list) | JSONField(list) | OK |
| `palate_description` | TextField | TextField | OK |
| `flavor_intensity` | IntegerField | IntegerField | OK |
| `complexity` | IntegerField | IntegerField | OK |
| `mouthfeel` | CharField(30) with choices | CharField(50), no choices | **NO CHOICES** |

### 6.6 DiscoveredProduct - Tasting Profile: Finish

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `finish_length` | IntegerField | IntegerField | OK |
| `warmth` | IntegerField | IntegerField | OK |
| `dryness` | IntegerField | IntegerField | OK |
| `finish_flavors` | JSONField(list) | JSONField(list) | OK |
| `finish_evolution` | TextField | TextField | OK |
| `finish_description` | TextField | TextField | OK |
| `final_notes` | TextField | TextField | OK |

### 6.7 DiscoveredProduct - Tasting Profile: Overall

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `balance` | IntegerField | IntegerField | OK |
| `overall_complexity` | IntegerField | IntegerField | OK |
| `uniqueness` | IntegerField | IntegerField | OK |
| `drinkability` | IntegerField | IntegerField | OK |
| `price_quality_ratio` | IntegerField | IntegerField | OK |
| `experience_level` | CharField(20) | CharField(50), null=True | OK |
| `serving_recommendation` | CharField(20) | CharField(200), null=True | OK (impl more generous) |
| `food_pairings` | TextField | TextField | OK |

### 6.8 DiscoveredProduct - Status & Verification

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `status` | CharField(20) | CharField(20) with choices | OK |
| `completeness_score` | IntegerField | IntegerField | OK |
| `source_count` | IntegerField | IntegerField | OK |
| `verified_fields` | JSONField(list) | JSONField(list) | OK |
| `discovery_source` | CharField(20) | CharField(20) with choices | OK |
| `extraction_confidence` | DecimalField(3,2) | FloatField | **TYPE MISMATCH** |

### 6.9 DiscoveredProduct - Cask Info

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `primary_cask` | JSONField(list) | JSONField(list) | OK |
| `finishing_cask` | JSONField(list) | JSONField(list) | OK |
| `wood_type` | JSONField(list) | JSONField(list) | OK |
| `cask_treatment` | JSONField(list) | JSONField(list) | OK |
| `maturation_notes` | TextField | TextField | OK |

### 6.10 WhiskeyDetails

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `product` | OneToOne FK | OneToOne FK | OK |
| `whiskey_type` | CharField(30) | CharField(30) with choices | OK |
| `distillery` | CharField(200), indexed | CharField(200) | **MISSING INDEX** |
| `mash_bill` | CharField(200) | CharField(200) | OK |
| `cask_strength` | BooleanField | BooleanField | OK |
| `single_cask` | BooleanField | BooleanField | OK |
| `cask_number` | CharField(50) | CharField(50) | OK |
| `vintage_year` | IntegerField | IntegerField | OK |
| `bottling_year` | IntegerField | IntegerField | OK |
| `batch_number` | CharField(50) | CharField(50) | OK |
| `peated` | BooleanField | BooleanField | OK |
| `peat_level` | CharField(20) | CharField(20) with choices | OK |
| `peat_ppm` | IntegerField | - | **MISSING** |
| `natural_color` | BooleanField | `color_added` BooleanField | **NAMING INVERTED** |
| `non_chill_filtered` | BooleanField | `chill_filtered` BooleanField | **NAMING INVERTED** |

### 6.11 PortWineDetails

| Spec Field | Spec Type | Implementation | Match? |
|------------|-----------|----------------|--------|
| `product` | OneToOne FK | OneToOne FK | OK |
| `style` | CharField(30) | CharField(20) with choices | **MAX_LENGTH TOO SHORT** |
| `indication_age` | CharField(50) | CharField(50) | OK |
| `harvest_year` | IntegerField, indexed | IntegerField | **MISSING INDEX** |
| `bottling_year` | IntegerField | IntegerField | OK |
| `producer_house` | CharField(200), indexed | CharField(200) | **MISSING INDEX** |
| `quinta` | CharField(200) | CharField(200) | OK |
| `douro_subregion` | CharField(30) | CharField(20) with choices | OK (impl shorter but has choices) |
| `grape_varieties` | JSONField(list) | JSONField(list) | OK |
| `aging_vessel` | CharField(100) | CharField(200) | OK (impl more generous) |
| `decanting_required` | BooleanField | BooleanField | OK |
| `drinking_window` | CharField(50) | CharField(50) | OK |

---

## 7. Recommended Actions

### Priority 1 - Critical (Data Integrity)

1. **Add `description` field** to DiscoveredProduct (TextField)
2. **Change `abv` type** from FloatField to DecimalField(4,1)
3. **Change `extraction_confidence` type** from FloatField to DecimalField(3,2)
4. **Change `age_statement` type** from IntegerField to CharField(20) to support "NAS"
5. **Add unique constraint** to `fingerprint` field

### Priority 2 - High (Performance)

6. **Add indexes** to:
   - `DiscoveredProduct.name`
   - `DiscoveredProduct.abv`
   - `DiscoveredProduct.country`
   - `DiscoveredProduct.region`
   - `WhiskeyDetails.distillery`
   - `PortWineDetails.harvest_year`
   - `PortWineDetails.producer_house`

### Priority 3 - Medium (Spec Compliance)

7. **Add `peat_ppm` field** to WhiskeyDetails (IntegerField)
8. **Add choices** to clarity, viscosity, mouthfeel fields
9. **Rename inverted booleans** or add aliases:
   - `natural_color` (opposite of `color_added`)
   - `non_chill_filtered` (opposite of `chill_filtered`)
10. **Increase `PortWineDetails.style` max_length** from 20 to 30

### Priority 4 - Low (Cleanup)

11. **Plan migration** for deprecated JSON fields:
    - `extracted_data`
    - `enriched_data`
    - `taste_profile`
12. **Review extra WhiskeyDetails fields** not in spec:
    - `whiskey_country`
    - `whiskey_region`
    - `cask_type`
    - `cask_finish`

---

## 8. Migration Complexity Assessment

| Change | Complexity | Risk | Notes |
|--------|------------|------|-------|
| Add `description` field | Low | Low | Add nullable TextField |
| Change `abv` to DecimalField | Medium | Medium | Requires data conversion |
| Change `extraction_confidence` to DecimalField | Medium | Medium | Requires data conversion |
| Change `age_statement` to CharField | High | High | Must convert integers to strings, handle "NAS" |
| Add unique to `fingerprint` | Medium | High | Must check for duplicates first |
| Add indexes | Low | Low | Just add db_index=True |
| Add `peat_ppm` | Low | Low | Add nullable IntegerField |
| Add choices to fields | Low | Low | Just add choices parameter |
| Deprecate JSON fields | High | High | Requires data migration strategy |

---

*End of Gap Analysis*
