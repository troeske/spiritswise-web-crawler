# Unified Product Pipeline Specification

## Executive Summary

This specification defines a unified product discovery and enrichment pipeline with:
1. **Mandatory tasting profile** for COMPLETE/VERIFIED status
2. **Multi-source verification** built into the flow
3. **Proper database columns** - no JSON blobs for searchable/filterable data
4. **Clean model separation** between DiscoveredProduct, WhiskeyDetails, and PortWineDetails

---

## 1. Core Requirements

### 1.1 Tasting Profile Is Mandatory

A product **cannot** be marked as COMPLETE or VERIFIED without tasting profile data.

**Minimum Required Tasting Fields:**
- `palate_flavors` (at least 2 tags) OR `palate_description`
- `initial_taste` OR `mid_palate_evolution`

**For VERIFIED status, additionally required:**
- `nose_description` OR `primary_aromas`
- `finish_description` OR `finish_flavors`
- Data confirmed from 2+ sources

### 1.2 Multi-Source Verification

Products discovered from one source should be enriched from additional sources to:
1. Verify extracted data accuracy
2. Fill in missing fields
3. Build confidence through consensus

**Verification Flow:**
```
Source 1 (Discovery)          Source 2 (Verification)        Source 3 (Enrichment)
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ Name: ✓       │             │ Name: ✓       │             │ Name: ✓       │
│ Brand: ✓      │             │ Brand: ✓      │ ──VERIFY──► │ Brand: ✓      │
│ ABV: 43%      │             │ ABV: 43%      │             │ ABV: 43%      │
│ Palate: -     │             │ Palate: ✓     │ ──ADD────►  │ Palate: ✓     │
│ Finish: -     │             │ Finish: -     │             │ Finish: ✓     │
└───────────────┘             └───────────────┘             └───────────────┘
        │                              │                              │
        └──────────────────────────────┴──────────────────────────────┘
                                       │
                                       ▼
                            VERIFIED with confidence
```

### 1.3 No JSON Blobs for Critical Data

**WRONG:**
```python
extracted_data = models.JSONField(default=dict)  # Catch-all blob
enriched_data = models.JSONField(default=dict)   # Another blob
taste_profile = models.JSONField(default=dict)   # Yet another blob
```

**RIGHT:**
```python
# Individual searchable/filterable columns
name = models.CharField(max_length=500)
abv = models.DecimalField(...)
palate_description = models.TextField(...)
finish_length = models.IntegerField(...)

# JSONField ONLY for:
# - Arrays of tags (primary_aromas, palate_flavors)
# - Rarely-queried metadata
# - Truly dynamic/extensible data
```

---

## 2. Database Schema

### 2.1 DiscoveredProduct - Core Fields

Based on PRODUCT_WIZARD_FIELD_REFERENCE.md, properly normalized:

