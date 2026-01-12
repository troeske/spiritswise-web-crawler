"""
Unit tests for V3 Ruby Exception for Port Wine.

Task 2.4: Implement Ruby Exception for Port Wine

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2.3

Tests verify:
- Ruby style waives indication_age/harvest_year requirement
- Reserve Ruby style also waives the requirement
- Tawny style still requires indication_age
- Vintage style still requires harvest_year
- Other styles (LBV, Colheita) still require age indication
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class RubyExceptionBasicTests(TestCase):
    """Tests for basic Ruby exception behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_check_or_field_exceptions_ruby_waives_age(self):
        """Test Ruby style waives indication_age/harvest_year OR requirement."""
        or_fields = [["indication_age", "harvest_year"]]
        exceptions = {"style": ["ruby", "reserve_ruby"]}
        product_data = {"style": "ruby"}

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        # Ruby should waive the age OR group
        self.assertEqual(filtered, [])

    def test_check_or_field_exceptions_reserve_ruby_waives_age(self):
        """Test Reserve Ruby style also waives indication_age/harvest_year."""
        or_fields = [["indication_age", "harvest_year"]]
        exceptions = {"style": ["ruby", "reserve_ruby"]}
        product_data = {"style": "reserve_ruby"}

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        self.assertEqual(filtered, [])

    def test_check_or_field_exceptions_case_insensitive(self):
        """Test exception matching is case-insensitive."""
        or_fields = [["indication_age", "harvest_year"]]
        exceptions = {"style": ["ruby", "reserve_ruby"]}
        product_data = {"style": "Ruby"}  # Capital R

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        self.assertEqual(filtered, [])

    def test_check_or_field_exceptions_tawny_keeps_age(self):
        """Test Tawny style keeps the age OR requirement."""
        or_fields = [["indication_age", "harvest_year"]]
        exceptions = {"style": ["ruby", "reserve_ruby"]}
        product_data = {"style": "Tawny"}

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        # Tawny should NOT waive, original OR group remains
        self.assertEqual(filtered, [["indication_age", "harvest_year"]])

    def test_check_or_field_exceptions_no_exceptions_defined(self):
        """Test no waiving when no exceptions defined."""
        or_fields = [["indication_age", "harvest_year"]]
        exceptions = {}
        product_data = {"style": "ruby"}

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        # No exceptions defined, original OR group remains
        self.assertEqual(filtered, [["indication_age", "harvest_year"]])

    def test_check_or_field_exceptions_preserves_other_or_groups(self):
        """Test exception only affects age OR group, not other OR groups."""
        or_fields = [
            ["indication_age", "harvest_year"],
            ["complexity", "overall_complexity"]
        ]
        exceptions = {"style": ["ruby", "reserve_ruby"]}
        product_data = {"style": "ruby"}

        filtered = self.quality_gate._check_or_field_exceptions(
            or_fields, exceptions, product_data
        )

        # Only age group waived, complexity group remains
        self.assertEqual(filtered, [["complexity", "overall_complexity"]])


