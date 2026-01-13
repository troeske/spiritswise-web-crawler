"""
Real Competition URLs for E2E Testing.

This module provides actual URLs from real competition sites, retailers,
and review sites for end-to-end testing of the V2 architecture.

IMPORTANT: These are real URLs that may change over time. Update as needed.

Sources:
- IWSC (International Wine & Spirit Competition): https://iwsc.net
- SFWSC (San Francisco World Spirits Competition): https://sfspiritscomp.com
- DWWA (Decanter World Wine Awards): https://awards.decanter.com

V3 Additions (Task 3.2.3):
- Producer page URLs (official brand sites)
- Review site URLs (whiskyadvocate, masterofmalt reviews)
- Retailer URLs (for deprioritization testing)

Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 9.3
"""

from dataclasses import dataclass, field
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
# V3: New URL Dataclasses for Enrichment Pipeline Testing
# Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 9.3
# =============================================================================


@dataclass
class ProducerPageURL:
    """
    Represents an official producer/brand page URL.

    Used for Step 1 of the 2-step enrichment pipeline.
    These are official brand websites with high confidence data (0.85-0.95).

    Attributes:
        url: The official brand/producer page URL
        brand_name: Name of the brand/producer
        product_name: Optional specific product name
        product_type: Expected product type (whiskey, port_wine)
        is_official: Whether this is the official brand domain
        expected_fields: Fields expected to be extractable from this source
        notes: Any special notes about the URL
    """

    url: str
    brand_name: str
    product_type: str
    product_name: Optional[str] = None
    is_official: bool = True
    expected_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class ReviewSiteURL:
    """
    Represents a review site URL.

    Used for Step 2 of the 2-step enrichment pipeline.
    These are authoritative review sites with medium confidence data (0.70-0.80).

    Attributes:
        url: The review page URL
        site_name: Name of the review site
        product_name: Product being reviewed
        product_type: Expected product type
        has_tasting_notes: Whether the review includes tasting notes
        has_ratings: Whether the review includes numerical ratings
        expected_fields: Fields expected to be extractable from this source
        notes: Any special notes about the URL
    """

    url: str
    site_name: str
    product_name: str
    product_type: str
    has_tasting_notes: bool = True
    has_ratings: bool = False
    expected_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class RetailerURL:
    """
    Represents a retailer URL.

    Used for deprioritization testing - retailer URLs should be ranked lower
    than official producer pages and review sites in the enrichment pipeline.

    Attributes:
        url: The retailer page URL
        retailer_name: Name of the retailer
        product_name: Product being sold
        product_type: Expected product type
        is_major_retailer: Whether this is a major/known retailer domain
        notes: Any special notes about the URL
    """

    url: str
    retailer_name: str
    product_name: str
    product_type: str
    is_major_retailer: bool = True
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
# V3: Producer Page URLs (Official Brand Sites)
# Task 3.2.3: Add producer page URLs for Step 1 enrichment testing
# Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.1.1
#
# These URLs represent official brand/producer websites that should:
# - Be prioritized in URL filtering (brand in domain)
# - Provide high confidence data (0.85-0.95)
# - Contain authoritative product specifications
# =============================================================================

