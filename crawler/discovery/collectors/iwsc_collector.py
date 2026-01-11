"""
IWSC URL Collector - Collects detail page URLs from IWSC listing pages.

This collector extracts detail page URLs from the International Wine & Spirit
Competition (IWSC) results pages. Unlike the old parser approach, this collector
only gathers URLs - data extraction is handled by AI.

Target URL: https://www.iwsc.net/results/search/{year}

The collector:
1. Fetches listing pages from IWSC
2. Parses .c-card--listing elements to find detail links
3. Extracts medal hints from award images
4. Detects product types from category/style metadata
"""

import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base_collector import BaseCollector, AwardDetailURL

logger = logging.getLogger(__name__)


class IWSCCollector(BaseCollector):
    """
    Collects detail page URLs from IWSC listing pages.

    This collector replaces direct data parsing with URL collection.
    AI extraction handles the actual data extraction from detail pages.
    """

    COMPETITION_NAME = "IWSC"
    BASE_URL = "https://www.iwsc.net"

    # Product type detection mapping: (category, style) -> product_type
    PRODUCT_TYPE_MAPPING = {
        ("wine", "fortified"): "port_wine",
        ("wine", "port"): "port_wine",
        ("spirit", "whisky"): "whiskey",
        ("spirit", "whiskey"): "whiskey",
        ("spirit", "scotch"): "whiskey",
        ("spirit", "bourbon"): "whiskey",
        ("spirit", "rye"): "whiskey",
        ("spirit", "irish whiskey"): "whiskey",
        ("spirit", "single malt"): "whiskey",
        ("spirit", "blended"): "whiskey",
        ("spirit", "gin"): "gin",
        ("spirit", "vodka"): "vodka",
        ("spirit", "rum"): "rum",
        ("spirit", "tequila"): "tequila",
        ("spirit", "brandy"): "brandy",
        ("spirit", "cognac"): "brandy",
    }

    def collect(self, year: int, product_types: Optional[List[str]] = None) -> List[AwardDetailURL]:
        """
        Collect detail page URLs from IWSC for given year.

        Args:
            year: Competition year
            product_types: Filter by product types (e.g., ["port_wine", "whiskey"])
                          If None, collects all product types

        Returns:
            List of AwardDetailURL objects with detail page URLs
        """
        urls = []

        # Build listing URL for the year
        listing_url = f"{self.BASE_URL}/results/search/{year}"

        try:
            # Fetch the listing page
            html = self._fetch_listing_page(listing_url)

            # Parse the listing page
            all_urls = self._parse_listing_page(html, listing_url, year)

            # Filter by product types if specified
            if product_types:
                urls = [u for u in all_urls if u.product_type_hint in product_types]
            else:
                urls = all_urls

            logger.info(
                f"IWSC Collector found {len(urls)} URLs for year {year}"
                + (f" (filtered to {product_types})" if product_types else "")
            )

        except Exception as e:
            logger.error(f"Error collecting IWSC URLs for year {year}: {e}")
            raise

        return urls

    def _fetch_listing_page(self, url: str) -> str:
        """
        Fetch HTML content from listing page.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        import httpx

        response = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        response.raise_for_status()
        return response.text

    def _parse_listing_page(self, html: str, listing_url: str, year: int) -> List[AwardDetailURL]:
        """
        Parse listing page HTML and extract detail URLs.

        Args:
            html: HTML content of listing page
            listing_url: URL of the listing page
            year: Competition year

        Returns:
            List of AwardDetailURL objects
        """
        soup = BeautifulSoup(html, "lxml")
        urls = []

        # Find all listing cards
        for card in soup.select(".c-card--listing"):
            # Find detail link
            link = card.select_one("a[href*='/results/detail/']")
            if not link:
                continue

            # Build absolute URL
            href = link.get("href", "")
            detail_url = urljoin(self.BASE_URL, href)

            # Extract medal and score hints
            medal_hint, score_hint = self._extract_medal_from_card(card)

            # Detect product type
            product_type_hint = self._detect_product_type_from_card(card)

            urls.append(AwardDetailURL(
                detail_url=detail_url,
                listing_url=listing_url,
                medal_hint=medal_hint,
                score_hint=score_hint,
                competition=self.COMPETITION_NAME,
                year=year,
                product_type_hint=product_type_hint,
            ))

        return urls

    def _extract_medal_from_card(self, card) -> Tuple[str, Optional[int]]:
        """
        Extract medal type and score from card.

        Looks for medal information in:
        1. Award image src (e.g., iwsc2025-gold-95-medal.png)
        2. Award image alt text
        3. Class names

        Args:
            card: BeautifulSoup element for the card

        Returns:
            Tuple of (medal_type, score) where score may be None
        """
        medal = "Unknown"
        score = None

        # Look for awards wrapper with medal image
        awards_wrapper = card.select_one(".c-card--listing__awards-wrapper")
        if awards_wrapper:
            medal_img = awards_wrapper.select_one("img")
            if medal_img:
                # Try to extract from src
                img_src = medal_img.get("data-src") or medal_img.get("src") or ""

                # Pattern: iwsc2025-gold-95-medal or iwsc2025-silver-90-medal
                medal_match = re.search(r"(gold|silver|bronze)-?(\d+)?-?medal", img_src.lower())
                if medal_match:
                    medal = medal_match.group(1).capitalize()
                    if medal_match.group(2):
                        score = int(medal_match.group(2))
                else:
                    # Try alt text
                    alt_text = medal_img.get("alt", "").lower()
                    if "gold" in alt_text:
                        medal = "Gold"
                    elif "silver" in alt_text:
                        medal = "Silver"
                    elif "bronze" in alt_text:
                        medal = "Bronze"

        # Fallback: check for medal classes on card
        if medal == "Unknown":
            classes = " ".join(card.get("class", []))
            if "gold" in classes.lower():
                medal = "Gold"
            elif "silver" in classes.lower():
                medal = "Silver"
            elif "bronze" in classes.lower():
                medal = "Bronze"

        return medal, score

    def _detect_product_type_from_card(self, card) -> str:
        """
        Detect product type from category/style in card.

        Looks for category and style information in various elements.

        Args:
            card: BeautifulSoup element for the card

        Returns:
            Product type string (e.g., "port_wine", "whiskey", "unknown")
        """
        # Try various selectors for category
        category_selectors = [
            ".c-card--listing__category",
            ".category",
            "[class*='category']",
        ]
        category = ""
        for selector in category_selectors:
            elem = card.select_one(selector)
            if elem:
                category = elem.get_text().strip()
                break

        # Try various selectors for style
        style_selectors = [
            ".c-card--listing__style",
            ".style",
            "[class*='style']",
        ]
        style = ""
        for selector in style_selectors:
            elem = card.select_one(selector)
            if elem:
                style = elem.get_text().strip()
                break

        return self._detect_product_type(category, style)

    def _detect_product_type(self, category: str, style: str) -> str:
        """
        Map category/style to product type.

        Args:
            category: Product category (e.g., "Wine", "Spirit")
            style: Product style (e.g., "Fortified", "Whisky")

        Returns:
            Product type string (e.g., "port_wine", "whiskey", "unknown")
        """
        # Normalize inputs
        category_lower = category.lower().strip()
        style_lower = style.lower().strip()

        # Try exact match first
        key = (category_lower, style_lower)
        if key in self.PRODUCT_TYPE_MAPPING:
            return self.PRODUCT_TYPE_MAPPING[key]

        # Try partial matching for style within category
        for (cat, sty), product_type in self.PRODUCT_TYPE_MAPPING.items():
            if category_lower == cat and sty in style_lower:
                return product_type

        # Check if style contains product keywords
        style_keywords = {
            "port": "port_wine",
            "fortified": "port_wine",
            "whisky": "whiskey",
            "whiskey": "whiskey",
            "scotch": "whiskey",
            "bourbon": "whiskey",
            "gin": "gin",
            "vodka": "vodka",
            "rum": "rum",
            "tequila": "tequila",
            "brandy": "brandy",
            "cognac": "brandy",
        }

        for keyword, product_type in style_keywords.items():
            if keyword in style_lower:
                return product_type

        return "unknown"
