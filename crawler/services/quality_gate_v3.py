"""
V3 Quality Gate Service

Configuration-driven quality assessment using QualityGateConfig from database.

V3 Changes from V2:
- New status ordering: REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE
- BASELINE replaces old COMPLETE (required fields met)
- COMPLETE now means 90% ECP threshold
- Simplified status determination (no any-of logic for PARTIAL/BASELINE)
- OR logic for ENRICHED status (complexity OR overall_complexity, etc.)
- Ruby exception for port wine (waives indication_age requirement)

Status Levels (ascending):
    REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple

from asgiref.sync import sync_to_async

from crawler.models import QualityGateConfig, ProductTypeConfig
from crawler.services.config_service import get_config_service
from crawler.services.ecp_calculator import get_ecp_calculator

logger = logging.getLogger(__name__)


class ProductStatus(str, Enum):
    """
    Product data quality status.

    V3 Status Hierarchy (lowest to highest):
        REJECTED  - Missing required field (name)
        SKELETON  - Has name only
        PARTIAL   - Has basic required fields
        BASELINE  - All required fields met (formerly COMPLETE in V2)
        ENRICHED  - Baseline + mouthfeel + OR fields satisfied
        COMPLETE  - 90% ECP threshold reached
    """
    REJECTED = "rejected"
    SKELETON = "skeleton"
    PARTIAL = "partial"
    BASELINE = "baseline"  # NEW in V3 - formerly COMPLETE in V2
    ENRICHED = "enriched"
    COMPLETE = "complete"  # V3 meaning: 90% ECP threshold

    def __lt__(self, other: "ProductStatus") -> bool:
        if isinstance(other, ProductStatus):
            order = [
                self.REJECTED,
                self.SKELETON,
                self.PARTIAL,
                self.BASELINE,
                self.ENRICHED,
                self.COMPLETE,
            ]
            return order.index(self) < order.index(other)
        return NotImplemented

    def __le__(self, other: "ProductStatus") -> bool:
        if isinstance(other, ProductStatus):
            return self == other or self < other
        return NotImplemented

    def __gt__(self, other: "ProductStatus") -> bool:
        if isinstance(other, ProductStatus):
            return other < self
        return NotImplemented

    def __ge__(self, other: "ProductStatus") -> bool:
        if isinstance(other, ProductStatus):
            return self == other or self > other
        return NotImplemented


@dataclass
class QualityAssessment:
    """Result of quality gate assessment."""
    status: ProductStatus
    completeness_score: float  # 0.0 - 1.0
    populated_fields: List[str] = field(default_factory=list)
    missing_required_fields: List[str] = field(default_factory=list)
    missing_any_of_fields: List[str] = field(default_factory=list)  # Deprecated in V3
    missing_or_fields: List[List[str]] = field(default_factory=list)  # V3: OR field groups
    enrichment_priority: int = 5  # 1-10, higher = more urgent
    needs_enrichment: bool = True
    rejection_reason: Optional[str] = None
    low_confidence_fields: List[str] = field(default_factory=list)
    ecp_by_group: Dict[str, Dict] = field(default_factory=dict)  # V3: ECP by field group
    ecp_total: float = 0.0  # V3: Total ECP percentage


class QualityGateV3:
    """
    V3 Quality Gate using database-backed configuration.

    Assesses extracted product data and determines:
    - Status level (REJECTED/SKELETON/PARTIAL/BASELINE/ENRICHED/COMPLETE)
    - Completeness score
    - Missing fields
    - Enrichment priority
    - ECP (Enrichment Completion Percentage)

    V3 Status Logic:
        SKELETON: Has name
        PARTIAL: Has ALL partial_required_fields
        BASELINE: Has ALL baseline_required_fields AND OR field requirements (with exceptions)
        ENRICHED: BASELINE + mouthfeel + enriched_or_fields satisfied
        COMPLETE: ECP >= 90%
    """

    CONFIDENCE_THRESHOLD = 0.5
    ECP_COMPLETE_THRESHOLD = 90.0  # V3: 90% ECP for COMPLETE status

    # Default thresholds when no database config exists
    DEFAULT_SKELETON_REQUIRED = ["name"]
    DEFAULT_PARTIAL_REQUIRED = ["name", "brand", "abv", "region", "country", "category"]
    DEFAULT_BASELINE_REQUIRED = [
        "name", "brand", "abv", "region", "country", "category",
        "volume_ml", "description", "primary_aromas", "finish_flavors",
        "age_statement", "primary_cask", "palate_flavors"
    ]
    DEFAULT_ENRICHED_REQUIRED = ["mouthfeel"]
    DEFAULT_ENRICHED_OR_FIELDS = [
        ["complexity", "overall_complexity"],
        ["finishing_cask", "maturation_notes"]
    ]

    # Categories where primary_cask is NOT required for baseline
    # (blended whiskies use dozens/hundreds of casks from multiple distilleries)
    CATEGORIES_NO_PRIMARY_CASK_REQUIRED = [
        "blended scotch whisky",
        "blended scotch",
        "blended whisky",
        "blended whiskey",
        "blended malt",
        "blended malt scotch whisky",
        "blended grain whisky",
        "canadian whisky",
        "canadian whiskey",
    ]

    # Categories where region is NOT required for baseline
    # (blended whiskies source grains from multiple regions across Scotland)
    CATEGORIES_NO_REGION_REQUIRED = [
        "blended scotch whisky",
        "blended scotch",
        "blended whisky",
        "blended whiskey",
        "blended malt",
        "blended malt scotch whisky",
        "blended grain whisky",
    ]

    def __init__(self, config_service=None):
        """Initialize with optional config service for testing."""
        self.config_service = config_service or get_config_service()

    def assess(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None,
        ecp_total: Optional[float] = None
    ) -> QualityAssessment:
        """
        Assess extracted data quality.

        Args:
            extracted_data: Dict of field_name -> value
            product_type: Product type (whiskey, port_wine)
            field_confidences: Optional dict of field_name -> confidence (0-1)
            product_category: Optional product category
            ecp_total: Optional pre-calculated ECP total percentage

        Returns:
            QualityAssessment with status, score, and recommendations
        """
        logger.debug(
            "Assessing quality for product_type=%s with %d fields",
            product_type,
            len(extracted_data)
        )

        confident_data = self._filter_by_confidence(extracted_data, field_confidences)
        populated = self._get_populated_fields(confident_data)

        logger.debug("Populated fields after confidence filter: %s", populated)

        config = self._get_quality_gate_config(product_type)
        if config:
            logger.debug("Using database config for product_type=%s", product_type)
        else:
            logger.debug("Using default config for product_type=%s", product_type)

        # Calculate ECP if not provided and field groups are available
        ecp_by_group = {}
        calculated_ecp_total = ecp_total
        if calculated_ecp_total is None:
            try:
                ecp_calculator = get_ecp_calculator()
                field_groups = ecp_calculator.load_field_groups_for_product_type(product_type)
                if field_groups:
                    ecp_by_group = ecp_calculator.calculate_ecp_by_group(confident_data, field_groups)
                    calculated_ecp_total = ecp_calculator.calculate_total_ecp(ecp_by_group)
                    logger.debug("Calculated ECP: %.2f%% from %d groups", calculated_ecp_total, len(field_groups))
            except Exception as e:
                logger.warning("Failed to calculate ECP: %s", e)
                calculated_ecp_total = 0.0

        # Check rejection condition: no name means reject
        if "name" not in populated:
            logger.info("Product rejected: missing required field 'name'")
            return QualityAssessment(
                status=ProductStatus.REJECTED,
                completeness_score=0.0,
                populated_fields=list(populated),
                missing_required_fields=["name"],
                rejection_reason="Missing required field: name",
                needs_enrichment=False
            )

        # Get product style for exception checking (port wine)
        product_style = extracted_data.get("style", "").lower() if extracted_data.get("style") else None

        # Get category from extracted data if not provided
        effective_category = product_category or extracted_data.get("category")

        status = self._determine_status(
            populated, config, product_type, product_style, calculated_ecp_total, effective_category
        )
        logger.debug("Determined status: %s (category=%s)", status.value, effective_category)

        schema_fields = self._get_schema_fields(product_type)
        completeness = self._calculate_completeness(confident_data, schema_fields)

        missing_required, missing_or = self._get_missing_for_upgrade(
            populated, status, config, product_type, product_style, effective_category
        )

        priority = self._calculate_enrichment_priority(status, completeness)
        needs_enrichment = status < ProductStatus.COMPLETE

        low_confidence = self._get_low_confidence_fields(field_confidences)

        assessment = QualityAssessment(
            status=status,
            completeness_score=completeness,
            populated_fields=list(populated),
            missing_required_fields=missing_required,
            missing_or_fields=missing_or,
            enrichment_priority=priority,
            needs_enrichment=needs_enrichment,
            low_confidence_fields=low_confidence,
            ecp_by_group=ecp_by_group,
            ecp_total=calculated_ecp_total or 0.0
        )

        logger.info(
            "Quality assessment complete: status=%s, score=%.2f, priority=%d",
            status.value,
            completeness,
            priority
        )

        return assessment

    def _filter_by_confidence(
        self,
        data: Dict[str, Any],
        confidences: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Filter out fields with confidence below threshold."""
        if not confidences:
            return data

        def get_confidence(key: str) -> float:
            """Get confidence value, handling string values."""
            val = confidences.get(key)
            if val is None:
                return 1.0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 1.0

        filtered = {
            k: v for k, v in data.items()
            if get_confidence(k) >= self.CONFIDENCE_THRESHOLD
        }

        removed_count = len(data) - len(filtered)
        if removed_count > 0:
            logger.debug(
                "Filtered out %d low-confidence fields (threshold=%.2f)",
                removed_count,
                self.CONFIDENCE_THRESHOLD
            )

        return filtered

    def _get_populated_fields(self, data: Dict[str, Any]) -> Set[str]:
        """Get set of fields that have non-null, non-empty values."""
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

    def _get_quality_gate_config(self, product_type: str) -> Optional[QualityGateConfig]:
        """Get quality gate config from database."""
        try:
            config = self.config_service.get_quality_gate_config(product_type)
            if config is None:
                logger.debug("No quality gate config found for product_type=%s", product_type)
            return config
        except Exception as e:
            logger.warning(
                "Failed to load quality gate config for %s: %s",
                product_type,
                str(e)
            )
            return None

    def _check_all_required(
        self,
        populated: Set[str],
        required_fields: List[str]
    ) -> bool:
        """
        Check if ALL required fields are present.

        V3 simplification: No any-of logic, just ALL required.
        """
        for req_field in required_fields:
            if req_field not in populated:
                return False
        return True

    def _check_or_fields(
        self,
        populated: Set[str],
        or_field_groups: List[List[str]]
    ) -> bool:
        """
        Check if OR field requirements are satisfied.

        V3 OR logic: For each group, at least ONE field must be present.
        Example: [["complexity", "overall_complexity"]] - need complexity OR overall_complexity
        """
        for field_group in or_field_groups:
            # At least one field from this group must be present
            if not any(field in populated for field in field_group):
                return False
        return True

    def _check_or_field_exceptions(
        self,
        or_field_groups: List[List[str]],
        or_field_exceptions: Dict[str, List[str]],
        product_data: Dict[str, Any]
    ) -> List[List[str]]:
        """
        Filter OR field groups based on exceptions.

        V3: Ruby/Reserve Ruby port wine exception waives indication_age/harvest_year.
        """
        if not or_field_exceptions:
            return or_field_groups

        filtered_groups = []
        for field_group in or_field_groups:
            # Check if this group has an exception
            should_waive = False
            for exception_field, exception_values in or_field_exceptions.items():
                field_value = product_data.get(exception_field, "")
                if field_value and str(field_value).lower() in [v.lower() for v in exception_values]:
                    # Check if this exception applies to this field group
                    # Exception applies if the exception field's values match
                    # and this is the age-related field group
                    if "indication_age" in field_group or "harvest_year" in field_group:
                        should_waive = True
                        logger.debug(
                            "Waiving OR field group %s due to %s=%s exception",
                            field_group, exception_field, field_value
                        )
                        break

            if not should_waive:
                filtered_groups.append(field_group)

        return filtered_groups

    def _determine_status(
        self,
        populated: Set[str],
        config: Optional[QualityGateConfig],
        product_type: str,
        product_style: Optional[str] = None,
        ecp_total: Optional[float] = None,
        product_category: Optional[str] = None
    ) -> ProductStatus:
        """
        Determine the highest status level the data qualifies for.

        V3 Logic:
            SKELETON: Has name
            PARTIAL: Has ALL partial_required_fields
            BASELINE: Has ALL baseline_required_fields + baseline_or_fields (with exceptions)
            ENRICHED: BASELINE + enriched_required_fields + enriched_or_fields
            COMPLETE: ECP >= 90%
        """
        # Extract thresholds from config or use defaults
        if config:
            skeleton_req = config.skeleton_required_fields or self.DEFAULT_SKELETON_REQUIRED
            partial_req = config.partial_required_fields or self.DEFAULT_PARTIAL_REQUIRED
            baseline_req = config.baseline_required_fields or self.DEFAULT_BASELINE_REQUIRED
            baseline_or = config.baseline_or_fields or []
            baseline_exceptions = config.baseline_or_field_exceptions or {}
            enriched_req = config.enriched_required_fields or self.DEFAULT_ENRICHED_REQUIRED
            enriched_or = config.enriched_or_fields or self.DEFAULT_ENRICHED_OR_FIELDS
        else:
            skeleton_req = self.DEFAULT_SKELETON_REQUIRED
            partial_req = self.DEFAULT_PARTIAL_REQUIRED
            baseline_req = self.DEFAULT_BASELINE_REQUIRED
            baseline_or = []
            baseline_exceptions = {}
            enriched_req = self.DEFAULT_ENRICHED_REQUIRED
            enriched_or = self.DEFAULT_ENRICHED_OR_FIELDS

        # Adjust baseline requirements based on category
        # Blended whiskies don't require primary_cask (they use dozens/hundreds of casks)
        # and don't require region (they source from multiple regions)
        if product_category:
            category_lower = product_category.lower().strip()
            removed_fields = []
            if category_lower in self.CATEGORIES_NO_PRIMARY_CASK_REQUIRED:
                baseline_req = [f for f in baseline_req if f != "primary_cask"]
                removed_fields.append("primary_cask")
            if category_lower in self.CATEGORIES_NO_REGION_REQUIRED:
                baseline_req = [f for f in baseline_req if f != "region"]
                partial_req = [f for f in partial_req if f != "region"]
                removed_fields.append("region")
            if removed_fields:
                logger.debug(
                    "Category '%s' - removing %s from baseline requirements",
                    product_category, removed_fields
                )

        # Build product data dict for exception checking
        product_data = {"style": product_style} if product_style else {}

        # Check from highest status to lowest
        # COMPLETE requires 90% ECP
        if ecp_total is not None and ecp_total >= self.ECP_COMPLETE_THRESHOLD:
            return ProductStatus.COMPLETE

        # ENRICHED requires BASELINE + enriched_required + enriched_or_fields
        if (
            self._check_all_required(populated, baseline_req) and
            self._check_or_fields(
                populated,
                self._check_or_field_exceptions(baseline_or, baseline_exceptions, product_data)
            ) and
            self._check_all_required(populated, enriched_req) and
            self._check_or_fields(populated, enriched_or)
        ):
            return ProductStatus.ENRICHED

        # BASELINE requires all baseline_required_fields + baseline_or_fields (with exceptions)
        filtered_baseline_or = self._check_or_field_exceptions(baseline_or, baseline_exceptions, product_data)
        if (
            self._check_all_required(populated, baseline_req) and
            self._check_or_fields(populated, filtered_baseline_or)
        ):
            return ProductStatus.BASELINE

        # PARTIAL requires all partial_required_fields
        if self._check_all_required(populated, partial_req):
            return ProductStatus.PARTIAL

        # SKELETON requires all skeleton_required_fields
        if self._check_all_required(populated, skeleton_req):
            return ProductStatus.SKELETON

        return ProductStatus.REJECTED

    def _calculate_completeness(
        self,
        data: Dict[str, Any],
        schema_fields: List[str]
    ) -> float:
        """Calculate completeness score as ratio of populated to total fields."""
        if not schema_fields:
            return 0.0

        populated = self._get_populated_fields(data)
        schema_field_set = set(schema_fields)
        populated_in_schema = populated.intersection(schema_field_set)

        return len(populated_in_schema) / len(schema_fields)

    def _get_schema_fields(self, product_type: str) -> List[str]:
        """Get all field names for a product type from config."""
        try:
            schema = self.config_service.build_extraction_schema(product_type)
            return [f.get('field_name') or f.get('name') for f in schema if f]
        except Exception as e:
            logger.warning(
                "Failed to get schema fields for %s: %s, using defaults",
                product_type,
                str(e)
            )
            # Return default set of fields
            return list(set(
                self.DEFAULT_SKELETON_REQUIRED +
                self.DEFAULT_PARTIAL_REQUIRED +
                self.DEFAULT_BASELINE_REQUIRED
            ))

    def _get_missing_for_upgrade(
        self,
        populated: Set[str],
        current_status: ProductStatus,
        config: Optional[QualityGateConfig],
        product_type: str,
        product_style: Optional[str] = None,
        product_category: Optional[str] = None
    ) -> Tuple[List[str], List[List[str]]]:
        """
        Get fields needed to upgrade to next status level.

        Returns:
            Tuple of (missing_required_fields, missing_or_fields)
        """
        if config:
            partial_req = config.partial_required_fields or self.DEFAULT_PARTIAL_REQUIRED
            baseline_req = config.baseline_required_fields or self.DEFAULT_BASELINE_REQUIRED
            baseline_or = config.baseline_or_fields or []
            baseline_exceptions = config.baseline_or_field_exceptions or {}
            enriched_req = config.enriched_required_fields or self.DEFAULT_ENRICHED_REQUIRED
            enriched_or = config.enriched_or_fields or self.DEFAULT_ENRICHED_OR_FIELDS
        else:
            partial_req = self.DEFAULT_PARTIAL_REQUIRED
            baseline_req = self.DEFAULT_BASELINE_REQUIRED
            baseline_or = []
            baseline_exceptions = {}
            enriched_req = self.DEFAULT_ENRICHED_REQUIRED
            enriched_or = self.DEFAULT_ENRICHED_OR_FIELDS

        # Adjust baseline requirements based on category (blends don't need primary_cask or region)
        if product_category:
            category_lower = product_category.lower().strip()
            if category_lower in self.CATEGORIES_NO_PRIMARY_CASK_REQUIRED:
                baseline_req = [f for f in baseline_req if f != "primary_cask"]
            if category_lower in self.CATEGORIES_NO_REGION_REQUIRED:
                baseline_req = [f for f in baseline_req if f != "region"]
                partial_req = [f for f in partial_req if f != "region"]

        product_data = {"style": product_style} if product_style else {}

        if current_status == ProductStatus.REJECTED:
            return ["name"], []

        if current_status == ProductStatus.SKELETON:
            missing_req = [f for f in partial_req if f not in populated]
            return missing_req, []

        if current_status == ProductStatus.PARTIAL:
            missing_req = [f for f in baseline_req if f not in populated]
            # Check which OR fields are needed (with exceptions applied)
            filtered_or = self._check_or_field_exceptions(baseline_or, baseline_exceptions, product_data)
            missing_or = [
                group for group in filtered_or
                if not any(f in populated for f in group)
            ]
            return missing_req, missing_or

        if current_status == ProductStatus.BASELINE:
            missing_req = [f for f in enriched_req if f not in populated]
            missing_or = [
                group for group in enriched_or
                if not any(f in populated for f in group)
            ]
            return missing_req, missing_or

        if current_status == ProductStatus.ENRICHED:
            # Need to reach 90% ECP for COMPLETE
            return [], []

        # COMPLETE status - already at max
        return [], []

    def _calculate_enrichment_priority(
        self,
        status: ProductStatus,
        completeness: float
    ) -> int:
        """
        Calculate enrichment priority (1-10, higher = more urgent).

        Priority is based on status and completeness:
        - REJECTED/SKELETON with low completeness = 10
        - PARTIAL = 7-8
        - BASELINE = 5-6
        - ENRICHED = 3-4
        - COMPLETE = 1-2
        """
        base_priority = {
            ProductStatus.REJECTED: 10,
            ProductStatus.SKELETON: 9,
            ProductStatus.PARTIAL: 7,
            ProductStatus.BASELINE: 5,
            ProductStatus.ENRICHED: 3,
            ProductStatus.COMPLETE: 1,
        }.get(status, 5)

        # Adjust by completeness (lower completeness = higher priority)
        adjustment = int((1 - completeness) * 2)

        return min(10, max(1, base_priority + adjustment))

    def _get_low_confidence_fields(
        self,
        confidences: Optional[Dict[str, float]]
    ) -> List[str]:
        """Get list of fields with confidence below threshold."""
        if not confidences:
            return []

        low_confidence = []
        for field_name, conf in confidences.items():
            if conf is None:
                continue
            # Normalize confidence to float if it's a list (LLM may return array)
            if isinstance(conf, list):
                conf = sum(conf) / len(conf) if conf else 0.5
            elif not isinstance(conf, (int, float)):
                conf = 0.5
            if conf < self.CONFIDENCE_THRESHOLD:
                low_confidence.append(field_name)
        return low_confidence

    # Async-safe methods for use in async contexts

    async def aassess(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None,
        ecp_total: Optional[float] = None
    ) -> QualityAssessment:
        """
        Async-safe version of assess().

        Uses sync_to_async to wrap database calls, allowing this method
        to be called from async contexts without "You cannot call this
        from an async context" errors.

        Args:
            extracted_data: Dict of field_name -> value
            product_type: Product type (whiskey, port_wine)
            field_confidences: Optional dict of field_name -> confidence (0-1)
            product_category: Optional product category
            ecp_total: Optional pre-calculated ECP total percentage

        Returns:
            QualityAssessment with status, score, and recommendations
        """
        logger.debug(
            "Assessing quality (async) for product_type=%s with %d fields",
            product_type,
            len(extracted_data)
        )

        confident_data = self._filter_by_confidence(extracted_data, field_confidences)
        populated = self._get_populated_fields(confident_data)

        logger.debug("Populated fields after confidence filter: %s", populated)

        # Use async-safe config loading
        config = await self._aget_quality_gate_config(product_type)
        if config:
            logger.debug("Using database config for product_type=%s", product_type)
        else:
            logger.debug("Using default config for product_type=%s", product_type)

        # Calculate ECP if not provided (async-safe)
        calculated_ecp_total = ecp_total
        if calculated_ecp_total is None:
            try:
                calculated_ecp_total = await self._acalculate_ecp(confident_data, product_type)
                logger.debug("Calculated ECP (async): %.2f%%", calculated_ecp_total or 0.0)
            except Exception as e:
                logger.warning("Failed to calculate ECP (async): %s", e)
                calculated_ecp_total = 0.0
        ecp_total = calculated_ecp_total

        # Check rejection condition: no name means reject
        if "name" not in populated:
            logger.info("Product rejected: missing required field 'name'")
            return QualityAssessment(
                status=ProductStatus.REJECTED,
                completeness_score=0.0,
                populated_fields=list(populated),
                missing_required_fields=["name"],
                rejection_reason="Missing required field: name",
                needs_enrichment=False
            )

        # Get product style for exception checking (port wine)
        product_style = extracted_data.get("style", "").lower() if extracted_data.get("style") else None

        # Get category from extracted data if not provided
        effective_category = product_category or extracted_data.get("category")

        status = self._determine_status(
            populated, config, product_type, product_style, ecp_total, effective_category
        )
        logger.debug("Determined status: %s (category=%s)", status.value, effective_category)

        # Use async-safe schema fields loading
        schema_fields = await self._aget_schema_fields(product_type)
        completeness = self._calculate_completeness(confident_data, schema_fields)

        missing_required, missing_or = self._get_missing_for_upgrade(
            populated, status, config, product_type, product_style, effective_category
        )

        priority = self._calculate_enrichment_priority(status, completeness)
        needs_enrichment = status < ProductStatus.COMPLETE

        low_confidence = self._get_low_confidence_fields(field_confidences)

        assessment = QualityAssessment(
            status=status,
            completeness_score=completeness,
            populated_fields=list(populated),
            missing_required_fields=missing_required,
            missing_or_fields=missing_or,
            enrichment_priority=priority,
            needs_enrichment=needs_enrichment,
            low_confidence_fields=low_confidence,
            ecp_total=ecp_total or 0.0
        )

        logger.info(
            "Quality assessment complete: status=%s, score=%.2f, priority=%d",
            status.value,
            completeness,
            priority
        )

        return assessment

    async def _aget_quality_gate_config(self, product_type: str) -> Optional[QualityGateConfig]:
        """Async-safe version of _get_quality_gate_config."""
        try:
            config = await self.config_service.aget_quality_gate_config(product_type)
            if config is None:
                logger.debug("No quality gate config found for product_type=%s", product_type)
            return config
        except Exception as e:
            logger.warning(
                "Failed to load quality gate config for %s: %s",
                product_type,
                str(e)
            )
            return None

    async def _aget_schema_fields(self, product_type: str) -> List[str]:
        """Async-safe version of _get_schema_fields."""
        try:
            schema = await self.config_service.abuild_extraction_schema(product_type)
            return [f.get('field_name') or f.get('name') for f in schema if f]
        except Exception as e:
            logger.warning(
                "Failed to get schema fields for %s: %s, using defaults",
                product_type,
                str(e)
            )
            # Return default set of fields
            return list(set(
                self.DEFAULT_SKELETON_REQUIRED +
                self.DEFAULT_PARTIAL_REQUIRED +
                self.DEFAULT_BASELINE_REQUIRED
            ))

    async def _acalculate_ecp(
        self,
        confident_data: Dict[str, Any],
        product_type: str
    ) -> float:
        """
        Async-safe ECP calculation.

        Wraps the synchronous ECP calculator methods in sync_to_async.

        Args:
            confident_data: Product data with low-confidence fields filtered
            product_type: Product type string

        Returns:
            ECP percentage (0-100), or 0.0 if calculation fails
        """
        def _calculate_ecp_sync():
            ecp_calculator = get_ecp_calculator()
            field_groups = ecp_calculator.load_field_groups_for_product_type(product_type)
            if not field_groups:
                return 0.0
            ecp_by_group = ecp_calculator.calculate_ecp_by_group(confident_data, field_groups)
            return ecp_calculator.calculate_total_ecp(ecp_by_group)

        return await sync_to_async(_calculate_ecp_sync, thread_sensitive=True)()


# Singleton instance
_quality_gate_v3: Optional[QualityGateV3] = None


def get_quality_gate_v3() -> QualityGateV3:
    """Get singleton QualityGateV3 instance."""
    global _quality_gate_v3
    if _quality_gate_v3 is None:
        _quality_gate_v3 = QualityGateV3()
    return _quality_gate_v3


def reset_quality_gate_v3() -> None:
    """Reset singleton for testing."""
    global _quality_gate_v3
    _quality_gate_v3 = None
