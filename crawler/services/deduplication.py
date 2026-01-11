"""
ProductCandidate Deduplication Service.

RECT-014: Implements deduplication workflow for product candidates.

Matching Pipeline Order:
1. GTIN match (exact, highest priority)
2. Fingerprint match (exact, high priority)
3. Fuzzy name match (with brand filter, medium priority)

Confidence Thresholds:
- HIGH (>= 0.85): Auto-match to existing product
- MEDIUM (>= 0.65): Flag for manual review
- LOW (< 0.65): Create as new product
"""

import logging
import re
import unicodedata
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.db.models import Q

from crawler.models import (
    DiscoveredBrand,
    DiscoveredProduct,
    ProductCandidate,
    MatchStatusChoices,
    ProductType,
)

logger = logging.getLogger(__name__)

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.65

# Common suffixes to remove during normalization
COMMON_SUFFIXES = [
    "whisky", "whiskey", "scotch", "bourbon", "rum",
    "vodka", "gin", "tequila", "brandy", "cognac",
    "port", "wine", "sherry", "single malt", "blended",
]


def normalize_product_name(name: str) -> str:
    """
    Normalize a product name for matching purposes.

    Steps:
    1. Convert to lowercase
    2. Remove special characters and trademarks
    3. Normalize unicode characters
    4. Collapse multiple spaces
    5. Remove common suffixes (only specific ones at end)
    6. Trim whitespace

    Args:
        name: Raw product name

    Returns:
        Normalized name for matching
    """
    if not name:
        return ""

    # First, remove trademark symbols explicitly
    normalized = name.replace('™', '').replace('®', '').replace('©', '')

    # Normalize unicode (e.g., é -> e)
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')

    # Convert to lowercase
    normalized = normalized.lower()

    # Remove remaining special characters
    # Keep alphanumeric, spaces, and basic punctuation
    normalized = re.sub(r'[^\w\s-]', '', normalized)

    # Collapse multiple spaces into single space
    normalized = re.sub(r'\s+', ' ', normalized)

    # Only remove spirit type suffixes at the very end
    # (whisky, whiskey, rum, etc. - not descriptive terms like scotch)
    spirit_suffixes = ["whisky", "whiskey", "rum", "vodka", "gin", "tequila", "brandy", "cognac"]
    for suffix in spirit_suffixes:
        pattern = rf'\b{re.escape(suffix)}\b\s*$'
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

    # Final trim
    normalized = normalized.strip()

    return normalized


def match_by_gtin(gtin: Optional[str]) -> Optional[DiscoveredProduct]:
    """
    Find a product by exact GTIN match.

    Args:
        gtin: Global Trade Item Number (barcode)

    Returns:
        Matching DiscoveredProduct or None
    """
    if not gtin or not gtin.strip():
        return None

    gtin = gtin.strip()

    try:
        return DiscoveredProduct.objects.filter(gtin=gtin).first()
    except Exception as e:
        logger.error(f"Error matching by GTIN {gtin}: {e}")
        return None


def match_by_fingerprint(fingerprint: Optional[str]) -> Optional[DiscoveredProduct]:
    """
    Find a product by exact fingerprint match.

    Args:
        fingerprint: Product fingerprint (normalized identifier)

    Returns:
        Matching DiscoveredProduct or None
    """
    if not fingerprint or not fingerprint.strip():
        return None

    fingerprint = fingerprint.strip()

    try:
        return DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()
    except Exception as e:
        logger.error(f"Error matching by fingerprint {fingerprint}: {e}")
        return None


