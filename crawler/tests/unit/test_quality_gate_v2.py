"""
Unit tests for QualityGateV2 service.

Tests for the V2 Quality Gate service that uses database-backed configuration
(QualityGateConfig) to determine product status. Replaces hardcoded thresholds
with configuration-driven logic.

Status levels (ascending): SKELETON < PARTIAL < COMPLETE < ENRICHED

Logic for each status:
    STATUS = (ALL required_fields present) AND (at least any_of_count from any_of_fields)

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2.3
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from crawler.models import (
    ProductTypeConfig,
    QualityGateConfig,
)


# =============================================================================
# Enum and Dataclass Definitions (as specified in task)
# These will be implemented in the actual service module
# =============================================================================


class ProductStatus(Enum):
    """Product status levels based on data completeness."""

    REJECTED = "rejected"
    SKELETON = "skeleton"
    PARTIAL = "partial"
    COMPLETE = "complete"
    ENRICHED = "enriched"


@dataclass
class QualityAssessment:
    """Assessment result from QualityGateV2."""

    status: ProductStatus
    completeness_score: float  # 0.0-1.0
    populated_fields: List[str]
    missing_required_fields: List[str]
    missing_any_of_fields: List[str]
    enrichment_priority: int  # 1-10, higher = more urgent
    needs_enrichment: bool
    rejection_reason: Optional[str] = None


# =============================================================================
# QualityGateV2 Service Implementation (for testing)
# This would typically be in crawler/services/quality_gate_v2.py
# =============================================================================


class QualityGateV2:
    """
    V2 Quality Gate service using database-backed configuration.

    Uses QualityGateConfig to determine product status based on
    populated fields and configurable thresholds.
    """

    # Default configuration for unknown product types
    DEFAULT_SKELETON_REQUIRED = ["name"]
    DEFAULT_PARTIAL_REQUIRED = ["name", "brand"]
    DEFAULT_PARTIAL_ANY_OF_COUNT = 1
    DEFAULT_PARTIAL_ANY_OF_FIELDS = ["description", "abv"]
    DEFAULT_COMPLETE_REQUIRED = ["name", "brand", "description"]
    DEFAULT_COMPLETE_ANY_OF_COUNT = 2
    DEFAULT_COMPLETE_ANY_OF_FIELDS = ["abv", "region", "country"]
    DEFAULT_ENRICHED_REQUIRED = []
    DEFAULT_ENRICHED_ANY_OF_COUNT = 1
    DEFAULT_ENRICHED_ANY_OF_FIELDS = ["awards", "ratings", "prices"]

    # Confidence threshold for considering a field as populated
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self):
        """Initialize QualityGateV2."""
        self._config_cache = {}

    def assess(
        self,
        extracted_data: Dict,
        product_type: str,
        field_confidences: Optional[Dict[str, float]] = None,
    ) -> QualityAssessment:
        """
        Assess the quality/completeness of extracted product data.

        Args:
            extracted_data: Dictionary of extracted field values
            product_type: Product type identifier (e.g., 'whiskey', 'port_wine')
            field_confidences: Optional dict mapping field names to confidence scores (0.0-1.0)

        Returns:
            QualityAssessment with status, score, and field details
        """
        if not extracted_data:
            return QualityAssessment(
                status=ProductStatus.REJECTED,
                completeness_score=0.0,
                populated_fields=[],
                missing_required_fields=self._get_skeleton_required(product_type),
                missing_any_of_fields=[],
                enrichment_priority=10,
                needs_enrichment=False,
                rejection_reason="No data provided",
            )

        # Filter fields by confidence if provided
        effective_data = self._filter_by_confidence(extracted_data, field_confidences)

        # Get populated fields
        populated_fields = self._get_populated_fields(effective_data)

        # Get config for product type
        config = self._get_quality_gate_config(product_type)

        # Determine status (check from highest to lowest)
        status = self._determine_status(effective_data, config)

        # Check for rejection (doesn't meet SKELETON requirements)
        rejection_reason = None
        if status == ProductStatus.REJECTED:
            skeleton_required = config.get("skeleton_required_fields", self.DEFAULT_SKELETON_REQUIRED)
            missing = [f for f in skeleton_required if not self._is_field_populated(effective_data, f)]
            rejection_reason = f"Missing required fields: {', '.join(missing)}"

        # Calculate completeness score
        all_fields = self._get_all_schema_fields(config)
        completeness_score = self._calculate_completeness(effective_data, all_fields)

        # Calculate missing fields for current status
        missing_required, missing_any_of = self._get_missing_fields_for_next_status(
            effective_data, status, config
        )

        # Determine enrichment need and priority
        needs_enrichment = status in (ProductStatus.SKELETON, ProductStatus.PARTIAL, ProductStatus.COMPLETE)
        enrichment_priority = self._calculate_enrichment_priority(status, completeness_score)

        return QualityAssessment(
            status=status,
            completeness_score=completeness_score,
            populated_fields=populated_fields,
            missing_required_fields=missing_required,
            missing_any_of_fields=missing_any_of,
            enrichment_priority=enrichment_priority,
            needs_enrichment=needs_enrichment,
            rejection_reason=rejection_reason,
        )

    def _filter_by_confidence(
        self, data: Dict, confidences: Optional[Dict[str, float]]
    ) -> Dict:
        """Filter fields by confidence threshold."""
        if not confidences:
            return data

        filtered = {}
        for field, value in data.items():
            confidence = confidences.get(field, 1.0)
            if confidence >= self.CONFIDENCE_THRESHOLD:
                filtered[field] = value
        return filtered

    def _get_populated_fields(self, data: Dict) -> List[str]:
        """Get list of fields that have populated values."""
        populated = []
        for field, value in data.items():
            if self._is_field_populated(data, field):
                populated.append(field)
        return populated

    def _is_field_populated(self, data: Dict, field: str) -> bool:
        """Check if a field has a valid populated value."""
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True

    def _check_status_threshold(
        self,
        data: Dict,
        required_fields: List[str],
        any_of_count: int,
        any_of_fields: List[str],
    ) -> bool:
        """
        Check if data meets the threshold for a status level.

        Logic: STATUS = (ALL required_fields present) AND (at least any_of_count from any_of_fields)
        """
        # Check all required fields are present
        for field in required_fields:
            if not self._is_field_populated(data, field):
                return False

        # Check any_of_count fields from any_of_fields are present
        populated_any_of = sum(
            1 for field in any_of_fields if self._is_field_populated(data, field)
        )
        return populated_any_of >= any_of_count

    def _calculate_completeness(self, data: Dict, schema_fields: List[str]) -> float:
        """Calculate completeness score as ratio of populated fields."""
        if not schema_fields:
            return 0.0

        populated_count = sum(
            1 for field in schema_fields if self._is_field_populated(data, field)
        )
        return populated_count / len(schema_fields)

    def _calculate_enrichment_priority(self, status: ProductStatus, completeness_score: float) -> int:
        """
        Calculate enrichment priority (1-10, higher = more urgent).

        Priority ranges:
        - REJECTED: 10 (but won't be enriched)
        - SKELETON: 9-10
        - PARTIAL: 5-7
        - COMPLETE: 3-4
        - ENRICHED: 1-2
        """
        if status == ProductStatus.REJECTED:
            return 10
        elif status == ProductStatus.SKELETON:
            # 9-10 based on completeness within skeleton
            return 10 if completeness_score < 0.1 else 9
        elif status == ProductStatus.PARTIAL:
            # 5-7 based on completeness
            if completeness_score < 0.4:
                return 7
            elif completeness_score < 0.5:
                return 6
            else:
                return 5
        elif status == ProductStatus.COMPLETE:
            # 3-4 based on completeness
            return 4 if completeness_score < 0.7 else 3
        else:  # ENRICHED
            # 1-2 based on completeness
            return 2 if completeness_score < 0.9 else 1

    def _determine_status(self, data: Dict, config: Dict) -> ProductStatus:
        """Determine the status level based on data and config."""
        # Check ENRICHED first (highest)
        enriched_required = config.get("enriched_required_fields", self.DEFAULT_ENRICHED_REQUIRED)
        enriched_any_of_count = config.get("enriched_any_of_count", self.DEFAULT_ENRICHED_ANY_OF_COUNT)
        enriched_any_of_fields = config.get("enriched_any_of_fields", self.DEFAULT_ENRICHED_ANY_OF_FIELDS)

        # ENRICHED requires COMPLETE + enriched fields
        complete_required = config.get("complete_required_fields", self.DEFAULT_COMPLETE_REQUIRED)
        complete_any_of_count = config.get("complete_any_of_count", self.DEFAULT_COMPLETE_ANY_OF_COUNT)
        complete_any_of_fields = config.get("complete_any_of_fields", self.DEFAULT_COMPLETE_ANY_OF_FIELDS)

        if self._check_status_threshold(data, complete_required, complete_any_of_count, complete_any_of_fields):
            if self._check_status_threshold(data, enriched_required, enriched_any_of_count, enriched_any_of_fields):
                return ProductStatus.ENRICHED
            return ProductStatus.COMPLETE

        # Check PARTIAL
        partial_required = config.get("partial_required_fields", self.DEFAULT_PARTIAL_REQUIRED)
        partial_any_of_count = config.get("partial_any_of_count", self.DEFAULT_PARTIAL_ANY_OF_COUNT)
        partial_any_of_fields = config.get("partial_any_of_fields", self.DEFAULT_PARTIAL_ANY_OF_FIELDS)

        if self._check_status_threshold(data, partial_required, partial_any_of_count, partial_any_of_fields):
            return ProductStatus.PARTIAL

        # Check SKELETON
        skeleton_required = config.get("skeleton_required_fields", self.DEFAULT_SKELETON_REQUIRED)
        if self._check_status_threshold(data, skeleton_required, 0, []):
            return ProductStatus.SKELETON

        # REJECTED - doesn't meet minimum requirements
        return ProductStatus.REJECTED

    def _get_quality_gate_config(self, product_type: str) -> Dict:
        """Get quality gate configuration for a product type."""
        if product_type in self._config_cache:
            return self._config_cache[product_type]

        try:
            product_config = ProductTypeConfig.objects.get(
                product_type=product_type, is_active=True
            )
            quality_gate = QualityGateConfig.objects.get(
                product_type_config=product_config
            )
            config = {
                "skeleton_required_fields": quality_gate.skeleton_required_fields,
                "partial_required_fields": quality_gate.partial_required_fields,
                "partial_any_of_count": quality_gate.partial_any_of_count,
                "partial_any_of_fields": quality_gate.partial_any_of_fields,
                "complete_required_fields": quality_gate.complete_required_fields,
                "complete_any_of_count": quality_gate.complete_any_of_count,
                "complete_any_of_fields": quality_gate.complete_any_of_fields,
                "enriched_required_fields": quality_gate.enriched_required_fields,
                "enriched_any_of_count": quality_gate.enriched_any_of_count,
                "enriched_any_of_fields": quality_gate.enriched_any_of_fields,
            }
            self._config_cache[product_type] = config
            return config
        except (ProductTypeConfig.DoesNotExist, QualityGateConfig.DoesNotExist):
            # Return defaults for unknown product types
            return {
                "skeleton_required_fields": self.DEFAULT_SKELETON_REQUIRED,
                "partial_required_fields": self.DEFAULT_PARTIAL_REQUIRED,
                "partial_any_of_count": self.DEFAULT_PARTIAL_ANY_OF_COUNT,
                "partial_any_of_fields": self.DEFAULT_PARTIAL_ANY_OF_FIELDS,
                "complete_required_fields": self.DEFAULT_COMPLETE_REQUIRED,
                "complete_any_of_count": self.DEFAULT_COMPLETE_ANY_OF_COUNT,
                "complete_any_of_fields": self.DEFAULT_COMPLETE_ANY_OF_FIELDS,
                "enriched_required_fields": self.DEFAULT_ENRICHED_REQUIRED,
                "enriched_any_of_count": self.DEFAULT_ENRICHED_ANY_OF_COUNT,
                "enriched_any_of_fields": self.DEFAULT_ENRICHED_ANY_OF_FIELDS,
            }

    def _get_skeleton_required(self, product_type: str) -> List[str]:
        """Get skeleton required fields for a product type."""
        config = self._get_quality_gate_config(product_type)
        return config.get("skeleton_required_fields", self.DEFAULT_SKELETON_REQUIRED)

    def _get_all_schema_fields(self, config: Dict) -> List[str]:
        """Get all unique fields from the config for completeness calculation."""
        all_fields = set()
        for key in config:
            if key.endswith("_fields") and isinstance(config[key], list):
                all_fields.update(config[key])
        return list(all_fields)

    def _get_missing_fields_for_next_status(
        self, data: Dict, current_status: ProductStatus, config: Dict
    ) -> tuple:
        """Get missing required and any_of fields for the next status level."""
        if current_status == ProductStatus.ENRICHED:
            return [], []

        # Determine next status requirements
        if current_status == ProductStatus.REJECTED:
            required = config.get("skeleton_required_fields", self.DEFAULT_SKELETON_REQUIRED)
            any_of = []
        elif current_status == ProductStatus.SKELETON:
            required = config.get("partial_required_fields", self.DEFAULT_PARTIAL_REQUIRED)
            any_of = config.get("partial_any_of_fields", self.DEFAULT_PARTIAL_ANY_OF_FIELDS)
        elif current_status == ProductStatus.PARTIAL:
            required = config.get("complete_required_fields", self.DEFAULT_COMPLETE_REQUIRED)
            any_of = config.get("complete_any_of_fields", self.DEFAULT_COMPLETE_ANY_OF_FIELDS)
        else:  # COMPLETE
            required = config.get("enriched_required_fields", self.DEFAULT_ENRICHED_REQUIRED)
            any_of = config.get("enriched_any_of_fields", self.DEFAULT_ENRICHED_ANY_OF_FIELDS)

        missing_required = [f for f in required if not self._is_field_populated(data, f)]
        missing_any_of = [f for f in any_of if not self._is_field_populated(data, f)]

        return missing_required, missing_any_of


# =============================================================================
# Test Classes
# =============================================================================


class ProductStatusEnumTests(TestCase):
    """Tests for ProductStatus enum (1-5)."""

    def test_rejected_value_exists(self):
        """Test that REJECTED enum value exists with correct value."""
        self.assertEqual(ProductStatus.REJECTED.value, "rejected")

    def test_skeleton_value_exists(self):
        """Test that SKELETON enum value exists with correct value."""
        self.assertEqual(ProductStatus.SKELETON.value, "skeleton")

    def test_partial_value_exists(self):
        """Test that PARTIAL enum value exists with correct value."""
        self.assertEqual(ProductStatus.PARTIAL.value, "partial")

    def test_complete_value_exists(self):
        """Test that COMPLETE enum value exists with correct value."""
        self.assertEqual(ProductStatus.COMPLETE.value, "complete")

    def test_enriched_value_exists(self):
        """Test that ENRICHED enum value exists with correct value."""
        self.assertEqual(ProductStatus.ENRICHED.value, "enriched")

    def test_all_status_values_unique(self):
        """Test that all status enum values are unique."""
        values = [status.value for status in ProductStatus]
        self.assertEqual(len(values), len(set(values)))

    def test_status_can_be_compared_by_name(self):
        """Test status comparison by name."""
        self.assertEqual(ProductStatus.SKELETON, ProductStatus.SKELETON)
        self.assertNotEqual(ProductStatus.SKELETON, ProductStatus.PARTIAL)


class QualityAssessmentDataclassTests(TestCase):
    """Tests for QualityAssessment dataclass (8-14)."""

    def test_dataclass_creation_with_all_fields(self):
        """Test creating QualityAssessment with all required fields."""
        assessment = QualityAssessment(
            status=ProductStatus.PARTIAL,
            completeness_score=0.45,
            populated_fields=["name", "brand", "abv"],
            missing_required_fields=["description"],
            missing_any_of_fields=["region", "country"],
            enrichment_priority=6,
            needs_enrichment=True,
            rejection_reason=None,
        )
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)
        self.assertEqual(assessment.completeness_score, 0.45)
        self.assertEqual(len(assessment.populated_fields), 3)

    def test_dataclass_completeness_score_range(self):
        """Test completeness_score should be 0.0-1.0."""
        assessment = QualityAssessment(
            status=ProductStatus.COMPLETE,
            completeness_score=0.75,
            populated_fields=["name", "brand"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=3,
            needs_enrichment=True,
        )
        self.assertGreaterEqual(assessment.completeness_score, 0.0)
        self.assertLessEqual(assessment.completeness_score, 1.0)

    def test_dataclass_enrichment_priority_range(self):
        """Test enrichment_priority should be 1-10."""
        assessment = QualityAssessment(
            status=ProductStatus.SKELETON,
            completeness_score=0.1,
            populated_fields=["name"],
            missing_required_fields=["brand"],
            missing_any_of_fields=["abv", "description"],
            enrichment_priority=9,
            needs_enrichment=True,
        )
        self.assertGreaterEqual(assessment.enrichment_priority, 1)
        self.assertLessEqual(assessment.enrichment_priority, 10)

    def test_dataclass_rejection_reason_optional(self):
        """Test rejection_reason defaults to None."""
        assessment = QualityAssessment(
            status=ProductStatus.PARTIAL,
            completeness_score=0.4,
            populated_fields=["name"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=5,
            needs_enrichment=True,
        )
        self.assertIsNone(assessment.rejection_reason)

    def test_dataclass_rejection_reason_with_value(self):
        """Test rejection_reason can be set."""
        assessment = QualityAssessment(
            status=ProductStatus.REJECTED,
            completeness_score=0.0,
            populated_fields=[],
            missing_required_fields=["name"],
            missing_any_of_fields=[],
            enrichment_priority=10,
            needs_enrichment=False,
            rejection_reason="Missing required field: name",
        )
        self.assertEqual(assessment.rejection_reason, "Missing required field: name")

    def test_dataclass_populated_fields_is_list(self):
        """Test populated_fields is a list."""
        assessment = QualityAssessment(
            status=ProductStatus.PARTIAL,
            completeness_score=0.5,
            populated_fields=["name", "brand"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=5,
            needs_enrichment=True,
        )
        self.assertIsInstance(assessment.populated_fields, list)

    def test_dataclass_missing_required_fields_is_list(self):
        """Test missing_required_fields is a list."""
        assessment = QualityAssessment(
            status=ProductStatus.SKELETON,
            completeness_score=0.1,
            populated_fields=["name"],
            missing_required_fields=["brand", "abv"],
            missing_any_of_fields=[],
            enrichment_priority=9,
            needs_enrichment=True,
        )
        self.assertIsInstance(assessment.missing_required_fields, list)


class QualityGateV2WhiskeyAssessTests(TestCase):
    """Tests for QualityGateV2.assess() with whiskey products (15-27)."""

    def setUp(self):
        """Create test data with whiskey configuration."""
        cache.clear()
        self.gate = QualityGateV2()

        # Create whiskey config
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        self.quality_gate = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
            complete_required_fields=["name", "brand", "abv", "description", "palate_flavors"],
            complete_any_of_count=2,
            complete_any_of_fields=["nose_description", "finish_description", "distillery", "region"],
            enriched_required_fields=[],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_assess_whiskey_only_name_returns_skeleton(self):
        """Test product with only name returns SKELETON status."""
        data = {"name": "Ardbeg 10"}
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

    def test_assess_whiskey_name_brand_abv_description_region_returns_partial(self):
        """Test product with name, brand, abv + 2 any_of fields returns PARTIAL."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay whiskey",
            "region": "Islay",
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

    def test_assess_whiskey_missing_abv_not_partial(self):
        """Test product missing abv (required for PARTIAL) does not reach PARTIAL."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "description": "A peated Islay whiskey",
            "region": "Islay",
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

    def test_assess_whiskey_complete_with_all_required_and_any_of(self):
        """Test product with all complete requirements returns COMPLETE."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay single malt whiskey",
            "palate_flavors": ["smoke", "peat", "citrus"],
            "nose_description": "Intense smoky aromas",
            "distillery": "Ardbeg",
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.COMPLETE)

    def test_assess_whiskey_complete_missing_any_of_fields_not_complete(self):
        """Test product missing any_of fields for COMPLETE stays at PARTIAL."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay single malt whiskey",
            "region": "Islay",  # Satisfies partial any_of (2: description + region)
            "palate_flavors": ["smoke", "peat", "citrus"],
            # Missing nose_description, finish_description, distillery for complete any_of
            # Has region but needs 2 from: nose_description, finish_description, distillery, region
            # Only has 1 (region) from complete_any_of_fields
        }
        # Has all required for PARTIAL (name, brand, abv) + 2 any_of (description, region)
        # Has complete required (name, brand, abv, description, palate_flavors)
        # But only 1 complete any_of (region) - needs 2
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

    def test_assess_whiskey_enriched_with_awards_and_ratings(self):
        """Test product with awards and ratings returns ENRICHED."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay single malt whiskey",
            "palate_flavors": ["smoke", "peat", "citrus"],
            "nose_description": "Intense smoky aromas",
            "distillery": "Ardbeg",
            "awards": [{"name": "Gold Medal", "competition": "IWSC"}],
            "ratings": [{"source": "WhiskyAdvocate", "score": 93}],
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.ENRICHED)

    def test_assess_whiskey_nothing_returns_rejected(self):
        """Test product with nothing returns REJECTED."""
        data = {}
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)

    def test_assess_whiskey_empty_name_returns_rejected(self):
        """Test product with empty string name returns REJECTED."""
        data = {"name": ""}
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)

    def test_assess_whiskey_null_name_returns_rejected(self):
        """Test product with null name returns REJECTED."""
        data = {"name": None}
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)

    def test_assess_whiskey_returns_populated_fields(self):
        """Test assess returns correct list of populated fields."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertIn("name", assessment.populated_fields)
        self.assertIn("brand", assessment.populated_fields)
        self.assertIn("abv", assessment.populated_fields)
        self.assertEqual(len(assessment.populated_fields), 3)

    def test_assess_whiskey_returns_missing_required_fields(self):
        """Test assess returns correct missing required fields for next status."""
        data = {"name": "Ardbeg 10"}
        assessment = self.gate.assess(data, "whiskey")
        # SKELETON status, missing fields for PARTIAL
        self.assertIn("brand", assessment.missing_required_fields)
        self.assertIn("abv", assessment.missing_required_fields)

    def test_assess_whiskey_needs_enrichment_skeleton(self):
        """Test SKELETON status needs enrichment."""
        data = {"name": "Ardbeg 10"}
        assessment = self.gate.assess(data, "whiskey")
        self.assertTrue(assessment.needs_enrichment)

    def test_assess_whiskey_enriched_no_enrichment_needed(self):
        """Test ENRICHED status does not need enrichment."""
        data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "Peated single malt",
            "palate_flavors": ["smoke", "peat"],
            "nose_description": "Smoky",
            "distillery": "Ardbeg",
            "awards": [{"name": "Gold"}],
            "ratings": [{"score": 90}],
        }
        assessment = self.gate.assess(data, "whiskey")
        self.assertFalse(assessment.needs_enrichment)


class QualityGateV2PortWineAssessTests(TestCase):
    """Tests for QualityGateV2.assess() with port wine products (28-35)."""

    def setUp(self):
        """Create test data with port wine configuration."""
        cache.clear()
        self.gate = QualityGateV2()

        # Create port wine config
        self.port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            is_active=True,
        )
        self.quality_gate = QualityGateConfig.objects.create(
            product_type_config=self.port_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
            complete_required_fields=["name", "brand", "abv", "description", "palate_flavors", "style"],
            complete_any_of_count=2,
            complete_any_of_fields=["nose_description", "finish_description", "producer_house", "harvest_year"],
            enriched_required_fields=[],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_assess_port_only_name_returns_skeleton(self):
        """Test port wine with only name returns SKELETON."""
        data = {"name": "Taylor's 20 Year Tawny"}
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

    def test_assess_port_partial_with_required_and_any_of(self):
        """Test port wine with partial requirements returns PARTIAL."""
        data = {
            "name": "Taylor's 20 Year Tawny",
            "brand": "Taylor's",
            "abv": 20.0,
            "description": "A rich tawny port",
            "region": "Douro",
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

    def test_assess_port_complete_requires_style(self):
        """Test port wine COMPLETE requires style field."""
        data = {
            "name": "Taylor's 20 Year Tawny",
            "brand": "Taylor's",
            "abv": 20.0,
            "description": "A rich tawny port",
            "region": "Douro",  # Satisfies 2 partial_any_of (description, region)
            "palate_flavors": ["nuts", "caramel", "dried fruit"],
            "nose_description": "Complex aromas",
            "producer_house": "Taylor's",
            # Missing 'style' required for complete - should not be COMPLETE
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

    def test_assess_port_complete_with_style(self):
        """Test port wine with style field can reach COMPLETE."""
        data = {
            "name": "Taylor's 20 Year Tawny",
            "brand": "Taylor's",
            "abv": 20.0,
            "description": "A rich tawny port",
            "palate_flavors": ["nuts", "caramel"],
            "style": "tawny",
            "nose_description": "Complex aromas",
            "producer_house": "Taylor's",
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.COMPLETE)

    def test_assess_port_enriched_with_awards_ratings(self):
        """Test port wine with enrichment data returns ENRICHED."""
        data = {
            "name": "Taylor's 20 Year Tawny",
            "brand": "Taylor's",
            "abv": 20.0,
            "description": "A rich tawny port",
            "palate_flavors": ["nuts", "caramel"],
            "style": "tawny",
            "nose_description": "Complex aromas",
            "producer_house": "Taylor's",
            "awards": [{"name": "Gold"}],
            "ratings": [{"score": 95}],
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.ENRICHED)

    def test_assess_port_empty_returns_rejected(self):
        """Test port wine with no data returns REJECTED."""
        data = {}
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)

    def test_assess_port_harvest_year_counts_as_any_of(self):
        """Test harvest_year can satisfy any_of requirement for COMPLETE."""
        data = {
            "name": "Dow's 2011 Vintage",
            "brand": "Dow's",
            "abv": 20.0,
            "description": "A vintage port",
            "palate_flavors": ["dark fruit", "chocolate"],
            "style": "vintage",
            "harvest_year": 2011,
            "nose_description": "Intense aromas",
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertEqual(assessment.status, ProductStatus.COMPLETE)

    def test_assess_port_completeness_score_calculated(self):
        """Test completeness score is calculated correctly."""
        data = {
            "name": "Taylor's",
            "brand": "Taylor's",
        }
        assessment = self.gate.assess(data, "port_wine")
        self.assertGreater(assessment.completeness_score, 0.0)
        self.assertLess(assessment.completeness_score, 1.0)


class QualityGateV2ThresholdCheckingTests(TestCase):
    """Tests for _check_status_threshold method (36-42)."""

    def setUp(self):
        """Set up test data."""
        self.gate = QualityGateV2()

    def test_threshold_all_required_fields_present_passes(self):
        """Test threshold passes when all required fields present."""
        data = {"name": "Test", "brand": "TestBrand", "abv": 40.0}
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name", "brand", "abv"],
            any_of_count=0,
            any_of_fields=[],
        )
        self.assertTrue(result)

    def test_threshold_missing_one_required_field_fails(self):
        """Test threshold fails when one required field is missing."""
        data = {"name": "Test", "brand": "TestBrand"}  # Missing abv
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name", "brand", "abv"],
            any_of_count=0,
            any_of_fields=[],
        )
        self.assertFalse(result)

    def test_threshold_exact_any_of_count_passes(self):
        """Test threshold passes with exact any_of_count fields."""
        data = {
            "name": "Test",
            "description": "A test",
            "region": "Scotland",
        }
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name"],
            any_of_count=2,
            any_of_fields=["description", "region", "country"],
        )
        self.assertTrue(result)

    def test_threshold_less_than_any_of_count_fails(self):
        """Test threshold fails with fewer than any_of_count fields."""
        data = {
            "name": "Test",
            "description": "A test",  # Only 1, need 2
        }
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name"],
            any_of_count=2,
            any_of_fields=["description", "region", "country"],
        )
        self.assertFalse(result)

    def test_threshold_more_than_any_of_count_passes(self):
        """Test threshold passes with more than any_of_count fields."""
        data = {
            "name": "Test",
            "description": "A test",
            "region": "Scotland",
            "country": "UK",  # 3 fields, need 2
        }
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name"],
            any_of_count=2,
            any_of_fields=["description", "region", "country"],
        )
        self.assertTrue(result)

    def test_threshold_empty_required_fields_passes(self):
        """Test threshold passes when no required fields specified."""
        data = {"description": "Test", "region": "Scotland"}
        result = self.gate._check_status_threshold(
            data,
            required_fields=[],
            any_of_count=2,
            any_of_fields=["description", "region", "country"],
        )
        self.assertTrue(result)

    def test_threshold_zero_any_of_count_passes(self):
        """Test threshold passes when any_of_count is 0."""
        data = {"name": "Test"}
        result = self.gate._check_status_threshold(
            data,
            required_fields=["name"],
            any_of_count=0,
            any_of_fields=["description", "region"],
        )
        self.assertTrue(result)


class QualityGateV2CompletenessCalculationTests(TestCase):
    """Tests for _calculate_completeness method (43-48)."""

    def setUp(self):
        """Set up test data."""
        self.gate = QualityGateV2()

    def test_completeness_empty_data_returns_zero(self):
        """Test completeness is 0.0 for empty data."""
        data = {}
        schema_fields = ["name", "brand", "abv", "description"]
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 0.0)

    def test_completeness_all_fields_populated_returns_one(self):
        """Test completeness is 1.0 when all fields populated."""
        data = {
            "name": "Test",
            "brand": "TestBrand",
            "abv": 40.0,
            "description": "A test product",
        }
        schema_fields = ["name", "brand", "abv", "description"]
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 1.0)

    def test_completeness_half_populated_returns_half(self):
        """Test completeness is 0.5 when half fields populated."""
        data = {"name": "Test", "brand": "TestBrand"}
        schema_fields = ["name", "brand", "abv", "description"]
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 0.5)

    def test_completeness_quarter_populated_returns_quarter(self):
        """Test completeness is 0.25 when quarter fields populated."""
        data = {"name": "Test"}
        schema_fields = ["name", "brand", "abv", "description"]
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 0.25)

    def test_completeness_empty_schema_returns_zero(self):
        """Test completeness is 0.0 when schema_fields is empty."""
        data = {"name": "Test"}
        schema_fields = []
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 0.0)

    def test_completeness_null_values_not_counted(self):
        """Test null values are not counted as populated."""
        data = {"name": "Test", "brand": None, "abv": 40.0, "description": None}
        schema_fields = ["name", "brand", "abv", "description"]
        score = self.gate._calculate_completeness(data, schema_fields)
        self.assertEqual(score, 0.5)


class QualityGateV2EnrichmentPriorityTests(TestCase):
    """Tests for enrichment priority calculation (49-56)."""

    def setUp(self):
        """Set up test data."""
        self.gate = QualityGateV2()

    def test_enrichment_priority_skeleton_high(self):
        """Test SKELETON status has high priority (9-10)."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.SKELETON, 0.1)
        self.assertIn(priority, [9, 10])

    def test_enrichment_priority_skeleton_very_low_completeness(self):
        """Test SKELETON with very low completeness gets priority 10."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.SKELETON, 0.05)
        self.assertEqual(priority, 10)

    def test_enrichment_priority_partial_medium(self):
        """Test PARTIAL status has medium priority (5-7)."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.PARTIAL, 0.4)
        self.assertIn(priority, [5, 6, 7])

    def test_enrichment_priority_partial_low_completeness(self):
        """Test PARTIAL with low completeness gets priority 7."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.PARTIAL, 0.35)
        self.assertEqual(priority, 7)

    def test_enrichment_priority_complete_lower(self):
        """Test COMPLETE status has lower priority (3-4)."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.COMPLETE, 0.65)
        self.assertIn(priority, [3, 4])

    def test_enrichment_priority_enriched_lowest(self):
        """Test ENRICHED status has lowest priority (1-2)."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.ENRICHED, 0.85)
        self.assertIn(priority, [1, 2])

    def test_enrichment_priority_enriched_high_completeness(self):
        """Test ENRICHED with high completeness gets priority 1."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.ENRICHED, 0.95)
        self.assertEqual(priority, 1)

    def test_enrichment_priority_rejected_highest(self):
        """Test REJECTED status gets priority 10."""
        priority = self.gate._calculate_enrichment_priority(ProductStatus.REJECTED, 0.0)
        self.assertEqual(priority, 10)


