"""
Unit tests for V3 QualityAssessment Dataclass.

Task 2.7: Update QualityAssessment Dataclass

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 6

Tests verify:
- ECP fields in assessment result (ecp_by_group, ecp_total)
- missing_or_fields for ENRICHED status
- All fields have correct types and defaults
"""

from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityAssessment, ProductStatus


class QualityAssessmentFieldsTests(TestCase):
    """Tests for QualityAssessment dataclass fields."""

    def test_has_status_field(self):
        """Test QualityAssessment has status field."""
        assessment = QualityAssessment(status=ProductStatus.BASELINE, completeness_score=0.5)
        self.assertEqual(assessment.status, ProductStatus.BASELINE)

    def test_has_completeness_score_field(self):
        """Test QualityAssessment has completeness_score field."""
        assessment = QualityAssessment(status=ProductStatus.BASELINE, completeness_score=0.75)
        self.assertEqual(assessment.completeness_score, 0.75)

    def test_has_populated_fields(self):
        """Test QualityAssessment has populated_fields field."""
        assessment = QualityAssessment(
            status=ProductStatus.BASELINE,
            completeness_score=0.5,
            populated_fields=["name", "brand", "abv"]
        )
        self.assertEqual(assessment.populated_fields, ["name", "brand", "abv"])

    def test_has_missing_required_fields(self):
        """Test QualityAssessment has missing_required_fields field."""
        assessment = QualityAssessment(
            status=ProductStatus.PARTIAL,
            completeness_score=0.3,
            missing_required_fields=["description", "volume_ml"]
        )
        self.assertEqual(assessment.missing_required_fields, ["description", "volume_ml"])

    def test_has_ecp_total_field(self):
        """Test QualityAssessment has ecp_total field (V3)."""
        assessment = QualityAssessment(
            status=ProductStatus.ENRICHED,
            completeness_score=0.8,
            ecp_total=85.5
        )
        self.assertEqual(assessment.ecp_total, 85.5)

    def test_has_ecp_by_group_field(self):
        """Test QualityAssessment has ecp_by_group field (V3)."""
        ecp_by_group = {
            "basic_product_info": {"filled": 7, "total": 9, "percentage": 77.78},
            "tasting_nose": {"filled": 4, "total": 5, "percentage": 80.0}
        }
        assessment = QualityAssessment(
            status=ProductStatus.ENRICHED,
            completeness_score=0.8,
            ecp_by_group=ecp_by_group
        )
        self.assertEqual(assessment.ecp_by_group, ecp_by_group)

    def test_has_missing_or_fields(self):
        """Test QualityAssessment has missing_or_fields field (V3)."""
        missing_or = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"]
        ]
        assessment = QualityAssessment(
            status=ProductStatus.BASELINE,
            completeness_score=0.7,
            missing_or_fields=missing_or
        )
        self.assertEqual(assessment.missing_or_fields, missing_or)


class QualityAssessmentDefaultsTests(TestCase):
    """Tests for QualityAssessment default values."""

    def test_populated_fields_defaults_to_empty_list(self):
        """Test populated_fields defaults to empty list."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.populated_fields, [])

    def test_missing_required_fields_defaults_to_empty_list(self):
        """Test missing_required_fields defaults to empty list."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.missing_required_fields, [])

    def test_missing_or_fields_defaults_to_empty_list(self):
        """Test missing_or_fields defaults to empty list."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.missing_or_fields, [])

    def test_ecp_total_defaults_to_zero(self):
        """Test ecp_total defaults to 0.0."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.ecp_total, 0.0)

    def test_ecp_by_group_defaults_to_empty_dict(self):
        """Test ecp_by_group defaults to empty dict."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.ecp_by_group, {})

    def test_enrichment_priority_defaults_to_five(self):
        """Test enrichment_priority defaults to 5."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.enrichment_priority, 5)

    def test_needs_enrichment_defaults_to_true(self):
        """Test needs_enrichment defaults to True."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertTrue(assessment.needs_enrichment)

    def test_rejection_reason_defaults_to_none(self):
        """Test rejection_reason defaults to None."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertIsNone(assessment.rejection_reason)

    def test_low_confidence_fields_defaults_to_empty_list(self):
        """Test low_confidence_fields defaults to empty list."""
        assessment = QualityAssessment(status=ProductStatus.REJECTED, completeness_score=0.0)
        self.assertEqual(assessment.low_confidence_fields, [])


class QualityAssessmentIntegrationTests(TestCase):
    """Tests for QualityAssessment integration with QualityGateV3."""

    def setUp(self):
        """Set up test fixtures."""
        from crawler.services.quality_gate_v3 import QualityGateV3
        self.quality_gate = QualityGateV3()

    def test_assessment_has_ecp_total_from_assess(self):
        """Test assess() populates ecp_total in result."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}
        result = self.quality_gate.assess(data, "whiskey", ecp_total=45.5)

        self.assertEqual(result.ecp_total, 45.5)

    def test_assessment_has_missing_or_fields_for_baseline(self):
        """Test assess() populates missing_or_fields for BASELINE status."""
        # BASELINE data without mouthfeel/complexity
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
        }
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.BASELINE)
        # Should have missing OR fields for upgrading to ENRICHED
        self.assertTrue(len(result.missing_or_fields) > 0)

    def test_assessment_no_missing_or_fields_at_enriched(self):
        """Test assess() has no missing_or_fields when ENRICHED."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Sherry",
        }
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.ENRICHED)
        # Should have no missing OR fields at ENRICHED
        self.assertEqual(result.missing_or_fields, [])

    def test_assessment_needs_enrichment_at_partial(self):
        """Test needs_enrichment is True at PARTIAL status."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.PARTIAL)
        self.assertTrue(result.needs_enrichment)

    def test_assessment_needs_enrichment_false_at_complete(self):
        """Test needs_enrichment is False at COMPLETE status."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
        }
        result = self.quality_gate.assess(data, "whiskey", ecp_total=95.0)

        self.assertEqual(result.status, ProductStatus.COMPLETE)
        self.assertFalse(result.needs_enrichment)


class QualityAssessmentMissingFieldsTests(TestCase):
    """Tests for missing fields tracking in QualityAssessment."""

    def setUp(self):
        """Set up test fixtures."""
        from crawler.services.quality_gate_v3 import QualityGateV3
        self.quality_gate = QualityGateV3()

    def test_missing_required_at_skeleton(self):
        """Test missing_required_fields at SKELETON status."""
        data = {"name": "Test Whiskey"}
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.SKELETON)
        # Should list partial requirements
        self.assertIn("brand", result.missing_required_fields)
        self.assertIn("abv", result.missing_required_fields)

    def test_missing_required_at_partial(self):
        """Test missing_required_fields at PARTIAL status."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.PARTIAL)
        # Should list baseline requirements
        self.assertIn("volume_ml", result.missing_required_fields)
        self.assertIn("description", result.missing_required_fields)

    def test_missing_or_at_baseline(self):
        """Test missing_or_fields at BASELINE status."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
        }
        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.BASELINE)
        # Should have OR fields for ENRICHED upgrade
        found_complexity = False
        found_cask = False
        for group in result.missing_or_fields:
            if "complexity" in group or "overall_complexity" in group:
                found_complexity = True
            if "finishing_cask" in group or "maturation_notes" in group:
                found_cask = True
        self.assertTrue(found_complexity)
        self.assertTrue(found_cask)
