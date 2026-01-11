"""
Unified Product Pipeline Phase 2: Completeness Scoring Service

This module provides functions for calculating data completeness scores
for DiscoveredProduct records, determining their status based on the
unified pipeline requirements, and calculating enrichment priority.

Key Requirements (from spec):
1. Tasting Profile = 40% of score (Palate 20, Nose 10, Finish 10)
2. Palate is MANDATORY for COMPLETE/VERIFIED status
3. Status thresholds: incomplete (0-29), partial (30-59), complete (60-79), verified (80+)

Status Model:
- INCOMPLETE: Score 0-29, or missing palate
- PARTIAL: Score 30-59, or has some data but no palate
- COMPLETE: Score 60-79 AND has palate data
- VERIFIED: Score 80-100 AND has palate data AND source_count >= 2

V2 Field Updates (AI Enhancement Service V2):
- palate_flavors (3+ items): +10 points
- primary_aromas (2+ items): +5 points
- finish_flavors (2+ items): +5 points
- description: +5 points
- category: +3 points
- appearance fields (any populated): +3 points total
- ratings fields (any populated): +5 points total
"""

from typing import List, Optional

# ============================================================
# Tasting Profile Score Constants
# ============================================================

MAX_TASTING_PROFILE_SCORE = 40  # 40% of total score (100 points)
MAX_PALATE_SCORE = 20
MAX_NOSE_SCORE = 10
MAX_FINISH_SCORE = 10

# ============================================================
# Legacy Field Weights (for backward compatibility)
# ============================================================

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

    # Valuable fields (3-4 pts) - Tasting notes (legacy - now use tasting profile scoring)
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
# Tasting Profile Scoring Functions (New - Unified Pipeline)
# ============================================================

def calculate_palate_score(product) -> int:
    """
    Calculate palate score (max 20 points).

    Breakdown:
    - 10 points for palate_flavors with 3+ items (V2 requirement)
    - 5 points for palate_description OR initial_taste
    - 3 points for mid_palate_evolution
    - 2 points for mouthfeel

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Palate score (0-20)
    """
    score = 0

    # Palate flavors (10 points for 3+ items per V2 spec)
    palate_flavors = getattr(product, 'palate_flavors', None)
    if palate_flavors and len(palate_flavors) >= 3:
        score += 10

    # Palate description or initial taste (5 points)
    palate_description = getattr(product, 'palate_description', None)
    initial_taste = getattr(product, 'initial_taste', None)
    if (palate_description and palate_description.strip()) or (initial_taste and initial_taste.strip()):
        score += 5

    # Mid-palate evolution (3 points)
    mid_palate = getattr(product, 'mid_palate_evolution', None)
    if mid_palate and mid_palate.strip():
        score += 3

    # Mouthfeel (2 points)
    mouthfeel = getattr(product, 'mouthfeel', None)
    if mouthfeel and mouthfeel.strip():
        score += 2

    return min(score, MAX_PALATE_SCORE)


def calculate_nose_score(product) -> int:
    """
    Calculate nose/aroma score (max 10 points).

    Breakdown:
    - 5 points for nose_description
    - 5 points for primary_aromas with 2+ items (V2 requirement)

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Nose score (0-10)
    """
    score = 0

    # Nose description (5 points)
    nose_description = getattr(product, 'nose_description', None)
    if nose_description and nose_description.strip():
        score += 5

    # Primary aromas (5 points for 2+ items per V2 spec)
    primary_aromas = getattr(product, 'primary_aromas', None)
    if primary_aromas and len(primary_aromas) >= 2:
        score += 5

    return min(score, MAX_NOSE_SCORE)


def calculate_finish_score(product) -> int:
    """
    Calculate finish score (max 10 points).

    Breakdown:
    - 5 points for finish_flavors with 2+ items (V2 requirement)
    - 3 points for finish_description or final_notes
    - 2 points for finish_length

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Finish score (0-10)
    """
    score = 0

    # Finish flavors (5 points for 2+ items per V2 spec - increased from 3)
    finish_flavors = getattr(product, 'finish_flavors', None)
    if finish_flavors and len(finish_flavors) >= 2:
        score += 5

    # Finish description or final_notes (3 points)
    finish_description = getattr(product, 'finish_description', None)
    final_notes = getattr(product, 'final_notes', None)
    if (finish_description and finish_description.strip()) or (final_notes and final_notes.strip()):
        score += 3

    # Finish length (2 points)
    finish_length = getattr(product, 'finish_length', None)
    if finish_length and finish_length > 0:
        score += 2

    return min(score, MAX_FINISH_SCORE)


