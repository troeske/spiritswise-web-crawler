"""
Unit tests for Quality Gate ECP Integration.

Task 3.4: Integrate ECP into Quality Gate

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3

Tests verify:
- ECP calculated during assess()
- ECP stored in QualityAssessment
- COMPLETE promotion based on ECP
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, QualityAssessment, ProductStatus


class ECPCalculationDuringAssessTests(TestCase):
    """Tests for ECP calculation during assess()."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_assess_calculates_ecp_when_field_groups_available(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test assess() calculates ECP when field groups are available."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "basic_product_info", "fields": ["name", "brand", "abv"], "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "basic_product_info": {"populated": 2, "total": 3, "percentage": 66.67, "missing": ["abv"]}
        }
        mock_calculator.calculate_total_ecp.return_value = 66.67
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey")

        mock_calculator.load_field_groups_for_product_type.assert_called_with("whiskey")
        mock_calculator.calculate_ecp_by_group.assert_called_once()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_assess_skips_ecp_when_no_field_groups(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test assess() skips ECP calculation when no field groups available."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = []
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey")

        # Should not call calculate methods when no field groups
        mock_calculator.calculate_ecp_by_group.assert_not_called()


class ECPStorageInAssessmentTests(TestCase):
    """Tests for ECP storage in QualityAssessment."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_assessment_has_ecp_total(self, mock_get_config, mock_get_ecp_calc):
        """Test assessment includes ecp_total from calculation."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "test", "fields": ["name", "brand"], "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "test": {"populated": 2, "total": 2, "percentage": 100.0, "missing": []}
        }
        mock_calculator.calculate_total_ecp.return_value = 100.0
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.ecp_total, 100.0)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_assessment_has_ecp_by_group(self, mock_get_config, mock_get_ecp_calc):
        """Test assessment includes ecp_by_group from calculation."""
        mock_get_config.return_value = None

        ecp_by_group = {
            "basic_product_info": {"populated": 3, "total": 5, "percentage": 60.0, "missing": ["abv", "volume_ml"]},
            "tasting_nose": {"populated": 1, "total": 3, "percentage": 33.33, "missing": ["primary_aromas", "secondary_aromas"]}
        }

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "basic_product_info", "fields": ["name", "brand", "description", "abv", "volume_ml"], "is_active": True},
            {"group_key": "tasting_nose", "fields": ["nose_description", "primary_aromas", "secondary_aromas"], "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = ecp_by_group
        mock_calculator.calculate_total_ecp.return_value = 50.0
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey", "brand": "Test Brand", "description": "Test", "nose_description": "Vanilla"}

        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.ecp_by_group, ecp_by_group)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_assessment_ecp_defaults_when_no_groups(self, mock_get_config, mock_get_ecp_calc):
        """Test assessment has default ECP values when no field groups available."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = []
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey"}

        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.ecp_total, 0.0)
        self.assertEqual(result.ecp_by_group, {})


class ECPCompletePromotionTests(TestCase):
    """Tests for COMPLETE status promotion based on ECP."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_product_promoted_to_complete_at_90_percent_ecp(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test product is promoted to COMPLETE when ECP >= 90%."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "test", "fields": ["name", "brand", "abv", "volume_ml", "description",
                                              "region", "country", "category", "primary_aromas", "finish_flavors"],
             "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "test": {"populated": 9, "total": 10, "percentage": 90.0, "missing": ["finish_flavors"]}
        }
        mock_calculator.calculate_total_ecp.return_value = 90.0
        mock_get_ecp_calc.return_value = mock_calculator

        # Full product data that would otherwise be ENRICHED
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "primary_aromas": ["vanilla"],
        }

        result = self.quality_gate.assess(data, "whiskey")

        self.assertEqual(result.status, ProductStatus.COMPLETE)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_product_not_promoted_below_90_percent_ecp(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test product is NOT promoted to COMPLETE when ECP < 90%."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "test", "fields": ["name", "brand", "abv", "volume_ml", "description",
                                              "region", "country", "category", "primary_aromas", "finish_flavors"],
             "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "test": {"populated": 8, "total": 10, "percentage": 80.0, "missing": ["primary_aromas", "finish_flavors"]}
        }
        mock_calculator.calculate_total_ecp.return_value = 80.0
        mock_get_ecp_calc.return_value = mock_calculator

        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }

        result = self.quality_gate.assess(data, "whiskey")

        self.assertNotEqual(result.status, ProductStatus.COMPLETE)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_complete_requires_ecp_not_just_enriched(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test COMPLETE requires 90% ECP, not just ENRICHED fields."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "test", "fields": ["name", "brand", "abv"], "is_active": True}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "test": {"populated": 3, "total": 3, "percentage": 100.0, "missing": []}
        }
        # Even 100% of one group may not equal 90% overall
        mock_calculator.calculate_total_ecp.return_value = 50.0
        mock_get_ecp_calc.return_value = mock_calculator

        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
        }

        result = self.quality_gate.assess(data, "whiskey")

        # Should be SKELETON (only has minimal fields), not COMPLETE
        self.assertNotEqual(result.status, ProductStatus.COMPLETE)