```python
class DiscoveredProduct(models.Model):
    """
    Core product discovery record.

    Design Principles:
    1. All searchable/filterable fields are individual columns
    2. JSONField only for arrays (tags) or rarely-queried data
    3. Related data uses FK relationships (Awards, Ratings, Images, Prices)
    4. Type-specific fields go in WhiskeyDetails/PortWineDetails
    """

    # ============================================================
    # IDENTIFICATION
    # ============================================================

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)

    # GTIN/Barcode (for inventory integration)
    gtin = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        db_index=True,
        help_text="Global Trade Item Number (8-14 digits)",
    )

    # ============================================================
    # MANDATORY PRODUCT INFO (Step 1 from Wizard)
    # ============================================================

    name = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Complete product name",
    )
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        db_index=True,
        help_text="Primary spirit category: whiskey, port_wine, etc.",
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Sub-classification: Single Malt, Bourbon, Tawny, etc.",
    )
    brand = models.ForeignKey(
        'DiscoveredBrand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Brand/manufacturer",
    )
    abv = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        db_index=True,
        help_text="Alcohol by volume percentage (0-80)",
    )

    # ============================================================
    # OPTIONAL PRODUCT DETAILS (Step 2 from Wizard)
    # ============================================================

    description = models.TextField(
        blank=True,
        help_text="Detailed product description (max 5000 chars)",
    )
    volume_ml = models.IntegerField(
        null=True,
        blank=True,
        help_text="Bottle volume in milliliters",
    )

    # ============================================================
    # SPIRIT-SPECIFIC ATTRIBUTES (Step 3 from Wizard)
    # These apply to BOTH whiskey and port (shared fields)
    # ============================================================

    age_statement = models.CharField(
        max_length=20,
        blank=True,
        help_text="Age in years or 'NAS' for No Age Statement",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Country of origin",
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Production region (Speyside, Kentucky, Douro, etc.)",
    )
    bottler = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bottling company (if different from brand)",
    )

    # Cask information (JSONField OK - arrays of selections)
    primary_cask = models.JSONField(
        default=list,
        blank=True,
        help_text="Primary cask types: ['ex-bourbon', 'sherry']",
    )
    finishing_cask = models.JSONField(
        default=list,
        blank=True,
        help_text="Finishing cask types: ['port', 'madeira']",
    )
    wood_type = models.JSONField(
        default=list,
        blank=True,
        help_text="Wood types: ['american_oak', 'european_oak']",
    )
    cask_treatment = models.JSONField(
        default=list,
        blank=True,
        help_text="Cask treatments: ['charred', 'toasted']",
    )
    maturation_notes = models.TextField(
        blank=True,
        help_text="Detailed aging process notes",
    )

    # ============================================================
    # VISUAL APPEARANCE (Tasting Profile Step 1)
    # ============================================================

    color_description = models.TextField(
        blank=True,
        help_text="Descriptive text of color and appearance",
    )
    color_intensity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Color depth rating 1-10",
    )
    clarity = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('crystal_clear', 'Crystal Clear'),
            ('slight_haze', 'Slight Haze'),
            ('cloudy', 'Cloudy'),
        ],
        help_text="Visual clarity",
    )
    viscosity = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('light', 'Light'),
            ('medium', 'Medium'),
            ('full_bodied', 'Full-bodied'),
            ('syrupy', 'Syrupy'),
        ],
        help_text="Texture/thickness",
    )

    # ============================================================
    # NOSE PROFILE (Tasting Profile Step 2)
    # ============================================================

    nose_description = models.TextField(
        blank=True,
        help_text="Overall nose/aroma description",
    )
    primary_aromas = models.JSONField(
        default=list,
        blank=True,
        help_text="Primary aroma tags: ['vanilla', 'honey', 'oak']",
    )
    primary_intensity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Primary aroma intensity 1-10",
    )
    secondary_aromas = models.JSONField(
        default=list,
        blank=True,
        help_text="Secondary aroma tags: ['citrus', 'floral']",
    )
    aroma_evolution = models.TextField(
        blank=True,
        help_text="How aromas change over time",
    )

    # ============================================================
    # PALATE EXPERIENCE (Tasting Profile Step 3) - CRITICAL
    # ============================================================

    initial_taste = models.TextField(
        blank=True,
        help_text="First impression on the palate",
    )
    mid_palate_evolution = models.TextField(
        blank=True,
        help_text="How flavors develop mid-taste",
    )
    palate_flavors = models.JSONField(
        default=list,
        blank=True,
        help_text="Palate flavor tags: ['caramel', 'apple', 'cinnamon']",
    )
    palate_description = models.TextField(
        blank=True,
        help_text="Overall palate description (combined)",
    )
    flavor_intensity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Flavor strength/boldness 1-10",
    )
    complexity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Number of flavor layers 1-10",
    )
    mouthfeel = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ('light_crisp', 'Light & Crisp'),
            ('light_smooth', 'Light & Smooth'),
            ('medium_dry', 'Medium & Dry'),
            ('medium_balanced', 'Medium & Balanced'),
            ('medium_creamy', 'Medium & Creamy'),
            ('full_dry', 'Full & Dry'),
            ('full_rich', 'Full & Rich'),
            ('full_oily', 'Full & Oily'),
            ('smooth_creamy', 'Smooth & Creamy'),
            ('robust_chewy', 'Robust & Chewy'),
            ('syrupy_coating', 'Syrupy & Coating'),
            ('warming_tingling', 'Warming & Tingling'),
        ],
        help_text="Physical texture sensation",
    )

    # ============================================================
    # FINISH ANALYSIS (Tasting Profile Step 4)
    # ============================================================

    finish_length = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Duration of aftertaste 1-10",
    )
    warmth = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Heat/warming sensation 1-10",
    )
    dryness = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Dryness level 1-10",
    )
    finish_flavors = models.JSONField(
        default=list,
        blank=True,
        help_text="Finish flavor tags: ['oak', 'spice', 'honey']",
    )
    finish_evolution = models.TextField(
        blank=True,
        help_text="How finish changes over time",
    )
    finish_description = models.TextField(
        blank=True,
        help_text="Overall finish description",
    )
    final_notes = models.TextField(
        blank=True,
        help_text="Last impressions and lingering sensations",
    )

    # ============================================================
    # OVERALL ASSESSMENT (Tasting Profile Step 5)
    # ============================================================

    balance = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Harmony between flavors 1-10",
    )
    overall_complexity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Depth and layers 1-10",
    )
    uniqueness = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="How distinctive 1-10",
    )
    drinkability = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="How easy/pleasant to drink 1-10",
    )
    value_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Price-quality ratio 1-10",
    )
    experience_level = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('beginner', 'Beginner'),
            ('casual', 'Casual'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        help_text="Recommended experience level",
    )
    serving_recommendation = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('neat', 'Neat'),
            ('on_rocks', 'On the Rocks'),
            ('splash_water', 'With Water'),
            ('cocktail', 'In Cocktails'),
            ('chilled', 'Chilled'),
            ('warmed', 'Warmed'),
        ],
        help_text="Best serving method",
    )
    food_pairings = models.TextField(
        blank=True,
        help_text="Recommended food pairings",
    )

    # ============================================================
    # PRICING (Current best price - historical in ProductPrice)
    # ============================================================

    best_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Current best known price",
    )
    best_price_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code",
    )
    best_price_retailer = models.CharField(
        max_length=200,
        blank=True,
        help_text="Retailer with best price",
    )
    best_price_url = models.URLField(
        blank=True,
        help_text="URL for best price",
    )
    best_price_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When best price was last updated",
    )

    # ============================================================
    # DISCOVERY & STATUS
    # ============================================================

    status = models.CharField(
        max_length=20,
        choices=[
            ('incomplete', 'Incomplete'),       # Missing critical data
            ('partial', 'Partial'),             # Has basic data, missing tasting
            ('complete', 'Complete'),           # Has tasting profile
            ('verified', 'Verified'),           # Multi-source verified
            ('rejected', 'Rejected'),           # Not a valid product
            ('merged', 'Merged'),               # Merged into another product
        ],
        default='incomplete',
        db_index=True,
    )
    completeness_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Data completeness percentage",
    )

    # Multi-source tracking
    source_count = models.IntegerField(
        default=1,
        help_text="Number of sources this product was found in",
    )
    verified_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Fields verified by multiple sources: ['name', 'abv', 'palate']",
    )

    # Discovery metadata
    discovery_source = models.CharField(
        max_length=20,
        choices=DiscoverySource.choices,
        help_text="Primary discovery method",
    )
    source_url = models.URLField(
        blank=True,
        help_text="Primary source URL",
    )
    discovered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Extraction quality
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="AI extraction confidence (0.00-1.00)",
    )

    # ============================================================
    # LEGACY JSON FIELDS (to be deprecated/migrated)
    # ============================================================

    # These should be migrated to proper columns or removed
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="DEPRECATED - Raw extraction dump for migration",
    )
    enriched_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="DEPRECATED - Enrichment dump for migration",
    )

    # ============================================================
    # RELATIONSHIPS (use FK tables, not JSON)
    # ============================================================

    # FK relationships defined elsewhere:
    # - brand -> DiscoveredBrand
    # - awards -> ProductAward (via awards_rel)
    # - ratings -> ProductRating
    # - images -> ProductImage
    # - prices -> ProductPrice
    # - sources -> ProductSource
    # - field_sources -> ProductFieldSource

    class Meta:
        db_table = "discovered_product"
        indexes = [
            models.Index(fields=['status', 'completeness_score']),
            models.Index(fields=['product_type', 'status']),
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['country', 'region']),
        ]
```

