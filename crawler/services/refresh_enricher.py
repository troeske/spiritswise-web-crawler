"""
RefreshEnricher Service for Single Product Enrichment Flow.

Task 4.1: Handles re-enrichment of existing products with focus on recent data.

Features:
- Confidence-aware field merging
- Identity field preservation (name, brand never overwritten)
- Array field union-merge with deduplication
- Recent review search templates

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 5.2, 5.3
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from asgiref.sync import sync_to_async

from crawler.models import DiscoveredProduct

logger = logging.getLogger(__name__)


# Identity fields that should never be overwritten
IDENTITY_FIELDS: Set[str] = {"name", "brand", "gtin", "fingerprint"}

# Array fields that should be union-merged
ARRAY_FIELDS: Set[str] = {
    "primary_aromas",
    "secondary_aromas",
    "finish_flavors",
    "palate_flavors",
    "awards",
    "food_pairings",
    "recommendations",
    "discovery_sources",
}


def get_recent_search_templates(year: int) -> List[str]:
    """
    Get search templates focused on recent reviews.

    Args:
        year: Current year for filtering

    Returns:
        List of search templates with year placeholders filled
    """
    previous_year = year - 1

    return [
        "{brand} {name} review " + str(year),
        "{brand} {name} review " + str(previous_year),
        "{name} latest review tasting notes",
        "{name} " + str(year) + " tasting",
        "{brand} {name} recent review",
        "{name} new release " + str(year),
    ]


@dataclass
class RefreshResult:
    """Result of a product refresh operation."""

    success: bool = True
    product_data: Dict[str, Any] = field(default_factory=dict)
    fields_enriched: List[str] = field(default_factory=list)
    fields_preserved: List[str] = field(default_factory=list)
    confidences: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None


class RefreshEnricher:
    """
    Service for refreshing existing products with recent data.

    Handles:
    - Confidence-aware field merging
    - Identity field preservation
    - Array field union-merge
    - Recent review prioritization
    """

    def __init__(self):
        """Initialize RefreshEnricher."""
        pass

    async def refresh_product(
        self,
        existing_product: DiscoveredProduct,
        new_extraction: Dict[str, Any],
        new_confidences: Dict[str, float],
        focus_recent: bool = True,
    ) -> RefreshResult:
        """
        Refresh an existing product with new extracted data.

        Args:
            existing_product: Existing DiscoveredProduct to refresh
            new_extraction: New extracted data from recent sources
            new_confidences: Confidence scores for new data
            focus_recent: Whether to prioritize recency in merge decisions

        Returns:
            RefreshResult with merged data and statistics
        """
        result = RefreshResult()

        try:
            # Get existing data and confidences
            existing_data = await self._get_product_data(existing_product)
            existing_confidences = await self._get_field_confidences(existing_product)

            # Merge data
            merged_data, merged_confidences = await self._merge_with_existing(
                existing_data, existing_confidences,
                new_extraction, new_confidences
            )

            # Track changes
            for field_name in merged_data:
                if field_name not in existing_data:
                    result.fields_enriched.append(field_name)
                elif merged_data[field_name] != existing_data.get(field_name):
                    if field_name in IDENTITY_FIELDS:
                        result.fields_preserved.append(field_name)
                    else:
                        result.fields_enriched.append(field_name)

            result.product_data = merged_data
            result.confidences = merged_confidences
            result.success = True

        except Exception as e:
            logger.exception("Error refreshing product: %s", e)
            result.success = False
            result.error = str(e)

        return result

    async def _merge_with_existing(
        self,
        existing_data: Dict[str, Any],
        existing_confidences: Dict[str, float],
        new_data: Dict[str, Any],
        new_confidences: Dict[str, float],
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Merge new data with existing data using confidence scores.

        Rules:
        1. Identity fields (name, brand, gtin) are NEVER overwritten
        2. Array fields are union-merged with deduplication
        3. Other fields: higher confidence wins
        4. New fields are always added

        Args:
            existing_data: Current product data
            existing_confidences: Confidence scores for existing fields
            new_data: New extracted data
            new_confidences: Confidence scores for new fields

        Returns:
            Tuple of (merged_data, merged_confidences)
        """
        merged = existing_data.copy()
        confidences = existing_confidences.copy()

        for field_name, new_value in new_data.items():
            if new_value is None:
                continue

            existing_value = existing_data.get(field_name)
            existing_conf = existing_confidences.get(field_name, 0.0)
            new_conf = new_confidences.get(field_name, 0.5)

            # Rule 1: Identity fields never overwritten
            if field_name in IDENTITY_FIELDS and existing_value:
                continue

            # Rule 2: Array fields - union merge
            if field_name in ARRAY_FIELDS:
                merged[field_name] = self._merge_arrays(existing_value, new_value)
                confidences[field_name] = max(existing_conf, new_conf)
                continue

            # Rule 3: New field - always add
            if existing_value is None or field_name not in existing_data:
                merged[field_name] = new_value
                confidences[field_name] = new_conf
                continue

            # Rule 4: Existing field - higher confidence wins
            if new_conf > existing_conf:
                merged[field_name] = new_value
                confidences[field_name] = new_conf
            # else keep existing

        return merged, confidences

    def _merge_arrays(
        self,
        existing: Optional[List[Any]],
        new: Optional[List[Any]],
    ) -> List[Any]:
        """
        Union-merge two arrays with deduplication.

        Args:
            existing: Existing array values
            new: New array values

        Returns:
            Union of both arrays without duplicates
        """
        existing_list = existing if isinstance(existing, list) else []
        new_list = new if isinstance(new, list) else []

        # Use set for deduplication while preserving order for existing
        seen = set()
        result = []

        for item in existing_list:
            key = str(item).lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(item)

        for item in new_list:
            key = str(item).lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    async def _get_product_data(
        self,
        product: DiscoveredProduct,
    ) -> Dict[str, Any]:
        """
        Extract product data as dictionary.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Dictionary of product field values
        """
        @sync_to_async
        def get_data():
            data = {}

            # Core fields
            data["name"] = product.name
            data["brand"] = product.brand.name if product.brand else None
            data["product_type"] = product.product_type
            data["status"] = product.status

            # Numeric fields
            if product.abv:
                data["abv"] = product.abv
            if product.age_statement:
                data["age_statement"] = product.age_statement
            if product.bottle_size_ml:
                data["bottle_size_ml"] = product.bottle_size_ml

            # Text fields
            if product.description:
                data["description"] = product.description
            if product.country:
                data["country"] = product.country
            if product.region:
                data["region"] = product.region

            # Array fields
            if product.primary_aromas:
                data["primary_aromas"] = product.primary_aromas
            if product.secondary_aromas:
                data["secondary_aromas"] = product.secondary_aromas
            if product.finish_flavors:
                data["finish_flavors"] = product.finish_flavors
            if product.palate_flavors:
                data["palate_flavors"] = product.palate_flavors
            if product.food_pairings:
                data["food_pairings"] = product.food_pairings

            return data

        return await get_data()

    async def _get_field_confidences(
        self,
        product: DiscoveredProduct,
    ) -> Dict[str, float]:
        """
        Get field confidence scores for a product.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Dictionary of field name to confidence score
        """
        @sync_to_async
        def get_confidences():
            # Try to get from field_provenance if available
            if hasattr(product, 'field_provenance') and product.field_provenance:
                confidences = {}
                for field_name, provenance in product.field_provenance.items():
                    if isinstance(provenance, dict):
                        confidences[field_name] = provenance.get("confidence", 0.7)
                    else:
                        confidences[field_name] = 0.7
                return confidences

            # Default confidences based on status
            base_confidence = 0.5
            if product.status == "complete":
                base_confidence = 0.9
            elif product.status == "enriched":
                base_confidence = 0.8
            elif product.status == "baseline":
                base_confidence = 0.7
            elif product.status == "partial":
                base_confidence = 0.6

            return {
                "name": base_confidence,
                "brand": base_confidence,
            }

        return await get_confidences()


# Singleton instance
_refresh_enricher: Optional[RefreshEnricher] = None


def get_refresh_enricher() -> RefreshEnricher:
    """Get singleton RefreshEnricher instance."""
    global _refresh_enricher
    if _refresh_enricher is None:
        _refresh_enricher = RefreshEnricher()
    return _refresh_enricher


def reset_refresh_enricher() -> None:
    """Reset singleton (for testing)."""
    global _refresh_enricher
    _refresh_enricher = None
