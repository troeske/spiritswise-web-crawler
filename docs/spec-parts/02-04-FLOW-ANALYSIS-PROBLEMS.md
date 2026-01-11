# FLOW_COMPARISON_ANALYSIS.md - Lines 92-1111
# Sections 1-4: Award Parser, Flow Analysis, Comparative Analysis, Problems

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
│         ┌────────────────────────────────────────────────────────────┐     │
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
