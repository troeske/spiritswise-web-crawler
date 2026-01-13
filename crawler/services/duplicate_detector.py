"""
Duplicate Detection Service.

This module provides multi-level duplicate detection to prevent redundant
processing during product discovery and enrichment. It checks URLs, content
hashes, and product names to identify duplicates at different stages of
the pipeline.

Task Reference: GENERIC_SEARCH_V3_TASKS.md Task 2.3
Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.7 (FEAT-007)

Deduplication Levels:
    URL-based:
        Checks if a URL has been crawled before using canonicalized URLs.
        Canonicalization normalizes trailing slashes, www prefixes, tracking
        parameters, fragments, and query parameter ordering.

    Content Hash-based:
        Checks if content has been processed before using SHA-256 hash of
        normalized content. Catches duplicates even if URLs differ.

    Product Name/Brand Fuzzy Matching:
        Finds existing products by fuzzy matching on name and brand.
        Uses first word of name with case-insensitive brand matching.

Session Caching:
    Maintains in-memory caches for URLs and content hashes within a
    discovery session. This avoids repeated database queries during
    a single discovery run.

Example:
    >>> detector = DuplicateDetector()
    >>> # Check before fetching
    >>> if detector.should_skip_url("https://example.com/product"):
    ...     print("Already crawled, skipping")
    >>> # Record after fetching
    >>> detector.record_url("https://example.com/product")
    >>> detector.record_content(content)

Usage:
    from crawler.services.duplicate_detector import get_duplicate_detector

    detector = get_duplicate_detector()

    # Check URL before fetch
    if not detector.should_skip_url(url):
        content = fetch(url)
        # Check content after fetch
        if not detector.should_skip_content(content):
            # Process content
            detector.record_url(url)
            detector.record_content(content)
"""

import hashlib
import logging
import re
from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import UUID

logger = logging.getLogger(__name__)


# Common tracking parameters to remove during URL canonicalization.
# These parameters don't affect page content but create false URL duplicates.
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",      # Facebook click ID
    "gclid",       # Google click ID
    "msclkid",     # Microsoft click ID
    "ref",         # Generic referral
    "source",      # Generic source
    "mc_cid",      # Mailchimp campaign ID
    "mc_eid",      # Mailchimp email ID
}


