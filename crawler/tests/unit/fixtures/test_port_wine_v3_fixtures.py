"""
Unit tests for Port Wine V3 Fixtures.

Task 1.6: Create Fixtures for Port Wine Config

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Appendix C & D

Tests verify:
- Fixture loads correctly
- All field groups present with correct fields (50 total)
- Status thresholds match V3 spec
- Ruby exception for baseline OR fields
- Pipeline config has V3 defaults
"""

import json
from pathlib import Path
from django.test import TestCase


class PortWineV3FixtureLoadTests(TestCase):
    """Tests for loading port wine V3 fixture."""

    def get_fixture_path(self):
        """Get path to port wine V3 fixture."""
        return Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"

    def test_fixture_file_exists(self):
        """Test that port_wine_pipeline_v3.json exists."""
        fixture_path = self.get_fixture_path()
        self.assertTrue(fixture_path.exists(), f"Fixture not found at {fixture_path}")

    def test_fixture_valid_json(self):
        """Test that fixture is valid JSON."""
        with open(self.get_fixture_path()) as f:
            data = json.load(f)

        self.assertIsInstance(data, dict)
        self.assertIn("pipeline_config", data)
        self.assertIn("field_groups", data)
        self.assertIn("quality_gate_config", data)


class PortWineV3PipelineConfigTests(TestCase):
    """Tests for port wine V3 pipeline config."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_pipeline_config_has_v3_defaults(self):
        """Test pipeline config has V3 increased search budget."""
        config = self.fixture_data["pipeline_config"]

        self.assertEqual(config["max_serpapi_searches"], 6)
        self.assertEqual(config["max_sources_per_product"], 8)
        self.assertEqual(config["max_enrichment_time_seconds"], 180)

    def test_pipeline_config_awards_search_enabled(self):
        """Test awards search is enabled."""
        config = self.fixture_data["pipeline_config"]

        self.assertTrue(config["awards_search_enabled"])

    def test_pipeline_config_ecp_threshold(self):
        """Test ECP complete threshold is 90%."""
        config = self.fixture_data["pipeline_config"]

        self.assertEqual(float(config["ecp_complete_threshold"]), 90.0)


class PortWineV3FieldGroupTests(TestCase):
    """Tests for port wine V3 field groups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_all_field_groups_present(self):
        """Test all 8 port wine field groups are present."""
        groups = self.fixture_data["field_groups"]

        expected_keys = [
            "basic_product_info",
            "tasting_appearance",
            "tasting_nose",
            "tasting_palate",
            "tasting_finish",
            "tasting_overall",
            "cask_info",
            "port_details",
        ]

        group_keys = [g["group_key"] for g in groups]

        for key in expected_keys:
            self.assertIn(key, group_keys, f"Missing field group: {key}")

    def test_total_enrichable_fields_count(self):
        """Test total enrichable fields is 50 per spec."""
        groups = self.fixture_data["field_groups"]
        total_fields = sum(len(g["fields"]) for g in groups)

        self.assertEqual(total_fields, 50)

    def test_basic_product_info_has_style(self):
        """Test basic_product_info includes style (port-specific)."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        self.assertIn("style", groups["basic_product_info"]["fields"])

    def test_basic_product_info_no_age_statement(self):
        """Test basic_product_info doesn't include age_statement (port uses indication_age)."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        self.assertNotIn("age_statement", groups["basic_product_info"]["fields"])

    def test_port_details_fields(self):
        """Test port_details has correct port-specific fields."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        expected = [
            "indication_age", "harvest_year", "bottling_year", "producer_house",
            "quinta", "douro_subregion", "grape_varieties", "decanting_required",
            "drinking_window"
        ]

        self.assertEqual(groups["port_details"]["fields"], expected)

    def test_cask_info_simplified(self):
        """Test cask_info is simplified for port wine (aging_vessel, maturation_notes only)."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        expected = ["aging_vessel", "maturation_notes"]
        self.assertEqual(groups["cask_info"]["fields"], expected)


class PortWineV3QualityGateTests(TestCase):
    """Tests for port wine V3 quality gate config."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_skeleton_required_fields(self):
        """Test skeleton requires only name."""
        config = self.fixture_data["quality_gate_config"]

        self.assertEqual(config["skeleton_required_fields"], ["name"])

    def test_partial_requires_style(self):
        """Test partial requires style (not region/country)."""
        config = self.fixture_data["quality_gate_config"]

        self.assertIn("style", config["partial_required_fields"])
        self.assertNotIn("region", config["partial_required_fields"])
        self.assertNotIn("country", config["partial_required_fields"])

    def test_baseline_required_fields(self):
        """Test baseline has correct port-specific required fields."""
        config = self.fixture_data["quality_gate_config"]

        expected = [
            "name", "brand", "abv", "style",
            "volume_ml", "description",
            "primary_aromas", "finish_flavors", "palate_flavors",
            "producer_house"
        ]

        self.assertEqual(config["baseline_required_fields"], expected)

    def test_baseline_or_fields_age_indication(self):
        """Test baseline OR fields include indication_age OR harvest_year."""
        config = self.fixture_data["quality_gate_config"]

        self.assertIn(
            ["indication_age", "harvest_year"],
            config["baseline_or_fields"]
        )

    def test_baseline_ruby_exception(self):
        """Test Ruby style exception for baseline OR fields."""
        config = self.fixture_data["quality_gate_config"]

        self.assertEqual(
            config["baseline_or_field_exceptions"]["style"],
            ["ruby", "reserve_ruby"]
        )

    def test_enriched_or_fields_port_specific(self):
        """Test enriched OR fields include port-specific grape_varieties OR quinta."""
        config = self.fixture_data["quality_gate_config"]

        self.assertIn(
            ["grape_varieties", "quinta"],
            config["enriched_or_fields"]
        )

    def test_enriched_or_fields_common(self):
        """Test enriched OR fields include common complexity OR overall_complexity."""
        config = self.fixture_data["quality_gate_config"]

        self.assertIn(
            ["complexity", "overall_complexity"],
            config["enriched_or_fields"]
        )


class PortWineV3EnrichmentConfigTests(TestCase):
    """Tests for port wine V3 enrichment config updates."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_ratings_search_removed(self):
        """Test ratings_search template is removed/inactive."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        self.assertNotIn("ratings_search", template_names)

    def test_price_search_removed(self):
        """Test price_search template is removed/inactive."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        self.assertNotIn("price_search", template_names)

    def test_port_style_template_exists(self):
        """Test port-specific style/producer template exists."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        # Should have producer_info template for producer_house, quinta
        self.assertIn("producer_info", template_names)
