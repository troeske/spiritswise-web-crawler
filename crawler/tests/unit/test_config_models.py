"""
Unit tests for Configuration Models (V2 Architecture).

Task 0.1.1-0.1.4: Write unit tests for configuration models.

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2

TDD Approach: These tests are written BEFORE the models exist and will FAIL
initially until the models are implemented in Task 0.1.5-0.1.8.

Test Groups:
- ProductTypeConfig: Core configuration for product types (whiskey, port_wine, etc.)
- FieldDefinition: Field definitions with AI extraction instructions and model mapping
- QualityGateConfig: Quality thresholds for SKELETON/PARTIAL/COMPLETE/ENRICHED status
- EnrichmentConfig: Search templates for progressive enrichment
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from crawler.models import (
    ProductTypeConfig,
    FieldDefinition,
    QualityGateConfig,
    EnrichmentConfig,
    FieldTypeChoices,
    FieldGroupChoices,
    TargetModelChoices,
)


# =============================================================================
# Task 0.1.1: ProductTypeConfig Tests
# =============================================================================


class ProductTypeConfigModelTests(TestCase):
    """Tests for ProductTypeConfig model."""

    def test_create_product_type_config_with_defaults(self):
        """Test creating ProductTypeConfig with default values."""
        config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        self.assertEqual(config.product_type, "whiskey")
        self.assertEqual(config.display_name, "Whiskey")
        self.assertEqual(config.version, "1.0")
        self.assertTrue(config.is_active)
        self.assertEqual(config.categories, [])
        self.assertEqual(config.max_sources_per_product, 5)
        self.assertEqual(config.max_serpapi_searches, 3)
        self.assertEqual(config.max_enrichment_time_seconds, 120)
        self.assertIsNotNone(config.created_at)
        self.assertIsNotNone(config.updated_at)
        self.assertEqual(config.updated_by, "")

    def test_product_type_config_with_custom_values(self):
        """Test creating ProductTypeConfig with custom values."""
        categories = ["bourbon", "scotch", "rye"]
        config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            version="2.0",
            is_active=False,
            categories=categories,
            max_sources_per_product=10,
            max_serpapi_searches=5,
            max_enrichment_time_seconds=180,
            updated_by="admin",
        )
        self.assertEqual(config.version, "2.0")
        self.assertFalse(config.is_active)
        self.assertEqual(config.categories, categories)
        self.assertEqual(config.max_sources_per_product, 10)
        self.assertEqual(config.max_serpapi_searches, 5)
        self.assertEqual(config.max_enrichment_time_seconds, 180)
        self.assertEqual(config.updated_by, "admin")

    def test_product_type_config_uuid_primary_key(self):
        """Test that ProductTypeConfig uses UUID primary key."""
        config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        self.assertIsInstance(config.id, uuid.UUID)

    def test_product_type_unique_constraint(self):
        """Test that product_type must be unique."""
        ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        with self.assertRaises(IntegrityError):
            ProductTypeConfig.objects.create(
                product_type="whiskey",
                display_name="Whiskey Duplicate",
            )

    def test_product_type_config_str_representation(self):
        """Test string representation of ProductTypeConfig."""
        config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )
        self.assertIn("port_wine", str(config))

    def test_product_type_config_db_table_name(self):
        """Test that ProductTypeConfig uses correct db_table."""
        self.assertEqual(ProductTypeConfig._meta.db_table, "product_type_config")

    def test_product_type_config_verbose_name(self):
        """Test verbose_name for ProductTypeConfig."""
        self.assertEqual(
            ProductTypeConfig._meta.verbose_name, "Product Type Configuration"
        )

    def test_product_type_config_categories_accepts_nested_list(self):
        """Test that categories JSONField accepts list of strings."""
        categories = ["tawny", "ruby", "vintage", "lbv", "colheita", "white", "rose", "crusted"]
        config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            categories=categories,
        )
        config.refresh_from_db()
        self.assertEqual(config.categories, categories)
        self.assertEqual(len(config.categories), 8)

    def test_product_type_config_updated_at_changes_on_save(self):
        """Test that updated_at is automatically updated on save."""
        config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        initial_updated_at = config.updated_at

        # Modify and save
        config.display_name = "Whisky"
        config.save()
        config.refresh_from_db()

        self.assertGreaterEqual(config.updated_at, initial_updated_at)

    def test_product_type_config_port_wine_enrichment_limits(self):
        """Test port_wine specific enrichment limits from spec."""
        config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
            categories=["ruby", "tawny", "white", "rose", "vintage", "lbv", "colheita", "crusted"],
            max_sources_per_product=4,
            max_serpapi_searches=2,
            max_enrichment_time_seconds=90,
        )
        self.assertEqual(config.max_sources_per_product, 4)
        self.assertEqual(config.max_serpapi_searches, 2)
        self.assertEqual(config.max_enrichment_time_seconds, 90)


# =============================================================================
# Task 0.1.2: FieldDefinition Tests
# =============================================================================


class FieldDefinitionModelTests(TestCase):
    """Tests for FieldDefinition model."""

    def setUp(self):
        """Create a ProductTypeConfig for testing."""
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_field_definition_basic(self):
        """Test creating a basic FieldDefinition."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery that produced this whiskey",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        self.assertEqual(field.field_name, "distillery")
        self.assertEqual(field.display_name, "Distillery")
        self.assertEqual(field.field_type, FieldTypeChoices.STRING)
        self.assertEqual(field.target_model, TargetModelChoices.WHISKEY_DETAILS)
        self.assertEqual(field.target_field, "distillery")

    def test_field_definition_shared_field_null_product_type(self):
        """Test creating a shared field with null product_type_config."""
        field = FieldDefinition.objects.create(
            product_type_config=None,
            field_name="name",
            display_name="Product Name",
            field_type=FieldTypeChoices.STRING,
            description="Full product name including brand and variant",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="name",
        )
        self.assertIsNone(field.product_type_config)

    def test_field_definition_with_all_fields(self):
        """Test creating a FieldDefinition with all fields populated."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="awards",
            display_name="Awards",
            field_group=FieldGroupChoices.RELATED,
            field_type=FieldTypeChoices.ARRAY,
            item_type="object",
            description="Competition awards won",
            examples=[{"competition": "IWSC", "medal": "gold"}],
            allowed_values=[],
            item_schema={
                "competition": "string",
                "year": "integer",
                "medal": "string",
            },
            target_model=TargetModelChoices.PRODUCT_AWARD,
            target_field="",
            sort_order=100,
            is_active=True,
        )
        self.assertEqual(field.field_group, FieldGroupChoices.RELATED)
        self.assertEqual(field.item_type, "object")
        self.assertIsInstance(field.item_schema, dict)

    def test_field_definition_uuid_primary_key(self):
        """Test that FieldDefinition uses UUID primary key."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="test_field",
            display_name="Test Field",
            field_type=FieldTypeChoices.STRING,
            description="Test field description",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="test_field",
        )
        self.assertIsInstance(field.id, uuid.UUID)

    def test_field_definition_unique_together_constraint(self):
        """Test unique_together constraint on product_type_config and field_name."""
        FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Distillery name",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        with self.assertRaises(IntegrityError):
            FieldDefinition.objects.create(
                product_type_config=self.whiskey_config,
                field_name="distillery",
                display_name="Distillery Duplicate",
                field_type=FieldTypeChoices.STRING,
                description="Distillery name duplicate",
                target_model=TargetModelChoices.WHISKEY_DETAILS,
                target_field="distillery",
            )

    def test_field_definition_unique_together_allows_same_name_different_config(self):
        """Test that same field_name can exist for different product_type_config."""
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

        # Create same field_name for whiskey
        field1 = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="region",
            display_name="Whiskey Region",
            field_type=FieldTypeChoices.STRING,
            description="Whiskey region",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="region",
        )

        # Create same field_name for port_wine - should succeed
        field2 = FieldDefinition.objects.create(
            product_type_config=port_config,
            field_name="region",
            display_name="Port Region",
            field_type=FieldTypeChoices.STRING,
            description="Port region",
            target_model=TargetModelChoices.PORT_WINE_DETAILS,
            target_field="region",
        )

        self.assertEqual(field1.field_name, field2.field_name)
        self.assertNotEqual(field1.product_type_config, field2.product_type_config)

    def test_field_definition_to_extraction_schema_basic(self):
        """Test to_extraction_schema method returns correct schema."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["description"], "Name of the distillery")

    def test_field_definition_to_extraction_schema_with_examples(self):
        """Test to_extraction_schema includes examples when present."""
        examples = ["Ardbeg", "Glenfiddich", "Macallan"]
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery",
            examples=examples,
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertEqual(schema["examples"], examples)

    def test_field_definition_to_extraction_schema_excludes_empty_examples(self):
        """Test to_extraction_schema excludes examples when empty list."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery",
            examples=[],
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertNotIn("examples", schema)

    def test_field_definition_to_extraction_schema_with_allowed_values(self):
        """Test to_extraction_schema includes allowed_values when present."""
        allowed = ["gold", "silver", "bronze"]
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="medal",
            display_name="Medal",
            field_type=FieldTypeChoices.STRING,
            description="Award medal type",
            allowed_values=allowed,
            target_model=TargetModelChoices.PRODUCT_AWARD,
            target_field="medal",
        )
        schema = field.to_extraction_schema()
        self.assertEqual(schema["allowed_values"], allowed)

    def test_field_definition_to_extraction_schema_excludes_empty_allowed_values(self):
        """Test to_extraction_schema excludes allowed_values when empty list."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery",
            allowed_values=[],
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertNotIn("allowed_values", schema)

    def test_field_definition_to_extraction_schema_array_type(self):
        """Test to_extraction_schema for array type with item_type."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="primary_aromas",
            display_name="Primary Aromas",
            field_type=FieldTypeChoices.ARRAY,
            item_type="string",
            description="List of primary aroma notes",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="primary_aromas",
        )
        schema = field.to_extraction_schema()
        self.assertEqual(schema["type"], "array")
        self.assertEqual(schema["item_type"], "string")

    def test_field_definition_to_extraction_schema_excludes_empty_item_type(self):
        """Test to_extraction_schema excludes item_type when empty string."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            item_type="",
            description="Name of the distillery",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertNotIn("item_type", schema)

    def test_field_definition_to_extraction_schema_with_item_schema(self):
        """Test to_extraction_schema includes item_schema for complex arrays."""
        item_schema = {
            "competition": "string",
            "year": "integer",
            "medal": "string",
        }
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="awards",
            display_name="Awards",
            field_type=FieldTypeChoices.ARRAY,
            item_type="object",
            description="Awards list",
            item_schema=item_schema,
            target_model=TargetModelChoices.PRODUCT_AWARD,
            target_field="",
        )
        schema = field.to_extraction_schema()
        self.assertEqual(schema["item_schema"], item_schema)

    def test_field_definition_to_extraction_schema_excludes_empty_item_schema(self):
        """Test to_extraction_schema excludes item_schema when empty dict."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Name of the distillery",
            item_schema={},
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        schema = field.to_extraction_schema()
        self.assertNotIn("item_schema", schema)

    def test_field_definition_ordering(self):
        """Test default ordering by field_group, sort_order, field_name."""
        FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="z_field",
            display_name="Z Field",
            field_group=FieldGroupChoices.CORE,
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="z_field",
            sort_order=1,
        )
        FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="a_field",
            display_name="A Field",
            field_group=FieldGroupChoices.CORE,
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="a_field",
            sort_order=2,
        )
        fields = list(FieldDefinition.objects.all())
        self.assertEqual(fields[0].field_name, "z_field")  # lower sort_order first
        self.assertEqual(fields[1].field_name, "a_field")

    def test_field_definition_db_table_name(self):
        """Test that FieldDefinition uses correct db_table."""
        self.assertEqual(FieldDefinition._meta.db_table, "field_definition")

    def test_field_definition_default_field_group(self):
        """Test that field_group defaults to 'core'."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="test_field",
            display_name="Test Field",
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="test_field",
        )
        self.assertEqual(field.field_group, FieldGroupChoices.CORE)

    def test_field_definition_default_sort_order(self):
        """Test that sort_order defaults to 0."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="test_field",
            display_name="Test Field",
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="test_field",
        )
        self.assertEqual(field.sort_order, 0)

    def test_field_definition_default_is_active(self):
        """Test that is_active defaults to True."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="test_field",
            display_name="Test Field",
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="test_field",
        )
        self.assertTrue(field.is_active)

    def test_field_definition_jsonfield_defaults(self):
        """Test that JSONField defaults (examples, allowed_values, item_schema) are empty."""
        field = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="test_field",
            display_name="Test Field",
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="test_field",
        )
        self.assertEqual(field.examples, [])
        self.assertEqual(field.allowed_values, [])
        self.assertEqual(field.item_schema, {})


# =============================================================================
# Task 0.1.3: QualityGateConfig Tests
# =============================================================================


class QualityGateConfigModelTests(TestCase):
    """Tests for QualityGateConfig model."""

    def setUp(self):
        """Create ProductTypeConfig for testing."""
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_quality_gate_config_basic(self):
        """Test creating a basic QualityGateConfig."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
            complete_required_fields=[
                "name",
                "brand",
                "abv",
                "description",
                "palate_flavors",
            ],
            complete_any_of_count=2,
            complete_any_of_fields=[
                "nose_description",
                "finish_description",
                "distillery",
                "region",
            ],
            enriched_required_fields=[],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )
        self.assertEqual(qg.skeleton_required_fields, ["name"])
        self.assertEqual(qg.partial_any_of_count, 2)
        self.assertEqual(qg.complete_any_of_count, 2)
        self.assertEqual(qg.enriched_any_of_count, 2)

    def test_quality_gate_config_uuid_primary_key(self):
        """Test that QualityGateConfig uses UUID primary key."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
        )
        self.assertIsInstance(qg.id, uuid.UUID)

    def test_quality_gate_config_one_to_one_relationship(self):
        """Test OneToOne relationship with ProductTypeConfig."""
        QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
        )
        # Attempting to create another should fail
        with self.assertRaises(IntegrityError):
            QualityGateConfig.objects.create(
                product_type_config=self.whiskey_config,
            )

    def test_quality_gate_config_defaults(self):
        """Test default values for QualityGateConfig fields."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
        )
        self.assertEqual(qg.skeleton_required_fields, [])
        self.assertEqual(qg.partial_required_fields, [])
        self.assertEqual(qg.partial_any_of_count, 2)
        self.assertEqual(qg.partial_any_of_fields, [])
        self.assertEqual(qg.complete_required_fields, [])
        self.assertEqual(qg.complete_any_of_count, 2)
        self.assertEqual(qg.complete_any_of_fields, [])
        self.assertEqual(qg.enriched_required_fields, [])
        self.assertEqual(qg.enriched_any_of_count, 2)
        self.assertEqual(qg.enriched_any_of_fields, [])

    def test_quality_gate_config_related_name(self):
        """Test accessing QualityGateConfig via related_name from ProductTypeConfig."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
        )
        # Access via related_name 'quality_gates'
        self.assertEqual(self.whiskey_config.quality_gates, qg)

    def test_quality_gate_config_db_table_name(self):
        """Test that QualityGateConfig uses correct db_table."""
        self.assertEqual(QualityGateConfig._meta.db_table, "quality_gate_config")

    def test_quality_gate_config_skeleton_required_fields(self):
        """Test skeleton_required_fields stores list correctly."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            skeleton_required_fields=["name"],
        )
        qg.refresh_from_db()
        self.assertEqual(qg.skeleton_required_fields, ["name"])

    def test_quality_gate_config_partial_fields(self):
        """Test partial_required_fields and partial_any_of_fields."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            partial_required_fields=["name", "brand", "abv"],
            partial_any_of_count=2,
            partial_any_of_fields=["description", "region", "country", "volume_ml"],
        )
        qg.refresh_from_db()
        self.assertEqual(qg.partial_required_fields, ["name", "brand", "abv"])
        self.assertEqual(qg.partial_any_of_count, 2)
        self.assertIn("description", qg.partial_any_of_fields)
        self.assertIn("region", qg.partial_any_of_fields)

    def test_quality_gate_config_complete_fields(self):
        """Test complete_required_fields and complete_any_of_fields."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            complete_required_fields=["name", "brand", "abv", "description", "palate_flavors"],
            complete_any_of_count=2,
            complete_any_of_fields=["nose_description", "finish_description", "distillery", "region"],
        )
        qg.refresh_from_db()
        self.assertIn("palate_flavors", qg.complete_required_fields)
        self.assertEqual(qg.complete_any_of_count, 2)
        self.assertEqual(len(qg.complete_any_of_fields), 4)

    def test_quality_gate_config_enriched_fields(self):
        """Test enriched_required_fields and enriched_any_of_fields."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            enriched_required_fields=[],
            enriched_any_of_count=2,
            enriched_any_of_fields=["awards", "ratings", "prices"],
        )
        qg.refresh_from_db()
        self.assertEqual(qg.enriched_required_fields, [])
        self.assertEqual(qg.enriched_any_of_count, 2)
        self.assertIn("awards", qg.enriched_any_of_fields)
        self.assertIn("ratings", qg.enriched_any_of_fields)
        self.assertIn("prices", qg.enriched_any_of_fields)

    def test_quality_gate_config_any_of_count_custom_values(self):
        """Test custom any_of_count values."""
        qg = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
            partial_any_of_count=3,
            complete_any_of_count=4,
            enriched_any_of_count=1,
        )
        self.assertEqual(qg.partial_any_of_count, 3)
        self.assertEqual(qg.complete_any_of_count, 4)
        self.assertEqual(qg.enriched_any_of_count, 1)


# =============================================================================
# Task 0.1.4: EnrichmentConfig Tests
# =============================================================================


class EnrichmentConfigModelTests(TestCase):
    """Tests for EnrichmentConfig model."""

    def setUp(self):
        """Create ProductTypeConfig for testing."""
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_enrichment_config_basic(self):
        """Test creating a basic EnrichmentConfig."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting_notes",
            display_name="Tasting Notes Search",
            search_template="{name} {brand} tasting notes review",
            target_fields=["nose_description", "palate_description"],
            priority=8,
            is_active=True,
        )
        self.assertEqual(ec.template_name, "tasting_notes")
        self.assertEqual(ec.display_name, "Tasting Notes Search")
        self.assertEqual(ec.priority, 8)
        self.assertTrue(ec.is_active)

    def test_enrichment_config_uuid_primary_key(self):
        """Test that EnrichmentConfig uses UUID primary key."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="test",
            display_name="Test",
            search_template="{name}",
        )
        self.assertIsInstance(ec.id, uuid.UUID)

    def test_enrichment_config_foreign_key(self):
        """Test ForeignKey relationship with ProductTypeConfig."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting",
            display_name="Tasting",
            search_template="{name}",
        )
        self.assertEqual(ec.product_type_config, self.whiskey_config)

    def test_enrichment_config_multiple_per_product_type(self):
        """Test that multiple EnrichmentConfigs can exist per ProductTypeConfig."""
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting_notes",
            display_name="Tasting Notes",
            search_template="{name} tasting notes",
        )
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="production_info",
            display_name="Production Info",
            search_template="{name} distillery production",
        )
        count = EnrichmentConfig.objects.filter(
            product_type_config=self.whiskey_config
        ).count()
        self.assertEqual(count, 2)

    def test_enrichment_config_related_name(self):
        """Test accessing EnrichmentConfigs via related_name from ProductTypeConfig."""
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting",
            display_name="Tasting",
            search_template="{name}",
        )
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="production",
            display_name="Production",
            search_template="{name}",
        )
        templates = self.whiskey_config.enrichment_templates.all()
        self.assertEqual(templates.count(), 2)

    def test_enrichment_config_ordering_by_priority(self):
        """Test default ordering by priority (descending)."""
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="low_priority",
            display_name="Low Priority",
            search_template="{name}",
            priority=1,
        )
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="high_priority",
            display_name="High Priority",
            search_template="{name}",
            priority=10,
        )
        EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="medium_priority",
            display_name="Medium Priority",
            search_template="{name}",
            priority=5,
        )
        configs = list(EnrichmentConfig.objects.all())
        self.assertEqual(configs[0].template_name, "high_priority")
        self.assertEqual(configs[1].template_name, "medium_priority")
        self.assertEqual(configs[2].template_name, "low_priority")

    def test_enrichment_config_defaults(self):
        """Test default values for EnrichmentConfig fields."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="test",
            display_name="Test",
            search_template="{name}",
        )
        self.assertEqual(ec.target_fields, [])
        self.assertEqual(ec.priority, 5)
        self.assertTrue(ec.is_active)

    def test_enrichment_config_db_table_name(self):
        """Test that EnrichmentConfig uses correct db_table."""
        self.assertEqual(EnrichmentConfig._meta.db_table, "enrichment_config")

    def test_enrichment_config_search_template_with_placeholders(self):
        """Test search_template with placeholders."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting_notes",
            display_name="Tasting Notes",
            search_template="{name} {brand} tasting notes review",
        )
        self.assertIn("{name}", ec.search_template)
        self.assertIn("{brand}", ec.search_template)

    def test_enrichment_config_target_fields_list(self):
        """Test target_fields accepts list of field names."""
        target_fields = ["nose_description", "palate_description", "finish_description"]
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="tasting_notes",
            display_name="Tasting Notes",
            search_template="{name} tasting notes",
            target_fields=target_fields,
        )
        ec.refresh_from_db()
        self.assertEqual(ec.target_fields, target_fields)

    def test_enrichment_config_priority_range(self):
        """Test priority accepts values 1-10."""
        ec_low = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="low",
            display_name="Low",
            search_template="{name}",
            priority=1,
        )
        ec_high = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="high",
            display_name="High",
            search_template="{name}",
            priority=10,
        )
        self.assertEqual(ec_low.priority, 1)
        self.assertEqual(ec_high.priority, 10)

    def test_enrichment_config_is_active_can_be_false(self):
        """Test is_active can be set to False."""
        ec = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="disabled",
            display_name="Disabled",
            search_template="{name}",
            is_active=False,
        )
        self.assertFalse(ec.is_active)


