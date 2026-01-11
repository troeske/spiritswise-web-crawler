# Unified Product Discovery Flow Analysis & Refactoring Spec

## Executive Summary

This document analyzes three product discovery flows in the crawler and proposes a unified architecture. Since we are in development phase (not production), we can make breaking changes without backward compatibility concerns.

**The Three Flows:**
1. **Award/Competition Discovery** - Creates skeleton products from structured competition pages
2. **Generic Search List Pages** - Extracts multiple products from blog/review articles
3. **Single Product Enhancement** - Full extraction from individual product pages

**Key Insight:** All three flows ultimately do the same thing - discover product data and save it. They differ only in:
- How they identify products (structured parser vs AI vs direct URL)
- How much data they extract initially
- When/how they enrich incomplete data

---

## CRITICAL REQUIREMENTS

### Requirement 1: Mandatory Tasting Profile

A product **CANNOT** be marked as COMPLETE or VERIFIED without tasting profile data.

**Minimum Required for COMPLETE:**
- `palate_flavors` (at least 2 tags) OR `palate_description` OR `initial_taste`

**Additional Required for VERIFIED:**
- Nose profile: `nose_description` OR `primary_aromas` (2+ tags)
- Finish profile: `finish_description` OR `finish_flavors` (2+ tags)
- Multi-source verification: `source_count >= 2`

### Requirement 2: Multi-Source Verification

Products discovered from one source **MUST** be enriched from additional sources to:
1. Verify extracted data accuracy (if 2 sources agree, field is verified)
2. Fill in missing fields (especially tasting profile)
3. Build confidence through consensus

**Target:** 2-3 sources per product before VERIFIED status.

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

### Requirement 3: No JSON Blobs for Searchable Data

**WRONG (current implementation):**
```python
extracted_data = models.JSONField(default=dict)  # Catch-all blob
enriched_data = models.JSONField(default=dict)   # Another blob
taste_profile = models.JSONField(default=dict)   # Yet another blob
```

**RIGHT (new implementation):**
```python
# Individual searchable/filterable columns
name = models.CharField(max_length=500)
abv = models.DecimalField(...)
palate_description = models.TextField(...)
finish_length = models.IntegerField(...)

# JSONField ONLY for:
# - Arrays of tags (primary_aromas, palate_flavors) - OK
# - Rarely-queried metadata
# - Truly dynamic/extensible data
```

### Requirement 4: Model Split

Keep separation between:
- **DiscoveredProduct** - Core product data + tasting profile + status
- **WhiskeyDetails** - Whiskey-only fields (distillery, peated, peat_level, mash_bill, etc.)
- **PortWineDetails** - Port-only fields (style, quinta, harvest_year, grape_varieties, etc.)

---

## 1. Award/Competition Parser Gaps & Enhancements

### 1.1 Current Parser Limitations

The current IWSC parser extracts:
- Product name ✓
- Medal (Gold/Silver/Bronze) ✓
- Score ✓
- Country ✓

**Missing extractions:**
| Field | Available on IWSC? | Current Status |
|-------|-------------------|----------------|
| Tasting notes | Yes (many entries) | NOT extracted |
| Category details | Yes ("unpeated", "10 Year Tawny") | NOT parsed |
| Style (for Port) | Yes (Wine + Fortified) | NOT filtered/extracted |
| Age indication | In category string | NOT parsed |

### 1.2 BeautifulSoup vs AI for Award Sites

**Recommendation: Hybrid Approach**

| Data Type | Method | Reason |
|-----------|--------|--------|
| Product name | BeautifulSoup | Structured HTML element |
| Medal/Score | BeautifulSoup | Structured/predictable |
| Country/Region | BeautifulSoup | Structured element |
| Category string | BeautifulSoup | Structured element |
| **Tasting notes** | **AI** | Free-text, needs semantic parsing |
| **Parse category → style/age** | **AI** | "10 Year Tawny" → style=tawny, indication_age="10 Year" |

**Implementation:**
```python
class IWSCParser:
    def parse(self, html: str, year: int) -> List[ProductCandidate]:
        # 1. BeautifulSoup extracts structured data
        candidates = self._extract_with_beautifulsoup(html, year)

        # 2. For each candidate, if tasting notes section exists:
        for candidate in candidates:
            if self._has_tasting_section(candidate.raw_element):
                # Use AI to extract tasting profile from free text
                tasting = await self.ai_client.extract_tasting_notes(
                    candidate.tasting_text
                )
                candidate.update_tasting(tasting)

            # 3. Parse category string for style/age
            if candidate.category:
                parsed = self._parse_category_info(candidate.category)
                candidate.update_from_category(parsed)

        return candidates

    def _parse_category_info(self, category: str) -> dict:
        """
        Parse category string for embedded info.

        Examples:
        - "Scotch Single Malt Whisky 16-20 Years" → age_range="16-20"
        - "10 Year Tawny Port" → style="tawny", indication_age="10 Year"
        - "Unpeated Single Malt" → peated=False
        - "Heavily Peated Islay" → peated=True, peat_level="heavily_peated"
        """
        result = {}
        category_lower = category.lower()

        # Peat detection
        if "unpeated" in category_lower:
            result["peated"] = False
        elif "heavily peated" in category_lower:
            result["peated"] = True
            result["peat_level"] = "heavily_peated"
        elif "lightly peated" in category_lower:
            result["peated"] = True
            result["peat_level"] = "lightly_peated"

        # Age indication for port
        age_match = re.search(r"(\d+)\s*year", category_lower)
        if age_match:
            result["indication_age"] = f"{age_match.group(1)} Year"

        # Port style detection
        for style in ["tawny", "ruby", "vintage", "lbv", "colheita"]:
            if style in category_lower:
                result["style"] = style
                break

        return result
```

### 1.3 Port Wine on IWSC

**Current Issue:** Port wines on IWSC are listed under:
- Category: "Wine"
- Style: "Fortified"

The current parser does NOT filter for this. We need:

```python
# In competition_orchestrator.py or IWSCParser

IWSC_PORT_WINE_FILTERS = {
    "category": "Wine",
    "style": "Fortified",
    # Or specific subcategories:
    "subcategories": [
        "Aged Tawny Port",
        "Ruby Port",
        "Vintage Port",
        "Late Bottled Vintage",
        "Colheita",
        "White Port",
    ]
}

def is_port_wine(result: dict) -> bool:
    """Check if IWSC result is a port wine."""
    category = (result.get("category") or "").lower()
    style = (result.get("style") or "").lower()

    # Direct category match
    if any(pc.lower() in category for pc in IWSC_PORT_WINE_FILTERS["subcategories"]):
        return True

    # Category + Style match
    if "wine" in category and "fortified" in style:
        return True

    return False
```

**Action Required:**
1. Update IWSC parser to extract category and style fields
2. Add `is_port_wine()` filter function
3. Route port wine results to PortWineDetails creation
4. Parse category string to extract `indication_age` and `style`

### 1.4 Award Site Detail Pages & AI Extraction

**Critical Finding:** IWSC has detail pages for each medal winner that we're currently ignoring!

Example: `https://www.iwsc.net/results/detail/157656/10-yo-tawny-nv` (10 Year Old Tawny Port)

**Current Implementation Gap:**
```
CURRENT (WRONG):
┌─────────────────────┐
│ IWSC Listing Page   │ ──► Extract from cards only (name, medal, country)
│ /results/search/    │
└─────────────────────┘
        ↓
        ✗ IGNORES detail page links: /results/detail/157656/...
        ✗ MISSES tasting notes, full descriptions, etc.
```

**Proposed Architecture: URL Collector → AI Extraction**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: URL COLLECTION (Specialized per site)        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ IWSCCollector (BeautifulSoup)                                    │  │
│  │                                                                  │  │
│  │ • Navigate pagination on /results/search/{year}                  │  │
│  │ • Filter by category (Whisky, Wine+Fortified for Port)          │  │
│  │ • Extract detail page URLs from cards                           │  │
│  │ • Extract medal hints from card images                          │  │
│  │ • Detect product type (whiskey vs port_wine)                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│         ┌────────────────────────────────────────────────────────┐     │
│         │ Award URL Queue                                         │     │
│         │ [{detail_url, medal_hint, competition, year, type}, ...]│     │
│         └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LAYER 2: AI EXTRACTION (Unified)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ For each detail_url:                                             │  │
│  │                                                                  │  │
│  │ 1. Fetch detail page HTML                                        │  │
│  │ 2. Pass to AI Extractor with enhanced prompt:                   │  │
│  │    - Competition context (IWSC 2025)                            │  │
│  │    - Medal hint (Gold, 95 points)                               │  │
│  │    - Product type hint (port_wine)                              │  │
│  │                                                                  │  │
│  │ 3. AI extracts ALL available data:                              │  │
│  │    - Product name, brand, producer                              │  │
│  │    - Tasting notes (nose, palate, finish)                       │  │
│  │    - Category details, age indication                           │  │
│  │    - Country, region                                            │  │
│  │    - Any other descriptive text                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│                    ProductCandidate (with award data)                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LAYER 3: VERIFICATION PIPELINE                        │
│                                                                         │
│  • If still missing tasting notes → search additional sources           │
│  • Verify data from 2-3 sources                                         │
│  • Calculate completeness (tasting = 40%)                               │
│  • Set status (INCOMPLETE → PARTIAL → COMPLETE → VERIFIED)              │
└─────────────────────────────────────────────────────────────────────────┘
```

**Why AI Extraction for Award Detail Pages:**

| Benefit | Explanation |
|---------|-------------|
| **Unified code path** | Same AI extractor for awards, reviews, official sites |
| **Extracts everything** | Won't miss tasting notes if available |
| **Handles variations** | IWSC 2024 layout ≠ 2025 layout - AI adapts |
| **Less maintenance** | No parser updates when HTML structure changes |
| **Consistent output** | Always produces `ProductCandidate` format |

**IWSCCollector Implementation:**

```python
@dataclass
class AwardDetailURL:
    """URL collected from award site for AI extraction."""
    detail_url: str        # e.g., "/results/detail/157656/10-yo-tawny-nv"
    listing_url: str       # The listing page we found it on
    medal_hint: str        # From listing card image/class ("Gold", "Silver")
    score_hint: Optional[int]  # From listing card if available (95)
    competition: str       # "IWSC"
    year: int              # 2025
    product_type_hint: str # "port_wine" or "whiskey"


class IWSCCollector:
    """
    Collects detail page URLs from IWSC listing pages.

    Replaces IWSCParser - we no longer extract data here,
    just collect URLs for AI extraction.
    """

    BASE_URL = "https://www.iwsc.net"

    def collect(self, listing_html: str, year: int) -> List[AwardDetailURL]:
        """
        Parse listing page and extract detail page URLs.

        Args:
            listing_html: HTML of /results/search/{year} page
            year: Competition year

        Returns:
            List of AwardDetailURL for AI extraction
        """
        soup = BeautifulSoup(listing_html, "lxml")
        urls = []

        for card in soup.select(".c-card--listing"):
            # Get detail page link
            link = card.select_one("a[href*='/results/detail/']")
            if not link:
                continue

            detail_url = urljoin(self.BASE_URL, link.get("href"))

            # Extract medal hint from award image
            medal_hint, score_hint = self._extract_medal_from_card(card)

            # Detect product type from card text/category
            product_type = self._detect_product_type(card)

            urls.append(AwardDetailURL(
                detail_url=detail_url,
                listing_url=f"{self.BASE_URL}/results/search/{year}",
                medal_hint=medal_hint,
                score_hint=score_hint,
                competition="IWSC",
                year=year,
                product_type_hint=product_type,
            ))

        return urls

    def _extract_medal_from_card(self, card) -> Tuple[str, Optional[int]]:
        """Extract medal type and score from card's award image."""
        medal = "Award"
        score = None

        awards_wrapper = card.select_one(".c-card--listing__awards-wrapper")
        if awards_wrapper:
            award_img = awards_wrapper.select_one("img")
            if award_img:
                img_src = award_img.get("data-src") or award_img.get("src") or ""

                # URL pattern: iwsc2025-gold-95-medal.png
                medal_match = re.search(r"(gold|silver|bronze)-?(\d+)?-?medal", img_src.lower())
                if medal_match:
                    medal = medal_match.group(1).capitalize()
                    if medal_match.group(2):
                        score = int(medal_match.group(2))

        return medal, score

    def _detect_product_type(self, card) -> str:
        """Detect if this is whiskey, port wine, etc."""
        text = card.get_text().lower()

        # Port wine indicators
        port_indicators = ["tawny", "ruby", "vintage port", "lbv", "colheita",
                          "fortified", "douro", "graham", "taylor", "fonseca"]
        if any(x in text for x in port_indicators):
            return "port_wine"

        # Whiskey indicators
        whiskey_indicators = ["whisky", "whiskey", "bourbon", "scotch", "malt",
                             "rye", "single grain", "blended"]
        if any(x in text for x in whiskey_indicators):
            return "whiskey"

        return "unknown"

    def collect_all_years(self, years: List[int]) -> List[AwardDetailURL]:
        """Collect URLs from multiple years."""
        all_urls = []
        for year in years:
            html = self._fetch_listing_page(year)
            urls = self.collect(html, year)
            all_urls.extend(urls)
            # Handle pagination if needed
            all_urls.extend(self._collect_paginated(year))
        return all_urls