def calculate_tasting_profile_score(product) -> int:
    """
    Calculate total tasting profile score (max 40 points = 40% of total).

    Breakdown:
    - Palate: 20 points
    - Nose: 10 points
    - Finish: 10 points

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Tasting profile score (0-40)
    """
    palate = calculate_palate_score(product)
    nose = calculate_nose_score(product)
    finish = calculate_finish_score(product)

    return min(palate + nose + finish, MAX_TASTING_PROFILE_SCORE)


# ============================================================
# V2 Fields Scoring Functions (AI Enhancement Service V2)
# ============================================================

def calculate_appearance_score(product) -> int:
    """
    Calculate appearance score (max 3 points for any populated fields).

    Checks for any populated appearance fields:
    - color_description
    - color_intensity
    - clarity
    - viscosity

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Appearance score (0 or 3)
    """
    # Check color_description
    color_description = getattr(product, 'color_description', None)
    if color_description and color_description.strip():
        return 3

    # Check color_intensity
    color_intensity = getattr(product, 'color_intensity', None)
    if color_intensity and color_intensity > 0:
        return 3

    # Check clarity
    clarity = getattr(product, 'clarity', None)
    if clarity and clarity.strip():
        return 3

    # Check viscosity
    viscosity = getattr(product, 'viscosity', None)
    if viscosity and viscosity.strip():
        return 3

    return 0


def calculate_ratings_score(product) -> int:
    """
    Calculate ratings score (max 5 points for any populated fields).

    Checks for any populated ratings fields:
    - flavor_intensity
    - complexity
    - warmth
    - dryness
    - balance
    - overall_complexity
    - uniqueness
    - drinkability

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Ratings score (0 or 5)
    """
    # List of ratings fields to check
    ratings_fields = [
        'flavor_intensity',
        'complexity',
        'warmth',
        'dryness',
        'balance',
        'overall_complexity',
        'uniqueness',
        'drinkability',
    ]

    for field in ratings_fields:
        value = getattr(product, field, None)
        if value is not None and value > 0:
            return 5

    return 0


# ============================================================
# Palate Data Check (Required for COMPLETE/VERIFIED)
# ============================================================

def has_palate_data(product) -> bool:
    """
    Check if product has mandatory palate tasting data.

    A product has palate data if ANY of:
    - palate_flavors has 2+ items
    - palate_description is non-empty
    - initial_taste is non-empty

    This is REQUIRED for a product to reach COMPLETE or VERIFIED status.

    Args:
        product: DiscoveredProduct instance

    Returns:
        bool: True if product has palate data
    """
    # Check palate_flavors (need 2+ items)
    palate_flavors = getattr(product, 'palate_flavors', None)
    if palate_flavors and len(palate_flavors) >= 2:
        return True

    # Check palate_description
    palate_description = getattr(product, 'palate_description', None)
    if palate_description and palate_description.strip():
        return True

    # Check initial_taste
    initial_taste = getattr(product, 'initial_taste', None)
    if initial_taste and initial_taste.strip():
        return True

    return False


# ============================================================
# Status Determination (New - Unified Pipeline)
# ============================================================

def determine_status(product) -> str:
    """
    Determine product status based on completeness and tasting data.

    Status Model:
    - INCOMPLETE: Score 0-29, or missing palate
    - PARTIAL: Score 30-59, or has some data but no palate (capped here without palate)
    - COMPLETE: Score 60-79 AND has palate data
    - VERIFIED: Score 80-100 AND has palate data AND source_count >= 2

    Key rule: COMPLETE/VERIFIED requires palate tasting profile.

    Args:
        product: DiscoveredProduct instance

    Returns:
        str: Status (incomplete, partial, complete, verified, rejected, merged)
    """
    # Import here to avoid circular imports
    from crawler.models import DiscoveredProductStatus

    # Don't change rejected/merged status
    current_status = getattr(product, 'status', None)
    if current_status in (
        DiscoveredProductStatus.REJECTED,
        DiscoveredProductStatus.MERGED,
        'rejected',
        'merged',
    ):
        return current_status if isinstance(current_status, str) else current_status.value

    # Get completeness score
    score = getattr(product, 'completeness_score', None)
    if score is None:
        score = calculate_completeness_score(product)

    # Check for palate data
    has_palate = has_palate_data(product)

    # Cannot be COMPLETE or VERIFIED without palate data
    if not has_palate:
        if score >= 30:
            return "partial"
        return "incomplete"

    # With palate data, status based on score and source_count
    source_count = getattr(product, 'source_count', 1) or 1

    if score >= 80 and source_count >= 2:
        return "verified"
    elif score >= 60:
        return "complete"
    elif score >= 30:
        return "partial"
    else:
        return "incomplete"


