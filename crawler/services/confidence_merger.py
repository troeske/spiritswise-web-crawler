"""
Confidence-Based Data Merger Service.

This module provides intelligent merging of product data from multiple sources
based on confidence scores. Higher confidence data wins over lower confidence
data, while arrays and dicts are merged to accumulate information.

Task Reference: GENERIC_SEARCH_V3_TASKS.md Task 1.2
Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 2.4 (COMP-LEARN-004)

The Problem:
    When enriching a product from multiple sources (producer page, review sites,
    retailers), we need to decide which source's data to use for each field.
    A producer's official ABV (0.85 confidence) should not be overwritten by
    a review site's estimated ABV (0.70 confidence).

Solution - Confidence-Based Merging:
    Merge Rules:
    1. IF new_confidence > existing_confidence: REPLACE field value
    2. ELIF both are arrays: APPEND unique items (preserves all information)
    3. ELIF both are dicts: MERGE recursively (same rules apply to nested fields)
    4. None/empty values in new data NEVER overwrite existing values

Confidence Levels (typical):
    - Producer/Official page: 0.85-0.95
    - Review sites: 0.70-0.80
    - Retailers: 0.60-0.70
    - Generic search results: 0.50-0.60

Example:
    >>> merger = ConfidenceBasedMerger()
    >>> existing = {"name": "Lagavulin 16", "abv": 43.0}
    >>> existing_conf = {"name": 0.85, "abv": 0.85}
    >>> new_data = {"abv": 43.5, "region": "Islay"}
    >>> merged, enriched = merger.merge(existing, existing_conf, new_data, 0.70)
    >>> print(merged)
    {"name": "Lagavulin 16", "abv": 43.0, "region": "Islay"}
    >>> print(enriched)
    ["region"]  # abv not enriched because new_conf (0.70) < existing_conf (0.85)

Usage:
    from crawler.services.confidence_merger import get_confidence_merger

    merger = get_confidence_merger()
    merged_data, enriched_fields = merger.merge(
        existing_data=product_data,
        existing_confidences=field_confidences,
        new_data=extracted_data,
        new_confidence=0.75,
    )
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ConfidenceBasedMerger:
    """
    Merges extracted data based on confidence scores.

    This class implements intelligent field-by-field merging that respects
    source confidence levels. It ensures high-quality data from authoritative
    sources is preserved while still accumulating additional information from
    less authoritative sources.

    Merge Behavior by Type:
        Scalar values (str, int, float, bool):
            Higher confidence replaces lower confidence.
            If confidence is equal or lower, existing value is kept.

        Arrays (list):
            Unique items from new array are appended to existing array.
            Deduplication uses string representation for complex objects.
            Original confidence is maintained.

        Dicts (dict):
            Recursively merged. New keys are added, existing keys follow
            the same confidence rules as scalars.

        None/Empty values:
            Never overwrite existing values. Empty string, None, empty list,
            and empty dict are all considered "empty" and ignored.

    Attributes:
        _updated_confidences: Dict tracking confidence scores after merge.
            Updated during each merge() call.

    Example:
        >>> merger = ConfidenceBasedMerger()
        >>> existing = {"palate_flavors": ["vanilla", "oak"]}
        >>> new_data = {"palate_flavors": ["vanilla", "caramel", "spice"]}
        >>> merged, enriched = merger.merge(existing, {}, new_data, 0.70)
        >>> print(merged["palate_flavors"])
        ["vanilla", "oak", "caramel", "spice"]  # Unique items appended
    """

    def __init__(self) -> None:
        """Initialize ConfidenceBasedMerger with empty confidence tracking."""
        self._updated_confidences: Dict[str, float] = {}

    def merge(
        self,
        existing_data: Dict[str, Any],
        existing_confidences: Dict[str, float],
        new_data: Dict[str, Any],
        new_confidence: float,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Merge new data into existing data based on confidence scores.

        Iterates through each field in new_data and decides whether to:
        1. Add it (if new field or existing is empty)
        2. Replace it (if new confidence > existing confidence)
        3. Append to it (if both are arrays)
        4. Merge into it (if both are dicts)
        5. Skip it (if lower confidence or empty new value)

        Args:
            existing_data: Current product data dict. Keys are field names,
                values are current field values of any type.
            existing_confidences: Dict mapping field names to confidence scores
                (0.0-1.0). Fields not in this dict are assumed to have 0.0
                confidence.
            new_data: New data to merge from a source. Same structure as
                existing_data.
            new_confidence: Confidence score for ALL fields in new_data
                (0.0-1.0). This is typically the source's overall confidence
                level.

        Returns:
            A tuple of (merged_data, enriched_fields) where:
            - merged_data: Dict with merged field values. Contains all keys
                from existing_data plus any new keys from new_data.
            - enriched_fields: List of field names that were added or updated.
                Does not include fields where new data was skipped.

        Example:
            >>> merger = ConfidenceBasedMerger()
            >>> existing = {"name": "Macallan 18", "abv": 43.0}
            >>> conf = {"name": 0.90, "abv": 0.85}
            >>> new = {"abv": 43.5, "region": "Speyside", "price": 350}
            >>> merged, enriched = merger.merge(existing, conf, new, 0.75)
            >>> print(enriched)
            ["region", "price"]  # abv not enriched due to lower confidence
        """
        merged = dict(existing_data)
        enriched_fields: List[str] = []

        # Start with existing confidences, will update as we merge
        self._updated_confidences = dict(existing_confidences)

        for field_name, new_value in new_data.items():
            # Skip None and empty values in new data
            # This prevents accidental data loss from incomplete extractions
            if self._is_empty_value(new_value):
                continue

            existing_value = existing_data.get(field_name)
            existing_confidence = existing_confidences.get(field_name, 0.0)

            # Handle field based on whether it exists and confidence levels
            if field_name not in existing_data or self._is_empty_value(existing_value):
                # New field or empty existing - always add
                merged[field_name] = new_value
                enriched_fields.append(field_name)
                self._updated_confidences[field_name] = new_confidence
                logger.debug(
                    "Added new field %s with confidence %.2f",
                    field_name,
                    new_confidence,
                )

            elif new_confidence > existing_confidence:
                # Higher confidence - replace existing value
                merged[field_name] = new_value
                enriched_fields.append(field_name)
                self._updated_confidences[field_name] = new_confidence
                logger.debug(
                    "Replaced field %s: new_conf=%.2f > existing_conf=%.2f",
                    field_name,
                    new_confidence,
                    existing_confidence,
                )

            elif isinstance(existing_value, list) and isinstance(new_value, list):
                # Both arrays - append unique items (accumulate information)
                merged_list, had_new_items = self._merge_arrays(existing_value, new_value)
                merged[field_name] = merged_list
                if had_new_items:
                    enriched_fields.append(field_name)
                    logger.debug(
                        "Appended unique items to array field %s",
                        field_name,
                    )
                # Keep higher confidence for arrays (we didn't replace, just appended)

            elif isinstance(existing_value, dict) and isinstance(new_value, dict):
                # Both dicts - merge recursively (accumulate information)
                merged_dict, had_new_keys = self._merge_dicts(existing_value, new_value)
                merged[field_name] = merged_dict
                if had_new_keys:
                    enriched_fields.append(field_name)
                    logger.debug(
                        "Merged dict field %s with new keys",
                        field_name,
                    )
                # Keep existing confidence for dict merges

            else:
                # Lower or equal confidence, not array/dict - skip
                logger.debug(
                    "Skipped field %s: new_conf=%.2f <= existing_conf=%.2f",
                    field_name,
                    new_confidence,
                    existing_confidence,
                )

        return merged, enriched_fields

    def get_updated_confidences(self) -> Dict[str, float]:
        """
        Get the updated confidence scores after the last merge.

        Returns a copy of the confidence dict that was updated during the
        most recent merge() call. Use this to track field confidences
        across multiple merge operations.

        Returns:
            Dict mapping field names to their confidence scores (0.0-1.0).
            Includes all fields from the existing_confidences passed to merge(),
            plus any new fields that were added.

        Example:
            >>> merger = ConfidenceBasedMerger()
            >>> merged, _ = merger.merge(existing, conf, new, 0.80)
            >>> new_conf = merger.get_updated_confidences()
            >>> print(new_conf["new_field"])
            0.80
        """
        return dict(self._updated_confidences)

    def _is_empty_value(self, value: Any) -> bool:
        """
        Check if a value should be considered empty/null.

        Empty values are never used to overwrite existing data, as they
        represent missing or incomplete information from a source.

        Args:
            value: Value to check. Can be any type.

        Returns:
            True if value is considered empty:
            - None
            - Empty string or whitespace-only string
            - Empty list
            - Empty dict
            Returns False for all other values including 0, False, etc.
        """
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, (list, dict)) and not value:
            return True
        return False

    def _merge_arrays(
        self,
        existing: List[Any],
        new: List[Any],
    ) -> Tuple[List[Any], bool]:
        """
        Merge two arrays, appending unique items from new to existing.

        Deduplication uses string representation for consistent comparison
        across different types. For strings, comparison is case-insensitive
        and whitespace-trimmed.

        Args:
            existing: Existing array values. Order is preserved.
            new: New array values to merge.

        Returns:
            A tuple of (merged_list, had_new_items) where:
            - merged_list: Combined list with unique items appended.
                Existing items come first, new unique items appended.
            - had_new_items: True if any new unique items were added.

        Example:
            >>> merger = ConfidenceBasedMerger()
            >>> merged, had_new = merger._merge_arrays(
            ...     ["Vanilla", "Oak"],
            ...     ["vanilla", "Caramel", "spice"]
            ... )
            >>> print(merged)
            ["Vanilla", "Oak", "Caramel", "spice"]  # "vanilla" deduplicated
        """
        # Convert existing to set for O(1) lookup using string keys
        existing_set: Set[str] = {self._item_key(item) for item in existing}

        merged = list(existing)
        had_new_items = False

        for item in new:
            item_key = self._item_key(item)
            if item_key not in existing_set:
                merged.append(item)
                existing_set.add(item_key)
                had_new_items = True

        return merged, had_new_items

    def _merge_dicts(
        self,
        existing: Dict[str, Any],
        new: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Merge two dicts recursively, only adding keys that don't exist.

        For nested dicts and arrays, applies the same merge logic recursively.
        Existing values are never replaced, only augmented with new keys.

        Args:
            existing: Existing dict values.
            new: New dict values to merge.

        Returns:
            A tuple of (merged_dict, had_new_keys) where:
            - merged_dict: Combined dict with new keys added.
            - had_new_keys: True if any new keys were added at any level.
        """
        merged = dict(existing)
        had_new_keys = False

        for key, new_value in new.items():
            if key not in existing or self._is_empty_value(existing.get(key)):
                # New key or empty existing - add it
                merged[key] = new_value
                had_new_keys = True
            elif isinstance(existing[key], dict) and isinstance(new_value, dict):
                # Both dicts - recurse
                merged[key], child_had_new = self._merge_dicts(existing[key], new_value)
                if child_had_new:
                    had_new_keys = True
            elif isinstance(existing[key], list) and isinstance(new_value, list):
                # Both lists - merge arrays
                merged[key], child_had_new = self._merge_arrays(existing[key], new_value)
                if child_had_new:
                    had_new_keys = True
            # Otherwise keep existing value (it already exists)

        return merged, had_new_keys

    def _item_key(self, item: Any) -> str:
        """
        Generate a unique key for an item for deduplication.

        Creates a string representation that can be used for set membership
        testing. For strings, normalizes to lowercase and strips whitespace.
        For other types, uses str() representation.

        Args:
            item: Item to generate key for. Can be any type.

        Returns:
            String key for the item. For strings, returns lowercase stripped.
            For other types, returns str(item).
        """
        if isinstance(item, (str, int, float, bool)):
            return str(item).lower().strip() if isinstance(item, str) else str(item)
        else:
            # For complex objects, use string representation
            return str(item)


# Singleton instance for module-level access
_confidence_merger: Optional[ConfidenceBasedMerger] = None


def get_confidence_merger() -> ConfidenceBasedMerger:
    """
    Get the singleton ConfidenceBasedMerger instance.

    Creates a new instance on first call, then returns the same instance
    on subsequent calls. Use reset_confidence_merger() to clear the
    singleton (mainly for testing).

    Returns:
        The shared ConfidenceBasedMerger instance.

    Example:
        >>> merger = get_confidence_merger()
        >>> merged, enriched = merger.merge(existing, conf, new, 0.75)
    """
    global _confidence_merger
    if _confidence_merger is None:
        _confidence_merger = ConfidenceBasedMerger()
    return _confidence_merger


def reset_confidence_merger() -> None:
    """
    Reset the singleton ConfidenceBasedMerger instance.

    Clears the singleton so the next call to get_confidence_merger()
    creates a fresh instance. Primarily used in tests to ensure isolation
    between test cases.
    """
    global _confidence_merger
    _confidence_merger = None