```

**Enhanced AI Prompt for Award Pages:**

```python
AWARD_EXTRACTION_PROMPT = """
Extract ALL product information from this award competition detail page.

Context:
- Competition: {competition}
- Year: {year}
- Medal (from listing): {medal_hint}
- Score (if available): {score_hint}
- Expected product type: {product_type_hint}

Extract everything available including:
1. IDENTIFICATION: Product name, brand, producer
2. BASIC INFO: ABV, age statement, volume, country, region
3. TASTING NOTES: Nose, palate, finish (capture full descriptions)
4. CATEGORY DETAILS: Style (tawny/ruby/etc), age indication, whiskey type
5. AWARD: Confirm medal, extract any additional award details

For Port Wine, also extract:
- Port style (tawny, ruby, vintage, LBV, colheita)
- Age indication ("10 Year", "20 Year")
- Producer house, Quinta name
- Grape varieties if mentioned

For Whiskey, also extract:
- Whiskey type (single malt, bourbon, etc.)
- Distillery name
- Peat level if mentioned
- Cask type if mentioned

Page content:
{content}
"""
```

### 1.5 Decanter World Wine Awards (DWWA) - JavaScript-Rendered Site

**DWWA is critical for Port Wine** - It's the world's largest wine competition with excellent fortified wine coverage.

**Detail Page Example:** `https://awards.decanter.com/DWWA/2025/wines/768949`

**Key Challenges:**

| Challenge | Description |
|-----------|-------------|
| **JavaScript-rendered** | Site requires browser to render - no static HTML |
| **Port wines from any country** | Port-style wines from South Africa, Australia, etc. |
| **Complex filtering** | Need to filter by "Fortified" category, not just "Port" |
| **Proprietary structure** | No public API documentation |

**What We Know:**
- Detail URL pattern: `https://awards.decanter.com/DWWA/{year}/wines/{wine_id}`
- Detail pages contain rich data: tasting notes, scores, producer info
- Port wines are in "Fortified" category (not just Portugal region)
- Requires headless browser (Playwright) to render JavaScript

**DWWA Collector Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DWWA COLLECTOR (Playwright-based)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 1: Browser Automation                                       │  │
│  │                                                                  │  │
│  │ • Launch Playwright headless browser                            │  │
│  │ • Navigate to awards.decanter.com                               │  │
│  │ • Wait for JavaScript to render                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 2: Apply Filters for Port/Fortified                        │  │
│  │                                                                  │  │
│  │ • Filter by Category: "Fortified" (captures all port styles)    │  │
│  │ • Filter by Year: 2024, 2025, etc.                              │  │
│  │ • Optionally filter by Medal: Gold, Silver, Bronze              │  │
│  │ • DO NOT filter by Country (port can be from anywhere)          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 3: Paginate and Collect URLs                               │  │
│  │                                                                  │  │
│  │ • Click through pagination or infinite scroll                   │  │
│  │ • Extract detail page URLs for each wine                        │  │
│  │ • Detect port wine styles from listing text                     │  │
│  │ • Extract medal hints from listing                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│         ┌────────────────────────────────────────────────────────┐     │
│         │ Award URL Queue                                         │     │
│         │ [{detail_url, medal_hint, style_hint}, ...]             │     │
│         └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI EXTRACTION (same as IWSC)                          │
│                                                                         │
│  • Fetch detail page (may need Playwright for JS rendering)            │
│  • Pass to unified AI extractor                                        │
│  • Extract: name, producer, tasting notes, style, vintage, score       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Port Wine Style Detection (from DWWA categories):**

```python
# DWWA uses "Fortified" as main category
# Port styles appear in wine name or sub-category

DWWA_PORT_INDICATORS = {
    "styles": [
        "tawny", "ruby", "vintage", "lbv", "late bottled vintage",
        "colheita", "crusted", "white port", "rosé port", "pink port",
        "single quinta", "garrafeira",
    ],
    "producers": [
        # Portuguese houses
        "taylor", "graham", "fonseca", "sandeman", "dow", "warre",
        "cockburn", "croft", "quinta do noval", "niepoort", "ramos pinto",
        "ferreira", "kopke", "burmester", "churchill",
        # Non-Portuguese producers making port-style wines
        "galpin peak", "boplaas", "allesverloren",  # South Africa
        "seppeltsfield", "yalumba",  # Australia
    ],
    "regions": [
        "douro", "porto", "portugal",
        # But also check non-Portugal origins:
        "south africa", "australia", "usa", "california",
    ]
}

def is_port_wine_dwwa(wine_data: dict) -> bool:
    """
    Determine if DWWA wine is a port or port-style wine.

    Important: Port-style wines can come from ANY country,
    not just Portugal. E.g., South African "Cape Port".
    """
    name = (wine_data.get("name") or "").lower()
    category = (wine_data.get("category") or "").lower()
    producer = (wine_data.get("producer") or "").lower()

    # Must be in Fortified category
    if "fortified" not in category:
        return False

    # Check for port style indicators
    for style in DWWA_PORT_INDICATORS["styles"]:
        if style in name:
            return True

    # Check for known port producers
    for prod in DWWA_PORT_INDICATORS["producers"]:
        if prod in producer or prod in name:
            return True

    # Check for explicit "port" in name
    if "port" in name:
        return True

    return False
```

**DWWACollector Implementation:**

```python
class DWWACollector:
    """
    Collects Port/Fortified wine detail page URLs from Decanter World Wine Awards.

    Requires Playwright for JavaScript rendering.
    """

    BASE_URL = "https://awards.decanter.com"

    async def collect(self, year: int) -> List[AwardDetailURL]:
        """
        Collect all fortified wine URLs for a given year.

        Uses Playwright to:
        1. Navigate to search page
        2. Apply "Fortified" filter
        3. Paginate through results
        4. Extract detail page URLs
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate and wait for JS to load
            await page.goto(f"{self.BASE_URL}/DWWA/{year}")
            await page.wait_for_selector("[data-filter='category']", timeout=10000)

            # Apply Fortified filter
            await self._apply_fortified_filter(page)

            # Collect URLs from all pages
            urls = []
            while True:
                # Extract URLs from current page
                page_urls = await self._extract_urls_from_page(page, year)
                urls.extend(page_urls)

                # Try to go to next page
                if not await self._go_to_next_page(page):
                    break

            await browser.close()
            return urls

    async def _apply_fortified_filter(self, page):
        """Apply filter for Fortified wines."""
        # Click category dropdown
        await page.click("[data-filter='category']")
        # Select Fortified
        await page.click("text=Fortified")
        # Wait for results to reload
        await page.wait_for_load_state("networkidle")

    async def _extract_urls_from_page(self, page, year: int) -> List[AwardDetailURL]:
        """Extract wine detail URLs from current results page."""
        urls = []

        # Get all wine cards
        cards = await page.query_selector_all(".wine-card, .result-item, [data-wine-id]")

        for card in cards:
            # Extract detail URL
            link = await card.query_selector("a[href*='/wines/']")
            if not link:
                continue

            href = await link.get_attribute("href")
            detail_url = urljoin(self.BASE_URL, href)

            # Extract hints from card
            card_text = await card.inner_text()
            medal_hint = self._extract_medal_hint(card_text)
            style_hint = self._detect_port_style(card_text)

            # Only include if it looks like port wine
            if self._is_likely_port(card_text):
                urls.append(AwardDetailURL(
                    detail_url=detail_url,
                    listing_url=f"{self.BASE_URL}/DWWA/{year}",
                    medal_hint=medal_hint,
                    score_hint=self._extract_score(card_text),
                    competition="DWWA",
                    year=year,
                    product_type_hint="port_wine",
                    style_hint=style_hint,  # tawny, ruby, vintage, etc.
                ))

        return urls

    def _is_likely_port(self, text: str) -> bool:
        """Check if wine is likely a port or port-style wine."""
        text_lower = text.lower()

        # Direct port indicators
        if "port" in text_lower:
            return True

        # Port style indicators
        for style in DWWA_PORT_INDICATORS["styles"]:
            if style in text_lower:
                return True

        # Known port producers
        for producer in DWWA_PORT_INDICATORS["producers"]:
            if producer in text_lower:
                return True

        return False

    def _detect_port_style(self, text: str) -> Optional[str]:
        """Detect port style from text."""
        text_lower = text.lower()

        style_mapping = {
            "tawny": "tawny",
            "ruby": "ruby",
            "vintage": "vintage",
            "lbv": "lbv",
            "late bottled": "lbv",
            "colheita": "colheita",
            "white port": "white",
            "rosé": "rose",
            "pink": "rose",
            "crusted": "crusted",
            "single quinta": "single_quinta",
            "garrafeira": "garrafeira",
        }

        for indicator, style in style_mapping.items():
            if indicator in text_lower:
                return style

        return None
```

**Enhanced AI Prompt for DWWA Port Wines:**

```python
DWWA_PORT_EXTRACTION_PROMPT = """
Extract ALL product information from this Decanter World Wine Awards detail page.

Context:
- Competition: Decanter World Wine Awards (DWWA)
- Year: {year}
- Medal (from listing): {medal_hint}
- Score (if available): {score_hint}
- Detected style: {style_hint}
- Category: Fortified Wine / Port

This is a PORT WINE or PORT-STYLE WINE. Extract:

1. IDENTIFICATION:
   - Full wine name
   - Producer/House name
   - Brand (if different from producer)

2. PORT-SPECIFIC DETAILS:
   - Style (tawny, ruby, vintage, LBV, colheita, white, rosé, crusted)
   - Age indication ("10 Year", "20 Year", "40 Year")
   - Vintage year (if vintage/colheita)
   - Single Quinta name (if applicable)

3. TASTING NOTES (CRITICAL):
   - Nose/Aroma description
   - Palate description
   - Finish description
   - Any flavor descriptors

4. TECHNICAL:
   - ABV
   - Score (points out of 100)
   - Medal (Platinum, Gold, Silver, Bronze, Commended)
   - Price if shown

5. ORIGIN:
   - Country (may NOT be Portugal for port-style wines)
   - Region (Douro, Cape, Barossa, etc.)
   - Grape varieties

Page content:
{content}
"""
```

**Key Point: Port Wines from Non-Portuguese Origins**

DWWA awards wines from around the world. Port-style wines can come from:
- **South Africa**: "Cape Port" (now "Cape Vintage", "Cape Ruby", "Cape Tawny")
- **Australia**: Fortified wines from Barossa, Rutherglen
- **USA**: California port-style wines
- **Others**: Any country producing fortified wines in port style

The collector must NOT filter by country - filter by "Fortified" category and then detect port styles.

---

## 2. Current Flow Analysis

