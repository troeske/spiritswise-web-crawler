"""
Tests for AIClientV2 full schema integration.

Task Group: Phase 2 - Update AI Client to Send Full Schema
Spec Reference: SCHEMA_OPTIMIZATION_TASKS.md

These tests verify that AIClientV2 sends full schema definitions (not just field names)
to the AI service, enabling better extraction quality through rich field descriptions.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.django_db
class TestAIClientGetDefaultSchemaFullSchema:
    """Tests for _get_default_schema() returning full schema dicts."""

    @pytest.fixture
    def setup_field_definitions(self, db):
        """Create test field definitions for schema testing."""
        from crawler.models import FieldDefinition, ProductTypeConfig

        # Create product type config for whiskey
        whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

        # Create common/shared fields (product_type_config=None)
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
            examples=["Ardbeg", "Macallan", "Glenfiddich"],
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
            format_hint="Numeric value 0-80. If given as proof, divide by 2.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="abv",
            is_active=True,
        )

        # Create whiskey-specific field with derive_from
        FieldDefinition.objects.create(
            field_name="primary_aromas",
            display_name="Primary Aromas",
            field_group="tasting_nose",
            field_type="array",
            item_type="string",
            description="List of primary aroma notes detected on the nose.",
            derive_from="nose_description",
            product_type_config=whiskey_config,
            target_model="DiscoveredProduct",
            target_field="primary_aromas",
            is_active=True,
        )

        # Create enum field for whiskey
        FieldDefinition.objects.create(
            field_name="peat_level",
            display_name="Peat Level",
            field_group="whiskey",
            field_type="string",
            description="Level of peat smoke in the whiskey.",
            allowed_values=["none", "light", "medium", "heavy"],
            product_type_config=whiskey_config,
            target_model="WhiskeyDetails",
            target_field="peat_level",
            is_active=True,
        )

        return {"whiskey_config": whiskey_config}

    def test_get_default_schema_returns_full_schema_dicts(self, setup_field_definitions):
        """Schema includes full field definitions, not just names."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Should return list of dicts, not strings
        assert isinstance(schema, list)
        assert len(schema) > 0
        assert all(isinstance(item, dict) for item in schema)

        # Each dict should have required keys
        for field_def in schema:
            assert "name" in field_def
            assert "type" in field_def
            assert "description" in field_def

    def test_get_default_schema_includes_descriptions(self, setup_field_definitions):
        """Schema includes field descriptions for AI context."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find the 'name' field
        name_field = next((f for f in schema if f["name"] == "name"), None)
        assert name_field is not None
        assert "description" in name_field
        assert "product name" in name_field["description"].lower()

    def test_get_default_schema_by_product_type(self, setup_field_definitions):
        """Schema filters by product type correctly."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        field_names = [f["name"] for f in schema]

        # Should include common fields
        assert "name" in field_names
        assert "brand" in field_names
        assert "abv" in field_names

        # Should include whiskey-specific fields
        assert "primary_aromas" in field_names
        assert "peat_level" in field_names

    def test_schema_includes_derive_from(self, setup_field_definitions):
        """Schema includes derive_from relationships."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find primary_aromas field
        aromas_field = next((f for f in schema if f["name"] == "primary_aromas"), None)
        assert aromas_field is not None
        assert "derive_from" in aromas_field
        assert aromas_field["derive_from"] == "nose_description"
        assert "derive_instruction" in aromas_field

    def test_schema_includes_enum_constraints(self, setup_field_definitions):
        """Enum fields include allowed values."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find peat_level field
        peat_field = next((f for f in schema if f["name"] == "peat_level"), None)
        assert peat_field is not None
        assert "allowed_values" in peat_field
        assert "none" in peat_field["allowed_values"]
        assert "heavy" in peat_field["allowed_values"]
        assert "enum_instruction" in peat_field

    def test_schema_includes_format_hint(self, setup_field_definitions):
        """Schema includes format_hint when present."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find abv field
        abv_field = next((f for f in schema if f["name"] == "abv"), None)
        assert abv_field is not None
        assert "format_hint" in abv_field
        assert "proof" in abv_field["format_hint"].lower()

    def test_schema_includes_examples(self, setup_field_definitions):
        """Schema includes examples when present."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        schema = client._get_default_schema("whiskey")

        # Find name field
        name_field = next((f for f in schema if f["name"] == "name"), None)
        assert name_field is not None
        assert "examples" in name_field
        assert len(name_field["examples"]) > 0


