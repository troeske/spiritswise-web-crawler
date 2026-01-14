"""
Tests for FieldDefinition model and schema generation.

Task Group: Phase 1 - Enhance FieldDefinition Model
Spec Reference: SCHEMA_OPTIMIZATION_TASKS.md
"""

import pytest
from uuid import uuid4


@pytest.mark.django_db
class TestFieldDefinitionToExtractionSchema:
    """Tests for FieldDefinition.to_extraction_schema() method."""

    def test_to_extraction_schema_includes_all_fields(self):
        """Schema includes name, type, description, examples, derive_from."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="nose_description",
            display_name="Nose Description",
            field_group="tasting_nose",
            field_type="text",
            description="Tasting notes describing the aroma/nose of the product.",
            examples=["Rich honey and vanilla", "Intense peat smoke"],
            target_model="DiscoveredProduct",
            target_field="nose_description",
        )

        schema = field.to_extraction_schema()

        assert schema["name"] == "nose_description"
        assert schema["type"] == "text"
        assert schema["description"] == "Tasting notes describing the aroma/nose of the product."
        assert schema["examples"] == ["Rich honey and vanilla", "Intense peat smoke"]

    def test_to_extraction_schema_handles_null_values(self):
        """Schema handles fields with null optional values gracefully."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="simple_field",
            display_name="Simple Field",
            field_group="core",
            field_type="string",
            description="A simple field without optional values.",
            examples=[],
            allowed_values=[],
            item_schema={},
            target_model="DiscoveredProduct",
            target_field="simple_field",
        )

        schema = field.to_extraction_schema()

        # Required fields present
        assert schema["name"] == "simple_field"
        assert schema["type"] == "string"
        assert schema["description"] == "A simple field without optional values."

        # Optional fields not included when empty
        assert "examples" not in schema
        assert "derive_from" not in schema
        assert "derive_instruction" not in schema
        assert "allowed_values" not in schema
        assert "enum_instruction" not in schema
        assert "item_schema" not in schema

    def test_to_extraction_schema_includes_allowed_values(self):
        """Enum fields include allowed_values in schema with instruction."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="whiskey_type",
            display_name="Whiskey Type",
            field_group="whiskey",
            field_type="string",
            description="Type classification of the whiskey.",
            allowed_values=["single_malt", "bourbon", "rye", "blended"],
            target_model="WhiskeyDetails",
            target_field="whiskey_type",
        )

        schema = field.to_extraction_schema()

        assert schema["allowed_values"] == ["single_malt", "bourbon", "rye", "blended"]
        assert "enum_instruction" in schema
        assert "MUST be one of:" in schema["enum_instruction"]
        assert "single_malt" in schema["enum_instruction"]

    def test_to_extraction_schema_includes_derive_from(self):
        """Schema includes derive_from with instruction when present."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="primary_aromas",
            display_name="Primary Aromas",
            field_group="tasting_nose",
            field_type="array",
            item_type="string",
            description="List of primary aroma notes.",
            derive_from="nose_description",
            target_model="DiscoveredProduct",
            target_field="primary_aromas",
        )

        schema = field.to_extraction_schema()

        assert schema["derive_from"] == "nose_description"
        assert "derive_instruction" in schema
        assert "primary_aromas" in schema["derive_instruction"]
        assert "nose_description" in schema["derive_instruction"]

    def test_to_extraction_schema_includes_item_schema(self):
        """Array fields include item_schema for nested types."""
        from crawler.models import FieldDefinition

        item_schema = {
            "type": "object",
            "properties": {
                "competition": {"type": "string"},
                "year": {"type": "integer"},
                "medal": {"type": "string"},
            },
            "required": ["competition", "year", "medal"],
        }

        field = FieldDefinition.objects.create(
            field_name="awards",
            display_name="Awards",
            field_group="related",
            field_type="array",
            item_type="object",
            description="Competition awards won by this product.",
            item_schema=item_schema,
            target_model="ProductAward",
            target_field="awards",
        )

        schema = field.to_extraction_schema()

        assert schema["item_schema"] == item_schema
        assert schema["item_schema"]["type"] == "object"

    def test_to_extraction_schema_includes_format_hint(self):
        """Schema includes format_hint when present."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="drinking_window",
            display_name="Drinking Window",
            field_group="port_wine",
            field_type="string",
            description="Optimal drinking window for the port.",
            format_hint="Format: 'YYYY-YYYY' or 'Now-YYYY' or 'Drink now'",
            target_model="PortWineDetails",
            target_field="drinking_window",
        )

        schema = field.to_extraction_schema()

        assert schema["format_hint"] == "Format: 'YYYY-YYYY' or 'Now-YYYY' or 'Drink now'"

    def test_to_extraction_schema_complete_field(self):
        """Test a field with all optional values populated."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="style",
            display_name="Port Wine Style",
            field_group="port_wine",
            field_type="string",
            description="Port wine style classification.",
            examples=["ruby", "tawny", "vintage"],
            allowed_values=["ruby", "tawny", "white", "rose", "lbv", "vintage"],
            format_hint="Use lowercase, single word",
            target_model="PortWineDetails",
            target_field="style",
        )

        schema = field.to_extraction_schema()

        assert schema["name"] == "style"
        assert schema["type"] == "string"
        assert schema["description"] == "Port wine style classification."
        assert schema["examples"] == ["ruby", "tawny", "vintage"]
        assert schema["allowed_values"] == ["ruby", "tawny", "white", "rose", "lbv", "vintage"]
        assert "enum_instruction" in schema
        assert schema["format_hint"] == "Use lowercase, single word"