def match_by_fuzzy_name(
    name: str,
    brand: Optional[DiscoveredBrand] = None,
    product_type: Optional[str] = None,
) -> Tuple[Optional[DiscoveredProduct], float]:
    """
    Find a product by fuzzy name matching.

    Uses simple Levenshtein-like similarity. For production,
    consider using rapidfuzz or fuzzywuzzy library.

    Args:
        name: Product name to match
        brand: Optional brand to filter by
        product_type: Optional product type to filter by

    Returns:
        Tuple of (matching DiscoveredProduct or None, confidence score)
    """
    if not name:
        return None, 0.0

    normalized_name = normalize_product_name(name)

    # Build query
    query = DiscoveredProduct.objects.all()

    if brand:
        query = query.filter(brand=brand)

    if product_type:
        query = query.filter(product_type=product_type)

    # Get potential matches (limit to reasonable number)
    candidates = query[:100]

    best_match = None
    best_score = 0.0

    for product in candidates:
        product_normalized = normalize_product_name(product.name)
        score = _calculate_similarity(normalized_name, product_normalized)

        if score > best_score:
            best_score = score
            best_match = product

    # Return match only if score is above minimum threshold
    if best_score >= MEDIUM_CONFIDENCE_THRESHOLD * 0.8:  # Allow some buffer below threshold
        return best_match, best_score

    return None, 0.0


def _calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity between two strings.

    Uses a combination of:
    - Token overlap (Jaccard similarity)
    - Sequence matching

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not s1 or not s2:
        return 0.0

    if s1 == s2:
        return 1.0

    # Token-based similarity (Jaccard)
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / union if union > 0 else 0

    # Sequence-based similarity (ratio of matching characters)
    from difflib import SequenceMatcher
    sequence_ratio = SequenceMatcher(None, s1, s2).ratio()

    # Weight: 40% Jaccard, 60% sequence matching
    combined_score = 0.4 * jaccard + 0.6 * sequence_ratio

    return combined_score


def generate_fingerprint(name: str, brand: Optional[str] = None) -> str:
    """
    Generate a fingerprint from product name and brand.

    Args:
        name: Product name
        brand: Optional brand name

    Returns:
        URL-safe fingerprint string
    """
    from django.utils.text import slugify

    normalized = normalize_product_name(name)
    fingerprint = slugify(normalized)

    # Ensure minimum length
    if not fingerprint:
        import hashlib
        fingerprint = hashlib.md5(name.encode()).hexdigest()[:20]

    return fingerprint


def process_candidate(candidate: ProductCandidate) -> Dict[str, Any]:
    """
    Process a product candidate through the deduplication pipeline.

    Pipeline Order:
    1. GTIN match (highest priority)
    2. Fingerprint match
    3. Fuzzy name match

    Args:
        candidate: ProductCandidate to process

    Returns:
        Dict with processing results
    """
    extracted_data = candidate.extracted_data or {}
    result = {
        "matched": False,
        "created": False,
        "match_method": None,
        "confidence": 0.0,
        "product_id": None,
    }

    # Step 1: Try GTIN match
    gtin = extracted_data.get("gtin")
    if gtin:
        match = match_by_gtin(gtin)
        if match:
            _apply_match(candidate, match, "gtin", 1.0)
            result.update({
                "matched": True,
                "match_method": "gtin",
                "confidence": 1.0,
                "product_id": str(match.id),
            })
            return result

    # Step 2: Try fingerprint match
    fingerprint = extracted_data.get("fingerprint")
    if fingerprint:
        match = match_by_fingerprint(fingerprint)
        if match:
            _apply_match(candidate, match, "fingerprint", 1.0)
            result.update({
                "matched": True,
                "match_method": "fingerprint",
                "confidence": 1.0,
                "product_id": str(match.id),
            })
            return result

    # Step 3: Try fuzzy name match
    brand = None
    brand_name = extracted_data.get("brand")
    if brand_name:
        brand = DiscoveredBrand.objects.filter(name__iexact=brand_name).first()

    product_type = extracted_data.get("product_type")

    match, confidence = match_by_fuzzy_name(
        candidate.raw_name,
        brand=brand,
        product_type=product_type,
    )

    if match and confidence >= HIGH_CONFIDENCE_THRESHOLD:
        # High confidence - auto-match
        _apply_match(candidate, match, "fuzzy", confidence)
        result.update({
            "matched": True,
            "match_method": "fuzzy",
            "confidence": confidence,
            "product_id": str(match.id),
        })
        return result

    if match and confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
        # Medium confidence - needs review
        candidate.matched_product = match
        candidate.match_confidence = Decimal(str(confidence))
        candidate.match_method = "fuzzy"
        candidate.match_status = MatchStatusChoices.NEEDS_REVIEW
        candidate.save()

        result.update({
            "matched": False,  # Not confirmed yet
            "match_method": "fuzzy",
            "confidence": confidence,
            "product_id": str(match.id),
            "needs_review": True,
        })
        return result

    # No match found - create new product
    # We don't have sample_crawler_source here, so just mark as NEW_PRODUCT
    # The actual product creation will be done by the caller
    candidate.match_status = MatchStatusChoices.NEW_PRODUCT
    candidate.save()

    result.update({
        "created": True,
        "match_method": None,
        "confidence": 0.0,
        "needs_creation": True,
    })

    return result


