"""
Confidence-Based Data Merger Service.

Task 1.2: Confidence-Based Merger

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 2.4 (COMP-LEARN-004)

Merge Rules:
- IF new_confidence > existing_confidence: REPLACE field value
- ELIF both are arrays: APPEND unique items
- ELIF both are dicts: MERGE recursively
- None/empty values in new data do not overwrite existing values
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ConfidenceBasedMerger:
    """
    Merges extracted data based on confidence scores.

    Higher confidence sources override lower confidence sources.
    Arrays append unique items when confidence is lower.
    Dicts merge recursively when confidence is lower.
    """

    def __init__(self):
        """Initialize ConfidenceBasedMerger."""
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

        Args:
            existing_data: Current product data dict
            existing_confidences: Dict mapping field names to confidence scores (0.0-1.0)
            new_data: New data to merge from a source
            new_confidence: Confidence score for the new data source (0.0-1.0)

        Returns:
            Tuple of:
            - merged_data: Dict with merged field values
            - enriched_fields: List of field names that were enriched/updated
        """
        merged = dict(existing_data)
        enriched_fields: List[str] = []

        # Start with existing confidences
        self._updated_confidences = dict(existing_confidences)

        for field_name, new_value in new_data.items():
            # Skip None and empty values in new data
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
                # Higher confidence - replace
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
                # Both arrays - append unique items
                merged_list, had_new_items = self._merge_arrays(existing_value, new_value)
                merged[field_name] = merged_list
                if had_new_items:
                    enriched_fields.append(field_name)
                    logger.debug(
                        "Appended unique items to array field %s",
                        field_name,
                    )
                # Keep higher confidence for arrays
                # (we didn't replace, just appended)

            elif isinstance(existing_value, dict) and isinstance(new_value, dict):
                # Both dicts - merge recursively
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

        Returns:
            Dict mapping field names to their confidence scores
        """
        return dict(self._updated_confidences)

    def _is_empty_value(self, value: Any) -> bool:
        """
        Check if a value should be considered empty/null.

        Args:
            value: Value to check

        Returns:
            True if value is None, empty string, or empty list/dict
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

        Args:
            existing: Existing array values
            new: New array values to merge

        Returns:
            Tuple of:
            - merged_list: Combined list with unique items
            - had_new_items: True if new unique items were added
        """
        # Convert existing to set for O(1) lookup
        # Use string representation for complex objects
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

        Args:
            existing: Existing dict values
            new: New dict values to merge

        Returns:
            Tuple of:
            - merged_dict: Combined dict
            - had_new_keys: True if new keys were added
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

        Args:
            item: Item to generate key for

        Returns:
            String key for the item
        """
        if isinstance(item, (str, int, float, bool)):
            return str(item).lower().strip() if isinstance(item, str) else str(item)
        else:
            # For complex objects, use string representation
            return str(item)


# Singleton instance
_confidence_merger: Optional[ConfidenceBasedMerger] = None


def get_confidence_merger() -> ConfidenceBasedMerger:
    """Get singleton ConfidenceBasedMerger instance."""
    global _confidence_merger
    if _confidence_merger is None:
        _confidence_merger = ConfidenceBasedMerger()
    return _confidence_merger


def reset_confidence_merger() -> None:
    """Reset singleton for testing."""
    global _confidence_merger
    _confidence_merger = None