PRODUCER_PAGE_URLS_WHISKEY: List[ProducerPageURL] = [
    # Bourbon Producers
    ProducerPageURL(
        url="https://www.frankaugust.com/products/kentucky-straight-bourbon",
        brand_name="Frank August",
        product_name="Frank August Kentucky Straight Bourbon",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "abv", "description", "mash_bill"],
        notes="Official Frank August - primary test product for bourbon enrichment",
    ),
    ProducerPageURL(
        url="https://www.buffalotracedistillery.com/our-brands/buffalo-trace.html",
        brand_name="Buffalo Trace",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "distillery", "abv", "description"],
        notes="Buffalo Trace Distillery official - flagship bourbon",
    ),
    ProducerPageURL(
        url="https://www.woodfordreserve.com/whiskey/distillers-select/",
        brand_name="Woodford Reserve",
        product_name="Woodford Reserve Distiller's Select",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "distillery", "abv", "mash_bill"],
        notes="Woodford Reserve official - premium Kentucky bourbon",
    ),
    ProducerPageURL(
        url="https://www.makersmark.com/our-whisky",
        brand_name="Maker's Mark",
        product_name="Maker's Mark Kentucky Straight Bourbon",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "abv", "description"],
        notes="Maker's Mark official - wheated bourbon",
    ),

    # Scotch Whisky Producers
    ProducerPageURL(
        url="https://www.glenfiddich.com/whiskies/18-year-old/",
        brand_name="Glenfiddich",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "age_statement", "abv", "region", "description"],
        notes="Glenfiddich official - classic Speyside single malt",
    ),
    ProducerPageURL(
        url="https://www.themacallan.com/en/double-cask-12-years-old",
        brand_name="The Macallan",
        product_name="The Macallan 12 Year Old Double Cask",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "age_statement", "abv", "primary_cask"],
        notes="Macallan official - premium Highland single malt",
    ),
    ProducerPageURL(
        url="https://www.lagavulin.com/en/whisky/lagavulin-16-year-old",
        brand_name="Lagavulin",
        product_name="Lagavulin 16 Year Old",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "age_statement", "abv", "region"],
        notes="Lagavulin official - peated Islay single malt",
    ),

    # Japanese Whisky Producers
    ProducerPageURL(
        url="https://www.suntory.com/brands/whisky/yamazaki/",
        brand_name="Yamazaki",
        product_name="Yamazaki Single Malt Whisky",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "distillery", "country"],
        notes="Suntory Yamazaki official - Japanese single malt",
    ),
    ProducerPageURL(
        url="https://www.nikka.com/eng/brands/taketsuru/",
        brand_name="Nikka",
        product_name="Nikka Taketsuru Pure Malt",
        product_type="whiskey",
        is_official=True,
        expected_fields=["name", "brand", "country", "description"],
        notes="Nikka official - Japanese pure malt",
    ),
]

PRODUCER_PAGE_URLS_PORT_WINE: List[ProducerPageURL] = [
    # Major Port Houses
    ProducerPageURL(
        url="https://www.taylor.pt/en/wines/tawny-20-years",
        brand_name="Taylor's",
        product_name="Taylor's 20 Year Old Tawny Port",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "indication_age", "producer_house"],
        notes="Taylor's official - premium aged tawny",
    ),
    ProducerPageURL(
        url="https://www.grahams-port.com/ports/20-year-old-tawny/",
        brand_name="Graham's",
        product_name="Graham's 20 Year Old Tawny Port",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "indication_age", "producer_house"],
        notes="Graham's official - Symington family port house",
    ),
    ProducerPageURL(
        url="https://www.fonseca.pt/en/wines/vintage-ports/vintage-2017/",
        brand_name="Fonseca",
        product_name="Fonseca Vintage Port 2017",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "harvest_year", "producer_house"],
        notes="Fonseca official - declared vintage port",
    ),
    ProducerPageURL(
        url="https://www.dows-port.com/ports/vintage-port-2016/",
        brand_name="Dow's",
        product_name="Dow's Vintage Port 2016",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "harvest_year", "producer_house"],
        notes="Dow's official - Symington vintage port",
    ),
    ProducerPageURL(
        url="https://www.sandeman.com/wines/porto/aged-tawny-20-years",
        brand_name="Sandeman",
        product_name="Sandeman 20 Year Old Tawny Port",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "indication_age"],
        notes="Sandeman official - iconic Don character",
    ),
    ProducerPageURL(
        url="https://www.warre.com/ports/vintage-port-2017/",
        brand_name="Warre's",
        product_name="Warre's Vintage Port 2017",
        product_type="port_wine",
        is_official=True,
        expected_fields=["name", "brand", "style", "harvest_year", "producer_house"],
        notes="Warre's official - oldest British port shipper",
    ),
]

# Combined producer page URLs
PRODUCER_PAGE_URLS: List[ProducerPageURL] = (
    PRODUCER_PAGE_URLS_WHISKEY + PRODUCER_PAGE_URLS_PORT_WINE
)


# =============================================================================
# V3: Review Site URLs
# Task 3.2.3: Add review site URLs for Step 2 enrichment testing
# Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.1.2
#
# These URLs represent authoritative review sites that should:
# - Provide tasting notes and detailed descriptions
# - Have medium confidence data (0.70-0.80)
# - Be used after producer page enrichment if not COMPLETE
# =============================================================================