# ============================================================
# Completeness Score Calculation (Updated for Unified Pipeline V2)
# ============================================================

def calculate_completeness_score(product) -> int:
    """
    Calculate the completeness score for a product (0-100).

    Uses the model's calculate_completeness_score method if available,
    otherwise uses the unified pipeline scoring breakdown:

    V2 Scoring Breakdown:
    - Identification: 15 points (name 10, brand 5)
    - Basic info: 13 points (type 5, ABV 5, category 3)
    - Description: 5 points
    - Tasting profile: 40 points (palate 20, nose 10, finish 10)
      - palate_flavors (3+ items): 10 points
      - primary_aromas (2+ items): 5 points
      - finish_flavors (2+ items): 5 points
    - Appearance fields (any populated): 3 points
    - Ratings fields (any populated): 5 points
    - Enrichment: 9 points (price 5, images 2, awards 2)
    - Verification bonus: 10 points (multi-source)

    Total possible: 100 points

    Args:
        product: DiscoveredProduct instance

    Returns:
        int: Completeness score (0-100)
    """
    # Use model method if available (it has the full scoring logic)
    if hasattr(product, 'calculate_completeness_score') and callable(product.calculate_completeness_score):
        return product.calculate_completeness_score()

    # Fallback: Calculate using unified pipeline scoring V2
    score = 0

    # IDENTIFICATION (15 points max)
    if getattr(product, 'name', None):
        score += 10
    if getattr(product, 'brand_id', None):
        score += 5

    # BASIC PRODUCT INFO (13 points max)
    if getattr(product, 'product_type', None):
        score += 5
    if getattr(product, 'abv', None):
        score += 5

    # Category (3 points) - V2 field
    category = getattr(product, 'category', None)
    if category and category.strip():
        score += 3

    # DESCRIPTION (5 points) - V2 field
    description = getattr(product, 'description', None)
    if description and description.strip():
        score += 5

    # TASTING PROFILE (40 points max)
    score += calculate_tasting_profile_score(product)

    # APPEARANCE FIELDS (3 points) - V2 field
    score += calculate_appearance_score(product)

    # RATINGS FIELDS (5 points) - V2 field
    score += calculate_ratings_score(product)

    # ENRICHMENT DATA (9 points max)
    if getattr(product, 'best_price', None):
        score += 5
    images = getattr(product, 'images', None)
    if images and len(images) > 0:
        score += 2
    awards = getattr(product, 'awards', None)
    if awards and len(awards) > 0:
        score += 2

    # VERIFICATION BONUS (10 points max)
    source_count = getattr(product, 'source_count', 0) or 0
    if source_count >= 2:
        score += 5
    if source_count >= 3:
        score += 5

    return min(score, 100)


# ============================================================
# Minimum Quality Threshold (Search Termination Criteria)
# ============================================================

