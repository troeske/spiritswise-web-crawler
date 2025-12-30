"""
Matching Pipeline Service for Product Deduplication.

Task Group 13: Matching Pipeline Implementation

This service implements a multi-step matching pipeline to identify duplicate
products across different sources. The pipeline runs in order of confidence:

1. GTIN Match (confidence: 1.0) - Exact barcode match
2. Fingerprint Match (confidence: 0.95) - Computed fingerprint match
3. Fuzzy Name Match (confidence: 0.7-0.9) - Levenshtein/token similarity

Additionally provides variant detection to identify different expressions
of the same base product (e.g., Macallan 18 Sherry Oak vs Macallan 18 Double Cask).

Matching thresholds:
- High confidence (>0.9): Auto-merge into existing product
- Medium confidence (0.7-0.9): Create product, flag for review
- Low confidence (<0.7) or no match: Create new product
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List, Dict, Any

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from crawler.models import (
    DiscoveredProduct,
    ProductCandidate,
    ProductCandidateMatchStatus,
)
from crawler.utils.normalization import normalize_product_name

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """
    Result from a matching attempt.

    Attributes:
        matched_product: The DiscoveredProduct that was matched
        confidence: Confidence score (0.0 to 1.0)
        method: Matching method used (gtin, fingerprint, fuzzy)
        details: Additional match details for debugging
    """
    matched_product: DiscoveredProduct
    confidence: float
    method: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class VariantResult:
    """
    Result from variant detection.

    Attributes:
        is_variant: Whether the product is a variant of the base
        variant_type: Type of variant (cask_finish, cask_strength, etc.)
        base_product: The base product this is a variant of
    """
    is_variant: bool
    variant_type: Optional[str]
    base_product: DiscoveredProduct


# Variant detection patterns
VARIANT_PATTERNS = {
    "cask_finish": [
        "sherry", "port", "rum", "wine", "madeira", "cognac",
        "sauternes", "burgundy", "bordeaux", "champagne",
        "pedro ximenez", "px", "oloroso", "moscatel",
        "triple cask", "double cask", "triple wood", "double wood",
        "quarter cask", "first fill", "second fill",
    ],
    "cask_strength": [
        "cask strength", "cs", "full strength", "barrel proof",
        "barrel strength", "original proof", "natural cask strength",
    ],
    "travel_retail": [
        "travel retail", "travel exclusive", "duty free",
        "airport exclusive", "tr exclusive",
    ],
    "limited_edition": [
        "limited edition", "limited release", "special edition",
        "special release", "collectors edition", "anniversary",
        "commemorative", "rare", "exclusive",
    ],
}


def match_by_gtin(candidate_data: Dict[str, Any]) -> Optional[MatchResult]:
    """
    Match product by GTIN barcode.

    Step 1 in the matching pipeline. GTIN is a unique identifier
    so matching on it provides 100% confidence.

    Args:
        candidate_data: Extracted data from the candidate

    Returns:
        MatchResult with confidence 1.0 if GTIN matches, None otherwise
    """
    gtin = candidate_data.get("gtin")

    if not gtin:
        return None

    # Clean GTIN (remove spaces, dashes)
    gtin = str(gtin).replace(" ", "").replace("-", "")

    # Query for existing product with this GTIN
    try:
        existing = DiscoveredProduct.objects.filter(gtin=gtin).first()
        if existing:
            logger.info(f"GTIN match found: {gtin} -> product {existing.id}")
            return MatchResult(
                matched_product=existing,
                confidence=1.0,
                method="gtin",
                details={"matched_gtin": gtin},
            )
    except Exception as e:
        logger.error(f"Error during GTIN matching: {e}")

    return None


def match_by_fingerprint(candidate_data: Dict[str, Any]) -> Optional[MatchResult]:
    """
    Match product by computed fingerprint.

    Step 2 in the matching pipeline. Fingerprint is computed from:
    brand + normalized_name + abv + age_statement + volume_ml

    Args:
        candidate_data: Extracted data from the candidate

    Returns:
        MatchResult with confidence 0.95 if fingerprint matches, None otherwise
    """
    # Compute fingerprint from candidate data
    candidate_fingerprint = DiscoveredProduct.compute_fingerprint(candidate_data)

    if not candidate_fingerprint:
        return None

    # Query for existing product with this fingerprint
    try:
        existing = DiscoveredProduct.objects.filter(
            fingerprint=candidate_fingerprint
        ).first()
        if existing:
            logger.info(
                f"Fingerprint match found: {candidate_fingerprint[:16]}... -> "
                f"product {existing.id}"
            )
            return MatchResult(
                matched_product=existing,
                confidence=0.95,
                method="fingerprint",
                details={"matched_fingerprint": candidate_fingerprint[:16]},
            )
    except Exception as e:
        logger.error(f"Error during fingerprint matching: {e}")

    return None


def match_by_fuzzy_name(
    candidate_data: Dict[str, Any],
    similarity_threshold: float = 0.85,
) -> Optional[MatchResult]:
    """
    Match product by fuzzy name matching.

    Step 3 in the matching pipeline. Uses multiple similarity measures:
    - Levenshtein distance
    - Token set ratio (handles word reordering)
    - Partial ratio (handles substrings)

    Thresholds:
    - >= 0.85 similarity + same brand + same product_type = likely match
    - >= 0.90 similarity + same ABV = likely match

    Args:
        candidate_data: Extracted data from the candidate
        similarity_threshold: Minimum similarity score to consider a match

    Returns:
        MatchResult with confidence 0.7-0.9 if fuzzy match found, None otherwise
    """
    candidate_name = candidate_data.get("name", "")
    candidate_brand = candidate_data.get("brand", "")
    candidate_abv = candidate_data.get("abv")
    candidate_product_type = candidate_data.get("product_type", "")

    if not candidate_name:
        return None

    # Normalize the candidate name
    normalized_candidate = normalize_product_name(candidate_name)

    if not normalized_candidate:
        return None

    # Build query for potential matches
    queryset = DiscoveredProduct.objects.all()

    # If brand is provided, filter by brand first
    if candidate_brand:
        normalized_brand = normalize_product_name(candidate_brand)
        queryset = queryset.filter(
            brand__name__icontains=normalized_brand
        ) | queryset.filter(
            name__icontains=normalized_brand
        )

    # Limit to same product type if provided
    if candidate_product_type:
        queryset = queryset.filter(product_type=candidate_product_type)

    # Get potential matches (limit to reasonable number)
    potential_matches = queryset[:100]

    best_match = None
    best_score = 0.0
    best_details = {}

    for product in potential_matches:
        normalized_product = normalize_product_name(product.name)

        if not normalized_product:
            continue

        # Calculate multiple similarity scores
        token_set_ratio = fuzz.token_set_ratio(
            normalized_candidate, normalized_product
        ) / 100.0
        partial_ratio = fuzz.partial_ratio(
            normalized_candidate, normalized_product
        ) / 100.0
        ratio = fuzz.ratio(normalized_candidate, normalized_product) / 100.0

        # Use the best of the similarity measures
        similarity = max(token_set_ratio, partial_ratio, ratio)

        # Apply brand bonus
        brand_match = False
        if candidate_brand and product.brand:
            brand_normalized = normalize_product_name(product.brand.name)
            candidate_brand_normalized = normalize_product_name(candidate_brand)
            if brand_normalized == candidate_brand_normalized:
                brand_match = True
                similarity = min(1.0, similarity + 0.05)

        # Apply ABV match bonus
        abv_match = False
        if candidate_abv and product.abv:
            try:
                abv_diff = abs(float(candidate_abv) - float(product.abv))
                if abv_diff < 0.5:  # Within 0.5% ABV
                    abv_match = True
                    similarity = min(1.0, similarity + 0.05)
            except (ValueError, TypeError):
                pass

        # Check threshold conditions
        is_match = False

        # Condition 1: >= 0.85 similarity + same brand + same product_type
        if similarity >= 0.85 and brand_match:
            is_match = True

        # Condition 2: >= 0.90 similarity + same ABV
        if similarity >= 0.90 and abv_match:
            is_match = True

        # Condition 3: Very high similarity (>= 0.95)
        if similarity >= 0.95:
            is_match = True

        if is_match and similarity > best_score:
            best_score = similarity
            best_match = product
            best_details = {
                "token_set_ratio": token_set_ratio,
                "partial_ratio": partial_ratio,
                "ratio": ratio,
                "brand_match": brand_match,
                "abv_match": abv_match,
            }

    if best_match and best_score >= similarity_threshold:
        # Map similarity to confidence (0.7 - 0.9 range)
        confidence = 0.7 + (best_score - similarity_threshold) * (0.2 / (1.0 - similarity_threshold))
        confidence = min(0.9, max(0.7, confidence))

        logger.info(
            f"Fuzzy match found: '{candidate_name}' -> "
            f"'{best_match.name}' (score: {best_score:.3f}, conf: {confidence:.3f})"
        )

        return MatchResult(
            matched_product=best_match,
            confidence=confidence,
            method="fuzzy",
            details={
                "similarity_score": best_score,
                **best_details,
            },
        )

    return None


def detect_variant(
    candidate_data: Dict[str, Any],
    potential_base: DiscoveredProduct,
) -> Optional[VariantResult]:
    """
    Detect if candidate is a variant of an existing product.

    Same base product, different expressions (e.g., cask finish variants)
    should be linked as variants rather than merged.

    Args:
        candidate_data: Extracted data from the candidate
        potential_base: Potential base product to check against

    Returns:
        VariantResult if variant detected, None otherwise
    """
    candidate_name = normalize_product_name(candidate_data.get("name", ""))
    base_name = normalize_product_name(potential_base.name)

    if not candidate_name or not base_name:
        return None

    # Check if names are too similar (likely same product, not variant)
    similarity = fuzz.ratio(candidate_name, base_name) / 100.0
    if similarity > 0.95:
        return None  # Same product, not a variant

    # Check if base name is contained in candidate name
    if base_name not in candidate_name:
        # Check partial containment
        base_words = set(base_name.split())
        candidate_words = set(candidate_name.split())

        # At least 60% of base words should be in candidate
        common_words = base_words.intersection(candidate_words)
        if len(common_words) < len(base_words) * 0.6:
            return None

    # Check for variant patterns
    candidate_lower = candidate_name.lower()

    for variant_type, patterns in VARIANT_PATTERNS.items():
        for pattern in patterns:
            if pattern in candidate_lower and pattern not in base_name.lower():
                logger.info(
                    f"Variant detected: '{candidate_name}' is {variant_type} "
                    f"variant of '{base_name}'"
                )
                return VariantResult(
                    is_variant=True,
                    variant_type=variant_type,
                    base_product=potential_base,
                )

    return None


class MatchingPipeline:
    """
    Orchestrates the complete matching pipeline.

    Runs matching steps in order:
    1. GTIN matching (confidence 1.0)
    2. Fingerprint matching (confidence 0.95)
    3. Fuzzy name matching (confidence 0.7-0.9)

    Based on match confidence, takes appropriate action:
    - High (>0.9): Auto-merge
    - Medium (0.7-0.9): Flag for review
    - Low (<0.7) or no match: Create new product
    """

    def __init__(
        self,
        high_confidence_threshold: float = 0.9,
        low_confidence_threshold: float = 0.7,
    ):
        """
        Initialize the matching pipeline.

        Args:
            high_confidence_threshold: Above this, auto-merge (default 0.9)
            low_confidence_threshold: Below this, create new product (default 0.7)
        """
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold

    def process_candidate(self, candidate: ProductCandidate) -> Optional[MatchResult]:
        """
        Process a ProductCandidate through the matching pipeline.

        Args:
            candidate: The ProductCandidate to process

        Returns:
            MatchResult if a match was found, None otherwise
        """
        candidate_data = candidate.extracted_data or {}
        candidate_data["name"] = candidate_data.get("name", candidate.raw_name)

        logger.info(f"Processing candidate: {candidate.raw_name}")

        # Step 1: GTIN matching
        result = match_by_gtin(candidate_data)
        if result:
            self._update_candidate_matched(candidate, result)
            return result

        # Step 2: Fingerprint matching
        result = match_by_fingerprint(candidate_data)
        if result:
            self._update_candidate_matched(candidate, result)
            return result

        # Step 3: Fuzzy name matching
        result = match_by_fuzzy_name(candidate_data)
        if result:
            # Check for variant
            variant_result = detect_variant(candidate_data, result.matched_product)
            if variant_result:
                # This is a variant, not a duplicate
                self._update_candidate_variant(candidate, variant_result)
                return result

            # Apply confidence-based action
            if result.confidence > self.high_confidence_threshold:
                self._update_candidate_matched(candidate, result)
            elif result.confidence >= self.low_confidence_threshold:
                self._update_candidate_needs_review(candidate, result)
            else:
                self._update_candidate_new_product(candidate)
            return result

        # No match found
        self._update_candidate_new_product(candidate)
        return None

    def _update_candidate_matched(
        self,
        candidate: ProductCandidate,
        result: MatchResult,
    ) -> None:
        """Update candidate status to matched (auto-merge)."""
        candidate.match_status = ProductCandidateMatchStatus.MATCHED
        candidate.matched_product = result.matched_product
        candidate.match_confidence = result.confidence
        candidate.match_method = result.method
        candidate.save()

        logger.info(
            f"Candidate {candidate.id} auto-merged with product "
            f"{result.matched_product.id} (confidence: {result.confidence:.3f})"
        )

    def _update_candidate_needs_review(
        self,
        candidate: ProductCandidate,
        result: MatchResult,
    ) -> None:
        """Update candidate status to needs_review."""
        candidate.match_status = ProductCandidateMatchStatus.NEEDS_REVIEW
        candidate.matched_product = result.matched_product
        candidate.match_confidence = result.confidence
        candidate.match_method = result.method
        candidate.save()

        logger.info(
            f"Candidate {candidate.id} flagged for review "
            f"(potential match: {result.matched_product.id}, "
            f"confidence: {result.confidence:.3f})"
        )

    def _update_candidate_new_product(self, candidate: ProductCandidate) -> None:
        """Update candidate status to new_product."""
        candidate.match_status = ProductCandidateMatchStatus.NEW_PRODUCT
        candidate.match_confidence = 0.0
        candidate.match_method = None
        candidate.save()

        logger.info(f"Candidate {candidate.id} marked as new product (no match found)")

    def _update_candidate_variant(
        self,
        candidate: ProductCandidate,
        variant_result: VariantResult,
    ) -> None:
        """Update candidate status for variant."""
        candidate.match_status = ProductCandidateMatchStatus.NEW_PRODUCT
        candidate.match_confidence = 0.0
        candidate.match_method = None
        # Store variant info in extracted_data
        if candidate.extracted_data is None:
            candidate.extracted_data = {}
        candidate.extracted_data["_variant_of"] = str(variant_result.base_product.id)
        candidate.extracted_data["_variant_type"] = variant_result.variant_type
        candidate.save()

        logger.info(
            f"Candidate {candidate.id} identified as {variant_result.variant_type} "
            f"variant of product {variant_result.base_product.id}"
        )