### 2.2 WhiskeyDetails - Whiskey-Specific Fields

```python
class WhiskeyDetails(models.Model):
    """
    Whiskey-specific attributes.

    Only fields that are unique to whiskey go here.
    Common fields (age, region, cask) stay on DiscoveredProduct.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    product = models.OneToOneField(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='whiskey_details',
    )

    # Classification
    whiskey_type = models.CharField(
        max_length=30,
        choices=[
            ('single_malt', 'Single Malt'),
            ('blended_malt', 'Blended Malt'),
            ('single_grain', 'Single Grain'),
            ('blended', 'Blended'),
            ('bourbon', 'Bourbon'),
            ('rye', 'Rye'),
            ('tennessee', 'Tennessee'),
            ('irish', 'Irish'),
            ('japanese', 'Japanese'),
            ('canadian', 'Canadian'),
            ('other', 'Other'),
        ],
        help_text="Whiskey classification",
    )

    # Production Details
    distillery = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        help_text="Distillery name",
    )
    mash_bill = models.CharField(
        max_length=200,
        blank=True,
        help_text="Grain composition (e.g., '75% corn, 21% rye, 4% malted barley')",
    )

    # Release Details
    cask_strength = models.BooleanField(
        default=False,
        help_text="Bottled at cask strength",
    )
    single_cask = models.BooleanField(
        default=False,
        help_text="Single cask release",
    )
    cask_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Cask number for single cask",
    )

    # Vintage/Batch
    vintage_year = models.IntegerField(
        null=True,
        blank=True,
        help_text="Year of distillation",
    )
    bottling_year = models.IntegerField(
        null=True,
        blank=True,
        help_text="Year of bottling",
    )
    batch_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Batch identifier",
    )

    # Peat Profile
    peated = models.BooleanField(
        null=True,
        blank=True,
        help_text="Is this whiskey peated?",
    )
    peat_level = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('unpeated', 'Unpeated'),
            ('lightly_peated', 'Lightly Peated'),
            ('moderately_peated', 'Moderately Peated'),
            ('heavily_peated', 'Heavily Peated'),
        ],
        help_text="Peat intensity level",
    )
    peat_ppm = models.IntegerField(
        null=True,
        blank=True,
        help_text="Phenol parts per million",
    )

    # Coloring/Filtration
    natural_color = models.BooleanField(
        null=True,
        blank=True,
        help_text="No added coloring (E150a)",
    )
    non_chill_filtered = models.BooleanField(
        null=True,
        blank=True,
        help_text="Not chill filtered",
    )

    class Meta:
        db_table = "whiskey_details"
        verbose_name = "Whiskey Details"
        verbose_name_plural = "Whiskey Details"
```