class DuplicateDetector:
    """
    Duplicate detection service for discovery flow.

    Provides three levels of deduplication to prevent redundant processing:

    1. URL-based deduplication:
       Checks CrawledSource table for existing URLs after canonicalization.
       Canonicalization removes tracking params, normalizes domains, etc.

    2. Content hash deduplication:
       Computes SHA-256 hash of normalized content and checks CrawledSource.
       Catches duplicates even when URLs differ (e.g., redirects, mirrors).

    3. Product fuzzy matching:
       Matches by brand (exact, case-insensitive) and first word of name.
       Used after extraction to find existing products.

    Also maintains session-level caches for efficient in-progress discovery:
    - _session_urls: Canonicalized URLs seen in current session
    - _session_content_hashes: Content hashes seen in current session

    The session cache prevents repeated database queries within a single
    discovery run, improving performance for batch operations.

    Attributes:
        _session_urls: Set of canonicalized URLs seen in current session.
        _session_content_hashes: Set of content hashes seen in current session.

    Example:
        >>> detector = DuplicateDetector()
        >>> # Full deduplication check
        >>> result = detector.check_all(
        ...     url="https://example.com/product?utm_source=test",
        ...     content="Product page content...",
        ...     product_name="Lagavulin 16 Year",
        ...     product_brand="Lagavulin"
        ... )
        >>> if result["is_duplicate"]:
        ...     print(f"Duplicate: {result['duplicate_type']}")
    """

    def __init__(self) -> None:
        """Initialize DuplicateDetector with empty session caches."""
        self._session_urls: Set[str] = set()
        self._session_content_hashes: Set[str] = set()

    def _canonicalize_url(self, url: Optional[str]) -> str:
        """
        Canonicalize URL for consistent comparison.

        Applies the following normalization steps:
        1. Return empty string for None/empty input
        2. Lowercase the domain
        3. Remove www prefix
        4. Remove trailing slash from path
        5. Remove fragment (#section)
        6. Remove tracking parameters (utm_*, fbclid, gclid, etc.)
        7. Sort remaining query parameters alphabetically

        This ensures URLs that point to the same content are treated as
        duplicates even if they have different tracking parameters or
        minor formatting differences.

        Args:
            url: URL to canonicalize. May be None.

        Returns:
            Canonicalized URL string. Empty string if input is None/empty.

        Example:
            >>> detector._canonicalize_url(
            ...     "https://WWW.Example.com/page/?utm_source=test&b=2&a=1#section"
            ... )
            "https://example.com/page?a=1&b=2"
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)

            # Lowercase domain and remove www prefix
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]

            # Remove trailing slash from path (but keep "/" for root)
            path = parsed.path.rstrip("/") if parsed.path else ""

            # Parse query parameters
            params = parse_qs(parsed.query, keep_blank_values=True)

            # Remove tracking parameters (case-insensitive comparison)
            filtered_params = {
                k: v for k, v in params.items()
                if k.lower() not in TRACKING_PARAMS
            }

            # Sort parameters and flatten single-item lists for consistent ordering
            sorted_params = sorted(filtered_params.items())
            query_pairs = []
            for key, values in sorted_params:
                for value in values:
                    query_pairs.append((key, value))
            query = urlencode(query_pairs)

            # Reconstruct URL without fragment
            canonical = urlunparse((
                parsed.scheme,
                netloc,
                path,
                "",      # params (rarely used)
                query,
                "",      # fragment removed
            ))

            return canonical

        except Exception as e:
            logger.warning(f"Error canonicalizing URL '{url}': {e}")
            return url or ""

    def _generate_content_hash(self, content: Optional[str]) -> str:
        """
        Generate SHA-256 hash of content for deduplication.

        Normalizes content before hashing:
        - Strip leading/trailing whitespace
        - Collapse multiple whitespace characters to single space

        This normalization ensures minor formatting differences don't
        create false negatives.

        Args:
            content: Content string to hash. May be None.

        Returns:
            SHA-256 hex digest of normalized content.
            Empty string if content is None/empty.

        Example:
            >>> detector._generate_content_hash("Hello   World  ")
            "a591a6d40bf420404a011733cfb7b190..."  # SHA-256 of "Hello World"
        """
        if not content:
            return ""

        # Normalize whitespace before hashing
        normalized = re.sub(r'\s+', ' ', content.strip())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def is_duplicate_url(self, url: Optional[str]) -> bool:
        """
        Check if URL has already been crawled in the database.

        Uses canonicalized URL for comparison to handle tracking parameters
        and minor URL variations.

        Spec Reference: Section 5.7.1

        Args:
            url: URL to check. May be None.

        Returns:
            True if URL exists in CrawledSource table, False otherwise.

        Note:
            This only checks the database, not the session cache.
            Use should_skip_url() for combined session + database check.
        """
        if not url:
            return False

        from crawler.models import CrawledSource

        canonical_url = self._canonicalize_url(url)
        if not canonical_url:
            return False

        try:
            return CrawledSource.objects.filter(url=canonical_url).exists()
        except Exception as e:
            logger.error(f"Error checking duplicate URL: {e}")
            return False

    def is_duplicate_content(self, content: Optional[str]) -> bool:
        """
        Check if content hash matches existing crawled content.

        Uses SHA-256 hash of normalized content for comparison.

        Spec Reference: Section 5.7.2

        Args:
            content: Content string to check. May be None.

        Returns:
            True if content hash exists in CrawledSource table, False otherwise.

        Note:
            This only checks the database, not the session cache.
            Use should_skip_content() for combined session + database check.
        """
        if not content:
            return False

        from crawler.models import CrawledSource

        content_hash = self._generate_content_hash(content)
        if not content_hash:
            return False

        try:
            return CrawledSource.objects.filter(content_hash=content_hash).exists()
        except Exception as e:
            logger.error(f"Error checking duplicate content: {e}")
            return False

    def find_duplicate_product(
        self,
        name: Optional[str],
        brand: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Find existing product by fuzzy name/brand matching.

        Uses a two-part matching strategy:
        1. If brand provided: exact match on brand (case-insensitive)
        2. First word of name: partial match (icontains)

        This catches products that might be named slightly differently
        across sources while still being the same product.

        Spec Reference: Section 5.7.3

        Args:
            name: Product name to search. May be None.
            brand: Optional brand name for filtering. Exact match (case-insensitive).

        Returns:
            UUID of matching DiscoveredProduct if found, None otherwise.

        Example:
            >>> detector.find_duplicate_product(
            ...     name="Lagavulin 16 Year Old Single Malt",
            ...     brand="Lagavulin"
            ... )
            UUID("12345678-...")  # Matches "Lagavulin 16" in database
        """
        if not name:
            return None

        from crawler.models import DiscoveredProduct

        try:
            # Build filter criteria
            filter_kwargs = {}

            # Brand filter: exact match (case-insensitive)
            if brand:
                filter_kwargs["brand__name__iexact"] = brand

            # Name filter: first word match (icontains for flexibility)
            # Using first word catches "Lagavulin 16" matching "Lagavulin 16 Year Old"
            name_parts = name.split()
            if name_parts:
                first_word = name_parts[0]
                filter_kwargs["name__icontains"] = first_word

            if not filter_kwargs:
                return None

            match = DiscoveredProduct.objects.filter(**filter_kwargs).first()
            return match.id if match else None

        except Exception as e:
            logger.error(f"Error finding duplicate product: {e}")
            return None

    def should_skip_url(self, url: Optional[str]) -> bool:
        """
        Check if URL should be skipped (duplicate or in session).

        Combines session cache check and database check for efficient
        deduplication during discovery flow. Check order:
        1. Session cache (fast, in-memory)
        2. Database (slower, but authoritative)

        Use this before fetching a URL to avoid redundant HTTP requests.

        Args:
            url: URL to check. May be None.

        Returns:
            True if URL should be skipped (is duplicate), False otherwise.
        """
        if not url:
            return False

        # Check session cache first (fast, in-memory)
        if self.is_url_in_session(url):
            return True

        # Check database (slower, but authoritative)
        return self.is_duplicate_url(url)

    def should_skip_content(self, content: Optional[str]) -> bool:
        """
        Check if content should be skipped (duplicate or in session).

        Combines session cache check and database check for efficient
        deduplication. Check order:
        1. Session cache (fast, in-memory)
        2. Database (slower, but authoritative)

        Use this after fetching content to avoid redundant extraction.

        Args:
            content: Content string to check. May be None.

        Returns:
            True if content should be skipped (is duplicate), False otherwise.
        """
        if not content:
            return False

        # Check session cache first (fast, in-memory)
        if self.is_content_in_session(content):
            return True

        # Check database (slower, but authoritative)
        return self.is_duplicate_content(content)

    def check_all(
        self,
        url: Optional[str] = None,
        content: Optional[str] = None,
        product_name: Optional[str] = None,
        product_brand: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform full deduplication check across all levels.

        Checks in order of speed (early exit on first duplicate found):
        1. URL check (fastest - index lookup on canonical URL)
        2. Content hash check (fast - index lookup on hash)
        3. Product fuzzy match (slower - text search)

        This order optimizes for the common case where duplicates are
        caught early by URL or content hash.

        Args:
            url: URL to check. May be None.
            content: Content to check. May be None.
            product_name: Product name to check. May be None.
            product_brand: Product brand to check. May be None.

        Returns:
            Dict with keys:
            - is_duplicate (bool): True if any duplicate found
            - duplicate_type (str | None): "url", "content", or "product"
            - existing_product_id (UUID | None): Only for product duplicates

        Example:
            >>> result = detector.check_all(
            ...     url="https://example.com/product",
            ...     content="Page content...",
            ...     product_name="Lagavulin 16",
            ...     product_brand="Lagavulin"
            ... )
            >>> if result["is_duplicate"]:
            ...     print(f"Found {result['duplicate_type']} duplicate")
        """
        result = {
            "is_duplicate": False,
            "duplicate_type": None,
            "existing_product_id": None,
        }

        # Check URL first (fastest - uses indexed canonical URL)
        if url and self.is_duplicate_url(url):
            result["is_duplicate"] = True
            result["duplicate_type"] = "url"
            return result

        # Check content second (fast - uses indexed content hash)
        if content and self.is_duplicate_content(content):
            result["is_duplicate"] = True
            result["duplicate_type"] = "content"
            return result

        # Check product last (slowest - involves text search)
        if product_name:
            existing_id = self.find_duplicate_product(product_name, product_brand)
            if existing_id:
                result["is_duplicate"] = True
                result["duplicate_type"] = "product"
                result["existing_product_id"] = existing_id
                return result

        return result

    # =========================================================================
    # Session-level caching methods
    # =========================================================================

    def record_url(self, url: str) -> None:
        """
        Record URL in session cache.

        Call this after successfully processing a URL to prevent
        re-processing within the same discovery session.

        Args:
            url: URL to record. Empty/None URLs are ignored.
        """
        if url:
            canonical = self._canonicalize_url(url)
            self._session_urls.add(canonical)

    def record_content(self, content: str) -> None:
        """
        Record content hash in session cache.

        Call this after successfully processing content to prevent
        re-processing within the same discovery session.

        Args:
            content: Content string to record. Empty/None content is ignored.
        """
        if content:
            content_hash = self._generate_content_hash(content)
            self._session_content_hashes.add(content_hash)

    def is_url_in_session(self, url: str) -> bool:
        """
        Check if URL is in session cache.

        Fast in-memory check without database access.

        Args:
            url: URL to check.

        Returns:
            True if URL was recorded in current session, False otherwise.
        """
        if not url:
            return False
        canonical = self._canonicalize_url(url)
        return canonical in self._session_urls

    def is_content_in_session(self, content: str) -> bool:
        """
        Check if content hash is in session cache.

        Fast in-memory check without database access.

        Args:
            content: Content to check.

        Returns:
            True if content was recorded in current session, False otherwise.
        """
        if not content:
            return False
        content_hash = self._generate_content_hash(content)
        return content_hash in self._session_content_hashes

    def clear_session_cache(self) -> None:
        """
        Clear session-level caches.

        Call this when starting a new discovery session to reset
        the in-memory URL and content hash caches.
        """
        self._session_urls.clear()
        self._session_content_hashes.clear()


# Singleton instance for module-level access
_duplicate_detector_instance: Optional[DuplicateDetector] = None


def get_duplicate_detector() -> DuplicateDetector:
    """
    Get the singleton DuplicateDetector instance.

    Creates a new instance on first call, then returns the same instance
    on subsequent calls. The singleton maintains session caches across
    calls within the same process.

    Returns:
        The shared DuplicateDetector instance.

    Example:
        >>> detector = get_duplicate_detector()
        >>> if not detector.should_skip_url(url):
        ...     process(url)
        ...     detector.record_url(url)
    """
    global _duplicate_detector_instance
    if _duplicate_detector_instance is None:
        _duplicate_detector_instance = DuplicateDetector()
    return _duplicate_detector_instance


def reset_duplicate_detector() -> None:
    """
    Reset the singleton DuplicateDetector instance.

    Clears the singleton so the next call to get_duplicate_detector()
    creates a fresh instance with empty session caches. Primarily used
    in tests to ensure isolation between test cases.
    """
    global _duplicate_detector_instance
    _duplicate_detector_instance = None
