"""
Unit tests for Removed Templates (V3).

Task 4.6: Remove Ratings and Prices Templates

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4

Tests verify:
- ratings_search not in active configs
- price_search not in active configs
- Deprecated templates marked with V3 DEPRECATED in display_name
"""

import json
from pathlib import Path

from django.test import TestCase


class WhiskeyRemovedTemplatesTests(TestCase):
    """Tests for removed templates in whiskey pipeline."""

    @classmethod
    def setUpClass(cls):
        """Load whiskey fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "whiskey_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_ratings_search_not_active(self):
        """Test ratings_search template is not active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        ratings_config = None
        for config in configs:
            if config.get("template_name") == "ratings_search":
                ratings_config = config
                break

        self.assertIsNotNone(ratings_config, "ratings_search template should exist")
        self.assertFalse(
            ratings_config.get("is_active"),
            "ratings_search should be inactive"
        )

    def test_price_search_not_active(self):
        """Test price_search template is not active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        price_config = None
        for config in configs:
            if config.get("template_name") == "price_search":
                price_config = config
                break

        self.assertIsNotNone(price_config, "price_search template should exist")
        self.assertFalse(
            price_config.get("is_active"),
            "price_search should be inactive"
        )

    def test_ratings_search_marked_deprecated(self):
        """Test ratings_search has V3 DEPRECATED in display name."""
        configs = self.fixture_data.get("enrichment_configs", [])

        ratings_config = None
        for config in configs:
            if config.get("template_name") == "ratings_search":
                ratings_config = config
                break

        self.assertIn(
            "V3 DEPRECATED",
            ratings_config.get("display_name", ""),
            "ratings_search should be marked as V3 DEPRECATED"
        )

    def test_price_search_marked_deprecated(self):
        """Test price_search has V3 DEPRECATED in display name."""
        configs = self.fixture_data.get("enrichment_configs", [])

        price_config = None
        for config in configs:
            if config.get("template_name") == "price_search":
                price_config = config
                break

        self.assertIn(
            "V3 DEPRECATED",
            price_config.get("display_name", ""),
            "price_search should be marked as V3 DEPRECATED"
        )

    def test_active_templates_count(self):
        """Test correct number of active templates."""
        configs = self.fixture_data.get("enrichment_configs", [])

        active_configs = [c for c in configs if c.get("is_active", True)]

        # Should be 5 active templates (tasting_notes, distillery_info,
        # production_details, cask_details, appearance)
        self.assertEqual(len(active_configs), 5)

    def test_active_templates_exclude_ratings_price(self):
        """Test active templates don't include ratings or price."""
        configs = self.fixture_data.get("enrichment_configs", [])

        active_configs = [c for c in configs if c.get("is_active", True)]
        active_names = [c.get("template_name") for c in active_configs]

        self.assertNotIn("ratings_search", active_names)
        self.assertNotIn("price_search", active_names)


class PortWineRemovedTemplatesTests(TestCase):
    """Tests for removed templates in port wine pipeline."""

    @classmethod
    def setUpClass(cls):
        """Load port wine fixture."""
        super().setUpClass()
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "port_wine_pipeline_v3.json"
        with open(fixture_path, "r") as f:
            cls.fixture_data = json.load(f)

    def test_ratings_search_not_active(self):
        """Test ratings_search template is not active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        ratings_config = None
        for config in configs:
            if config.get("template_name") == "ratings_search":
                ratings_config = config
                break

        if ratings_config:
            self.assertFalse(
                ratings_config.get("is_active"),
                "ratings_search should be inactive"
            )

    def test_price_search_not_active(self):
        """Test price_search template is not active."""
        configs = self.fixture_data.get("enrichment_configs", [])

        price_config = None
        for config in configs:
            if config.get("template_name") == "price_search":
                price_config = config
                break

        if price_config:
            self.assertFalse(
                price_config.get("is_active"),
                "price_search should be inactive"
            )

    def test_active_templates_exclude_ratings_price(self):
        """Test active templates don't include ratings or price."""
        configs = self.fixture_data.get("enrichment_configs", [])

        active_configs = [c for c in configs if c.get("is_active", True)]
        active_names = [c.get("template_name") for c in active_configs]

        self.assertNotIn("ratings_search", active_names)
        self.assertNotIn("price_search", active_names)


class TemplateFilteringTests(TestCase):
    """Tests for template filtering helper logic."""

    def test_filter_active_templates(self):
        """Test filtering to only active templates."""
        configs = [
            {"template_name": "active_one", "is_active": True},
            {"template_name": "active_two", "is_active": True},
            {"template_name": "inactive", "is_active": False},
        ]

        active = [c for c in configs if c.get("is_active", True)]

        self.assertEqual(len(active), 2)
        self.assertEqual(active[0]["template_name"], "active_one")
        self.assertEqual(active[1]["template_name"], "active_two")

    def test_filter_defaults_to_active(self):
        """Test that missing is_active defaults to True."""
        configs = [
            {"template_name": "no_flag"},  # Should default to active
            {"template_name": "explicit_true", "is_active": True},
            {"template_name": "explicit_false", "is_active": False},
        ]

        active = [c for c in configs if c.get("is_active", True)]

        self.assertEqual(len(active), 2)
        names = [c["template_name"] for c in active]
        self.assertIn("no_flag", names)
        self.assertIn("explicit_true", names)
        self.assertNotIn("explicit_false", names)
