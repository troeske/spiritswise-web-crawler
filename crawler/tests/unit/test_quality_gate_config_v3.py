"""
Unit tests for QualityGateConfig V3 updates.

Task 1.3: Update QualityGateConfig Model

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 6.1

V3 Changes:
- Rename complete_required_fields → baseline_required_fields
- Remove any_of_count, any_of_fields for all statuses
- Add baseline_or_fields for port wine (indication_age OR harvest_year)
- Add baseline_or_field_exceptions for ruby style exception
- Add enriched_or_fields for OR logic requirements
"""

import uuid
from django.test import TestCase
from crawler.models import (
    ProductTypeConfig,
    QualityGateConfig,
)


class QualityGateConfigV3Tests(TestCase):
    """Tests for QualityGateConfig V3 structure."""

    def setUp(self):
        """Create ProductTypeConfig for FK relationship."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_quality_gate_config_with_v3_fields(self):
        """Test creating QualityGateConfig with V3 field names."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv", "region", "country", "category"],
            baseline_required_fields=[
                "name", "brand", "abv", "region", "country", "category",
                "volume_ml", "description", "primary_aromas", "finish_flavors",
                "age_statement", "primary_cask", "palate_flavors"
            ],
            enriched_required_fields=["mouthfeel"],
            enriched_or_fields=[
                ["complexity", "overall_complexity"],
                ["finishing_cask", "maturation_notes"]
            ],
        )

        self.assertIsInstance(config.id, uuid.UUID)
        self.assertEqual(config.skeleton_required_fields, ["name"])
        self.assertEqual(len(config.partial_required_fields), 6)
        self.assertEqual(len(config.baseline_required_fields), 13)
        self.assertEqual(config.enriched_required_fields, ["mouthfeel"])
        self.assertEqual(len(config.enriched_or_fields), 2)

    def test_baseline_required_fields_replaces_complete(self):
        """Test that baseline_required_fields is used instead of complete_required_fields."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            baseline_required_fields=["name", "brand", "description"],
        )

        # baseline_required_fields should exist
        self.assertEqual(config.baseline_required_fields, ["name", "brand", "description"])

        # Verify it has baseline_required_fields attribute
        self.assertTrue(hasattr(config, "baseline_required_fields"))

    def test_enriched_or_fields_structure(self):
        """Test enriched_or_fields stores list of field pairs."""
        or_fields = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"],
        ]

        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            enriched_or_fields=or_fields,
        )

        self.assertEqual(config.enriched_or_fields, or_fields)
        self.assertEqual(config.enriched_or_fields[0], ["complexity", "overall_complexity"])
        self.assertEqual(config.enriched_or_fields[1], ["finishing_cask", "maturation_notes"])

    def test_enriched_or_fields_default_empty(self):
        """Test enriched_or_fields defaults to empty list."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
        )

        self.assertEqual(config.enriched_or_fields, [])

    def test_baseline_or_fields_for_port_wine(self):
        """Test baseline_or_fields for port wine (indication_age OR harvest_year)."""
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

        config = QualityGateConfig.objects.create(
            product_type_config=port_config,
            baseline_required_fields=[
                "name", "brand", "abv", "style",
                "volume_ml", "description",
                "primary_aromas", "finish_flavors", "palate_flavors",
                "producer_house"
            ],
            baseline_or_fields=[
                ["indication_age", "harvest_year"]
            ],
        )

        self.assertEqual(
            config.baseline_or_fields,
            [["indication_age", "harvest_year"]]
        )

    def test_baseline_or_field_exceptions(self):
        """Test baseline_or_field_exceptions for ruby style waiver."""
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

        config = QualityGateConfig.objects.create(
            product_type_config=port_config,
            baseline_or_fields=[
                ["indication_age", "harvest_year"]
            ],
            baseline_or_field_exceptions={
                "style": ["ruby", "reserve_ruby"]
            },
        )

        self.assertEqual(
            config.baseline_or_field_exceptions["style"],
            ["ruby", "reserve_ruby"]
        )

    def test_baseline_or_field_exceptions_default_empty(self):
        """Test baseline_or_field_exceptions defaults to empty dict."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
        )

        self.assertEqual(config.baseline_or_field_exceptions, {})


class QualityGateConfigWhiskeyV3Tests(TestCase):
    """Tests for Whiskey QualityGateConfig per V3 spec."""

    def setUp(self):
        """Create ProductTypeConfig for whiskey."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_whiskey_thresholds_per_v3_spec(self):
        """Test whiskey status thresholds match V3 spec Appendix A."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            skeleton_required_fields=["name"],
            partial_required_fields=[
                "name", "brand", "abv", "region", "country", "category"
            ],
            baseline_required_fields=[
                "name", "brand", "abv", "region", "country", "category",
                "volume_ml", "description", "primary_aromas", "finish_flavors",
                "age_statement", "primary_cask", "palate_flavors"
            ],
            enriched_required_fields=["mouthfeel"],
            enriched_or_fields=[
                ["complexity", "overall_complexity"],
                ["finishing_cask", "maturation_notes"]
            ],
        )

        # Skeleton: just name
        self.assertEqual(config.skeleton_required_fields, ["name"])

        # Partial: 6 fields, no any-of
        self.assertEqual(len(config.partial_required_fields), 6)
        self.assertIn("category", config.partial_required_fields)

        # Baseline: 13 fields
        self.assertEqual(len(config.baseline_required_fields), 13)
        self.assertIn("primary_aromas", config.baseline_required_fields)
        self.assertIn("palate_flavors", config.baseline_required_fields)

        # Enriched: mouthfeel required + OR fields
        self.assertEqual(config.enriched_required_fields, ["mouthfeel"])
        self.assertEqual(len(config.enriched_or_fields), 2)


class QualityGateConfigPortWineV3Tests(TestCase):
    """Tests for Port Wine QualityGateConfig per V3 spec."""

    def setUp(self):
        """Create ProductTypeConfig for port wine."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

    def test_port_wine_thresholds_per_v3_spec(self):
        """Test port wine status thresholds match V3 spec Appendix C."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv", "style"],
            baseline_required_fields=[
                "name", "brand", "abv", "style",
                "volume_ml", "description",
                "primary_aromas", "finish_flavors", "palate_flavors",
                "producer_house"
            ],
            baseline_or_fields=[
                ["indication_age", "harvest_year"]
            ],
            baseline_or_field_exceptions={
                "style": ["ruby", "reserve_ruby"]
            },
            enriched_required_fields=["mouthfeel"],
            enriched_or_fields=[
                ["complexity", "overall_complexity"],
                ["grape_varieties", "quinta"]
            ],
        )

        # Partial: style is essential for port
        self.assertIn("style", config.partial_required_fields)
        self.assertNotIn("region", config.partial_required_fields)
        self.assertNotIn("country", config.partial_required_fields)

        # Baseline: producer_house is port equivalent of distillery
        self.assertIn("producer_house", config.baseline_required_fields)

        # Baseline OR: indication_age OR harvest_year
        self.assertEqual(
            config.baseline_or_fields,
            [["indication_age", "harvest_year"]]
        )

        # Ruby exception: waive age requirement
        self.assertEqual(
            config.baseline_or_field_exceptions["style"],
            ["ruby", "reserve_ruby"]
        )

        # Enriched OR: grape_varieties OR quinta (port-specific)
        self.assertIn(
            ["grape_varieties", "quinta"],
            config.enriched_or_fields
        )

    def test_port_wine_no_age_statement_in_baseline(self):
        """Test age_statement is NOT in port wine baseline (uses indication_age instead)."""
        config = QualityGateConfig.objects.create(
            product_type_config=self.product_type_config,
            baseline_required_fields=[
                "name", "brand", "abv", "style",
                "volume_ml", "description",
                "primary_aromas", "finish_flavors", "palate_flavors",
                "producer_house"
            ],
        )

        self.assertNotIn("age_statement", config.baseline_required_fields)
