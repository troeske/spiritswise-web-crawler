"""
ECP (Enrichment Completion Percentage) Calculator Service.

V3 Feature: Calculates enrichment completion by field group.

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ECPCalculator:
    """
    Calculates Enrichment Completion Percentage (ECP) by field group.

    ECP tracks how complete a product's data is across different field groups
    (e.g., basic_product_info, tasting_nose, cask_info).

    Each field group has:
    - populated: count of fields with values
    - total: total fields in group
    - percentage: (populated/total) * 100
    - missing: list of missing field names

    Total ECP is the weighted average across all active groups.
    """

    def __init__(self):
        """Initialize ECPCalculator with empty cache."""
        self._field_groups_cache: Dict[str, List[Dict]] = {}

    def calculate_ecp_by_group(
        self,
        product_data: Dict[str, Any],
        field_groups: List[Dict],
    ) -> Dict[str, Dict]:
        """
        Calculate ECP for each field group.

        Args:
            product_data: Dict of field_name -> value
            field_groups: List of field group configs, each with:
                - group_key: str
                - fields: List[str]
                - is_active: bool

        Returns:
            Dict mapping group_key to ECP data:
            {
                "group_key": {
                    "populated": int,
                    "total": int,
                    "percentage": float,
                    "missing": List[str]
                },
                ...
            }
        """
        populated_fields = self._get_populated_fields(product_data)
        result = {}

        for group in field_groups:
            # Skip inactive groups
            if not group.get("is_active", True):
                continue

            group_key = group.get("group_key")
            fields = group.get("fields", [])

            if not group_key or not fields:
                continue

            # Count populated and missing
            group_populated = 0
            group_missing = []

            for field in fields:
                if field in populated_fields:
                    group_populated += 1
                else:
                    group_missing.append(field)

            total = len(fields)
            percentage = (group_populated / total * 100) if total > 0 else 0.0

            result[group_key] = {
                "populated": group_populated,
                "total": total,
                "percentage": round(percentage, 2),
                "missing": group_missing,
            }

        return result

    def calculate_total_ecp(
        self,
        ecp_by_group: Dict[str, Dict],
    ) -> float:
        """
        Calculate total ECP across all groups.

        Args:
            ecp_by_group: Dict from calculate_ecp_by_group()

        Returns:
            Total ECP percentage (0-100)
        """
        if not ecp_by_group:
            return 0.0

        total_populated = 0
        total_fields = 0

        for group_data in ecp_by_group.values():
            total_populated += group_data.get("populated", 0)
            total_fields += group_data.get("total", 0)

        if total_fields == 0:
            return 0.0

        return round(total_populated / total_fields * 100, 2)

    def get_missing_fields_by_group(
        self,
        product_data: Dict[str, Any],
        field_groups: List[Dict],
    ) -> Dict[str, List[str]]:
        """
        Get missing fields organized by group.

        Args:
            product_data: Dict of field_name -> value
            field_groups: List of field group configs

        Returns:
            Dict mapping group_key to list of missing field names
        """
        ecp_by_group = self.calculate_ecp_by_group(product_data, field_groups)

        return {
            group_key: group_data.get("missing", [])
            for group_key, group_data in ecp_by_group.items()
        }

    def build_ecp_json(
        self,
        product_data: Dict[str, Any],
        field_groups: List[Dict],
    ) -> Dict[str, Any]:
        """
        Build the complete ECP JSON structure for storage.

        Args:
            product_data: Dict of field_name -> value
            field_groups: List of field group configs

        Returns:
            Complete ECP JSON with groups, total, and timestamp
        """
        ecp_by_group = self.calculate_ecp_by_group(product_data, field_groups)
        total_ecp = self.calculate_total_ecp(ecp_by_group)

        # Calculate overall totals
        total_populated = sum(g.get("populated", 0) for g in ecp_by_group.values())
        total_fields = sum(g.get("total", 0) for g in ecp_by_group.values())

        result = dict(ecp_by_group)
        result["total"] = {
            "populated": total_populated,
            "total": total_fields,
            "percentage": total_ecp,
        }
        result["last_updated"] = datetime.now(timezone.utc).isoformat()

        return result

    def _get_populated_fields(self, data: Dict[str, Any]) -> Set[str]:
        """
        Get set of fields that have non-null, non-empty values.

        Args:
            data: Dict of field_name -> value

        Returns:
            Set of field names with valid values
        """
        populated = set()

        for field_name, value in data.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            populated.add(field_name)

        return populated

    def load_field_groups(
        self,
        product_type_config,
    ) -> List[Dict]:
        """
        Load field groups from a ProductTypeConfig model instance.

        Args:
            product_type_config: ProductTypeConfig model instance

        Returns:
            List of field group dicts with keys:
            - group_key: str
            - display_name: str
            - fields: List[str]
            - is_active: bool
        """
        # Query active field groups, ordered by sort_order
        field_groups = product_type_config.field_groups.filter(
            is_active=True
        ).order_by("sort_order")

        # Convert to dicts
        result = []
        for fg in field_groups:
            result.append({
                "group_key": fg.group_key,
                "display_name": fg.display_name,
                "fields": fg.fields,
                "is_active": fg.is_active,
            })

        return result

    def load_field_groups_for_product_type(
        self,
        product_type: str,
    ) -> List[Dict]:
        """
        Load field groups for a product type string.

        Uses caching to avoid repeated database queries.

        Args:
            product_type: Product type string (e.g., "whiskey", "port_wine")

        Returns:
            List of field group dicts, or empty list if not found
        """
        # Check cache first
        if product_type in self._field_groups_cache:
            return self._field_groups_cache[product_type]

        try:
            from crawler.models import ProductTypeConfig
            config = ProductTypeConfig.objects.get(product_type=product_type)
            field_groups = self.load_field_groups(config)
            self._field_groups_cache[product_type] = field_groups
            return field_groups
        except ProductTypeConfig.DoesNotExist:
            logger.warning("ProductTypeConfig not found for: %s", product_type)
            return []

    def clear_cache(self) -> None:
        """Clear the field groups cache."""
        self._field_groups_cache = {}


# Singleton instance
_ecp_calculator: Optional[ECPCalculator] = None


def get_ecp_calculator() -> ECPCalculator:
    """Get singleton ECPCalculator instance."""
    global _ecp_calculator
    if _ecp_calculator is None:
        _ecp_calculator = ECPCalculator()
    return _ecp_calculator


def reset_ecp_calculator() -> None:
    """Reset singleton for testing."""
    global _ecp_calculator
    _ecp_calculator = None