### 2.3 PortWineDetails - Port-Specific Fields

```python
class PortWineDetails(models.Model):
    """
    Port wine-specific attributes.

    Only fields that are unique to port go here.
    Common fields stay on DiscoveredProduct.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    product = models.OneToOneField(
        DiscoveredProduct,
        on_delete=models.CASCADE,
        related_name='port_details',
    )

    # Style Classification
    style = models.CharField(
        max_length=30,
        choices=[
            ('ruby', 'Ruby'),
            ('tawny', 'Tawny'),
            ('white', 'White'),
            ('rose', 'Rosé'),
            ('vintage', 'Vintage'),
            ('late_bottled_vintage', 'Late Bottled Vintage (LBV)'),
            ('crusted', 'Crusted'),
            ('colheita', 'Colheita'),
            ('garrafeira', 'Garrafeira'),
        ],
        help_text="Port style classification",
    )
    indication_age = models.CharField(
        max_length=50,
        blank=True,
        help_text="Age indication: '10 Year', '20 Year', '40 Year'",
    )

    # Vintage
    harvest_year = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Harvest/vintage year",
    )
    bottling_year = models.IntegerField(
        null=True,
        blank=True,
        help_text="Year of bottling",
    )

    # Production
    producer_house = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Port house (Taylor's, Graham's, etc.)",
    )
    quinta = models.CharField(
        max_length=200,
        blank=True,
        help_text="Quinta (estate) name",
    )
    douro_subregion = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ('baixo_corgo', 'Baixo Corgo'),
            ('cima_corgo', 'Cima Corgo'),
            ('douro_superior', 'Douro Superior'),
        ],
        help_text="Douro Valley subregion",
    )
    grape_varieties = models.JSONField(
        default=list,
        blank=True,
        help_text="Grape varieties: ['Touriga Nacional', 'Touriga Franca']",
    )

    # Aging
    aging_vessel = models.CharField(
        max_length=100,
        blank=True,
        help_text="Aging vessel type (large oak vats, barrels, etc.)",
    )

    # Serving
    decanting_required = models.BooleanField(
        default=False,
        help_text="Requires decanting before serving",
    )
    drinking_window = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optimal drinking window: '2025-2060'",
    )

    class Meta:
        db_table = "port_wine_details"
        verbose_name = "Port Wine Details"
        verbose_name_plural = "Port Wine Details"
```