def _apply_match(
    candidate: ProductCandidate,
    product: DiscoveredProduct,
    method: str,
    confidence: float,
) -> None:
    """
    Apply a match result to a candidate.

    Args:
        candidate: The ProductCandidate to update
        product: The matched DiscoveredProduct
        method: The matching method used
        confidence: The match confidence score
    """
    candidate.matched_product = product
    candidate.match_confidence = Decimal(str(confidence))
    candidate.match_method = method
    candidate.match_status = MatchStatusChoices.MATCHED
    candidate.save()

    logger.info(
        f"Matched candidate '{candidate.raw_name}' to product '{product.name}' "
        f"via {method} (confidence: {confidence:.2f})"
    )


def create_product_from_candidate(
    candidate: ProductCandidate,
    crawler_source: "CrawlerSource",
) -> Optional[DiscoveredProduct]:
    """
    Create a new DiscoveredProduct from a ProductCandidate.

    Args:
        candidate: ProductCandidate with extracted data
        crawler_source: CrawlerSource to associate with product

    Returns:
        Created DiscoveredProduct or None on error
    """
    from crawler.services.content_processor import (
        extract_individual_fields,
        get_or_create_brand,
    )

    extracted_data = candidate.extracted_data or {}

    try:
        # Generate fingerprint
        fingerprint = generate_fingerprint(
            candidate.raw_name,
            extracted_data.get("brand"),
        )

        # Ensure fingerprint is unique
        counter = 1
        base_fingerprint = fingerprint
        while DiscoveredProduct.objects.filter(fingerprint=fingerprint).exists():
            fingerprint = f"{base_fingerprint}-{counter}"
            counter += 1

        # Determine product type
        product_type_str = extracted_data.get("product_type", "unknown")
        try:
            product_type = ProductType(product_type_str)
        except ValueError:
            product_type = ProductType.UNKNOWN

        # Get or create brand
        brand, _ = get_or_create_brand(extracted_data)

        # Extract individual fields (but exclude 'name' as we set it explicitly)
        individual_fields = extract_individual_fields(extracted_data)
        # Remove fields that we set explicitly to avoid duplicate keyword args
        individual_fields.pop("name", None)
        individual_fields.pop("brand", None)

        # Create product with individual fields only (extracted_data removed)
        product = DiscoveredProduct.objects.create(
            source=crawler_source,
            source_url=candidate.source.url,
            fingerprint=fingerprint,
            product_type=product_type,
            raw_content=candidate.source.raw_content or "",
            raw_content_hash=candidate.source.content_hash or "",
            name=candidate.raw_name,
            brand=brand,
            **individual_fields,
        )

        # Update candidate
        candidate.matched_product = product
        candidate.match_status = MatchStatusChoices.NEW_PRODUCT
        candidate.save()

        logger.info(f"Created new product '{product.name}' from candidate")
        return product

    except Exception as e:
        logger.error(f"Failed to create product from candidate: {e}")
        return None
