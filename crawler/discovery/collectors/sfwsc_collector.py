"""
SFWSC URL Collector - Collects product entries from San Francisco World Spirits Competition.

This collector extracts product entries from The Tasting Alliance results pages.
The competition data is embedded as JSON in the page HTML (GlobalsObj.CMS_JSON).

Target URL: https://thetastingalliance.com/results/?event=sfwsc

The collector:
1. Fetches the results page from The Tasting Alliance
2. Extracts embedded JSON data (GlobalsObj.CMS_JSON)
3. Parses product entries from the JSON
4. Filters for whiskey categories
5. Extracts medal hints from award data
6. Handles pagination via multiple page loads
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from .base_collector import BaseCollector, AwardDetailURL

logger = logging.getLogger(__name__)


class SFWSCCollector(BaseCollector):
    """
    Collects product entries from San Francisco World Spirits Competition (SFWSC).

    The Tasting Alliance hosts SFWSC results with data embedded as JSON.
    This collector parses that JSON to extract whiskey award winners.

    Note: SFWSC does not provide individual detail page URLs for products.
    The detail_url field contains the listing URL with product ID as anchor.
    """

    COMPETITION_NAME = "SFWSC"
    BASE_URL = "https://thetastingalliance.com"

    # Known SFWSC event IDs by year (discovered from page analysis)
    # New years may need to be added as they become available
    SFWSC_EVENT_IDS = {
        2025: [6370],
        2024: [145073],
        2023: [6369],  # May need verification
        2022: [6368],  # May need verification
    }

    # Whiskey category patterns for detection
    WHISKEY_PATTERNS = [
        re.compile(r"\bbourbon\b", re.IGNORECASE),
        re.compile(r"\brye\s+whisk[e]?y\b", re.IGNORECASE),
        re.compile(r"\brye\b", re.IGNORECASE),
        re.compile(r"\bwhisk[e]?y\b", re.IGNORECASE),
        re.compile(r"\bscotch\b", re.IGNORECASE),
        re.compile(r"\bsingle\s+malt\b", re.IGNORECASE),
        re.compile(r"\bblended\s+(scotch|malt)\b", re.IGNORECASE),
        re.compile(r"\btennessee\b", re.IGNORECASE),
        re.compile(r"\birish\b", re.IGNORECASE),
        re.compile(r"\bcanadian\b", re.IGNORECASE),
        re.compile(r"\bjapanese\b", re.IGNORECASE),
        re.compile(r"\bworld\s+whisk[e]?y\b", re.IGNORECASE),
    ]

    # Non-whiskey spirit patterns
    NON_WHISKEY_PATTERNS = {
        "gin": re.compile(r"\bgin\b", re.IGNORECASE),
        "vodka": re.compile(r"\bvodka\b", re.IGNORECASE),
        "rum": re.compile(r"\brum\b", re.IGNORECASE),
        "tequila": re.compile(r"\btequila\b", re.IGNORECASE),
        "mezcal": re.compile(r"\bmezcal\b", re.IGNORECASE),
        "brandy": re.compile(r"\bbrandy\b|\bcognac\b|\barmagnac\b", re.IGNORECASE),
        "liqueur": re.compile(r"\bliqueur\b|\bliquor\b", re.IGNORECASE),
    }

    # Medal code mapping
    MEDAL_CODES = {
        "GG": "Double Gold",
        "G": "Gold",
        "S": "Silver",
        "B": "Bronze",
        "best-of-class": "Best of Class",
        "best-in-show": "Best in Show",
        "platinum": "Platinum",
    }

    def collect(
        self, year: int, product_types: Optional[List[str]] = None
    ) -> List[AwardDetailURL]:
        """
        Collect product entries from SFWSC for given year.

        Args:
            year: Competition year
            product_types: Filter by product types (e.g., ["whiskey"])
                          If None, collects all spirits

        Returns:
            List of AwardDetailURL objects with product entries
        """
        urls = []

        # Get listing URL for the year
        listing_url = self._get_listing_url(year)

        try:
            # Fetch and parse the page
            html = self._fetch_page(listing_url)

            # Extract JSON data from page
            json_data = self._extract_json_from_page(html)

            if not json_data:
                logger.warning(f"No JSON data found in SFWSC page for year {year}")
                return urls

            # Parse products from JSON
            all_urls = self._parse_products(json_data, listing_url, year)

            # Filter by product types if specified
            if product_types:
                urls = [u for u in all_urls if u.product_type_hint in product_types]
            else:
                urls = all_urls

            logger.info(
                f"SFWSC Collector found {len(urls)} products for year {year}"
                + (f" (filtered to {product_types})" if product_types else "")
            )

        except Exception as e:
            logger.error(f"Error collecting SFWSC data for year {year}: {e}")
            raise

        return urls

    def _get_listing_url(self, year: int) -> str:
        """
        Build the listing URL for a specific year.

        Args:
            year: Competition year

        Returns:
            URL string for the results page
        """
        # The Tasting Alliance uses event query param
        return f"{self.BASE_URL}/results/?event=sfwsc"

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        response.raise_for_status()
        return response.text

    def _extract_json_from_page(self, html: str) -> Optional[Dict]:
        """
        Extract the CMS_JSON object from the page HTML.

        The Tasting Alliance embeds product data as:
        GlobalsObj.CMS_JSON = {...}

        Args:
            html: Page HTML content

        Returns:
            Parsed JSON dictionary or None
        """
        # Try to find the script containing CMS_JSON using BeautifulSoup first
        soup = BeautifulSoup(html, "lxml")

        for script in soup.find_all("script"):
            script_text = script.string or ""
            if "GlobalsObj.CMS_JSON" not in script_text:
                continue

            # Find the start of the JSON object
            cms_json_start = script_text.find("GlobalsObj.CMS_JSON")
            if cms_json_start == -1:
                continue

            # Find the equals sign
            equals_pos = script_text.find("=", cms_json_start)
            if equals_pos == -1:
                continue

            # Find the start of the JSON object (first '{' after '=')
            json_start = script_text.find("{", equals_pos)
            if json_start == -1:
                continue

            # Use brace counting to find the end of the JSON object
            json_str = self._extract_balanced_json(script_text[json_start:])
            if json_str:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON parse attempt failed: {e}")
                    continue

        # Fallback: try regex pattern
        pattern = r"GlobalsObj\.CMS_JSON\s*=\s*(\{)"
        match = re.search(pattern, html)
        if match:
            start_idx = match.start(1)
            json_str = self._extract_balanced_json(html[start_idx:])
            if json_str:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse CMS_JSON: {e}")

        return None

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """
        Extract a balanced JSON object from text starting with '{'.

        Args:
            text: Text starting with '{'

        Returns:
            Balanced JSON string or None
        """
        if not text or text[0] != "{":
            return None

        brace_count = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[: i + 1]

        return None

    def _parse_products(
        self, json_data: Dict, listing_url: str, year: int
    ) -> List[AwardDetailURL]:
        """
        Parse product entries from the JSON data.

        Args:
            json_data: Parsed CMS_JSON dictionary
            listing_url: URL of the listing page
            year: Competition year

        Returns:
            List of AwardDetailURL objects
        """
        urls = []

        # Navigate to products: page.content.modules[*].results.items
        try:
            page_data = json_data.get("page", {})
            content = page_data.get("content", {})
            modules = content.get("modules", [])

            for module in modules:
                if module.get("module") == "bottles-list":
                    results = module.get("results", {})
                    items = results.get("items", [])

                    # Get event IDs for the target year
                    target_event_ids = self._get_event_ids_for_year(year)

                    for item in items:
                        # Filter by event ID (year) if we have known IDs
                        item_event_id = item.get("event_id")
                        award_text = item.get("award", "")

                        # Check if this item is from the target year
                        year_match = False
                        if target_event_ids and item_event_id:
                            year_match = item_event_id in target_event_ids
                        elif str(year) in award_text:
                            year_match = True
                        elif not target_event_ids:
                            # If we don't have event IDs, include all
                            year_match = True

                        if not year_match:
                            continue

                        # Extract product data
                        product_id = item.get("id", "")
                        title = item.get("title", "")
                        category = item.get("class", "")
                        award = item.get("award", "")
                        award_code = item.get("award_code", "")
                        region = item.get("region", "")
                        country = item.get("country", "")

                        # Detect product type
                        product_type = self._detect_product_type(category)

                        # Extract medal hint
                        medal = self._extract_medal_from_award(award, award_code)

                        # Build detail URL (listing URL with product anchor)
                        detail_url = f"{listing_url}#product-{product_id}"

                        urls.append(
                            AwardDetailURL(
                                detail_url=detail_url,
                                listing_url=listing_url,
                                medal_hint=medal,
                                score_hint=None,  # SFWSC doesn't publish scores
                                competition=self.COMPETITION_NAME,
                                year=year,
                                product_type_hint=product_type,
                            )
                        )

        except (KeyError, TypeError) as e:
            logger.warning(f"Error parsing SFWSC JSON structure: {e}")

        return urls

    def _get_event_ids_for_year(self, year: int) -> List[int]:
        """
        Get SFWSC event IDs for a specific year.

        Args:
            year: Competition year

        Returns:
            List of event IDs for that year
        """
        return self.SFWSC_EVENT_IDS.get(year, [])

    def _detect_product_type(self, category: str) -> str:
        """
        Detect product type from category class.

        Args:
            category: Product category (e.g., "Straight Bourbon", "London Dry Gin")

        Returns:
            Product type string (e.g., "whiskey", "gin", "vodka")
        """
        if not category:
            return "unknown"

        # Check for whiskey first
        for pattern in self.WHISKEY_PATTERNS:
            if pattern.search(category):
                return "whiskey"

        # Check for other spirits
        for spirit_type, pattern in self.NON_WHISKEY_PATTERNS.items():
            if pattern.search(category):
                return spirit_type

        return "unknown"

    def _extract_medal_from_award(self, award: str, award_code: str) -> str:
        """
        Extract medal type from award data.

        Args:
            award: Award description (e.g., "2024 SFWSC Gold")
            award_code: Award code (e.g., "G", "GG", "S", "B")

        Returns:
            Medal type string (e.g., "Gold", "Double Gold")
        """
        # First try award code
        if award_code in self.MEDAL_CODES:
            return self.MEDAL_CODES[award_code]

        # Fall back to parsing award text
        award_lower = award.lower()

        if "double gold" in award_lower:
            return "Double Gold"
        elif "best in show" in award_lower:
            return "Best in Show"
        elif "best of class" in award_lower:
            return "Best of Class"
        elif "platinum" in award_lower:
            return "Platinum"
        elif "gold" in award_lower:
            return "Gold"
        elif "silver" in award_lower:
            return "Silver"
        elif "bronze" in award_lower:
            return "Bronze"

        return "Unknown"
