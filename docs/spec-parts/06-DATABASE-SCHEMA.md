# Part 6: Database Schema
*Lines 1318-1460 from FLOW_COMPARISON_ANALYSIS.md*

## 6. Database Schema (Based on PRODUCT_WIZARD_FIELD_REFERENCE.md)

### 6.1 DiscoveredProduct - All Fields as Individual Columns

The following fields MUST be individual columns (not in JSON blobs):

**Identification:**
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(500) | Required, indexed |
| `brand` | FK to DiscoveredBrand | Indexed |
| `gtin` | CharField(14) | Optional, indexed |
| `fingerprint` | CharField(64) | Unique, indexed |

**Basic Product Info:**
| Field | Type | Notes |
|-------|------|-------|
| `product_type` | CharField(20) | whiskey, port_wine, etc. |
| `category` | CharField(100) | Sub-classification |
| `abv` | DecimalField(4,1) | 0-80%, indexed |
| `volume_ml` | IntegerField | Bottle size |
| `description` | TextField | Product description |
| `age_statement` | CharField(20) | "12", "NAS", etc. |
| `country` | CharField(100) | Indexed |
| `region` | CharField(100) | Indexed |
| `bottler` | CharField(100) | If different from brand |

**Tasting Profile - Appearance:**
| Field | Type | Notes |
|-------|------|-------|
| `color_description` | TextField | Descriptive text |
| `color_intensity` | IntegerField | 1-10 |
| `clarity` | CharField(20) | crystal_clear, slight_haze, cloudy |
| `viscosity` | CharField(20) | light, medium, full_bodied, syrupy |

**Tasting Profile - Nose:**
| Field | Type | Notes |
|-------|------|-------|
| `nose_description` | TextField | Overall nose description |
| `primary_aromas` | JSONField(list) | Array of tags - OK |
| `primary_intensity` | IntegerField | 1-10 |
| `secondary_aromas` | JSONField(list) | Array of tags - OK |
| `aroma_evolution` | TextField | How it changes |

**Tasting Profile - Palate (CRITICAL):**
| Field | Type | Notes |
|-------|------|-------|
| `initial_taste` | TextField | First impression |
| `mid_palate_evolution` | TextField | Flavor development |
| `palate_flavors` | JSONField(list) | Array of tags - OK |
| `palate_description` | TextField | Overall palate description |
| `flavor_intensity` | IntegerField | 1-10 |
| `complexity` | IntegerField | 1-10 |
| `mouthfeel` | CharField(30) | Choices: light_crisp, medium_balanced, full_rich, etc. |

**Tasting Profile - Finish:**
| Field | Type | Notes |
|-------|------|-------|
| `finish_length` | IntegerField | 1-10 |
| `warmth` | IntegerField | 1-10 |
| `dryness` | IntegerField | 1-10 |
| `finish_flavors` | JSONField(list) | Array of tags - OK |
| `finish_evolution` | TextField | How finish changes |
| `finish_description` | TextField | Overall finish description |
| `final_notes` | TextField | Lingering sensations |

**Tasting Profile - Overall:**
| Field | Type | Notes |
|-------|------|-------|
| `balance` | IntegerField | 1-10 |
| `overall_complexity` | IntegerField | 1-10 |
| `uniqueness` | IntegerField | 1-10 |
| `drinkability` | IntegerField | 1-10 |
| `price_quality_ratio` | IntegerField | 1-10 |
| `experience_level` | CharField(20) | beginner, intermediate, expert |
| `serving_recommendation` | CharField(20) | neat, on_rocks, cocktail |
| `food_pairings` | TextField | Recommendations |

**Status & Verification:**
| Field | Type | Notes |
|-------|------|-------|
| `status` | CharField(20) | incomplete, partial, complete, verified, rejected, merged |
| `completeness_score` | IntegerField | 0-100 |
| `source_count` | IntegerField | Number of sources |
| `verified_fields` | JSONField(list) | Fields verified by 2+ sources |
| `discovery_source` | CharField(20) | Primary discovery method |
| `extraction_confidence` | DecimalField(3,2) | 0.00-1.00 |

**Cask Info (Arrays OK):**
| Field | Type | Notes |
|-------|------|-------|
| `primary_cask` | JSONField(list) | ex-bourbon, sherry, etc. |
| `finishing_cask` | JSONField(list) | port, madeira, etc. |
| `wood_type` | JSONField(list) | american_oak, european_oak |
| `cask_treatment` | JSONField(list) | charred, toasted |
| `maturation_notes` | TextField | Detailed notes |

**DEPRECATED (migrate data then remove):**
| Field | Type | Notes |
|-------|------|-------|
| `extracted_data` | JSONField | DEPRECATED - migrate to columns |
| `enriched_data` | JSONField | DEPRECATED - migrate to columns |
| `taste_profile` | JSONField | DEPRECATED - migrate to columns |

### 6.2 WhiskeyDetails - Whiskey-Only Fields

| Field | Type | Notes |
|-------|------|-------|
| `product` | OneToOne FK | Link to DiscoveredProduct |
| `whiskey_type` | CharField(30) | single_malt, bourbon, rye, etc. |
| `distillery` | CharField(200) | Indexed |
| `mash_bill` | CharField(200) | Grain composition |
| `cask_strength` | BooleanField | |
| `single_cask` | BooleanField | |
| `cask_number` | CharField(50) | |
| `vintage_year` | IntegerField | Year distilled |
| `bottling_year` | IntegerField | |
| `batch_number` | CharField(50) | |
| `peated` | BooleanField | |
| `peat_level` | CharField(20) | unpeated, lightly, heavily |
| `peat_ppm` | IntegerField | Phenol PPM |
| `natural_color` | BooleanField | No E150a |
| `non_chill_filtered` | BooleanField | NCF |

### 6.3 PortWineDetails - Port-Only Fields

| Field | Type | Notes |
|-------|------|-------|
| `product` | OneToOne FK | Link to DiscoveredProduct |
| `style` | CharField(30) | ruby, tawny, vintage, LBV, etc. |
| `indication_age` | CharField(50) | "10 Year", "20 Year" |
| `harvest_year` | IntegerField | Indexed |
| `bottling_year` | IntegerField | |
| `producer_house` | CharField(200) | Taylor's, Graham's, etc. Indexed |
| `quinta` | CharField(200) | Estate name |
| `douro_subregion` | CharField(30) | baixo_corgo, cima_corgo, douro_superior |
| `grape_varieties` | JSONField(list) | Array of grape names |
| `aging_vessel` | CharField(100) | |
| `decanting_required` | BooleanField | |
| `drinking_window` | CharField(50) | "2025-2060" |