### 2.1 Award/Competition Discovery Flow (Current)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT: Competition HTML (IWSC, SFWSC, WWA page)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │  Site-Specific BeautifulSoup Parser │  ◄── Deterministic            │
│  │  (parsers.py)                       │      Structured extraction    │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  SkeletonProductManager             │                               │
│  │  • Creates DiscoveredProduct        │                               │
│  │  • status = SKELETON                │  ◄── Minimal data only       │
│  │  • Creates ProductAward             │                               │
│  │  • confidence = 0.7                 │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼  SEPARATE PHASE (deferred)                        │
│  ┌─────────────────────────────────────┐                               │
│  │  EnrichmentSearcher                 │                               │
│  │  • 3x SerpAPI searches per skeleton │  ◄── High API cost           │
│  │  • "{name} price buy online"        │                               │
│  │  • "{name} review tasting notes"    │                               │
│  │  • "{name} official site"           │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  URL Frontier Queue                 │  ◄── Queued for later        │
│  │  (priority = 10)                    │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼  ANOTHER SEPARATE PHASE                           │
│  ┌─────────────────────────────────────┐                               │
│  │  ContentProcessor + AI Enhancement  │                               │
│  │  • Full extraction from URL         │                               │
│  │  • Updates skeleton → PENDING       │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
│  OUTPUT: DiscoveredProduct (PENDING) with full data                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Characteristics:**
| Aspect | Value |
|--------|-------|
| Extraction | BeautifulSoup (deterministic) |
| Initial Status | SKELETON |
| Initial Data | Name, brand, award only |
| Enrichment | Deferred (3-phase process) |
| SerpAPI Calls | 3 per skeleton (always) |
| AI Calls | 1 per enrichment URL |
| Total Steps | 4+ |

---

### 1.2 Generic Search List Page Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT: List Page HTML (blog, review site, "Top 10" article)           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │  AI List Extraction                 │  ◄── Probabilistic           │
│  │  _call_ai_list_extraction()         │      LLM-based extraction    │
│  │  • Identifies all products on page  │                               │
│  │  • Extracts names, links, data      │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼  FOR EACH PRODUCT                                 │
│  ┌─────────────────────────────────────┐                               │
│  │  _enrich_product_from_list()        │                               │
│  │                                     │                               │
│  │  Strategy 1: Has direct link?       │                               │
│  │    → SmartCrawler.extract_product() │  ◄── Immediate enrichment    │
│  │    → Full AI enhancement            │                               │
│  │                                     │                               │
│  │  Strategy 2: No link?               │                               │
│  │    → SerpAPI search for product     │  ◄── Search only if needed   │
│  │    → Crawl best result              │                               │
│  │                                     │                               │
│  │  Strategy 3: Search failed?         │                               │
│  │    → Save with available data       │  ◄── Partial product         │
│  │    → Mark as "partial"              │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  save_discovered_product()          │                               │
│  │  • status = PENDING                 │                               │
│  │  • May be marked "partial"          │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
│  OUTPUT: DiscoveredProduct (PENDING) - may be partial or complete     │
└─────────────────────────────────────────────────────────────────────────┘
```

**Characteristics:**
| Aspect | Value |
|--------|-------|
| Extraction | AI/LLM (probabilistic) |
| Initial Status | PENDING (skips SKELETON) |
| Initial Data | All available from page |
| Enrichment | Immediate (same process) |
| SerpAPI Calls | 0-1 per product (only if no link) |
| AI Calls | 1 for list + 0-1 per product |
| Total Steps | 2-3 |

---

### 1.3 Single Product Enhancement Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT: Single Product Page URL                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Entry Points:                                                          │
│  • ContentProcessor.process(url, content)                              │
│  • SmartCrawler.extract_product(name, url)                             │
│  • Enrichment queue processing                                         │
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │  SmartRouter.fetch(url)             │                               │
│  │  • Tier 1: httpx                    │                               │
│  │  • Tier 2: Playwright               │                               │
│  │  • Tier 3: ScrapingBee              │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  trafilatura.extract()              │  ◄── HTML → clean text        │
│  │  • Removes nav, ads, boilerplate    │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  AIEnhancementClient.enhance()      │  ◄── Full AI extraction      │
│  │  • Extracts ALL product fields      │                               │
│  │  • Tasting profile (nose/palate/    │                               │
│  │    finish)                          │                               │
│  │  • Awards, ratings, images          │                               │
│  │  • Per-field confidence scores      │                               │
│  └─────────────────────────────────────┘                               │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────┐                               │
│  │  save_discovered_product()          │                               │
│  │  • Creates DiscoveredProduct        │                               │
│  │  • Creates WhiskeyDetails or        │                               │
│  │    PortWineDetails                  │                               │
│  │  • Creates ProductAward records     │                               │
│  │  • Creates ProductRating records    │                               │
│  │  • Creates ProductImage records     │                               │
│  │  • Creates ProductFieldSource       │                               │
│  │    provenance records               │                               │
│  │  • status = PENDING                 │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
│  OUTPUT: DiscoveredProduct (PENDING) with full data + provenance       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Characteristics:**
| Aspect | Value |
|--------|-------|
| Extraction | AI/LLM (full extraction) |
| Initial Status | PENDING |
| Initial Data | Complete (all fields) |
| Enrichment | N/A (already complete) |
| SerpAPI Calls | 0 (URL already known) |
| AI Calls | 1 |
| Total Steps | 2 |

---

## 3. Comparative Analysis

### 3.1 Flow Comparison Matrix

| Aspect | Award Flow | List Page Flow | Single Product Flow |
|--------|------------|----------------|---------------------|
| **Input** | Competition HTML | Article/Blog HTML | Product Page URL |
| **Products per Page** | Many (10-100+) | Multiple (3-20) | 1 |
| **Extraction Method** | BeautifulSoup | AI List Extraction | AI Full Extraction |
| **Initial Product Status** | SKELETON | PENDING | PENDING |
| **Needs Enrichment?** | Always | Sometimes | Never |
| **SerpAPI Calls** | 3 per product | 0-1 per product | 0 |
| **AI Calls** | 0 initial, 1+ later | 1 list + 0-1 per | 1 |
| **Total Phases** | 4+ | 2-3 | 2 |
| **URL Queue Used?** | Yes | No | No |
| **Creates Awards?** | Yes (directly) | Maybe (from AI) | Maybe (from AI) |

### 3.2 Code Path Analysis

```
                    ┌─────────────────────┐
                    │  Product Discovery  │
                    └─────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Award Flow    │   │ List Flow     │   │ Single Flow   │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ parsers.py    │   │ discovery_    │   │ content_      │
│ skeleton_     │   │ orchestrator  │   │ processor.py  │
│ manager.py    │   │ .py           │   │               │
│ enrichment_   │   │               │   │ smart_        │
│ searcher.py   │   │ smart_        │   │ crawler.py    │
│ competition_  │   │ crawler.py    │   │               │
│ orchestrator  │   │               │   │ ai_client.py  │
│ .py           │   │ ai_client.py  │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ save_discovered_    │  ◄── Only unified point
                    │ product()           │
                    │ (product_saver.py)  │
                    └─────────────────────┘
```

**Key Observation:** The only unified point is `save_discovered_product()`. Everything before it is duplicated logic across three different code paths.

---

## 3. Identified Problems

### 3.1 Architectural Issues

| Problem | Description | Impact |
|---------|-------------|--------|
| **3 Code Paths** | Same goal, 3 different implementations | Hard to maintain, bugs in one path |
| **Status Inconsistency** | SKELETON vs PENDING, no clear semantics | Confusing queries, unclear completeness |
| **Duplicated Dedup** | Each flow has own deduplication | Inconsistent duplicate detection |
| **Enrichment Waste** | Award flow always does 3 searches | High API cost, often unnecessary |
| **Deferred vs Immediate** | Award enriches later, others immediate | Stale skeletons, complex scheduling |

### 3.2 Specific Code Issues

**Issue 1: Skeleton Status Is Meaningless Outside Award Flow**
```python
# skeleton_manager.py - creates SKELETON
product.status = DiscoveredProductStatus.SKELETON

# discovery_orchestrator.py - never creates SKELETON
# Goes directly to PENDING

# content_processor.py - never creates SKELETON
# Goes directly to PENDING
```

**Issue 2: Three Different Deduplication Implementations**

```python
# skeleton_manager.py:97-99
existing = DiscoveredProduct.objects.filter(
    Q(fingerprint=fingerprint) | Q(name__iexact=product_name)
).first()

# discovery_orchestrator.py:710-733
def _find_existing_product(self, url, name):
    # Check URL match, CrawledSource path, fingerprint
    ...

# product_saver.py:1494-1520
def save_discovered_product(...):
    # Check fingerprint match
    existing = DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()
```

**Issue 3: Award Flow Always Wastes 3 SerpAPI Calls**
```python
# enrichment_searcher.py - ALWAYS does all 3 searches
SEARCH_TEMPLATES = {
    "price": "{product_name} price buy online",
    "review": "{product_name} review tasting notes",
    "official": "{product_name} official site",
}
# No check if data already exists!
```

**Issue 4: Different Data Normalization**
```python
# Competition flow normalizes award data one way
award_entry = {
    "competition": award_data.get("competition", "Unknown"),
    "year": award_data.get("year", timezone.now().year),
    "medal": award_data.get("medal", "gold"),
}

# AI extraction returns data differently
# product_saver has to handle both formats
```

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

---

## 7. Multi-Source Verification Pipeline

### 7.1 Verification Flow

```python
class VerificationPipeline:
    """
    Pipeline that enriches products from multiple sources.
    Goal: Every product should be verified from 2+ sources before VERIFIED status.
    """

    TARGET_SOURCES = 3
    MIN_SOURCES_FOR_VERIFIED = 2

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
    }

    async def verify_product(self, candidate: ProductCandidate) -> VerificationResult:
        """
        Steps:
        1. Save initial product (from first source)
        2. Identify missing/unverified fields
        3. Search for additional sources
        4. Extract data from each source
        5. Merge and verify data (if values match = verified)
        6. Update completeness and status
        """
        product = await self._get_or_create_product(candidate)
        sources_used = 1

        missing = self._get_missing_critical_fields(product)
        needs_verification = self._get_unverified_fields(product)

        if missing or needs_verification or sources_used < self.TARGET_SOURCES:
            search_results = await self._search_additional_sources(product, missing)

            for source_url in search_results[:self.TARGET_SOURCES - 1]:
                extraction = await self._extract_from_source(source_url, product)
                if extraction.success:
                    await self._merge_and_verify(product, extraction)
                    sources_used += 1

        product.source_count = sources_used
        product.completeness_score = calculate_completeness(product)
        product.status = determine_status(product)
        await self._save_product(product)

        return VerificationResult(product=product, sources_used=sources_used)

    def _get_missing_critical_fields(self, product) -> List[str]:
        """Especially: palate, nose, finish, abv, description."""
        missing = []
        if not product.palate_flavors and not product.palate_description:
            missing.append("palate")
        if not product.nose_description and not product.primary_aromas:
            missing.append("nose")
        if not product.finish_description and not product.finish_flavors:
            missing.append("finish")
        return missing

    async def _merge_and_verify(self, product, extraction):
        """
        Merge new data, marking verified fields.
        If values match = field is verified!
        """
        verified = list(product.verified_fields or [])

        for field, new_value in extraction.data.items():
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
                # Values differ - log conflict
                await self._log_conflict(product, field, current_value, new_value)

        product.verified_fields = verified
```

---

## 8. Implementation Plan

### 8.1 Core Data Structures

**ProductCandidate - Unified Intermediate Format:**
```python
# crawler/discovery/product_candidate.py

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
from enum import Enum


class ExtractionSource(str, Enum):
    """How the product was initially extracted."""
    COMPETITION_PARSER = "competition_parser"  # BeautifulSoup from award site
    AI_LIST_EXTRACTION = "ai_list_extraction"  # LLM from list page
    AI_SINGLE_EXTRACTION = "ai_single_extraction"  # LLM from product page
    MANUAL = "manual"  # User-provided data


