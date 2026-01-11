"""
DWWA URL Collector - Collects detail page URLs from Decanter World Wine Awards.

This collector uses Playwright for JavaScript rendering since DWWA is a
JavaScript-rendered site. It navigates to awards.decanter.com, applies
the Fortified category filter to capture port wines, and extracts detail
page URLs for later AI extraction.

Target URL: https://awards.decanter.com/DWWA/{year}/search

The collector:
1. Launches a headless browser via Playwright
2. Navigates to DWWA search page
3. Applies "Fortified" category filter
4. Handles pagination or infinite scroll
5. Extracts detail page URLs with medal hints
6. Detects port wine styles from card text
"""

import asyncio
import logging
import re
from typing import List, Optional, Tuple

from .base_collector import BaseCollector, AwardDetailURL

logger = logging.getLogger(__name__)


class DWWACollector(BaseCollector):
    """
    Collects detail page URLs from Decanter World Wine Awards (DWWA).

    This collector uses Playwright for JavaScript-rendered pages.
    It applies the Fortified category filter to discover port wines
    and other fortified wine award winners.

    The collector is async and must be awaited.
    """

    COMPETITION_NAME = "DWWA"
    BASE_URL = "https://awards.decanter.com"

    # Port wine style patterns for detection - ORDER MATTERS!
    # More specific patterns first, then general ones
    PORT_STYLE_PATTERNS = [
        # Specific compound styles first
        ("single_quinta", re.compile(r"\bsingle\s+quinta\b", re.IGNORECASE)),
        ("lbv", re.compile(r"\blbv\b|\blate\s+bottled\s+vintage\b", re.IGNORECASE)),
        ("white_port", re.compile(r"\bwhite\s+port\b", re.IGNORECASE)),
        ("rose_port", re.compile(r"\bros[eé]\s+port\b|\bpink\s+port\b", re.IGNORECASE)),
        # Then specific single-word styles
        ("garrafeira", re.compile(r"\bgarrafeira\b", re.IGNORECASE)),
        ("colheita", re.compile(r"\bcolheita\b", re.IGNORECASE)),
        ("crusted", re.compile(r"\bcrusted\b", re.IGNORECASE)),
        ("tawny", re.compile(r"\btawny\b", re.IGNORECASE)),
        ("ruby", re.compile(r"\bruby\b", re.IGNORECASE)),
        # Generic vintage last (to avoid matching "Late Bottled Vintage" or "Single Quinta Vintage")
        ("vintage", re.compile(r"\bvintage\s+port\b|\b(?<!bottled\s)(?<!quinta\s)vintage\b", re.IGNORECASE)),
    ]

    # Known fortified wine producers (Portuguese and non-Portuguese)
    FORTIFIED_PRODUCERS = {
        # Portuguese port houses
        "taylor", "graham", "fonseca", "sandeman", "dow",
        "warre", "cockburn", "croft", "quinta do noval", "niepoort",
        "ramos pinto", "ferreira", "kopke", "burmester", "churchill",
        "taylor fladgate", "taylor's", "graham's", "fonseca guimaraens",
        "warre's", "cockburn's", "dow's", "croft port",
        # South African Cape Port producers
        "galpin peak", "boplaas", "allesverloren",
        "de krans", "axe hill", "calitzdorp",
        # Australian fortified wine producers
        "seppeltsfield", "yalumba", "penfolds",
        "morris", "chambers", "campbells",
    }

    # Medal mapping for extraction
    MEDAL_PATTERNS = {
        "Platinum": re.compile(r"\bplatinum\b|\bbest\s+in\s+show\b", re.IGNORECASE),
        "Gold": re.compile(r"\bgold\b", re.IGNORECASE),
        "Silver": re.compile(r"\bsilver\b", re.IGNORECASE),
        "Bronze": re.compile(r"\bbronze\b", re.IGNORECASE),
    }

    async def collect(
        self, year: int, product_types: Optional[List[str]] = None
    ) -> List[AwardDetailURL]:
        """
        Collect detail page URLs from DWWA for given year.

        Uses Playwright to render JavaScript and navigate through results.

        Args:
            year: Competition year
            product_types: Filter by product types (e.g., ["port_wine"])
                          If None, collects all fortified wines

        Returns:
            List of AwardDetailURL objects with detail page URLs
        """
        urls = []

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Launch headless browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                try:
                    # Navigate to DWWA search page
                    search_url = f"{self.BASE_URL}/DWWA/{year}/search"
                    logger.info(f"Navigating to DWWA: {search_url}")
                    await page.goto(search_url, wait_until="networkidle", timeout=60000)

                    # Wait for page to load and apply filters
                    await self._apply_fortified_filter(page)

                    # Collect URLs from all pages
                    all_urls = await self._collect_all_pages(page, year, search_url)

                    # Filter by product types if specified
                    if product_types:
                        urls = [u for u in all_urls if u.product_type_hint in product_types]
                    else:
                        urls = all_urls

                    logger.info(
                        f"DWWA Collector found {len(urls)} URLs for year {year}"
                        + (f" (filtered to {product_types})" if product_types else "")
                    )

                finally:
                    await browser.close()

        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Error collecting DWWA URLs for year {year}: {e}")
            raise

        return urls

    async def _apply_fortified_filter(self, page) -> None:
        """
        Apply Fortified category filter on DWWA search page.

        Args:
            page: Playwright page object
        """
        try:
            # Look for filter/facet controls
            # DWWA typically has category/style filters
            # Try multiple selectors for robustness

            # Wait for filters to be visible
            await page.wait_for_timeout(2000)

            # Try to find and click Fortified filter
            filter_selectors = [
                # Direct text match
                "text=Fortified",
                # Checkbox/radio with fortified label
                "[data-category='fortified']",
                "input[value='fortified']",
                "label:has-text('Fortified')",
                # Category filter dropdown
                ".category-filter >> text=Fortified",
                ".wine-style >> text=Fortified",
                # Data attribute patterns
                "[data-wine-style='fortified']",
                "[data-style='fortified']",
            ]

            filter_applied = False
            for selector in filter_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        await page.wait_for_timeout(1000)
                        filter_applied = True
                        logger.info(f"Applied Fortified filter using selector: {selector}")
                        break
                except Exception:
                    continue

            if not filter_applied:
                # Try alternative: use search/filter input
                try:
                    search_input = await page.query_selector(
                        "input[type='search'], input[placeholder*='search'], .search-input"
                    )
                    if search_input:
                        await search_input.fill("fortified")
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(2000)
                        filter_applied = True
                        logger.info("Applied Fortified filter via search input")
                except Exception:
                    pass

            if not filter_applied:
                logger.warning("Could not apply Fortified filter - collecting all wines")

            # Wait for results to load
            await page.wait_for_load_state("networkidle")

        except Exception as e:
            logger.warning(f"Error applying Fortified filter: {e}")

    async def _collect_all_pages(
        self, page, year: int, listing_url: str
    ) -> List[AwardDetailURL]:
        """
        Collect URLs from all pages (handles pagination/infinite scroll).

        Args:
            page: Playwright page object
            year: Competition year
            listing_url: URL of the listing page

        Returns:
            List of AwardDetailURL objects
        """
        all_urls = []
        seen_urls = set()
        page_num = 0
        max_pages = 50  # Safety limit

        while page_num < max_pages:
            # Extract URLs from current page
            page_urls = await self._extract_urls_from_page(page, year, listing_url)

            # Check for new URLs
            new_urls = [u for u in page_urls if u.detail_url not in seen_urls]
            if not new_urls:
                logger.info(f"No new URLs on page {page_num + 1}, stopping pagination")
                break

            for url in new_urls:
                seen_urls.add(url.detail_url)
            all_urls.extend(new_urls)

            logger.info(f"Collected {len(new_urls)} URLs from page {page_num + 1}")

            # Try to go to next page
            has_next = await self._navigate_to_next_page(page)
            if not has_next:
                break

            page_num += 1
            await page.wait_for_timeout(1500)

        return all_urls

    async def _extract_urls_from_page(
        self, page, year: int, listing_url: str
    ) -> List[AwardDetailURL]:
        """
        Extract detail URLs from current page.

        Args:
            page: Playwright page object
            year: Competition year
            listing_url: URL of the listing page

        Returns:
            List of AwardDetailURL objects
        """
        urls = []

        # Find wine cards/items on the page
        card_selectors = [
            ".wine-card",
            ".result-card",
            ".wine-item",
            ".search-result",
            "[data-wine-id]",
            ".wine-result",
            "article.wine",
            ".wines-list-item",
        ]

        cards = []
        for selector in card_selectors:
            cards = await page.query_selector_all(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                break

        if not cards:
            # Fallback: try to find any links to wine detail pages
            links = await page.query_selector_all(f"a[href*='/wines/'], a[href*='/DWWA/{year}/']")
            for link in links:
                href = await link.get_attribute("href")
                if href and "/wines/" in href:
                    # Build full URL
                    if not href.startswith("http"):
                        href = f"{self.BASE_URL}{href}"

                    # Get surrounding text for hints
                    text_content = await link.text_content() or ""
                    parent = await link.query_selector("xpath=..")
                    if parent:
                        parent_text = await parent.text_content() or ""
                        text_content = parent_text

                    medal = self._extract_medal_from_text(text_content)
                    style = self._detect_port_style(text_content)
                    product_type = "port_wine" if style else "fortified"

                    urls.append(AwardDetailURL(
                        detail_url=href,
                        listing_url=listing_url,
                        medal_hint=medal,
                        score_hint=None,
                        competition=self.COMPETITION_NAME,
                        year=year,
                        product_type_hint=product_type,
                    ))

            return urls

        # Process each card
        for card in cards:
            try:
                # Find detail link within card
                link = await card.query_selector("a[href*='/wines/'], a[href*='/DWWA/']")
                if not link:
                    link = await card.query_selector("a")
                if not link:
                    continue

                href = await link.get_attribute("href")
                if not href or "/wines/" not in href:
                    continue

                # Build full URL
                if not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Get card text for hints
                card_text = await card.text_content() or ""

                # Extract medal hint
                medal = self._extract_medal_from_text(card_text)

                # Extract score if visible
                score = self._extract_score_from_text(card_text)

                # Detect port style
                style = self._detect_port_style(card_text)

                # Determine product type
                product_type = "port_wine" if style else "fortified"

                urls.append(AwardDetailURL(
                    detail_url=href,
                    listing_url=listing_url,
                    medal_hint=medal,
                    score_hint=score,
                    competition=self.COMPETITION_NAME,
                    year=year,
                    product_type_hint=product_type,
                ))

            except Exception as e:
                logger.debug(f"Error extracting URL from card: {e}")
                continue

        return urls

    async def _navigate_to_next_page(self, page) -> bool:
        """
        Navigate to next page of results.

        Handles both traditional pagination and infinite scroll.

        Args:
            page: Playwright page object

        Returns:
            True if navigated to next page, False if no more pages
        """
        # Try pagination first
        next_selectors = [
            "a.next",
            "button.next",
            "[aria-label='Next page']",
            ".pagination-next",
            "a:has-text('Next')",
            "button:has-text('Next')",
            ".pager-next a",
            "a[rel='next']",
        ]

        for selector in next_selectors:
            try:
                next_button = await page.query_selector(selector)
                if next_button:
                    is_disabled = await next_button.get_attribute("disabled")
                    class_name = await next_button.get_attribute("class") or ""

                    if is_disabled or "disabled" in class_name:
                        return False

                    await next_button.click()
                    await page.wait_for_load_state("networkidle")
                    return True
            except Exception:
                continue

        # Try infinite scroll
        try:
            # Get current scroll height
            prev_height = await page.evaluate("document.body.scrollHeight")

            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            # Check if new content loaded
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height > prev_height:
                return True
        except Exception:
            pass

        # Try "Load More" button
        load_more_selectors = [
            "button:has-text('Load More')",
            "button:has-text('Show More')",
            "a:has-text('Load More')",
            ".load-more",
            ".show-more",
        ]

        for selector in load_more_selectors:
            try:
                load_more = await page.query_selector(selector)
                if load_more:
                    await load_more.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue

        return False

    def _detect_port_style(self, text: str) -> Optional[str]:
        """
        Detect port wine style from text.

        Args:
            text: Text to analyze (card content, wine name, etc.)

        Returns:
            Port style string or None if not detected
        """
        if not text:
            return None

        # Check patterns in order (more specific first)
        for style, pattern in self.PORT_STYLE_PATTERNS:
            if pattern.search(text):
                return style

        return None

    def _extract_medal_from_text(self, text: str) -> str:
        """
        Extract medal type from text.

        Args:
            text: Text to analyze

        Returns:
            Medal type string (Gold, Silver, Bronze, Platinum, or Unknown)
        """
        if not text:
            return "Unknown"

        # Check patterns in order of precedence (Platinum first)
        for medal, pattern in self.MEDAL_PATTERNS.items():
            if pattern.search(text):
                return medal

        return "Unknown"

    def _extract_score_from_text(self, text: str) -> Optional[int]:
        """
        Extract numeric score from text.

        Args:
            text: Text to analyze

        Returns:
            Score as integer or None
        """
        if not text:
            return None

        # Look for patterns like "95 points", "Score: 92", etc.
        score_patterns = [
            r"(\d{2,3})\s*points",
            r"score[:\s]+(\d{2,3})",
            r"(\d{2,3})/100",
        ]

        for pattern in score_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score = int(match.group(1))
                if 0 <= score <= 100:
                    return score

        return None

    def _is_fortified_wine_producer(self, producer_name: str) -> bool:
        """
        Check if producer is known for fortified wines.

        Args:
            producer_name: Producer/winery name

        Returns:
            True if producer is known for fortified wines
        """
        if not producer_name:
            return False

        producer_lower = producer_name.lower().strip()

        # Check exact match
        if producer_lower in self.FORTIFIED_PRODUCERS:
            return True

        # Check partial match (producer name contains known producer)
        for known_producer in self.FORTIFIED_PRODUCERS:
            if known_producer in producer_lower or producer_lower in known_producer:
                return True

        return False
