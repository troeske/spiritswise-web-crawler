"""
E2E Test Fixtures Package.

Provides test fixtures for E2E testing including:
- Search terms for whiskey and port wine discovery
- URL fixtures for producer pages, review sites, and retailers

Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 9.3
"""

from tests.e2e.fixtures.search_terms import (
    SearchTermFixture,
    WHISKEY_SEARCH_TERMS,
    PORT_WINE_SEARCH_TERMS,
    ALL_SEARCH_TERMS,
    get_search_terms_by_product_type,
    get_search_terms_by_category,
)

__all__ = [
    "SearchTermFixture",
    "WHISKEY_SEARCH_TERMS",
    "PORT_WINE_SEARCH_TERMS",
    "ALL_SEARCH_TERMS",
    "get_search_terms_by_product_type",
    "get_search_terms_by_category",
]
