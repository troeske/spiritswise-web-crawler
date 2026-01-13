"""
E2E tests for 90% ECP to COMPLETE Status.

Task 5.4: E2E Test - 90% ECP to COMPLETE

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2.4

Tests verify:
- Product with 90%+ populated fields
- Automatic promotion to COMPLETE
- ECP persisted correctly
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class ECPCompleteThresholdTests(TestCase):
    """Tests for 90% ECP threshold to COMPLETE."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_90_percent_ecp_promotes_to_complete(self, mock_get_calculator):
        """Test 90% ECP promotes to COMPLETE."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 9, "total": 10, "percentage": 90.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 90.0
        mock_get_calculator.return_value = mock_calculator

        # Product with all ENRICHED requirements met
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Oloroso Sherry"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_89_percent_ecp_stays_enriched(self, mock_get_calculator):
        """Test 89% ECP stays at ENRICHED."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 89, "total": 100, "percentage": 89.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 89.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Oloroso Sherry"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.ENRICHED.value)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_95_percent_ecp_is_complete(self, mock_get_calculator):
        """Test 95% ECP is COMPLETE."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["f1", "f2", "f3", "f4", "f5"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 95, "total": 100, "percentage": 95.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 95.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Oloroso Sherry"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)


class ECPPersistenceTests(TestCase):
    """Tests for ECP persistence."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_ecp_total_in_assessment(self, mock_get_calculator):
        """Test ECP total is included in assessment."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "basic", "fields": ["name", "brand"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "basic": {"populated": 2, "total": 2, "percentage": 100.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 75.5
        mock_get_calculator.return_value = mock_calculator

        product_data = {"name": "Test", "brand": "Test"}

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.ecp_total, 75.5)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_ecp_by_group_in_assessment(self, mock_get_calculator):
        """Test ECP by group is included in assessment."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "basic", "fields": ["name", "brand"]},
            {"group_key": "tasting", "fields": ["nose", "palate"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "basic": {"populated": 2, "total": 2, "percentage": 100.0},
            "tasting": {"populated": 1, "total": 2, "percentage": 50.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 75.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {"name": "Test", "brand": "Test", "nose": "Honey"}

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertIn("basic", assessment.ecp_by_group)
        self.assertIn("tasting", assessment.ecp_by_group)


class EdgeCaseTests(TestCase):
    """Tests for edge cases in ECP calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_exactly_90_percent_is_complete(self, mock_get_calculator):
        """Test exactly 90.0% ECP is COMPLETE."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["f1"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 90, "total": 100, "percentage": 90.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 90.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Test",
            "brand": "Test",
            "abv": 40.0,
            "region": "Test",
            "country": "Test",
            "category": "Test",
            "volume_ml": 700,
            "description": "Test",
            "primary_aromas": ["test"],
            "finish_flavors": ["test"],
            "age_statement": "NAS",
            "primary_cask": "Test",
            "palate_flavors": ["test"],
            "mouthfeel": "Test",
            "complexity": "Test",
            "finishing_cask": "Test"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_89_99_percent_is_enriched(self, mock_get_calculator):
        """Test 89.99% ECP is ENRICHED (not COMPLETE)."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["f1"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 8999, "total": 10000, "percentage": 89.99}
        }
        mock_calculator.calculate_total_ecp.return_value = 89.99
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Test",
            "brand": "Test",
            "abv": 40.0,
            "region": "Test",
            "country": "Test",
            "category": "Test",
            "volume_ml": 700,
            "description": "Test",
            "primary_aromas": ["test"],
            "finish_flavors": ["test"],
            "age_statement": "NAS",
            "primary_cask": "Test",
            "palate_flavors": ["test"],
            "mouthfeel": "Test",
            "complexity": "Test",
            "finishing_cask": "Test"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.ENRICHED.value)

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_100_percent_is_complete(self, mock_get_calculator):
        """Test 100% ECP is COMPLETE."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["name"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 10, "total": 10, "percentage": 100.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 100.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Complete Product",
            "brand": "Test",
            "abv": 40.0,
            "region": "Test",
            "country": "Test",
            "category": "Test",
            "volume_ml": 700,
            "description": "Test",
            "primary_aromas": ["test"],
            "finish_flavors": ["test"],
            "age_statement": "NAS",
            "primary_cask": "Test",
            "palate_flavors": ["test"],
            "mouthfeel": "Test",
            "complexity": "Test",
            "finishing_cask": "Test"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)


class NeedsEnrichmentTests(TestCase):
    """Tests for needs_enrichment flag."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_complete_does_not_need_enrichment(self, mock_get_calculator):
        """Test COMPLETE status sets needs_enrichment to False."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["name"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 95, "total": 100, "percentage": 95.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 95.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Test",
            "brand": "Test",
            "abv": 40.0,
            "region": "Test",
            "country": "Test",
            "category": "Test",
            "volume_ml": 700,
            "description": "Test",
            "primary_aromas": ["test"],
            "finish_flavors": ["test"],
            "age_statement": "NAS",
            "primary_cask": "Test",
            "palate_flavors": ["test"],
            "mouthfeel": "Test",
            "complexity": "Test",
            "finishing_cask": "Test"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        # COMPLETE status means needs_enrichment should be False
        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)
        self.assertFalse(assessment.needs_enrichment)

    def test_skeleton_needs_enrichment(self):
        """Test SKELETON status needs enrichment."""
        product_data = {"name": "Test"}

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertTrue(assessment.needs_enrichment)
