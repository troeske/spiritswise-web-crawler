# Crawler-AI Service Architecture V2

## Executive Summary

This document defines the architecture where:
- **Crawler owns ALL quality assessment** - decides what to do with results
- **AI Service extracts ALL available information** - no filtering, just extraction
- **Crawler specifies product type and category** - AI knows what to look for
- **Progressive enrichment loop** - crawler orchestrates multi-source data collection

---

## 1. Core Principles

### 1.1 Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **Crawler** | Orchestration, quality gates, enrichment decisions, saves |
| **AI Service** | Extract ALL available information from source data |

### 1.2 Quality Gate Philosophy

- **AI Service Quality Gate**: "Did I extract ALL fields from the schema that exist in the source?"
  - Crawler passes flat `extraction_schema` (list of field names)
  - AI extracts EVERY field from the schema that it can find
  - **Applies to BOTH single-product AND multi-product pages** - list pages often contain rich data (tasting notes, descriptions, ratings) that must be captured
  - AI determines if source is single or multi-product
  - If info is in source but not extracted = AI failure
  - Missing info because source doesn't have it = OK (return null)
  - NO required/optional distinction - AI always extracts everything available

- **Crawler Quality Gate**: "Is this product data good enough for my purpose?"
  - Receives extracted data and decides based on which fields were populated
  - Decides: save as skeleton, partial, or complete
  - Decides: needs enrichment or not
  - Decides: what additional sources to search

### 1.3 Configuration-Driven Architecture

Both Crawler and AI Service are **content-agnostic**. All product type knowledge is stored in database configuration:

- **AI Service**: Pure extraction engine - receives field definitions with descriptions/examples, extracts data, returns results. Zero domain knowledge.
- **Crawler**: Loads configuration from database, builds extraction schema, applies quality gates, maps extracted data to model fields.
- **Adding new product types** (e.g., GIN): Just add database configuration via Django Admin - no code changes required.

```
┌─────────────────────────────────────────────────────────────┐
│                 Configuration-Driven Flow                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────────────┐      ┌─────────────────────┐     │
│   │  Database            │ ◄──► │  Django Admin       │     │
│   │  - ProductTypeConfig │      │  (Configuration UI) │     │
│   │  - FieldDefinition   │      └─────────────────────┘     │
│   │  - QualityGateConfig │               │                   │
│   │  - EnrichmentConfig  │               ▼                   │
│   └──────────────────────┘      ┌─────────────────────┐     │
│              │                  │  Future: Custom     │     │
│              │                  │  Config Web UI      │     │
│              │                  └─────────────────────┘     │
│              │                                               │
│              ▼                                               │
│   ┌──────────────────────────────────────────────────┐      │
│   │  Crawler                                          │      │
│   │  1. Load ProductTypeConfig for "whiskey"          │      │
│   │  2. Build extraction_schema from FieldDefinitions │      │
│   │  3. Call AI Service with schema                   │      │
│   │  4. Apply QualityGateConfig to results            │      │
│   │  5. Map extracted data to models via target_model │      │
│   │  6. Save to DiscoveredProduct/WhiskeyDetails/etc  │      │
│   └──────────────────────────────────────────────────┘      │
│              │                                               │
│              ▼                                               │
│   ┌──────────────────────────────────────────────────┐      │
│   │  AI Service (Content-Agnostic)                    │      │
│   │  - Receives field definitions with descriptions   │      │
│   │  - Extracts ALL fields it can find                │      │
│   │  - Returns extracted data + confidences           │      │
│   │  - NO hardcoded product knowledge                 │      │
│   └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Roadmap**: YAML import/export for version control and PR reviews of configuration changes.

---

## 2. Configuration Models (MVP)

### 2.1 ProductTypeConfig

Top-level configuration for a product type.

```python
class ProductTypeConfig(models.Model):
    """Configuration for a product type (whiskey, port_wine, gin, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Identity
    product_type = models.CharField(max_length=50, unique=True, db_index=True)
    display_name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, default="1.0")
    is_active = models.BooleanField(default=True)

    # Valid categories for this product type
    categories = models.JSONField(
        default=list,
        help_text='Valid categories: ["bourbon", "scotch", "rye"]'
    )

    # ═══════════════════════════════════════════════════════════
    # Enrichment Limits (per product type)
    # ═══════════════════════════════════════════════════════════
    max_sources_per_product = models.IntegerField(
        default=5,
        help_text="Maximum number of sources to fetch per product during enrichment"
    )
    max_serpapi_searches = models.IntegerField(
        default=3,
        help_text="Maximum SerpAPI searches per product (cost control)"
    )
    max_enrichment_time_seconds = models.IntegerField(
        default=120,
        help_text="Maximum time in seconds for enrichment per product"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "product_type_config"
        verbose_name = "Product Type Configuration"
```

### 2.2 FieldDefinition

Field definitions with AI extraction instructions AND model mapping.

```python
class FieldDefinition(models.Model):
    """Field definition for extraction schema with model mapping"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Relationship - null means shared/base field for all product types
    product_type_config = models.ForeignKey(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name='fields',
        null=True,
        blank=True,
        help_text="Null = shared/base field for all product types"
    )

    # Field identity
    field_name = models.CharField(max_length=100, db_index=True)
    display_name = models.CharField(max_length=200)
    field_group = models.CharField(
        max_length=50,
        choices=[
            ('core', 'Core Product'),
            ('tasting_appearance', 'Tasting - Appearance'),
            ('tasting_nose', 'Tasting - Nose'),
            ('tasting_palate', 'Tasting - Palate'),
            ('tasting_finish', 'Tasting - Finish'),
            ('tasting_overall', 'Tasting - Overall'),
            ('production', 'Production'),
            ('cask', 'Cask/Maturation'),
            ('related', 'Related Data'),
            ('type_specific', 'Type Specific'),
        ],
        default='core'
    )

    # ═══════════════════════════════════════════════════════════
    # AI Extraction Schema (sent to AI Service)
    # ═══════════════════════════════════════════════════════════

    field_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('text', 'Text (long)'),
            ('integer', 'Integer'),
            ('decimal', 'Decimal'),
            ('boolean', 'Boolean'),
            ('array', 'Array'),
            ('object', 'Object'),
        ]
    )
    item_type = models.CharField(
        max_length=20,
        blank=True,
        help_text="For arrays: type of items (string, object)"
    )
    description = models.TextField(
        help_text="Description for AI extraction - be specific and clear!"
    )
    examples = models.JSONField(
        default=list,
        help_text='Examples help AI understand: ["Ardbeg 10", "Glenfiddich 18"]'
    )
    allowed_values = models.JSONField(
        default=list,
        blank=True,
        help_text='For enums: ["gold", "silver", "bronze"]'
    )
    item_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="Schema for object/array items (awards, ratings, etc.)"
    )

    # ═══════════════════════════════════════════════════════════
    # Model Mapping (where to store extracted data)
    # ═══════════════════════════════════════════════════════════

    target_model = models.CharField(
        max_length=100,
        choices=[
            ('DiscoveredProduct', 'DiscoveredProduct'),
            ('WhiskeyDetails', 'WhiskeyDetails'),
            ('PortWineDetails', 'PortWineDetails'),
            ('ProductAward', 'ProductAward'),
            ('ProductPrice', 'ProductPrice'),
            ('ProductRating', 'ProductRating'),
        ],
        help_text="Django model where this field is stored"
    )
    target_field = models.CharField(
        max_length=100,
        help_text="Field name in the target model"
    )

    # Ordering
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "field_definition"
        ordering = ['field_group', 'sort_order', 'field_name']
        unique_together = [['product_type_config', 'field_name']]

    def to_extraction_schema(self) -> dict:
        """Convert to schema format for AI Service request."""
        schema = {
            "type": self.field_type,
            "description": self.description,
        }
        if self.examples:
            schema["examples"] = self.examples
        if self.allowed_values:
            schema["allowed_values"] = self.allowed_values
        if self.item_type:
            schema["item_type"] = self.item_type
        if self.item_schema:
            schema["item_schema"] = self.item_schema
        return schema
