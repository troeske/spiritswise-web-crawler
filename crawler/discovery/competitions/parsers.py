"""
Competition Result Parsers - Extract award data from competition result pages.

Supports major spirits competitions:
- IWSC (International Wine & Spirit Competition): iwsc.net/results/search/{year}
- SFWSC (San Francisco World Spirits Competition): thetastingalliance.com/results/
- World Whiskies Awards: worldwhiskiesawards.com/winners
- Decanter World Wine Awards: awards.decanter.com

Each parser extracts: product name, medal/award, year, producer, category
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class CompetitionResult:
    """A single competition result/award."""

    product_name: str
    competition: str
    year: int
    medal: str  # e.g., "Gold", "Silver", "Bronze", "Best in Class"
    producer: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    award_category: Optional[str] = None  # e.g., "World's Best Single Malt"
    score: Optional[float] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "product_name": self.product_name,
            "competition": self.competition,
            "year": self.year,
            "medal": self.medal,
            "producer": self.producer,
            "category": self.category,
            "country": self.country,
            "award_category": self.award_category,
            "score": self.score,
            **self.additional_info,
        }


class BaseCompetitionParser(ABC):
    """Base class for competition result parsers."""

    COMPETITION_NAME: str = "Unknown"
    BASE_URL: str = ""

    def __init__(self):
        """Initialize the parser."""
        pass

    @abstractmethod
    def parse(self, html: str, year: int) -> List[Dict[str, Any]]:
        """
        Parse competition results from HTML.

        Args:
            html: Raw HTML content of results page
            year: Year of the competition

        Returns:
            List of dictionaries with competition result data
        """
        pass

    def _clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        # Remove extra whitespace, newlines
        text = re.sub(r"\s+", " ", text.strip())
        return text

    def _extract_text(self, element, selector: str) -> str:
        """Extract text from element using selector."""
        if element is None:
            return ""
        found = element.select_one(selector)
        return self._clean_text(found.get_text()) if found else ""

    def _normalize_medal(self, medal_text: str) -> str:
        """Normalize medal names to standard format."""
        medal_lower = medal_text.lower().strip()

        medal_mapping = {
            "gold": "Gold",
            "gold medal": "Gold",
            "gold outstanding": "Gold Outstanding",
            "silver": "Silver",
            "silver medal": "Silver",
            "bronze": "Bronze",
            "bronze medal": "Bronze",
            "double gold": "Double Gold",
            "best in class": "Best in Class",
            "best in show": "Best in Show",
            "trophy": "Trophy",
            "platinum": "Platinum",
        }

        for key, value in medal_mapping.items():
            if key in medal_lower:
                return value

        # Return original if no mapping found
        return medal_text.strip().title()


class IWSCParser(BaseCompetitionParser):
    """
    Parser for IWSC (International Wine & Spirit Competition) results.

    Target URL: iwsc.net/results/search/{year}
    """

    COMPETITION_NAME = "IWSC"
    BASE_URL = "https://iwsc.net/results/search/"

    def parse(self, html: str, year: int) -> List[Dict[str, Any]]:
        """Parse IWSC results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Primary selector: .c-card--listing (IWSC site structure as of Dec 2025)
        cards = soup.select(".c-card--listing")

        if cards:
            logger.info("Found %d IWSC cards with .c-card--listing" % len(cards))
            for card in cards:
                title_elem = card.select_one(".c-card--listing__title")
                if not title_elem:
                    continue
                # Replace <br> tags with space to avoid concatenation issues
                for br in title_elem.find_all("br"):
                    br.replace_with(" ")
                product_name = self._clean_text(title_elem.get_text())
                if not product_name or len(product_name) < 3:
                    continue

                meta_elem = card.select_one(".c-card--listing__meta")
                location = ""
                country = None
                if meta_elem:
                    location = self._clean_text(meta_elem.get_text())
                    for c in ["Scotland", "Ireland", "USA", "Japan", "Taiwan", "Belgium",
                              "France", "Germany", "Poland", "Australia", "Canada", "Mexico",
                              "Puerto Rico", "South Africa", "Netherlands", "India", "England"]:
                        if c.lower() in location.lower():
                            country = c
                            break

                # Extract medal info from awards wrapper image
                medal = "Award"
                score = None
                award_image_url = None
                
                awards_wrapper = card.select_one(".c-card--listing__awards-wrapper")
                if awards_wrapper:
                    award_img = awards_wrapper.select_one("img")
                    if award_img:
                        # Get image URL (try data-src first, then src)
                        img_src = award_img.get("data-src") or award_img.get("src") or ""
                        if img_src:
                            # Make absolute URL
                            if img_src.startswith("/"):
                                award_image_url = f"https://www.iwsc.net{img_src}"
                            else:
                                award_image_url = img_src
                            
                            # Extract medal type and score from URL
                            # URL pattern: iwsc2025-gold-95-medal or iwsc2025-silver-90-medal
                            medal_match = re.search(r"(gold|silver|bronze)-?(\d+)?-?medal", img_src.lower())
                            if medal_match:
                                medal = medal_match.group(1).capitalize()
                                if medal_match.group(2):
                                    score = int(medal_match.group(2))
                        
                        # Also check alt attribute for medal info
                        alt_text = award_img.get("alt", "").lower()
                        if not medal or medal == "Award":
                            if "gold" in alt_text:
                                medal = "Gold"
                            elif "silver" in alt_text:
                                medal = "Silver"
                            elif "bronze" in alt_text:
                                medal = "Bronze"
                
                # Build additional_info with all award details
                additional_info = {}
                if location:
                    additional_info["origin"] = location
                if score:
                    additional_info["score"] = score
                if award_image_url:
                    additional_info["award_image_url"] = award_image_url

                results.append(CompetitionResult(
                    product_name=product_name,
                    competition=self.COMPETITION_NAME,
                    year=year,
                    medal=medal,
                    score=score,
                    country=country,
                    additional_info=additional_info,
                ).to_dict())
        else:
            # Fallback to legacy selectors
            for selector in [".result-item", ".results-list .item", ".award-item"]:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        result = self._parse_iwsc_item(element, year)
                        if result:
                            results.append(result)
                    break
            if not results:
                results = self._parse_iwsc_fallback(soup, year)

        logger.info(f"IWSC parser found {len(results)} results for year {year}")
        return results

    def _parse_iwsc_item(self, element, year: int) -> Optional[Dict[str, Any]]:
        """Parse a single IWSC result item."""
        # Try various selectors for product name
        name_selectors = [
            ".product-name",
            ".name",
            "h3",
            "h4",
            ".title",
            "td.product",
        ]
        product_name = ""
        for selector in name_selectors:
            product_name = self._extract_text(element, selector)
            if product_name:
                break

        if not product_name:
            return None

        # Extract medal
        medal_selectors = [
            ".medal",
            ".award-level",
            ".medal-type",
            "td.medal",
            "[class*='gold']",
            "[class*='silver']",
            "[class*='bronze']",
        ]
        medal = ""
        for selector in medal_selectors:
            found = element.select_one(selector)
            if found:
                medal = self._normalize_medal(found.get_text())
                if not medal:
                    # Check class names
                    classes = found.get("class", [])
                    for cls in classes:
                        if "gold" in cls.lower():
                            medal = "Gold"
                        elif "silver" in cls.lower():
                            medal = "Silver"
                        elif "bronze" in cls.lower():
                            medal = "Bronze"
                if medal:
                    break

        if not medal:
            medal = "Award"  # Default if medal not found

        # Extract producer
        producer_selectors = [".producer", ".company", ".brand", "td.producer"]
        producer = ""
        for selector in producer_selectors:
            producer = self._extract_text(element, selector)
            if producer:
                break

        # Extract category
        category_selectors = [".category", ".type", "td.category"]
        category = ""
        for selector in category_selectors:
            category = self._extract_text(element, selector)
            if category:
                break

        return CompetitionResult(
            product_name=product_name,
            competition=self.COMPETITION_NAME,
            year=year,
            medal=medal,
            producer=producer or None,
            category=category or None,
        ).to_dict()

    def _parse_iwsc_fallback(self, soup: BeautifulSoup, year: int) -> List[Dict[str, Any]]:
        """Fallback parsing for IWSC when standard selectors don't work."""
        results = []

        # Look for table rows
        for row in soup.select("table tr"):
            cells = row.select("td")
            if len(cells) >= 2:
                product_name = self._clean_text(cells[0].get_text())
                if product_name and len(product_name) > 3:
                    medal = self._clean_text(cells[-1].get_text()) if cells else "Award"
                    results.append(
                        CompetitionResult(
                            product_name=product_name,
                            competition=self.COMPETITION_NAME,
                            year=year,
                            medal=self._normalize_medal(medal),
                        ).to_dict()
                    )

        return results


