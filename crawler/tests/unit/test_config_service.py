"""
Unit tests for ConfigService (Schema Builder Service).

Task 0.3.1-0.3.7: Tests for ConfigService class.

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2

Tests:
1. test_get_product_type_config_returns_active_config
2. test_get_product_type_config_returns_none_for_inactive
3. test_get_product_type_config_returns_none_for_missing
4. test_build_extraction_schema_includes_shared_fields
5. test_build_extraction_schema_includes_type_specific_fields
6. test_build_extraction_schema_excludes_other_type_fields
7. test_build_extraction_schema_excludes_inactive_fields
8. test_build_extraction_schema_returns_empty_for_unknown_type
9. test_get_quality_gate_config_returns_config
10. test_get_enrichment_templates_ordered_by_priority
11. test_caching_works (verify cache.get is called on second request)
12. test_invalidate_cache_clears_entries
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from crawler.models import (
    ProductTypeConfig,
    FieldDefinition,
    QualityGateConfig,
    EnrichmentConfig,
    FieldTypeChoices,
    FieldGroupChoices,
    TargetModelChoices,
)
from crawler.services.config_service import ConfigService, get_config_service


class ConfigServiceProductTypeConfigTests(TestCase):
    """Tests for ConfigService.get_product_type_config()."""

    def setUp(self):
        """Create test data and clear cache."""
        cache.clear()
        self.service = ConfigService()

        # Create active whiskey config
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
            categories=["bourbon", "scotch", "rye"],
        )

        # Create inactive port_wine config
        self.inactive_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            is_active=False,
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_get_product_type_config_returns_active_config(self):
        """Test that get_product_type_config returns active config."""
        config = self.service.get_product_type_config("whiskey")
        self.assertIsNotNone(config)
        self.assertEqual(config.product_type, "whiskey")
        self.assertEqual(config.display_name, "Whiskey")
        self.assertTrue(config.is_active)

    def test_get_product_type_config_returns_none_for_inactive(self):
        """Test that get_product_type_config returns None for inactive config."""
        config = self.service.get_product_type_config("port_wine")
        self.assertIsNone(config)

    def test_get_product_type_config_returns_none_for_missing(self):
        """Test that get_product_type_config returns None for non-existent type."""
        config = self.service.get_product_type_config("nonexistent")
        self.assertIsNone(config)


class ConfigServiceExtractionSchemaTests(TestCase):
    """Tests for ConfigService.build_extraction_schema()."""

    def setUp(self):
        """Create test data with shared and type-specific fields."""
        cache.clear()
        self.service = ConfigService()

        # Create product type configs
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        self.port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            is_active=True,
        )

        # Create shared/base fields (product_type_config=None)
        self.shared_name = FieldDefinition.objects.create(
            product_type_config=None,
            field_name="name",
            display_name="Product Name",
            field_group=FieldGroupChoices.CORE,
            field_type=FieldTypeChoices.STRING,
            description="Full product name including brand and variant",
            examples=["Ardbeg 10", "Glenfiddich 18"],
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="name",
            sort_order=1,
            is_active=True,
        )
        self.shared_brand = FieldDefinition.objects.create(
            product_type_config=None,
            field_name="brand",
            display_name="Brand",
            field_group=FieldGroupChoices.CORE,
            field_type=FieldTypeChoices.STRING,
            description="Brand or producer name",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="brand",
            sort_order=2,
            is_active=True,
        )

        # Create whiskey-specific field
        self.whiskey_distillery = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_group=FieldGroupChoices.TYPE_SPECIFIC,
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery that produced this whiskey",
            examples=["Ardbeg", "Glenfiddich", "Macallan"],
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
            sort_order=1,
            is_active=True,
        )

        # Create port-specific field
        self.port_style = FieldDefinition.objects.create(
            product_type_config=self.port_config,
            field_name="style",
            display_name="Port Style",
            field_group=FieldGroupChoices.TYPE_SPECIFIC,
            field_type=FieldTypeChoices.STRING,
            description="Port wine style (ruby, tawny, vintage, etc.)",
            allowed_values=["ruby", "tawny", "vintage", "lbv"],
            target_model=TargetModelChoices.PORT_WINE_DETAILS,
            target_field="style",
            sort_order=1,
            is_active=True,
        )

        # Create inactive field (should be excluded)
        self.inactive_field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="inactive_field",
            display_name="Inactive Field",
            field_group=FieldGroupChoices.CORE,
            field_type=FieldTypeChoices.STRING,
            description="This field is inactive",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="inactive_field",
            is_active=False,
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_build_extraction_schema_includes_shared_fields(self):
        """Test that extraction schema includes shared/base fields."""
        schema = self.service.build_extraction_schema("whiskey")
        field_names = [f['field_name'] for f in schema]
        self.assertIn("name", field_names)
        self.assertIn("brand", field_names)

    def test_build_extraction_schema_includes_type_specific_fields(self):
        """Test that extraction schema includes type-specific fields."""
        schema = self.service.build_extraction_schema("whiskey")
        field_names = [f['field_name'] for f in schema]
        self.assertIn("distillery", field_names)

    def test_build_extraction_schema_excludes_other_type_fields(self):
        """Test that extraction schema excludes fields from other product types."""
        # Whiskey schema should not include port_wine's 'style' field
        schema = self.service.build_extraction_schema("whiskey")
        field_names = [f['field_name'] for f in schema]
        self.assertNotIn("style", field_names)

        # Port schema should not include whiskey's 'distillery' field
        port_schema = self.service.build_extraction_schema("port_wine")
        port_field_names = [f['field_name'] for f in port_schema]
        self.assertNotIn("distillery", port_field_names)
        self.assertIn("style", port_field_names)

    def test_build_extraction_schema_excludes_inactive_fields(self):
        """Test that extraction schema excludes inactive fields."""
        schema = self.service.build_extraction_schema("whiskey")
        field_names = [f['field_name'] for f in schema]
        self.assertNotIn("inactive_field", field_names)

    def test_build_extraction_schema_returns_empty_for_unknown_type(self):
        """Test that extraction schema returns empty list for unknown product type."""
        schema = self.service.build_extraction_schema("nonexistent")
        self.assertEqual(schema, [])

    def test_build_extraction_schema_field_format(self):
        """Test that extraction schema fields have correct format."""
        schema = self.service.build_extraction_schema("whiskey")

        # Find the 'name' field
        name_field = next((f for f in schema if f['field_name'] == 'name'), None)
        self.assertIsNotNone(name_field)
        self.assertEqual(name_field['field_name'], 'name')
        self.assertEqual(name_field['type'], 'string')
        self.assertIn('description', name_field)
        self.assertIn('examples', name_field)

    def test_build_extraction_schema_includes_allowed_values(self):
        """Test that schema includes allowed_values when present."""
        schema = self.service.build_extraction_schema("port_wine")

        # Find the 'style' field
        style_field = next((f for f in schema if f['field_name'] == 'style'), None)
        self.assertIsNotNone(style_field)
        self.assertIn('allowed_values', style_field)
        self.assertIn('ruby', style_field['allowed_values'])


class ConfigServiceQualityGateTests(TestCase):
    """Tests for ConfigService.get_quality_gate_config()."""

    def setUp(self):
        """Create test data."""
        cache.clear()
        self.service = ConfigService()

        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        self.quality_gate = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
            complete_required_fields=["name", "brand", "abv", "description", "palate_flavors"],
            complete_any_of_count=2,
            complete_any_of_fields=["nose_description", "finish_description", "distillery", "region"],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_get_quality_gate_config_returns_config(self):
        """Test that get_quality_gate_config returns correct config."""
        config = self.service.get_quality_gate_config("whiskey")
        self.assertIsNotNone(config)
        self.assertEqual(config.skeleton_required_fields, ["name"])
        self.assertEqual(config.partial_required_fields, ["name", "brand", "abv"])
        self.assertEqual(config.partial_any_of_count, 2)

    def test_get_quality_gate_config_returns_none_for_missing_type(self):
        """Test that get_quality_gate_config returns None for missing type."""
        config = self.service.get_quality_gate_config("nonexistent")
        self.assertIsNone(config)

    def test_get_quality_gate_config_returns_none_when_no_quality_gate(self):
        """Test returns None when product type exists but has no QualityGateConfig."""
        # Create port config without quality gate
        ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            is_active=True,
        )
        config = self.service.get_quality_gate_config("port_wine")
        self.assertIsNone(config)


class ConfigServiceEnrichmentTemplatesTests(TestCase):
    """Tests for ConfigService.get_enrichment_templates()."""

    def setUp(self):
        """Create test data with multiple enrichment templates."""
        cache.clear()
        self.service = ConfigService()

        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )

        # Create templates with different priorities
        self.low_priority = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="production_info",
            display_name="Production Info",
            search_template="{name} {brand} distillery production",
            target_fields=["distillery", "mash_bill"],
            priority=3,
            is_active=True,
        )
        self.high_priority = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting_notes",
            display_name="Tasting Notes",
            search_template="{name} {brand} tasting notes review",
            target_fields=["nose_description", "palate_description"],
            priority=10,
            is_active=True,
        )
        self.medium_priority = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="awards",
            display_name="Awards Search",
            search_template="{name} {brand} awards medals",
            target_fields=["awards"],
            priority=5,
            is_active=True,
        )
        # Inactive template - should be excluded
        self.inactive_template = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="inactive",
            display_name="Inactive Template",
            search_template="{name}",
            is_active=False,
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_get_enrichment_templates_ordered_by_priority(self):
        """Test that enrichment templates are ordered by priority (descending)."""
        templates = self.service.get_enrichment_templates("whiskey")

        self.assertEqual(len(templates), 3)  # 3 active templates
        self.assertEqual(templates[0].template_name, "tasting_notes")  # priority 10
        self.assertEqual(templates[1].template_name, "awards")  # priority 5
        self.assertEqual(templates[2].template_name, "production_info")  # priority 3

    def test_get_enrichment_templates_excludes_inactive(self):
        """Test that inactive templates are excluded."""
        templates = self.service.get_enrichment_templates("whiskey")
        template_names = [t.template_name for t in templates]
        self.assertNotIn("inactive", template_names)

    def test_get_enrichment_templates_returns_empty_for_unknown_type(self):
        """Test that empty list is returned for unknown product type."""
        templates = self.service.get_enrichment_templates("nonexistent")
        self.assertEqual(templates, [])


class ConfigServiceCachingTests(TestCase):
    """Tests for ConfigService caching behavior."""

    def setUp(self):
        """Create test data."""
        cache.clear()
        self.service = ConfigService()

        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Distillery name",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
            is_active=True,
        )
        QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
        )
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting",
            display_name="Tasting",
            search_template="{name}",
            is_active=True,
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_caching_works_for_product_type_config(self):
        """Test that product type config is cached on second request."""
        # First call - should query database
        config1 = self.service.get_product_type_config("whiskey")
        self.assertIsNotNone(config1)

        # Verify it's in cache
        cache_key = f"{self.service.CACHE_PREFIX}:product_type:whiskey"
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)

        # Second call - should use cache
        with patch.object(ProductTypeConfig.objects, 'get') as mock_get:
            config2 = self.service.get_product_type_config("whiskey")
            mock_get.assert_not_called()  # Should not hit database

        self.assertEqual(config1.id, config2.id)

    def test_caching_works_for_extraction_schema(self):
        """Test that extraction schema is cached on second request."""
        # First call
        schema1 = self.service.build_extraction_schema("whiskey")
        self.assertTrue(len(schema1) > 0)

        # Verify it's in cache
        cache_key = f"{self.service.CACHE_PREFIX}:schema:whiskey"
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)

        # Second call - should use cache (won't query FieldDefinition)
        with patch.object(FieldDefinition.objects, 'filter') as mock_filter:
            schema2 = self.service.build_extraction_schema("whiskey")
            mock_filter.assert_not_called()

        self.assertEqual(schema1, schema2)

    def test_caching_works_for_quality_gate(self):
        """Test that quality gate config is cached."""
        # First call
        config1 = self.service.get_quality_gate_config("whiskey")

        # Verify in cache
        cache_key = f"{self.service.CACHE_PREFIX}:quality_gate:whiskey"
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)

        # Second call - should use cache
        with patch.object(QualityGateConfig.objects, 'get') as mock_get:
            config2 = self.service.get_quality_gate_config("whiskey")
            mock_get.assert_not_called()

    def test_caching_works_for_enrichment_templates(self):
        """Test that enrichment templates are cached."""
        # First call
        templates1 = self.service.get_enrichment_templates("whiskey")

        # Verify in cache
        cache_key = f"{self.service.CACHE_PREFIX}:enrichment:whiskey"
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)

        # Second call - should use cache
        with patch.object(EnrichmentConfig.objects, 'filter') as mock_filter:
            templates2 = self.service.get_enrichment_templates("whiskey")
            mock_filter.assert_not_called()

    def test_invalidate_cache_clears_entries(self):
        """Test that invalidate_cache clears all cache entries for a product type."""
        # Populate cache
        self.service.get_product_type_config("whiskey")
        self.service.build_extraction_schema("whiskey")
        self.service.get_quality_gate_config("whiskey")
        self.service.get_enrichment_templates("whiskey")

        # Verify all are in cache
        self.assertIsNotNone(cache.get(f"{self.service.CACHE_PREFIX}:product_type:whiskey"))
        self.assertIsNotNone(cache.get(f"{self.service.CACHE_PREFIX}:schema:whiskey"))
        self.assertIsNotNone(cache.get(f"{self.service.CACHE_PREFIX}:quality_gate:whiskey"))
        self.assertIsNotNone(cache.get(f"{self.service.CACHE_PREFIX}:enrichment:whiskey"))

        # Invalidate cache
        self.service.invalidate_cache("whiskey")

        # Verify all are cleared
        self.assertIsNone(cache.get(f"{self.service.CACHE_PREFIX}:product_type:whiskey"))
        self.assertIsNone(cache.get(f"{self.service.CACHE_PREFIX}:schema:whiskey"))
        self.assertIsNone(cache.get(f"{self.service.CACHE_PREFIX}:quality_gate:whiskey"))
        self.assertIsNone(cache.get(f"{self.service.CACHE_PREFIX}:enrichment:whiskey"))

    def test_invalidate_cache_all_clears_everything(self):
        """Test that invalidate_cache with no argument clears all cache."""
        # Populate cache for whiskey
        self.service.get_product_type_config("whiskey")
        self.service.build_extraction_schema("whiskey")

        # Verify in cache
        self.assertIsNotNone(cache.get(f"{self.service.CACHE_PREFIX}:product_type:whiskey"))

        # Invalidate all
        self.service.invalidate_cache()

        # Verify cleared
        self.assertIsNone(cache.get(f"{self.service.CACHE_PREFIX}:product_type:whiskey"))


class ConfigServiceHelperMethodsTests(TestCase):
    """Tests for ConfigService helper methods."""

    def setUp(self):
        """Create test data."""
        cache.clear()
        self.service = ConfigService()

        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )
        FieldDefinition.objects.create(
            product_type_config=None,
            field_name="name",
            display_name="Name",
            field_type=FieldTypeChoices.STRING,
            description="Product name",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="name",
            is_active=True,
        )
        FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Distillery name",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
            is_active=True,
        )

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_get_field_names_returns_list_of_names(self):
        """Test that get_field_names returns list of field name strings."""
        field_names = self.service.get_field_names("whiskey")
        self.assertIsInstance(field_names, list)
        self.assertIn("name", field_names)
        self.assertIn("distillery", field_names)

    def test_get_field_names_returns_empty_for_unknown_type(self):
        """Test that get_field_names returns empty list for unknown type."""
        field_names = self.service.get_field_names("nonexistent")
        self.assertEqual(field_names, [])


class ConfigServiceSingletonTests(TestCase):
    """Tests for ConfigService singleton pattern."""

    def tearDown(self):
        """Reset singleton."""
        import crawler.services.config_service as module
        module._config_service = None

    def test_get_config_service_returns_singleton(self):
        """Test that get_config_service returns the same instance."""
        service1 = get_config_service()
        service2 = get_config_service()
        self.assertIs(service1, service2)

    def test_get_config_service_returns_config_service_instance(self):
        """Test that get_config_service returns ConfigService instance."""
        service = get_config_service()
        self.assertIsInstance(service, ConfigService)
