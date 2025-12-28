"""
Sitemap Parser Service.

Parses standard sitemaps, sitemap indexes, and gzipped sitemaps.
Discovers sitemaps from robots.txt and supports URL filtering and prioritization.

Features:
- Parse sitemap.xml and sitemap index files
- Support for gzipped sitemaps (.xml.gz)
- Parse robots.txt for Sitemap: directives
- Filter URLs by product patterns
- Prioritize recently modified URLs
- Streaming parser for large sitemaps
- Timeout and error handling
"""

import gzip
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from io import BytesIO
from typing import List, Optional
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)


# XML namespaces for sitemaps
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapParseError(Exception):
    """Exception raised for sitemap parsing errors."""

    pass


@dataclass
class SitemapURL:
    """
    Represents a URL entry from a sitemap.

    Attributes:
        url: The URL location
        lastmod: Last modification date
        changefreq: Change frequency hint
        priority: URL priority (0.0 to 1.0)
        sitemap_source: The sitemap file this URL was parsed from
    """

    url: str
    sitemap_source: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None


@dataclass
class SitemapResult:
    """
    Result of parsing a sitemap.

    Attributes:
        urls: List of parsed SitemapURL objects
        is_index: Whether this is a sitemap index file
        child_sitemaps: List of child sitemap URLs (if index)
        total_urls: Total count of URLs parsed
        parse_errors: List of non-fatal parse errors encountered
    """

    urls: List[SitemapURL]
    is_index: bool
    child_sitemaps: List[str]
    total_urls: int
    parse_errors: List[str] = field(default_factory=list)


