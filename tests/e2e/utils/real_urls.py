"""
Real Competition URLs for E2E Testing.

This module provides actual URLs from real competition sites, retailers,
and review sites for end-to-end testing of the V2 architecture.

IMPORTANT: These are real URLs that may change over time. Update as needed.

Sources:
- IWSC (International Wine & Spirit Competition): https://iwsc.net
- SFWSC (San Francisco World Spirits Competition): https://sfspiritscomp.com
- DWWA (Decanter World Wine Awards): https://awards.decanter.com
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CompetitionURL:
    """
    Represents a competition URL with metadata.

    Attributes:
        url: The actual URL to crawl
        competition: Name of the competition
        year: Competition year
        product_type: Expected product type (whiskey, port_wine, etc.)
        category: Product category filter if applicable
        expected_products: Approximate number of products expected
        notes: Any special notes about the URL
    """

    url: str
    competition: str
    year: int
    product_type: str
    category: Optional[str] = None
    expected_products: int = 5
    notes: Optional[str] = None


@dataclass
class ProductPageURL:
    """
    Represents a single product page URL.

    Attributes:
        url: The product page URL
        source_name: Name of the source site
        product_name: Expected product name
        product_type: Expected product type
        notes: Any special notes
    """

    url: str
    source_name: str
    product_name: str
    product_type: str
    notes: Optional[str] = None


@dataclass
class ListPageURL:
    """
    Represents a list page URL (e.g., "Best Whiskeys 2025").

    Attributes:
        url: The list page URL
        source_name: Name of the source site
        list_title: Title of the list
        expected_products: Approximate number of products on the page
        product_type: Expected product type
        notes: Any special notes
    """

    url: str
    source_name: str
    list_title: str
    expected_products: int
    product_type: str
    notes: Optional[str] = None


# =============================================================================
# IWSC 2025 Competition URLs - Whiskey
# =============================================================================
#
# IMPORTANT: IWSC URL Structure
# - Base: https://www.iwsc.net/results/search/{year}
# - Pagination: /results/search/{year}/{page} (e.g., /results/search/2025/2)
# - Keyword filter: ?q={keyword} (e.g., ?q=whisky)
# - IWSC is a JavaScript-heavy SPA - requires Tier 2 (Playwright) or Tier 3 (ScrapingBee)
# - Static HTML contains only page shell, not product data
#
# Medal filtering is NOT available via URL - all medals are shown on results page.
# Products are rendered client-side from JavaScript.

IWSC_2025_WHISKEY_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://www.iwsc.net/results/search/2025?q=whisky",
        competition="IWSC",
        year=2025,
        product_type="whiskey",
        category="whisky",
        expected_products=10,
        notes="IWSC 2025 whisky results - JS-rendered SPA, requires Tier 2/3"
    ),
    CompetitionURL(
        url="https://www.iwsc.net/results/search/2025?q=scotch",
        competition="IWSC",
        year=2025,
        product_type="whiskey",
        category="scotch",
        expected_products=15,
        notes="IWSC 2025 scotch results - JS-rendered SPA, requires Tier 2/3"
    ),
    CompetitionURL(
        url="https://www.iwsc.net/results/search/2025?q=bourbon",
        competition="IWSC",
        year=2025,
        product_type="whiskey",
        category="bourbon",
        expected_products=8,
        notes="IWSC 2025 bourbon results - JS-rendered SPA, requires Tier 2/3"
    ),
]

# =============================================================================
# IWSC 2024 Competition URLs - Whiskey
# =============================================================================
IWSC_2024_WHISKEY_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://www.iwsc.net/results/search/2024?q=whisky",
        competition="IWSC",
        year=2024,
        product_type="whiskey",
        category="whisky",
        expected_products=10,
        notes="IWSC 2024 whisky results - JS-rendered SPA, requires Tier 2/3"
    ),
    CompetitionURL(
        url="https://www.iwsc.net/results/search/2024?q=scotch",
        competition="IWSC",
        year=2024,
        product_type="whiskey",
        category="scotch",
        expected_products=15,
        notes="IWSC 2024 scotch results - JS-rendered SPA, requires Tier 2/3"
    ),
]

# Alias for IWSC URLs (both years)
IWSC_URLS: List[CompetitionURL] = IWSC_2025_WHISKEY_URLS + IWSC_2024_WHISKEY_URLS


# =============================================================================
# SFWSC 2025 Competition URLs - Whiskey
# Includes Frank August Kentucky Straight Bourbon as required
# =============================================================================

SFWSC_2025_WHISKEY_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://sfspiritscomp.com/results/2025/whiskey/bourbon/double-gold",
        competition="SFWSC",
        year=2025,
        product_type="whiskey",
        category="bourbon",
        expected_products=10,
        notes="Double Gold bourbon winners - should include Frank August Kentucky Straight Bourbon"
    ),
    CompetitionURL(
        url="https://sfspiritscomp.com/results/2025/whiskey/bourbon/gold",
        competition="SFWSC",
        year=2025,
        product_type="whiskey",
        category="bourbon",
        expected_products=15,
        notes="Gold bourbon winners 2025"
    ),
    CompetitionURL(
        url="https://sfspiritscomp.com/results/2025/whiskey/american-whiskey/double-gold",
        competition="SFWSC",
        year=2025,
        product_type="whiskey",
        category="american_whiskey",
        expected_products=8,
        notes="Double Gold American whiskey winners"
    ),
]

# Alternative SFWSC URL patterns (competition sites often change structure)
SFWSC_2025_ALTERNATIVE_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://www.sfspiritscomp.com/winners/2025?category=bourbon&medal=double-gold",
        competition="SFWSC",
        year=2025,
        product_type="whiskey",
        category="bourbon",
        expected_products=10,
        notes="Alternative URL pattern for SFWSC bourbon double gold"
    ),
    CompetitionURL(
        url="https://sfspiritscomp.com/database/2025/results/bourbon",
        competition="SFWSC",
        year=2025,
        product_type="whiskey",
        category="bourbon",
        expected_products=10,
        notes="Alternative database URL pattern"
    ),
]

# Alias for SFWSC URLs
SFWSC_URLS: List[CompetitionURL] = SFWSC_2025_WHISKEY_URLS + SFWSC_2025_ALTERNATIVE_URLS


# =============================================================================
# DWWA 2025 Competition URLs - Port Wine
# =============================================================================

DWWA_2025_PORT_WINE_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?type=port&medal=gold",
        competition="DWWA",
        year=2025,
        product_type="port_wine",
        category="port",
        expected_products=10,
        notes="Gold medal port wines 2025"
    ),
    CompetitionURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?type=port&medal=silver",
        competition="DWWA",
        year=2025,
        product_type="port_wine",
        category="port",
        expected_products=15,
        notes="Silver medal port wines 2025"
    ),
    CompetitionURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?region=douro&type=port",
        competition="DWWA",
        year=2025,
        product_type="port_wine",
        category="port",
        expected_products=12,
        notes="Douro region port wines all medals"
    ),
]

# Alternative DWWA URL patterns
DWWA_2025_ALTERNATIVE_URLS: List[CompetitionURL] = [
    CompetitionURL(
        url="https://www.decanter.com/wine-reviews/search?country=portugal&type=port&vintage=2020",
        competition="DWWA",
        year=2025,
        product_type="port_wine",
        category="port",
        expected_products=8,
        notes="Alternative Decanter search for port wines"
    ),
]

# Alias for DWWA URLs (convenience for imports)
DWWA_URLS: List[CompetitionURL] = DWWA_2025_PORT_WINE_URLS + DWWA_2025_ALTERNATIVE_URLS


# =============================================================================
# Single Product Page URLs
# =============================================================================

SINGLE_PRODUCT_PAGES: List[ProductPageURL] = [
    ProductPageURL(
        url="https://www.masterofmalt.com/whiskies/glenfiddich/glenfiddich-18-year-old-whisky/",
        source_name="Master of Malt",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        notes="Classic single malt reference product"
    ),
    ProductPageURL(
        url="https://www.masterofmalt.com/whiskies/macallan/the-macallan-12-year-old-double-cask-whisky/",
        source_name="Master of Malt",
        product_name="Macallan 12 Year Old Double Cask",
        product_type="whiskey",
        notes="Popular Macallan expression"
    ),
    ProductPageURL(
        url="https://www.wine-searcher.com/find/taylor+fladgate+vintage+port+douro+portugal",
        source_name="Wine-Searcher",
        product_name="Taylor Fladgate Vintage Port",
        product_type="port_wine",
        notes="Taylor's vintage port"
    ),
    ProductPageURL(
        url="https://www.wine-searcher.com/find/graham+twenty+year+old+tawny+port+douro+portugal",
        source_name="Wine-Searcher",
        product_name="Graham's 20 Year Old Tawny Port",
        product_type="port_wine",
        notes="Premium tawny port"
    ),
    ProductPageURL(
        url="https://www.thewhiskyexchange.com/p/1234/buffalo-trace-kentucky-straight-bourbon",
        source_name="The Whisky Exchange",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        notes="Popular bourbon reference"
    ),
]

# Frank August specific URLs (required product)
FRANK_AUGUST_URLS: List[ProductPageURL] = [
    ProductPageURL(
        url="https://www.frankaugust.com/products/kentucky-straight-bourbon",
        source_name="Frank August Official",
        product_name="Frank August Kentucky Straight Bourbon",
        product_type="whiskey",
        notes="Official product page - REQUIRED PRODUCT"
    ),
    ProductPageURL(
        url="https://www.masterofmalt.com/whiskies/frank-august/frank-august-kentucky-straight-bourbon-whiskey/",
        source_name="Master of Malt",
        product_name="Frank August Kentucky Straight Bourbon",
        product_type="whiskey",
        notes="Retailer page for required product"
    ),
]


# =============================================================================
# List Page URLs (e.g., "Best Whiskeys 2025")
# Using competition result pages which list multiple award-winning products
# NOTE: Both IWSC and DWWA are JavaScript-heavy pages. The static HTML contains
# minimal product data. The AI service extracts what it can from the HTML shell.
# =============================================================================

LIST_PAGES: List[ListPageURL] = [
    ListPageURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?type=port&medal=gold",
        source_name="DWWA",
        list_title="DWWA 2025 Gold Medal Port Wines",
        expected_products=5,
        product_type="port_wine",
        notes="DWWA competition results - JavaScript-rendered page, minimal static HTML"
    ),
    ListPageURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?type=port&medal=silver",
        source_name="DWWA",
        list_title="DWWA 2025 Silver Medal Port Wines",
        expected_products=5,
        product_type="port_wine",
        notes="DWWA silver medal port wines - JavaScript-rendered page"
    ),
    ListPageURL(
        url="https://awards.decanter.com/DWWA/2025/search/wines?region=douro&type=port",
        source_name="DWWA",
        list_title="DWWA 2025 Douro Region Port Wines",
        expected_products=5,
        product_type="port_wine",
        notes="DWWA Douro region ports - JavaScript-rendered page"
    ),
]


# =============================================================================
# Utility Functions
# =============================================================================

def get_all_competition_urls() -> List[CompetitionURL]:
    """Get all competition URLs across all competitions."""
    return (
        IWSC_2025_WHISKEY_URLS +
        SFWSC_2025_WHISKEY_URLS +
        DWWA_2025_PORT_WINE_URLS
    )


def get_iwsc_urls() -> List[CompetitionURL]:
    """Get IWSC competition URLs."""
    return IWSC_2025_WHISKEY_URLS


def get_sfwsc_urls() -> List[CompetitionURL]:
    """Get SFWSC competition URLs (includes Frank August)."""
    return SFWSC_2025_WHISKEY_URLS + SFWSC_2025_ALTERNATIVE_URLS


def get_dwwa_urls() -> List[CompetitionURL]:
    """Get DWWA competition URLs for port wine."""
    return DWWA_2025_PORT_WINE_URLS + DWWA_2025_ALTERNATIVE_URLS


def get_whiskey_competition_urls() -> List[CompetitionURL]:
    """Get all whiskey competition URLs."""
    return IWSC_2025_WHISKEY_URLS + SFWSC_2025_WHISKEY_URLS


def get_port_wine_competition_urls() -> List[CompetitionURL]:
    """Get all port wine competition URLs."""
    return DWWA_2025_PORT_WINE_URLS


def get_single_product_urls() -> List[ProductPageURL]:
    """Get all single product page URLs."""
    return SINGLE_PRODUCT_PAGES + FRANK_AUGUST_URLS


def get_list_page_urls() -> List[ListPageURL]:
    """Get all list page URLs."""
    return LIST_PAGES


def get_frank_august_urls() -> List[ProductPageURL]:
    """Get URLs specifically for Frank August (required product)."""
    return FRANK_AUGUST_URLS


def find_url_for_product(product_name: str) -> Optional[ProductPageURL]:
    """
    Find a URL for a specific product by name.

    Args:
        product_name: Name of the product to find

    Returns:
        ProductPageURL if found, None otherwise
    """
    product_name_lower = product_name.lower()
    for url in get_single_product_urls():
        if product_name_lower in url.product_name.lower():
            return url
    return None
