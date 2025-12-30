"""
Freshness tracking utilities for DiscoveredProduct data.

Task Group 14: Implements freshness score calculation and management utilities
for determining when product data needs to be re-crawled.

Freshness Thresholds by Data Type:
- Price: Fresh (<7 days), Stale (7-30 days), Critical (>30 days)
- Availability/Stock: Fresh (<3 days), Stale (3-14 days), Critical (>14 days)
- Ratings/Reviews: Fresh (<30 days), Stale (30-90 days), Critical (>90 days)
- Awards: Fresh (<90 days), Stale (90-365 days), Critical (>365 days)
- Product Details: Fresh (<180 days), Stale (180-365 days), Critical (>365 days)

Weights:
- Price: 35%
- Availability: 25%
- Ratings: 20%
- Awards: 10%
- Product Details: 10%
"""

from datetime import timedelta
from typing import Dict, Literal, Optional, Union
from django.utils import timezone


# Freshness threshold configuration (in days)
FRESHNESS_THRESHOLDS = {
    "price": {
        "fresh": 7,       # < 7 days is fresh
        "stale": 30,      # 7-30 days is stale
        # > 30 days is critical
    },
    "availability": {
        "fresh": 3,       # < 3 days is fresh
        "stale": 14,      # 3-14 days is stale
        # > 14 days is critical
    },
    "ratings": {
        "fresh": 30,      # < 30 days is fresh
        "stale": 90,      # 30-90 days is stale
        # > 90 days is critical
    },
    "awards": {
        "fresh": 90,      # < 90 days is fresh
        "stale": 365,     # 90-365 days is stale
        # > 365 days is critical
    },
    "product_details": {
        "fresh": 180,     # < 180 days is fresh
        "stale": 365,     # 180-365 days is stale
        # > 365 days is critical
    },
}

# Weight configuration for freshness score calculation
FRESHNESS_WEIGHTS = {
    "price": 0.35,        # 35% weight
    "availability": 0.25, # 25% weight
    "ratings": 0.20,      # 20% weight
    "awards": 0.10,       # 10% weight
    "product_details": 0.10,  # 10% weight
}

# Score decay rates (points per day)
SCORE_DECAY_RATES = {
    "price": 3,           # -3 points per day (hits 0 in ~33 days)
    "availability": 5,    # -5 points per day (hits 0 in 20 days)
    "ratings": 1,         # -1 point per day (hits 0 in 100 days)
    "awards": 0.3,        # -0.3 points per day (hits 0 in ~333 days)
    "product_details": 0.3,  # -0.3 points per day
}

# Threshold for needs_refresh flag
NEEDS_REFRESH_THRESHOLD = 50  # Score below 50 triggers needs_refresh


FreshnessLevel = Literal["fresh", "stale", "critical"]


def get_data_freshness_level(
    data_type: str,
    last_check: Optional[timezone.datetime],
) -> FreshnessLevel:
    """
    Determine the freshness level for a specific data type.

    Args:
        data_type: Type of data being checked (price, availability, ratings, awards, product_details)
        last_check: DateTime of last check (None means never checked)

    Returns:
        FreshnessLevel: "fresh", "stale", or "critical"
    """
    if last_check is None:
        # Never checked means data is critical
        return "critical"

    now = timezone.now()
    days_since_check = (now - last_check).days

    thresholds = FRESHNESS_THRESHOLDS.get(data_type, FRESHNESS_THRESHOLDS["product_details"])

    if days_since_check < thresholds["fresh"]:
        return "fresh"
    elif days_since_check < thresholds["stale"]:
        return "stale"
    else:
        return "critical"


def _calculate_component_score(
    data_type: str,
    last_check: Optional[timezone.datetime],
) -> int:
    """
    Calculate freshness score for a single data component.

    Args:
        data_type: Type of data being scored
        last_check: DateTime of last check (None returns 100 - treated as no data yet)

    Returns:
        int: Score from 0 to 100
    """
    if last_check is None:
        # No data yet - this is neither fresh nor stale, it's just missing
        # Return 100 to indicate "nothing to be stale"
        return 100

    now = timezone.now()
    days_since_check = (now - last_check).days

    # Get decay rate for this data type
    decay_rate = SCORE_DECAY_RATES.get(data_type, SCORE_DECAY_RATES["product_details"])

    # Calculate score: start at 100, decay over time
    score = max(0, 100 - (days_since_check * decay_rate))

    return int(score)