@dataclass
class ProductCandidate:
    """
    Unified intermediate format for all product discovery flows.

    This is the single data structure that ALL extractors produce,
    regardless of source type.
    """

    # === IDENTIFICATION ===
    name: str
    brand: Optional[str] = None

    # === SOURCE INFO ===
    extraction_source: ExtractionSource = ExtractionSource.AI_SINGLE_EXTRACTION
    source_url: str = ""
    direct_product_link: Optional[str] = None  # If we have a link to crawl

    # === PRODUCT DATA ===
    product_type: str = "whiskey"
    extracted_data: Dict[str, Any] = field(default_factory=dict)

    # === STRUCTURED DATA (extracted from extracted_data for convenience) ===
    abv: Optional[float] = None
    age_statement: Optional[str] = None
    volume_ml: Optional[int] = None
    description: Optional[str] = None

    # === TASTING PROFILE ===
    tasting_notes: Optional[str] = None
    nose_description: Optional[str] = None
    palate_flavors: Optional[List[str]] = None
    finish_description: Optional[str] = None

    # === RELATED DATA ===
    awards: List[Dict[str, Any]] = field(default_factory=list)
    ratings: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    prices: List[Dict[str, Any]] = field(default_factory=list)

    # === QUALITY INDICATORS ===
    extraction_confidence: float = 0.5
    field_confidences: Dict[str, float] = field(default_factory=dict)

    # === COMPUTED PROPERTIES ===
    @property
    def has_tasting_notes(self) -> bool:
        return bool(
            self.tasting_notes or
            self.nose_description or
            self.palate_flavors or
            self.finish_description
        )

    @property
    def has_pricing(self) -> bool:
        return len(self.prices) > 0

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def has_ratings(self) -> bool:
        return len(self.ratings) > 0

    @property
    def has_awards(self) -> bool:
        return len(self.awards) > 0

    @property
    def completeness_score(self) -> int:
        """Calculate how complete this candidate's data is."""
        score = 0

        # Required (40 points)
        if self.name: score += 20
        if self.brand: score += 10
        if self.product_type: score += 10

        # Important (30 points)
        if self.has_tasting_notes: score += 15
        if self.description: score += 10
        if self.abv: score += 5

        # Nice to have (30 points)
        if self.has_pricing: score += 10
        if self.has_images: score += 10
        if self.has_ratings: score += 5
        if self.has_awards: score += 5

        return min(score, 100)

    def needs_enrichment(self, threshold: int = 50) -> bool:
        """Check if this candidate needs additional enrichment."""
        return self.completeness_score < threshold

    def get_missing_data_types(self) -> List[str]:
        """Return list of data types that are missing."""
        missing = []
        if not self.has_tasting_notes:
            missing.append("tasting_notes")
        if not self.has_pricing:
            missing.append("pricing")
        if not self.has_images:
            missing.append("images")
        if not self.description:
            missing.append("description")
        return missing

    def to_extracted_data(self) -> Dict[str, Any]:
        """Convert to format expected by save_discovered_product."""
        data = {
            "name": self.name,
            "brand": self.brand,
            "product_type": self.product_type,
            "abv": self.abv,
            "age_statement": self.age_statement,
            "volume_ml": self.volume_ml,
            "description": self.description,
            "tasting_notes": self.tasting_notes,
            "nose_description": self.nose_description,
            "palate_flavors": self.palate_flavors,
            "finish_description": self.finish_description,
            **self.extracted_data,
        }

        if self.awards:
            data["awards"] = self.awards
        if self.ratings:
            data["ratings"] = self.ratings
        if self.images:
            data["images"] = self.images

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_competition_result(cls, result: Dict[str, Any]) -> "ProductCandidate":
        """Create ProductCandidate from competition parser output."""
        return cls(
            name=result.get("product_name", ""),
            brand=result.get("producer"),
            extraction_source=ExtractionSource.COMPETITION_PARSER,
            product_type=cls._infer_product_type(result),
            awards=[{
                "competition": result.get("competition"),
                "year": result.get("year"),
                "medal": result.get("medal"),
                "category": result.get("category"),
            }],
            extraction_confidence=0.85,  # High for structured data
        )

    @classmethod
    def from_ai_extraction(cls, data: Dict[str, Any], source_url: str) -> "ProductCandidate":
        """Create ProductCandidate from AI extraction output."""
        return cls(
            name=data.get("name", ""),
            brand=data.get("brand"),
            extraction_source=ExtractionSource.AI_SINGLE_EXTRACTION,
            source_url=source_url,
            product_type=data.get("product_type", "whiskey"),
            extracted_data=data,
            abv=data.get("abv"),
            age_statement=data.get("age_statement"),
            description=data.get("description"),
            tasting_notes=data.get("tasting_notes"),
            nose_description=data.get("nose_description"),
            palate_flavors=data.get("palate_flavors"),
            awards=data.get("awards", []),
            ratings=data.get("ratings", []),
            images=data.get("images", []),
            extraction_confidence=data.get("confidence", 0.7),
        )

    @staticmethod
    def _infer_product_type(data: Dict[str, Any]) -> str:
        """Infer product type from data."""
        category = (data.get("category") or "").lower()
        if any(k in category for k in ["whisky", "whiskey", "bourbon", "scotch"]):
            return "whiskey"
        if any(k in category for k in ["port", "porto"]):
            return "port_wine"
        return "whiskey"
```

### 8.2 Unified Processing Pipeline

```python
# crawler/services/product_pipeline.py

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from crawler.models import DiscoveredProduct
from crawler.discovery.product_candidate import ProductCandidate, ExtractionSource
from crawler.services.product_saver import save_discovered_product, ProductSaveResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of processing a ProductCandidate through the pipeline."""
    product: Optional[DiscoveredProduct]
    created: bool
    was_duplicate: bool
    was_enriched: bool
    enrichment_source: Optional[str]
    completeness_before: int
    completeness_after: int
    error: Optional[str] = None


class ProductPipeline:
    """
    Unified processing pipeline for all product discovery flows.

    Takes a ProductCandidate and:
    1. Checks for duplicates
    2. Evaluates completeness
    3. Enriches if needed and possible
    4. Saves the product
    """

    # Completeness threshold below which we attempt enrichment
    ENRICHMENT_THRESHOLD = 50

    # Minimum completeness to save a product
    MINIMUM_COMPLETENESS = 20

    def __init__(
        self,
        smart_crawler=None,
        serpapi_client=None,
        ai_client=None,
        enable_enrichment: bool = True,
    ):
        self.smart_crawler = smart_crawler
        self.serpapi_client = serpapi_client
        self.ai_client = ai_client
        self.enable_enrichment = enable_enrichment

    async def process(
        self,
        candidate: ProductCandidate,
        force_enrichment: bool = False,
        skip_enrichment: bool = False,
    ) -> PipelineResult:
        """
        Process a ProductCandidate through the full pipeline.

        Args:
            candidate: The product candidate to process
            force_enrichment: Force enrichment even if completeness is high
            skip_enrichment: Skip enrichment entirely

        Returns:
            PipelineResult with the created/updated product
        """
        result = PipelineResult(
            product=None,
            created=False,
            was_duplicate=False,
            was_enriched=False,
            enrichment_source=None,
            completeness_before=candidate.completeness_score,
            completeness_after=candidate.completeness_score,
        )

        # Validate minimum data
        if not candidate.name:
            result.error = "Product name is required"
            return result

        # Step 1: Check for duplicate
        existing = await self._find_duplicate(candidate)
        if existing:
            result.was_duplicate = True
            result.product = await self._merge_into_existing(existing, candidate)
            result.completeness_after = self._get_product_completeness(result.product)
            return result

        # Step 2: Evaluate completeness and enrich if needed
        if (
            self.enable_enrichment and
            not skip_enrichment and
            (force_enrichment or candidate.needs_enrichment(self.ENRICHMENT_THRESHOLD))
        ):
            enriched_candidate, enrichment_source = await self._enrich(candidate)
            if enriched_candidate:
                candidate = enriched_candidate
                result.was_enriched = True
                result.enrichment_source = enrichment_source

        # Step 3: Save the product
        if candidate.completeness_score < self.MINIMUM_COMPLETENESS:
            result.error = f"Completeness {candidate.completeness_score} below minimum {self.MINIMUM_COMPLETENESS}"
            return result

        save_result = await self._save(candidate)
        result.product = save_result.product
        result.created = save_result.created
        result.completeness_after = candidate.completeness_score

        return result

    async def process_batch(
        self,
        candidates: List[ProductCandidate],
        **kwargs,
    ) -> List[PipelineResult]:
        """Process multiple candidates."""
        results = []
        for candidate in candidates:
            result = await self.process(candidate, **kwargs)
            results.append(result)
        return results

    async def _find_duplicate(
        self,
        candidate: ProductCandidate,
    ) -> Optional[DiscoveredProduct]:
        """Find existing product that matches this candidate."""
        from asgiref.sync import sync_to_async
        from django.db.models import Q

        # Compute fingerprint
        fingerprint = DiscoveredProduct.compute_fingerprint({
            "name": candidate.name,
            "brand": candidate.brand,
            "product_type": candidate.product_type,
        })

        @sync_to_async
        def find():
            return DiscoveredProduct.objects.filter(
                Q(fingerprint=fingerprint) |
                Q(name__iexact=candidate.name)
            ).first()

        return await find()

    async def _merge_into_existing(
        self,
        existing: DiscoveredProduct,
        candidate: ProductCandidate,
    ) -> DiscoveredProduct:
        """Merge candidate data into existing product."""
        from asgiref.sync import sync_to_async
        from crawler.services.product_saver import create_product_awards

        @sync_to_async
        def merge():
            # Add new awards
            if candidate.awards:
                create_product_awards(existing, candidate.awards)

            # Merge any additional data that existing doesn't have
            # (Field-level merge logic)

            # Track that this product was also found via this source
            if existing.discovery_sources is None:
                existing.discovery_sources = []
            source_name = candidate.extraction_source.value
            if source_name not in existing.discovery_sources:
                existing.discovery_sources.append(source_name)
                existing.save(update_fields=["discovery_sources"])

            return existing

        return await merge()

    async def _enrich(
        self,
        candidate: ProductCandidate,
    ) -> tuple[Optional[ProductCandidate], Optional[str]]:
        """
        Attempt to enrich the candidate with additional data.

        Returns:
            Tuple of (enriched_candidate or None, enrichment_source or None)
        """
        # Strategy 1: If we have a direct product link, crawl it
        if candidate.direct_product_link and self.smart_crawler:
            enriched = await self._enrich_from_link(candidate)
            if enriched:
                return enriched, "direct_link"

        # Strategy 2: Search for specific missing data
        missing = candidate.get_missing_data_types()
        if missing and self.serpapi_client:
            enriched = await self._enrich_from_search(candidate, missing)
            if enriched:
                return enriched, "search"

        # No enrichment possible
        return None, None

    async def _enrich_from_link(
        self,
        candidate: ProductCandidate,
    ) -> Optional[ProductCandidate]:
        """Enrich by crawling the direct product link."""
        try:
            extraction = self.smart_crawler.extract_product(
                expected_name=candidate.name,
                product_type=candidate.product_type,
                primary_url=candidate.direct_product_link,
            )

            if extraction.success and extraction.data:
                # Merge extracted data into candidate
                return self._merge_extraction_into_candidate(candidate, extraction.data)
        except Exception as e:
            logger.warning(f"Link enrichment failed for {candidate.name}: {e}")

        return None

    async def _enrich_from_search(
        self,
        candidate: ProductCandidate,
        missing_types: List[str],
    ) -> Optional[ProductCandidate]:
        """Enrich by searching for specific missing data."""
        # Build targeted search queries based on what's missing
        queries = []

        if "tasting_notes" in missing_types:
            queries.append(f"{candidate.name} tasting notes review")
        if "pricing" in missing_types:
            queries.append(f"{candidate.name} price buy")
        if "images" in missing_types:
            queries.append(f"{candidate.name} bottle image")

        # Limit to 2 queries max to control API costs
        for query in queries[:2]:
            try:
                results = await self.serpapi_client.search(query, num_results=3)
                for result in results:
                    # Try to extract from each result
                    enriched = await self._try_extract_from_url(
                        candidate,
                        result.url,
                        missing_types,
                    )
                    if enriched:
                        return enriched
            except Exception as e:
                logger.warning(f"Search enrichment failed: {e}")

        return None

    async def _try_extract_from_url(
        self,
        candidate: ProductCandidate,
        url: str,
        missing_types: List[str],
    ) -> Optional[ProductCandidate]:
        """Try to extract missing data from a URL."""
        if not self.smart_crawler:
            return None

        try:
            extraction = self.smart_crawler.extract_product(
                expected_name=candidate.name,
                product_type=candidate.product_type,
                primary_url=url,
            )

            if extraction.success and extraction.data:
                return self._merge_extraction_into_candidate(candidate, extraction.data)
        except Exception:
            pass

        return None

    def _merge_extraction_into_candidate(
        self,
        candidate: ProductCandidate,
        extraction_data: Dict[str, Any],
    ) -> ProductCandidate:
        """Merge extraction data into candidate, preferring existing data."""
        # Create a copy with merged data
        merged = ProductCandidate(
            name=candidate.name,  # Keep original name
            brand=candidate.brand or extraction_data.get("brand"),
            extraction_source=candidate.extraction_source,
            source_url=candidate.source_url,
            product_type=candidate.product_type,
            abv=candidate.abv or extraction_data.get("abv"),
            age_statement=candidate.age_statement or extraction_data.get("age_statement"),
            description=candidate.description or extraction_data.get("description"),
            tasting_notes=candidate.tasting_notes or extraction_data.get("tasting_notes"),
            nose_description=candidate.nose_description or extraction_data.get("nose_description"),
            palate_flavors=candidate.palate_flavors or extraction_data.get("palate_flavors"),
            awards=candidate.awards + extraction_data.get("awards", []),
            ratings=candidate.ratings + extraction_data.get("ratings", []),
            images=candidate.images + extraction_data.get("images", []),
            prices=candidate.prices + extraction_data.get("prices", []),
            extraction_confidence=max(
                candidate.extraction_confidence,
                extraction_data.get("confidence", 0.5),
            ),
        )

        return merged

    async def _save(self, candidate: ProductCandidate) -> ProductSaveResult:
        """Save the candidate as a DiscoveredProduct."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def do_save():
            return save_discovered_product(
                extracted_data=candidate.to_extracted_data(),
                source_url=candidate.source_url,
                product_type=candidate.product_type,
                discovery_source=candidate.extraction_source.value,
                extraction_confidence=candidate.extraction_confidence,
                field_confidences=candidate.field_confidences,
                raw_content="",
            )

        return await do_save()

    def _get_product_completeness(self, product: DiscoveredProduct) -> int:
        """Calculate completeness score for an existing product."""
        score = 0

        if product.name: score += 20
        if product.brand: score += 10
        if product.product_type: score += 10
        if product.nose_description or product.palate_flavors: score += 15
        if product.description: score += 10
        if product.abv: score += 5
        if product.best_price: score += 10
        if product.images.exists(): score += 10
        if product.ratings.exists(): score += 5
        if product.awards_rel.exists(): score += 5

        return min(score, 100)
