"""
Product Match Validator Service.

Task 1.1: Product Match Validator

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.2 (FEAT-002)

Multi-level validation to prevent enrichment cross-contamination:
- Level 1: Brand matching (target vs extracted must overlap)
- Level 2: Product type keywords (bourbon vs rye, single malt vs blended)
- Level 3: Name token overlap (>= 30% required)

Real-world example: "Frank August Bourbon" enrichment rejected data from "Frank August Rye" page.
"""

import logging
import re
from typing import Dict, Any, Tuple, Set, List, Optional

logger = logging.getLogger(__name__)


# Level 2: Mutually exclusive keyword groups
# If target has keyword from group_a and extracted has keyword from group_b, reject
MUTUALLY_EXCLUSIVE_KEYWORDS: List[Tuple[Set[str], Set[str]]] = [
    ({"bourbon"}, {"rye", "corn whiskey"}),
    ({"single malt"}, {"blended", "blend"}),
    ({"scotch"}, {"irish", "japanese", "american"}),
    ({"vintage"}, {"lbv", "late bottled vintage"}),
    ({"tawny"}, {"ruby"}),
]

# Level 3: Token filtering constants
STOPWORDS: Set[str] = {"the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for"}
MIN_TOKEN_LENGTH: int = 3
MIN_OVERLAP_RATIO: float = 0.30


class ProductMatchValidator:
    """
    Validates that extracted data matches the target product.

    Implements 3-level validation to prevent enrichment cross-contamination:
    - Level 1: Brand matching
    - Level 2: Product type keywords
    - Level 3: Name token overlap

    Usage:
        validator = ProductMatchValidator()
        is_match, reason = validator.validate(target_data, extracted_data)
        if is_match:
            # Safe to merge extracted data with target
        else:
            # Reject extracted data
    """

    def __init__(self):
        """Initialize the ProductMatchValidator."""
        self.stopwords = STOPWORDS
        self.min_token_length = MIN_TOKEN_LENGTH
        self.min_overlap_ratio = MIN_OVERLAP_RATIO
        self.mutually_exclusive_keywords = MUTUALLY_EXCLUSIVE_KEYWORDS

    def validate(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate that extracted data matches the target product.

        Runs all three validation levels in order:
        1. Brand matching
        2. Product type keywords
        3. Name token overlap

        Args:
            target_data: Original product data being enriched
            extracted_data: Data extracted from a new source

        Returns:
            Tuple of (is_match: bool, reason: str)
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

        Args:
            target_brand: Brand from target product
            extracted_brand: Brand from extracted data

        Returns:
            Tuple of (is_match: bool, reason: str)
        """
        # Handle None and empty string cases
        target_empty = not target_brand or not target_brand.strip()
        extracted_empty = not extracted_brand or not extracted_brand.strip()

        if target_empty and extracted_empty:
            return True, "both_empty"

        if target_empty or extracted_empty:
            return True, "one_empty_allowed"

        target_lower = target_brand.lower().strip()
        extracted_lower = extracted_brand.lower().strip()

        # Check for overlap (one contained in the other)
        if target_lower in extracted_lower or extracted_lower in target_lower:
            return True, "brand_overlap"

        return False, f"brand_mismatch: target='{target_brand}', extracted='{extracted_brand}'"

    def _validate_product_type_keywords(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Level 2: Validate product type keywords are not mutually exclusive.

        Args:
            target_data: Target product data dict
            extracted_data: Extracted product data dict

        Returns:
            Tuple of (is_match: bool, reason: str)
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

        Combines name, category, and description fields into lowercase text.

        Args:
            data: Product data dict

        Returns:
            Combined lowercase text for keyword searching
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

        Args:
            target_name: Name from target product
            extracted_name: Name from extracted data

        Returns:
            Tuple of (is_match: bool, reason: str)
        """
        target_tokens = self._tokenize(target_name or "")
        extracted_tokens = self._tokenize(extracted_name or "")

        # If either has insufficient tokens, allow (can't make determination)
        if not target_tokens or not extracted_tokens:
            return True, "insufficient_tokens"

        # Calculate overlap
        overlap = target_tokens.intersection(extracted_tokens)
        max_tokens = max(len(target_tokens), len(extracted_tokens))
        overlap_ratio = len(overlap) / max_tokens

        if overlap_ratio >= self.min_overlap_ratio:
            return True, f"name_overlap_{overlap_ratio:.2f}"

        return False, f"name_mismatch: overlap={overlap_ratio:.2f}, tokens={overlap}"

    def _tokenize(self, text: str) -> Set[str]:
        """
        Tokenize text into a set of significant tokens.

        Filters out stopwords and tokens shorter than MIN_TOKEN_LENGTH.

        Args:
            text: Text to tokenize

        Returns:
            Set of significant tokens (lowercase)
        """
        if not text:
            return set()

        # Convert to lowercase and split on non-alphanumeric characters
        text_lower = text.lower()
        tokens = re.split(r'[^a-z0-9]+', text_lower)

        # Filter out stopwords and short tokens
        filtered = {
            token for token in tokens
            if token
            and token not in self.stopwords
            and len(token) >= self.min_token_length
        }

        return filtered


# Singleton instance
_validator: Optional[ProductMatchValidator] = None


def get_product_match_validator() -> ProductMatchValidator:
    """Get singleton ProductMatchValidator instance."""
    global _validator
    if _validator is None:
        _validator = ProductMatchValidator()
    return _validator


def reset_product_match_validator() -> None:
    """Reset singleton for testing."""
    global _validator
    _validator = None