@pytest.mark.django_db(transaction=True)
class TestAIClientAPICallWithFullSchema:
    """Tests for API calls including full schema in request payload."""

    @pytest.fixture
    def setup_minimal_fields(self, db):
        """Create minimal field definitions for API call testing."""
        from crawler.models import FieldDefinition, ProductTypeConfig

        # Create product type config for whiskey (needed for schema lookup)
        whiskey_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

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
        FieldDefinition.objects.create(
            field_name="brand",
            display_name="Brand",
            field_group="core",
            field_type="string",
            description="Brand name.",
            product_type_config=None,
            target_model="DiscoveredProduct",
            target_field="brand",
            is_active=True,
        )

        return {"whiskey_config": whiskey_config}

    @pytest.mark.asyncio
    async def test_extract_sends_full_schema_in_request(self, setup_minimal_fields):
        """API call includes full schema dicts in request payload."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Preprocessed content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def capture_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json", {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [{"extracted_data": {"name": "Test"}, "confidence": 0.9}],
                "processing_time_ms": 100,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                await client.extract(
                    content="<html>Test Product</html>",
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

        # Verify schema was sent
        assert captured_payload is not None
        assert "extraction_schema" in captured_payload

        schema = captured_payload["extraction_schema"]
        assert isinstance(schema, list)
        assert len(schema) >= 2

        # Schema should contain dicts with full definitions, not just strings
        assert all(isinstance(item, dict) for item in schema)

        # Verify schema items have descriptions
        name_field = next((f for f in schema if f["name"] == "name"), None)
        assert name_field is not None
        assert "description" in name_field

    @pytest.mark.asyncio
    async def test_api_request_schema_format(self, setup_minimal_fields):
        """Schema is properly formatted in API request."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Preprocessed content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def capture_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json", {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [{"extracted_data": {"name": "Test"}, "confidence": 0.9}],
                "processing_time_ms": 100,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        # Verify payload structure
        assert captured_payload is not None
        schema = captured_payload["extraction_schema"]

        # Each schema item should have name, type, description at minimum
        for field_def in schema:
            assert "name" in field_def, f"Missing 'name' in {field_def}"
            assert "type" in field_def, f"Missing 'type' in {field_def}"
            assert "description" in field_def, f"Missing 'description' in {field_def}"


@pytest.mark.django_db
class TestAIClientSchemaBackwardCompatibility:
    """Tests ensuring backward compatibility with existing callers."""

    @pytest.fixture
    def setup_fields(self, db):
        """Create test field definitions."""
        from crawler.models import FieldDefinition

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

    def test_custom_extraction_schema_still_works(self, setup_fields):
        """Custom extraction_schema parameter still works."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Custom schema can still be strings for backward compatibility
        custom_schema = ["name", "brand", "abv"]

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Preprocessed content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        preprocessed = mock_preprocess("<html></html>")

        # Build request with custom schema
        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/",
            product_type="whiskey",
            product_category=None,
            extraction_schema=custom_schema,
        )

        # Custom schema should be used as-is
        assert request["extraction_schema"] == custom_schema

    @pytest.mark.asyncio
    async def test_multi_product_skeleton_schema_still_works(self, setup_fields):
        """MULTI_PRODUCT_SKELETON_SCHEMA still works for list pages."""
        from crawler.services.ai_client_v2 import AIClientV2, MULTI_PRODUCT_SKELETON_SCHEMA

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        def mock_preprocess(content, url=None):
            mock = MagicMock()
            mock.content = "Preprocessed content"
            mock.content_type = MagicMock()
            mock.content_type.value = "cleaned_text"
            mock.token_estimate = 100
            mock.original_length = 500
            mock.headings = []
            mock.truncated = False
            return mock

        async def capture_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json", {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "products": [],
                "processing_time_ms": 100,
            }
            return mock_resp

        with patch("crawler.services.ai_client_v2.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = mock_preprocess

                # With detect_multi_product=True, should use skeleton schema
                await client.extract(
                    content="<html>List page</html>",
                    source_url="https://example.com/products",
                    product_type="whiskey",
                    detect_multi_product=True,
                )

        # Should use skeleton schema (list of strings)
        assert captured_payload is not None
        assert captured_payload["extraction_schema"] == MULTI_PRODUCT_SKELETON_SCHEMA


class TestAIClientEnumValidation:
    """Tests for enum field validation in AI response processing (Task 5.2)."""

    def test_validate_enum_field_accepts_valid(self):
        """Valid enum value passes validation unchanged."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Schema with enum field
        schema = [
            {
                "name": "whiskey_type",
                "type": "string",
                "description": "Type of whiskey",
                "allowed_values": ["single_malt", "blended", "bourbon", "rye"],
            },
            {
                "name": "name",
                "type": "string",
                "description": "Product name",
            },
        ]

        # Response with valid enum value
        response_data = {
            "whiskey_type": "single_malt",
            "name": "Test Whiskey",
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Valid value should pass through unchanged
        assert validated["whiskey_type"] == "single_malt"
        assert validated["name"] == "Test Whiskey"
        assert len(warnings) == 0

    def test_validate_enum_field_rejects_invalid(self):
        """Invalid enum value is flagged and set to None."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        schema = [
            {
                "name": "peat_level",
                "type": "string",
                "description": "Peat level",
                "allowed_values": ["unpeated", "lightly_peated", "medium_peated", "heavily_peated"],
            },
        ]

        # Response with invalid enum value
        response_data = {
            "peat_level": "smoky",  # Not in allowed_values
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Invalid value should be set to None
        assert validated["peat_level"] is None
        # Warning should be generated
        assert len(warnings) == 1
        assert "peat_level" in warnings[0]
        assert "smoky" in warnings[0]

    def test_validate_enum_case_insensitive(self):
        """Enum validation is case-insensitive."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        schema = [
            {
                "name": "style",
                "type": "string",
                "description": "Port wine style",
                "allowed_values": ["ruby", "tawny", "vintage", "lbv"],
            },
        ]

        # Response with different case
        response_data = {
            "style": "TAWNY",  # Uppercase but should match "tawny"
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Case-insensitive match should pass (normalized to lowercase)
        assert validated["style"] == "tawny"
        assert len(warnings) == 0

    def test_validate_enum_skips_non_enum_fields(self):
        """Fields without allowed_values are not validated."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        schema = [
            {
                "name": "name",
                "type": "string",
                "description": "Product name",
                # No allowed_values - free text
            },
            {
                "name": "abv",
                "type": "decimal",
                "description": "Alcohol by volume",
                # No allowed_values
            },
        ]

        response_data = {
            "name": "Any Name Here",
            "abv": 46.0,
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Non-enum fields should pass through unchanged
        assert validated["name"] == "Any Name Here"
        assert validated["abv"] == 46.0
        assert len(warnings) == 0

    def test_validate_enum_handles_null_values(self):
        """Null values for enum fields pass validation (field not extracted)."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        schema = [
            {
                "name": "whiskey_type",
                "type": "string",
                "description": "Type of whiskey",
                "allowed_values": ["single_malt", "blended"],
            },
        ]

        # Response with null value
        response_data = {
            "whiskey_type": None,
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Null should pass through unchanged
        assert validated["whiskey_type"] is None
        assert len(warnings) == 0

    def test_validate_enum_handles_empty_string(self):
        """Empty string for enum fields is treated as null."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        schema = [
            {
                "name": "peat_level",
                "type": "string",
                "description": "Peat level",
                "allowed_values": ["unpeated", "lightly_peated"],
            },
        ]

        response_data = {
            "peat_level": "",  # Empty string
        }

        validated, warnings = client._validate_enum_fields(response_data, schema)

        # Empty string should be normalized to None
        assert validated["peat_level"] is None
        assert len(warnings) == 0
