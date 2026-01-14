"""
Integration tests for the Schema System.

Task Group: Phase 6 - Testing & Validation
Spec Reference: SCHEMA_OPTIMIZATION_TASKS.md

These tests verify the complete schema flow from database to AI service
and back, ensuring consistency and proper validation at each step.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.django_db(transaction=True)
class TestFullSchemaFlow:
    """Test complete schema flow from database to extraction."""

    @pytest.fixture
    def setup_complete_schema(self, db):
        """Set up a complete schema with various field types for testing."""
        from crawler.models import FieldDefinition, ProductTypeConfig

        # Create product type config
        whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

        # Create common fields (shared across product types)
        FieldDefinition.objects.create(
            field_name="name",
            display_name="Product Name",
            field_group="core",
            field_type="string",
            description="Full product name including brand and expression.",
            examples=["Ardbeg 10 Year Old", "Glenfiddich 18"],
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="name",
            is_active=True,
        )
        FieldDefinition.objects.create(
            field_name="brand",
            display_name="Brand",
            field_group="core",
            field_type="string",
            description="Brand name of the product.",
            examples=["Ardbeg", "Macallan"],
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="brand",
            is_active=True,
        )
        FieldDefinition.objects.create(
            field_name="abv",
            display_name="ABV",
            field_group="core",
            field_type="decimal",
            description="Alcohol by volume percentage.",
            examples=[40.0, 46.0, 58.0],
            format_hint="Numeric value 0-80",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="abv",
            is_active=True,
        )

        # Create whiskey-specific field with enum
        FieldDefinition.objects.create(
            field_name="whiskey_type",
            display_name="Whiskey Type",
            field_group="whiskey",
            field_type="string",
            description="Type classification of the whiskey.",
            examples=["single_malt", "bourbon", "rye"],
            allowed_values=["single_malt", "blended_malt", "blended", "bourbon", "rye"],
            product_type_config=whiskey_config,
            target_model="WhiskeyDetails",
            target_field="whiskey_type",
            is_active=True,
        )

        # Create field with derive_from
        FieldDefinition.objects.create(
            field_name="color_intensity",
            display_name="Color Intensity",
            field_group="assessment",
            field_type="integer",
            description="Color intensity rating 1-10.",
            derive_from="color_description",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="color_intensity",
            is_active=True,
        )

        return {"whiskey_config": whiskey_config}

    def test_schema_loads_from_database(self, setup_complete_schema):
        """Schema loads correctly from FieldDefinition model."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Should include both common and whiskey-specific fields
        field_names = [f["name"] for f in schema]
        assert "name" in field_names
        assert "brand" in field_names
        assert "abv" in field_names
        assert "whiskey_type" in field_names
        assert "color_intensity" in field_names

    def test_schema_includes_full_definitions(self, setup_complete_schema):
        """Schema includes all field definition attributes."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find the whiskey_type field (has enum)
        whiskey_type = next(f for f in schema if f["name"] == "whiskey_type")
        assert whiskey_type["type"] == "string"
        assert "description" in whiskey_type
        assert "allowed_values" in whiskey_type
        assert "single_malt" in whiskey_type["allowed_values"]
        assert "enum_instruction" in whiskey_type  # Auto-generated from allowed_values

        # Find the color_intensity field (has derive_from)
        color_intensity = next(f for f in schema if f["name"] == "color_intensity")
        assert color_intensity["derive_from"] == "color_description"
        assert "derive_instruction" in color_intensity

        # Find the abv field (has format_hint)
        abv_field = next(f for f in schema if f["name"] == "abv")
        assert "format_hint" in abv_field
        assert "0-80" in abv_field["format_hint"]

    @pytest.mark.asyncio
    async def test_full_extraction_flow_with_schema(self, setup_complete_schema):
        """Test complete flow: load schema -> send to AI -> validate response."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Track what gets sent to the API
        captured_schema = None

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Test whiskey product content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def mock_post(*args, **kwargs):
            nonlocal captured_schema
            payload = kwargs.get("json", {})
            captured_schema = payload.get("extraction_schema")

            # Simulate AI response with valid and invalid enum values
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [
                    {
                        "extracted_data": {
                            "name": "Ardbeg 10 Year Old",
                            "brand": "Ardbeg",
                            "abv": 46.0,
                            "whiskey_type": "SINGLE_MALT",  # Uppercase - should be normalized
                        },
                        "confidence": 0.95,
                    }
                ],
                "processing_time_ms": 250,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                result = await client.extract(
                    content="<html>Ardbeg 10 Year Old Single Malt</html>",
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

        # Verify schema was sent with full definitions
        assert captured_schema is not None
        assert all(isinstance(f, dict) for f in captured_schema)

        # Verify extraction succeeded
        assert result.success is True
        assert len(result.products) == 1

        # Verify enum validation normalized the value
        product = result.products[0]
        assert product.extracted_data["whiskey_type"] == "single_malt"  # Normalized to lowercase

    @pytest.mark.asyncio
    async def test_invalid_enum_is_nullified(self, setup_complete_schema):
        """Invalid enum values are set to None with warning."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Test content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def mock_post(*args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [
                    {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "whiskey_type": "invalid_type",  # Not in allowed_values
                        },
                        "confidence": 0.8,
                    }
                ],
                "processing_time_ms": 100,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        # Invalid enum should be set to None
        assert result.success is True
        product = result.products[0]
        assert product.extracted_data["whiskey_type"] is None


@pytest.mark.django_db(transaction=True)
class TestSchemaConsistency:
    """Test schema consistency across the system."""

    @pytest.fixture
    def load_real_fixtures(self, db):
        """Load the actual base_fields.json fixture."""
        from django.core.management import call_command

        call_command("loaddata", "crawler/fixtures/base_fields.json", verbosity=0)

    def test_database_schema_is_authoritative(self, load_real_fixtures):
        """Database schema (base_fields.json) is the single source of truth."""
        from crawler.models import FieldDefinition

        # Verify fixture loaded
        field_count = FieldDefinition.objects.filter(is_active=True).count()
        assert field_count > 50, "base_fields.json should have 50+ field definitions"

        # Check key enum fields have allowed_values
        whiskey_type = FieldDefinition.objects.get(field_name="whiskey_type")
        assert whiskey_type.allowed_values is not None
        assert len(whiskey_type.allowed_values) > 0

        peat_level = FieldDefinition.objects.get(field_name="peat_level")
        assert peat_level.allowed_values is not None

    def test_ai_client_uses_database_schema(self, load_real_fixtures):
        """AI client loads schema from database, not hardcoded."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Get schema for whiskey
        schema = client._get_default_schema("whiskey")

        # Schema should be list of dicts, not strings
        assert isinstance(schema, list)
        assert len(schema) > 0
        assert isinstance(schema[0], dict)

        # Verify it matches database
        field_names_from_schema = {f["name"] for f in schema}
        from crawler.models import FieldDefinition

        db_field_names = set(
            FieldDefinition.objects.filter(is_active=True).values_list("field_name", flat=True)
        )

        # Schema should contain fields from database
        common_fields = field_names_from_schema & db_field_names
        assert len(common_fields) > 30, "Schema should contain many fields from database"

    def test_schema_includes_all_required_attributes(self, load_real_fixtures):
        """Schema dicts include all required attributes for AI extraction."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Every field should have these core attributes
        for field_def in schema:
            assert "name" in field_def, f"Missing 'name' in {field_def}"
            assert "type" in field_def, f"Missing 'type' in {field_def}"
            assert "description" in field_def, f"Missing 'description' in {field_def}"

    def test_no_hardcoded_field_descriptions_used(self, load_real_fixtures):
        """Verify hardcoded FIELD_DESCRIPTIONS are not used when schema provided."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find abv field
        abv_field = next((f for f in schema if f["name"] == "abv"), None)
        assert abv_field is not None

        # Description should be from database, not the old hardcoded one
        # The old hardcoded was: "Alcohol by volume percentage (e.g., 40.0 for 40%)"
        # The database one is more detailed with "Look for: ABV, Alcohol by Volume..."
        assert len(abv_field["description"]) > 50, "Description should be detailed from database"


@pytest.mark.django_db(transaction=True)
class TestSchemaBackwardCompatibility:
    """Test backward compatibility of schema system."""

    @pytest.fixture
    def setup_fields(self, db):
        """Set up minimal fields for testing."""
        from crawler.models import FieldDefinition, ProductTypeConfig

        ProductTypeConfig.objects.create(product_type="whiskey", display_name="Whiskey")

        FieldDefinition.objects.create(
            field_name="name",
            display_name="Product Name",
            field_group="core",
            field_type="string",
            description="Full product name.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="name",
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_skeleton_schema_skips_enum_validation(self, setup_fields):
        """MULTI_PRODUCT_SKELETON_SCHEMA (list of strings) skips enum validation."""
        from crawler.services.ai_client_v2 import AIClientV2, MULTI_PRODUCT_SKELETON_SCHEMA

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Test content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def mock_post(*args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [
                    {
                        "extracted_data": {
                            "name": "Product 1",
                            "style": "some_invalid_style",  # Would fail validation with full schema
                        },
                        "confidence": 0.7,
                    }
                ],
                "processing_time_ms": 100,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                # Use detect_multi_product which uses skeleton schema (strings only)
                result = await client.extract(
                    content="<html>List page</html>",
                    source_url="https://example.com/products",
                    product_type="whiskey",
                    detect_multi_product=True,
                )

        # Should succeed - skeleton schema doesn't have enum validation
        assert result.success is True
        # Value should be unchanged (no validation with string schema)
        assert result.products[0].extracted_data["style"] == "some_invalid_style"
