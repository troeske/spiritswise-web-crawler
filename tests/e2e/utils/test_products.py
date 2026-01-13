"""
Test Product Configuration for E2E Tests.

Provides centralized test product definitions for each product type,
enabling parameterized E2E testing across whiskey, port_wine, and future spirits.

Usage:
    from tests.e2e.utils.test_products import (
        get_test_config,
        get_primary_test_product,
        get_all_test_products,
        PRODUCT_TYPE_CONFIGS,
    )

    # Get configuration for a product type
    config = get_test_config("whiskey")

    # Get primary test product for a type
    product = get_primary_test_product("port_wine")

    # Iterate over all supported product types
    for product_type in PRODUCT_TYPE_CONFIGS:
        ...
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TestProduct:
    """
    A specific product to use in E2E tests.

    Attributes:
        name: Full product name for searching
        brand: Brand/producer name
        product_type: Product type identifier (whiskey, port_wine, etc.)
        search_hints: Alternative search terms for dynamic discovery
        expected_fields: Product-type-specific fields to verify after extraction
        notes: Optional notes about this test product
    """

    name: str
    brand: str
    product_type: str
    search_hints: List[str] = field(default_factory=list)
    expected_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class ProductTypeTestConfig:
    """
    Complete test configuration for a product type.

    Attributes:
        product_type: Product type identifier
        display_name: Human-readable name
        test_products: List of test products for this type
        search_templates: Search templates for dynamic product discovery
        skeleton_fields: Required fields for SKELETON status
        partial_fields: Required fields for PARTIAL status
        complete_fields: Required fields for COMPLETE status
    """

    product_type: str
    display_name: str
    test_products: List[TestProduct]
    search_templates: List[str]
    skeleton_fields: List[str]
    partial_fields: List[str]
    complete_fields: List[str]


# =============================================================================
# Whiskey Test Products
# =============================================================================

WHISKEY_TEST_PRODUCTS = [
    TestProduct(
        name="Frank August Small Batch Kentucky Straight Bourbon Whiskey",
        brand="Frank August",
        product_type="whiskey",
        search_hints=[
            "Frank August Small Batch bourbon",
            "Frank August Kentucky Straight Bourbon",
        ],
        expected_fields=["distillery", "mash_bill", "abv", "region"],
        notes="Primary test product - Frank August's flagship small batch expression",
    ),
    TestProduct(
        name="Buffalo Trace Kentucky Straight Bourbon Whiskey",
        brand="Buffalo Trace Distillery",
        product_type="whiskey",
        search_hints=[
            "Buffalo Trace bourbon whiskey",
            "Buffalo Trace Kentucky Straight",
        ],
        expected_fields=["distillery", "abv", "region", "country"],
        notes="Buffalo Trace Distillery's flagship bourbon expression",
    ),
    TestProduct(
        name="Glenfiddich 18 Year Old Single Malt Scotch Whisky",
        brand="Glenfiddich",
        product_type="whiskey",
        search_hints=[
            "Glenfiddich 18 Year Old",
            "Glenfiddich 18 single malt scotch",
        ],
        expected_fields=["age_statement", "distillery", "region", "whiskey_type"],
        notes="Glenfiddich's 18 year aged single malt expression",
    ),
]


# =============================================================================
# Port Wine Test Products
# =============================================================================

PORT_WINE_TEST_PRODUCTS = [
    TestProduct(
        name="Taylor Fladgate 20 Year Old Tawny Port",
        brand="Taylor Fladgate",
        product_type="port_wine",
        search_hints=[
            "Taylor Fladgate 20 Year Tawny",
            "Taylor's 20 Year Old Tawny Port",
        ],
        expected_fields=["style", "indication_age", "producer_house"],
        notes="Primary test product - Taylor Fladgate's 20 Year Tawny expression",
    ),
    TestProduct(
        name="Graham's 10 Year Old Tawny Port",
        brand="Graham's",
        product_type="port_wine",
        search_hints=[
            "Graham's 10 Year Tawny Port",
            "Grahams Ten Year Old Tawny",
        ],
        expected_fields=["style", "indication_age", "producer_house"],
        notes="Graham's 10 Year aged tawny expression from Symington family",
    ),
    TestProduct(
        name="Dow's Vintage Port 2017",
        brand="Dow's",
        product_type="port_wine",
        search_hints=[
            "Dow's 2017 Vintage Port",
            "Dows Declared Vintage 2017",
        ],
        expected_fields=["style", "harvest_year", "producer_house"],
        notes="Dow's declared vintage port from 2017 harvest",
    ),
    TestProduct(
        name="Fonseca Bin No. 27 Premium Reserve Port",
        brand="Fonseca",
        product_type="port_wine",
        search_hints=[
            "Fonseca Bin 27 Reserve Port",
            "Fonseca Bin No 27",
        ],
        expected_fields=["style", "producer_house"],
        notes="Fonseca's premium ruby reserve port blend",
    ),
]


# =============================================================================
# Product Type Configurations
# =============================================================================

WHISKEY_CONFIG = ProductTypeTestConfig(
    product_type="whiskey",
    display_name="Whiskey",
    test_products=WHISKEY_TEST_PRODUCTS,
    search_templates=[
        "{name} official site",
        "{name} {brand}",
        "{name} {product_type}",
        "{name} tasting notes review",
        "{name} buy online",
    ],
    skeleton_fields=["name"],
    partial_fields=["name", "brand"],
    complete_fields=["name", "brand", "abv", "description", "palate_flavors"],
)

PORT_WINE_CONFIG = ProductTypeTestConfig(
    product_type="port_wine",
    display_name="Port Wine",
    test_products=PORT_WINE_TEST_PRODUCTS,
    search_templates=[
        "{name} official site",
        "{name} {brand} port",
        "{name} port wine",
        "{name} port tasting notes review",
        "{name} port buy online",
    ],
    skeleton_fields=["name"],
    partial_fields=["name", "brand"],
    complete_fields=["name", "brand", "abv", "description", "palate_flavors", "style"],
)


# =============================================================================
# Registry and Utility Functions
# =============================================================================

PRODUCT_TYPE_CONFIGS: Dict[str, ProductTypeTestConfig] = {
    "whiskey": WHISKEY_CONFIG,
    "port_wine": PORT_WINE_CONFIG,
}

# List of product type IDs for pytest parameterization
PRODUCT_TYPE_IDS: List[str] = list(PRODUCT_TYPE_CONFIGS.keys())


def get_test_config(product_type: str) -> ProductTypeTestConfig:
    """
    Get test configuration for a product type.

    Args:
        product_type: Product type identifier (whiskey, port_wine, etc.)

    Returns:
        ProductTypeTestConfig for the specified type

    Raises:
        ValueError: If product type is not configured
    """
    if product_type not in PRODUCT_TYPE_CONFIGS:
        raise ValueError(
            f"Unknown product type: {product_type}. "
            f"Available types: {list(PRODUCT_TYPE_CONFIGS.keys())}"
        )
    return PRODUCT_TYPE_CONFIGS[product_type]


def get_primary_test_product(product_type: str) -> TestProduct:
    """
    Get the primary (first) test product for a product type.

    This is the default product used when only product_type is specified.

    Args:
        product_type: Product type identifier

    Returns:
        Primary TestProduct for the type
    """
    config = get_test_config(product_type)
    return config.test_products[0]


def get_all_test_products(product_type: str) -> List[TestProduct]:
    """
    Get all test products for a product type.

    Args:
        product_type: Product type identifier

    Returns:
        List of all TestProduct instances for the type
    """
    config = get_test_config(product_type)
    return config.test_products


def get_test_product_by_name(product_type: str, product_name: str) -> TestProduct:
    """
    Get a specific test product by name.

    Args:
        product_type: Product type identifier
        product_name: Product name to find

    Returns:
        TestProduct with matching name

    Raises:
        ValueError: If product not found
    """
    config = get_test_config(product_type)
    for product in config.test_products:
        if product.name == product_name:
            return product
    raise ValueError(
        f"Product not found: {product_name} in {product_type}. "
        f"Available: {[p.name for p in config.test_products]}"
    )


def get_search_templates(product_type: str) -> List[str]:
    """
    Get search templates for a product type.

    Args:
        product_type: Product type identifier

    Returns:
        List of search template strings with placeholders
    """
    config = get_test_config(product_type)
    return config.search_templates