class ECPOverrideTests(TestCase):
    """Tests for passing pre-calculated ECP."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_passed_ecp_total_used_for_status(self):
        """Test pre-calculated ecp_total is used for status determination."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        # Pass a high ECP total
        result = self.quality_gate.assess(data, "whiskey", ecp_total=95.0)

        self.assertEqual(result.status, ProductStatus.COMPLETE)
        self.assertEqual(result.ecp_total, 95.0)

    def test_passed_ecp_total_overrides_calculation(self):
        """Test passed ecp_total takes precedence over calculation."""
        data = {"name": "Test Whiskey"}

        # This data would normally have low ECP, but we pass a high value
        result = self.quality_gate.assess(data, "whiskey", ecp_total=92.0)

        self.assertEqual(result.status, ProductStatus.COMPLETE)


class ECPNeedsEnrichmentTests(TestCase):
    """Tests for needs_enrichment based on ECP."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_needs_enrichment_false_at_complete(self):
        """Test needs_enrichment is False when at COMPLETE status."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey", ecp_total=95.0)

        self.assertEqual(result.status, ProductStatus.COMPLETE)
        self.assertFalse(result.needs_enrichment)

    def test_needs_enrichment_true_below_complete(self):
        """Test needs_enrichment is True when below COMPLETE status."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey", ecp_total=85.0)

        self.assertNotEqual(result.status, ProductStatus.COMPLETE)
        self.assertTrue(result.needs_enrichment)


class ECPEdgeCaseTests(TestCase):
    """Tests for ECP edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    @patch.object(QualityGateV3, '_get_quality_gate_config')
    def test_ecp_calculation_error_does_not_crash(
        self, mock_get_config, mock_get_ecp_calc
    ):
        """Test ECP calculation errors don't crash assess()."""
        mock_get_config.return_value = None

        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.side_effect = Exception("DB error")
        mock_get_ecp_calc.return_value = mock_calculator

        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        # Should not raise, should return assessment with default ECP
        result = self.quality_gate.assess(data, "whiskey")

        self.assertIsInstance(result, QualityAssessment)
        self.assertEqual(result.ecp_total, 0.0)

    def test_ecp_exactly_90_is_complete(self):
        """Test ECP exactly at 90.0 qualifies as COMPLETE."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey", ecp_total=90.0)

        self.assertEqual(result.status, ProductStatus.COMPLETE)

    def test_ecp_just_below_90_is_not_complete(self):
        """Test ECP just below 90.0 does NOT qualify as COMPLETE."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.quality_gate.assess(data, "whiskey", ecp_total=89.99)

        self.assertNotEqual(result.status, ProductStatus.COMPLETE)
