"""
Conflict Detection Service.

RECT-009: Implement Conflict Detection Logic

Detects conflicts when merging data from multiple sources for
the same product. Compares field values from different sources
and flags products with conflicting information.

Conflict Types:
1. Numerical conflicts: Different values for ABV, age, volume
2. String conflicts: Different values for region, country
3. Array fields: Generally additive (not conflicting)
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from django.db.models import QuerySet

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration: Field Types for Conflict Detection
# =============================================================================

# Numerical fields require exact match (conflicts if different)
NUMERICAL_FIELDS: Set[str] = {
    "abv",
    "age_statement",
    "volume_ml",
    "vintage_year",
    "bottling_year",
    "harvest_year",
    "color_intensity",
    "primary_intensity",
    "flavor_intensity",
    "complexity",
}

# String fields that are case-insensitive (conflicts if different after normalization)
CASE_INSENSITIVE_FIELDS: Set[str] = {
    "country",
    "region",
    "whiskey_country",
    "whiskey_region",
}

# String fields that are case-sensitive (conflicts if different)
CASE_SENSITIVE_FIELDS: Set[str] = {
    "name",
    "distillery",
    "producer_house",
    "quinta",
    "brand",
}

# Array fields are additive - different values do NOT create conflicts
ARRAY_FIELDS: Set[str] = {
    "primary_aromas",
    "secondary_aromas",
    "palate_flavors",
    "finish_flavors",
    "grape_varieties",
}

# All fields that should be checked for conflicts
ALL_CONFLICT_FIELDS: Set[str] = (
    NUMERICAL_FIELDS | CASE_INSENSITIVE_FIELDS | CASE_SENSITIVE_FIELDS
)


# =============================================================================
# Conflict Detection Functions
# =============================================================================

def _normalize_value(value: str, field_name: str) -> str:
    """
    Normalize a value for comparison.

    - Strips whitespace
    - Lowercases if field is case-insensitive
    """
    if value is None:
        return ""

    normalized = str(value).strip()

    if field_name in CASE_INSENSITIVE_FIELDS:
        normalized = normalized.lower()

    return normalized


def _parse_array_value(value: str) -> List[str]:
    """Parse array value from JSON string or return empty list."""
    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v).strip().lower() for v in parsed]
    except (json.JSONDecodeError, TypeError):
        pass

    return []


def detect_conflicts(
    product,
    min_confidence: float = 0.0,
) -> Dict[str, Any]:
    """
    Detect conflicts in field values from multiple sources.

    Args:
        product: DiscoveredProduct instance
        min_confidence: Minimum confidence threshold for values to be considered

    Returns:
        Dictionary containing:
        - has_conflicts: bool - True if any conflicts detected
        - conflicting_fields: List[str] - Names of fields with conflicts
        - conflict_details: Dict - Details about each conflict
    """
    from crawler.models import ProductFieldSource

    # Get all provenance records for this product
    provenance_records = ProductFieldSource.objects.filter(
        product=product
    ).select_related("source")

    if min_confidence > 0:
        provenance_records = provenance_records.filter(confidence__gte=min_confidence)

    # Group records by field name
    fields_by_name: Dict[str, List] = {}
    for record in provenance_records:
        if record.field_name not in fields_by_name:
            fields_by_name[record.field_name] = []
        fields_by_name[record.field_name].append(record)

    # Detect conflicts
    conflicting_fields = []
    conflict_details = {}

    for field_name, records in fields_by_name.items():
        if len(records) < 2:
            # Need at least 2 sources to have a conflict
            continue

        if field_name in ARRAY_FIELDS:
            # Array fields are additive - no conflicts
            continue

        # Check for conflicts
        unique_values = set()
        for record in records:
            normalized = _normalize_value(record.extracted_value, field_name)
            if normalized:  # Skip empty values
                unique_values.add(normalized)

        if len(unique_values) > 1:
            # Conflict detected!
            conflicting_fields.append(field_name)

            # Build conflict details
            values = []
            sources = []
            confidences = []

            for record in records:
                values.append(record.extracted_value)
                # Convert Decimal to float for JSON serialization
                conf_float = float(record.confidence) if record.confidence else 0.0
                sources.append({
                    "source_id": str(record.source.id) if record.source else None,
                    "source_url": record.source.url if record.source else None,
                    "confidence": conf_float,
                })
                confidences.append(conf_float)

            conflict_details[field_name] = {
                "values": values,
                "sources": sources,
                "confidences": confidences,
            }

    return {
        "has_conflicts": len(conflicting_fields) > 0,
        "conflicting_fields": conflicting_fields,
        "conflict_details": conflict_details,
    }


class ConflictDetector:
    """
    Service class for detecting and managing conflicts.

    Usage:
        detector = ConflictDetector()
        detector.update_product_conflicts(product)
    """

    def __init__(self, min_confidence: float = 0.0):
        """
        Initialize the ConflictDetector.

        Args:
            min_confidence: Minimum confidence threshold for values
        """
        self.min_confidence = min_confidence

    def detect(self, product) -> Dict[str, Any]:
        """
        Detect conflicts for a product.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Conflict detection result dictionary
        """
        return detect_conflicts(product, self.min_confidence)

    def update_product_conflicts(self, product) -> bool:
        """
        Detect conflicts and update the product's conflict fields.

        Args:
            product: DiscoveredProduct instance

        Returns:
            True if conflicts were found, False otherwise
        """
        conflicts = self.detect(product)

        # Update product fields
        product.has_conflicts = conflicts["has_conflicts"]

        if conflicts["has_conflicts"]:
            product.conflict_details = conflicts["conflict_details"]
        else:
            product.conflict_details = {}

        product.save(update_fields=["has_conflicts", "conflict_details"])

        if conflicts["has_conflicts"]:
            logger.info(
                f"Product {product.id} has conflicts in fields: "
                f"{', '.join(conflicts['conflicting_fields'])}"
            )

        return conflicts["has_conflicts"]

    def get_conflicting_products(self, queryset: Optional[QuerySet] = None) -> QuerySet:
        """
        Get all products with conflicts.

        Args:
            queryset: Optional base queryset to filter

        Returns:
            QuerySet of products with has_conflicts=True
        """
        from crawler.models import DiscoveredProduct

        if queryset is None:
            queryset = DiscoveredProduct.objects.all()

        return queryset.filter(has_conflicts=True)

    def resolve_conflict(
        self,
        product,
        field_name: str,
        resolved_value: Any,
        resolution_reason: str = "manual",
    ) -> None:
        """
        Mark a conflict as resolved by setting the authoritative value.

        Args:
            product: DiscoveredProduct instance
            field_name: Name of the field to resolve
            resolved_value: The authoritative value to use
            resolution_reason: Reason for resolution (manual, highest_confidence, etc.)
        """
        # Update the field on the product
        if hasattr(product, field_name):
            setattr(product, field_name, resolved_value)

        # Update conflict details to mark as resolved
        if product.conflict_details and field_name in product.conflict_details:
            product.conflict_details[field_name]["resolved"] = True
            product.conflict_details[field_name]["resolved_value"] = str(resolved_value)
            product.conflict_details[field_name]["resolution_reason"] = resolution_reason

        # Check if all conflicts are resolved
        all_resolved = True
        if product.conflict_details:
            for field, details in product.conflict_details.items():
                if not details.get("resolved", False):
                    all_resolved = False
                    break

        if all_resolved:
            product.has_conflicts = False

        product.save()

        logger.info(
            f"Resolved conflict for product {product.id}, "
            f"field {field_name} = {resolved_value} ({resolution_reason})"
        )


def auto_resolve_by_confidence(product, min_confidence_gap: float = 0.2) -> int:
    """
    Automatically resolve conflicts where one source has significantly
    higher confidence than others.

    Args:
        product: DiscoveredProduct instance
        min_confidence_gap: Minimum difference in confidence to auto-resolve

    Returns:
        Number of conflicts resolved
    """
    from crawler.models import ProductFieldSource

    if not product.has_conflicts or not product.conflict_details:
        return 0

    resolved_count = 0
    detector = ConflictDetector()

    for field_name, details in product.conflict_details.items():
        if details.get("resolved"):
            continue

        confidences = details.get("confidences", [])
        if len(confidences) < 2:
            continue

        # Sort confidences descending
        sorted_conf = sorted(confidences, reverse=True)
        highest = sorted_conf[0]
        second = sorted_conf[1]

        # Check if gap is sufficient
        if highest - second >= min_confidence_gap:
            # Find the value with highest confidence
            for i, conf in enumerate(confidences):
                if conf == highest:
                    best_value = details["values"][i]
                    detector.resolve_conflict(
                        product,
                        field_name,
                        best_value,
                        f"auto_confidence_gap_{min_confidence_gap}"
                    )
                    resolved_count += 1
                    break

    return resolved_count