# =============================================================================
# Choices Tests
# =============================================================================


class FieldTypeChoicesTests(TestCase):
    """Tests for FieldTypeChoices enum."""

    def test_field_type_choices_values(self):
        """Test that all required field types are defined."""
        expected_types = ["string", "text", "integer", "decimal", "boolean", "array", "object"]
        actual_types = [choice[0] for choice in FieldTypeChoices.choices]
        for expected in expected_types:
            self.assertIn(expected, actual_types)


class FieldGroupChoicesTests(TestCase):
    """Tests for FieldGroupChoices enum."""

    def test_field_group_choices_values(self):
        """Test that all required field groups are defined."""
        expected_groups = [
            "core",
            "tasting_appearance",
            "tasting_nose",
            "tasting_palate",
            "tasting_finish",
            "tasting_overall",
            "production",
            "cask",
            "related",
            "type_specific",
        ]
        actual_groups = [choice[0] for choice in FieldGroupChoices.choices]
        for expected in expected_groups:
            self.assertIn(expected, actual_groups)


class TargetModelChoicesTests(TestCase):
    """Tests for TargetModelChoices enum."""

    def test_target_model_choices_values(self):
        """Test that all required target models are defined."""
        expected_models = [
            "DiscoveredProduct",
            "WhiskeyDetails",
            "PortWineDetails",
            "ProductAward",
            "ProductPrice",
            "ProductRating",
        ]
        actual_models = [choice[0] for choice in TargetModelChoices.choices]
        for expected in expected_models:
            self.assertIn(expected, actual_models)


