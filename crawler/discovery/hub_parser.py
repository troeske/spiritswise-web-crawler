"""
Hub Page Parser - Extracts brand listings from retailer hub pages.

Parses brand/producer listings from retailer sites like:
- thewhiskyexchange.com/brands
- masterofmalt.com/brands
- whiskybase.com/distilleries
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class BrandInfo:
    """Information about a discovered brand/producer."""

    name: str
    hub_url: str  # URL on the hub site (e.g., /brands/glenfiddich)
    external_url: Optional[str] = None  # External official site if found
    hub_source: str = ""  # Which hub site this was discovered from

    def __post_init__(self):
        """Clean up brand name."""
        self.name = self.name.strip()


@dataclass
class HubConfig:
    """Configuration for parsing a specific hub site."""

    domain: str
    brand_selectors: List[str] = field(default_factory=list)
    name_selectors: List[str] = field(default_factory=list)
    pagination_selectors: List[str] = field(default_factory=list)
    external_link_patterns: List[str] = field(default_factory=list)


# Pre-configured hub site parsers
HUB_CONFIGS = {
    "thewhiskyexchange.com": HubConfig(
        domain="thewhiskyexchange.com",
        brand_selectors=[
            ".brand-item",
            ".brand-list a",
            "a[href*='/brands/']",
            ".az-list a",
        ],
        name_selectors=[
            ".brand-name",
            ".name",
            "span",
            "h3",
        ],
        pagination_selectors=[
            ".pagination a",
            ".page-numbers a",
            "a.next",
        ],
        external_link_patterns=[
            r"^https?://(?!.*thewhiskyexchange\.com)",
        ],
    ),
    "masterofmalt.com": HubConfig(
        domain="masterofmalt.com",
        brand_selectors=[
            ".brand-item",
            ".distillery-item",
            "a[href*='/distilleries/']",
            "a[href*='/brands/']",
        ],
        name_selectors=[
            ".brand-name",
            ".distillery-name",
            ".title",
            "h3",
            "span",
        ],
        pagination_selectors=[
            ".pagination a",
            ".paging a",
            "a[rel='next']",
        ],
        external_link_patterns=[
            r"^https?://(?!.*masterofmalt\.com)",
        ],
    ),
    "whiskybase.com": HubConfig(
        domain="whiskybase.com",
        brand_selectors=[
            ".distillery-list a",
            "a[href*='/distilleries/']",
            "a[href*='/distillery/']",
            ".brand-row a",
        ],
        name_selectors=[
            ".distillery-name",
            ".name",
            "h3",
            "span",
        ],
        pagination_selectors=[
            ".pagination a",
            ".pager a",
        ],
        external_link_patterns=[
            r"^https?://(?!.*whiskybase\.com)",
        ],
    ),
}


class HubPageParser:
    """
    Parser for extracting brand listings from retailer hub pages.

    Supports multiple hub sites with configurable selectors.
    """

    def __init__(self, custom_configs: Optional[dict] = None):
        """
        Initialize hub parser.

        Args:
            custom_configs: Additional hub configurations to merge
        """
        self.configs = {**HUB_CONFIGS}
        if custom_configs:
            self.configs.update(custom_configs)

    def _get_config_for_url(self, url: str) -> Optional[HubConfig]:
        """Get the appropriate config for a hub URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")

        for config_domain, config in self.configs.items():
            if config_domain in domain:
                return config

        # Return generic config if no match
        return HubConfig(
            domain=domain,
            brand_selectors=[
                "a[href*='/brands/']",
                "a[href*='/distillery/']",
                ".brand-item",
                ".brand-list a",
            ],
            name_selectors=[".name", "span", "h3", "h4"],
            pagination_selectors=[".pagination a", "a.next"],
            external_link_patterns=[r"^https?://"],
        )

    def parse_brands(
        self,
        html: str,
        hub_url: str,
    ) -> List[BrandInfo]:
        """
        Parse brand listings from hub page HTML.

        Args:
            html: Raw HTML content of hub page
            hub_url: URL of the hub page (for resolving relative links)

        Returns:
            List of BrandInfo objects for discovered brands
        """
        config = self._get_config_for_url(hub_url)
        soup = BeautifulSoup(html, "lxml")
        brands = []
        seen_names = set()

        # Parse the hub domain for source tracking
        parsed_hub = urlparse(hub_url)
        hub_domain = parsed_hub.netloc.replace("www.", "")

        # Try each brand selector
        for selector in config.brand_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    brand = self._extract_brand_from_element(
                        element=element,
                        config=config,
                        hub_url=hub_url,
                        hub_domain=hub_domain,
                    )
                    if brand and brand.name.lower() not in seen_names:
                        seen_names.add(brand.name.lower())
                        brands.append(brand)
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue

        logger.info(f"Parsed {len(brands)} brands from {hub_url}")
        return brands

    def _extract_brand_from_element(
        self,
        element,
        config: HubConfig,
        hub_url: str,
        hub_domain: str,
    ) -> Optional[BrandInfo]:
        """Extract brand info from a BeautifulSoup element."""
        # Get the link URL
        href = element.get("href", "")
        if not href:
            return None

        # Resolve relative URLs
        full_url = urljoin(hub_url, href)

        # Check if this is an external link
        external_url = None
        if self._is_external_link(full_url, config):
            external_url = full_url

        # Extract brand name
        name = self._extract_name(element, config)
        if not name:
            return None

        # Skip generic/navigation links
        if self._is_generic_text(name):
            return None

        return BrandInfo(
            name=name,
            hub_url=full_url if not external_url else hub_url,
            external_url=external_url,
            hub_source=hub_domain,
        )

    def _extract_name(self, element, config: HubConfig) -> Optional[str]:
        """Extract brand name from element."""
        # Try name selectors first
        for selector in config.name_selectors:
            try:
                name_elem = element.select_one(selector)
                if name_elem and name_elem.get_text(strip=True):
                    return name_elem.get_text(strip=True)
            except Exception:
                continue

        # Fall back to element text
        text = element.get_text(strip=True)
        if text and len(text) < 100:  # Reasonable name length
            return text

        # Try title attribute
        title = element.get("title", "")
        if title:
            return title.strip()

        return None

    def _is_external_link(self, url: str, config: HubConfig) -> bool:
        """Check if URL is an external link (not on the hub site)."""
        for pattern in config.external_link_patterns:
            if re.match(pattern, url):
                # Make sure it's not just a different path on the hub
                parsed = urlparse(url)
                if config.domain not in parsed.netloc:
                    return True
        return False

    def _is_generic_text(self, text: str) -> bool:
        """Check if text is generic navigation text to skip."""
        generic_terms = [
            "next",
            "previous",
            "more",
            "view all",
            "see all",
            "load more",
            "show more",
            "back",
            "home",
            "page",
            "menu",
            "search",
            "filter",
            "sort",
        ]
        text_lower = text.lower().strip()
        return text_lower in generic_terms or len(text_lower) < 2

    def extract_pagination_links(
        self,
        html: str,
        hub_url: str,
    ) -> List[str]:
        """
        Extract pagination links from hub page.

        Args:
            html: Raw HTML content
            hub_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs for pagination pages
        """
        config = self._get_config_for_url(hub_url)
        soup = BeautifulSoup(html, "lxml")
        pagination_links = []
        seen_urls = set()

        for selector in config.pagination_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get("href", "")
                    if href:
                        full_url = urljoin(hub_url, href)
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            pagination_links.append(full_url)
            except Exception as e:
                logger.debug(f"Pagination selector {selector} failed: {e}")
                continue

        return pagination_links