```

### 2.3 QualityGateConfig

Quality thresholds for SKELETON/PARTIAL/COMPLETE/ENRICHED status.

**Logic**: Each status level uses AND logic:
```
STATUS = (ALL required_fields present) AND (at least any_of_count from any_of_fields)
```

```python
class QualityGateConfig(models.Model):
    """
    Quality gate thresholds for a product type.

    Logic for each status:
        STATUS = (ALL required_fields) AND (N or more from any_of_fields)

    Example for COMPLETE:
        complete_required_fields = ["name", "brand", "abv", "description", "palate_flavors"]
        complete_any_of_count = 2
        complete_any_of_fields = ["nose_description", "finish_description", "distillery", "region"]

        A product is COMPLETE if:
        - Has name AND brand AND abv AND description AND palate_flavors (all 5 required)
        - AND has at least 2 of: nose_description, finish_description, distillery, region

    Note: ABV is legally required on all spirits labels, so it's required for PARTIAL and COMPLETE.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    product_type_config = models.OneToOneField(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name='quality_gates'
    )

    # ═══════════════════════════════════════════════════════════
    # SKELETON: Minimum to save at all
    # ═══════════════════════════════════════════════════════════
    skeleton_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL of these. Example: ["name"]'
    )

    # ═══════════════════════════════════════════════════════════
    # PARTIAL: Has some useful data
    # ═══════════════════════════════════════════════════════════
    partial_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL of these. Example: ["name", "brand"]'
    )
    partial_any_of_count = models.IntegerField(
        default=2,
        help_text='Must have at least this many from any_of_fields'
    )
    partial_any_of_fields = models.JSONField(
        default=list,
        help_text='Pool of fields. Example: ["abv", "description", "region"]'
    )

    # ═══════════════════════════════════════════════════════════
    # COMPLETE: Ready for production use
    # ═══════════════════════════════════════════════════════════
    complete_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL. Example: ["name", "brand", "description", "palate_flavors"]'
    )
    complete_any_of_count = models.IntegerField(
        default=2,
        help_text='Must have at least this many from any_of_fields'
    )
    complete_any_of_fields = models.JSONField(
        default=list,
        help_text='Pool of fields. Example: ["abv", "nose_description", "finish_description"]'
    )

    # ═══════════════════════════════════════════════════════════
    # ENRICHED: Fully enriched with external data
    # ═══════════════════════════════════════════════════════════
    enriched_required_fields = models.JSONField(
        default=list,
        help_text='Must have ALL (inherits COMPLETE + these)'
    )
    enriched_any_of_count = models.IntegerField(
        default=2,
        help_text='Must have at least this many from any_of_fields'
    )
    enriched_any_of_fields = models.JSONField(
        default=list,
        help_text='External data fields: ["awards", "ratings", "prices"]'
    )

    class Meta:
        db_table = "quality_gate_config"
```

**Default Whiskey Quality Gates:**

| Status | Required Fields (ALL) | Any-Of Count | Any-Of Fields (pool) |
|--------|----------------------|--------------|---------------------|
| SKELETON | `["name"]` | 0 | - |
| PARTIAL | `["name", "brand", "abv"]` | 2 | `["description", "region", "country", "volume_ml"]` |
| COMPLETE | `["name", "brand", "abv", "description", "palate_flavors"]` | 2 | `["nose_description", "finish_description", "distillery", "region"]` |
| ENRICHED | (inherits COMPLETE) | 2 | `["awards", "ratings", "prices"]` |

**Note on ABV (Legal Requirement):** ABV is legally required on all spirits labels. The AI must recognize various terms used for alcohol content:
- ABV, abv, Abv
- Alcohol by Volume
- Alcohol Content
- Alc./Vol., Alc/Vol
- Vol%, % Vol, % vol
- Proof (US: divide by 2 for ABV, e.g., 80 proof = 40% ABV)
- Alkoholgehalt (German)
- Titre alcoométrique (French)

### 2.4 EnrichmentConfig

Search templates for progressive enrichment.

```python
class EnrichmentConfig(models.Model):
    """Enrichment search templates for a product type"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    product_type_config = models.ForeignKey(
        ProductTypeConfig,
        on_delete=models.CASCADE,
        related_name='enrichment_templates'
    )

    # Template identity
    template_name = models.CharField(max_length=50)  # e.g., "tasting_notes"
    display_name = models.CharField(max_length=100)

    # Search template with placeholders
    search_template = models.CharField(
        max_length=500,
        help_text='Use placeholders: "{name} {brand} tasting notes review"'
    )

    # What fields this search targets
    target_fields = models.JSONField(
        default=list,
        help_text='Fields this enriches: ["nose_description", "palate_description"]'
    )

    # Priority and status
    priority = models.IntegerField(
        default=5,
        help_text="1-10, higher priority = search first when fields missing"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "enrichment_config"
        ordering = ['-priority']
```

### 2.5 Example Configuration Data

**Whiskey ProductTypeConfig:**

| Field | Value |
|-------|-------|
| product_type | `whiskey` |
| display_name | `Whiskey` |
| categories | `["bourbon", "scotch", "rye", "irish", "japanese", "single_malt", "blended"]` |
| max_sources_per_product | `5` |
| max_serpapi_searches | `3` |
| max_enrichment_time_seconds | `120` |

**Port Wine ProductTypeConfig:**

| Field | Value |
|-------|-------|
| product_type | `port_wine` |
| display_name | `Port Wine` |
| categories | `["ruby", "tawny", "white", "rose", "vintage", "lbv", "colheita", "crusted"]` |
| max_sources_per_product | `4` |
| max_serpapi_searches | `2` |
| max_enrichment_time_seconds | `90` |

**Sample FieldDefinitions (whiskey-specific):**

| field_name | field_type | description | target_model | target_field |
|------------|------------|-------------|--------------|--------------|
| `distillery` | string | "Name of the distillery that produced this whiskey" | WhiskeyDetails | distillery |
| `mash_bill` | string | "Grain composition/recipe" | WhiskeyDetails | mash_bill |
| `peated` | boolean | "Whether whiskey uses peated/smoked malt" | WhiskeyDetails | peated |
| `peat_ppm` | integer | "Phenol PPM measurement" | WhiskeyDetails | peat_ppm |
| `cask_strength` | boolean | "Whether bottled at cask strength" | WhiskeyDetails | cask_strength |

**Sample FieldDefinitions (shared/base):**

| field_name | field_type | description | target_model | target_field |
|------------|------------|-------------|--------------|--------------|
| `name` | string | "Full product name including brand and variant" | DiscoveredProduct | name |
| `brand` | string | "Brand or producer name" | DiscoveredProduct | brand |
| `abv` | decimal | "Alcohol percentage (0-80). Look for: ABV, Alcohol by Volume, Alcohol Content, Alc./Vol., Vol%, % vol, Proof (divide by 2), Alkoholgehalt, Titre alcoométrique" | DiscoveredProduct | abv |
| `nose_description` | text | "Aroma/nose tasting notes" | DiscoveredProduct | nose_description |
| `primary_aromas` | array | "List of primary aroma notes" | DiscoveredProduct | primary_aromas |
| `awards` | array | "Competition awards won" | ProductAward | (creates records) |

---

## 3. Content Preprocessing (Crawler Responsibility)

### 3.1 Why Preprocess?

Raw HTML contains significant clutter that wastes tokens and can confuse AI extraction:

| Content Type | Typical Size | Useful for Extraction |
|--------------|--------------|----------------------|
| Navigation menus | 5-15 KB | No |
| Footer links | 2-10 KB | No |
| JavaScript/CSS | 20-100 KB | No |
| Ads/tracking | 5-20 KB | No |
| Cookie banners | 1-5 KB | No |
| **Main content** | **2-10 KB** | **Yes** |

**Token Cost Analysis:**

| Scenario | Content Size | Est. Tokens | Cost (GPT-4o) |
|----------|--------------|-------------|---------------|
| Raw HTML | 80,000 chars | ~20,000 | $0.60 |
| Cleaned text | 5,000 chars | ~1,250 | $0.04 |
| **Savings** | **94%** | **94%** | **93%** |

### 3.2 Preprocessing Strategy

The **crawler** is responsible for preprocessing before sending to AI Service:

```
Raw HTML (80KB)
    ↓
trafilatura.extract() - removes nav, ads, scripts
    ↓
BeautifulSoup - preserves title/h1 if stripped
    ↓
Cleaned Text (5KB)
    ↓
AI Service /api/v2/extract/
```

### 3.3 Content Types

| Type | When to Use | Preprocessing |
|------|-------------|---------------|
| `cleaned_text` | **Default** - Product pages, articles | trafilatura + title/h1 preservation |
| `structured_html` | List pages with HTML structure needed | Strip scripts/styles, keep structure |
| `raw_html` | Fallback when cleaning fails | None (expensive, use sparingly) |

### 3.4 Preprocessing Implementation

```python
# crawler/services/content_preprocessor.py

import trafilatura
from bs4 import BeautifulSoup

class ContentPreprocessor:
    """Preprocesses HTML before sending to AI Service."""

    def preprocess(
        self,
        raw_html: str,
        preserve_structure: bool = False
    ) -> tuple[str, str]:
        """
        Preprocess HTML for AI extraction.

        Args:
            raw_html: Raw HTML from fetcher
            preserve_structure: Keep HTML structure (for list pages)

        Returns:
            (content, content_type) tuple
        """
        if not raw_html:
            return "", "cleaned_text"

        if preserve_structure:
            return self._clean_structured_html(raw_html), "structured_html"

        return self._extract_clean_text(raw_html), "cleaned_text"

    def _extract_clean_text(self, html: str) -> str:
        """Extract clean text using trafilatura."""
        # Preserve title/h1 that trafilatura might strip
        title, h1 = self._extract_headings(html)

        # Extract main content
        extracted = trafilatura.extract(
            html,
            include_links=False,
            include_images=False,
            include_tables=True,
            output_format="txt",
        )

        if not extracted or len(extracted) < 50:
            # Fallback: basic text extraction
            return self._basic_text_extract(html)

        # Prepend headings if missing
        return self._prepend_headings(extracted, title, h1)

    def _clean_structured_html(self, html: str) -> str:
        """Clean HTML while preserving structure."""
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted elements
        for tag in soup.find_all(['script', 'style', 'nav', 'footer',
                                   'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # Remove common ad/tracking classes
        for elem in soup.find_all(class_=lambda c: c and any(
            x in str(c).lower() for x in ['ad-', 'ads-', 'tracking', 'cookie', 'popup']
        )):
            elem.decompose()

        # Get main content area if exists
        main = soup.find('main') or soup.find('article') or soup.find(id='content')
        if main:
            return str(main)

        return str(soup.body) if soup.body else str(soup)

    def _extract_headings(self, html: str) -> tuple[str, str]:
        """Extract title and h1 from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        h1 = soup.h1.get_text(strip=True) if soup.h1 else ""
        return title, h1

    def _prepend_headings(self, text: str, title: str, h1: str) -> str:
        """Prepend title/h1 if missing from extracted text."""
        prefix = []
        text_lower = text.lower()

        if title and title.lower() not in text_lower:
            clean_title = title.split("|")[0].strip()
            if clean_title:
                prefix.append(f"[Page Title: {clean_title}]")

        if h1 and h1.lower() not in text_lower:
            prefix.append(f"[Product Name: {h1}]")

        if prefix:
            return "\n".join(prefix) + "\n\n" + text
        return text

    def _basic_text_extract(self, html: str) -> str:
        """Fallback text extraction."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
```

### 3.5 When to Preserve Structure

| Page Type | Use `preserve_structure` | Reason |
|-----------|-------------------------|--------|
| Single product page | No | Clean text is sufficient |
| Article/review | No | Clean text is sufficient |
| List page (best of) | **Yes** | Need to identify product boundaries |
| Award results table | **Yes** | Table structure helps extraction |
| Search results | **Yes** | Need to parse result items |

---

## 4. API Contract

### 4.1 Request: `POST /api/v2/extract/`

```json
{
    "source_data": {
        "type": "cleaned_text",
        "content": "[Page Title: Ardbeg 10 Year Old]\n[Product Name: Ardbeg 10 Year Old Single Malt Scotch Whisky]\n\nArdbeg Ten Years Old is revered around the world...",
        "source_url": "https://example.com/product"
    },
    "product_type": "whiskey",
    "product_category": "scotch",
    "extraction_schema": [
        "name", "brand", "description", "abv", "age_statement", "volume_ml",
        "region", "country", "category", "bottler", "gtin",
        "primary_cask", "finishing_cask", "wood_type", "cask_treatment", "maturation_notes",
        "color_description", "clarity", "viscosity",
        "nose_description", "primary_aromas", "secondary_aromas", "aroma_evolution",
        "palate_description", "palate_flavors", "initial_taste", "mid_palate_evolution", "mouthfeel",
        "finish_description", "finish_flavors", "finish_evolution", "final_notes",
        "balance", "overall_complexity", "experience_level", "serving_recommendation", "food_pairings",
        "distillery", "mash_bill", "whiskey_type",
        "cask_strength", "single_cask", "cask_number",
        "vintage_year", "bottling_year", "batch_number",
        "peated", "peat_level", "peat_ppm",
        "natural_color", "non_chill_filtered",
        "awards", "ratings", "prices"
    ],
    "options": {
        "detect_multi_product": true,
        "max_products": 20
    }
}
```

**Key Design Decisions**:
1. The crawler passes a flat list of fields in `extraction_schema` - NO required/optional distinction
2. The AI Service extracts ALL fields from the schema that it can find in the source data
3. The AI Service determines if the source is single-product or multi-product
4. **For multi-product pages, the AI extracts ALL schema fields for EVERY product** - list pages often contain tasting notes, descriptions, ratings, and other rich data
5. The crawler's Quality Gate decides what's "good enough" based on which fields were populated

#### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_data.type` | enum | Yes | `cleaned_text`, `structured_html`, or `raw_html` |
| `source_data.content` | string | Yes | Preprocessed content (max 100,000 chars) |
| `source_data.source_url` | string | No | URL where content came from |
| `product_type` | enum | Yes | `whiskey`, `port_wine` |
| `product_category` | string | No | Subcategory within type (helps AI apply domain-specific extraction) |
| `extraction_schema` | array | Yes | Flat list of field names to extract (no required/optional distinction) |
| `options.detect_multi_product` | bool | No | Auto-detect list pages (default: true) |
| `options.max_products` | int | No | Max products to extract (default: 20) |

#### Product Types and Categories

| Product Type | Valid Categories |
|--------------|------------------|
| `whiskey` | `bourbon`, `scotch`, `rye`, `irish`, `japanese`, `single_malt`, `blended`, `tennessee`, `canadian`, `wheat`, `corn`, `malt` |
| `port_wine` | `tawny`, `ruby`, `vintage`, `lbv`, `colheita`, `white`, `rose`, `crusted`, `reserve`, `fine` |

#### Complete Field Schema Reference

The `extraction_schema` should include all fields the crawler wants to extract. Fields are organized by model source:

**Core Product Fields (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Product name |
| `brand` | string | Brand name |
| `description` | text | Product description |
| `abv` | decimal | Alcohol by volume (0-80%) |
| `age_statement` | string | Age statement (e.g., "12", "18", "NAS") |
| `volume_ml` | int | Bottle volume in milliliters |
| `region` | string | Product region (e.g., Speyside, Kentucky) |
| `country` | string | Country of origin |
| `category` | string | Sub-category (e.g., "Single Malt", "Bourbon") |
| `bottler` | string | Independent bottler name |
| `gtin` | string | Barcode/GTIN for product matching |

**Cask/Maturation Fields (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `primary_cask` | array | Primary cask types (e.g., ["ex-bourbon", "american_oak"]) |
| `finishing_cask` | array | Finishing cask types (e.g., ["sherry", "oloroso"]) |
| `wood_type` | array | Wood types (e.g., ["american_oak", "european_oak"]) |
| `cask_treatment` | array | Cask treatments (e.g., ["charred", "toasted"]) |
| `maturation_notes` | text | Detailed maturation/aging notes |

**Tasting Profile - Appearance (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `color_description` | text | Color description |
| `color_intensity` | int | Color intensity rating 1-10 |
| `clarity` | string | Clarity (e.g., "brilliant", "hazy") |
| `viscosity` | string | Viscosity (e.g., "light", "medium", "oily") |

**Tasting Profile - Nose (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `nose_description` | text | Overall nose/aroma description |
| `primary_aromas` | array | Primary aroma notes (e.g., ["vanilla", "honey"]) |
| `primary_intensity` | int | Primary aroma intensity 1-10 |
| `secondary_aromas` | array | Secondary aroma notes |
| `aroma_evolution` | text | How aromas evolve over time |

**Tasting Profile - Palate (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `palate_description` | text | Overall palate description |
| `palate_flavors` | array | Palate flavor notes (e.g., ["vanilla", "toffee"]) |
| `initial_taste` | text | Initial taste/first impression |
| `mid_palate_evolution` | text | How flavors develop mid-palate |
| `flavor_intensity` | int | Flavor intensity rating 1-10 |
| `complexity` | int | Flavor complexity rating 1-10 |
| `mouthfeel` | string | Mouthfeel (e.g., "oily", "creamy", "thin") |

**Tasting Profile - Finish (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `finish_description` | text | Overall finish description |
| `finish_length` | int | Finish length rating 1-10 |
| `warmth` | int | Warmth/heat rating 1-10 |
| `dryness` | int | Dryness rating 1-10 |
| `finish_flavors` | array | Finish flavor notes |
| `finish_evolution` | text | How finish evolves and fades |
| `final_notes` | text | Final lingering notes |

**Overall Assessment (DiscoveredProduct)**
| Field | Type | Description |
|-------|------|-------------|
| `balance` | int | Overall balance rating 1-10 |
| `overall_complexity` | int | Overall complexity rating 1-10 |
| `uniqueness` | int | Uniqueness rating 1-10 |
| `drinkability` | int | Drinkability rating 1-10 |
| `price_quality_ratio` | int | Price-quality ratio 1-10 |
| `experience_level` | string | Recommended level (e.g., "beginner", "enthusiast") |
| `serving_recommendation` | string | Serving suggestion (e.g., "neat", "on the rocks") |
| `food_pairings` | text | Recommended food pairings |

**Whiskey-Specific Fields (WhiskeyDetails)**
| Field | Type | Description |
|-------|------|-------------|
| `whiskey_type` | string | Type of whiskey (bourbon, scotch, rye, etc.) |
| `distillery` | string | Distillery name |
| `mash_bill` | string | Grain composition |
| `cask_strength` | bool | Whether cask strength release |
| `single_cask` | bool | Whether from single cask |
| `cask_number` | string | Cask number for single cask releases |
| `vintage_year` | int | Year of distillation |
| `bottling_year` | int | Year of bottling |
| `batch_number` | string | Batch number |
| `peated` | bool | Whether peated |
| `peat_level` | string | Peat level (unpeated, lightly, heavily) |
| `peat_ppm` | int | Phenol PPM measurement |
| `natural_color` | bool | No E150a color added |
| `non_chill_filtered` | bool | Non-chill filtered |

**Port Wine-Specific Fields (PortWineDetails)**
| Field | Type | Description |
|-------|------|-------------|
| `style` | string | Port style (ruby, tawny, vintage, LBV, etc.) |
| `indication_age` | string | Age indication (e.g., "20 Year") |
| `harvest_year` | int | Year of harvest/vintage |
| `bottling_year` | int | Year of bottling |
| `grape_varieties` | array | Grape varieties used |
| `quinta` | string | Quinta (estate) name |
| `douro_subregion` | string | Douro subregion |
| `producer_house` | string | Port house/producer name |
| `aging_vessel` | string | Type of aging vessel |
| `decanting_required` | bool | Whether decanting recommended |
| `drinking_window` | string | Optimal drinking window |

**Related Data Fields**
| Field | Type | Description |
|-------|------|-------------|
| `awards` | array | Awards: [{competition, year, medal, category, score}] |
| `ratings` | array | Ratings: [{source, score, max_score, reviewer, date}] |
| `prices` | array | Prices: [{retailer, price, currency, url, in_stock}] |
| `images` | array | Images: [{url, type}] |

### 4.2 Response: Single Product

```json
{
    "success": true,
    "is_multi_product": false,
    "product_count": 1,
    "products": [
        {
            "product_type": "whiskey",
            "product_category": "rye",
            "type_confidence": 0.95,
            "extracted_data": {
                "name": "Bulleit Straight Rye",
                "brand": "Bulleit",
                "description": "A bold, spicy rye whiskey with exceptional complexity...",
                "abv": 45.0,
                "age_statement": null,
                "volume_ml": 750,
                "region": "Kentucky",
                "country": "USA",
                "category": "Rye Whiskey",
                "nose_description": "Vanilla, honey and spice notes with subtle oak undertones",
                "primary_aromas": ["vanilla", "honey", "spice", "oak"],
                "palate_description": "Oak, pepper, and dried fruit dominate with a creamy mouthfeel",
                "palate_flavors": ["oak", "pepper", "dried fruit", "caramel"],
                "mouthfeel": "creamy",
                "finish_description": "Long, warm, and spicy with lingering vanilla",
                "finish_length": 7,
                "warmth": 6,
                "finish_flavors": ["vanilla", "spice", "oak"],
                "whiskey_type": "rye",
                "distillery": "Bulleit Distilling Co",
                "mash_bill": "95% rye, 5% malted barley",
                "cask_strength": false,
                "peated": false
            },
            "field_confidences": {
                "name": 0.99,
                "brand": 0.98,
                "description": 0.90,
                "abv": 0.95,
                "age_statement": null,
                "volume_ml": 0.90,
                "region": 0.85,
                "country": 0.95,
                "category": 0.88,
                "nose_description": 0.85,
                "primary_aromas": 0.82,
                "palate_description": 0.85,
                "palate_flavors": 0.80,
                "mouthfeel": 0.75,
                "finish_description": 0.85,
                "finish_length": 0.70,
                "warmth": 0.70,
                "finish_flavors": 0.78,
                "whiskey_type": 0.95,
                "distillery": 0.92,
                "mash_bill": 0.88,
                "cask_strength": 0.85,
                "peated": 0.90
            },
            "extraction_summary": {
                "fields_found": ["name", "brand", "description", "abv", "volume_ml", "region", "country", "category", "nose_description", "primary_aromas", "palate_description", "palate_flavors", "mouthfeel", "finish_description", "finish_length", "warmth", "finish_flavors", "whiskey_type", "distillery", "mash_bill", "cask_strength", "peated"],
                "fields_missing": ["age_statement", "gtin", "vintage_year", "bottling_year"],
                "fields_not_in_source": ["age_statement", "gtin", "vintage_year", "bottling_year"]
            }
        }
    ],
    "processing_time_ms": 1250,
    "token_usage": {
        "prompt_tokens": 1500,
        "completion_tokens": 400,
        "total_tokens": 1900
    }
}
```

### 4.3 Response: Multi-Product (List Page)

**IMPORTANT**: The AI Service extracts ALL fields from `extraction_schema` for EVERY product, regardless of whether it's a single-product or multi-product page. Many list pages include tasting notes, descriptions, ratings, and other rich data that should be captured.

```json
{
    "success": true,
    "is_multi_product": true,
    "product_count": 3,
    "list_metadata": {
        "list_type": "best_of",
        "total_detected": 10,
        "extracted": 3,
        "truncated": true
    },
    "products": [
        {
            "product_type": "whiskey",
            "product_category": "bourbon",
            "type_confidence": 0.88,
            "extracted_data": {
                "name": "Buffalo Trace Kentucky Straight Bourbon",
                "brand": "Buffalo Trace",
                "description": "A rich, complex bourbon with notes of vanilla, toffee, and candied fruit",
                "abv": 45.0,
                "region": "Kentucky",
                "country": "USA",
                "category": "Bourbon",
                "nose_description": "Vanilla, mint, and molasses aromas",
                "primary_aromas": ["vanilla", "mint", "molasses", "toffee"],
                "palate_description": "Complex with notes of brown sugar, spice, and oak",
                "palate_flavors": ["brown sugar", "spice", "oak", "anise"],
                "finish_description": "Long and smooth with lingering toffee",
                "distillery": "Buffalo Trace Distillery",
                "detail_url": "https://example.com/buffalo-trace",
                "awards": [
                    {"competition": "San Francisco World Spirits", "year": 2023, "medal": "Double Gold"}
                ]
            },
            "field_confidences": {
                "name": 0.95,
                "brand": 0.90,
                "description": 0.85,
                "abv": 0.92,
                "nose_description": 0.80,
                "palate_description": 0.82,
                "finish_description": 0.78,
                "distillery": 0.88,
                "detail_url": 0.99,
                "awards": 0.90
            },
            "extraction_summary": {
                "fields_found": ["name", "brand", "description", "abv", "region", "country", "category", "nose_description", "primary_aromas", "palate_description", "palate_flavors", "finish_description", "distillery", "detail_url", "awards"],
                "fields_missing": ["age_statement", "volume_ml", "mash_bill"],
                "fields_not_in_source": ["age_statement", "volume_ml", "mash_bill"]
            }
        },
        {
            "product_type": "whiskey",
            "product_category": "rye",
            "type_confidence": 0.85,
            "extracted_data": {
                "name": "Sazerac Straight Rye",
                "brand": "Sazerac",
                "description": "Spicy and full-bodied with a hint of sweetness",
                "abv": 45.0,
                "category": "Rye Whiskey",
                "palate_description": "Pepper, clove, and subtle fruit notes",
                "palate_flavors": ["pepper", "clove", "fruit"],
                "detail_url": "https://example.com/sazerac-rye"
            },
            "extraction_summary": {
                "fields_found": ["name", "brand", "description", "abv", "category", "palate_description", "palate_flavors", "detail_url"],
                "fields_missing": ["nose_description", "finish_description", "distillery"],
                "fields_not_in_source": ["nose_description", "finish_description", "distillery"]
            }
        },
        {
            "product_type": "whiskey",
            "product_category": "bourbon",
            "type_confidence": 0.82,
            "extracted_data": {
                "name": "Woodford Reserve",
                "brand": "Woodford Reserve",
                "detail_url": "https://example.com/woodford"
            },
            "extraction_summary": {
                "fields_found": ["name", "brand", "detail_url"],
                "fields_missing": ["description", "abv", "nose_description", "palate_description"],
                "fields_not_in_source": ["description", "abv", "nose_description", "palate_description"]
            }
        }
    ],
    "processing_time_ms": 2100
}
```

Note: The example above shows varying levels of data richness per product - some list pages provide extensive tasting notes and descriptions (product 1), others have partial data (product 2), and some have minimal data (product 3). The AI Service extracts ALL available data for each product.

### 4.4 Response: Error

```json
{
    "success": false,
    "error": {
        "code": "EXTRACTION_FAILED",
        "message": "Unable to extract product information from source",
        "details": {
            "reason": "Content appears to be a non-product page",
            "source_type_detected": "navigation_page"
        }
    },
    "processing_time_ms": 450
}
```

---

## 5. Crawler Quality Gate System

### 5.1 Product Status Flow

```
SKELETON ────────→ PARTIAL ─────────────→ COMPLETE ────────────────→ ENRICHED
   ↑                  ↑                       ↑                          ↑
   │                  │                       │                          │
 name               + brand                 + description              + awards
 only               + ABV                   + palate_flavors           + ratings
                    + 2 of:                 + 2 of:                    + prices
                      (description,           (nose_description,
                       region,                 finish_description,
                       country,                distillery,
                       volume_ml)              region)

Logic: STATUS = (ALL required_fields) AND (N or more from any_of_fields)
```

**Default Whiskey Quality Gates:**

| Status | Required Fields (ALL must be present) | Any-Of Count | Any-Of Fields (pool to pick from) |
|--------|--------------------------------------|--------------|----------------------------------|
| SKELETON | `["name"]` | 0 | - |
| PARTIAL | `["name", "brand", "abv"]` | 2 | `["description", "region", "country", "volume_ml"]` |
| COMPLETE | `["name", "brand", "abv", "description", "palate_flavors"]` | 2 | `["nose_description", "finish_description", "distillery", "region"]` |
| ENRICHED | (inherits COMPLETE requirements) | 2 | `["awards", "ratings", "prices"]` |

**Note:** ABV is legally required on all spirits labels and must be present from PARTIAL status onward.

### 5.2 Quality Thresholds (Configuration-Driven)

Quality thresholds are **loaded from database** via `QualityGateConfig` model (see Section 2.3).

```python
class QualityGateEvaluator:
    """Evaluates product data against configuration-driven quality gates."""

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    def evaluate(self, product_type: str, extracted_data: Dict) -> str:
        """
        Determine product status based on QualityGateConfig.

        Returns: "skeleton", "partial", "complete", or "enriched"
        """
        config = self.config_service.get_quality_gate_config(product_type)
        present_fields = {k for k, v in extracted_data.items() if v is not None}

        # Check each status level (highest to lowest)
        if self._meets_status(present_fields, config, "enriched"):
            return "enriched"
        if self._meets_status(present_fields, config, "complete"):
            return "complete"
        if self._meets_status(present_fields, config, "partial"):
            return "partial"
        if self._meets_status(present_fields, config, "skeleton"):
            return "skeleton"
        return "rejected"

    def _meets_status(self, present: Set[str], config, status: str) -> bool:
        """
        Check if present fields meet status requirements.

        Logic: (ALL required_fields) AND (N or more from any_of_fields)
        """
        required = set(getattr(config, f"{status}_required_fields", []))
        any_of = set(getattr(config, f"{status}_any_of_fields", []))
        any_of_count = getattr(config, f"{status}_any_of_count", 0)

        # All required fields must be present
        if not required.issubset(present):
            return False

        # Must have at least N from any_of pool
        if any_of_count > 0:
            matched = len(present.intersection(any_of))
            if matched < any_of_count:
                return False

        return True

    # Confidence thresholds (global settings)
    MIN_FIELD_CONFIDENCE = 0.6
    MIN_TYPE_CONFIDENCE = 0.7
```

**Port Wine Quality Gates** (similar structure with port-specific fields):

| Status | Required Fields (ALL) | Any-Of Count | Any-Of Fields (pool) |
|--------|----------------------|--------------|---------------------|
| SKELETON | `["name"]` | 0 | - |
| PARTIAL | `["name", "brand", "abv"]` | 2 | `["description", "port_style", "vintage", "volume_ml"]` |
| COMPLETE | `["name", "brand", "abv", "description", "palate_flavors", "port_style"]` | 2 | `["nose_description", "finish_description", "producer", "region"]` |
| ENRICHED | (inherits COMPLETE) | 2 | `["awards", "ratings", "prices"]` |

### 5.3 Quality Gate Class

```python
@dataclass
class QualityAssessment:
    """Result of quality assessment."""
    save_decision: bool
    status: str  # "rejected", "skeleton", "partial", "complete", "enriched"
    completeness_score: float  # 0-100
    fields_present: List[str]
    fields_missing_for_next_status: List[str]
    needs_enrichment: bool
    enrichment_priority: int  # 1=high, 2=medium, 3=low
    rejection_reason: Optional[str] = None


class QualityGate:
    """Crawler-side quality assessment using configuration-driven thresholds."""

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service
        self.evaluator = QualityGateEvaluator(config_service)

    def assess(
        self,
        extracted_data: Dict,
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None
    ) -> QualityAssessment:
        """
        Assess extracted data against QualityGateConfig thresholds.

        Uses configuration-driven logic:
        STATUS = (ALL required_fields) AND (N or more from any_of_fields)
        """
        # Filter out None values and low-confidence fields
        present_fields = self._get_present_fields(extracted_data, field_confidences)

        # Determine status using config-driven evaluator
        status = self.evaluator.evaluate(product_type, extracted_data)

        # Get config for enrichment decisions
        config = self.config_service.get_quality_gate_config(product_type)

        # Calculate what's missing for next status level
        missing_for_next = self._get_missing_for_next_status(
            status, present_fields, config
        )

        # Determine enrichment needs
        needs_enrichment = status in ("skeleton", "partial")
        enrichment_priority = {"rejected": 0, "skeleton": 1, "partial": 2,
                               "complete": 3, "enriched": 3}.get(status, 2)

        return QualityAssessment(
            save_decision=(status != "rejected"),
            status=status,
            completeness_score=self._calculate_completeness(present_fields, config),
            fields_present=list(present_fields),
            fields_missing_for_next_status=missing_for_next,
            needs_enrichment=needs_enrichment,
            enrichment_priority=enrichment_priority,
            rejection_reason="No name found" if status == "rejected" else None
        )

    def _get_present_fields(
        self,
        data: Dict,
        confidences: Optional[Dict[str, float]]
    ) -> Set[str]:
        """Get fields that are present and meet confidence threshold."""
        MIN_CONFIDENCE = 0.6
        present = set()
        for field, value in data.items():
            if value is None:
                continue
            if confidences and confidences.get(field, 1.0) < MIN_CONFIDENCE:
                continue
            present.add(field)
        return present

    def _get_missing_for_next_status(
        self,
        current_status: str,
        present: Set[str],
        config
    ) -> List[str]:
        """Determine what fields are needed to reach next status level."""
        next_status_map = {
            "rejected": "skeleton",
            "skeleton": "partial",
            "partial": "complete",
            "complete": "enriched"
        }
        next_status = next_status_map.get(current_status)
        if not next_status:
            return []

        required = set(getattr(config, f"{next_status}_required_fields", []))
        return list(required - present)

    def _calculate_completeness(self, present: Set[str], config) -> float:
        """Calculate 0-100 completeness score based on COMPLETE requirements."""
        complete_required = set(config.complete_required_fields or [])
        complete_any_of = set(config.complete_any_of_fields or [])
        complete_any_of_count = config.complete_any_of_count or 0

        total_needed = len(complete_required) + complete_any_of_count
        if total_needed == 0:
            return 100.0

        required_met = len(present.intersection(complete_required))
        any_of_met = min(len(present.intersection(complete_any_of)), complete_any_of_count)

        return round((required_met + any_of_met) / total_needed * 100, 1)
```

---

## 6. Enrichment Orchestrator

### 6.1 Enrichment Flow

```
Product with missing fields
    ↓
Search for additional sources (SerpAPI)
    ↓
For each source (up to MAX_SOURCES):
    ├── Fetch content
    ├── Call AI Service /api/v2/extract/
    ├── Merge new data (prefer higher confidence)
    └── Re-assess quality
    ↓
If COMPLETE status reached → Stop
Else if limits hit → Save as PARTIAL
    ↓
Update product in database
```

### 6.2 Enrichment Limits (Configuration-Driven)

Enrichment limits are loaded from `ProductTypeConfig` model (see Section 2.1):

```python
class EnrichmentOrchestrator:
    """Orchestrates progressive enrichment using config-driven limits."""

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    def enrich_product(self, product_type: str, product_data: Dict) -> Dict:
        """Enrich product data within configured limits."""
        config = self.config_service.get_product_type_config(product_type)

        # Load limits from config (adjustable per product type)
        max_sources = config.max_sources_per_product      # default: 5
        max_searches = config.max_serpapi_searches        # default: 3
        max_time = config.max_enrichment_time_seconds     # default: 120

        # ... enrichment logic using these limits ...
```

**Default Limits:**

| Product Type | Max Sources | Max Searches | Max Time (s) |
|--------------|-------------|--------------|--------------|
| whiskey | 5 | 3 | 120 |
| port_wine | 4 | 2 | 90 |

These can be adjusted via Django Admin without code changes.

### 6.3 Data Merging Strategy

When merging data from multiple sources:

1. **Empty field** → Accept new value
2. **Existing field** → Keep if confidence higher, replace if new confidence > existing + 0.1
3. **Conflicting values** → Keep both with source attribution, flag for review

### 6.4 Source Tracking and Content Archival

All crawled URLs are stored in `CrawledSource` with full provenance tracking, enabling users to view original articles and providing permanent references via Internet Archive.

#### 6.4.1 CrawledSource Model Updates

Add `preprocessed_content` field to existing `CrawledSource` model:

```python
class CrawledSource(models.Model):
    """Stores crawled article/page data with content archival."""

    # ... existing fields ...

    # Raw Content
    raw_content = models.TextField(
        blank=True,
        null=True,
        help_text="Raw HTML content of the page",
    )

    # NEW: Preprocessed Content (trafilatura output)
    preprocessed_content = models.TextField(
        blank=True,
        null=True,
        help_text="Cleaned text content (trafilatura output) for summaries/excerpts",
    )
    preprocessed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When content was preprocessed",
    )

    # Cleanup tracking
    raw_content_cleared = models.BooleanField(
        default=False,
        help_text="Whether raw content has been cleared after processing",
    )
    cleanup_eligible = models.BooleanField(
        default=False,
        help_text="Ready for raw_content cleanup (extraction + wayback complete)",
    )

    # Wayback Machine (existing)
    wayback_url = models.URLField(max_length=500, blank=True, null=True)
    wayback_saved_at = models.DateTimeField(blank=True, null=True)
    wayback_status = models.CharField(
        max_length=20,
        choices=WaybackStatusChoices.choices,
        default=WaybackStatusChoices.PENDING,
    )
```

#### 6.4.2 Crawl → Store → Archive Flow

```
URL Crawled
    ↓
┌─────────────────────────────────────────────────────────┐
│  1. Store in CrawledSource                               │
│     - raw_content = HTML                                 │
│     - content_hash = SHA-256(HTML)                       │
│     - extraction_status = PENDING                        │
│     - wayback_status = PENDING                           │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  2. Preprocess Content (async)                           │
│     - preprocessed_content = trafilatura(raw_content)    │
│     - preprocessed_at = now()                            │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  3. AI Extraction                                        │
│     - Pass preprocessed_content to AI Service            │
│     - On success: extraction_status = PROCESSED          │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  4. Link Products to Source                              │
│     - Create ProductSource record for each product       │
│     - Create ProductFieldSource for field-level tracking │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  5. Wayback Machine Archive (async job)                  │
│     - POST to https://web.archive.org/save/{url}         │
│     - On success: wayback_url, wayback_saved_at          │
│     - wayback_status = SAVED                             │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  6. Cleanup (when both complete)                         │
│     - IF extraction_status = PROCESSED                   │
│     - AND wayback_status = SAVED                         │
│     - THEN: raw_content = NULL, raw_content_cleared = T  │
│     - KEEP: preprocessed_content (for summaries/excerpts)│
└─────────────────────────────────────────────────────────┘
```

#### 6.4.3 Internet Archive Integration

```python
class WaybackService:
    """Async service to archive URLs to Internet Archive."""

    SAVE_URL = "https://web.archive.org/save/"
    CHECK_URL = "https://archive.org/wayback/available"

    async def archive_url(self, crawled_source: CrawledSource) -> bool:
        """
        Submit URL to Wayback Machine for archival.

        Called async after crawl completes. Retries on failure.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.SAVE_URL}{crawled_source.url}",
                    timeout=30.0,
                    follow_redirects=True
                )

                if response.status_code == 200:
                    # Extract archive URL from response
                    archive_url = self._extract_archive_url(response)
                    crawled_source.wayback_url = archive_url
                    crawled_source.wayback_saved_at = timezone.now()
                    crawled_source.wayback_status = WaybackStatusChoices.SAVED
                    crawled_source.save()
                    return True

        except Exception as e:
            crawled_source.wayback_status = WaybackStatusChoices.FAILED
            crawled_source.last_crawl_error = str(e)
            crawled_source.save()
            return False

    def check_cleanup_eligible(self, crawled_source: CrawledSource) -> bool:
        """Check if source is ready for raw_content cleanup."""
        return (
            crawled_source.extraction_status == ExtractionStatusChoices.PROCESSED
            and crawled_source.wayback_status == WaybackStatusChoices.SAVED
        )
```

#### 6.4.4 User-Facing Source Links

Products link to their sources via `ProductSource`, enabling UI to show:

```python
# Get source URLs for a product
product = DiscoveredProduct.objects.get(id=product_id)
sources = ProductSource.objects.filter(product=product).select_related('source')

for ps in sources:
    print(f"Original: {ps.source.url}")
    print(f"Archived: {ps.source.wayback_url}")  # Permanent reference
    print(f"Excerpt: {ps.source.preprocessed_content[:500]}...")
```

#### 6.4.5 Preprocessed Content Uses

The `preprocessed_content` field enables:

1. **Article Excerpts** - Show snippet in product detail view
2. **Summaries** - Generate AI summaries without re-crawling
3. **Re-extraction** - Re-run AI extraction with updated prompts
4. **Search** - Full-text search across crawled content
5. **Deduplication** - Compare content across sources

---

## 7. List Page Handling

### 7.1 Detection

The AI Service auto-detects list pages when `detect_multi_product: true`.

Indicators:
- Multiple product names in content
- List/table structure with repeated patterns
- URLs like `/best-*`, `/top-*`, `/awards/*`

### 7.2 Processing Flow

```
List page URL
    ↓
Fetch content
    ↓
AI Service extracts all products (up to max_products)
    ↓
For each extracted product:
    ├── Run through QualityGate
    ├── If has detail_url → Queue for detailed extraction
    ├── Else → Save as SKELETON, queue for enrichment
    └── Continue
```

### 7.3 List Types

| Type | Example | Expected Fields |
|------|---------|-----------------|
| `best_of` | "Best Whiskeys 2024" | name, brand, maybe description |
| `awards` | "IWSC Winners" | name, brand, award, medal |
| `comparison` | "Bourbon vs Rye" | name, brand, brief notes |
| `gift_guide` | "Gift Guide" | name, brand, price |

---

## 8. AI Service Implementation

### 8.1 Prompt Strategy

The AI Service builds prompts based on:
1. `product_type` - Determines extraction template
2. `product_category` - Refines field expectations
3. `extraction_fields` - What to look for

```python
def build_extraction_prompt(
    content: str,
    product_type: str,
    product_category: Optional[str],
    fields: List[str]
) -> str:
    """Build extraction prompt."""

    type_context = get_type_context(product_type, product_category)
    field_descriptions = get_field_descriptions(fields, product_type)

    return f"""Extract {product_type} product information from the content below.

{type_context}

Fields to extract:
{field_descriptions}

Rules:
1. Extract ALL information that is present in the source
2. Use null for fields not found in source
3. Do NOT hallucinate or invent information
4. If multiple products found, extract all (up to limit)
5. Include confidence score (0-1) for each field

Content:
{content[:15000]}

Return JSON matching the specified schema."""
```

### 8.2 Type-Specific Context

```python
TYPE_CONTEXTS = {
    "whiskey": {
        "description": "Whiskey/whisky is a distilled spirit made from fermented grain mash.",
        "common_fields": ["distillery", "age_statement", "cask_type", "abv", "proof"],
        "categories": {
            "bourbon": "American whiskey, 51%+ corn, new charred oak barrels",
            "scotch": "Scottish whisky, aged 3+ years in oak",
            "rye": "51%+ rye grain in mashbill",
            ...
        }
    },
    "port_wine": {
        "description": "Port is a fortified wine from Portugal's Douro Valley.",
        "common_fields": ["vintage", "producer", "grape_varieties", "sweetness"],
        "categories": {
            "tawny": "Aged in wood, nutty/caramel flavors",
            "ruby": "Fruit-forward, less wood aging",
            "vintage": "Single vintage, 2+ years bottle aging",
            ...
        }
    }
}
```

---

## 9. Data Models

### 9.1 Extraction Request Schema

```python
class ExtractionRequest(BaseModel):
    source_data: SourceData
    product_type: ProductType
    product_category: Optional[str] = None
    extraction_fields: ExtractionFields
    options: ExtractionOptions = ExtractionOptions()

class SourceData(BaseModel):
    type: Literal["cleaned_text", "structured_html", "raw_html"]
    content: str = Field(..., max_length=100000)
    source_url: Optional[str] = None

class ProductType(str, Enum):
    WHISKEY = "whiskey"
    PORT_WINE = "port_wine"

class ExtractionFields(BaseModel):
    required: List[str] = ["name"]
    optional: List[str] = []

class ExtractionOptions(BaseModel):
    detect_multi_product: bool = True
    max_products: int = Field(default=20, ge=1, le=50)
```

### 9.2 Extraction Response Schema

```python
class ExtractionResponse(BaseModel):
    success: bool
    is_multi_product: bool
    product_count: int
    list_metadata: Optional[ListMetadata] = None
    products: List[ExtractedProduct]
    processing_time_ms: int
    token_usage: Optional[TokenUsage] = None
    error: Optional[ExtractionError] = None

class ExtractedProduct(BaseModel):
    product_type: str
    product_category: Optional[str]
    type_confidence: float
    extracted_data: Dict[str, Any]
    field_confidences: Dict[str, Optional[float]]
    extraction_summary: ExtractionSummary

class ExtractionSummary(BaseModel):
    fields_found: List[str]
    fields_missing: List[str]
    fields_not_in_source: List[str]
```

---

## 10. Error Handling

### 10.1 AI Service Errors

| Error Code | Meaning | Crawler Action |
|------------|---------|----------------|
| `EXTRACTION_FAILED` | Could not extract any data | Try different source |
| `INVALID_CONTENT` | Content not processable | Skip URL |
| `RATE_LIMITED` | OpenAI rate limit | Retry with backoff |
| `TIMEOUT` | Processing took too long | Retry or skip |
| `INVALID_PRODUCT_TYPE` | Unknown product type | Log error, skip |

### 10.2 Crawler Error Handling

```python
async def extract_with_retry(url: str, max_retries: int = 3):
    for attempt in range(max_retries):
        result = await ai_client.extract(...)

        if result.success:
            return result

        if result.error.code == "RATE_LIMITED":
            await asyncio.sleep(2 ** attempt)
            continue

        if result.error.code in ["INVALID_CONTENT", "INVALID_PRODUCT_TYPE"]:
            break  # Don't retry

    return None
```

---

## 11. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Products from IWSC per crawl | 50+ | Count after crawl |
| List page extraction rate | 80%+ | Products found / pages processed |
| Field extraction accuracy | 90%+ | Manual review sample |
| Enrichment success rate | 70%+ | PARTIAL → COMPLETE conversions |
| Average fields per product | 10+ | Database query |
| Processing time per product | < 5s | AI Service logs |

---

## 12. Implementation Notes

### 12.1 Technology Stack

- **AI Service**: FastAPI, Pydantic, OpenAI GPT-4o
- **Crawler**: Django, asyncio, httpx
- **Testing**: pytest, pytest-asyncio, TDD approach

### 12.2 Key Files to Create/Modify

**AI Service:**
- `ai_enhancement_engine/api/v2/endpoints.py` - New V2 endpoint
- `ai_enhancement_engine/api/v2/schemas.py` - Request/response schemas
- `ai_enhancement_engine/services/extractor_v2.py` - Extraction logic
- `ai_enhancement_engine/prompts/extraction_prompts.py` - Prompt templates

**Crawler:**
- `crawler/services/content_preprocessor.py` - HTML preprocessing (trafilatura + BeautifulSoup)
- `crawler/services/quality_gate.py` - Quality assessment
- `crawler/services/enrichment_orchestrator.py` - Progressive enrichment
- `crawler/services/ai_client_v2.py` - V2 API client
- `crawler/services/discovery_orchestrator.py` - Update to use V2

### 12.3 Testing Strategy

- **Unit tests**: All new classes and functions
- **Integration tests**: Crawler ↔ AI Service communication
- **E2E tests**: Full flow from URL to saved product
- **TDD**: Write tests before implementation