# =============================================================================
# Cascade Delete Tests
# =============================================================================


class ConfigModelCascadeTests(TestCase):
    """Tests for cascade delete behavior."""

    def setUp(self):
        """Create test data."""
        self.whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        self.field_def = FieldDefinition.objects.create(
            product_type_config=self.whiskey_config,
            field_name="distillery",
            display_name="Distillery",
            field_type=FieldTypeChoices.STRING,
            description="Test",
            target_model=TargetModelChoices.WHISKEY_DETAILS,
            target_field="distillery",
        )
        self.quality_gate = QualityGateConfig.objects.create(
            product_type_config=self.whiskey_config,
        )
        self.enrichment = EnrichmentConfig.objects.create(
            product_type_config=self.whiskey_config,
            template_name="test",
            display_name="Test",
            search_template="{name}",
        )

    def test_cascade_delete_field_definitions(self):
        """Test that deleting ProductTypeConfig deletes related FieldDefinitions."""
        self.whiskey_config.delete()
        self.assertEqual(
            FieldDefinition.objects.filter(field_name="distillery").count(), 0
        )

    def test_cascade_delete_quality_gate_config(self):
        """Test that deleting ProductTypeConfig deletes related QualityGateConfig."""
        self.whiskey_config.delete()
        self.assertEqual(QualityGateConfig.objects.count(), 0)

    def test_cascade_delete_enrichment_config(self):
        """Test that deleting ProductTypeConfig deletes related EnrichmentConfigs."""
        self.whiskey_config.delete()
        self.assertEqual(EnrichmentConfig.objects.count(), 0)

    def test_shared_field_not_deleted_when_config_deleted(self):
        """Test that shared fields (product_type_config=None) are not deleted."""
        shared_field = FieldDefinition.objects.create(
            product_type_config=None,
            field_name="name",
            display_name="Product Name",
            field_type=FieldTypeChoices.STRING,
            description="Shared field",
            target_model=TargetModelChoices.DISCOVERED_PRODUCT,
            target_field="name",
        )

        self.whiskey_config.delete()

        # Shared field should still exist
        self.assertEqual(
            FieldDefinition.objects.filter(field_name="name").count(), 1
        )