class SitemapParser:
    """
    Parser for XML sitemaps and sitemap indexes.

    Supports:
    - Standard sitemap.xml format
    - Sitemap index files
    - Gzipped sitemaps (.xml.gz)
    - Robots.txt sitemap discovery
    - URL filtering and prioritization
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_size_bytes: int = 50 * 1024 * 1024,  # 50MB
        user_agent: str = "SpiritswiseCrawler/1.0",
    ):
        """
        Initialize the sitemap parser.

        Args:
            timeout: HTTP request timeout in seconds
            max_size_bytes: Maximum sitemap size to download
            user_agent: User-Agent header for HTTP requests
        """
        self.timeout = timeout
        self.max_size_bytes = max_size_bytes
        self.user_agent = user_agent

    async def parse_sitemap(self, url: str) -> SitemapResult:
        """
        Parse a sitemap from URL.

        Automatically detects sitemap vs sitemap index and handles gzipped content.

        Args:
            url: URL of the sitemap to parse

        Returns:
            SitemapResult with parsed URLs or child sitemaps

        Raises:
            SitemapParseError: If the sitemap cannot be fetched or parsed
        """
        logger.info(f"Parsing sitemap: {url}")

        try:
            content = await self._fetch_sitemap_content(url)
        except TimeoutError as e:
            raise SitemapParseError(f"Timeout fetching sitemap: {e}")
        except ConnectionError as e:
            raise SitemapParseError(f"Connection failed: {e}")
        except Exception as e:
            raise SitemapParseError(f"Failed to fetch sitemap: {e}")

        # Decompress if gzipped
        if url.endswith(".gz") or self._is_gzipped(content):
            try:
                content = self._decompress_gzip(content)
            except Exception as e:
                raise SitemapParseError(f"Failed to decompress gzipped sitemap: {e}")

        # Ensure content is string
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        return self._parse_xml(content, url)

    async def parse_sitemap_index(self, url: str) -> List[str]:
        """
        Parse a sitemap index file and return child sitemap URLs.

        Args:
            url: URL of the sitemap index

        Returns:
            List of child sitemap URLs

        Raises:
            SitemapParseError: If the index cannot be fetched or parsed
        """
        result = await self.parse_sitemap(url)

        if not result.is_index:
            logger.warning(f"URL {url} is not a sitemap index")
            return []

        return result.child_sitemaps

    async def discover_sitemaps_from_robots(self, robots_url: str) -> List[str]:
        """
        Discover sitemap URLs from a robots.txt file.

        Parses Sitemap: directives from the robots.txt content.

        Args:
            robots_url: URL of the robots.txt file

        Returns:
            List of discovered sitemap URLs
        """
        logger.info(f"Discovering sitemaps from: {robots_url}")

        try:
            content = await self._fetch_robots_txt(robots_url)
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt: {e}")
            return []

        return self._extract_sitemap_urls_from_robots(content)

    def filter_urls_by_pattern(
        self, urls: List[SitemapURL], patterns: List[str]
    ) -> List[SitemapURL]:
        """
        Filter URLs that match any of the given regex patterns.

        Args:
            urls: List of SitemapURL objects to filter
            patterns: List of regex patterns to match against URLs

        Returns:
            List of SitemapURL objects matching at least one pattern
        """
        if not patterns:
            return urls

        compiled_patterns = []
        for pattern in patterns:
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue

        if not compiled_patterns:
            return urls

        filtered = []
        for url in urls:
            for regex in compiled_patterns:
                if regex.search(url.url):
                    filtered.append(url)
                    break

        logger.debug(f"Filtered {len(urls)} URLs to {len(filtered)} matching patterns")
        return filtered

    def prioritize_urls(self, urls: List[SitemapURL]) -> List[SitemapURL]:
        """
        Sort URLs by priority, with most important first.

        Prioritization order:
        1. Most recently modified (lastmod)
        2. Highest priority value
        3. Original order for ties

        Args:
            urls: List of SitemapURL objects to sort

        Returns:
            Sorted list with highest priority URLs first
        """

        def sort_key(url: SitemapURL) -> tuple:
            # Use lastmod as primary sort (most recent first)
            # Use epoch 0 for None values to push them to end
            lastmod_ts = 0.0
            if url.lastmod:
                lastmod_ts = url.lastmod.timestamp()

            # Use priority as secondary sort (highest first)
            priority = url.priority if url.priority is not None else 0.0

            # Negate values for descending sort
            return (-lastmod_ts, -priority)

        return sorted(urls, key=sort_key)

    async def _fetch_sitemap_content(self, url: str) -> bytes | str:
        """
        Fetch sitemap content from URL.

        Args:
            url: URL to fetch

        Returns:
            Raw content (bytes for gzipped, str otherwise)

        Raises:
            Various HTTP exceptions on failure
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/xml, text/xml, application/gzip, */*",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)

            if response.status_code == 404:
                raise SitemapParseError(f"HTTP 404: Not Found - {url}")
            if response.status_code >= 400:
                raise SitemapParseError(
                    f"HTTP {response.status_code}: {response.reason_phrase}"
                )

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.max_size_bytes:
                raise SitemapParseError(
                    f"Sitemap too large: {content_length} bytes exceeds {self.max_size_bytes}"
                )

            return response.content

    async def _fetch_robots_txt(self, url: str) -> str:
        """
        Fetch robots.txt content from URL.

        Args:
            url: URL of robots.txt

        Returns:
            Text content of robots.txt
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/plain, */*",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text

    def _is_gzipped(self, content: bytes) -> bool:
        """Check if content is gzip compressed by magic bytes."""
        if isinstance(content, str):
            return False
        return len(content) >= 2 and content[:2] == b"\x1f\x8b"

    def _decompress_gzip(self, content: bytes) -> str:
        """Decompress gzipped content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return gzip.decompress(content).decode("utf-8")

    def _parse_xml(self, content: str, source_url: str) -> SitemapResult:
        """
        Parse XML sitemap content.

        Args:
            content: XML string content
            source_url: URL of the sitemap (for tracking source)

        Returns:
            SitemapResult with parsed data

        Raises:
            SitemapParseError: If XML is invalid
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise SitemapParseError(f"Invalid XML: {e}")

        # Detect sitemap type from root element
        root_tag = root.tag.lower()

        if "sitemapindex" in root_tag:
            return self._parse_sitemap_index_xml(root, source_url)
        elif "urlset" in root_tag:
            return self._parse_urlset_xml(root, source_url)
        else:
            raise SitemapParseError(f"Unknown sitemap root element: {root.tag}")

    def _parse_sitemap_index_xml(self, root: ET.Element, source_url: str) -> SitemapResult:
        """Parse a sitemap index XML element."""
        child_sitemaps = []
        parse_errors = []

        for sitemap in root.findall("sm:sitemap", SITEMAP_NS):
            loc = sitemap.find("sm:loc", SITEMAP_NS)
            if loc is not None and loc.text:
                child_sitemaps.append(loc.text.strip())

        # Try without namespace if no results
        if not child_sitemaps:
            for sitemap in root.findall("sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    child_sitemaps.append(loc.text.strip())

        logger.info(f"Parsed sitemap index with {len(child_sitemaps)} child sitemaps")

        return SitemapResult(
            urls=[],
            is_index=True,
            child_sitemaps=child_sitemaps,
            total_urls=0,
            parse_errors=parse_errors,
        )

    def _parse_urlset_xml(self, root: ET.Element, source_url: str) -> SitemapResult:
        """Parse a urlset XML element."""
        urls = []
        parse_errors = []

        # Try with namespace first
        url_elements = root.findall("sm:url", SITEMAP_NS)

        # Fall back to no namespace
        if not url_elements:
            url_elements = root.findall("url")

        for url_elem in url_elements:
            parsed_url = self._parse_url_element(url_elem, source_url, parse_errors)
            if parsed_url:
                urls.append(parsed_url)

        logger.info(f"Parsed sitemap with {len(urls)} URLs")

        return SitemapResult(
            urls=urls,
            is_index=False,
            child_sitemaps=[],
            total_urls=len(urls),
            parse_errors=parse_errors,
        )

    def _parse_url_element(
        self, url_elem: ET.Element, source_url: str, parse_errors: List[str]
    ) -> Optional[SitemapURL]:
        """Parse a single URL element from the sitemap."""
        # Extract loc (required)
        loc = url_elem.find("sm:loc", SITEMAP_NS)
        if loc is None:
            loc = url_elem.find("loc")
        if loc is None or not loc.text:
            return None

        url = loc.text.strip()

        # Extract lastmod (optional)
        lastmod = None
        lastmod_elem = url_elem.find("sm:lastmod", SITEMAP_NS)
        if lastmod_elem is None:
            lastmod_elem = url_elem.find("lastmod")
        if lastmod_elem is not None and lastmod_elem.text:
            lastmod = self._parse_date(lastmod_elem.text.strip(), parse_errors)

        # Extract changefreq (optional)
        changefreq = None
        changefreq_elem = url_elem.find("sm:changefreq", SITEMAP_NS)
        if changefreq_elem is None:
            changefreq_elem = url_elem.find("changefreq")
        if changefreq_elem is not None and changefreq_elem.text:
            changefreq = changefreq_elem.text.strip()

        # Extract priority (optional)
        priority = None
        priority_elem = url_elem.find("sm:priority", SITEMAP_NS)
        if priority_elem is None:
            priority_elem = url_elem.find("priority")
        if priority_elem is not None and priority_elem.text:
            priority = self._parse_priority(priority_elem.text.strip(), parse_errors)

        return SitemapURL(
            url=url,
            sitemap_source=source_url,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority,
        )

    def _parse_date(self, date_str: str, parse_errors: List[str]) -> Optional[datetime]:
        """
        Parse a date string in various formats.

        Supported formats:
        - YYYY-MM-DD
        - YYYY-MM-DDTHH:MM:SSZ
        - YYYY-MM-DDTHH:MM:SS+HH:MM
        """
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt_timezone.utc)
                return parsed
            except ValueError:
                continue

        # Try ISO format parsing (handles various timezone formats)
        try:
            # Handle +00:00 format
            if "+" in date_str or date_str.endswith("Z"):
                date_str = date_str.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(date_str)
                return parsed
        except ValueError:
            pass

        parse_errors.append(f"Invalid date format: {date_str}")
        return None

    def _parse_priority(
        self, priority_str: str, parse_errors: List[str]
    ) -> Optional[float]:
        """Parse a priority value (0.0 to 1.0)."""
        try:
            priority = float(priority_str)
            if 0.0 <= priority <= 1.0:
                return priority
            parse_errors.append(f"Priority out of range: {priority_str}")
            return None
        except ValueError:
            parse_errors.append(f"Invalid priority value: {priority_str}")
            return None

    def _extract_sitemap_urls_from_robots(self, content: str) -> List[str]:
        """
        Extract Sitemap: URLs from robots.txt content.

        Args:
            content: robots.txt file content

        Returns:
            List of sitemap URLs
        """
        sitemaps = []
        pattern = re.compile(r"^\s*Sitemap:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

        for match in pattern.finditer(content):
            sitemap_url = match.group(1).strip()
            if sitemap_url:
                sitemaps.append(sitemap_url)

        logger.debug(f"Found {len(sitemaps)} sitemaps in robots.txt")
        return sitemaps


def get_sitemap_parser(
    timeout: float = 30.0,
    user_agent: str = "SpiritswiseCrawler/1.0",
) -> SitemapParser:
    """
    Factory function to get configured SitemapParser.

    Args:
        timeout: HTTP request timeout in seconds
        user_agent: User-Agent header for requests

    Returns:
        Configured SitemapParser instance
    """
    return SitemapParser(timeout=timeout, user_agent=user_agent)