def meets_minimum_quality_threshold(product) -> bool:
    """
    Check if product has enough data to stop searching for more.

    This function determines when a product has sufficient data quality
    to be considered "complete enough" for consumer display, triggering
    the crawler to stop searching for additional sources.

    Requirements (from PRODUCT_DATA_REQUIREMENTS.md):
    - palate_flavors obtained with 3+ items (MANDATORY)
    - category determined (whiskey_type for whiskey OR style for port wine)
    - At least 2 of 3 tasting sections populated (nose, palate, finish)
    - Price obtained from at least 1 retailer (best_price is set)
    - Core identity confirmed (name, brand_id, abv)
    - Completeness score >= 60

    Args:
        product: DiscoveredProduct instance

    Returns:
        bool: True if product meets all minimum quality requirements,
              False if more data is needed
    """
    # Check palate_flavors (MANDATORY - 3+ items)
    palate_flavors = getattr(product, 'palate_flavors', None)
    if not palate_flavors or len(palate_flavors) < 3:
        return False

    # Check category (whiskey_type or port style)
    product_type = getattr(product, 'product_type', None)
    has_category = False

    if product_type == 'whiskey':
        # For whiskey: check whiskey_details.whiskey_type
        whiskey_details = getattr(product, 'whiskey_details', None)
        if whiskey_details:
            whiskey_type = getattr(whiskey_details, 'whiskey_type', None)
            if whiskey_type:
                has_category = True
        # Fallback: check category field on product
        if not has_category:
            category = getattr(product, 'category', None)
            if category and category.strip():
                has_category = True
    elif product_type == 'port_wine':
        # For port: check port_details.style
        port_details = getattr(product, 'port_details', None)
        if port_details:
            style = getattr(port_details, 'style', None)
            if style:
                has_category = True
        # Fallback: check category field on product
        if not has_category:
            category = getattr(product, 'category', None)
            if category and category.strip():
                has_category = True
    else:
        # For other product types, check the generic category field
        category = getattr(product, 'category', None)
        if category and category.strip():
            has_category = True

    if not has_category:
        return False

    # Check tasting sections (2 of 3: nose, palate, finish)
    tasting_sections_populated = 0

    # Nose section
    nose_description = getattr(product, 'nose_description', None)
    primary_aromas = getattr(product, 'primary_aromas', None)
    if (nose_description and nose_description.strip()) or (primary_aromas and len(primary_aromas) >= 2):
        tasting_sections_populated += 1

    # Palate section (we already know palate_flavors has 3+ items)
    palate_description = getattr(product, 'palate_description', None)
    initial_taste = getattr(product, 'initial_taste', None)
    # palate_flavors already checked above with 3+ items, so palate is populated
    tasting_sections_populated += 1

    # Finish section
    finish_description = getattr(product, 'finish_description', None)
    final_notes = getattr(product, 'final_notes', None)
    finish_flavors = getattr(product, 'finish_flavors', None)
    finish_length = getattr(product, 'finish_length', None)
    if ((finish_description and finish_description.strip()) or
        (final_notes and final_notes.strip()) or
        (finish_flavors and len(finish_flavors) >= 2) or
        (finish_length and finish_length > 0)):
        tasting_sections_populated += 1

    if tasting_sections_populated < 2:
        return False

    # Check price (best_price set)
    best_price = getattr(product, 'best_price', None)
    if best_price is None:
        return False

    # Check core identity (name, brand_id, abv)
    name = getattr(product, 'name', None)
    if not name or not name.strip():
        return False

    brand_id = getattr(product, 'brand_id', None)
    if brand_id is None:
        return False

    abv = getattr(product, 'abv', None)
    if abv is None:
        return False

    # Check completeness score >= 60
    completeness_score = getattr(product, 'completeness_score', None)
    if completeness_score is None:
        completeness_score = calculate_completeness_score(product)

    if completeness_score < 60:
        return False

    # All requirements met
    return True


