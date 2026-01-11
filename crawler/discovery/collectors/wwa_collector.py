"""
WWA URL Collector - Collects detail page URLs from World Whiskies Awards.

This collector extracts product detail URLs from the World Whiskies Awards
(WWA) website. WWA is a prestigious whiskey-only competition with results
organized by year and category.

Target URL: https://worldwhiskiesawards.com/winners/

The collector:
1. Fetches the winners page to discover category links
2. Visits each category page to extract winner URLs
3. Extracts award levels (World's Best, Best Regional, etc.)
4. Detects whiskey type from category information
5. Handles multiple years (2012-2025)
"""

import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base_collector import BaseCollector, AwardDetailURL

logger = logging.getLogger(__name__)


class WWACollector(BaseCollector):
    """
    Collects detail page URLs from World Whiskies Awards (WWA).

    WWA organizes winners by category with multiple award levels:
    - World's Best (top award in each category)
    - Best Regional (Best Scotch, Best American, Best Irish, etc.)
    - Country/Region Winners

    URL Structure:
    - Winners index: /winners/
    - Category page: /winner-whisky/whisky/{year}/{category-slug}
    - Product detail: /winner-whisky/{product-slug}-{id}-world-whiskies-awards-{year}
    """

    COMPETITION_NAME = "WWA"
    BASE_URL = "https://worldwhiskiesawards.com"

    # WWA category slugs mapping
    # Key: internal category name, Value: URL slug pattern
    CATEGORY_SLUGS: Dict[str, str] = {
        "single_malt": "worlds-best-single-malt",
        "bourbon": "worlds-best-bourbon",
        "rye": "worlds-best-rye",
        "blended": "worlds-best-blended",
        "blended_malt": "worlds-best-blended-malt",
        "grain": "worlds-best-grain",
        "pot_still": "worlds-best-pot-still",
        "tennessee": "worlds-best-tennessee-whiskey",
        "american_style": "worlds-best-american-style-whiskey",
        "canadian": "worlds-best-canadian-blended",
        "corn": "worlds-best-corn",
        "wheat": "worlds-best-wheat",
        "flavoured": "worlds-best-flavoured-whisky",
        "single_cask_single_malt": "worlds-best-single-cask-single-malt",
        "single_cask_single_grain": "worlds-best-single-cask-single-grain",
        "single_cask_single_rye": "worlds-best-single-cask-single-rye",
        "small_batch_bourbon": "worlds-best-small-batch-bourbon",
        "small_batch_single_malt": "worlds-best-small-batch-single-malt",
        "single_barrel_bourbon": "worlds-best-single-barrel-bourbon",
        "finished_bourbon": "worlds-best-finished-bourbon",
        "blended_limited": "worlds-best-blended-limited-release",
        "new_make": "worlds-best-new-make--young-spirit",
    }

    # Default categories to collect if none specified
    DEFAULT_CATEGORIES = [
        "single_malt",
        "bourbon",
        "rye",
        "blended",
        "blended_malt",
        "grain",
        "pot_still",
        "tennessee",
    ]

    # Rate limiting and retry configuration
    REQUEST_DELAY_SECONDS = 1.0  # Delay between requests to avoid rate limiting
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2.0

    def collect(
        self,
        year: int,
        product_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> List[AwardDetailURL]:
        """
        Collect detail page URLs from WWA for given year.

        Args:
            year: Competition year (2012-2025)
            product_types: Filter by product types (default: ["whiskey"])
                          WWA is whiskey-only, so this is mainly for consistency
            categories: Specific WWA categories to collect (e.g., ["bourbon", "single_malt"])
                       If None, collects from all default categories

        Returns:
            List of AwardDetailURL objects with detail page URLs
        """
        urls = []

        # Determine which categories to collect
        target_categories = categories or self.DEFAULT_CATEGORIES

        # First, try to get category URLs from the winners page
        category_urls = self._get_category_urls(year, target_categories)

        if not category_urls:
            logger.warning(f"No category URLs found for WWA {year}")
            return urls

        # Collect from each category page
        for category_name, category_url in category_urls.items():
            try:
                category_urls_list = self._collect_from_category_page(
                    category_url, category_name, year
                )
                urls.extend(category_urls_list)
                # Rate limiting between category pages
                time.sleep(self.REQUEST_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"Error collecting from {category_name} page: {e}")
                continue

        # Filter by product types if specified (all WWA are whiskey)
        if product_types:
            urls = [u for u in urls if u.product_type_hint in product_types]

        logger.info(
            f"WWA Collector found {len(urls)} URLs for year {year}"
            + (f" (categories: {target_categories})" if categories else "")
        )

        return urls

    def _get_winners_page_url(self, year: int) -> str:
        """
        Get the winners index page URL for a year.

        Args:
            year: Competition year

        Returns:
            URL string for the winners page
        """
        return f"{self.BASE_URL}/winners/"

    def _get_category_url(self, year: int, category: str) -> str:
        """
        Build the category page URL for a specific year and category.

        Args:
            year: Competition year
            category: Category name (e.g., "single_malt", "bourbon")

        Returns:
            URL string for the category page
        """
        slug = self._get_category_slug(category)
        # WWA URL pattern includes year and sometimes category ID
        # Pattern: /winner-whisky/whisky/{year}/{slug}-world-whiskies-awards-{year}
        return f"{self.BASE_URL}/winner-whisky/whisky/{year}/{slug}-world-whiskies-awards-{year}"

    def _get_category_slug(self, category: str) -> str:
        """
        Get the URL slug for a category name.

        Args:
            category: Internal category name (e.g., "single_malt")

        Returns:
            URL slug (e.g., "worlds-best-single-malt")
        """
        return self.CATEGORY_SLUGS.get(category, category.replace("_", "-"))

    def _get_category_urls(
        self, year: int, categories: List[str]
    ) -> Dict[str, str]:
        """
        Get category page URLs for the specified year and categories.

        Args:
            year: Competition year
            categories: List of category names to get URLs for

        Returns:
            Dictionary mapping category name to URL
        """
        category_urls = {}

        # First try to discover category URLs from the winners page
        winners_url = self._get_winners_page_url(year)

        try:
            html = self._fetch_page_with_retry(winners_url)
            discovered_urls = self._discover_category_urls_from_page(html, year)

            # Match discovered URLs to requested categories
            for category in categories:
                slug = self._get_category_slug(category)
                # Look for matching URL in discovered URLs
                for url in discovered_urls:
                    if slug in url.lower():
                        category_urls[category] = url
                        break

                # If not found in discovery, construct URL directly
                if category not in category_urls:
                    category_urls[category] = self._get_category_url(year, category)

        except Exception as e:
            logger.warning(f"Could not fetch winners page: {e}. Using constructed URLs.")
            # Fall back to constructed URLs
            for category in categories:
                category_urls[category] = self._get_category_url(year, category)

        return category_urls

    def _discover_category_urls_from_page(self, html: str, year: int) -> List[str]:
        """
        Discover category URLs from the winners page HTML.

        Args:
            html: HTML content of winners page
            year: Competition year

        Returns:
            List of discovered category URLs
        """
        soup = BeautifulSoup(html, "lxml")
        urls = []

        # Find all links to category pages
        # Pattern: /winner-whisky/whisky/{year}/...
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if f"/winner-whisky/whisky/{year}/" in href:
                full_url = urljoin(self.BASE_URL, href)
                if full_url not in urls:
                    urls.append(full_url)

        return urls

    def _collect_from_category_page(
        self, url: str, category_name: str, year: int
    ) -> List[AwardDetailURL]:
        """
        Collect winner URLs from a category page.

        Args:
            url: Category page URL
            category_name: Category name for logging
            year: Competition year

        Returns:
            List of AwardDetailURL objects
        """
        urls = []

        try:
            html = self._fetch_page_with_retry(url)
            urls = self._parse_category_page(html, url, year, category_name)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Category page not found: {url}")
            else:
                logger.warning(f"HTTP error fetching {url}: {e}")
        except Exception as e:
            logger.warning(f"Error fetching category page {url}: {e}")

        return urls

    def _parse_category_page(
        self, html: str, listing_url: str, year: int, category_name: str
    ) -> List[AwardDetailURL]:
        """
        Parse a category page to extract winner URLs.

        Args:
            html: HTML content of category page
            listing_url: URL of the category page
            year: Competition year
            category_name: Category name

        Returns:
            List of AwardDetailURL objects
        """
        soup = BeautifulSoup(html, "lxml")
        urls = []

        # Find all product links
        # WWA uses various link patterns to product detail pages
        # Pattern: /winner-whisky/{product-slug}-{id}-world-whiskies-awards-{year}

        # Find links within the main content area
        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Skip navigation and category links
            if f"/winner-whisky/whisky/{year}/" in href:
                continue

            # Match product detail URLs
            if "/winner-whisky/" in href and f"world-whiskies-awards-{year}" in href:
                full_url = urljoin(self.BASE_URL, href)

                # Skip if this is the same as listing URL
                if full_url == listing_url:
                    continue

                # Try to extract award level from surrounding text
                award_level = self._extract_award_level_from_context(link)

                # Check for duplicates
                if any(u.detail_url == full_url for u in urls):
                    continue

                urls.append(
                    AwardDetailURL(
                        detail_url=full_url,
                        listing_url=listing_url,
                        medal_hint=award_level,
                        score_hint=None,  # WWA doesn't publish scores
                        competition=self.COMPETITION_NAME,
                        year=year,
                        product_type_hint="whiskey",  # WWA is whiskey-only
                    )
                )

        # If no detail URLs found, try to extract winners from list structure
        if not urls:
            urls = self._parse_winner_list(soup, listing_url, year, category_name)

        return urls

    def _parse_winner_list(
        self, soup: BeautifulSoup, listing_url: str, year: int, category_name: str
    ) -> List[AwardDetailURL]:
        """
        Parse winners from list structure on category page.

        Some WWA pages list winners without individual detail page links.

        Args:
            soup: BeautifulSoup object of the page
            listing_url: URL of the category page
            year: Competition year
            category_name: Category name

        Returns:
            List of AwardDetailURL objects
        """
        urls = []

        # Look for award list structure (.listaward)
        award_lists = soup.select(".listaward li")

        for item in award_lists:
            # Find any link in the item
            link = item.find("a", href=True)
            if link:
                href = link["href"]
                if "/winner-whisky/" in href:
                    full_url = urljoin(self.BASE_URL, href)

                    # Extract award level from heading
                    heading = item.find(["h3", "h4", "strong"])
                    award_level = "Winner"
                    if heading:
                        award_level = self._extract_award_level(heading.get_text())

                    urls.append(
                        AwardDetailURL(
                            detail_url=full_url,
                            listing_url=listing_url,
                            medal_hint=award_level,
                            score_hint=None,
                            competition=self.COMPETITION_NAME,
                            year=year,
                            product_type_hint="whiskey",
                        )
                    )

        return urls

    def _extract_award_level_from_context(self, link_element) -> str:
        """
        Extract award level from the context around a link.

        Args:
            link_element: BeautifulSoup link element

        Returns:
            Award level string (e.g., "World's Best", "Best Scotch")
        """
        # Check parent elements for heading or award text
        parent = link_element.parent
        while parent and parent.name not in ["body", "html"]:
            # Look for preceding heading
            prev_heading = parent.find_previous_sibling(["h2", "h3", "h4"])
            if prev_heading:
                return self._extract_award_level(prev_heading.get_text())

            # Look for heading within parent
            heading = parent.find(["h2", "h3", "h4"])
            if heading:
                return self._extract_award_level(heading.get_text())

            parent = parent.parent

        return "Winner"

    def _extract_award_level(self, text: str) -> str:
        """
        Extract award level from text.

        Args:
            text: Text containing award information

        Returns:
            Award level string
        """
        text_lower = text.lower().strip()

        # Check for World's Best
        if "world's best" in text_lower or "worlds best" in text_lower:
            return "World's Best"

        # Check for regional best
        regional_patterns = [
            (r"best\s+scotch", "Best Scotch"),
            (r"best\s+american", "Best American"),
            (r"best\s+irish", "Best Irish"),
            (r"best\s+japanese", "Best Japanese"),
            (r"best\s+canadian", "Best Canadian"),
            (r"best\s+australian", "Best Australian"),
            (r"best\s+indian", "Best Indian"),
            (r"best\s+taiwanese", "Best Taiwanese"),
            (r"best\s+kentucky", "Best Kentucky"),
            (r"best\s+non-kentucky", "Best Non-Kentucky"),
            (r"best\s+tennessee", "Best Tennessee"),
            (r"best\s+speyside", "Best Speyside"),
            (r"best\s+islay", "Best Islay"),
            (r"best\s+highland", "Best Highland"),
            (r"best\s+lowland", "Best Lowland"),
            (r"best\s+campbeltown", "Best Campbeltown"),
        ]

        for pattern, label in regional_patterns:
            if re.search(pattern, text_lower):
                return label

        # Generic "best" pattern
        if text_lower.startswith("best "):
            # Capitalize and return
            return text.strip()

        return "Winner"

    def _detect_product_type(self, category_text: str) -> str:
        """
        Detect product type from category text.

        WWA is a whiskey-only competition, so all products are whiskey.

        Args:
            category_text: Category or award text

        Returns:
            Product type string (always "whiskey" for WWA)
        """
        # WWA is exclusively for whiskey - all entries are whiskey
        return "whiskey"

    def _fetch_page_with_retry(self, url: str) -> str:
        """
        Fetch HTML content from URL with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string

        Raises:
            Exception: If all retries fail
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._fetch_page(url)
            except (httpx.ConnectError, httpx.ReadError, OSError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    logger.debug(
                        f"Retry {attempt + 1}/{self.MAX_RETRIES} for {url} after error: {e}"
                    )
                    time.sleep(self.RETRY_DELAY_SECONDS * (attempt + 1))
                continue
            except httpx.HTTPStatusError:
                # Don't retry HTTP errors (404, 500, etc.)
                raise

        # If we get here, all retries failed
        raise last_error

    def _fetch_page(self, url: str) -> str:
        """
        Fetch HTML content from URL.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        response = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        response.raise_for_status()
        return response.text