def calculate_freshness_score(
    product_data: Dict[str, Optional[timezone.datetime]],
) -> int:
    """
    Calculate overall freshness score based on weighted factors.

    The score is calculated by:
    1. Computing individual scores for each data type based on days since last check
    2. Weighting each score according to FRESHNESS_WEIGHTS
    3. Summing weighted scores for total

    Args:
        product_data: Dictionary containing last check timestamps:
            - last_price_check: DateTime or None
            - last_availability_check: DateTime or None
            - last_enrichment: DateTime or None (used for ratings/awards/product_details)

    Returns:
        int: Overall freshness score from 1 to 100
    """
    scores = []

    # Price freshness (weight: 35%)
    price_score = _calculate_component_score(
        "price",
        product_data.get("last_price_check"),
    )
    scores.append(("price", price_score, FRESHNESS_WEIGHTS["price"]))

    # Availability freshness (weight: 25%)
    availability_score = _calculate_component_score(
        "availability",
        product_data.get("last_availability_check"),
    )
    scores.append(("availability", availability_score, FRESHNESS_WEIGHTS["availability"]))

    # For ratings, awards, and product details, we use last_enrichment as proxy
    last_enrichment = product_data.get("last_enrichment")

    # Ratings freshness (weight: 20%)
    ratings_score = _calculate_component_score(
        "ratings",
        last_enrichment,
    )
    scores.append(("ratings", ratings_score, FRESHNESS_WEIGHTS["ratings"]))

    # Awards freshness (weight: 10%)
    awards_score = _calculate_component_score(
        "awards",
        last_enrichment,
    )
    scores.append(("awards", awards_score, FRESHNESS_WEIGHTS["awards"]))

    # Product details freshness (weight: 10%)
    product_details_score = _calculate_component_score(
        "product_details",
        last_enrichment,
    )
    scores.append(("product_details", product_details_score, FRESHNESS_WEIGHTS["product_details"]))

    # Calculate weighted average
    total_score = sum(score * weight for _, score, weight in scores)

    # Ensure score is within 1-100 range
    final_score = max(1, min(100, int(total_score)))

    return final_score


def update_product_freshness(product) -> None:
    """
    Update freshness score and needs_refresh flag for a DiscoveredProduct.

    This utility fetches the relevant timestamps from the product,
    calculates the new freshness score, and updates both the score
    and the needs_refresh flag.

    Args:
        product: DiscoveredProduct instance to update
    """
    product_data = {
        "last_price_check": product.last_price_check,
        "last_availability_check": product.last_availability_check,
        "last_enrichment": product.last_enrichment,
    }

    # Calculate new freshness score
    new_score = calculate_freshness_score(product_data)

    # Determine if refresh is needed
    needs_refresh = new_score < NEEDS_REFRESH_THRESHOLD

    # Update the product
    product.data_freshness_score = new_score
    product.needs_refresh = needs_refresh
    product.save(update_fields=["data_freshness_score", "needs_refresh"])


def get_products_needing_refresh(queryset=None, limit: int = 100):
    """
    Get products that need to be refreshed, ordered by priority.

    Priority factors:
    - Lower freshness score = higher priority
    - needs_refresh=True takes precedence

    Args:
        queryset: Optional queryset to filter from (defaults to all DiscoveredProduct)
        limit: Maximum number of products to return

    Returns:
        QuerySet of products needing refresh, ordered by priority
    """
    from crawler.models import DiscoveredProduct

    if queryset is None:
        queryset = DiscoveredProduct.objects.all()

    return queryset.filter(needs_refresh=True).order_by(
        "data_freshness_score",  # Lower score = higher priority
    )[:limit]


def batch_update_freshness_scores(queryset=None, batch_size: int = 100):
    """
    Batch update freshness scores for multiple products.

    This is useful for periodic maintenance tasks to keep
    freshness scores up to date.

    Args:
        queryset: Optional queryset to update (defaults to all DiscoveredProduct)
        batch_size: Number of products to process at a time

    Returns:
        int: Number of products updated
    """
    from crawler.models import DiscoveredProduct

    if queryset is None:
        queryset = DiscoveredProduct.objects.all()

    updated_count = 0

    for product in queryset.iterator(chunk_size=batch_size):
        update_product_freshness(product)
        updated_count += 1

    return updated_count