```

### 8.3 Updated Extractors

Each extractor now produces `ProductCandidate`:

```python
# crawler/discovery/competitions/competition_extractor.py

class CompetitionExtractor:
    """Extracts products from competition pages using BeautifulSoup parsers."""

    def extract(self, html: str, competition_key: str, year: int) -> List[ProductCandidate]:
        """Extract all products from a competition page."""
        parser = get_parser(competition_key)
        results = parser.parse(html, year)

        candidates = []
        for result in results:
            candidate = ProductCandidate.from_competition_result(result.to_dict())
            candidates.append(candidate)

        return candidates


# crawler/discovery/list_extractor.py

class ListPageExtractor:
    """Extracts products from list pages using AI."""

    async def extract(self, html: str, url: str, product_type: str) -> List[ProductCandidate]:
        """Extract all products from a list page."""
        response = await self.ai_client.extract_product_list(html, url)

        candidates = []
        for product_data in response.get("products", []):
            candidate = ProductCandidate(
                name=product_data.get("name", ""),
                brand=product_data.get("brand"),
                extraction_source=ExtractionSource.AI_LIST_EXTRACTION,
                source_url=url,
                direct_product_link=product_data.get("link"),
                product_type=product_type,
                tasting_notes=product_data.get("tasting_notes"),
                ratings=product_data.get("ratings", []),
                extraction_confidence=0.6,
            )
            candidates.append(candidate)

        return candidates


# crawler/discovery/single_extractor.py

class SingleProductExtractor:
    """Extracts a single product from a product page using AI."""

    async def extract(self, html: str, url: str, product_type: str) -> Optional[ProductCandidate]:
        """Extract product from a single product page."""
        response = await self.ai_client.enhance_from_crawler(html, url, product_type)

        if response.success:
            return ProductCandidate.from_ai_extraction(response.extracted_data, url)

        return None
```

### 8.4 Simplified Orchestrators

```python
# crawler/services/competition_orchestrator.py (simplified)

class CompetitionOrchestrator:
    """Orchestrates competition discovery using unified pipeline."""

    def __init__(self):
        self.extractor = CompetitionExtractor()
        self.pipeline = ProductPipeline(
            enable_enrichment=False,  # Competition products get enriched separately
        )

    async def discover(self, html: str, competition_key: str, year: int) -> DiscoveryResult:
        """Discover products from a competition page."""
        # Extract all candidates
        candidates = self.extractor.extract(html, competition_key, year)

        # Process through pipeline
        results = await self.pipeline.process_batch(
            candidates,
            skip_enrichment=True,  # Don't enrich during discovery
        )

        return DiscoveryResult(
            candidates_found=len(candidates),
            products_created=sum(1 for r in results if r.created),
            duplicates=sum(1 for r in results if r.was_duplicate),
        )


# crawler/services/discovery_orchestrator.py (simplified)

class DiscoveryOrchestrator:
    """Orchestrates generic search discovery using unified pipeline."""

    def __init__(self):
        self.list_extractor = ListPageExtractor()
        self.single_extractor = SingleProductExtractor()
        self.pipeline = ProductPipeline(
            enable_enrichment=True,  # Enable immediate enrichment
        )

    async def process_list_page(self, html: str, url: str, product_type: str):
        """Process a list page."""
        candidates = await self.list_extractor.extract(html, url, product_type)
        results = await self.pipeline.process_batch(candidates)
        return results

    async def process_single_page(self, html: str, url: str, product_type: str):
        """Process a single product page."""
        candidate = await self.single_extractor.extract(html, url, product_type)
        if candidate:
            return await self.pipeline.process(candidate)
        return None
```

---

## 9. Migration Plan

### Phase 1: Core Infrastructure

1. **Create ProductCandidate dataclass**
   - `crawler/discovery/product_candidate.py`
   - Include all factory methods
   - Add completeness calculation with tasting = 40%

2. **Create ProductPipeline**
   - `crawler/services/product_pipeline.py`
   - Implement deduplication (reuse existing logic)
   - Implement save (wrap existing `save_discovered_product`)
   - Stub enrichment methods

3. **Update status model and add fields**
   - Add `INCOMPLETE`, `PARTIAL`, `COMPLETE`, `VERIFIED` to `DiscoveredProductStatus`
   - Add `completeness_score`, `source_count`, `verified_fields` to `DiscoveredProduct`
   - Add `palate_description`, `finish_description` to `DiscoveredProduct`
   - Create migrations

### Phase 2: Extractors & Orchestrators

1. **Create unified extractors**
   - `CompetitionExtractor` → produces `ProductCandidate`
   - `ListPageExtractor` → produces `ProductCandidate`
   - `SingleProductExtractor` → produces `ProductCandidate`

2. **Update orchestrators to use pipeline**
   - `CompetitionOrchestrator` → uses `ProductPipeline`
   - `DiscoveryOrchestrator` → uses `ProductPipeline`
   - `ContentProcessor` → uses `ProductPipeline`

### Phase 3: Multi-Source Verification

1. **Implement VerificationPipeline**
   - Search for additional sources when missing tasting data
   - Extract from 2-3 sources per product
   - Merge and verify data (matching values = verified)
   - Update `source_count` and `verified_fields`

2. **Implement smart enrichment in ProductPipeline**
   - `_enrich_from_link()` - if direct link available
   - `_enrich_from_search()` - targeted search for missing data
   - Only search for MISSING fields (not wasteful 3-search approach)

### Phase 4: Cleanup

1. **Remove legacy enrichment code**
   - Delete `SkeletonProductManager`
   - Delete `EnrichmentSearcher`
   - Delete skeleton-specific code from orchestrators
   - Remove SKELETON status handling

2. **Migrate data from JSON blobs**
   - Create data migration to move `extracted_data`, `enriched_data`, `taste_profile` to columns
   - Mark JSON fields as deprecated
   - Eventually remove JSON blob fields

3. **Update tests**
   - Create tests for `ProductCandidate`
   - Create tests for `ProductPipeline`
   - Create tests for `VerificationPipeline`
   - Test completeness calculation (especially tasting requirement)

---

## 10. Benefits of Unified Approach

| Aspect | Before | After |
|--------|--------|-------|
| **Code Paths** | 3 separate flows | 1 unified pipeline |
| **Product Creation** | 3 different implementations | 1 (`ProductPipeline.process`) |
| **Deduplication** | 3 implementations | 1 (in pipeline) |
| **Enrichment** | Always 3 SerpAPI calls | Smart, 0-2 targeted calls |
| **Status Model** | SKELETON/PENDING confusion | Clear completeness-based |
| **Maintainability** | Fix bugs in 3 places | Fix bugs in 1 place |
| **Testing** | Test 3 flows | Test 1 pipeline |
| **New Extractor** | Implement full flow | Just produce `ProductCandidate` |

---

## 11. Files to Create/Modify

### New Files

**Core Pipeline:**
- `crawler/discovery/product_candidate.py` - ProductCandidate dataclass with completeness calculation
- `crawler/services/product_pipeline.py` - Unified processing pipeline
- `crawler/services/verification_pipeline.py` - Multi-source verification pipeline

**Award Site URL Collectors:**
- `crawler/discovery/collectors/base_collector.py` - Base class for URL collectors
- `crawler/discovery/collectors/iwsc_collector.py` - IWSC URL collector (detail page URLs)
- `crawler/discovery/collectors/sfwsc_collector.py` - SFWSC URL collector
- `crawler/discovery/collectors/wwa_collector.py` - World Whiskies Awards URL collector
- `crawler/discovery/collectors/dwwa_collector.py` - Decanter WWA collector (Playwright-based, for Port wines)

**AI Extractors (unified):**
- `crawler/discovery/extractors/ai_extractor.py` - Unified AI extractor for all sources
- `crawler/discovery/extractors/extraction_prompts.py` - Extraction prompt templates

**Structural Change Detection:**
- `crawler/discovery/health/selector_health.py` - Pre-crawl selector health checker
- `crawler/discovery/health/yield_monitor.py` - Runtime yield monitoring
- `crawler/discovery/health/fingerprint.py` - Structural fingerprint computation and comparison
- `crawler/discovery/health/known_products.py` - Known product verification (ground truth)
- `crawler/discovery/health/alerts.py` - Alert handler (Sentry, Slack, email integration)
- `crawler/tasks/health_checks.py` - Celery tasks for scheduled health checks

**REST API:**
- `crawler/api/__init__.py` - API module init
- `crawler/api/views.py` - API view functions (extraction, crawl triggers, health)
- `crawler/api/urls.py` - API URL routing
- `crawler/api/serializers.py` - Request/response serializers
- `crawler/api/throttling.py` - Custom throttle classes
- `crawler/tasks/award_crawl.py` - Celery task for async award crawls

### Modified Files
- `crawler/models.py` - Add new statuses, `palate_description`, `finish_description`, `source_count`, `verified_fields`, `SourceHealthCheck`, `SourceFingerprint`, `CrawlJob` models
- `config/urls.py` - Include API URLs under `/api/v1/`
- `config/settings/base.py` - Add REST framework throttling configuration
- `crawler/services/competition_orchestrator.py` - Use URL collectors + AI extraction
- `crawler/services/discovery_orchestrator.py` - Simplify to use pipeline
- `crawler/services/content_processor.py` - Simplify to use pipeline
- `crawler/services/product_saver.py` - Update to handle new fields

### Deleted Files (after migration)
- `crawler/discovery/competitions/parsers.py` - Replaced by URL collectors + AI extraction
- `crawler/discovery/competitions/skeleton_manager.py` - No more skeleton products
- `crawler/discovery/competitions/enrichment_searcher.py` - Replaced by verification pipeline
- `crawler/discovery/enrichment/` (entire directory if no longer needed)

---

## 12. Structural Change Detection for Award Sites

Award sites periodically redesign their HTML structure. Without detection, collectors silently fail, returning zero results or malformed data. This section defines mechanisms to detect structural changes early.

### 12.1 Multi-Layer Detection Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURAL CHANGE DETECTION LAYERS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: SELECTOR HEALTH CHECK (Pre-crawl)                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Before each crawl run:                                               │   │
│  │  • Fetch a known sample page                                          │   │
│  │  • Test all CSS selectors used by collector                           │   │
│  │  • If >50% selectors fail → ABORT + ALERT                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 2: YIELD MONITORING (During crawl)                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Track results per listing page:                                      │   │
│  │  • Expected: 20-50 products per page                                  │   │
│  │  • If page yields <5 products when >20 expected → FLAG                │   │
│  │  • If 3 consecutive pages yield <10% expected → ABORT + ALERT         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 3: SCHEMA VALIDATION (Post-extraction)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Validate each extracted AwardDetailURL:                              │   │
│  │  • detail_url matches expected pattern (regex)                        │   │
│  │  • medal_hint is valid enum value                                     │   │
│  │  • If >30% of items fail validation → ALERT                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 4: KNOWN PRODUCT VERIFICATION (Periodic)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Weekly: Re-extract 3-5 known products per source                     │   │
│  │  • Compare extracted data with stored "ground truth"                  │   │
│  │  • If extraction differs significantly → INVESTIGATE                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Selector Health Check Implementation

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import httpx
import logging

logger = logging.getLogger(__name__)


@dataclass
class SelectorHealth:
    """Result of testing a CSS selector."""
    selector: str
    found_count: int
    expected_min: int
    healthy: bool


@dataclass
class CollectorHealthReport:
    """Health report for a collector's selectors."""
    source: str
    sample_url: str
    selectors_tested: int
    selectors_healthy: int
    is_healthy: bool
    failed_selectors: List[str]
    timestamp: str


class SelectorHealthChecker:
    """
    Pre-crawl health check for collector CSS selectors.
    Run before each scheduled crawl to detect site changes.
    """

    # Define expected selectors for each source
    # These are the CSS selectors each collector relies on
    SOURCE_SELECTORS = {
        "iwsc": {
            "sample_url": "https://www.iwsc.net/results/{year}?category=wine&style=fortified",
            "selectors": {
                ".c-card--listing": {"min": 10, "desc": "Product cards"},
                "a[href*='/results/detail/']": {"min": 10, "desc": "Detail page links"},
                ".c-card--listing img[src*='medal']": {"min": 5, "desc": "Medal images"},
            }
        },
        "dwwa": {
            "sample_url": "https://awards.decanter.com/DWWA/{year}",
            "selectors": {
                "[data-wine-id]": {"min": 10, "desc": "Wine cards"},
                "a[href*='/wines/']": {"min": 10, "desc": "Detail page links"},
                ".medal-badge, .award-level": {"min": 5, "desc": "Medal indicators"},
            }
        },
        "sfwsc": {
            "sample_url": "https://sfwsc.com/winners/{year}/",
            "selectors": {
                ".winner-entry, .product-card": {"min": 10, "desc": "Winner entries"},
                ".medal-type, .award-medal": {"min": 5, "desc": "Medal types"},
            }
        }
    }

    async def check_source(self, source: str, year: int) -> CollectorHealthReport:
        """
        Check if a source's selectors still work.
        Run BEFORE each crawl job.
        """
        if source not in self.SOURCE_SELECTORS:
            raise ValueError(f"Unknown source: {source}")

        config = self.SOURCE_SELECTORS[source]
        sample_url = config["sample_url"].format(year=year)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(sample_url, timeout=30)
                response.raise_for_status()
                html = response.text
        except Exception as e:
            logger.error(f"Failed to fetch sample page for {source}: {e}")
            return CollectorHealthReport(
                source=source,
                sample_url=sample_url,
                selectors_tested=0,
                selectors_healthy=0,
                is_healthy=False,
                failed_selectors=["FETCH_FAILED"],
                timestamp=datetime.now().isoformat()
            )

        soup = BeautifulSoup(html, "lxml")
        results = []
        failed = []

        for selector, spec in config["selectors"].items():
            found = soup.select(selector)
            healthy = len(found) >= spec["min"]

            if not healthy:
                failed.append(f"{selector} (found {len(found)}, expected {spec['min']}+)")
                logger.warning(
                    f"Selector health check FAILED for {source}: "
                    f"{selector} found {len(found)}, expected {spec['min']}+ "
                    f"({spec['desc']})"
                )

            results.append(SelectorHealth(
                selector=selector,
                found_count=len(found),
                expected_min=spec["min"],
                healthy=healthy
            ))

        healthy_count = sum(1 for r in results if r.healthy)
        # Consider healthy if >50% selectors work
        is_healthy = (healthy_count / len(results)) > 0.5 if results else False

        return CollectorHealthReport(
            source=source,
            sample_url=sample_url,
            selectors_tested=len(results),
            selectors_healthy=healthy_count,
            is_healthy=is_healthy,
            failed_selectors=failed,
            timestamp=datetime.now().isoformat()
        )
```