REVIEW_SITE_URLS_WHISKEY: List[ReviewSiteURL] = [
    # Whisky Advocate Reviews
    ReviewSiteURL(
        url="https://www.whiskyadvocate.com/ratings-reviews/?search=buffalo+trace",
        site_name="Whisky Advocate",
        product_name="Buffalo Trace",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "rating_score"],
        notes="Whisky Advocate - authoritative ratings and reviews",
    ),
    ReviewSiteURL(
        url="https://www.whiskyadvocate.com/ratings-reviews/?search=glenfiddich+18",
        site_name="Whisky Advocate",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "rating_score"],
        notes="Whisky Advocate Glenfiddich review",
    ),
    ReviewSiteURL(
        url="https://www.whiskyadvocate.com/ratings-reviews/?search=macallan+12",
        site_name="Whisky Advocate",
        product_name="The Macallan 12 Year Old",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description"],
        notes="Whisky Advocate Macallan review",
    ),

    # Master of Malt Reviews (also retailer but has detailed reviews)
    ReviewSiteURL(
        url="https://www.masterofmalt.com/whiskies/glenfiddich/glenfiddich-18-year-old-whisky/",
        site_name="Master of Malt",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "abv", "volume_ml"],
        notes="Master of Malt - detailed specs and tasting notes",
    ),
    ReviewSiteURL(
        url="https://www.masterofmalt.com/whiskies/buffalo-trace/buffalo-trace-whiskey/",
        site_name="Master of Malt",
        product_name="Buffalo Trace",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "abv"],
        notes="Master of Malt Buffalo Trace review",
    ),

    # Distiller Reviews
    ReviewSiteURL(
        url="https://distiller.com/spirits/buffalo-trace-kentucky-straight-bourbon",
        site_name="Distiller",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "rating_score"],
        notes="Distiller app review database",
    ),
    ReviewSiteURL(
        url="https://distiller.com/spirits/glenfiddich-18-year-old",
        site_name="Distiller",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description"],
        notes="Distiller Glenfiddich review",
    ),

    # Breaking Bourbon (bourbon-specific)
    ReviewSiteURL(
        url="https://www.breakingbourbon.com/review/buffalo-trace",
        site_name="Breaking Bourbon",
        product_name="Buffalo Trace",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "rating_score"],
        notes="Breaking Bourbon - bourbon-focused reviews",
    ),
    ReviewSiteURL(
        url="https://www.breakingbourbon.com/review/woodford-reserve-distillers-select",
        site_name="Breaking Bourbon",
        product_name="Woodford Reserve Distiller's Select",
        product_type="whiskey",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description"],
        notes="Breaking Bourbon Woodford review",
    ),
]

REVIEW_SITE_URLS_PORT_WINE: List[ReviewSiteURL] = [
    # Decanter Reviews
    ReviewSiteURL(
        url="https://www.decanter.com/wine-reviews/search?q=taylor+port",
        site_name="Decanter",
        product_name="Taylor's Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description", "rating_score"],
        notes="Decanter - authoritative wine reviews",
    ),
    ReviewSiteURL(
        url="https://www.decanter.com/wine-reviews/search?q=graham+tawny+port",
        site_name="Decanter",
        product_name="Graham's Tawny Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "finish_description"],
        notes="Decanter Graham's review",
    ),

    # Wine Enthusiast Reviews
    ReviewSiteURL(
        url="https://www.winemag.com/buying-guide/?searchTerm=taylor+port",
        site_name="Wine Enthusiast",
        product_name="Taylor's Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["description", "rating_score"],
        notes="Wine Enthusiast - buying guide reviews",
    ),
    ReviewSiteURL(
        url="https://www.winemag.com/buying-guide/?searchTerm=fonseca+vintage+port",
        site_name="Wine Enthusiast",
        product_name="Fonseca Vintage Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["description", "rating_score"],
        notes="Wine Enthusiast Fonseca review",
    ),

    # Wine-Searcher Reviews
    ReviewSiteURL(
        url="https://www.wine-searcher.com/find/taylor+fladgate+tawny+twenty+year+old+port+douro",
        site_name="Wine-Searcher",
        product_name="Taylor Fladgate 20 Year Old Tawny Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["description", "critic_scores"],
        notes="Wine-Searcher aggregates critic scores",
    ),
    ReviewSiteURL(
        url="https://www.wine-searcher.com/find/dow+vintage+port+douro",
        site_name="Wine-Searcher",
        product_name="Dow's Vintage Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["description", "critic_scores"],
        notes="Wine-Searcher Dow's review",
    ),

    # JancisRobinson.com (premium wine reviews)
    ReviewSiteURL(
        url="https://www.jancisrobinson.com/tastings/search?q=taylor+port",
        site_name="Jancis Robinson",
        product_name="Taylor's Port",
        product_type="port_wine",
        has_tasting_notes=True,
        has_ratings=True,
        expected_fields=["nose_description", "palate_description", "rating_score"],
        notes="Jancis Robinson - premium wine critic",
    ),
]

