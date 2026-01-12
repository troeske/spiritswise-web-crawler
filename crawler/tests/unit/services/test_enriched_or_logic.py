"""
Unit tests for V3 ENRICHED Status OR Logic.

Task 2.3: Implement OR Logic for ENRICHED Status

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2.2

Tests verify:
- complexity OR overall_complexity satisfies requirement
- finishing_cask OR maturation_notes (whiskey)
- grape_varieties OR quinta (port wine)
- All OR groups must be satisfied (each group needs at least one)
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class EnrichedOrLogicBasicTests(TestCase):
    """Tests for basic ENRICHED OR logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_check_or_fields_single_group_first_field(self):
        """Test OR logic satisfied when first field in group is present."""
        populated = {"complexity"}
        or_groups = [["complexity", "overall_complexity"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)

    def test_check_or_fields_single_group_second_field(self):
        """Test OR logic satisfied when second field in group is present."""
        populated = {"overall_complexity"}
        or_groups = [["complexity", "overall_complexity"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)

    def test_check_or_fields_single_group_both_fields(self):
        """Test OR logic satisfied when both fields in group are present."""
        populated = {"complexity", "overall_complexity"}
        or_groups = [["complexity", "overall_complexity"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)

    def test_check_or_fields_single_group_neither_field(self):
        """Test OR logic fails when neither field in group is present."""
        populated = {"mouthfeel"}
        or_groups = [["complexity", "overall_complexity"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertFalse(result)

    def test_check_or_fields_multiple_groups_all_satisfied(self):
        """Test OR logic passes when all groups have at least one field."""
        populated = {"complexity", "finishing_cask"}
        or_groups = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"]
        ]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)

    def test_check_or_fields_multiple_groups_one_missing(self):
        """Test OR logic fails when one group has no fields."""
        populated = {"complexity"}  # Has first group, missing second
        or_groups = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"]
        ]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertFalse(result)

    def test_check_or_fields_empty_groups(self):
        """Test OR logic passes when no OR groups defined."""
        populated = {"complexity"}
        or_groups = []

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)


class WhiskeyEnrichedOrLogicTests(TestCase):
    """Tests for whiskey ENRICHED OR logic."""

    def setUp(self):
        """Set up test fixtures with whiskey BASELINE data."""
        self.quality_gate = QualityGateV3()
        self.baseline_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey", "caramel"],
        }

    def test_whiskey_enriched_with_complexity(self):
        """Test whiskey reaches ENRICHED with complexity + mouthfeel."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["complexity"] = "Complex"
        data["finishing_cask"] = "Sherry"

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_whiskey_enriched_with_overall_complexity(self):
        """Test whiskey reaches ENRICHED with overall_complexity + mouthfeel."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["overall_complexity"] = "Very Complex"
        data["maturation_notes"] = "Aged in oak"

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_whiskey_enriched_with_finishing_cask(self):
        """Test whiskey reaches ENRICHED with finishing_cask OR field."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["complexity"] = "Complex"
        data["finishing_cask"] = "Oloroso Sherry"

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_whiskey_enriched_with_maturation_notes(self):
        """Test whiskey reaches ENRICHED with maturation_notes OR field."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["overall_complexity"] = "Complex"
        data["maturation_notes"] = "12 years in American oak"

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_whiskey_baseline_without_mouthfeel(self):
        """Test whiskey stays at BASELINE without mouthfeel."""
        data = {**self.baseline_data}
        data["complexity"] = "Complex"
        data["finishing_cask"] = "Sherry"
        # Missing: mouthfeel

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_whiskey_baseline_missing_complexity_or(self):
        """Test whiskey stays at BASELINE without complexity OR group."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["finishing_cask"] = "Sherry"
        # Missing: complexity AND overall_complexity

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_whiskey_baseline_missing_cask_or(self):
        """Test whiskey stays at BASELINE without finishing_cask OR group."""
        data = {**self.baseline_data}
        data["mouthfeel"] = "Full-bodied"
        data["complexity"] = "Complex"
        # Missing: finishing_cask AND maturation_notes

        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.BASELINE)


class PortWineEnrichedOrLogicTests(TestCase):
    """Tests for port wine ENRICHED OR logic."""

    def setUp(self):
        """Set up test fixtures with mocked port wine config."""
        self.quality_gate = QualityGateV3()
        self.mock_config = MagicMock()
        self.mock_config.skeleton_required_fields = ["name"]
        self.mock_config.partial_required_fields = ["name", "brand", "abv", "style"]
        self.mock_config.baseline_required_fields = [
            "name", "brand", "abv", "style",
            "volume_ml", "description",
            "primary_aromas", "finish_flavors", "palate_flavors",
            "producer_house"
        ]
        self.mock_config.baseline_or_fields = [["indication_age", "harvest_year"]]
        self.mock_config.baseline_or_field_exceptions = {"style": ["ruby", "reserve_ruby"]}
        self.mock_config.enriched_required_fields = ["mouthfeel"]
        self.mock_config.enriched_or_fields = [
            ["complexity", "overall_complexity"],
            ["grape_varieties", "quinta"]
        ]

    def test_port_enriched_with_grape_varieties(self):
        """Test port wine reaches ENRICHED with grape_varieties."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
                "volume_ml": 750,
                "description": "A fine aged port",
                "primary_aromas": ["caramel", "nuts"],
                "finish_flavors": ["dried fruit"],
                "palate_flavors": ["toffee"],
                "producer_house": "Graham's Port Lodge",
                "indication_age": "20 Year Old",
                "mouthfeel": "Silky",
                "complexity": "Highly complex",
                "grape_varieties": ["Touriga Nacional", "Touriga Franca"],
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_port_enriched_with_quinta(self):
        """Test port wine reaches ENRICHED with quinta."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
                "volume_ml": 750,
                "description": "A fine aged port",
                "primary_aromas": ["caramel", "nuts"],
                "finish_flavors": ["dried fruit"],
                "palate_flavors": ["toffee"],
                "producer_house": "Graham's Port Lodge",
                "indication_age": "20 Year Old",
                "mouthfeel": "Silky",
                "overall_complexity": "Very complex",
                "quinta": "Quinta dos Malvedos",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_port_baseline_missing_grape_or_quinta(self):
        """Test port wine stays at BASELINE without grape_varieties OR quinta."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
                "volume_ml": 750,
                "description": "A fine aged port",
                "primary_aromas": ["caramel", "nuts"],
                "finish_flavors": ["dried fruit"],
                "palate_flavors": ["toffee"],
                "producer_house": "Graham's Port Lodge",
                "indication_age": "20 Year Old",
                "mouthfeel": "Silky",
                "complexity": "Complex",
                # Missing: grape_varieties AND quinta
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class MissingOrFieldsReportingTests(TestCase):
    """Tests for missing OR fields reporting."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_missing_or_fields_reported_for_enriched(self):
        """Test missing OR fields reported when upgrading to ENRICHED."""
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

        # At BASELINE, missing_or_fields should show what's needed for ENRICHED
        self.assertEqual(result.status, ProductStatus.BASELINE)
        # Should have the two OR field groups
        self.assertTrue(len(result.missing_or_fields) >= 1)
        # First OR group should be complexity options
        found_complexity_group = False
        for group in result.missing_or_fields:
            if "complexity" in group or "overall_complexity" in group:
                found_complexity_group = True
                break
        self.assertTrue(found_complexity_group)

    def test_no_missing_or_fields_when_satisfied(self):
        """Test no missing OR fields when all are satisfied."""
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
        # At ENRICHED, no missing OR fields for current level
        self.assertEqual(result.missing_or_fields, [])


class EnrichedOrLogicEdgeCasesTests(TestCase):
    """Tests for ENRICHED OR logic edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_empty_string_not_counted(self):
        """Test empty string fields don't satisfy OR requirement."""
        populated = self.quality_gate._get_populated_fields({
            "complexity": "",
            "overall_complexity": "Very Complex"
        })
        or_groups = [["complexity", "overall_complexity"]]

        # complexity is empty string, but overall_complexity has value
        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)
        self.assertNotIn("complexity", populated)
        self.assertIn("overall_complexity", populated)

    def test_none_value_not_counted(self):
        """Test None fields don't satisfy OR requirement."""
        populated = self.quality_gate._get_populated_fields({
            "complexity": None,
            "overall_complexity": "Very Complex"
        })
        or_groups = [["complexity", "overall_complexity"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)

    def test_empty_list_not_counted(self):
        """Test empty list fields don't satisfy OR requirement."""
        populated = self.quality_gate._get_populated_fields({
            "grape_varieties": [],
            "quinta": "Quinta X"
        })
        or_groups = [["grape_varieties", "quinta"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)
        self.assertNotIn("grape_varieties", populated)
        self.assertIn("quinta", populated)

    def test_three_option_or_group(self):
        """Test OR group with three options."""
        populated = {"option_b"}
        or_groups = [["option_a", "option_b", "option_c"]]

        result = self.quality_gate._check_or_fields(populated, or_groups)
        self.assertTrue(result)