### 12.3 Yield Monitoring Implementation

```python
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class YieldMonitor:
    """
    Monitors yield (results per page) during a crawl.
    Detects abnormal drops that indicate structural changes.
    """
    source: str
    expected_min_per_page: int = 10
    expected_avg_per_page: int = 25
    consecutive_low_threshold: int = 3

    # Tracking state
    pages_processed: int = 0
    total_items_collected: int = 0
    consecutive_low_pages: int = 0
    alerts: List[str] = field(default_factory=list)

    def record_page(self, items_collected: int, page_url: str) -> bool:
        """
        Record results from a page. Returns False if crawl should abort.
        """
        self.pages_processed += 1
        self.total_items_collected += items_collected

        # Check for abnormally low yield
        if items_collected < self.expected_min_per_page:
            self.consecutive_low_pages += 1

            if items_collected == 0:
                alert = f"ZERO YIELD on page {page_url}"
                self.alerts.append(alert)
                logger.error(alert)
            else:
                alert = f"LOW YIELD: {items_collected} items on {page_url} (expected {self.expected_min_per_page}+)"
                self.alerts.append(alert)
                logger.warning(alert)

            # Abort if too many consecutive low-yield pages
            if self.consecutive_low_pages >= self.consecutive_low_threshold:
                abort_msg = (
                    f"ABORTING {self.source} crawl: "
                    f"{self.consecutive_low_pages} consecutive pages with low yield. "
                    f"Site structure may have changed."
                )
                self.alerts.append(abort_msg)
                logger.critical(abort_msg)
                return False  # Signal to abort
        else:
            # Reset counter on healthy page
            self.consecutive_low_pages = 0

        return True  # Continue crawling

    def get_summary(self) -> dict:
        """Get yield monitoring summary."""
        avg_yield = (
            self.total_items_collected / self.pages_processed
            if self.pages_processed > 0 else 0
        )
        return {
            "source": self.source,
            "pages_processed": self.pages_processed,
            "total_items": self.total_items_collected,
            "avg_per_page": round(avg_yield, 1),
            "expected_avg": self.expected_avg_per_page,
            "yield_health": "HEALTHY" if avg_yield >= self.expected_min_per_page else "DEGRADED",
            "alerts": self.alerts,
        }
```

### 12.4 Known Product Verification (Ground Truth)

```python
from dataclasses import dataclass
from typing import Dict, Any, List
import json

@dataclass
class KnownProduct:
    """A product with known correct extraction for verification."""
    source: str
    detail_url: str
    expected_data: Dict[str, Any]  # Ground truth


# Store 3-5 known products per source for periodic verification
KNOWN_PRODUCTS = {
    "iwsc": [
        KnownProduct(
            source="iwsc",
            detail_url="https://www.iwsc.net/results/detail/157656/10-yo-tawny-nv",
            expected_data={
                "name_contains": "10 Year",
                "medal": "Gold",
                "has_tasting_notes": True,
                "product_type": "port_wine",
            }
        ),
        # Add more known products...
    ],
    "dwwa": [
        KnownProduct(
            source="dwwa",
            detail_url="https://awards.decanter.com/DWWA/2025/wines/768949",
            expected_data={
                "name_contains": "Galpin Peak",
                "medal_in": ["Gold", "Silver", "Bronze", "Platinum"],
                "has_tasting_notes": True,
                "origin_country": "South Africa",
            }
        ),
        # Add more known products...
    ],
}


class KnownProductVerifier:
    """
    Periodically verify extraction on known products.
    Run weekly via scheduled task.
    """

    def __init__(self, ai_extractor):
        self.ai_extractor = ai_extractor

    async def verify_source(self, source: str) -> Dict[str, Any]:
        """Verify all known products for a source."""
        if source not in KNOWN_PRODUCTS:
            return {"error": f"No known products for {source}"}

        results = []
        for known in KNOWN_PRODUCTS[source]:
            result = await self._verify_single(known)
            results.append(result)

        passed = sum(1 for r in results if r["passed"])
        return {
            "source": source,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "health": "HEALTHY" if passed == len(results) else "DEGRADED",
            "details": results,
        }

    async def _verify_single(self, known: KnownProduct) -> Dict[str, Any]:
        """Verify extraction for a single known product."""
        try:
            # Extract using current implementation
            extracted = await self.ai_extractor.extract_from_url(known.detail_url)

            # Compare with expected
            checks = []
            for key, expected in known.expected_data.items():
                if key == "name_contains":
                    actual = extracted.get("name", "")
                    passed = expected.lower() in actual.lower()
                    checks.append({"check": key, "passed": passed})
                elif key == "medal_in":
                    actual = extracted.get("medal", "")
                    passed = actual in expected
                    checks.append({"check": key, "passed": passed})
                elif key == "has_tasting_notes":
                    has_notes = bool(
                        extracted.get("palate_description") or
                        extracted.get("nose_description") or
                        extracted.get("finish_description")
                    )
                    passed = has_notes == expected
                    checks.append({"check": key, "passed": passed})
                elif key.startswith("origin_"):
                    field = key.replace("origin_", "")
                    actual = extracted.get(field, "")
                    passed = expected.lower() in actual.lower()
                    checks.append({"check": key, "passed": passed})

            all_passed = all(c["passed"] for c in checks)
            return {
                "url": known.detail_url,
                "passed": all_passed,
                "checks": checks,
            }
        except Exception as e:
            return {
                "url": known.detail_url,
                "passed": False,
                "error": str(e),
            }
```

### 12.5 Structural Fingerprinting

```python
import hashlib
from bs4 import BeautifulSoup


class StructuralFingerprint:
    """
    Create a fingerprint of key structural elements.
    Changes in fingerprint indicate structural changes.
    """

    # Elements that define site structure (not content)
    STRUCTURE_ELEMENTS = {
        "iwsc": [
            "div.c-card--listing",
            "div.results-grid",
            "nav.pagination",
            "form.filter-form",
        ],
        "dwwa": [
            "div[data-wine-id]",
            "div.results-container",
            "div.filter-panel",
            "nav.pagination",
        ],
    }

    @classmethod
    def compute(cls, source: str, html: str) -> str:
        """
        Compute structural fingerprint for a page.
        Returns hash of structural element presence/hierarchy.
        """
        soup = BeautifulSoup(html, "lxml")
        elements = cls.STRUCTURE_ELEMENTS.get(source, [])

        structure = []
        for selector in elements:
            found = soup.select(selector)
            # Record: selector, count, first element's classes/attrs
            if found:
                first = found[0]
                attrs = sorted(first.attrs.keys())
                structure.append(f"{selector}:{len(found)}:{attrs}")
            else:
                structure.append(f"{selector}:0:[]")

        fingerprint_str = "|".join(structure)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()

    @classmethod
    def compare(cls, old_fingerprint: str, new_fingerprint: str) -> bool:
        """
        Compare fingerprints. Returns True if they match (no structural change).
        """
        return old_fingerprint == new_fingerprint


# Store and compare fingerprints
class FingerPrintStore:
    """Store fingerprints in database for comparison."""

    def store(self, source: str, fingerprint: str, url: str):
        """Store a new fingerprint."""
        from crawler.models import SourceFingerprint
        SourceFingerprint.objects.update_or_create(
            source=source,
            defaults={
                "fingerprint": fingerprint,
                "sample_url": url,
                "updated_at": timezone.now(),
            }
        )

    def check_changed(self, source: str, new_fingerprint: str) -> bool:
        """Check if fingerprint has changed. Returns True if changed."""
        from crawler.models import SourceFingerprint
        try:
            stored = SourceFingerprint.objects.get(source=source)
            return stored.fingerprint != new_fingerprint
        except SourceFingerprint.DoesNotExist:
            return False  # First time, no comparison possible
```

### 12.6 Alerting Integration

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class StructureAlert:
    """Alert for structural change detection."""
    source: str
    severity: AlertSeverity
    message: str
    details: Optional[dict] = None


