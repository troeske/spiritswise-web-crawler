"""
Whiskey Validators - Normalization and cleaning for whiskey product data.

Phase 11: Integration Failure Validators

Fixes 11 product failures:
- Whiskey type normalization (5 products)
- Vintage year cleaning (2 products)
- Brand fallback logic (3 products)
- Validation pipeline (1 product)
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional


# =============================================================================
# Whiskey Type Normalization
# =============================================================================

# Mapping of common whiskey type variations to normalized values
WHISKEY_TYPE_MAPPING = {
    # Single Malt Scotch variations
    "single malt": "scotch_single_malt",
    "single malt scotch": "scotch_single_malt",
    "single_malt_scotch": "scotch_single_malt",  # AI service format
    "single malt scotch whisky": "scotch_single_malt",
    "speyside single malt": "scotch_single_malt",
    "highland single malt": "scotch_single_malt",
    "islay single malt": "scotch_single_malt",
    "lowland single malt": "scotch_single_malt",
    "campbeltown single malt": "scotch_single_malt",
    "scotch single malt": "scotch_single_malt",
    "scotch_single_malt": "scotch_single_malt",

    # Blended Scotch variations
    "blended scotch": "scotch_blend",
    "blended scotch whisky": "scotch_blend",
    "scotch blend": "scotch_blend",
    "scotch_blend": "scotch_blend",

    # Bourbon variations
    "bourbon": "bourbon",
    "kentucky bourbon": "bourbon",
    "kentucky straight bourbon": "bourbon",
    "kentucky straight bourbon whiskey": "bourbon",
    "small batch bourbon": "bourbon",
    "single barrel bourbon": "bourbon",
    "straight bourbon": "bourbon",
    "wheated bourbon": "bourbon",

    # Tennessee variations
    "tennessee": "tennessee",
    "tennessee whiskey": "tennessee",
    "tennessee whisky": "tennessee",

    # Rye variations
    "rye": "rye",
    "rye whiskey": "rye",
    "straight rye": "rye",
    "straight rye whiskey": "rye",
    "kentucky straight rye": "rye",

    # American Single Malt
    "american single malt": "american_single_malt",

    # Irish variations
    "irish": "irish_blend",
    "irish whiskey": "irish_blend",
    "irish blend": "irish_blend",
    "irish_blend": "irish_blend",
    "irish single malt": "irish_single_malt",
    "irish_single_malt": "irish_single_malt",
    "irish single pot still": "irish_single_pot",
    "single pot still": "irish_single_pot",
    "irish_single_pot": "irish_single_pot",

    # Japanese variations
    "japanese": "japanese",
    "japanese whisky": "japanese",
    "japanese single malt": "japanese",

    # Canadian variations
    "canadian": "canadian",
    "canadian whisky": "canadian",
    "canadian rye": "canadian",

    # Indian variations
    "indian": "indian",
    "indian whisky": "indian",
    "indian single malt": "indian",

    # Taiwanese variations
    "taiwanese": "taiwanese",
    "taiwanese whisky": "taiwanese",
    "taiwan": "taiwanese",

    # Australian variations
    "australian": "australian",
    "australian whisky": "australian",

    # World Whiskey (catch-all)
    "world whiskey": "world_whiskey",
    "world whisky": "world_whiskey",
    "world_whiskey": "world_whiskey",
    "other": "world_whiskey",
}


def normalize_whiskey_type(whiskey_type: Optional[str]) -> Optional[str]:
    """
    Normalize whiskey type to valid enum values.

    Handles common variations like:
    - "Kentucky Straight Bourbon" -> "bourbon"
    - "Single Malt Scotch" -> "scotch_single_malt"
    - "Tennessee Whiskey" -> "tennessee"

    Args:
        whiskey_type: Raw whiskey type string

    Returns:
        Normalized whiskey type or None if input is None
    """
    if whiskey_type is None:
        return None

    # Normalize to lowercase for matching
    normalized = whiskey_type.lower().strip()

    # Check direct mapping
    if normalized in WHISKEY_TYPE_MAPPING:
        return WHISKEY_TYPE_MAPPING[normalized]

    # Check if it's already a valid enum value
    valid_types = [
        "scotch_single_malt", "scotch_blend", "bourbon", "tennessee",
        "rye", "american_single_malt", "irish_blend", "irish_single_malt",
        "irish_single_pot", "japanese", "canadian", "indian", "taiwanese",
        "australian", "world_whiskey",
    ]
    if normalized in valid_types:
        return normalized

    # Fallback to world_whiskey for unknown types
    return "world_whiskey"


# =============================================================================
# Vintage Year Cleaning
# =============================================================================


def clean_vintage_year(vintage_year: Any) -> Optional[int]:
    """
    Clean and validate vintage year values.

    Handles:
    - Null-like strings: "N/A", "None", "NV"
    - Year in string format: "2019", "2019 vintage"
    - Integer values: 2019
    - Invalid values: years before 1900 or after current year

    Args:
        vintage_year: Raw vintage year value

    Returns:
        Valid year as integer, or None if invalid
    """
    if vintage_year is None:
        return None

    # Handle string inputs
    if isinstance(vintage_year, str):
        cleaned = vintage_year.strip()

        # Handle empty string
        if not cleaned:
            return None

        # Handle null-like strings
        null_values = ["n/a", "na", "none", "nv", "non-vintage", "nonvintage", "-", ""]
        if cleaned.lower() in null_values:
            return None

        # Try to extract 4-digit year from string
        match = re.search(r'\b(19\d{2}|20\d{2})\b', cleaned)
        if match:
            year = int(match.group(1))
        else:
            # Try direct conversion
            try:
                year = int(cleaned)
            except ValueError:
                return None
    elif isinstance(vintage_year, (int, float)):
        year = int(vintage_year)
    else:
        return None

    # Validate year range (1900 to current year)
    current_year = datetime.now().year
    if year < 1900 or year > current_year:
        return None

    return year


# =============================================================================
# Brand Fallback Logic
# =============================================================================

# Known brand patterns for extraction
KNOWN_BRAND_PATTERNS = [
    # Possessive brands
    (r"^(Booker's)", "Booker's"),
    (r"^(Maker's Mark)", "Maker's Mark"),
    (r"^(Russell's Reserve)", "Russell's Reserve"),
    (r"^(Evan Williams)", "Evan Williams"),
    (r"^(Jack Daniel's)", "Jack Daniel's"),
    (r"^(Johnnie Walker)", "Johnnie Walker"),
    (r"^(Dewar's)", "Dewar's"),

    # Two-word brands
    (r"^(Buffalo Trace)", "Buffalo Trace"),
    (r"^(Wild Turkey)", "Wild Turkey"),
    (r"^(Jim Beam)", "Jim Beam"),
    (r"^(Elijah Craig)", "Elijah Craig"),
    (r"^(Four Roses)", "Four Roses"),
    (r"^(Woodford Reserve)", "Woodford Reserve"),
    (r"^(Bulleit Bourbon)", "Bulleit"),
    (r"^(Bulleit)", "Bulleit"),
    (r"^(Knob Creek)", "Knob Creek"),
    (r"^(Old Forester)", "Old Forester"),
    (r"^(Old Grand-Dad)", "Old Grand-Dad"),
    (r"^(Old Fitzgerald)", "Old Fitzgerald"),
    (r"^(Heaven Hill)", "Heaven Hill"),
    (r"^(Angel's Envy)", "Angel's Envy"),

    # Scottish brands
    (r"^(Glenfiddich)", "Glenfiddich"),
    (r"^(Glenlivet)", "Glenlivet"),
    (r"^(GlenAllachie)", "GlenAllachie"),
    (r"^(Benriach)", "Benriach"),
    (r"^(Macallan)", "Macallan"),
    (r"^(Ardbeg)", "Ardbeg"),
    (r"^(Laphroaig)", "Laphroaig"),
    (r"^(Lagavulin)", "Lagavulin"),
    (r"^(Highland Park)", "Highland Park"),
    (r"^(Talisker)", "Talisker"),
    (r"^(Oban)", "Oban"),
    (r"^(Bowmore)", "Bowmore"),

    # Number-based brands
    (r"^(1792)", "1792"),

    # Single word brands that need exact match
    (r"^(Bulleit)\b", "Bulleit"),
    (r"^(Balvenie)\b", "Balvenie"),
    (r"^(Kavalan)\b", "Kavalan"),
    (r"^(Arran)\b", "Arran"),
]


def extract_brand_from_name(name: Optional[str]) -> Optional[str]:
    """
    Extract brand name from product name when brand field is missing.

    Uses known brand patterns first, then falls back to extracting
    words before the first number.

    Args:
        name: Product name string

    Returns:
        Extracted brand name or None
    """
    if name is None or not name.strip():
        return None

    name = name.strip()

    # Check known brand patterns first
    for pattern, brand in KNOWN_BRAND_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return brand

    # Generic fallback: extract words before first number
    # e.g., "Unknown Distillery 12 Year Old" -> "Unknown Distillery"
    match = re.match(r'^(.+?)(?:\s+\d|\s+Year|\s+YO|\s+y\.o\.|$)', name, re.IGNORECASE)
    if match:
        potential_brand = match.group(1).strip()
        # Clean up common suffixes
        potential_brand = re.sub(r'\s+(Bourbon|Whiskey|Whisky|Rye|Single Malt)$', '', potential_brand, flags=re.IGNORECASE)
        if potential_brand:
            return potential_brand

    return None


# =============================================================================
# Full Validation Pipeline
# =============================================================================


def validate_whiskey_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full validation pipeline for whiskey product data.

    Applies all validators:
    1. Normalize whiskey_type
    2. Clean vintage_year
    3. Extract brand from name if missing

    Args:
        data: Raw whiskey data dictionary

    Returns:
        Validated and cleaned data dictionary
    """
    validated = data.copy()

    # Normalize whiskey_type
    if "whiskey_type" in validated:
        validated["whiskey_type"] = normalize_whiskey_type(validated["whiskey_type"])

    # Clean vintage_year
    if "vintage_year" in validated:
        validated["vintage_year"] = clean_vintage_year(validated["vintage_year"])

    # Extract brand from name if missing
    if not validated.get("brand") and validated.get("name"):
        validated["brand"] = extract_brand_from_name(validated["name"])

    return validated
