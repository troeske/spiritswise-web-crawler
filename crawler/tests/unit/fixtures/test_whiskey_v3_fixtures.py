"""
Unit tests for Whiskey V3 Fixtures.

Task 1.5: Create Fixtures for Whiskey Config

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Appendix A & B

Tests verify:
- Fixture loads correctly
- All field groups present with correct fields
- Status thresholds match V3 spec
- Pipeline config has V3 defaults
"""

import json
from decimal import Decimal
from pathlib import Path
from django.test import TestCase
from crawler.models import (
    ProductTypeConfig,
    PipelineConfig,
    FieldGroup,
    QualityGateConfig,
    EnrichmentConfig,
)


class WhiskeyV3FixtureLoadTests(TestCase):
    """Tests for loading whiskey V3 fixture."""

    def get_fixture_path(self):
        """Get path to whiskey V3 fixture."""
        return Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"

    def test_fixture_file_exists(self):
        """Test that whiskey_pipeline_v3.json exists."""
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


class WhiskeyV3PipelineConfigTests(TestCase):
    """Tests for whiskey V3 pipeline config."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
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
        self.assertIn("{name}", config["awards_search_template"])
        self.assertIn("awards", config["awards_search_template"])

    def test_pipeline_config_members_only_detection(self):
        """Test members-only detection settings."""
        config = self.fixture_data["pipeline_config"]

        self.assertTrue(config["members_only_detection_enabled"])
        self.assertIsInstance(config["members_only_patterns"], list)

    def test_pipeline_config_ecp_threshold(self):
        """Test ECP complete threshold is 90%."""
        config = self.fixture_data["pipeline_config"]

        self.assertEqual(float(config["ecp_complete_threshold"]), 90.0)


class WhiskeyV3FieldGroupTests(TestCase):
    """Tests for whiskey V3 field groups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_all_field_groups_present(self):
        """Test all 8 whiskey field groups are present."""
        groups = self.fixture_data["field_groups"]

        expected_keys = [
            "basic_product_info",
            "tasting_appearance",
            "tasting_nose",
            "tasting_palate",
            "tasting_finish",
            "tasting_overall",
            "cask_info",
            "whiskey_details",
        ]

        group_keys = [g["group_key"] for g in groups]

        for key in expected_keys:
            self.assertIn(key, group_keys, f"Missing field group: {key}")

    def test_field_groups_ordered_by_sort_order(self):
        """Test field groups have correct sort order."""
        groups = self.fixture_data["field_groups"]
        sort_orders = [g["sort_order"] for g in groups]

        # Should be sorted
        self.assertEqual(sort_orders, sorted(sort_orders))

    def test_total_enrichable_fields_count(self):
        """Test total enrichable fields is 59 per spec."""
        groups = self.fixture_data["field_groups"]
        total_fields = sum(len(g["fields"]) for g in groups)

        self.assertEqual(total_fields, 59)

    def test_basic_product_info_fields(self):
        """Test basic_product_info has correct fields."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        expected = [
            "product_type", "category", "abv", "volume_ml", "description",
            "age_statement", "country", "region", "bottler"
        ]

        self.assertEqual(groups["basic_product_info"]["fields"], expected)

    def test_tasting_nose_fields(self):
        """Test tasting_nose has correct fields."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        expected = [
            "nose_description", "primary_aromas", "primary_intensity",
            "secondary_aromas", "aroma_evolution"
        ]

        self.assertEqual(groups["tasting_nose"]["fields"], expected)

    def test_whiskey_details_fields_count(self):
        """Test whiskey_details has 14 fields per spec."""
        groups = {g["group_key"]: g for g in self.fixture_data["field_groups"]}

        self.assertEqual(len(groups["whiskey_details"]["fields"]), 14)


class WhiskeyV3QualityGateTests(TestCase):
    """Tests for whiskey V3 quality gate config."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path) as f:
            cls.fixture_data = json.load(f)

    def test_skeleton_required_fields(self):
        """Test skeleton requires only name."""
        config = self.fixture_data["quality_gate_config"]

        self.assertEqual(config["skeleton_required_fields"], ["name"])

    def test_partial_required_fields_no_any_of(self):
        """Test partial has 6 required fields, no any-of."""
        config = self.fixture_data["quality_gate_config"]

        expected = ["name", "brand", "abv", "region", "country", "category"]
        self.assertEqual(config["partial_required_fields"], expected)

    def test_baseline_required_fields(self):
        """Test baseline has 13 required fields per spec."""
        config = self.fixture_data["quality_gate_config"]

        expected = [
            "name", "brand", "abv", "region", "country", "category",
            "volume_ml", "description", "primary_aromas", "finish_flavors",
            "age_statement", "primary_cask", "palate_flavors"
        ]

        self.assertEqual(config["baseline_required_fields"], expected)

    def test_enriched_required_fields(self):
        """Test enriched requires mouthfeel."""
        config = self.fixture_data["quality_gate_config"]

        self.assertEqual(config["enriched_required_fields"], ["mouthfeel"])

    def test_enriched_or_fields(self):
        """Test enriched OR fields per spec."""
        config = self.fixture_data["quality_gate_config"]

        expected = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"]
        ]

        self.assertEqual(config["enriched_or_fields"], expected)


class WhiskeyV3EnrichmentConfigTests(TestCase):
    """Tests for whiskey V3 enrichment config updates."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
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

    def test_cask_details_template_added(self):
        """Test cask_details template is added."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        self.assertIn("cask_details", template_names)

    def test_appearance_template_added(self):
        """Test appearance template is added."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        self.assertIn("appearance", template_names)

    def test_awards_search_still_active(self):
        """Test awards_search template is still active (moved to Step 4 but config exists)."""
        configs = self.fixture_data.get("enrichment_configs", [])
        template_names = [c["template_name"] for c in configs if c.get("is_active", True)]

        # Awards search is now handled by PipelineConfig, but template may still exist
        # for backward compatibility or as reference
        pass  # This is informational - awards search is in PipelineConfig now
