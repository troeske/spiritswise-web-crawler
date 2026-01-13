"""
Unit tests for New Enrichment Templates (V3).

Task 4.7: Add New Enrichment Templates

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4

Tests verify:
- cask_details template exists and is active
- appearance template exists and is active
- Templates have correct target fields
"""

import json
from pathlib import Path

from django.test import TestCase


class WhiskeyCaskDetailsTemplateTests(TestCase):
    """Tests for cask_details template in whiskey pipeline."""

    @classmethod
    def setUpClass(cls):
        """Load whiskey fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_cask_details_template_exists(self):
        """Test cask_details template exists."""
        configs = self.fixture_data.get("enrichment_configs", [])

        cask_config = None
        for config in configs:
            if config.get("template_name") == "cask_details":
                cask_config = config
                break

        self.assertIsNotNone(cask_config, "cask_details template should exist")

    def test_cask_details_is_active(self):
        """Test cask_details template is active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        cask_config = None
        for config in configs:
            if config.get("template_name") == "cask_details":
                cask_config = config
                break

        self.assertTrue(
            cask_config.get("is_active"),
            "cask_details should be active"
        )

    def test_cask_details_target_fields(self):
        """Test cask_details has correct target fields."""
        configs = self.fixture_data.get("enrichment_configs", [])

        cask_config = None
        for config in configs:
            if config.get("template_name") == "cask_details":
                cask_config = config
                break

        target_fields = cask_config.get("target_fields", [])

        # Should include wood_type, cask_treatment, maturation_notes
        self.assertIn("wood_type", target_fields)
        self.assertIn("cask_treatment", target_fields)
        self.assertIn("maturation_notes", target_fields)

    def test_cask_details_search_template(self):
        """Test cask_details has appropriate search template."""
        configs = self.fixture_data.get("enrichment_configs", [])

        cask_config = None
        for config in configs:
            if config.get("template_name") == "cask_details":
                cask_config = config
                break

        search_template = cask_config.get("search_template", "")

        # Should include cask/maturation keywords
        self.assertIn("cask", search_template.lower())
        self.assertIn("maturation", search_template.lower())


class WhiskeyAppearanceTemplateTests(TestCase):
    """Tests for appearance template in whiskey pipeline."""

    @classmethod
    def setUpClass(cls):
        """Load whiskey fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_appearance_template_exists(self):
        """Test appearance template exists."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        self.assertIsNotNone(appearance_config, "appearance template should exist")

    def test_appearance_is_active(self):
        """Test appearance template is active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        self.assertTrue(
            appearance_config.get("is_active"),
            "appearance should be active"
        )

    def test_appearance_target_fields(self):
        """Test appearance has correct target fields."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        target_fields = appearance_config.get("target_fields", [])

        # Should include color_description, clarity, viscosity
        self.assertIn("color_description", target_fields)
        self.assertIn("clarity", target_fields)
        self.assertIn("viscosity", target_fields)

    def test_appearance_search_template(self):
        """Test appearance has appropriate search template."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        search_template = appearance_config.get("search_template", "")

        # Should include color/appearance keywords
        self.assertIn("color", search_template.lower())
        self.assertIn("appearance", search_template.lower())


class PortWineStyleTemplateTests(TestCase):
    """Tests for style_info template in port wine pipeline.

    Note: Port wine uses style_info for aging/oak details rather than cask_details.
    """

    @classmethod
    def setUpClass(cls):
        """Load port wine fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_style_info_template_exists(self):
        """Test style_info template exists in port wine."""
        configs = self.fixture_data.get("enrichment_configs", [])

        style_config = None
        for config in configs:
            if config.get("template_name") == "style_info":
                style_config = config
                break

        self.assertIsNotNone(
            style_config,
            "style_info template should exist for port wine"
        )

    def test_style_info_is_active(self):
        """Test style_info template is active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        style_config = None
        for config in configs:
            if config.get("template_name") == "style_info":
                style_config = config
                break

        self.assertTrue(
            style_config.get("is_active"),
            "style_info template should be active"
        )


class PortWineAppearanceTemplateTests(TestCase):
    """Tests for appearance template in port wine pipeline."""

    @classmethod
    def setUpClass(cls):
        """Load port wine fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_appearance_template_exists(self):
        """Test appearance template exists."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        self.assertIsNotNone(
            appearance_config,
            "appearance template should exist"
        )

    def test_appearance_is_active(self):
        """Test appearance template is active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        if appearance_config:
            self.assertTrue(
                appearance_config.get("is_active"),
                "appearance should be active"
            )


class TemplatePriorityTests(TestCase):
    """Tests for template priority settings."""

    @classmethod
    def setUpClass(cls):
        """Load whiskey fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_cask_details_has_priority(self):
        """Test cask_details has priority set."""
        configs = self.fixture_data.get("enrichment_configs", [])

        cask_config = None
        for config in configs:
            if config.get("template_name") == "cask_details":
                cask_config = config
                break

        self.assertIn("priority", cask_config)
        self.assertIsInstance(cask_config["priority"], int)

    def test_appearance_has_priority(self):
        """Test appearance has priority set."""
        configs = self.fixture_data.get("enrichment_configs", [])

        appearance_config = None
        for config in configs:
            if config.get("template_name") == "appearance":
                appearance_config = config
                break

        self.assertIn("priority", appearance_config)
        self.assertIsInstance(appearance_config["priority"], int)

    def test_tasting_notes_highest_priority(self):
        """Test tasting_notes has highest priority."""
        configs = self.fixture_data.get("enrichment_configs", [])

        active_configs = [c for c in configs if c.get("is_active", True)]

        # Find highest priority
        max_priority = 0
        max_template = None
        for config in active_configs:
            if config.get("priority", 0) > max_priority:
                max_priority = config["priority"]
                max_template = config.get("template_name")

        # tasting_notes should have highest priority
        self.assertEqual(max_template, "tasting_notes")
