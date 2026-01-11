"""
Extraction prompt templates for different award sources.

These prompts are used by AIExtractor to extract structured product data
from award site detail pages. Each prompt is tailored for specific sources
and product types to maximize extraction accuracy.
"""

IWSC_EXTRACTION_PROMPT = """
Extract ALL product information from this IWSC competition result page.

Context:
- Competition: International Wine & Spirit Competition (IWSC)
- Year: {year}
- Medal (from listing): {medal_hint}
- Score (if available): {score_hint}
- Detected product type: {product_type_hint}

Extract these fields:

1. IDENTIFICATION:
   - Full product name
   - Brand/Producer name
   - Product type (whiskey, port_wine, gin, etc.)

2. SPECIFICATIONS:
   - ABV (alcohol percentage)
   - Age statement (years, if any)
   - Volume (ml)
   - Region/Country of origin

3. TASTING NOTES (CRITICAL - extract all available):
   - Nose/Aroma description
   - Palate description
   - Finish description
   - Flavor notes/tags

4. AWARD INFO:
   - Medal awarded (Gold, Silver, Bronze)
   - Score (if shown)
   - Category won

5. FOR WHISKEY:
   - Distillery name
   - Whiskey type (Single Malt, Bourbon, etc.)
   - Cask types used

6. FOR PORT WINE:
   - Style (Tawny, Ruby, Vintage, LBV, etc.)
   - Age indication (10 Year, 20 Year, etc.)
   - Harvest/Vintage year

Page content:
{content}

Return as JSON with snake_case keys.
"""

DWWA_PORT_EXTRACTION_PROMPT = """
Extract ALL product information from this Decanter World Wine Awards page.

Context:
- Competition: DWWA
- Year: {year}
- Medal hint: {medal_hint}
- This is a PORT WINE or FORTIFIED WINE

Extract:
1. Wine name, Producer
2. Style (tawny, ruby, LBV, vintage, colheita, white, rose)
3. Age indication
4. Country/Region (may NOT be Portugal for port-style wines)
5. Tasting notes: nose, palate, finish
6. Score/Medal
7. ABV, Price if shown

Page content:
{content}

Return as JSON.
"""

GENERAL_EXTRACTION_PROMPT = """
Extract product information from this spirits/wine page.

Product type hint: {product_type_hint}

Extract all available:
- Name, Brand, Product Type
- ABV, Age, Volume, Region, Country
- Tasting: nose_description, palate_description, finish_description
- Flavor tags/notes
- Price, Ratings, Awards

Page content:
{content}

Return as JSON with snake_case keys.
"""