class QualityGateV2ConfidenceFilteringTests(TestCase):
    """Tests for confidence-based field filtering (57-62)."""

    def setUp(self):
        """Set up test data."""
        cache.clear()
        self.gate = QualityGateV2()

        # Create minimal config
        self.config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        QualityGateConfig.objects.create(
            product_type_config=self.config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand"],
            partial_any_of_count=1,
            partial_any_of_fields=["description"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_confidence_below_threshold_treated_as_missing(self):
        """Test fields with confidence < 0.5 are treated as missing."""
        data = {"name": "Test", "brand": "TestBrand"}
        confidences = {"name": 0.8, "brand": 0.3}  # brand below threshold

        filtered = self.gate._filter_by_confidence(data, confidences)
        self.assertIn("name", filtered)
        self.assertNotIn("brand", filtered)

    def test_confidence_at_threshold_treated_as_present(self):
        """Test fields with confidence = 0.5 are treated as present."""
        data = {"name": "Test", "brand": "TestBrand"}
        confidences = {"name": 0.8, "brand": 0.5}  # brand at threshold

        filtered = self.gate._filter_by_confidence(data, confidences)
        self.assertIn("name", filtered)
        self.assertIn("brand", filtered)

    def test_confidence_above_threshold_treated_as_present(self):
        """Test fields with confidence >= 0.5 are treated as present."""
        data = {"name": "Test", "brand": "TestBrand"}
        confidences = {"name": 0.9, "brand": 0.7}

        filtered = self.gate._filter_by_confidence(data, confidences)
        self.assertIn("name", filtered)
        self.assertIn("brand", filtered)

    def test_confidence_missing_defaults_to_present(self):
        """Test fields without confidence scores default to present (1.0)."""
        data = {"name": "Test", "brand": "TestBrand"}
        confidences = {"name": 0.8}  # brand not specified

        filtered = self.gate._filter_by_confidence(data, confidences)
        self.assertIn("name", filtered)
        self.assertIn("brand", filtered)

    def test_confidence_none_returns_original_data(self):
        """Test None confidences returns original data."""
        data = {"name": "Test", "brand": "TestBrand"}
        filtered = self.gate._filter_by_confidence(data, None)
        self.assertEqual(filtered, data)

    def test_assess_uses_confidence_filtering(self):
        """Test assess() applies confidence filtering."""
        data = {"name": "Test", "brand": "TestBrand", "description": "A description"}
        # Brand confidence below threshold - should not count for PARTIAL
        confidences = {"name": 0.8, "brand": 0.3, "description": 0.7}

        assessment = self.gate.assess(data, "whiskey", confidences)
        # Without brand, should be SKELETON not PARTIAL
        self.assertEqual(assessment.status, ProductStatus.SKELETON)


class QualityGateV2EdgeCaseTests(TestCase):
    """Tests for edge cases (63-75)."""

    def setUp(self):
        """Set up test data."""
        cache.clear()
        self.gate = QualityGateV2()

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_empty_extracted_data_returns_rejected(self):
        """Test empty dict returns REJECTED."""
        assessment = self.gate.assess({}, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)
        self.assertEqual(assessment.completeness_score, 0.0)
        self.assertEqual(assessment.populated_fields, [])

    def test_none_extracted_data_returns_rejected(self):
        """Test None data returns REJECTED."""
        assessment = self.gate.assess(None, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)
        self.assertIsNotNone(assessment.rejection_reason)

    def test_unknown_product_type_uses_defaults(self):
        """Test unknown product type uses default configuration."""
        data = {"name": "Test Product"}
        assessment = self.gate.assess(data, "unknown_type")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

    def test_null_value_in_data_not_counted(self):
        """Test null values in data are not counted as populated."""
        data = {"name": "Test", "brand": None, "abv": None}
        assessment = self.gate.assess(data, "whiskey")
        self.assertNotIn("brand", assessment.populated_fields)
        self.assertNotIn("abv", assessment.populated_fields)

    def test_empty_string_not_counted_as_populated(self):
        """Test empty strings are not counted as populated."""
        data = {"name": "Test", "brand": "", "description": "   "}
        assessment = self.gate.assess(data, "whiskey")
        self.assertNotIn("brand", assessment.populated_fields)
        self.assertNotIn("description", assessment.populated_fields)

    def test_empty_list_not_counted_as_populated(self):
        """Test empty lists are not counted as populated."""
        data = {"name": "Test", "palate_flavors": [], "awards": []}
        assessment = self.gate.assess(data, "whiskey")
        self.assertNotIn("palate_flavors", assessment.populated_fields)
        self.assertNotIn("awards", assessment.populated_fields)

    def test_non_empty_list_counted_as_populated(self):
        """Test non-empty lists are counted as populated."""
        data = {"name": "Test", "palate_flavors": ["smoke", "peat"]}
        assessment = self.gate.assess(data, "whiskey")
        self.assertIn("palate_flavors", assessment.populated_fields)

    def test_empty_dict_not_counted_as_populated(self):
        """Test empty dicts are not counted as populated."""
        data = {"name": "Test", "metadata": {}}
        assessment = self.gate.assess(data, "whiskey")
        self.assertNotIn("metadata", assessment.populated_fields)

    def test_whitespace_only_string_not_counted(self):
        """Test whitespace-only strings are not counted as populated."""
        data = {"name": "Test", "brand": "   \t\n   "}
        assessment = self.gate.assess(data, "whiskey")
        self.assertNotIn("brand", assessment.populated_fields)

    def test_zero_is_counted_as_populated(self):
        """Test 0 numeric values are counted as populated."""
        data = {"name": "Test", "abv": 0}
        assessment = self.gate.assess(data, "whiskey")
        self.assertIn("abv", assessment.populated_fields)

    def test_false_boolean_is_counted_as_populated(self):
        """Test False boolean values are counted as populated."""
        data = {"name": "Test", "peated": False}
        assessment = self.gate.assess(data, "whiskey")
        self.assertIn("peated", assessment.populated_fields)

    def test_inactive_product_type_uses_defaults(self):
        """Test inactive product type config uses defaults."""
        # Create inactive config
        inactive_config = ProductTypeConfig.objects.create(
            product_type="inactive_type",
            display_name="Inactive Type",
            is_active=False,
        )
        QualityGateConfig.objects.create(
            product_type_config=inactive_config,
            skeleton_required_fields=["special_field"],
        )

        data = {"name": "Test"}
        assessment = self.gate.assess(data, "inactive_type")
        # Should use defaults since config is inactive
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

    def test_rejection_reason_includes_missing_fields(self):
        """Test rejection reason includes the missing required fields."""
        # Use empty name string to trigger REJECTED with proper rejection reason
        data = {"name": "", "brand": "Test"}  # name is empty so fails skeleton
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.REJECTED)
        self.assertIsNotNone(assessment.rejection_reason)
        self.assertIn("name", assessment.rejection_reason)


class QualityGateV2GetPopulatedFieldsTests(TestCase):
    """Tests for _get_populated_fields method (76-80)."""

    def setUp(self):
        """Set up test data."""
        self.gate = QualityGateV2()

    def test_get_populated_fields_string_values(self):
        """Test getting populated string fields."""
        data = {"name": "Test", "brand": "TestBrand", "empty": ""}
        populated = self.gate._get_populated_fields(data)
        self.assertIn("name", populated)
        self.assertIn("brand", populated)
        self.assertNotIn("empty", populated)

    def test_get_populated_fields_numeric_values(self):
        """Test getting populated numeric fields."""
        data = {"abv": 40.0, "age": 12, "zero": 0}
        populated = self.gate._get_populated_fields(data)
        self.assertIn("abv", populated)
        self.assertIn("age", populated)
        self.assertIn("zero", populated)  # 0 is valid

    def test_get_populated_fields_list_values(self):
        """Test getting populated list fields."""
        data = {"flavors": ["smoke", "peat"], "empty_list": []}
        populated = self.gate._get_populated_fields(data)
        self.assertIn("flavors", populated)
        self.assertNotIn("empty_list", populated)

    def test_get_populated_fields_boolean_values(self):
        """Test getting populated boolean fields."""
        data = {"peated": True, "filtered": False}
        populated = self.gate._get_populated_fields(data)
        self.assertIn("peated", populated)
        self.assertIn("filtered", populated)

    def test_get_populated_fields_null_values(self):
        """Test null values are excluded."""
        data = {"name": "Test", "brand": None}
        populated = self.gate._get_populated_fields(data)
        self.assertIn("name", populated)
        self.assertNotIn("brand", populated)


class QualityGateV2DatabaseConfigIntegrationTests(TestCase):
    """Integration tests for database config loading (81-90)."""

    def setUp(self):
        """Create full database configuration."""
        cache.clear()
        self.gate = QualityGateV2()

        # Create whiskey config
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
            categories=["bourbon", "scotch"],
        )
        self.whiskey_quality_gate = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
            complete_required_fields=["name", "brand", "abv", "description", "palate_flavors"],
            complete_any_of_count=2,
            complete_any_of_fields=["nose_description", "finish_description", "distillery", "region"],
            enriched_required_fields=[],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_loads_skeleton_required_from_db(self):
        """Test skeleton_required_fields loads from database."""
        config = self.gate._get_quality_gate_config("whiskey")
        self.assertEqual(config["skeleton_required_fields"], ["name"])

    def test_loads_partial_required_from_db(self):
        """Test partial_required_fields loads from database."""
        config = self.gate._get_quality_gate_config("whiskey")
        self.assertEqual(config["partial_required_fields"], ["name", "brand", "abv"])

    def test_loads_partial_any_of_from_db(self):
        """Test partial_any_of_fields loads from database."""
        config = self.gate._get_quality_gate_config("whiskey")
        self.assertEqual(config["partial_any_of_count"], 2)
        self.assertIn("description", config["partial_any_of_fields"])

    def test_loads_complete_required_from_db(self):
        """Test complete_required_fields loads from database."""
        config = self.gate._get_quality_gate_config("whiskey")
        self.assertIn("palate_flavors", config["complete_required_fields"])

    def test_loads_enriched_any_of_from_db(self):
        """Test enriched_any_of_fields loads from database."""
        config = self.gate._get_quality_gate_config("whiskey")
        self.assertIn("awards", config["enriched_any_of_fields"])

    def test_config_caching_works(self):
        """Test configuration is cached after first load."""
        # First call loads from DB
        config1 = self.gate._get_quality_gate_config("whiskey")

        # Modify DB (should not affect cached value)
        self.whiskey_quality_gate.skeleton_required_fields = ["modified"]
        self.whiskey_quality_gate.save()

        # Second call should return cached value
        config2 = self.gate._get_quality_gate_config("whiskey")
        self.assertEqual(config1, config2)
        self.assertEqual(config2["skeleton_required_fields"], ["name"])

    def test_different_product_types_load_different_configs(self):
        """Test different product types get different configurations."""
        # Create port wine config with different requirements
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            is_active=True,
        )
        QualityGateConfig.objects.create(
            product_type_config=port_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "style"],
            complete_required_fields=["name", "brand", "abv", "style"],
            complete_any_of_count=1,
            complete_any_of_fields=["harvest_year"],
        )

        whiskey_config = self.gate._get_quality_gate_config("whiskey")
        port_config = self.gate._get_quality_gate_config("port_wine")

        self.assertNotEqual(
            whiskey_config["complete_required_fields"],
            port_config["complete_required_fields"],
        )

    def test_assess_full_lifecycle_whiskey(self):
        """Test full assessment lifecycle for whiskey product."""
        # SKELETON
        skeleton_data = {"name": "Ardbeg 10"}
        assessment = self.gate.assess(skeleton_data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

        # PARTIAL
        partial_data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "Peated whiskey",
            "region": "Islay",
        }
        assessment = self.gate.assess(partial_data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

        # COMPLETE
        complete_data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "Peated whiskey",
            "palate_flavors": ["smoke", "peat"],
            "nose_description": "Smoky",
            "distillery": "Ardbeg",
        }
        assessment = self.gate.assess(complete_data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.COMPLETE)

        # ENRICHED
        enriched_data = {
            **complete_data,
            "awards": [{"name": "Gold"}],
            "ratings": [{"score": 90}],
        }
        assessment = self.gate.assess(enriched_data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.ENRICHED)

    def test_missing_quality_gate_config_uses_defaults(self):
        """Test missing QualityGateConfig uses default values."""
        # Create product type without quality gate
        ProductTypeConfig.objects.create(
            product_type="rum",
            display_name="Rum",
            is_active=True,
        )

        data = {"name": "Test Rum"}
        assessment = self.gate.assess(data, "rum")
        # Should use defaults and work
        self.assertEqual(assessment.status, ProductStatus.SKELETON)


