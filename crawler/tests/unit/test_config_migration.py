"""
Unit tests for Config Migration (Task 0.2 - Config Consolidation).

Tests the data migration from PipelineConfig to ProductTypeConfig.

TDD Approach: Tests written BEFORE migration implementation.
"""

from decimal import Decimal
from django.test import TestCase
from crawler.models import ProductTypeConfig, PipelineConfig
from crawler.utils.migration_helpers import migrate_pipeline_config_data


class PipelineConfigMigrationTests(TestCase):
    """Tests for migrating PipelineConfig data to ProductTypeConfig."""

    def test_migrate_pipeline_config_data(self):
        """Test that PipelineConfig data is migrated to ProductTypeConfig."""

        # Create ProductTypeConfig with old defaults (before V3)
        ptc = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            # Leave V3 fields at their defaults - migration should override
        )

        # Create PipelineConfig with custom V3 values
        PipelineConfig.objects.create(
            product_type_config=ptc,
            max_serpapi_searches=10,
            max_sources_per_product=12,
            max_enrichment_time_seconds=300,
            awards_search_enabled=False,
            awards_search_template="{name} custom awards",
            members_only_detection_enabled=False,
            members_only_patterns=["login required", "paywall"],
            status_thresholds={"complete": {"min_fields": 25}},
            ecp_complete_threshold=Decimal("85.0"),
        )

        # Run migration
        migrate_pipeline_config_data()

        # Verify data moved to ProductTypeConfig
        ptc.refresh_from_db()
        self.assertEqual(ptc.max_serpapi_searches, 10)
        self.assertEqual(ptc.max_sources_per_product, 12)
        self.assertEqual(ptc.max_enrichment_time_seconds, 300)
        self.assertFalse(ptc.awards_search_enabled)
        self.assertEqual(ptc.awards_search_template, "{name} custom awards")
        self.assertFalse(ptc.members_only_detection_enabled)
        self.assertEqual(ptc.members_only_patterns, ["login required", "paywall"])
        self.assertEqual(ptc.status_thresholds, {"complete": {"min_fields": 25}})
        self.assertEqual(ptc.ecp_complete_threshold, Decimal("85.0"))

    def test_migrate_multiple_pipeline_configs(self):
        """Test migrating multiple PipelineConfig records."""
        # Create multiple product types with PipelineConfigs
        ptc_whiskey = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        PipelineConfig.objects.create(
            product_type_config=ptc_whiskey,
            max_serpapi_searches=8,
            awards_search_template="{name} whiskey awards",
        )

        ptc_port = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )
        PipelineConfig.objects.create(
            product_type_config=ptc_port,
            max_serpapi_searches=4,
            awards_search_template="{name} port awards",
        )

        # Run migration
        migrate_pipeline_config_data()

        # Verify both were migrated
        ptc_whiskey.refresh_from_db()
        ptc_port.refresh_from_db()

        self.assertEqual(ptc_whiskey.max_serpapi_searches, 8)
        self.assertEqual(ptc_whiskey.awards_search_template, "{name} whiskey awards")

        self.assertEqual(ptc_port.max_serpapi_searches, 4)
        self.assertEqual(ptc_port.awards_search_template, "{name} port awards")

    def test_migration_without_pipeline_config(self):
        """Test that ProductTypeConfig without PipelineConfig keeps defaults."""
        # Create ProductTypeConfig WITHOUT PipelineConfig
        ptc = ProductTypeConfig.objects.create(
            product_type="gin",
            display_name="Gin",
        )

        # Run migration (should not fail)
        migrate_pipeline_config_data()

        # Verify defaults are preserved
        ptc.refresh_from_db()
        self.assertEqual(ptc.max_serpapi_searches, 6)  # V3 default
        self.assertEqual(ptc.max_sources_per_product, 8)  # V3 default
        self.assertTrue(ptc.awards_search_enabled)  # V3 default

    def test_migration_idempotent(self):
        """Test that running migration multiple times is safe."""
        ptc = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        PipelineConfig.objects.create(
            product_type_config=ptc,
            max_serpapi_searches=10,
        )

        # Run migration twice
        migrate_pipeline_config_data()
        migrate_pipeline_config_data()

        # Should still have correct values
        ptc.refresh_from_db()
        self.assertEqual(ptc.max_serpapi_searches, 10)