# Combined review site URLs
REVIEW_SITE_URLS: List[ReviewSiteURL] = (
    REVIEW_SITE_URLS_WHISKEY + REVIEW_SITE_URLS_PORT_WINE
)


# =============================================================================
# V3: Retailer URLs (For Deprioritization Testing)
# Task 3.2.3: Add retailer URLs for deprioritization testing
# Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.1.1
#
# These URLs represent retailer sites that should:
# - Be deprioritized in URL filtering
# - Be ranked below official sites and review sites
# - Used for testing the URL priority filtering logic
# =============================================================================

RETAILER_URLS_WHISKEY: List[RetailerURL] = [
    # Total Wine & More
    RetailerURL(
        url="https://www.totalwine.com/spirits/bourbon/kentucky-straight-bourbon/buffalo-trace-bourbon/p/98566750",
        retailer_name="Total Wine",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="Total Wine - major US spirits retailer, should be deprioritized",
    ),
    RetailerURL(
        url="https://www.totalwine.com/spirits/bourbon/small-batch-bourbon/woodford-reserve-bourbon/p/95161750",
        retailer_name="Total Wine",
        product_name="Woodford Reserve Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="Total Wine Woodford listing",
    ),

    # Drizly
    RetailerURL(
        url="https://drizly.com/liquor/whiskey/bourbon/buffalo-trace-bourbon/p11174",
        retailer_name="Drizly",
        product_name="Buffalo Trace Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="Drizly - delivery marketplace, should be deprioritized",
    ),
    RetailerURL(
        url="https://drizly.com/liquor/whiskey/scotch-whisky/glenfiddich-18-year/p4716",
        retailer_name="Drizly",
        product_name="Glenfiddich 18 Year",
        product_type="whiskey",
        is_major_retailer=True,
        notes="Drizly Glenfiddich listing",
    ),

    # ReserveBar
    RetailerURL(
        url="https://www.reservebar.com/products/buffalo-trace-kentucky-straight-bourbon",
        retailer_name="ReserveBar",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="ReserveBar - premium spirits retailer",
    ),

    # The Whisky Exchange
    RetailerURL(
        url="https://www.thewhiskyexchange.com/p/1234/buffalo-trace-kentucky-straight-bourbon",
        retailer_name="The Whisky Exchange",
        product_name="Buffalo Trace Kentucky Straight Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="The Whisky Exchange - UK retailer",
    ),
    RetailerURL(
        url="https://www.thewhiskyexchange.com/p/5678/glenfiddich-18-year-old",
        retailer_name="The Whisky Exchange",
        product_name="Glenfiddich 18 Year Old",
        product_type="whiskey",
        is_major_retailer=True,
        notes="The Whisky Exchange Glenfiddich listing",
    ),

    # Caskers
    RetailerURL(
        url="https://www.caskers.com/buffalo-trace-bourbon/",
        retailer_name="Caskers",
        product_name="Buffalo Trace Bourbon",
        product_type="whiskey",
        is_major_retailer=True,
        notes="Caskers - online spirits retailer",
    ),
]

RETAILER_URLS_PORT_WINE: List[RetailerURL] = [
    # Wine.com
    RetailerURL(
        url="https://www.wine.com/product/taylors-20-year-old-tawny-port/123456",
        retailer_name="Wine.com",
        product_name="Taylor's 20 Year Old Tawny Port",
        product_type="port_wine",
        is_major_retailer=True,
        notes="Wine.com - major wine retailer",
    ),
    RetailerURL(
        url="https://www.wine.com/product/grahams-20-year-old-tawny-port/654321",
        retailer_name="Wine.com",
        product_name="Graham's 20 Year Old Tawny Port",
        product_type="port_wine",
        is_major_retailer=True,
        notes="Wine.com Graham's listing",
    ),

    # Total Wine & More (Port section)
    RetailerURL(
        url="https://www.totalwine.com/wine/dessert-fortified-wine/port/taylors-20-year-old-tawny/p/123456",
        retailer_name="Total Wine",
        product_name="Taylor's 20 Year Old Tawny",
        product_type="port_wine",
        is_major_retailer=True,
        notes="Total Wine port listing",
    ),

    # Vivino
    RetailerURL(
        url="https://www.vivino.com/taylor-s-20-year-old-tawny-port/w/1234567",
        retailer_name="Vivino",
        product_name="Taylor's 20 Year Old Tawny Port",
        product_type="port_wine",
        is_major_retailer=True,
        notes="Vivino - wine marketplace with user reviews",
    ),
    RetailerURL(
        url="https://www.vivino.com/fonseca-vintage-port/w/7654321",
        retailer_name="Vivino",
        product_name="Fonseca Vintage Port",
        product_type="port_wine",
        is_major_retailer=True,
        notes="Vivino Fonseca listing",
    ),

    # K&L Wine Merchants
    RetailerURL(
        url="https://www.klwines.com/p/i?i=123456&searchId=taylor-port",
        retailer_name="K&L Wine Merchants",
        product_name="Taylor's Port",
        product_type="port_wine",
        is_major_retailer=True,
        notes="K&L Wine Merchants - specialty retailer",
    ),
]

