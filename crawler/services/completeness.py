"""
Task Group 19: Completeness Scoring Service

This module provides functions for calculating data completeness scores
for DiscoveredProduct records, determining their completeness tier,
identifying missing fields, and calculating enrichment priority.

Field weights are configurable and based on business importance.
"""

from typing import List, Optional

# ============================================================
# Task 19.4: Field Weights Configuration
# ============================================================

# Field weights define the importance of each field for completeness scoring.
# Higher weights indicate more critical fields.
# Total max score is approximately 100 points.

FIELD_WEIGHTS = {
    # Critical fields (10 pts) - Must have for product identification
    "name": 10,
    "brand": 10,  # FK field - checked via brand_id

    # Important fields (5-8 pts) - Key product attributes
    "product_type": 8,
    "abv": 6,
    "age_statement": 5,
    "region": 5,
    "category": 5,

    # Valuable fields (3-4 pts) - Cask info
    "primary_cask": 4,
    "finishing_cask": 3,

    # Valuable fields (3-4 pts) - Tasting notes
    "nose_description": 4,
    "palate_flavors": 4,
    "finish_length": 3,
    "primary_aromas": 3,

    # Nice to have fields (2-3 pts)
    "color_description": 2,
    "maturation_notes": 2,
    "food_pairings": 2,
    "serving_recommendation": 2,

    # Business critical fields (4-7 pts)
    "best_price": 7,  # min_price_eur equivalent
    "award_count": 5,
    "rating_count": 4,
}

# Calculate max possible score based on weights
MAX_SCORE = sum(FIELD_WEIGHTS.values())  # Should be approximately 100


# ============================================================
# Task 19.5: Completeness Calculation Service Functions
# ============================================================

def calculate_completeness_score(product) -> int:
    """
    Calculate the completeness score for a product based on field weights.

    Examines which fields are populated and sums their weights to produce
    a score from 1-100 representing data completeness.

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Completeness score (1-100)
    """
    score = 0

    for field_name, weight in FIELD_WEIGHTS.items():
        if _is_field_populated(product, field_name):
            score += weight

    # Normalize to 1-100 scale
    percentage = int((score / MAX_SCORE) * 100)

    # Ensure minimum of 1 if any data exists
    return max(1, min(100, percentage))


def determine_tier(score: int) -> str:
    """
    Determine the completeness tier based on the score.

    Tiers:
    - complete: 90-100%
    - good: 70-89%
    - partial: 40-69%
    - skeleton: 0-39%

    Args:
        score: Completeness score (0-100)

    Returns:
        str: Tier name (complete, good, partial, skeleton)
    """
    if score >= 90:
        return "complete"
    elif score >= 70:
        return "good"
    elif score >= 40:
        return "partial"
    else:
        return "skeleton"


def get_missing_fields(product) -> List[str]:
    """
    Get a list of important field names that are missing or empty.

    Identifies which weighted fields are not populated, enabling
    targeted enrichment efforts.

    Args:
        product: DiscoveredProduct instance

    Returns:
        list[str]: List of missing field names
    """
    missing = []

    for field_name in FIELD_WEIGHTS.keys():
        if not _is_field_populated(product, field_name):
            missing.append(field_name)

    return missing


def calculate_enrichment_priority(product) -> int:
    """
    Calculate enrichment priority based on multiple factors.

    Priority is 1-10 where 10 means highest priority (needs enrichment most urgently).

    Factors:
    - Low completeness score increases priority
    - High award count increases priority (award-winning products are important)
    - High rating count increases priority (popular products)
    - New releases get priority boost

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Enrichment priority (1-10)
    """
    # Get completeness score (use stored value or calculate)
    completeness = product.completeness_score
    if completeness is None:
        completeness = calculate_completeness_score(product)

    # Base priority inversely proportional to completeness
    # Low completeness = high priority
    # 0% completeness -> priority 10
    # 100% completeness -> priority 1
    base_priority = max(1, 10 - int(completeness / 11))

    # Award count boost (max +2)
    award_boost = 0
    if hasattr(product, 'award_count') and product.award_count:
        if product.award_count >= 3:
            award_boost = 2
        elif product.award_count >= 1:
            award_boost = 1

    # Rating count boost (max +1)
    rating_boost = 0
    if hasattr(product, 'rating_count') and product.rating_count:
        if product.rating_count >= 5:
            rating_boost = 1

    # New release boost (max +1)
    new_release_boost = 0
    if hasattr(product, 'is_new_release') and product.is_new_release:
        new_release_boost = 1

    # Calculate final priority
    priority = base_priority + award_boost + rating_boost + new_release_boost

    # Clamp to 1-10 range
    return max(1, min(10, priority))


def update_product_completeness(product, save: bool = True) -> None:
    """
    Update all completeness-related fields on a product.

    This is the main entry point for recalculating completeness.
    It updates:
    - completeness_score
    - completeness_tier
    - missing_fields
    - enrichment_priority

    Args:
        product: DiscoveredProduct instance
        save: Whether to save the product after updating (default True)
    """
    # Calculate all completeness metrics
    score = calculate_completeness_score(product)
    tier = determine_tier(score)
    missing = get_missing_fields(product)

    # Update the product fields
    product.completeness_score = score
    product.completeness_tier = tier
    product.missing_fields = missing

    # Calculate priority (uses the score we just set)
    product.enrichment_priority = calculate_enrichment_priority(product)

    if save:
        product.save(update_fields=[
            "completeness_score",
            "completeness_tier",
            "missing_fields",
            "enrichment_priority",
        ])


# ============================================================
# Helper Functions
# ============================================================

def _is_field_populated(product, field_name: str) -> bool:
    """
    Check if a field is populated with a meaningful value.

    Handles different field types:
    - Regular fields: check for None or empty string
    - FK fields (like brand): check if the FK is set
    - JSONField arrays: check if list is non-empty
    - Integer counters: check if > 0

    Args:
        product: DiscoveredProduct instance
        field_name: Name of the field to check

    Returns:
        bool: True if field has a meaningful value
    """
    # Special case for FK field 'brand'
    if field_name == "brand":
        return product.brand_id is not None

    # Special case for counter fields
    if field_name in ("award_count", "rating_count"):
        value = getattr(product, field_name, 0)
        return value is not None and value > 0

    # Special case for price field
    if field_name == "best_price":
        value = getattr(product, "best_price", None)
        return value is not None

    # Get the field value
    value = getattr(product, field_name, None)

    # Check for None
    if value is None:
        return False

    # Check for empty string
    if isinstance(value, str) and value.strip() == "":
        return False

    # Check for empty list (JSONField arrays)
    if isinstance(value, list) and len(value) == 0:
        return False

    # Check for empty dict
    if isinstance(value, dict) and len(value) == 0:
        return False

    # Field is populated
    return True