class SFWSCParser(BaseCompetitionParser):
    """
    Parser for SFWSC (San Francisco World Spirits Competition) results.

    Target URL: thetastingalliance.com/results/
    """

    COMPETITION_NAME = "SFWSC"
    BASE_URL = "https://thetastingalliance.com/results/"

    def parse(self, html: str, year: int) -> List[Dict[str, Any]]:
        """Parse SFWSC results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # SFWSC result selectors
        selectors = [
            ".result-entry",
            ".winner-item",
            ".medal-winner",
            "tr[data-medal]",
            ".results-table tr",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    result = self._parse_sfwsc_item(element, year)
                    if result:
                        results.append(result)
                break

        # Fallback parsing
        if not results:
            results = self._parse_sfwsc_fallback(soup, year)

        logger.info(f"SFWSC parser found {len(results)} results for year {year}")
        return results

    def _parse_sfwsc_item(self, element, year: int) -> Optional[Dict[str, Any]]:
        """Parse a single SFWSC result item."""
        # Extract product name
        name_selectors = [".product-name", ".spirit-name", ".entry-name", "td:first-child"]
        product_name = ""
        for selector in name_selectors:
            product_name = self._extract_text(element, selector)
            if product_name:
                break

        if not product_name:
            return None

        # Extract medal (SFWSC uses Double Gold, Gold, Silver, Bronze)
        medal_selectors = [
            ".medal",
            ".award",
            "[class*='double-gold']",
            "[class*='gold']",
        ]
        medal = ""
        for selector in medal_selectors:
            found = element.select_one(selector)
            if found:
                medal_text = found.get_text()
                classes = " ".join(found.get("class", []))

                if "double" in medal_text.lower() or "double" in classes.lower():
                    medal = "Double Gold"
                else:
                    medal = self._normalize_medal(medal_text)

                if medal:
                    break

        if not medal:
            medal = "Award"

        # Extract producer/brand
        producer_selectors = [".brand", ".producer", ".company"]
        producer = ""
        for selector in producer_selectors:
            producer = self._extract_text(element, selector)
            if producer:
                break

        # Extract country
        country_selectors = [".country", ".origin"]
        country = ""
        for selector in country_selectors:
            country = self._extract_text(element, selector)
            if country:
                break

        return CompetitionResult(
            product_name=product_name,
            competition=self.COMPETITION_NAME,
            year=year,
            medal=medal,
            producer=producer or None,
            country=country or None,
        ).to_dict()

    def _parse_sfwsc_fallback(self, soup: BeautifulSoup, year: int) -> List[Dict[str, Any]]:
        """Fallback parsing for SFWSC."""
        results = []

        # Look for any list items or cards that might contain results
        for item in soup.select("li, .card, article"):
            text = item.get_text(separator=" ", strip=True)
            # Look for medal keywords
            if any(medal in text.lower() for medal in ["gold", "silver", "bronze"]):
                # Try to extract product name (usually first line or heading)
                heading = item.select_one("h2, h3, h4, strong")
                if heading:
                    product_name = self._clean_text(heading.get_text())
                    if product_name and len(product_name) > 3:
                        medal = "Gold" if "gold" in text.lower() else (
                            "Silver" if "silver" in text.lower() else "Bronze"
                        )
                        if "double" in text.lower():
                            medal = "Double Gold"

                        results.append(
                            CompetitionResult(
                                product_name=product_name,
                                competition=self.COMPETITION_NAME,
                                year=year,
                                medal=medal,
                            ).to_dict()
                        )

        return results


class WorldWhiskiesAwardsParser(BaseCompetitionParser):
    """
    Parser for World Whiskies Awards results.

    Target URL: worldwhiskiesawards.com/winners
    """

    COMPETITION_NAME = "World Whiskies Awards"
    BASE_URL = "https://www.worldwhiskiesawards.com/winners"

    def parse(self, html: str, year: int) -> List[Dict[str, Any]]:
        """Parse World Whiskies Awards results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # WWA result selectors
        selectors = [
            ".winner-card",
            ".winner-item",
            ".award-winner",
            ".category-winner",
            "[data-winner]",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    result = self._parse_wwa_item(element, year)
                    if result:
                        results.append(result)
                break

        # Fallback parsing
        if not results:
            results = self._parse_wwa_fallback(soup, year)

        logger.info(f"WWA parser found {len(results)} results for year {year}")
        return results

    def _parse_wwa_item(self, element, year: int) -> Optional[Dict[str, Any]]:
        """Parse a single WWA result item."""
        # Extract award category (e.g., "World's Best Single Malt")
        award_selectors = [".award-title", ".category-name", "h4", ".award-category"]
        award_category = ""
        for selector in award_selectors:
            award_category = self._extract_text(element, selector)
            if award_category:
                break

        # Extract winner name (product)
        name_selectors = [".winner-name", ".product-name", ".whisky-name", "h3", ".name"]
        product_name = ""
        for selector in name_selectors:
            product_name = self._extract_text(element, selector)
            if product_name:
                break

        if not product_name:
            return None

        # Extract distillery/producer
        producer_selectors = [".distillery", ".producer", ".brand"]
        producer = ""
        for selector in producer_selectors:
            producer = self._extract_text(element, selector)
            if producer:
                break

        # Extract country
        country_selectors = [".country", ".origin", ".region"]
        country = ""
        for selector in country_selectors:
            country = self._extract_text(element, selector)
            if country:
                break

        # Determine medal from award category
        medal = "Winner"
        if award_category:
            if "world" in award_category.lower() and "best" in award_category.lower():
                medal = award_category  # Use full award as medal
            elif "best" in award_category.lower():
                medal = award_category

        return CompetitionResult(
            product_name=product_name,
            competition=self.COMPETITION_NAME,
            year=year,
            medal=medal,
            producer=producer or None,
            country=country or None,
            award_category=award_category or None,
        ).to_dict()

    def _parse_wwa_fallback(self, soup: BeautifulSoup, year: int) -> List[Dict[str, Any]]:
        """Fallback parsing for WWA."""
        results = []

        # Look for sections or articles
        for section in soup.select("section, article, .award-section"):
            # Find category heading
            heading = section.select_one("h2, h3, .section-title")
            category = self._clean_text(heading.get_text()) if heading else ""

            # Find winners in this section
            for winner in section.select("p, .winner, li"):
                text = self._clean_text(winner.get_text())
                if text and len(text) > 5 and text != category:
                    results.append(
                        CompetitionResult(
                            product_name=text,
                            competition=self.COMPETITION_NAME,
                            year=year,
                            medal="Winner",
                            award_category=category or None,
                        ).to_dict()
                    )

        return results


class DecanterWWAParser(BaseCompetitionParser):
    """
    Parser for Decanter World Wine Awards (for Port wines).

    Target URL: awards.decanter.com (filter by category)
    Note: Primarily for Port wine support (future use)
    """

    COMPETITION_NAME = "Decanter WWA"
    BASE_URL = "https://awards.decanter.com/"

    def parse(self, html: str, year: int, category_filter: str = "Port") -> List[Dict[str, Any]]:
        """
        Parse Decanter WWA results page.

        Args:
            html: Raw HTML content
            year: Competition year
            category_filter: Category to filter (default: "Port")
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Decanter result selectors
        selectors = [
            ".wine-item",
            ".result-card",
            ".award-entry",
            "tr.result",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    result = self._parse_decanter_item(element, year, category_filter)
                    if result:
                        results.append(result)
                break

        logger.info(f"Decanter WWA parser found {len(results)} results for year {year}")
        return results

    def _parse_decanter_item(
        self, element, year: int, category_filter: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single Decanter WWA result item."""
        # Check if item matches category filter
        category_selectors = [".category", ".wine-type", ".style"]
        category = ""
        for selector in category_selectors:
            category = self._extract_text(element, selector)
            if category:
                break

        # Filter by category if specified
        if category_filter and category:
            if category_filter.lower() not in category.lower():
                return None

        # Extract wine/product name
        name_selectors = [".wine-name", ".product-name", "h3", ".title"]
        product_name = ""
        for selector in name_selectors:
            product_name = self._extract_text(element, selector)
            if product_name:
                break

        if not product_name:
            return None

        # Extract medal
        medal_selectors = [".medal", ".award-level", "[class*='medal']"]
        medal = ""
        for selector in medal_selectors:
            found = element.select_one(selector)
            if found:
                medal = self._normalize_medal(found.get_text())
                if medal:
                    break

        if not medal:
            medal = "Award"

        # Extract producer
        producer_selectors = [".producer", ".winery", ".brand"]
        producer = ""
        for selector in producer_selectors:
            producer = self._extract_text(element, selector)
            if producer:
                break

        # Extract score (Decanter often includes scores)
        score = None
        score_elem = element.select_one(".score, .rating, .points")
        if score_elem:
            score_text = score_elem.get_text()
            score_match = re.search(r"(\d+(?:\.\d+)?)", score_text)
            if score_match:
                try:
                    score = float(score_match.group(1))
                except ValueError:
                    pass

        return CompetitionResult(
            product_name=product_name,
            competition=self.COMPETITION_NAME,
            year=year,
            medal=medal,
            producer=producer or None,
            category=category or None,
            score=score,
        ).to_dict()


# Parser registry for easy access
COMPETITION_PARSERS = {
    "iwsc": IWSCParser,
    "sfwsc": SFWSCParser,
    "wwa": WorldWhiskiesAwardsParser,
    "world_whiskies_awards": WorldWhiskiesAwardsParser,
    "decanter": DecanterWWAParser,
}


def get_parser(competition_name: str) -> Optional[BaseCompetitionParser]:
    """
    Get the appropriate parser for a competition.

    Args:
        competition_name: Name or key of the competition

    Returns:
        Parser instance or None if not found
    """
    parser_class = COMPETITION_PARSERS.get(competition_name.lower())
    if parser_class:
        return parser_class()
    return None
