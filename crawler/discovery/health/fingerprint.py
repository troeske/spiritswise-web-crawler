"""
Structural Fingerprinting for Award Site Pages.

Creates hash fingerprints of HTML DOM structure to detect when page
layouts change. Fingerprints focus on structure (elements, classes,
IDs) rather than content (text, URLs), so they remain stable when
only data changes but detect when the page structure changes.

Usage:
    # Compute fingerprint
    fingerprint = StructuralFingerprint.compute("iwsc", html)

    # Compare with stored fingerprint
    stored = StructuralFingerprint.get_stored("iwsc")
    if stored and not StructuralFingerprint.compare(fingerprint, stored):
        # Structure has changed!
        alert_handler.handle_fingerprint_change("iwsc", stored, fingerprint)

    # Store new fingerprint
    StructuralFingerprint.store("iwsc", fingerprint)
"""

import hashlib
import logging
from typing import Optional, Dict, List
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# In-memory fingerprint storage (would use Redis/DB in production)
_fingerprint_store: Dict[str, str] = {}


class StructuralFingerprint:
    """
    Compute and compare structural fingerprints of HTML pages.

    Fingerprints capture the DOM structure (elements, classes, IDs)
    but ignore content (text, href values). This allows detecting
    when page layouts change while ignoring normal data updates.
    """

    # Important attributes to include in fingerprint
    # These are typically used by CSS selectors in collectors
    STRUCTURE_ATTRIBUTES = {"class", "id", "data-"}

    @classmethod
    def compute(cls, source: str, html: str) -> str:
        """
        Compute a structural fingerprint for HTML content.

        Args:
            source: Source name (used for source-specific handling)
            html: HTML content to fingerprint

        Returns:
            32-character MD5 hash of the structural signature
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract structural signature
        signature = cls._extract_signature(soup)

        # Hash the signature
        hash_obj = hashlib.md5(signature.encode("utf-8"))
        fingerprint = hash_obj.hexdigest()

        logger.debug(f"Computed fingerprint for {source}: {fingerprint}")
        return fingerprint

    @classmethod
    def _extract_signature(cls, soup: BeautifulSoup) -> str:
        """
        Extract structural signature from parsed HTML.

        Creates a string representation of the DOM structure that
        captures element tags and important attributes while ignoring
        text content and dynamic attribute values.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            String signature of the DOM structure
        """
        signature_parts = []

        # Process all elements
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue

            # Build element signature: tag[class][id][data-*]
            elem_sig = cls._element_signature(element)
            if elem_sig:
                signature_parts.append(elem_sig)

        return "|".join(signature_parts)

    @classmethod
    def _element_signature(cls, element: Tag) -> str:
        """
        Create signature for a single HTML element.

        Includes tag name and structural attributes (class, id, data-*)
        but excludes content-specific attributes (href, src values).

        Args:
            element: BeautifulSoup Tag element

        Returns:
            String signature for the element
        """
        parts = [element.name]

        # Add class names (sorted for consistency)
        classes = element.get("class", [])
        if classes:
            if isinstance(classes, str):
                classes = [classes]
            sorted_classes = sorted(classes)
            parts.append(f"class={','.join(sorted_classes)}")

        # Add id
        elem_id = element.get("id")
        if elem_id:
            parts.append(f"id={elem_id}")

        # Add data-* attributes (names only, not values)
        for attr in element.attrs:
            if attr.startswith("data-"):
                parts.append(f"{attr}")

        return ":".join(parts)

    @classmethod
    def compare(cls, fingerprint1: str, fingerprint2: str) -> bool:
        """
        Compare two fingerprints for equality.

        Args:
            fingerprint1: First fingerprint hash
            fingerprint2: Second fingerprint hash

        Returns:
            True if fingerprints match, False otherwise
        """
        return fingerprint1 == fingerprint2

    @classmethod
    def store(cls, source: str, fingerprint: str) -> None:
        """
        Store a fingerprint for a source.

        In production, this would persist to Redis or database.
        Currently uses in-memory storage.

        Args:
            source: Source name
            fingerprint: 32-character fingerprint hash
        """
        _fingerprint_store[source] = fingerprint
        logger.info(f"Stored fingerprint for {source}: {fingerprint}")

    @classmethod
    def get_stored(cls, source: str) -> Optional[str]:
        """
        Get stored fingerprint for a source.

        Args:
            source: Source name

        Returns:
            Stored fingerprint hash, or None if not found
        """
        return _fingerprint_store.get(source)

    @classmethod
    def clear_stored(cls, source: str) -> bool:
        """
        Clear stored fingerprint for a source.

        Args:
            source: Source name

        Returns:
            True if fingerprint was cleared, False if not found
        """
        if source in _fingerprint_store:
            del _fingerprint_store[source]
            return True
        return False

    @classmethod
    def get_all_stored(cls) -> Dict[str, str]:
        """
        Get all stored fingerprints.

        Returns:
            Dict mapping source names to fingerprint hashes
        """
        return dict(_fingerprint_store)

    @classmethod
    def compute_similarity(cls, source: str, html: str, reference: str) -> float:
        """
        Compute similarity between HTML structure and a reference fingerprint.

        This is a simple binary comparison (0.0 or 1.0). A more sophisticated
        implementation could compare structural signatures element-by-element
        to compute partial similarity.

        Args:
            source: Source name
            html: HTML content to compare
            reference: Reference fingerprint to compare against

        Returns:
            1.0 if structures match, 0.0 if different
        """
        fingerprint = cls.compute(source, html)
        return 1.0 if cls.compare(fingerprint, reference) else 0.0