def get_missing_required_fields(product) -> List[str]:
    """
    Get a list of required fields that are still missing for minimum quality.

    This helper function identifies which specific requirements are not yet
    met for the product to reach the minimum quality threshold. Useful for
    targeting enrichment efforts and debugging.

    Args:
        product: DiscoveredProduct instance

    Returns:
        List[str]: List of missing requirement descriptions
    """
    missing = []

    # Check palate_flavors (MANDATORY - 3+ items)
    palate_flavors = getattr(product, 'palate_flavors', None)
    if not palate_flavors:
        missing.append("palate_flavors (need 3+ items, currently empty)")
    elif len(palate_flavors) < 3:
        missing.append(f"palate_flavors (need 3+ items, currently {len(palate_flavors)})")

    # Check category based on product type
    product_type = getattr(product, 'product_type', None)
    has_category = False

    if product_type == 'whiskey':
        whiskey_details = getattr(product, 'whiskey_details', None)
        if whiskey_details:
            whiskey_type = getattr(whiskey_details, 'whiskey_type', None)
            if whiskey_type:
                has_category = True
        if not has_category:
            category = getattr(product, 'category', None)
            if category and category.strip():
                has_category = True
        if not has_category:
            missing.append("whiskey_type (via whiskey_details or category)")
    elif product_type == 'port_wine':
        port_details = getattr(product, 'port_details', None)
        if port_details:
            style = getattr(port_details, 'style', None)
            if style:
                has_category = True
        if not has_category:
            category = getattr(product, 'category', None)
            if category and category.strip():
                has_category = True
        if not has_category:
            missing.append("port_style (via port_details or category)")
    else:
        category = getattr(product, 'category', None)
        if not category or not category.strip():
            missing.append("category")

    # Check tasting sections (2 of 3: nose, palate, finish)
    tasting_sections_populated = 0
    missing_sections = []

    # Nose section
    nose_description = getattr(product, 'nose_description', None)
    primary_aromas = getattr(product, 'primary_aromas', None)
    if (nose_description and nose_description.strip()) or (primary_aromas and len(primary_aromas) >= 2):
        tasting_sections_populated += 1
    else:
        missing_sections.append("nose")

    # Palate section
    palate_populated = False
    if palate_flavors and len(palate_flavors) >= 2:
        palate_populated = True
    palate_description = getattr(product, 'palate_description', None)
    initial_taste = getattr(product, 'initial_taste', None)
    if (palate_description and palate_description.strip()) or (initial_taste and initial_taste.strip()):
        palate_populated = True
    if palate_populated:
        tasting_sections_populated += 1
    else:
        missing_sections.append("palate")

    # Finish section
    finish_description = getattr(product, 'finish_description', None)
    final_notes = getattr(product, 'final_notes', None)
    finish_flavors = getattr(product, 'finish_flavors', None)
    finish_length = getattr(product, 'finish_length', None)
    if ((finish_description and finish_description.strip()) or
        (final_notes and final_notes.strip()) or
        (finish_flavors and len(finish_flavors) >= 2) or
        (finish_length and finish_length > 0)):
        tasting_sections_populated += 1
    else:
        missing_sections.append("finish")

    if tasting_sections_populated < 2:
        missing.append(f"tasting sections (need 2 of 3, have {tasting_sections_populated}: missing {', '.join(missing_sections)})")

    # Check price
    best_price = getattr(product, 'best_price', None)
    if best_price is None:
        missing.append("best_price (need at least 1 retailer price)")

    # Check core identity
    name = getattr(product, 'name', None)
    if not name or not name.strip():
        missing.append("name")

    brand_id = getattr(product, 'brand_id', None)
    if brand_id is None:
        missing.append("brand_id")

    abv = getattr(product, 'abv', None)
    if abv is None:
        missing.append("abv")

    # Check completeness score
    completeness_score = getattr(product, 'completeness_score', None)
    if completeness_score is None:
        completeness_score = calculate_completeness_score(product)

    if completeness_score < 60:
        missing.append(f"completeness_score (need >= 60, currently {completeness_score})")

    return missing


# ============================================================
# Legacy Functions (Maintained for Backward Compatibility)
# ============================================================

def determine_tier(score: int) -> str:
    """
    Determine the completeness tier based on the score.

    Legacy tier system (for backward compatibility):
    - complete: 90-100%
    - good: 70-89%
    - partial: 40-69%
    - skeleton: 0-39%

    Note: Use determine_status() for the new unified pipeline status model.

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
    - status (using new unified pipeline logic)

    Args:
        product: DiscoveredProduct instance
        save: Whether to save the product after updating (default True)
    """
    # Calculate all completeness metrics
    score = calculate_completeness_score(product)
    tier = determine_tier(score)
    missing = get_missing_fields(product)
    status = determine_status(product)

    # Update the product fields
    product.completeness_score = score
    product.completeness_tier = tier
    product.missing_fields = missing

    # Update status using new unified pipeline logic
    # Import status choices
    from crawler.models import DiscoveredProductStatus
    if hasattr(DiscoveredProductStatus, status.upper()):
        product.status = getattr(DiscoveredProductStatus, status.upper())

    # Calculate priority (uses the score we just set)
    product.enrichment_priority = calculate_enrichment_priority(product)

    if save:
        product.save(update_fields=[
            "completeness_score",
            "completeness_tier",
            "missing_fields",
            "enrichment_priority",
            "status",
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