class RubyExceptionStatusTests(TestCase):
    """Tests for Ruby exception affecting status determination."""

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

    def test_ruby_port_reaches_baseline_without_age(self):
        """Test Ruby port wine reaches BASELINE without indication_age or harvest_year."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "ruby",
                "volume_ml": 750,
                "description": "A classic ruby port",
                "primary_aromas": ["plum", "cherry"],
                "finish_flavors": ["spice"],
                "palate_flavors": ["blackberry"],
                "producer_house": "Graham's Port Lodge",
                # No indication_age or harvest_year - should still reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_reserve_ruby_port_reaches_baseline_without_age(self):
        """Test Reserve Ruby port wine reaches BASELINE without indication_age."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's Six Grapes Reserve",
                "brand": "Graham's",
                "abv": "20%",
                "style": "reserve_ruby",
                "volume_ml": 750,
                "description": "A reserve ruby port",
                "primary_aromas": ["plum", "cherry"],
                "finish_flavors": ["chocolate"],
                "palate_flavors": ["blackberry"],
                "producer_house": "Graham's Port Lodge",
                # No indication_age or harvest_year - should still reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_tawny_port_requires_age_for_baseline(self):
        """Test Tawny port wine requires indication_age for BASELINE."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
                "volume_ml": 750,
                "description": "A fine aged tawny",
                "primary_aromas": ["caramel", "nuts"],
                "finish_flavors": ["dried fruit"],
                "palate_flavors": ["toffee"],
                "producer_house": "Graham's Port Lodge",
                # Missing indication_age - should NOT reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_tawny_port_reaches_baseline_with_age(self):
        """Test Tawny port wine reaches BASELINE with indication_age."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
                "volume_ml": 750,
                "description": "A fine aged tawny",
                "primary_aromas": ["caramel", "nuts"],
                "finish_flavors": ["dried fruit"],
                "palate_flavors": ["toffee"],
                "producer_house": "Graham's Port Lodge",
                "indication_age": "20 Year Old",  # Has age indication
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class VintagePortRequirementsTests(TestCase):
    """Tests for Vintage port wine requirements."""

    def setUp(self):
        """Set up test fixtures with mocked config."""
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
        self.mock_config.enriched_or_fields = []

    def test_vintage_port_requires_harvest_year_for_baseline(self):
        """Test Vintage port wine requires harvest_year for BASELINE."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 2017 Vintage",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Vintage",
                "volume_ml": 750,
                "description": "A fine vintage port",
                "primary_aromas": ["blackberry"],
                "finish_flavors": ["chocolate"],
                "palate_flavors": ["dark fruit"],
                "producer_house": "Graham's Port Lodge",
                # Missing harvest_year - should NOT reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_vintage_port_reaches_baseline_with_harvest_year(self):
        """Test Vintage port wine reaches BASELINE with harvest_year."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 2017 Vintage",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Vintage",
                "volume_ml": 750,
                "description": "A fine vintage port",
                "primary_aromas": ["blackberry"],
                "finish_flavors": ["chocolate"],
                "palate_flavors": ["dark fruit"],
                "producer_house": "Graham's Port Lodge",
                "harvest_year": "2017",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class OtherPortStylesTests(TestCase):
    """Tests for other port wine styles (LBV, Colheita, etc.)."""

    def setUp(self):
        """Set up test fixtures with mocked config."""
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
        self.mock_config.enriched_or_fields = []

    def test_lbv_port_requires_age_for_baseline(self):
        """Test LBV port wine requires harvest_year for BASELINE."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's LBV 2018",
                "brand": "Graham's",
                "abv": "20%",
                "style": "LBV",
                "volume_ml": 750,
                "description": "Late Bottled Vintage port",
                "primary_aromas": ["plum"],
                "finish_flavors": ["spice"],
                "palate_flavors": ["dark fruit"],
                "producer_house": "Graham's Port Lodge",
                # Missing harvest_year - should NOT reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_lbv_port_reaches_baseline_with_harvest_year(self):
        """Test LBV port wine reaches BASELINE with harvest_year."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's LBV 2018",
                "brand": "Graham's",
                "abv": "20%",
                "style": "LBV",
                "volume_ml": 750,
                "description": "Late Bottled Vintage port",
                "primary_aromas": ["plum"],
                "finish_flavors": ["spice"],
                "palate_flavors": ["dark fruit"],
                "producer_house": "Graham's Port Lodge",
                "harvest_year": "2018",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_colheita_port_requires_age_for_baseline(self):
        """Test Colheita port wine requires harvest_year for BASELINE."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's Colheita 1985",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Colheita",
                "volume_ml": 750,
                "description": "Single harvest tawny port",
                "primary_aromas": ["caramel"],
                "finish_flavors": ["nuts"],
                "palate_flavors": ["dried fruit"],
                "producer_house": "Graham's Port Lodge",
                # Missing harvest_year - should NOT reach BASELINE
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_colheita_port_reaches_baseline_with_harvest_year(self):
        """Test Colheita port wine reaches BASELINE with harvest_year."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's Colheita 1985",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Colheita",
                "volume_ml": 750,
                "description": "Single harvest tawny port",
                "primary_aromas": ["caramel"],
                "finish_flavors": ["nuts"],
                "palate_flavors": ["dried fruit"],
                "producer_house": "Graham's Port Lodge",
                "harvest_year": "1985",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class MissingOrFieldsWithExceptionTests(TestCase):
    """Tests for missing OR fields reporting with exceptions applied."""

    def setUp(self):
        """Set up test fixtures with mocked config."""
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
        self.mock_config.enriched_or_fields = []

    def test_ruby_does_not_report_age_as_missing(self):
        """Test Ruby port doesn't report indication_age/harvest_year as missing."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "ruby",
            }
            result = self.quality_gate.assess(data, "port_wine")

            # Ruby is PARTIAL (missing baseline required fields)
            self.assertEqual(result.status, ProductStatus.PARTIAL)
            # Missing OR fields should NOT include age group for Ruby
            for group in result.missing_or_fields:
                self.assertNotIn("indication_age", group)
                self.assertNotIn("harvest_year", group)

    def test_tawny_reports_age_as_missing(self):
        """Test Tawny port reports indication_age/harvest_year as missing."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_config):
            data = {
                "name": "Graham's 20 Year Old Tawny",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Tawny",
            }
            result = self.quality_gate.assess(data, "port_wine")

            # Tawny is PARTIAL (missing baseline required fields)
            self.assertEqual(result.status, ProductStatus.PARTIAL)
            # Missing OR fields SHOULD include age group for Tawny
            found_age_group = False
            for group in result.missing_or_fields:
                if "indication_age" in group or "harvest_year" in group:
                    found_age_group = True
                    break
            self.assertTrue(found_age_group)
