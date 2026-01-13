"""
Duplicate Detection Service.

Task 2.3: Duplicate Detection (FEAT-007)

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.7

Implements duplicate detection to prevent redundant processing:
- URL-based deduplication with canonicalization
- Content hash deduplication
- Product name/brand fuzzy matching

Key Features:
- URL canonicalization (trailing slashes, www, tracking params, fragments)
- Content hash normalization (whitespace normalization)
- Fuzzy product matching by first word of name
- Session-level caching for in-progress discovery runs
"""

import hashlib
import logging
import re
from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import UUID

logger = logging.getLogger(__name__)

# Common tracking parameters to remove during URL canonicalization
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "msclkid",
    "ref",
    "source",
    "mc_cid",
    "mc_eid",
}


class DuplicateDetector:
    """
    Duplicate detection service for discovery flow.

    Provides three levels of deduplication:
    1. URL-based: Check if URL has been crawled before
    2. Content-based: Check if content hash matches existing content
    3. Product-based: Fuzzy match on name/brand to find existing products

    Also maintains session-level cache for in-progress discovery runs
    to avoid re-checking the same URLs/content within a single session.
    """

    def __init__(self):
        """Initialize DuplicateDetector with empty session caches."""
        self._session_urls: Set[str] = set()
        self._session_content_hashes: Set[str] = set()

    def _canonicalize_url(self, url: Optional[str]) -> str:
        """
        Canonicalize URL for consistent comparison.

        Normalization steps:
        1. Return empty string for None/empty
        2. Lowercase the domain
        3. Remove www prefix
        4. Remove trailing slash from path
        5. Remove fragment (#section)
        6. Remove tracking parameters
        7. Sort remaining query parameters

        Args:
            url: URL to canonicalize

        Returns:
            Canonicalized URL string
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)

            # Lowercase domain and remove www
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]

            # Remove trailing slash from path
            path = parsed.path.rstrip("/") if parsed.path else ""

            # Parse and filter query parameters
            params = parse_qs(parsed.query, keep_blank_values=True)

            # Remove tracking parameters
            filtered_params = {
                k: v for k, v in params.items()
                if k.lower() not in TRACKING_PARAMS
            }

            # Sort and encode remaining parameters
            sorted_params = sorted(filtered_params.items())
            # Flatten single-item lists
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
                "",  # params
                query,
                "",  # fragment removed
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
        - Collapse multiple whitespace to single space

        Args:
            content: Content to hash

        Returns:
            SHA-256 hex digest of normalized content
        """
        if not content:
            return ""

        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', content.strip())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def is_duplicate_url(self, url: Optional[str]) -> bool:
        """
        Check if URL has already been crawled.

        Spec Reference: Section 5.7.1

        Args:
            url: URL to check

        Returns:
            True if URL exists in CrawledSource, False otherwise
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

        Spec Reference: Section 5.7.2

        Args:
            content: Content to check

        Returns:
            True if content hash exists in CrawledSource, False otherwise
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

        Spec Reference: Section 5.7.3

        Matching strategy:
        - If brand provided: exact match on brand (case-insensitive)
        - First word of name for fuzzy match (icontains)

        Args:
            name: Product name to search
            brand: Optional brand name for filtering

        Returns:
            UUID of matching DiscoveredProduct, or None if not found
        """
        if not name:
            return None

        from crawler.models import DiscoveredProduct

        try:
            # Build filter
            filter_kwargs = {}

            # Brand filter (case-insensitive exact match)
            if brand:
                filter_kwargs["brand__name__iexact"] = brand

            # First word of name for fuzzy match
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

        Used in discovery flow before fetching.

        Args:
            url: URL to check

        Returns:
            True if URL should be skipped
        """
        if not url:
            return False

        # Check session cache first (fast)
        if self.is_url_in_session(url):
            return True

        # Check database
        return self.is_duplicate_url(url)

    def should_skip_content(self, content: Optional[str]) -> bool:
        """
        Check if content should be skipped (duplicate or in session).

        Used in discovery flow after fetching.

        Args:
            content: Content to check

        Returns:
            True if content should be skipped
        """
        if not content:
            return False

        # Check session cache first (fast)
        if self.is_content_in_session(content):
            return True

        # Check database
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

        Check order (early exit on first duplicate found):
        1. URL check (fastest - index lookup)
        2. Content hash check (fast - index lookup)
        3. Product fuzzy match (slower - text search)

        Args:
            url: URL to check
            content: Content to check
            product_name: Product name to check
            product_brand: Product brand to check

        Returns:
            Dict with keys:
            - is_duplicate: bool
            - duplicate_type: "url" | "content" | "product" | None
            - existing_product_id: UUID | None (only for product duplicates)
        """
        result = {
            "is_duplicate": False,
            "duplicate_type": None,
            "existing_product_id": None,
        }

        # Check URL first
        if url and self.is_duplicate_url(url):
            result["is_duplicate"] = True
            result["duplicate_type"] = "url"
            return result

        # Check content second
        if content and self.is_duplicate_content(content):
            result["is_duplicate"] = True
            result["duplicate_type"] = "content"
            return result

        # Check product last
        if product_name:
            existing_id = self.find_duplicate_product(product_name, product_brand)
            if existing_id:
                result["is_duplicate"] = True
                result["duplicate_type"] = "product"
                result["existing_product_id"] = existing_id
                return result

        return result

    # Session-level caching methods

    def record_url(self, url: str) -> None:
        """
        Record URL in session cache.

        Args:
            url: URL to record
        """
        if url:
            canonical = self._canonicalize_url(url)
            self._session_urls.add(canonical)

    def record_content(self, content: str) -> None:
        """
        Record content hash in session cache.

        Args:
            content: Content to record
        """
        if content:
            content_hash = self._generate_content_hash(content)
            self._session_content_hashes.add(content_hash)

    def is_url_in_session(self, url: str) -> bool:
        """
        Check if URL is in session cache.

        Args:
            url: URL to check

        Returns:
            True if URL was recorded in current session
        """
        if not url:
            return False
        canonical = self._canonicalize_url(url)
        return canonical in self._session_urls

    def is_content_in_session(self, content: str) -> bool:
        """
        Check if content hash is in session cache.

        Args:
            content: Content to check

        Returns:
            True if content was recorded in current session
        """
        if not content:
            return False
        content_hash = self._generate_content_hash(content)
        return content_hash in self._session_content_hashes

    def clear_session_cache(self) -> None:
        """Clear session-level caches."""
        self._session_urls.clear()
        self._session_content_hashes.clear()


# Singleton pattern
_duplicate_detector_instance: Optional[DuplicateDetector] = None


def get_duplicate_detector() -> DuplicateDetector:
    """
    Get singleton DuplicateDetector instance.

    Returns:
        DuplicateDetector singleton
    """
    global _duplicate_detector_instance
    if _duplicate_detector_instance is None:
        _duplicate_detector_instance = DuplicateDetector()
    return _duplicate_detector_instance


def reset_duplicate_detector() -> None:
    """Reset singleton DuplicateDetector instance (for testing)."""
    global _duplicate_detector_instance
    _duplicate_detector_instance = None