@pytest.mark.django_db
class TestFieldDefinitionGetSchemaForProductType:
    """Tests for FieldDefinition.get_schema_for_product_type() class method."""

    @pytest.fixture
    def setup_field_definitions(self, db):
        """Create test field definitions for various product types."""
        from crawler.models import FieldDefinition, ProductTypeConfig

        # Create product type configs
        whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

        # Create shared/common fields (product_type_config=None)
        FieldDefinition.objects.create(
            field_name="name",
            display_name="Product Name",
            field_group="core",
            field_type="string",
            description="Full product name.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="name",
        )
        FieldDefinition.objects.create(
            field_name="brand",
            display_name="Brand",
            field_group="core",
            field_type="string",
            description="Brand name.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="brand",
        )
        FieldDefinition.objects.create(
            field_name="abv",
            display_name="ABV",
            field_group="core",
            field_type="decimal",
            description="Alcohol percentage.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="abv",
        )

        # Create whiskey-specific fields
        FieldDefinition.objects.create(
            field_name="distillery",
            display_name="Distillery",
            field_group="whiskey",
            field_type="string",
            description="Name of the distillery.",
            product_type_config=whiskey_config,
            target_model="WhiskeyDetails",
            target_field="distillery",
        )
        FieldDefinition.objects.create(
            field_name="peated",
            display_name="Peated",
            field_group="whiskey",
            field_type="boolean",
            description="Whether the whiskey uses peated malt.",
            product_type_config=whiskey_config,
            target_model="WhiskeyDetails",
            target_field="peated",
        )

        # Create port wine-specific fields
        FieldDefinition.objects.create(
            field_name="style",
            display_name="Port Wine Style",
            field_group="port_wine",
            field_type="string",
            description="Port wine style classification.",
            product_type_config=port_config,
            target_model="PortWineDetails",
            target_field="style",
        )
        FieldDefinition.objects.create(
            field_name="quinta",
            display_name="Quinta",
            field_group="port_wine",
            field_type="string",
            description="Name of the quinta.",
            product_type_config=port_config,
            target_model="PortWineDetails",
            target_field="quinta",
        )

        return {
            "whiskey_config": whiskey_config,
            "port_config": port_config,
        }

    def test_get_schema_for_whiskey(self, setup_field_definitions):
        """Returns whiskey-specific fields plus common fields."""
        from crawler.models import FieldDefinition

        schema = FieldDefinition.get_schema_for_product_type("whiskey")

        field_names = [f["name"] for f in schema]

        # Should include common fields
        assert "name" in field_names
        assert "brand" in field_names
        assert "abv" in field_names

        # Should include whiskey-specific fields
        assert "distillery" in field_names
        assert "peated" in field_names

        # Should NOT include port wine fields
        assert "style" not in field_names
        assert "quinta" not in field_names

    def test_get_schema_for_port_wine(self, setup_field_definitions):
        """Returns port wine-specific fields plus common fields."""
        from crawler.models import FieldDefinition

        schema = FieldDefinition.get_schema_for_product_type("port_wine")

        field_names = [f["name"] for f in schema]

        # Should include common fields
        assert "name" in field_names
        assert "brand" in field_names
        assert "abv" in field_names

        # Should include port wine fields
        assert "style" in field_names
        assert "quinta" in field_names

        # Should NOT include whiskey fields
        assert "distillery" not in field_names
        assert "peated" not in field_names

    def test_get_schema_excludes_irrelevant_fields(self, setup_field_definitions):
        """Whiskey schema doesn't include port wine fields."""
        from crawler.models import FieldDefinition

        whiskey_schema = FieldDefinition.get_schema_for_product_type("whiskey")
        port_schema = FieldDefinition.get_schema_for_product_type("port_wine")

        whiskey_fields = {f["name"] for f in whiskey_schema}
        port_fields = {f["name"] for f in port_schema}

        # Verify no overlap in product-specific fields
        whiskey_specific = whiskey_fields - {"name", "brand", "abv"}
        port_specific = port_fields - {"name", "brand", "abv"}

        assert whiskey_specific.isdisjoint(port_specific)

    def test_get_schema_returns_list_of_dicts(self, setup_field_definitions):
        """Returns list of schema dicts, not field objects."""
        from crawler.models import FieldDefinition

        schema = FieldDefinition.get_schema_for_product_type("whiskey")

        assert isinstance(schema, list)
        assert len(schema) > 0

        for item in schema:
            assert isinstance(item, dict)
            assert "name" in item
            assert "type" in item
            assert "description" in item

    def test_get_schema_without_common_fields(self, setup_field_definitions):
        """Can exclude common fields when include_common=False."""
        from crawler.models import FieldDefinition

        schema = FieldDefinition.get_schema_for_product_type(
            "whiskey", include_common=False
        )

        field_names = [f["name"] for f in schema]

        # Should NOT include common fields
        assert "name" not in field_names
        assert "brand" not in field_names
        assert "abv" not in field_names

        # Should include whiskey-specific fields
        assert "distillery" in field_names
        assert "peated" in field_names

    def test_get_schema_for_unknown_product_type(self, setup_field_definitions):
        """Returns only common fields for unknown product type."""
        from crawler.models import FieldDefinition

        schema = FieldDefinition.get_schema_for_product_type("unknown_type")

        field_names = [f["name"] for f in schema]

        # Should include common fields only
        assert "name" in field_names
        assert "brand" in field_names
        assert "abv" in field_names

        # Should NOT include any product-specific fields
        assert "distillery" not in field_names
        assert "style" not in field_names


