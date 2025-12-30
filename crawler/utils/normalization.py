"""
Product name normalization utility functions.

Task Group 12: ProductCandidate Staging Model

Provides name normalization utilities for product deduplication and matching.
These transformations help identify products that are the same but named
differently across different sources.

Normalization Rules:
- Lowercase transformation
- Remove leading "the"
- Standardize: "years/yrs/yo/y.o." -> "year"
- Remove trademark symbols (R), (TM)
- Standardize quotes and apostrophes
- Remove extra whitespace
- Expand common abbreviations
"""

import re
from typing import Optional


def normalize_product_name(name: str) -> str:
    """
    Normalize a product name for deduplication matching.

    Applies a series of transformations to standardize product names across
    different sources. This helps identify the same product when named
    differently (e.g., "The Macallan 18 Years Old" vs "Macallan 18yo").

    Args:
        name: The original product name to normalize

    Returns:
        The normalized product name

    Example:
        >>> normalize_product_name("The Macallan(R) 18 Years Old Double Cask")
        'macallan 18 year old double cask'
    """
    if not name:
        return ""

    # Strip leading/trailing whitespace first
    result = name.strip()

    if not result:
        return ""

    # 1. Lowercase transformation
    result = result.lower()

    # 2. Remove trademark symbols (R), (TM), registered marks
    result = re.sub(r'\(r\)|\(tm\)|®|™', '', result, flags=re.IGNORECASE)

    # 3. Standardize quotes and apostrophes - remove them all
    # This handles: ' ' " " ' `
    result = re.sub(r"['''\"`]", '', result)

    # 4. Remove leading "the " (with word boundary)
    result = re.sub(r'^the\s+', '', result)

    # 5. Standardize year variations
    # "years" -> "year", "yrs" -> "year"
    result = re.sub(r'\byears\b', 'year', result)
    result = re.sub(r'\byrs\b', 'year', result)

    # "18yo" -> "18 year", "18 y.o." -> "18 year", "18y/o" -> "18 year"
    result = re.sub(r'(\d+)\s*y\.?o\.?', r'\1 year', result)
    result = re.sub(r'(\d+)\s*y/o', r'\1 year', result)

    # 6. Remove extra whitespace (collapse multiple spaces to single)
    result = re.sub(r'\s+', ' ', result)

    # 7. Strip again after all transformations
    result = result.strip()

    return result


def expand_abbreviations(name: str) -> str:
    """
    Expand common abbreviations in product names.

    This is a supplementary function for additional normalization
    when needed for fuzzy matching.

    Args:
        name: The product name to process

    Returns:
        The product name with abbreviations expanded

    Example:
        >>> expand_abbreviations("macallan ltd edition")
        'macallan limited edition'
    """
    if not name:
        return ""

    result = name.lower().strip()

    # Common abbreviation expansions
    abbreviations = {
        r'\bltd\b': 'limited',
        r'\bed\b': 'edition',
        r'\bsgl\b': 'single',
        r'\bdist\b': 'distillery',
        r'\bvint\b': 'vintage',
        r'\bbbl\b': 'barrel',
        r'\bcs\b': 'cask strength',
        r'\bsc\b': 'single cask',
        r'\bib\b': 'independent bottler',
        r'\bnr\b': 'new release',
        r'\ble\b': 'limited edition',
    }

    for pattern, replacement in abbreviations.items():
        result = re.sub(pattern, replacement, result)

    return result


def generate_match_key(name: str, brand: Optional[str] = None, abv: Optional[float] = None) -> str:
    """
    Generate a key for quick matching based on normalized fields.

    Combines normalized name with optional brand and ABV for more
    precise matching.

    Args:
        name: The product name
        brand: Optional brand name
        abv: Optional ABV value

    Returns:
        A match key string for comparison

    Example:
        >>> generate_match_key("Macallan 18 Year", brand="Macallan", abv=43.0)
        'macallan:macallan 18 year:43.0'
    """
    normalized_name = normalize_product_name(name)
    normalized_brand = normalize_product_name(brand) if brand else ""

    parts = []
    if normalized_brand:
        parts.append(normalized_brand)
    parts.append(normalized_name)
    if abv is not None:
        parts.append(str(abv))

    return ":".join(parts)