# Combined retailer URLs
RETAILER_URLS: List[RetailerURL] = RETAILER_URLS_WHISKEY + RETAILER_URLS_PORT_WINE


# =============================================================================
# V3: Known Retailer Domains (for URL filtering)
# Used by EnrichmentPipelineV3 to deprioritize retailer URLs
# =============================================================================

KNOWN_RETAILER_DOMAINS: List[str] = [
    # Major US Retailers
    "totalwine.com",
    "drizly.com",
    "reservebar.com",
    "caskers.com",
    "wine.com",

    # UK/EU Retailers
    "thewhiskyexchange.com",
    "masterofmalt.com",
    "whiskyshop.com",
    "finedrams.com",

    # Marketplaces
    "vivino.com",
    "wine-searcher.com",  # Aggregator but often links to retailers

    # General eCommerce
    "amazon.com",
    "amazon.co.uk",
    "ebay.com",
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


# =============================================================================
# V3: New Utility Functions for Enrichment Pipeline Testing
# =============================================================================

def get_producer_page_urls(product_type: Optional[str] = None) -> List[ProducerPageURL]:
    """
    Get producer page URLs, optionally filtered by product type.

    Args:
        product_type: Optional filter for whiskey or port_wine

    Returns:
        List of ProducerPageURL instances
    """
    if product_type == "whiskey":
        return PRODUCER_PAGE_URLS_WHISKEY
    elif product_type == "port_wine":
        return PRODUCER_PAGE_URLS_PORT_WINE
    return PRODUCER_PAGE_URLS


def get_review_site_urls(product_type: Optional[str] = None) -> List[ReviewSiteURL]:
    """
    Get review site URLs, optionally filtered by product type.

    Args:
        product_type: Optional filter for whiskey or port_wine

    Returns:
        List of ReviewSiteURL instances
    """
    if product_type == "whiskey":
        return REVIEW_SITE_URLS_WHISKEY
    elif product_type == "port_wine":
        return REVIEW_SITE_URLS_PORT_WINE
    return REVIEW_SITE_URLS


def get_retailer_urls(product_type: Optional[str] = None) -> List[RetailerURL]:
    """
    Get retailer URLs, optionally filtered by product type.

    Args:
        product_type: Optional filter for whiskey or port_wine

    Returns:
        List of RetailerURL instances
    """
    if product_type == "whiskey":
        return RETAILER_URLS_WHISKEY
    elif product_type == "port_wine":
        return RETAILER_URLS_PORT_WINE
    return RETAILER_URLS


def get_known_retailer_domains() -> List[str]:
    """
    Get list of known retailer domains for URL deprioritization.

    Returns:
        List of retailer domain strings
    """
    return KNOWN_RETAILER_DOMAINS


def is_retailer_domain(url: str) -> bool:
    """
    Check if a URL is from a known retailer domain.

    Args:
        url: URL to check

    Returns:
        True if URL is from a known retailer domain
    """
    url_lower = url.lower()
    return any(domain in url_lower for domain in KNOWN_RETAILER_DOMAINS)


def find_producer_url_for_brand(brand_name: str) -> Optional[ProducerPageURL]:
    """
    Find a producer page URL for a specific brand.

    Args:
        brand_name: Brand name to find

    Returns:
        ProducerPageURL if found, None otherwise
    """
    brand_lower = brand_name.lower()
    for url in PRODUCER_PAGE_URLS:
        if brand_lower in url.brand_name.lower():
            return url
    return None


def find_review_urls_for_product(
    product_name: str,
    limit: int = 3
) -> List[ReviewSiteURL]:
    """
    Find review site URLs for a specific product.

    Args:
        product_name: Product name to search for
        limit: Maximum number of URLs to return

    Returns:
        List of matching ReviewSiteURL instances
    """
    product_lower = product_name.lower()
    matches = []
    for url in REVIEW_SITE_URLS:
        if product_lower in url.product_name.lower():
            matches.append(url)
            if len(matches) >= limit:
                break
    return matches