@pytest.mark.django_db
class TestFieldDefinitionFormatHintField:
    """Tests for format_hint field on FieldDefinition."""

    def test_format_hint_field_exists(self):
        """FieldDefinition has format_hint field."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="test_field",
            display_name="Test Field",
            field_group="core",
            field_type="string",
            description="Test field description.",
            format_hint="Test format hint",
            target_model="DiscoveredProduct",
            target_field="test_field",
        )

        assert field.format_hint == "Test format hint"
        field.refresh_from_db()
        assert field.format_hint == "Test format hint"

    def test_format_hint_in_extraction_schema(self):
        """format_hint is included in extraction schema."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="abv",
            display_name="ABV",
            field_group="core",
            field_type="decimal",
            description="Alcohol by volume percentage.",
            format_hint="Numeric value 0-80. If given as proof, divide by 2.",
            target_model="DiscoveredProduct",
            target_field="abv",
        )

        schema = field.to_extraction_schema()

        assert "format_hint" in schema
        assert schema["format_hint"] == "Numeric value 0-80. If given as proof, divide by 2."

    def test_format_hint_can_be_null(self):
        """format_hint can be null/blank."""
        from crawler.models import FieldDefinition

        field = FieldDefinition.objects.create(
            field_name="description",
            display_name="Description",
            field_group="core",
            field_type="text",
            description="Product description.",
            format_hint=None,
            target_model="DiscoveredProduct",
            target_field="description",
        )

        assert field.format_hint is None

        schema = field.to_extraction_schema()
        assert "format_hint" not in schema
