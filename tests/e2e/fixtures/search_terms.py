"""
Search Term Fixtures for E2E Testing.

Provides search terms for testing the Generic Search Discovery flow.
These terms are designed to return high-quality listicle and review pages
that contain product information suitable for extraction.

Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 9.3

Usage:
    from tests.e2e.fixtures.search_terms import (
        WHISKEY_SEARCH_TERMS,
        PORT_WINE_SEARCH_TERMS,
        get_search_terms_by_product_type,
    )

    # Get all whiskey search terms
    for term in WHISKEY_SEARCH_TERMS:
        print(f"{term.query} - expects {term.expected_products} products")

    # Get search terms by category
    best_list_terms = get_search_terms_by_category("best_lists")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SearchTermFixture:
    """
    Represents a search term fixture for E2E testing.

    Attributes:
        query: The search query string to execute
        product_type: Target product type (whiskey, port_wine)
        category: Search category (best_lists, reviews, recommendations)
        expected_products: Approximate number of products expected in results
        expected_sources: Types of sources expected (listicle, review_site, retailer)
        notes: Optional notes about this search term
        priority: Priority for execution order (higher = run first)
        tags: Optional tags for filtering search terms
    """

    query: str
    product_type: str
    category: str
    expected_products: int = 5
    expected_sources: List[str] = field(default_factory=lambda: ["listicle", "review_site"])
    notes: Optional[str] = None
    priority: int = 100
    tags: List[str] = field(default_factory=list)


# =============================================================================
# Whiskey Search Terms
# =============================================================================
# Task 3.2.1: Whiskey search terms for E2E testing
# These terms target listicles and review articles that list multiple whiskeys
# with detailed tasting notes and specifications.

WHISKEY_SEARCH_TERMS: List[SearchTermFixture] = [
    # Primary whiskey search terms (from spec)
    SearchTermFixture(
        query="best single malt scotch 2025",
        product_type="whiskey",
        category="best_lists",
        expected_products=10,
        expected_sources=["listicle", "review_site"],
        notes="Best-of lists for single malt scotch - high quality extraction targets",
        priority=100,
        tags=["single_malt", "scotch", "best_of", "primary"],
    ),
    SearchTermFixture(
        query="bourbon whiskey reviews",
        product_type="whiskey",
        category="reviews",
        expected_products=8,
        expected_sources=["review_site", "listicle"],
        notes="Bourbon review articles - good for tasting notes extraction",
        priority=95,
        tags=["bourbon", "american", "reviews", "primary"],
    ),
    SearchTermFixture(
        query="Japanese whisky recommendations",
        product_type="whiskey",
        category="recommendations",
        expected_products=6,
        expected_sources=["listicle", "review_site"],
        notes="Japanese whisky recommendation articles - premium segment",
        priority=90,
        tags=["japanese", "recommendations", "primary"],
    ),

    # Additional whiskey search terms for comprehensive testing
    SearchTermFixture(
        query="best bourbon under $50",
        product_type="whiskey",
        category="best_lists",
        expected_products=8,
        expected_sources=["listicle", "review_site"],
        notes="Budget bourbon lists - good for testing price extraction",
        priority=85,
        tags=["bourbon", "budget", "best_of"],
    ),
    SearchTermFixture(
        query="top rated Irish whiskey",
        product_type="whiskey",
        category="best_lists",
        expected_products=7,
        expected_sources=["listicle", "review_site"],
        notes="Irish whiskey rankings - tests regional variety",
        priority=80,
        tags=["irish", "ratings", "best_of"],
    ),
    SearchTermFixture(
        query="best rye whiskey to buy",
        product_type="whiskey",
        category="recommendations",
        expected_products=6,
        expected_sources=["listicle", "retailer"],
        notes="Rye whiskey buying guides - may include retailer links",
        priority=75,
        tags=["rye", "american", "buying_guide"],
    ),
    SearchTermFixture(
        query="award winning scotch whisky 2024",
        product_type="whiskey",
        category="awards",
        expected_products=10,
        expected_sources=["competition_page", "review_site"],
        notes="Award articles - high quality products with competition data",
        priority=70,
        tags=["scotch", "awards", "competition"],
    ),
    SearchTermFixture(
        query="blended scotch whisky reviews",
        product_type="whiskey",
        category="reviews",
        expected_products=8,
        expected_sources=["review_site", "listicle"],
        notes="Blended scotch - tests category-specific exemptions (no region/cask required)",
        priority=65,
        tags=["blended", "scotch", "reviews", "category_test"],
    ),
]


# =============================================================================
# Port Wine Search Terms
# =============================================================================
# Task 3.2.2: Port wine search terms for E2E testing
# These terms target port wine listicles and review articles.

PORT_WINE_SEARCH_TERMS: List[SearchTermFixture] = [
    # Primary port wine search terms (from spec)
    SearchTermFixture(
        query="best vintage port wine",
        product_type="port_wine",
        category="best_lists",
        expected_products=8,
        expected_sources=["listicle", "review_site"],
        notes="Vintage port best-of lists - premium declared vintage ports",
        priority=100,
        tags=["vintage", "best_of", "primary"],
    ),
    SearchTermFixture(
        query="tawny port reviews",
        product_type="port_wine",
        category="reviews",
        expected_products=6,
        expected_sources=["review_site", "listicle"],
        notes="Tawny port reviews - tests age indication extraction",
        priority=95,
        tags=["tawny", "reviews", "primary"],
    ),

    # Additional port wine search terms for comprehensive testing
    SearchTermFixture(
        query="best ruby port wines",
        product_type="port_wine",
        category="best_lists",
        expected_products=6,
        expected_sources=["listicle", "review_site"],
        notes="Ruby port lists - entry-level port style",
        priority=85,
        tags=["ruby", "best_of"],
    ),
    SearchTermFixture(
        query="LBV port wine recommendations",
        product_type="port_wine",
        category="recommendations",
        expected_products=5,
        expected_sources=["listicle", "review_site"],
        notes="Late Bottled Vintage port - tests style classification",
        priority=80,
        tags=["lbv", "recommendations"],
    ),
    SearchTermFixture(
        query="top port wine producers Douro",
        product_type="port_wine",
        category="producer_info",
        expected_products=7,
        expected_sources=["review_site", "listicle"],
        notes="Douro producer articles - good for house/quinta extraction",
        priority=75,
        tags=["producer", "douro", "houses"],
    ),
    SearchTermFixture(
        query="colheita port wine guide",
        product_type="port_wine",
        category="guides",
        expected_products=5,
        expected_sources=["review_site", "listicle"],
        notes="Colheita (single harvest tawny) guides - niche style",
        priority=70,
        tags=["colheita", "tawny", "guides"],
    ),
    SearchTermFixture(
        query="best port wine for beginners",
        product_type="port_wine",
        category="recommendations",
        expected_products=8,
        expected_sources=["listicle", "retailer"],
        notes="Beginner port guides - may include retailer links",
        priority=65,
        tags=["beginner", "recommendations", "buying_guide"],
    ),
]


# =============================================================================
# Combined Search Terms
# =============================================================================

ALL_SEARCH_TERMS: List[SearchTermFixture] = WHISKEY_SEARCH_TERMS + PORT_WINE_SEARCH_TERMS


# =============================================================================
# Search Term Categories
# =============================================================================

SEARCH_TERM_CATEGORIES: Dict[str, str] = {
    "best_lists": "Best-of and top lists (Forbes, VinePair style)",
    "reviews": "Review articles with tasting notes",
    "recommendations": "Recommendation and buying guides",
    "awards": "Award and competition coverage",
    "producer_info": "Producer/house focused articles",
    "guides": "Educational and category guides",
}


# =============================================================================
# Utility Functions
# =============================================================================

def get_search_terms_by_product_type(product_type: str) -> List[SearchTermFixture]:
    """
    Get search terms for a specific product type.

    Args:
        product_type: Product type identifier (whiskey, port_wine)

    Returns:
        List of SearchTermFixture instances for the product type

    Raises:
        ValueError: If product type is not recognized
    """
    if product_type == "whiskey":
        return WHISKEY_SEARCH_TERMS
    elif product_type == "port_wine":
        return PORT_WINE_SEARCH_TERMS
    else:
        raise ValueError(
            f"Unknown product type: {product_type}. "
            f"Available types: whiskey, port_wine"
        )


def get_search_terms_by_category(category: str) -> List[SearchTermFixture]:
    """
    Get search terms for a specific category across all product types.

    Args:
        category: Search category (best_lists, reviews, recommendations, etc.)

    Returns:
        List of SearchTermFixture instances matching the category
    """
    return [term for term in ALL_SEARCH_TERMS if term.category == category]


def get_search_terms_by_tag(tag: str) -> List[SearchTermFixture]:
    """
    Get search terms that have a specific tag.

    Args:
        tag: Tag to filter by

    Returns:
        List of SearchTermFixture instances with the tag
    """
    return [term for term in ALL_SEARCH_TERMS if tag in term.tags]


def get_primary_search_terms() -> List[SearchTermFixture]:
    """
    Get primary search terms (those marked with 'primary' tag).

    These are the terms specified in the spec Section 9.3.

    Returns:
        List of primary SearchTermFixture instances
    """
    return get_search_terms_by_tag("primary")


def get_search_terms_sorted_by_priority(
    product_type: Optional[str] = None
) -> List[SearchTermFixture]:
    """
    Get search terms sorted by priority (highest first).

    Args:
        product_type: Optional product type filter

    Returns:
        List of SearchTermFixture instances sorted by priority descending
    """
    terms = (
        get_search_terms_by_product_type(product_type)
        if product_type
        else ALL_SEARCH_TERMS
    )
    return sorted(terms, key=lambda t: t.priority, reverse=True)
