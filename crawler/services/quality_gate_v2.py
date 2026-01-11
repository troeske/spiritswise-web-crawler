"""
V2 Quality Gate Service

Configuration-driven quality assessment using QualityGateConfig from database.

Status Logic:
    STATUS = (ALL required_fields present) AND (at least any_of_count from any_of_fields)

Status Levels (ascending):
    REJECTED < SKELETON < PARTIAL < COMPLETE < ENRICHED
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple

from asgiref.sync import sync_to_async

from crawler.models import QualityGateConfig, ProductTypeConfig
from crawler.services.config_service import get_config_service

logger = logging.getLogger(__name__)


class ProductStatus(str, Enum):
    """Product data quality status."""
    REJECTED = "rejected"
    SKELETON = "skeleton"
    PARTIAL = "partial"
    COMPLETE = "complete"
    ENRICHED = "enriched"

    def __lt__(self, other: "ProductStatus") -> bool:
        if isinstance(other, ProductStatus):
            order = [self.REJECTED, self.SKELETON, self.PARTIAL, self.COMPLETE, self.ENRICHED]
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
    missing_any_of_fields: List[str] = field(default_factory=list)
    enrichment_priority: int = 5  # 1-10, higher = more urgent
    needs_enrichment: bool = True
    rejection_reason: Optional[str] = None
    low_confidence_fields: List[str] = field(default_factory=list)


class QualityGateV2:
    """
    V2 Quality Gate using database-backed configuration.

    Assesses extracted product data and determines:
    - Status level (REJECTED/SKELETON/PARTIAL/COMPLETE/ENRICHED)
    - Completeness score
    - Missing fields
    - Enrichment priority

    Status Logic:
        Each status level has TWO requirements that must BOTH be met (AND logic):
        1. ALL required_fields must be present
        2. At least any_of_count fields from any_of_fields must be present

        Example for PARTIAL status:
            partial_required_fields = ["name", "brand"]
            partial_any_of_count = 2
            partial_any_of_fields = ["description", "abv", "region", "country"]

            Product is PARTIAL if:
            - Has "name" AND "brand" (all required fields)
            - AND has at least 2 of: description, abv, region, country
    """

    CONFIDENCE_THRESHOLD = 0.5

    # Default thresholds when no database config exists
    DEFAULT_SKELETON_REQUIRED = ["name"]
    DEFAULT_PARTIAL_REQUIRED = ["name", "brand"]
    DEFAULT_PARTIAL_ANY_OF_COUNT = 2
    DEFAULT_PARTIAL_ANY_OF = ["description", "abv", "region", "country"]
    DEFAULT_COMPLETE_REQUIRED = ["name", "brand", "abv", "description"]
    DEFAULT_COMPLETE_ANY_OF_COUNT = 2
    DEFAULT_COMPLETE_ANY_OF = ["nose_description", "palate_flavors", "region"]

    def __init__(self, config_service=None):
        """Initialize with optional config service for testing."""
        self.config_service = config_service or get_config_service()

    def assess(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None
    ) -> QualityAssessment:
        """
        Assess extracted data quality.

        Args:
            extracted_data: Dict of field_name -> value
            product_type: Product type (whiskey, port_wine)
            field_confidences: Optional dict of field_name -> confidence (0-1)
            product_category: Optional product category

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

        status = self._determine_status(populated, config)
        logger.debug("Determined status: %s", status.value)

        schema_fields = self._get_schema_fields(product_type)
        completeness = self._calculate_completeness(confident_data, schema_fields)

        missing_required, missing_any_of = self._get_missing_for_upgrade(
            populated, status, config
        )

        priority = self._calculate_enrichment_priority(status, completeness)
        needs_enrichment = status < ProductStatus.COMPLETE

        low_confidence = self._get_low_confidence_fields(field_confidences)

        assessment = QualityAssessment(
            status=status,
            completeness_score=completeness,
            populated_fields=list(populated),
            missing_required_fields=missing_required,
            missing_any_of_fields=missing_any_of,
            enrichment_priority=priority,
            needs_enrichment=needs_enrichment,
            low_confidence_fields=low_confidence
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

        filtered = {
            k: v for k, v in data.items()
            if (confidences.get(k) or 1.0) >= self.CONFIDENCE_THRESHOLD
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

    def _check_status_threshold(
        self,
        populated: Set[str],
        required_fields: List[str],
        any_of_count: int,
        any_of_fields: List[str]
    ) -> bool:
        """
        Check if populated fields meet a status threshold.

        Logic (AND condition):
            (ALL required_fields present) AND (at least any_of_count from any_of_fields)

        Args:
            populated: Set of field names with values
            required_fields: All of these must be present
            any_of_count: Minimum count from any_of_fields
            any_of_fields: Pool of optional fields

        Returns:
            True if threshold is met, False otherwise
        """
        # Check all required fields are present
        for req_field in required_fields:
            if req_field not in populated:
                return False

        # Check any_of condition
        any_of_present = sum(1 for f in any_of_fields if f in populated)
        return any_of_present >= any_of_count

    def _determine_status(
        self,
        populated: Set[str],
        config: Optional[QualityGateConfig]
    ) -> ProductStatus:
        """Determine the highest status level the data qualifies for."""
        # Extract thresholds from config or use defaults
        if config:
            skeleton_req = config.skeleton_required_fields or self.DEFAULT_SKELETON_REQUIRED
            partial_req = config.partial_required_fields or self.DEFAULT_PARTIAL_REQUIRED
            partial_count = config.partial_any_of_count if config.partial_any_of_count is not None else self.DEFAULT_PARTIAL_ANY_OF_COUNT
            partial_any = config.partial_any_of_fields or self.DEFAULT_PARTIAL_ANY_OF
            complete_req = config.complete_required_fields or self.DEFAULT_COMPLETE_REQUIRED
            complete_count = config.complete_any_of_count if config.complete_any_of_count is not None else self.DEFAULT_COMPLETE_ANY_OF_COUNT
            complete_any = config.complete_any_of_fields or self.DEFAULT_COMPLETE_ANY_OF
            enriched_req = config.enriched_required_fields or []
            enriched_count = config.enriched_any_of_count if config.enriched_any_of_count is not None else 1
            enriched_any = config.enriched_any_of_fields or ["awards", "ratings", "prices"]
        else:
            skeleton_req = self.DEFAULT_SKELETON_REQUIRED
            partial_req = self.DEFAULT_PARTIAL_REQUIRED
            partial_count = self.DEFAULT_PARTIAL_ANY_OF_COUNT
            partial_any = self.DEFAULT_PARTIAL_ANY_OF
            complete_req = self.DEFAULT_COMPLETE_REQUIRED
            complete_count = self.DEFAULT_COMPLETE_ANY_OF_COUNT
            complete_any = self.DEFAULT_COMPLETE_ANY_OF
            enriched_req = []
            enriched_count = 1
            enriched_any = ["awards", "ratings", "prices"]

        # Check from highest status to lowest (ENRICHED -> SKELETON)
        # ENRICHED requires COMPLETE requirements + enriched requirements
        if self._check_status_threshold(
            populated,
            complete_req + enriched_req,
            enriched_count,
            enriched_any
        ):
            return ProductStatus.ENRICHED

        if self._check_status_threshold(populated, complete_req, complete_count, complete_any):
            return ProductStatus.COMPLETE

        if self._check_status_threshold(populated, partial_req, partial_count, partial_any):
            return ProductStatus.PARTIAL

        if self._check_status_threshold(populated, skeleton_req, 0, []):
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
                self.DEFAULT_PARTIAL_ANY_OF +
                self.DEFAULT_COMPLETE_REQUIRED +
                self.DEFAULT_COMPLETE_ANY_OF
            ))

    def _get_missing_for_upgrade(
        self,
        populated: Set[str],
        current_status: ProductStatus,
        config: Optional[QualityGateConfig]
    ) -> Tuple[List[str], List[str]]:
        """
        Get fields needed to upgrade to next status level.

        Returns:
            Tuple of (missing_required_fields, missing_any_of_fields)
        """
        if current_status == ProductStatus.REJECTED:
            return ["name"], []

        if current_status == ProductStatus.SKELETON:
            req = config.partial_required_fields if config else self.DEFAULT_PARTIAL_REQUIRED
            any_of = config.partial_any_of_fields if config else self.DEFAULT_PARTIAL_ANY_OF
            missing_req = [f for f in req if f not in populated]
            missing_any = [f for f in any_of if f not in populated]
            return missing_req, missing_any

        if current_status == ProductStatus.PARTIAL:
            req = config.complete_required_fields if config else self.DEFAULT_COMPLETE_REQUIRED
            any_of = config.complete_any_of_fields if config else self.DEFAULT_COMPLETE_ANY_OF
            missing_req = [f for f in req if f not in populated]
            missing_any = [f for f in any_of if f not in populated]
            return missing_req, missing_any

        if current_status == ProductStatus.COMPLETE:
            any_of = config.enriched_any_of_fields if config else ["awards", "ratings", "prices"]
            missing_any = [f for f in any_of if f not in populated]
            return [], missing_any

        # ENRICHED status - already at max
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
        - PARTIAL = 6-8
        - COMPLETE = 3-5
        - ENRICHED = 1-2
        """
        base_priority = {
            ProductStatus.REJECTED: 10,
            ProductStatus.SKELETON: 9,
            ProductStatus.PARTIAL: 6,
            ProductStatus.COMPLETE: 3,
            ProductStatus.ENRICHED: 1,
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

        return [
            field_name for field_name, conf in confidences.items()
            if conf is not None and conf < self.CONFIDENCE_THRESHOLD
        ]

    # Async-safe methods for use in async contexts

    async def aassess(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None
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

        status = self._determine_status(populated, config)
        logger.debug("Determined status: %s", status.value)

        # Use async-safe schema fields loading
        schema_fields = await self._aget_schema_fields(product_type)
        completeness = self._calculate_completeness(confident_data, schema_fields)

        missing_required, missing_any_of = self._get_missing_for_upgrade(
            populated, status, config
        )

        priority = self._calculate_enrichment_priority(status, completeness)
        needs_enrichment = status < ProductStatus.COMPLETE

        low_confidence = self._get_low_confidence_fields(field_confidences)

        assessment = QualityAssessment(
            status=status,
            completeness_score=completeness,
            populated_fields=list(populated),
            missing_required_fields=missing_required,
            missing_any_of_fields=missing_any_of,
            enrichment_priority=priority,
            needs_enrichment=needs_enrichment,
            low_confidence_fields=low_confidence
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
                self.DEFAULT_PARTIAL_ANY_OF +
                self.DEFAULT_COMPLETE_REQUIRED +
                self.DEFAULT_COMPLETE_ANY_OF
            ))


# Singleton instance
_quality_gate_v2: Optional[QualityGateV2] = None


def get_quality_gate_v2() -> QualityGateV2:
    """Get singleton QualityGateV2 instance."""
    global _quality_gate_v2
    if _quality_gate_v2 is None:
        _quality_gate_v2 = QualityGateV2()
    return _quality_gate_v2


def reset_quality_gate_v2() -> None:
    """Reset singleton for testing."""
    global _quality_gate_v2
    _quality_gate_v2 = None