class StructureChangeAlertHandler:
    """
    Handle structural change alerts.
    Integrates with Sentry, email, and Slack.
    """

    def __init__(self, config):
        self.config = config

    def send_alert(self, alert: StructureAlert):
        """Send alert through configured channels."""
        if alert.severity == AlertSeverity.CRITICAL:
            self._send_sentry(alert)
            self._send_slack(alert)
            self._send_email(alert)
        elif alert.severity == AlertSeverity.WARNING:
            self._send_sentry(alert)
            self._send_slack(alert)
        else:
            self._send_sentry(alert)

    def _send_sentry(self, alert: StructureAlert):
        """Send to Sentry."""
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("source", alert.source)
            scope.set_tag("severity", alert.severity.value)
            scope.set_extra("details", alert.details)
            if alert.severity == AlertSeverity.CRITICAL:
                sentry_sdk.capture_message(alert.message, level="error")
            else:
                sentry_sdk.capture_message(alert.message, level="warning")

    def _send_slack(self, alert: StructureAlert):
        """Send to Slack webhook."""
        import httpx
        webhook_url = self.config.get("slack_webhook")
        if not webhook_url:
            return

        color = {
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.INFO: "#17a2b8",
        }[alert.severity]

        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert.severity.value.upper()}] {alert.source} Structure Change",
                "text": alert.message,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in (alert.details or {}).items()
                ],
            }]
        }
        httpx.post(webhook_url, json=payload)

    def _send_email(self, alert: StructureAlert):
        """Send email for critical alerts."""
        from django.core.mail import send_mail
        send_mail(
            subject=f"[CRITICAL] {alert.source} Structure Change Detected",
            message=f"{alert.message}\n\nDetails: {alert.details}",
            from_email=self.config.get("from_email"),
            recipient_list=self.config.get("alert_emails", []),
        )
```

### 12.7 Scheduled Health Checks

```python
# Add to Celery beat schedule
CELERY_BEAT_SCHEDULE = {
    # Run selector health check before each scheduled crawl
    "pre-crawl-health-check-iwsc": {
        "task": "crawler.tasks.check_source_health",
        "schedule": crontab(hour=5, minute=45),  # 15 min before IWSC crawl
        "args": ["iwsc"],
    },
    "pre-crawl-health-check-dwwa": {
        "task": "crawler.tasks.check_source_health",
        "schedule": crontab(hour=5, minute=45, day_of_week="monday"),
        "args": ["dwwa"],
    },

    # Weekly known product verification
    "weekly-known-product-verification": {
        "task": "crawler.tasks.verify_known_products",
        "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),
    },
}


# Celery task implementation
@shared_task
def check_source_health(source: str) -> dict:
    """
    Run pre-crawl health check for a source.
    Aborts scheduled crawl if health check fails.
    """
    from crawler.discovery.health import SelectorHealthChecker, StructureChangeAlertHandler

    checker = SelectorHealthChecker()
    year = datetime.now().year

    report = asyncio.run(checker.check_source(source, year))

    if not report.is_healthy:
        # Send alert
        alert_handler = StructureChangeAlertHandler(settings.ALERT_CONFIG)
        alert_handler.send_alert(StructureAlert(
            source=source,
            severity=AlertSeverity.CRITICAL,
            message=f"Pre-crawl health check FAILED for {source}. Crawl aborted.",
            details={
                "failed_selectors": report.failed_selectors,
                "healthy_ratio": f"{report.selectors_healthy}/{report.selectors_tested}",
            }
        ))

        # Cancel the scheduled crawl task
        revoke_scheduled_crawl(source)

        return {"status": "UNHEALTHY", "crawl_cancelled": True, "report": report}

    return {"status": "HEALTHY", "report": report}
```

### 12.8 Database Model for Tracking

```python
# Add to crawler/models.py

class SourceHealthCheck(models.Model):
    """Track health check results for each source."""
    source = models.CharField(max_length=50)
    check_type = models.CharField(
        max_length=20,
        choices=[
            ("selector", "Selector Health"),
            ("yield", "Yield Monitoring"),
            ("fingerprint", "Structural Fingerprint"),
            ("known_product", "Known Product Verification"),
        ]
    )
    is_healthy = models.BooleanField()
    details = models.JSONField(default=dict)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "source_health_check"
        indexes = [
            models.Index(fields=["source", "check_type"]),
            models.Index(fields=["checked_at"]),
        ]


class SourceFingerprint(models.Model):
    """Store structural fingerprints for change detection."""
    source = models.CharField(max_length=50, unique=True)
    fingerprint = models.CharField(max_length=64)  # MD5 hash
    sample_url = models.URLField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "source_fingerprint"
```

---

## 13. REST API Endpoints

The crawler exposes REST API endpoints for on-demand extraction and crawl triggering.

### 13.1 API Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REST API ENDPOINTS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EXTRACTION ENDPOINTS (On-demand product extraction)                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/extract/url/                                            │   │
│  │  Extract product(s) from a single URL (list or detail page)           │   │
│  │                                                                        │   │
│  │  POST /api/v1/extract/urls/                                           │   │
│  │  Batch extract from multiple URLs                                      │   │
│  │                                                                        │   │
│  │  POST /api/v1/extract/search/                                         │   │
│  │  Search + extract (SerpAPI → SmartCrawler)                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  CRAWL TRIGGER ENDPOINTS (Award site crawls)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/crawl/awards/                                           │   │
│  │  Trigger unscheduled award site crawl                                  │   │
│  │                                                                        │   │
│  │  GET  /api/v1/crawl/awards/status/{job_id}/                           │   │
│  │  Check crawl job status                                                │   │
│  │                                                                        │   │
│  │  GET  /api/v1/crawl/awards/sources/                                   │   │
│  │  List available award sources with health status                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  HEALTH & MONITORING                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  GET  /api/health/                     (existing)                     │   │
│  │  GET  /api/v1/sources/health/          Source-level health            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Extraction Endpoints

#### POST /api/v1/extract/url/

Extract product(s) from a single URL. Automatically detects if URL is a list page or single product page.

**Request:**
```json
{
  "url": "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
  "product_type": "whiskey",           // Optional: "whiskey", "port_wine", "auto"
  "save_to_db": true,                  // Optional: Save to DiscoveredProduct (default: true)
  "enrich": true                       // Optional: Run multi-source enrichment (default: false)
}
```

**Response (Single Product):**
```json
{
  "success": true,
  "page_type": "single_product",
  "products": [
    {
      "id": 12345,                     // DiscoveredProduct.id if saved
      "name": "Ardbeg 10 Year Old",
      "brand": "Ardbeg",
      "product_type": "whiskey",
      "abv": 46.0,
      "status": "partial",
      "completeness_score": 45,
      "source_url": "https://www.masterofmalt.com/...",
      "palate_description": "Smoky with citrus notes...",
      "nose_description": "Intense peat smoke...",
      "has_tasting_profile": true
    }
  ],
  "extraction_time_ms": 2340
}
```

**Response (List Page):**
```json
{
  "success": true,
  "page_type": "list_page",
  "products_found": 12,
  "products_extracted": 10,
  "products_failed": 2,
  "products": [
    { "id": 12345, "name": "Product 1", "status": "partial", ... },
    { "id": 12346, "name": "Product 2", "status": "complete", ... }
  ],
  "failed_products": [
    { "name": "Product X", "error": "Extraction timeout" }
  ],
  "extraction_time_ms": 15420
}
```

#### POST /api/v1/extract/urls/

Batch extract from multiple URLs.

**Request:**
```json
{
  "urls": [
    "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
    "https://www.thewhiskyexchange.com/p/12345/lagavulin-16-year-old",
    "https://www.wine.com/product/taylors-10-year-tawny-port/123456"
  ],
  "product_type": "auto",              // Auto-detect per URL
  "save_to_db": true,
  "parallel": true                     // Process URLs in parallel (default: true)
}
```

**Response:**
```json
{
  "success": true,
  "total_urls": 3,
  "successful": 3,
  "failed": 0,
  "products_extracted": 3,
  "results": [
    { "url": "https://...", "success": true, "product_id": 12345 },
    { "url": "https://...", "success": true, "product_id": 12346 },
    { "url": "https://...", "success": true, "product_id": 12347 }
  ],
  "extraction_time_ms": 8540
}
```

#### POST /api/v1/extract/search/

Search for a product and extract from best results.

**Request:**
```json
{
  "query": "Ardbeg Uigeadail whisky",
  "product_type": "whiskey",
  "num_results": 5,                    // Number of search results to try
  "save_to_db": true,
  "prefer_official": true              // Prefer official brand sites (default: true)
}
```

**Response:**
```json
{
  "success": true,
  "query": "Ardbeg Uigeadail whisky",
  "search_results_found": 10,
  "urls_tried": 3,
  "product": {
    "id": 12345,
    "name": "Ardbeg Uigeadail",
    "source_url": "https://www.ardbeg.com/en-US/whisky/ultimate-range/uigeadail",
    "source_type": "official_brand",
    "status": "complete",
    "completeness_score": 75
  },
  "extraction_time_ms": 4520
}
```

### 13.3 Award Crawl Trigger Endpoints

#### POST /api/v1/crawl/awards/

Trigger an unscheduled award site crawl.

**Request:**
```json
{
  "source": "iwsc",                    // "iwsc", "dwwa", "sfwsc", "wwa"
  "year": 2025,                        // Optional: defaults to current year
  "product_types": ["port_wine"],      // Optional: filter by product type
  "run_health_check": true,            // Optional: run health check first (default: true)
  "async": true                        // Optional: return immediately with job_id (default: true)
}
```

**Response (async=true):**
```json
{
  "success": true,
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "queued",
  "health_check": {
    "passed": true,
    "selectors_healthy": 3,
    "selectors_total": 3
  },
  "estimated_products": 150,
  "status_url": "/api/v1/crawl/awards/status/award-crawl-iwsc-2025-abc123/"
}
```

**Response (async=false):**
```json
{
  "success": true,
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "completed",
  "products_found": 145,
  "products_saved": 142,
  "products_failed": 3,
  "new_products": 89,
  "updated_products": 53,
  "duration_seconds": 342,
  "errors": [
    { "url": "https://...", "error": "Extraction failed" }
  ]
}
```

#### GET /api/v1/crawl/awards/status/{job_id}/

Check status of a crawl job.

**Response:**
```json
{
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "running",                 // "queued", "running", "completed", "failed"
  "progress": {
    "pages_processed": 5,
    "pages_total": 12,
    "products_found": 85,
    "products_saved": 82,
    "current_page": "https://www.iwsc.net/results/2025?page=6"
  },
  "started_at": "2026-01-05T14:30:00Z",
  "elapsed_seconds": 145
}
```

#### GET /api/v1/crawl/awards/sources/

List available award sources with health status.

**Response:**
```json
{
  "sources": [
    {
      "id": "iwsc",
      "name": "International Wine & Spirit Competition",
      "url": "https://www.iwsc.net",
      "product_types": ["whiskey", "port_wine", "gin", "vodka"],
      "requires_playwright": false,
      "health": {
        "status": "healthy",
        "last_check": "2026-01-05T06:00:00Z",
        "selectors_healthy": 3,
        "last_crawl": "2026-01-04T06:15:00Z",
        "last_crawl_products": 245
      },
      "schedule": {
        "enabled": true,
        "cron": "0 6 * * 1",
        "next_run": "2026-01-06T06:00:00Z"
      }
    },
    {
      "id": "dwwa",
      "name": "Decanter World Wine Awards",
      "url": "https://awards.decanter.com",
      "product_types": ["port_wine", "wine"],
      "requires_playwright": true,
      "health": {
        "status": "healthy",
        "last_check": "2026-01-05T06:00:00Z",
        "selectors_healthy": 3,
        "last_crawl": "2025-12-30T06:15:00Z",
        "last_crawl_products": 89
      },
      "schedule": {
        "enabled": true,
        "cron": "0 6 * * 1",
        "next_run": "2026-01-06T06:00:00Z"
      }
    }
  ]
}
```

### 13.4 Source Health Endpoint

#### GET /api/v1/sources/health/

Get health status for all sources (award sites + retailers).

**Response:**
```json
{
  "overall_status": "healthy",
  "sources": {
    "award_sites": [
      {
        "id": "iwsc",
        "status": "healthy",
        "last_health_check": "2026-01-05T06:00:00Z",
        "checks": {
          "selector_health": "passed",
          "fingerprint_match": true,
          "last_yield": 245
        }
      }
    ],
    "retailers": [
      {
        "domain": "masterofmalt.com",
        "status": "healthy",
        "success_rate_24h": 0.94,
        "avg_extraction_time_ms": 2150
      }
    ]
  }
}
```

### 13.5 Authentication & Rate Limiting

```python
# API Authentication (add to settings)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # For admin UI
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/hour',           # General rate limit
        'extraction': '50/hour',       # Extraction endpoints
        'crawl_trigger': '10/hour',    # Crawl triggers
    },
}
```

### 13.6 Implementation: Views

```python
# crawler/api/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from crawler.services.smart_crawler import SmartCrawler
from crawler.services.discovery_orchestrator import DiscoveryOrchestrator
from crawler.discovery.collectors import get_collector
from crawler.tasks import trigger_award_crawl