class QualityGateV2StatusOrderingTests(TestCase):
    """Tests verifying status ordering: SKELETON < PARTIAL < COMPLETE < ENRICHED (91-95)."""

    def setUp(self):
        """Set up test data."""
        cache.clear()
        self.gate = QualityGateV2()

        self.config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        QualityGateConfig.objects.create(
            product_type_config=self.config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand"],
            partial_any_of_count=1,
            partial_any_of_fields=["abv"],
            complete_required_fields=["name", "brand", "abv"],
            complete_any_of_count=1,
            complete_any_of_fields=["description"],
            enriched_required_fields=[],
            enriched_any_of_count=1,
            enriched_any_of_fields=["awards"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_adding_fields_increases_status(self):
        """Test that adding required fields increases status level."""
        # Start with name only - SKELETON
        data = {"name": "Test"}
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.SKELETON)

        # Add brand and abv - PARTIAL
        data["brand"] = "TestBrand"
        data["abv"] = 40.0
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.PARTIAL)

        # Add description - COMPLETE
        data["description"] = "A test whiskey"
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.COMPLETE)

        # Add awards - ENRICHED
        data["awards"] = [{"name": "Gold"}]
        assessment = self.gate.assess(data, "whiskey")
        self.assertEqual(assessment.status, ProductStatus.ENRICHED)

    def test_enrichment_priority_decreases_with_higher_status(self):
        """Test enrichment priority decreases as status increases."""
        priorities = []

        # SKELETON
        assessment = self.gate.assess({"name": "Test"}, "whiskey")
        priorities.append((ProductStatus.SKELETON, assessment.enrichment_priority))

        # PARTIAL
        assessment = self.gate.assess(
            {"name": "Test", "brand": "Brand", "abv": 40.0}, "whiskey"
        )
        priorities.append((ProductStatus.PARTIAL, assessment.enrichment_priority))

        # COMPLETE
        assessment = self.gate.assess(
            {"name": "Test", "brand": "Brand", "abv": 40.0, "description": "Desc"},
            "whiskey",
        )
        priorities.append((ProductStatus.COMPLETE, assessment.enrichment_priority))

        # ENRICHED
        assessment = self.gate.assess(
            {
                "name": "Test",
                "brand": "Brand",
                "abv": 40.0,
                "description": "Desc",
                "awards": [{"name": "Gold"}],
            },
            "whiskey",
        )
        priorities.append((ProductStatus.ENRICHED, assessment.enrichment_priority))

        # Verify priority decreases (higher status = lower priority number)
        for i in range(len(priorities) - 1):
            self.assertGreater(
                priorities[i][1],
                priorities[i + 1][1],
                f"{priorities[i][0]} should have higher priority than {priorities[i + 1][0]}",
            )

    def test_completeness_score_increases_with_more_fields(self):
        """Test completeness score increases as more fields are added."""
        data = {"name": "Test"}
        assessment1 = self.gate.assess(data, "whiskey")

        data["brand"] = "TestBrand"
        assessment2 = self.gate.assess(data, "whiskey")

        data["abv"] = 40.0
        assessment3 = self.gate.assess(data, "whiskey")

        self.assertLess(assessment1.completeness_score, assessment2.completeness_score)
        self.assertLess(assessment2.completeness_score, assessment3.completeness_score)

    def test_needs_enrichment_false_only_for_enriched(self):
        """Test needs_enrichment is False only for ENRICHED status."""
        statuses_and_needs = [
            ({"name": "Test"}, True),  # SKELETON
            ({"name": "Test", "brand": "B", "abv": 40}, True),  # PARTIAL
            ({"name": "Test", "brand": "B", "abv": 40, "description": "D"}, True),  # COMPLETE
            (
                {"name": "Test", "brand": "B", "abv": 40, "description": "D", "awards": [{"n": "G"}]},
                False,
            ),  # ENRICHED
        ]

        for data, expected_needs in statuses_and_needs:
            assessment = self.gate.assess(data, "whiskey")
            self.assertEqual(
                assessment.needs_enrichment,
                expected_needs,
                f"For data {data}, needs_enrichment should be {expected_needs}",
            )
