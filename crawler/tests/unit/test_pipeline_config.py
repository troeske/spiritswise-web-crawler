"""
Unit tests for PipelineConfig Model (V3 Architecture).

Task 1.1: Create PipelineConfig Model

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 6.1

TDD Approach: Tests written FIRST, implementation follows.

PipelineConfig stores product-type specific pipeline configuration:
- Search budget (max_serpapi_searches=6, max_sources_per_product=8)
- Awards search settings
- Members-only detection settings
- Status thresholds
- ECP complete threshold
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from crawler.models import (
    ProductTypeConfig,
    PipelineConfig,
)


class PipelineConfigModelTests(TestCase):
    """Tests for PipelineConfig model."""

    def setUp(self):
        """Create ProductTypeConfig for FK relationship."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_pipeline_config_with_defaults(self):
        """Test creating PipelineConfig with default values per V3 spec."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
        )

        # Identity
        self.assertIsInstance(config.id, uuid.UUID)
        self.assertEqual(config.product_type_config, self.product_type_config)

        # Search budget - V3 defaults
        self.assertEqual(config.max_serpapi_searches, 6)  # Increased from 3
        self.assertEqual(config.max_sources_per_product, 8)  # Increased from 5
        self.assertEqual(config.max_enrichment_time_seconds, 180)  # Increased from 120

        # Awards search
        self.assertTrue(config.awards_search_enabled)
        self.assertIn("{name}", config.awards_search_template)
        self.assertIn("awards", config.awards_search_template.lower())

        # Members-only detection
        self.assertTrue(config.members_only_detection_enabled)
        self.assertEqual(config.members_only_patterns, [])

        # Status thresholds
        self.assertEqual(config.status_thresholds, {})

        # ECP settings
        self.assertEqual(config.ecp_complete_threshold, Decimal("90.0"))

        # Timestamps
        self.assertIsNotNone(config.created_at)
        self.assertIsNotNone(config.updated_at)

    def test_pipeline_config_uuid_primary_key(self):
        """Test that PipelineConfig uses UUID primary key."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
        )
        self.assertIsInstance(config.id, uuid.UUID)

    def test_pipeline_config_one_to_one_relationship(self):
        """Test OneToOne relationship with ProductTypeConfig."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
        )

        # Access from ProductTypeConfig
        self.assertEqual(
            self.product_type_config.pipeline_config,
            config
        )

        # Creating second PipelineConfig for same ProductTypeConfig should fail
        with self.assertRaises(IntegrityError):
            PipelineConfig.objects.create(
                product_type_config=self.product_type_config,
            )

    def test_pipeline_config_with_custom_search_budget(self):
        """Test PipelineConfig with custom search budget values."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            max_serpapi_searches=10,
            max_sources_per_product=15,
            max_enrichment_time_seconds=300,
        )

        self.assertEqual(config.max_serpapi_searches, 10)
        self.assertEqual(config.max_sources_per_product, 15)
        self.assertEqual(config.max_enrichment_time_seconds, 300)

    def test_pipeline_config_awards_search_template(self):
        """Test custom awards search template."""
        custom_template = "{brand} {name} competition winner gold medal"

        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            awards_search_template=custom_template,
        )

        self.assertEqual(config.awards_search_template, custom_template)

    def test_pipeline_config_awards_search_disabled(self):
        """Test disabling awards search."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            awards_search_enabled=False,
        )

        self.assertFalse(config.awards_search_enabled)

    def test_pipeline_config_members_only_patterns(self):
        """Test members-only detection patterns as list."""
        patterns = [
            r'<form[^>]*login',
            r'members?\s*only',
            r'subscription\s*required',
        ]

        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            members_only_patterns=patterns,
        )

        self.assertEqual(config.members_only_patterns, patterns)
        self.assertEqual(len(config.members_only_patterns), 3)

    def test_pipeline_config_members_only_disabled(self):
        """Test disabling members-only detection."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            members_only_detection_enabled=False,
        )

        self.assertFalse(config.members_only_detection_enabled)

    def test_pipeline_config_status_thresholds_json(self):
        """Test status thresholds stored as JSON matching spec structure."""
        thresholds = {
            "skeleton": {
                "required": ["name"]
            },
            "partial": {
                "required": ["name", "brand", "abv", "region", "country", "category"]
            },
            "baseline": {
                "required": [
                    "name", "brand", "abv", "region", "country", "category",
                    "volume_ml", "description", "primary_aromas", "finish_flavors",
                    "age_statement", "primary_cask", "palate_flavors"
                ]
            },
            "enriched": {
                "required": ["mouthfeel"],
                "or_fields": [
                    ["complexity", "overall_complexity"],
                    ["finishing_cask", "maturation_notes"]
                ]
            },
            "complete": {
                "ecp_threshold": 90.0
            }
        }

        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            status_thresholds=thresholds,
        )

        self.assertEqual(config.status_thresholds, thresholds)
        self.assertEqual(
            config.status_thresholds["baseline"]["required"][0],
            "name"
        )
        self.assertEqual(
            config.status_thresholds["enriched"]["or_fields"][0],
            ["complexity", "overall_complexity"]
        )

    def test_pipeline_config_ecp_complete_threshold(self):
        """Test custom ECP complete threshold."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            ecp_complete_threshold=Decimal("85.0"),
        )

        self.assertEqual(config.ecp_complete_threshold, Decimal("85.0"))

    def test_pipeline_config_delete_cascade(self):
        """Test that PipelineConfig is deleted when ProductTypeConfig is deleted."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
        )
        config_id = config.id

        # Delete ProductTypeConfig
        self.product_type_config.delete()

        # PipelineConfig should be deleted too
        self.assertFalse(
            PipelineConfig.objects.filter(id=config_id).exists()
        )

    def test_pipeline_config_str_representation(self):
        """Test string representation of PipelineConfig."""
        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
        )

        str_repr = str(config)
        self.assertIn("whiskey", str_repr.lower())


class PipelineConfigPortWineTests(TestCase):
    """Tests for PipelineConfig with port wine specific settings."""

    def setUp(self):
        """Create ProductTypeConfig for port wine."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

    def test_port_wine_pipeline_config_with_thresholds(self):
        """Test port wine specific status thresholds per V3 spec."""
        port_thresholds = {
            "skeleton": {
                "required": ["name"]
            },
            "partial": {
                "required": ["name", "brand", "abv", "style"]
            },
            "baseline": {
                "required": [
                    "name", "brand", "abv", "style",
                    "volume_ml", "description",
                    "primary_aromas", "finish_flavors", "palate_flavors",
                    "producer_house"
                ],
                "or_fields": [
                    ["indication_age", "harvest_year"]
                ],
                "or_field_exceptions": {
                    "style": ["ruby", "reserve_ruby"]
                }
            },
            "enriched": {
                "required": ["mouthfeel"],
                "or_fields": [
                    ["complexity", "overall_complexity"],
                    ["grape_varieties", "quinta"]
                ]
            },
            "complete": {
                "ecp_threshold": 90.0
            }
        }

        config = PipelineConfig.objects.create(
            product_type_config=self.product_type_config,
            status_thresholds=port_thresholds,
        )

        # Verify port wine specific thresholds
        self.assertIn("style", config.status_thresholds["partial"]["required"])
        self.assertIn(
            ["indication_age", "harvest_year"],
            config.status_thresholds["baseline"]["or_fields"]
        )
        self.assertEqual(
            config.status_thresholds["baseline"]["or_field_exceptions"]["style"],
            ["ruby", "reserve_ruby"]
        )