class ExtractionThrottle(UserRateThrottle):
    rate = '50/hour'


class CrawlTriggerThrottle(UserRateThrottle):
    rate = '10/hour'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_url(request):
    """
    Extract product(s) from a single URL.
    Automatically detects list page vs single product page.
    """
    url = request.data.get('url')
    if not url:
        return Response(
            {'error': 'url is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    enrich = request.data.get('enrich', False)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        # Detect page type and extract
        result = crawler.extract_from_url(
            url=url,
            product_type=product_type,
            save_to_db=save_to_db,
            enrich=enrich,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': True,
            'page_type': result.page_type,
            'products': result.products,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception(f"Extraction failed for {url}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_urls(request):
    """Batch extract from multiple URLs."""
    urls = request.data.get('urls', [])
    if not urls:
        return Response(
            {'error': 'urls is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(urls) > 50:
        return Response(
            {'error': 'Maximum 50 URLs per request'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    parallel = request.data.get('parallel', True)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        if parallel:
            # Use asyncio for parallel extraction
            results = asyncio.run(
                crawler.extract_from_urls_parallel(urls, product_type, save_to_db)
            )
        else:
            results = crawler.extract_from_urls_sequential(urls, product_type, save_to_db)

        elapsed_ms = int((time.time() - start_time) * 1000)

        successful = sum(1 for r in results if r['success'])
        products_extracted = sum(len(r.get('products', [])) for r in results if r['success'])

        return Response({
            'success': True,
            'total_urls': len(urls),
            'successful': successful,
            'failed': len(urls) - successful,
            'products_extracted': products_extracted,
            'results': results,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception("Batch extraction failed")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_search(request):
    """Search for a product and extract from best results."""
    query = request.data.get('query')
    if not query:
        return Response(
            {'error': 'query is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    num_results = min(request.data.get('num_results', 5), 10)
    save_to_db = request.data.get('save_to_db', True)
    prefer_official = request.data.get('prefer_official', True)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        result = crawler.extract_product(
            search_term=query,
            product_type=product_type,
            save_to_db=save_to_db,
            prefer_official=prefer_official,
            max_search_results=num_results,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': result.success,
            'query': query,
            'search_results_found': result.search_results_count,
            'urls_tried': len(result.urls_tried),
            'product': result.product if result.success else None,
            'error': result.error if not result.success else None,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception(f"Search extraction failed for: {query}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([CrawlTriggerThrottle])
def trigger_award_crawl_view(request):
    """Trigger an unscheduled award site crawl."""
    source = request.data.get('source')
    if not source:
        return Response(
            {'error': 'source is required (iwsc, dwwa, sfwsc, wwa)'},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_sources = ['iwsc', 'dwwa', 'sfwsc', 'wwa']
    if source not in valid_sources:
        return Response(
            {'error': f'Invalid source. Must be one of: {valid_sources}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    year = request.data.get('year', datetime.now().year)
    product_types = request.data.get('product_types')
    run_health_check = request.data.get('run_health_check', True)
    is_async = request.data.get('async', True)

    try:
        # Run health check first if requested
        health_result = None
        if run_health_check:
            from crawler.discovery.health import SelectorHealthChecker
            checker = SelectorHealthChecker()
            health_report = asyncio.run(checker.check_source(source, year))

            if not health_report.is_healthy:
                return Response({
                    'success': False,
                    'error': 'Health check failed - site structure may have changed',
                    'health_check': {
                        'passed': False,
                        'failed_selectors': health_report.failed_selectors,
                    }
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            health_result = {
                'passed': True,
                'selectors_healthy': health_report.selectors_healthy,
                'selectors_total': health_report.selectors_tested,
            }

        # Generate job ID
        job_id = f"award-crawl-{source}-{year}-{uuid.uuid4().hex[:8]}"

        if is_async:
            # Queue the crawl task
            trigger_award_crawl.delay(
                job_id=job_id,
                source=source,
                year=year,
                product_types=product_types,
            )

            return Response({
                'success': True,
                'job_id': job_id,
                'source': source,
                'year': year,
                'status': 'queued',
                'health_check': health_result,
                'status_url': f'/api/v1/crawl/awards/status/{job_id}/',
            })
        else:
            # Run synchronously (blocking)
            result = run_award_crawl_sync(
                job_id=job_id,
                source=source,
                year=year,
                product_types=product_types,
            )

            return Response({
                'success': True,
                'job_id': job_id,
                **result,
            })

    except Exception as e:
        logger.exception(f"Failed to trigger award crawl for {source}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crawl_status(request, job_id):
    """Get status of a crawl job."""
    try:
        from crawler.models import CrawlJob
        job = CrawlJob.objects.get(job_id=job_id)

        return Response({
            'job_id': job.job_id,
            'source': job.source,
            'year': job.year,
            'status': job.status,
            'progress': job.progress,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'elapsed_seconds': job.elapsed_seconds,
            'error': job.error,
        })

    except CrawlJob.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_award_sources(request):
    """List available award sources with health status."""
    from crawler.discovery.health import SelectorHealthChecker
    from crawler.models import SourceHealthCheck, CrawlSchedule

    sources = []
    source_configs = {
        'iwsc': {
            'name': 'International Wine & Spirit Competition',
            'url': 'https://www.iwsc.net',
            'product_types': ['whiskey', 'port_wine', 'gin', 'vodka'],
            'requires_playwright': False,
        },
        'dwwa': {
            'name': 'Decanter World Wine Awards',
            'url': 'https://awards.decanter.com',
            'product_types': ['port_wine', 'wine'],
            'requires_playwright': True,
        },
        'sfwsc': {
            'name': 'San Francisco World Spirits Competition',
            'url': 'https://sfwsc.com',
            'product_types': ['whiskey', 'gin', 'vodka', 'rum', 'tequila'],
            'requires_playwright': False,
        },
        'wwa': {
            'name': 'World Whiskies Awards',
            'url': 'https://www.worldwhiskiesawards.com',
            'product_types': ['whiskey'],
            'requires_playwright': False,
        },
    }

    for source_id, config in source_configs.items():
        # Get latest health check
        health_check = SourceHealthCheck.objects.filter(
            source=source_id
        ).order_by('-checked_at').first()

        # Get schedule
        schedule = CrawlSchedule.objects.filter(
            source_id=source_id
        ).first()

        sources.append({
            'id': source_id,
            **config,
            'health': {
                'status': 'healthy' if health_check and health_check.is_healthy else 'unknown',
                'last_check': health_check.checked_at.isoformat() if health_check else None,
                'selectors_healthy': health_check.details.get('selectors_healthy') if health_check else None,
            } if health_check else {'status': 'unknown'},
            'schedule': {
                'enabled': schedule.enabled if schedule else False,
                'cron': schedule.cron_expression if schedule else None,
                'next_run': schedule.next_run.isoformat() if schedule and schedule.next_run else None,
            } if schedule else {'enabled': False},
        })

    return Response({'sources': sources})
```

### 13.7 URL Configuration

```python
# crawler/api/urls.py

from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Extraction endpoints
    path('extract/url/', views.extract_from_url, name='extract-url'),
    path('extract/urls/', views.extract_from_urls, name='extract-urls'),
    path('extract/search/', views.extract_from_search, name='extract-search'),

    # Award crawl endpoints
    path('crawl/awards/', views.trigger_award_crawl_view, name='trigger-award-crawl'),
    path('crawl/awards/status/<str:job_id>/', views.get_crawl_status, name='crawl-status'),
    path('crawl/awards/sources/', views.list_award_sources, name='award-sources'),

    # Health endpoints
    path('sources/health/', views.sources_health, name='sources-health'),
]


# config/urls.py - update to include API
urlpatterns = [
    # ... existing patterns ...
    path("api/v1/", include("crawler.api.urls")),
]
```

### 13.8 Celery Task for Async Crawl

```python
# crawler/tasks/award_crawl.py

from celery import shared_task
from crawler.models import CrawlJob
from crawler.discovery.collectors import get_collector
from crawler.discovery.extractors import AIExtractor


@shared_task(bind=True)
def trigger_award_crawl(self, job_id: str, source: str, year: int, product_types: list = None):
    """
    Celery task to run award site crawl asynchronously.
    Updates CrawlJob model with progress.
    """
    from django.utils import timezone

    # Create or update job record
    job, _ = CrawlJob.objects.update_or_create(
        job_id=job_id,
        defaults={
            'source': source,
            'year': year,
            'status': 'running',
            'started_at': timezone.now(),
            'celery_task_id': self.request.id,
        }
    )

    try:
        collector = get_collector(source)
        extractor = AIExtractor()

        # Collect URLs from listing pages
        detail_urls = collector.collect(year=year, product_types=product_types)

        job.progress = {
            'pages_processed': 0,
            'pages_total': len(detail_urls),
            'products_found': len(detail_urls),
            'products_saved': 0,
        }
        job.save()

        # Extract from each detail URL
        saved_count = 0
        errors = []

        for i, url_info in enumerate(detail_urls):
            try:
                product_data = extractor.extract(
                    url=url_info.detail_url,
                    context={
                        'source': source,
                        'year': year,
                        'medal_hint': url_info.medal_hint,
                        'score_hint': url_info.score_hint,
                    }
                )

                if product_data:
                    save_discovered_product(product_data, source=source)
                    saved_count += 1

            except Exception as e:
                errors.append({'url': url_info.detail_url, 'error': str(e)})

            # Update progress
            job.progress['pages_processed'] = i + 1
            job.progress['products_saved'] = saved_count
            job.save()

        # Mark complete
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress['errors'] = errors[:10]  # Keep first 10 errors
        job.save()

    except Exception as e:
        job.status = 'failed'
        job.error = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise
```

### 13.9 CrawlJob Model

```python
# Add to crawler/models.py

class CrawlJob(models.Model):
    """Track async crawl jobs triggered via API."""

    job_id = models.CharField(max_length=100, unique=True, db_index=True)
    source = models.CharField(max_length=50)
    year = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='queued',
    )
    progress = models.JSONField(default=dict)
    error = models.TextField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crawl_job'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['source', 'year']),
        ]

    @property
    def elapsed_seconds(self) -> int:
        if not self.started_at:
            return 0
        end = self.completed_at or timezone.now()
        return int((end - self.started_at).total_seconds())
```

---

## Summary

This spec defines a unified product pipeline that:

1. **Requires tasting profile for COMPLETE/VERIFIED** - Products CANNOT be marked complete without palate data
2. **Verifies from multiple sources** - Target 2-3 sources per product, track `source_count` and `verified_fields`
3. **Uses proper database columns** - No JSON blobs for searchable data, individual columns for all tasting fields
4. **Maintains model split** - DiscoveredProduct + WhiskeyDetails + PortWineDetails
5. **Uses completeness scoring** - Tasting = 40%, with palate being mandatory for COMPLETE status
6. **URL Collector → AI Extraction for awards** - Specialized collectors find detail page URLs, unified AI extracts all data
7. **DWWA support for Port wines** - Playwright-based collector for JavaScript-rendered DWWA site, includes non-Portuguese port-style wines
8. **Structural change detection** - Multi-layer detection (selector health, yield monitoring, fingerprinting, known product verification) with automated alerts and crawl abort on failure
9. **REST API for extraction & crawl triggers** - On-demand extraction from URLs/search, async award crawl triggering with job status tracking

---

*Document created: 2026-01-05*
*Last updated: 2026-01-05*
*Version: 2.4 - Added REST API endpoints for extraction and award crawl triggers (Section 13)*