---

## 3. Completeness & Status Logic

### 3.1 New Status Model

```python
class ProductStatus(str, Enum):
    INCOMPLETE = "incomplete"   # Score 0-29: Missing critical data
    PARTIAL = "partial"         # Score 30-59: Has basic info, no tasting
    COMPLETE = "complete"       # Score 60-79: Has tasting profile
    VERIFIED = "verified"       # Score 80-100: Multi-source verified
    REJECTED = "rejected"       # Not a valid product
    MERGED = "merged"           # Merged into another product
```

### 3.2 Completeness Score Calculation

```python
def calculate_completeness(product: DiscoveredProduct) -> int:
    """
    Calculate product data completeness.

    Tasting profile is heavily weighted - cannot reach COMPLETE without it.
    """
    score = 0

    # ============================================================
    # IDENTIFICATION (15 points max)
    # ============================================================
    if product.name:
        score += 10
    if product.brand:
        score += 5

    # ============================================================
    # BASIC PRODUCT INFO (15 points max)
    # ============================================================
    if product.product_type:
        score += 5
    if product.abv:
        score += 5
    if product.description:
        score += 5

    # ============================================================
    # TASTING PROFILE (40 points max) - CRITICAL
    # Cannot reach COMPLETE without at least 20 points here
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

    # Pricing (5 points)
    if product.best_price:
        score += 5

    # Images (5 points)
    if product.images.exists():
        score += 5

    # Ratings (5 points)
    if product.ratings.exists():
        score += 5

    # Awards (5 points)
    if product.awards_rel.exists():
        score += 5

    # ============================================================
    # VERIFICATION BONUS (10 points max)
    # ============================================================
    if product.source_count >= 2:
        score += 5
    if product.source_count >= 3:
        score += 5

    return min(score, 100)


def determine_status(product: DiscoveredProduct) -> str:
    """
    Determine product status based on completeness and tasting data.

    Key rule: COMPLETE/VERIFIED requires palate tasting profile.
    """
    score = product.completeness_score

    # Check for mandatory tasting profile
    has_palate = bool(
        (product.palate_flavors and len(product.palate_flavors) >= 2) or
        product.palate_description or
        product.initial_taste
    )

    # Cannot be COMPLETE or VERIFIED without palate data
    if not has_palate:
        if score >= 30:
            return ProductStatus.PARTIAL
        return ProductStatus.INCOMPLETE

    # With palate data, status based on score
    if score >= 80:
        return ProductStatus.VERIFIED
    elif score >= 60:
        return ProductStatus.COMPLETE
    elif score >= 30:
        return ProductStatus.PARTIAL
    else:
        return ProductStatus.INCOMPLETE
```

---

## 4. Multi-Source Verification Pipeline

### 4.1 Verification Strategy

