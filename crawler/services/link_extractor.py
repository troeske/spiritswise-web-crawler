"""
Link Extractor Service.

Extracts and classifies links from HTML content for URL discovery.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLink:
    """Represents an extracted link with classification metadata."""

    url: str
    text: str = ""
    link_type: str = "unknown"
    is_internal: bool = True
    is_product: bool = False
    is_category: bool = False
    is_pagination: bool = False
    depth: int = 0


class LinkExtractor:
    """
    Extracts and classifies links from HTML content.

    Identifies product links, category links, pagination, and other
    relevant URLs for crawling.
    """

    # Pagination patterns
    PAGINATION_PATTERNS = [
        r"[?&]page=\d+",
        r"/page/\d+",
        r"/p/\d+",
        r"[?&]offset=\d+",
        r"[?&]start=\d+",
    ]

    # Category patterns
    CATEGORY_PATTERNS = [
        r"/category/",
        r"/categories/",
        r"/collection/",
        r"/collections/",
        r"/browse/",
        r"/shop/",
        r"/products/?$",
    ]

    # Related product patterns
    RELATED_PATTERNS = [
        r"related",
        r"similar",
        r"you-may-also",
        r"also-like",
        r"customers-also",
    ]

    # URLs to skip
    SKIP_PATTERNS = [
        r"\.(jpg|jpeg|png|gif|svg|webp|ico|css|js|pdf|zip|exe)$",
        r"^mailto:",
        r"^tel:",
        r"^javascript:",
        r"^#",
        r"/cart",
        r"/checkout",
        r"/login",
        r"/signup",
        r"/account",
        r"/wishlist",
        r"/compare",
    ]

    def __init__(self):
        """Initialize the link extractor."""
        self._pagination_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.PAGINATION_PATTERNS
        ]
        self._category_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.CATEGORY_PATTERNS
        ]
        self._related_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.RELATED_PATTERNS
        ]
        self._skip_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.SKIP_PATTERNS
        ]

    def extract_links(
        self,
        html: str,
        base_url: str,
        product_patterns: Optional[List[str]] = None,
    ) -> List[ExtractedLink]:
        """
        Extract and classify links from HTML content.

        Args:
            html: Raw HTML content
            base_url: Base URL for resolving relative links
            product_patterns: Optional list of regex patterns for product URLs

        Returns:
            List of ExtractedLink objects
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc

        # Compile product patterns
        product_regexes = []
        if product_patterns:
            product_regexes = [
                re.compile(p, re.IGNORECASE) for p in product_patterns
            ]

        links: List[ExtractedLink] = []
        seen_urls: Set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()

            if not href:
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)

            # Normalize URL
            parsed = urlparse(full_url)
            normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized_url += f"?{parsed.query}"

            # Skip duplicates
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            # Skip unwanted URLs
            if self._should_skip(normalized_url):
                continue

            # Extract link text
            link_text = anchor.get_text(strip=True)[:200]

            # Determine if internal
            link_domain = parsed.netloc
            is_internal = link_domain == base_domain

            # Classify the link
            link = self._classify_link(
                url=normalized_url,
                text=link_text,
                is_internal=is_internal,
                product_regexes=product_regexes,
            )

            links.append(link)

        logger.debug(f"Extracted {len(links)} links from {base_url}")
        return links

    def _should_skip(self, url: str) -> bool:
        """Check if URL should be skipped."""
        for regex in self._skip_regexes:
            if regex.search(url):
                return True
        return False

    def _classify_link(
        self,
        url: str,
        text: str,
        is_internal: bool,
        product_regexes: List[re.Pattern],
    ) -> ExtractedLink:
        """Classify a link based on URL patterns."""
        link_type = "unknown"
        is_product = False
        is_category = False
        is_pagination = False

        # Check if it's a product URL
        for regex in product_regexes:
            if regex.search(url):
                link_type = "product"
                is_product = True
                break

        # Check if it's a category page
        if not is_product:
            for regex in self._category_regexes:
                if regex.search(url):
                    link_type = "category"
                    is_category = True
                    break

        # Check if it's pagination
        for regex in self._pagination_regexes:
            if regex.search(url):
                link_type = "pagination"
                is_pagination = True
                break

        # Check if it's a related product link
        if not link_type or link_type == "unknown":
            for regex in self._related_regexes:
                if regex.search(url) or regex.search(text.lower()):
                    link_type = "related"
                    is_product = True
                    break

        return ExtractedLink(
            url=url,
            text=text,
            link_type=link_type,
            is_internal=is_internal,
            is_product=is_product,
            is_category=is_category,
            is_pagination=is_pagination,
        )


def get_link_extractor() -> LinkExtractor:
    """Factory function to get LinkExtractor instance."""
    return LinkExtractor()
