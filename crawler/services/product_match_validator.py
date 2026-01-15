"""
Product Match Validator Service.

This module provides multi-level validation to prevent enrichment cross-contamination
when merging data from multiple sources. It ensures that extracted data from a source
actually belongs to the target product being enriched.

Task Reference: GENERIC_SEARCH_V3_TASKS.md Task 1.1
Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.2 (FEAT-002)

The Problem:
    When enriching "Frank August Bourbon", a search might return pages about
    "Frank August Rye". Without validation, the rye's tasting notes could
    contaminate the bourbon's data.

Solution - 3-Level Validation:
    Level 1 (Brand Matching):
        Target and extracted brand names must overlap. Either one can be
        contained within the other (e.g., "Glenfiddich" matches "The Glenfiddich
        Distillery"). Empty brands are allowed to pass.

    Level 2 (Product Type Keywords):
        Checks for mutually exclusive keywords that indicate different products.
        For example, if target has "bourbon" and extracted has "rye", they are
        different products and should be rejected.

    Level 3 (Name Token Overlap):
        At least 30% of significant tokens must overlap between target and
        extracted product names. Tokens are filtered to remove stopwords and
        short words (< 3 chars).

Example:
    >>> validator = ProductMatchValidator()
    >>> target = {"name": "Frank August Bourbon", "brand": "Frank August"}
    >>> extracted = {"name": "Frank August Rye Whiskey", "brand": "Frank August"}
    >>> is_match, reason = validator.validate(target, extracted)
    >>> print(is_match, reason)
    False product_type_mismatch: target has {'bourbon'}, extracted has {'rye', 'corn whiskey'}

Usage:
    from crawler.services.product_match_validator import get_product_match_validator

    validator = get_product_match_validator()
    is_match, reason = validator.validate(target_data, extracted_data)

    if is_match:
        # Safe to merge extracted_data with target
        merger.merge(target_data, extracted_data)
    else:
        # Reject and log reason
        logger.warning(f"Rejected enrichment: {reason}")
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# Level 2: Mutually exclusive keyword groups for product type validation.
# Each tuple contains two sets of keywords that are mutually exclusive.
# If target has a keyword from group_a and extracted has a keyword from group_b,
# the match is rejected (and vice versa).
#
# Business Rules:
# - Bourbon and Rye Whiskey are distinct whiskey types that should never be conflated
#   IMPORTANT: Use specific phrases like "rye whiskey", "straight rye" to avoid
#   false positives from "high rye mashbill" in bourbon descriptions
# - Single Malt and Blended are fundamentally different production methods
# - Vintage and LBV (Late Bottled Vintage) are different port wine categories
# - Tawny and Ruby are distinct port wine styles with different aging processes
#
# NOTE: Scotch/Irish/Japanese/American rule was REMOVED because it caused false
# positives when official Scotch distillery pages mention other whisky types in
# navigation, footers, or general text. Brand and name overlap validation are
# sufficient to prevent cross-contamination between these categories.
MUTUALLY_EXCLUSIVE_KEYWORDS: List[Tuple[Set[str], Set[str]]] = [
    # Use specific "rye whiskey" phrases to avoid matching "high rye mashbill" in bourbons
    ({"bourbon"}, {"rye whiskey", "straight rye", "rye whisky", "corn whiskey"}),
    ({"single malt"}, {"blended", "blend"}),
    # REMOVED: ({"scotch"}, {"irish", "japanese", "american"}) - too aggressive
    ({"vintage"}, {"lbv", "late bottled vintage"}),
    ({"tawny"}, {"ruby"}),
]

# Level 3: Token filtering constants for name overlap validation.
# These stopwords are common English words that don't contribute to product identity.
STOPWORDS: Set[str] = {"the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for"}

# Category-specific stopwords that don't contribute to product identity.
# These terms are common across many products in the same category and would
# inflate token counts unfairly, causing false negatives in name matching.
#
# Example problem: "Ballantine's 10 YO Blended Scotch Whisky"
# Without filtering: tokens = {ballantine, blended, scotch, whisky} = 4 tokens
# If extracted has "Ballantine 10 Year", overlap = {ballantine} = 1/4 = 25% < 30% = FAIL
#
# With filtering: tokens = {ballantine} = 1 token
# Overlap = {ballantine} = 1/1 = 100% = PASS
#
# These categories are filtered:
# - Product type: whisky, whiskey, port, wine, spirit, liquor
# - Category: scotch, bourbon, rye, malt, blended, single, tawny, ruby
# - Age indicators: year, years, old, aged
# - Bottling info: cask, strength, reserve, edition, limited, special
# - Production: distillery, bottled, vintage
CATEGORY_STOPWORDS: Set[str] = {
    # Product types
    "whisky", "whiskey", "port", "wine", "spirit", "spirits", "liquor",
    # Whisky categories
    "scotch", "bourbon", "malt", "blended", "single", "straight",
    # Port wine categories
    "tawny", "ruby", "vintage", "lbv",
    # Age indicators
    "year", "years", "old", "aged",
    # Bottling info
    "cask", "strength", "reserve", "edition", "limited", "special",
    "release", "collection", "batch", "bottled",
    # Geographic terms (already in name as part of brand typically)
    "highland", "speyside", "islay", "lowland", "campbeltown", "kentucky",
}

# Minimum token length to be considered significant (filters out abbreviations and noise).
MIN_TOKEN_LENGTH: int = 3

# Minimum required overlap ratio between target and extracted name tokens.
# 30% threshold balances between catching obvious mismatches while allowing
# minor variations in product naming across sources.
MIN_OVERLAP_RATIO: float = 0.30


class ProductMatchValidator:
    """
    Validates that extracted data matches the target product.

    This class implements 3-level validation to prevent enrichment cross-contamination
    when merging data from multiple sources. Each level adds more specificity to the
    validation, and all levels must pass for a match to be confirmed.

    Validation Levels:
        Level 1 - Brand Matching:
            Checks if brand names overlap (one contained in the other).
            Empty brands are considered a match.
            Brand names are normalized to handle apostrophes, hyphens, etc.

        Level 2 - Product Type Keywords:
            Checks for mutually exclusive keywords that indicate different products.
            Uses MUTUALLY_EXCLUSIVE_KEYWORDS constant for keyword groups.

        Level 3 - Name Token Overlap:
            Checks if at least 30% of significant tokens overlap between names.
            Filters out stopwords and short tokens.

    Attributes:
        stopwords: Set of common words to filter from token analysis.
        min_token_length: Minimum length for a token to be considered significant.
        min_overlap_ratio: Minimum required overlap ratio for name matching.
        mutually_exclusive_keywords: List of mutually exclusive keyword pairs.

    Example:
        >>> validator = ProductMatchValidator()
        >>> target = {"name": "Glenfiddich 18 Year", "brand": "Glenfiddich"}
        >>> extracted = {"name": "Glenfiddich 18 Year Old Single Malt", "brand": "Glenfiddich"}
        >>> is_match, reason = validator.validate(target, extracted)
        >>> print(is_match)
        True
    """

    def __init__(self) -> None:
        """Initialize the ProductMatchValidator with default configuration."""
        self.stopwords = STOPWORDS
        self.category_stopwords = CATEGORY_STOPWORDS
        self.min_token_length = MIN_TOKEN_LENGTH
        self.min_overlap_ratio = MIN_OVERLAP_RATIO
        self.mutually_exclusive_keywords = MUTUALLY_EXCLUSIVE_KEYWORDS

    def _normalize_brand(self, brand: str) -> str:
        """
        Normalize brand name for comparison by removing special characters.

        This handles common variations in brand names across different sources:
        - Removes apostrophes (straight ' and curly '/') for brands like "Ballantine's"
        - Normalizes hyphens and whitespace for brands like "Johnnie-Walker"
        - Removes "The " prefix for brands like "The Macallan"

        Args:
            brand: Brand name to normalize. May be empty.

        Returns:
            Normalized lowercase brand name with special characters removed.
            Returns empty string if input is empty or None.

        Example:
            >>> validator = ProductMatchValidator()
            >>> validator._normalize_brand("Ballantine's")
            'ballantines'
            >>> validator._normalize_brand("The Macallan")
            'macallan'
            >>> validator._normalize_brand("Johnnie-Walker")
            'johnnie walker'
        """
        if not brand:
            return ""

        # Remove apostrophes (straight ', curly ', Unicode variations U+2019 U+2018)
        normalized = re.sub(r"['\u2019\u2018\u0027]", "", brand)

        # Normalize hyphens to spaces
        normalized = re.sub(r"-", " ", normalized)

        # Normalize multiple whitespace to single space
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove "The " prefix (case insensitive)
        normalized = re.sub(r"^the\s+", "", normalized, flags=re.IGNORECASE)

        return normalized.lower().strip()

    def validate(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate that extracted data matches the target product.

        Runs all three validation levels in order. If any level fails,
        validation stops and returns False with a reason. All levels must
        pass for the validation to succeed.

        Args:
            target_data: Original product data being enriched. Expected keys
                include 'name', 'brand', 'category', 'description', 'product_type'.
            extracted_data: Data extracted from a new source to be validated
                against the target. Same expected keys as target_data.

        Returns:
            A tuple of (is_match, reason) where:
            - is_match: True if all validation levels pass, False otherwise.
            - reason: A string describing the validation result. For failures,
                this explains which level failed and why. For success, returns
                "product_match_validated".

        Example:
            >>> validator = ProductMatchValidator()
            >>> target = {"name": "Lagavulin 16", "brand": "Lagavulin"}
            >>> extracted = {"name": "Lagavulin 16 Year", "brand": "Lagavulin"}
            >>> is_match, reason = validator.validate(target, extracted)
            >>> print(is_match, reason)
            True product_match_validated
        """
        logger.debug(
            "Validating product match: target='%s', extracted='%s'",
            target_data.get("name", ""),
            extracted_data.get("name", "")
        )

        # Level 1: Brand matching
        target_brand = target_data.get("brand", "")
        extracted_brand = extracted_data.get("brand", "")
        is_match, reason = self._validate_brand_match(target_brand, extracted_brand)
        if not is_match:
            logger.info("Product match failed: %s", reason)
            return False, reason

        # Level 2: Product type keywords
        is_match, reason = self._validate_product_type_keywords(target_data, extracted_data)
        if not is_match:
            logger.info("Product match failed: %s", reason)
            return False, reason

        # Level 3: Name token overlap
        target_name = target_data.get("name", "")
        extracted_name = extracted_data.get("name", "")
        is_match, reason = self._validate_name_overlap(target_name, extracted_name)
        if not is_match:
            logger.info("Product match failed: %s", reason)
            return False, reason

        logger.debug("Product match validated: all levels passed")
        return True, "product_match_validated"

    def _validate_brand_match(
        self,
        target_brand: Optional[str],
        extracted_brand: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Level 1: Validate brand matching.

        Checks if the brand names overlap by seeing if one is contained within
        the other. This handles cases where brands have variations like
        "Macallan" vs "The Macallan" or "Ballantine's" vs "Ballantines".

        Brand names are normalized before comparison to handle:
        - Apostrophes (straight ' and curly ')
        - Hyphens vs spaces ("Johnnie-Walker" vs "Johnnie Walker")
        - "The" prefix ("The Macallan" vs "Macallan")

        Empty brands are allowed because:
        1. Not all products have brand information
        2. We don't want to reject valid data just because brand is missing
        3. Other validation levels will catch mismatches

        Args:
            target_brand: Brand name from target product. May be None or empty.
            extracted_brand: Brand name from extracted data. May be None or empty.

        Returns:
            A tuple of (is_match, reason) where:
            - is_match: True if brands match or one/both are empty.
            - reason: "both_empty", "one_empty_allowed", "brand_overlap", or
                "brand_mismatch: target='X', extracted='Y'".
        """
        # Handle None and empty string cases
        target_empty = not target_brand or not target_brand.strip()
        extracted_empty = not extracted_brand or not extracted_brand.strip()

        if target_empty and extracted_empty:
            return True, "both_empty"

        if target_empty or extracted_empty:
            return True, "one_empty_allowed"

        # Normalize brands to handle apostrophes, hyphens, "The" prefix
        # This fixes the Ballantine's vs Ballantines mismatch issue
        target_normalized = self._normalize_brand(target_brand)
        extracted_normalized = self._normalize_brand(extracted_brand)

        # Check for overlap (one contained in the other)
        # This handles cases like "Macallan" matching "The Macallan"
        if target_normalized in extracted_normalized or extracted_normalized in target_normalized:
            return True, "brand_overlap"

        return False, f"brand_mismatch: target='{target_brand}', extracted='{extracted_brand}'"

    def _validate_product_type_keywords(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Level 2: Validate product type keywords are not mutually exclusive.

        Searches for mutually exclusive keywords in the combined text of name,
        category, description, and product_type fields. If the target has a
        keyword from one exclusive group and the extracted data has a keyword
        from the opposing group, the match is rejected.

        Business Logic Examples:
        - Target "Frank August Bourbon" + Extracted "Frank August Rye" -> REJECTED
        - Target "Glenfiddich Single Malt" + Extracted "Glenfiddich Blend" -> REJECTED
        - Target "Taylor's Vintage Port" + Extracted "Taylor's LBV Port" -> REJECTED

        Args:
            target_data: Target product data dict with text fields to search.
            extracted_data: Extracted product data dict with text fields to search.

        Returns:
            A tuple of (is_match, reason) where:
            - is_match: True if no mutually exclusive keywords found.
            - reason: "keywords_compatible" on success, or
                "product_type_mismatch: target has {group_a}, extracted has {group_b}"
                on failure.
        """
        target_text = self._build_keyword_text(target_data)
        extracted_text = self._build_keyword_text(extracted_data)

        for group_a, group_b in self.mutually_exclusive_keywords:
            target_has_a = any(kw in target_text for kw in group_a)
            extracted_has_b = any(kw in extracted_text for kw in group_b)

            if target_has_a and extracted_has_b:
                return False, f"product_type_mismatch: target has {group_a}, extracted has {group_b}"

            # Also check reverse (target has B, extracted has A)
            target_has_b = any(kw in target_text for kw in group_b)
            extracted_has_a = any(kw in extracted_text for kw in group_a)

            if target_has_b and extracted_has_a:
                return False, f"product_type_mismatch: target has {group_b}, extracted has {group_a}"

        return True, "keywords_compatible"

    def _build_keyword_text(self, data: Dict[str, Any]) -> str:
        """
        Build searchable text from product data for keyword matching.

        Combines multiple text fields into a single lowercase string for
        keyword searching. This ensures we catch product type indicators
        regardless of which field they appear in.

        Args:
            data: Product data dict that may contain 'name', 'category',
                'description', and 'product_type' fields.

        Returns:
            Combined lowercase text string from all available text fields,
            joined by spaces. Returns empty string if no text fields found.
        """
        parts = []

        for field in ["name", "category", "description", "product_type"]:
            value = data.get(field)
            if value and isinstance(value, str):
                parts.append(value.lower())

        return " ".join(parts)

    def _validate_name_overlap(
        self,
        target_name: Optional[str],
        extracted_name: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Level 3: Validate name token overlap meets minimum threshold.

        Tokenizes both names, filters out stopwords and short tokens, then
        calculates the overlap ratio. At least 30% of tokens must overlap
        for the match to pass.

        The 30% threshold is chosen to:
        - Allow minor naming variations across sources
        - Catch obvious mismatches (e.g., completely different products)
        - Handle cases where one source has more detailed naming

        Args:
            target_name: Product name from target data. May be None or empty.
            extracted_name: Product name from extracted data. May be None or empty.

        Returns:
            A tuple of (is_match, reason) where:
            - is_match: True if overlap ratio >= 30% or insufficient tokens.
            - reason: "insufficient_tokens" if either name lacks significant tokens,
                "name_overlap_X.XX" where X.XX is the overlap ratio on success,
                or "name_mismatch: overlap=X.XX, tokens={...}" on failure.
        """
        target_tokens = self._tokenize(target_name or "")
        extracted_tokens = self._tokenize(extracted_name or "")

        # If either has insufficient tokens, allow (can't make determination)
        # This handles edge cases like single-word names or names with only stopwords
        if not target_tokens or not extracted_tokens:
            return True, "insufficient_tokens"

        # Calculate overlap ratio using the larger token set as denominator
        # This penalizes cases where one name is much more specific than the other
        overlap = target_tokens.intersection(extracted_tokens)
        max_tokens = max(len(target_tokens), len(extracted_tokens))
        overlap_ratio = len(overlap) / max_tokens

        if overlap_ratio >= self.min_overlap_ratio:
            return True, f"name_overlap_{overlap_ratio:.2f}"

        return False, f"name_mismatch: overlap={overlap_ratio:.2f}, tokens={overlap}"

    def _tokenize(self, text: str) -> Set[str]:
        """
        Tokenize text into a set of significant tokens.

        Splits text on non-alphanumeric characters, converts to lowercase,
        and filters out:
        - General stopwords (the, a, an, of, etc.)
        - Category-specific stopwords (whisky, scotch, bourbon, year, etc.)
        - Tokens shorter than MIN_TOKEN_LENGTH

        This improved filtering ensures product identity tokens (brand, name)
        are prioritized over common category terms that would inflate counts.

        Args:
            text: Text to tokenize. May be empty.

        Returns:
            Set of significant lowercase tokens. Returns empty set if input
            is empty or contains only stopwords/short tokens.

        Example:
            >>> validator = ProductMatchValidator()
            >>> tokens = validator._tokenize("Ballantine's 10 Year Blended Scotch Whisky")
            >>> print(tokens)
            {'ballantines'}  # category terms 'year', 'blended', 'scotch', 'whisky' filtered
        """
        if not text:
            return set()

        # Convert to lowercase and split on non-alphanumeric characters
        text_lower = text.lower()
        tokens = re.split(r'[^a-z0-9]+', text_lower)

        # Filter out stopwords, category stopwords, and short tokens
        # This ensures product identity tokens are prioritized
        filtered = {
            token for token in tokens
            if token
            and token not in self.stopwords
            and token not in self.category_stopwords
            and len(token) >= self.min_token_length
        }

        return filtered


# Singleton instance for module-level access
_validator: Optional[ProductMatchValidator] = None


def get_product_match_validator() -> ProductMatchValidator:
    """
    Get the singleton ProductMatchValidator instance.

    Creates a new instance on first call, then returns the same instance
    on subsequent calls. Use reset_product_match_validator() to clear
    the singleton (mainly for testing).

    Returns:
        The shared ProductMatchValidator instance.

    Example:
        >>> validator = get_product_match_validator()
        >>> is_match, reason = validator.validate(target, extracted)
    """
    global _validator
    if _validator is None:
        _validator = ProductMatchValidator()
    return _validator


def reset_product_match_validator() -> None:
    """
    Reset the singleton ProductMatchValidator instance.

    Clears the singleton so the next call to get_product_match_validator()
    creates a fresh instance. Primarily used in tests to ensure isolation
    between test cases.
    """
    global _validator
    _validator = None