```python
class VerificationPipeline:
    """
    Pipeline that enriches products from multiple sources.

    Goal: Every product should be verified from 2+ sources before VERIFIED status.
    """

    # Target sources per product
    TARGET_SOURCES = 3
    MIN_SOURCES_FOR_VERIFIED = 2

    # Search strategies for missing data
    ENRICHMENT_STRATEGIES = {
        "tasting_notes": [
            "{name} tasting notes review",
            "{name} nose palate finish",
            "{brand} {name} whisky review",
        ],
        "pricing": [
            "{name} buy price",
            "{name} whisky exchange price",
        ],
        "images": [
            "{name} bottle image",
        ],
    }

    async def verify_product(
        self,
        candidate: ProductCandidate,
    ) -> VerificationResult:
        """
        Verify and enrich a product from multiple sources.

        Steps:
        1. Save initial product (from first source)
        2. Identify missing/unverified fields
        3. Search for additional sources
        4. Extract data from each source
        5. Merge and verify data
        6. Update completeness and status
        """

        # Step 1: Create/find product
        product = await self._get_or_create_product(candidate)
        sources_used = 1

        # Step 2: Identify what we need
        missing = self._get_missing_critical_fields(product)
        needs_verification = self._get_unverified_fields(product)

        # Step 3: Search for additional sources
        if missing or needs_verification or sources_used < self.TARGET_SOURCES:
            search_results = await self._search_additional_sources(
                product,
                missing,
                needs_verification,
            )

            # Step 4: Extract from each source
            for source_url in search_results[:self.TARGET_SOURCES - 1]:
                extraction = await self._extract_from_source(source_url, product)

                if extraction.success:
                    # Step 5: Merge and verify
                    await self._merge_and_verify(product, extraction)
                    sources_used += 1

        # Step 6: Update status
        product.source_count = sources_used
        product.completeness_score = calculate_completeness(product)
        product.status = determine_status(product)
        await self._save_product(product)

        return VerificationResult(
            product=product,
            sources_used=sources_used,
            verified_fields=product.verified_fields,
            missing_fields=missing,
        )

    def _get_missing_critical_fields(self, product: DiscoveredProduct) -> List[str]:
        """Get list of critical missing fields (especially tasting)."""
        missing = []

        # Palate is critical
        if not product.palate_flavors and not product.palate_description:
            missing.append("palate")

        # Nose is important
        if not product.nose_description and not product.primary_aromas:
            missing.append("nose")

        # Finish is important
        if not product.finish_description and not product.finish_flavors:
            missing.append("finish")

        # Basic info
        if not product.abv:
            missing.append("abv")
        if not product.description:
            missing.append("description")

        return missing

    async def _merge_and_verify(
        self,
        product: DiscoveredProduct,
        extraction: ExtractionResult,
    ):
        """
        Merge new extraction into product, marking verified fields.
        """
        new_data = extraction.data
        verified = list(product.verified_fields or [])

        # For each field in new extraction
        for field, new_value in new_data.items():
            if not new_value:
                continue

            current_value = getattr(product, field, None)

            if current_value is None:
                # Field was missing - add it
                setattr(product, field, new_value)
            elif self._values_match(current_value, new_value):
                # Values match - field is verified!
                if field not in verified:
                    verified.append(field)
            else:
                # Values differ - log conflict, keep highest confidence
                await self._log_conflict(product, field, current_value, new_value)
                # Could implement conflict resolution here

        product.verified_fields = verified
```

---

## 5. Updated ProductCandidate

