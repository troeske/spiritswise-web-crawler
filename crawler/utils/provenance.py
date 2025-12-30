"""
Field provenance utility functions.

Task Group 8: Per-Field Provenance Tracking

Provides utility functions for querying field provenance data from
ProductFieldSource records. Enables easy lookup of which sources
contributed to each field value, with confidence scores for conflict
detection and data quality assessment.
"""

from dataclasses import dataclass
from typing import List, Optional, Union
from uuid import UUID

from django.db.models import QuerySet


@dataclass
class FieldProvenanceResult:
    """
    Result of a field provenance query.

    Attributes:
        field_name: Name of the field
        source_count: Number of sources that provided values for this field
        sources: QuerySet or list of ProductFieldSource records
        has_conflicts: True if sources provide different values
        highest_confidence: The highest confidence score among sources
        highest_confidence_value: The value from the highest-confidence source
    """

    field_name: str
    source_count: int
    sources: Union[QuerySet, List]
    has_conflicts: bool
    highest_confidence: Optional[float]
    highest_confidence_value: Optional[str]


def get_field_provenance(
    product,
    field_name: str,
    include_low_confidence: bool = True,
    min_confidence: float = 0.0,
) -> FieldProvenanceResult:
    """
    Get all sources that contributed to a specific field for a product.

    This function retrieves ProductFieldSource records for a given product
    and field, enabling:
    - Tracking which sources provided the field value
    - Conflict detection when sources provide different values
    - Confidence-based source prioritization

    Args:
        product: DiscoveredProduct instance or UUID
        field_name: Name of the field to look up (e.g., 'abv', 'region', 'primary_aromas')
        include_low_confidence: If False, filter out sources with confidence < min_confidence
        min_confidence: Minimum confidence threshold (default 0.0)

    Returns:
        FieldProvenanceResult containing:
        - source_count: Number of sources found
        - sources: QuerySet of ProductFieldSource records ordered by confidence (desc)
        - has_conflicts: True if multiple sources provide different values
        - highest_confidence: The highest confidence score
        - highest_confidence_value: The value from the most confident source

    Example:
        >>> from crawler.utils.provenance import get_field_provenance
        >>> result = get_field_provenance(product, "abv")
        >>> print(f"ABV has {result.source_count} sources")
        >>> if result.has_conflicts:
        ...     print("Warning: Sources disagree on ABV value")
        >>> print(f"Best value: {result.highest_confidence_value} ({result.highest_confidence:.0%} confidence)")
    """
    from crawler.models import ProductFieldSource, DiscoveredProduct

    # Handle UUID or model instance
    if isinstance(product, UUID):
        product_id = product
    elif isinstance(product, str):
        product_id = UUID(product)
    elif isinstance(product, DiscoveredProduct):
        product_id = product.id
    else:
        raise TypeError(f"product must be DiscoveredProduct, UUID, or str, got {type(product)}")

    # Build the query
    queryset = ProductFieldSource.objects.filter(
        product_id=product_id,
        field_name=field_name,
    ).select_related("source").order_by("-confidence")

    # Apply confidence filter if requested
    if not include_low_confidence or min_confidence > 0:
        queryset = queryset.filter(confidence__gte=min_confidence)

    # Convert to list for analysis (we need to iterate)
    sources = list(queryset)
    source_count = len(sources)

    # Determine if there are conflicts (different extracted values)
    has_conflicts = False
    unique_values = set()
    for source in sources:
        unique_values.add(source.extracted_value)
    if len(unique_values) > 1:
        has_conflicts = True

    # Get highest confidence source info
    highest_confidence = None
    highest_confidence_value = None
    if sources:
        top_source = sources[0]  # Already sorted by confidence desc
        highest_confidence = top_source.confidence
        highest_confidence_value = top_source.extracted_value

    return FieldProvenanceResult(
        field_name=field_name,
        source_count=source_count,
        sources=sources,
        has_conflicts=has_conflicts,
        highest_confidence=highest_confidence,
        highest_confidence_value=highest_confidence_value,
    )


def get_all_field_provenance(product) -> dict:
    """
    Get provenance information for all fields of a product.

    Args:
        product: DiscoveredProduct instance or UUID

    Returns:
        Dictionary mapping field_name to FieldProvenanceResult

    Example:
        >>> provenance = get_all_field_provenance(product)
        >>> for field_name, result in provenance.items():
        ...     if result.has_conflicts:
        ...         print(f"Conflict in {field_name}")
    """
    from crawler.models import ProductFieldSource, DiscoveredProduct

    # Handle UUID or model instance
    if isinstance(product, UUID):
        product_id = product
    elif isinstance(product, str):
        product_id = UUID(product)
    elif isinstance(product, DiscoveredProduct):
        product_id = product.id
    else:
        raise TypeError(f"product must be DiscoveredProduct, UUID, or str, got {type(product)}")

    # Get all unique field names for this product
    field_names = ProductFieldSource.objects.filter(
        product_id=product_id
    ).values_list("field_name", flat=True).distinct()

    # Build provenance results for each field
    results = {}
    for field_name in field_names:
        results[field_name] = get_field_provenance(product_id, field_name)

    return results


def detect_field_conflicts(product, conflict_threshold: float = 0.5) -> List[str]:
    """
    Detect fields with conflicting values from different sources.

    A conflict is detected when:
    1. Multiple sources provide different values for the same field
    2. At least one source has confidence >= conflict_threshold

    Args:
        product: DiscoveredProduct instance or UUID
        conflict_threshold: Minimum confidence for a source to trigger conflict detection

    Returns:
        List of field names that have conflicts

    Example:
        >>> conflicts = detect_field_conflicts(product)
        >>> if conflicts:
        ...     print(f"Review needed for fields: {', '.join(conflicts)}")
    """
    all_provenance = get_all_field_provenance(product)

    conflicts = []
    for field_name, result in all_provenance.items():
        if result.has_conflicts:
            # Check if any conflicting source has sufficient confidence
            if result.highest_confidence and result.highest_confidence >= conflict_threshold:
                conflicts.append(field_name)

    return conflicts