```python
@dataclass
class ProductCandidate:
    """
    Unified intermediate format for all product discovery flows.

    Now includes proper tasting profile fields (not JSON blobs).
    """

    # ============================================================
    # IDENTIFICATION
    # ============================================================
    name: str
    brand: Optional[str] = None
    gtin: Optional[str] = None

    # ============================================================
    # BASIC INFO
    # ============================================================
    product_type: str = "whiskey"
    category: Optional[str] = None
    abv: Optional[float] = None
    volume_ml: Optional[int] = None
    description: Optional[str] = None
    age_statement: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None

    # ============================================================
    # TASTING PROFILE - Individual fields, not JSON
    # ============================================================

    # Appearance
    color_description: Optional[str] = None
    color_intensity: Optional[int] = None
    clarity: Optional[str] = None
    viscosity: Optional[str] = None

    # Nose
    nose_description: Optional[str] = None
    primary_aromas: List[str] = field(default_factory=list)
    primary_intensity: Optional[int] = None
    secondary_aromas: List[str] = field(default_factory=list)
    aroma_evolution: Optional[str] = None

    # Palate (CRITICAL - mandatory for COMPLETE status)
    initial_taste: Optional[str] = None
    mid_palate_evolution: Optional[str] = None
    palate_flavors: List[str] = field(default_factory=list)
    palate_description: Optional[str] = None
    flavor_intensity: Optional[int] = None
    complexity: Optional[int] = None
    mouthfeel: Optional[str] = None

    # Finish
    finish_length: Optional[int] = None
    warmth: Optional[int] = None
    dryness: Optional[int] = None
    finish_flavors: List[str] = field(default_factory=list)
    finish_evolution: Optional[str] = None
    finish_description: Optional[str] = None
    final_notes: Optional[str] = None

    # Overall
    balance: Optional[int] = None
    overall_complexity: Optional[int] = None
    uniqueness: Optional[int] = None
    drinkability: Optional[int] = None
    experience_level: Optional[str] = None
    serving_recommendation: Optional[str] = None
    food_pairings: Optional[str] = None

    # ============================================================
    # RELATED DATA
    # ============================================================
    awards: List[Dict[str, Any]] = field(default_factory=list)
    ratings: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    prices: List[Dict[str, Any]] = field(default_factory=list)

    # ============================================================
    # SOURCE INFO
    # ============================================================
    extraction_source: ExtractionSource = ExtractionSource.AI_SINGLE_EXTRACTION
    source_url: str = ""
    direct_product_link: Optional[str] = None
    extraction_confidence: float = 0.5

    # ============================================================
    # COMPUTED PROPERTIES
    # ============================================================

    @property
    def has_palate_profile(self) -> bool:
        """Check if we have mandatory palate data."""
        return bool(
            (self.palate_flavors and len(self.palate_flavors) >= 2) or
            self.palate_description or
            self.initial_taste
        )

    @property
    def has_nose_profile(self) -> bool:
        return bool(
            self.nose_description or
            (self.primary_aromas and len(self.primary_aromas) >= 2)
        )

    @property
    def has_finish_profile(self) -> bool:
        return bool(
            self.finish_description or
            (self.finish_flavors and len(self.finish_flavors) >= 2)
        )

    @property
    def has_complete_tasting(self) -> bool:
        """Check if we have all three tasting components."""
        return (
            self.has_palate_profile and
            self.has_nose_profile and
            self.has_finish_profile
        )

    @property
    def completeness_score(self) -> int:
        """Calculate completeness - see full calculation above."""
        # ... implementation matches calculate_completeness()
        pass

    def can_be_complete(self) -> bool:
        """Check if this candidate can reach COMPLETE status."""
        return self.has_palate_profile

    def get_missing_for_complete(self) -> List[str]:
        """Get fields needed to reach COMPLETE status."""
        missing = []

        if not self.has_palate_profile:
            missing.append("palate_profile")

        if not self.name:
            missing.append("name")

        return missing

    def get_missing_for_verified(self) -> List[str]:
        """Get fields needed to reach VERIFIED status."""
        missing = self.get_missing_for_complete()

        if not self.has_nose_profile:
            missing.append("nose_profile")

        if not self.has_finish_profile:
            missing.append("finish_profile")

        if not self.abv:
            missing.append("abv")

        return missing
```

---

## 6. Migration Path

### 6.1 Database Migration Steps

1. **Add new columns** to DiscoveredProduct for all tasting fields
2. **Migrate data** from JSON blobs to individual columns
3. **Add completeness_score** column
4. **Add source_count** and **verified_fields** columns
5. **Update status enum** values
6. **Mark JSON fields as deprecated**

### 6.2 Data Migration Script

```python
def migrate_json_to_columns():
    """
    Migrate data from extracted_data/enriched_data/taste_profile JSON
    to individual columns.
    """
    for product in DiscoveredProduct.objects.all():
        # Combine all JSON sources
        data = {
            **product.extracted_data,
            **product.enriched_data,
            **(product.taste_profile if hasattr(product, 'taste_profile') else {}),
        }

        # Map to individual columns
        if not product.nose_description and data.get('nose'):
            product.nose_description = data['nose']

        if not product.palate_description and data.get('palate'):
            product.palate_description = data['palate']

        if not product.finish_description and data.get('finish'):
            product.finish_description = data['finish']

        # ... map all fields

        # Recalculate completeness
        product.completeness_score = calculate_completeness(product)
        product.status = determine_status(product)

        product.save()
```

---

## 7. Summary

### Key Changes from Previous Design:

1. **Tasting Profile is Mandatory** - Cannot reach COMPLETE without palate data
2. **Multi-Source Verification** - Target 2-3 sources per product for VERIFIED
3. **No JSON Blobs** - All searchable fields are individual columns
4. **Completeness Score** - Weighted scoring with tasting = 40%
5. **Clear Status Model** - INCOMPLETE → PARTIAL → COMPLETE → VERIFIED
6. **Proper Model Split** - Base fields on DiscoveredProduct, type-specific on Details

### Implementation Priority:

1. Update DiscoveredProduct model with new columns
2. Create migration for existing data
3. Implement completeness calculation
4. Update ProductCandidate
5. Build verification pipeline
6. Update extractors to populate new fields
7. Deprecate JSON blob fields

---

*Document created: 2026-01-05*
*Version: 2.0*
