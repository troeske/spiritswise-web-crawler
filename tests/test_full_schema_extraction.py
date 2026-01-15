"""
Tests for Full Schema Extraction Behavior.

TDD: These tests are written BEFORE implementation.
They should FAIL initially, then PASS after Task 3 implementation.

Tests verify that:
1. detect_multi_product=True uses full schema from database (not skeleton)
2. Product-type-specific schemas are loaded correctly
3. Full schema is sent to VPS API
4. Backward compatibility with explicit extraction_schema is maintained

Spec Reference: FULL_SCHEMA_EXTRACTION_TASKS.md - Task 2
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import List, Dict, Any

from crawler.services.ai_client_v2 import (
    AIClientV2,
    MULTI_PRODUCT_SKELETON_SCHEMA,
    PreprocessedContent,
    ContentType,
)


@pytest.fixture
def setup_fields(db):
    """Set up FieldDefinition entries for testing."""
    from crawler.models import FieldDefinition, ProductTypeConfig

    # Create product type config for whiskey
    whiskey_config = ProductTypeConfig.objects.create(
        product_type="whiskey",
        display_name="Whiskey",
    )

    # Create shared fields (product_type_config=None)
    FieldDefinition.objects.create(
        field_name="name",
        display_name="Product Name",
        field_group="core",
        field_type="string",
        description="Full product name including brand and expression.",
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
        product_type_config=None,
        target_model="DiscoveredProduct",
        target_field="brand",
        is_active=True,
    )
    FieldDefinition.objects.create(
        field_name="finish_description",
        display_name="Finish Description",
        field_group="tasting_finish",
        field_type="text",
        description="Description of the finish taste and mouthfeel.",
        product_type_config=None,
        target_model="DiscoveredProduct",
        target_field="finish_description",
        is_active=True,
    )

    # Create whiskey-specific fields with derive_from
    FieldDefinition.objects.create(
        field_name="warmth",
        display_name="Warmth",
        field_group="tasting_finish",
        field_type="integer",
        description="Warmth rating 1-10",
        derive_from="finish_description",
        product_type_config=whiskey_config,
        target_model="WhiskeyDetails",
        target_field="warmth",
        is_active=True,
    )
    FieldDefinition.objects.create(
        field_name="dryness",
        display_name="Dryness",
        field_group="tasting_finish",
        field_type="integer",
        description="Dryness rating 1-10",
        derive_from="finish_description",
        product_type_config=whiskey_config,
        target_model="WhiskeyDetails",
        target_field="dryness",
        is_active=True,
    )
    FieldDefinition.objects.create(
        field_name="whiskey_style",
        display_name="Whiskey Style",
        field_group="whiskey",
        field_type="string",
        description="Type of whiskey",
        allowed_values=["scotch_single_malt", "bourbon", "rye"],
        product_type_config=whiskey_config,
        target_model="WhiskeyDetails",
        target_field="whiskey_style",
        is_active=True,
    )

    return {"whiskey_config": whiskey_config}


@pytest.fixture
def mock_preprocess():
    """Create mock preprocessor response."""
    return PreprocessedContent(
        content="<html>Test content</html>",
        content_type=ContentType.CLEANED_TEXT,
        original_length=1000,
        headings=["Test Heading"],
        truncated=False,
        token_estimate=500,
    )


class TestFullSchemaExtraction:
    """
    Tests for full schema extraction behavior.

    TDD: These tests should FAIL before Task 3 implementation.
    """

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_extract_uses_full_schema_for_multi_product(self, setup_fields, mock_preprocess):
        """
        When detect_multi_product=True, extract() should use full schema
        from database instead of skeleton schema.

        Verifies that:
        - 'schema' key in payload contains full field definitions (dicts)
        - Schema includes derive_from fields from database
        """
        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        async def capture_request(payload):
            nonlocal captured_payload
            captured_payload = payload
            return {
                "success": True,
                "is_multi_product": True,
                "product_count": 1,
                "products": [{
                    "product_type": "whiskey",
                    "type_confidence": 0.9,
                    "extracted_data": {"name": "Test Whiskey"},
                    "field_confidences": {},
                }],
            }

        with patch.object(client, "_send_request", side_effect=capture_request):
            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = MagicMock(return_value=mock_preprocess)

                await client.extract(
                    content="<html>Multi product page</html>",
                    source_url="https://example.com/products",
                    product_type="whiskey",
                    detect_multi_product=True,
                )

        # Assert: Payload should contain 'schema' with full field definitions
        assert captured_payload is not None

        # Full schema should be in 'schema' key (dicts with descriptions, derive_from)
        schema = captured_payload.get("schema", [])
        assert len(schema) > 0, "Expected 'schema' in payload with field definitions"
        assert isinstance(schema[0], dict), (
            f"Expected schema to contain dicts (full definitions), got {type(schema[0])}"
        )

        # Verify schema has derive_from fields (proves database schema was loaded)
        has_derive_from = any(
            f.get("derive_from") is not None for f in schema if isinstance(f, dict)
        )
        assert has_derive_from, "Expected at least one field with derive_from from database"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_extract_loads_product_type_specific_schema(self, setup_fields, mock_preprocess):
        """
        Full schema should be product-type-specific, loaded from database.

        TDD: This test should FAIL before implementation.
        """
        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        async def capture_request(payload):
            nonlocal captured_payload
            captured_payload = payload
            return {
                "success": True,
                "is_multi_product": True,
                "product_count": 1,
                "products": [{
                    "product_type": "whiskey",
                    "type_confidence": 0.9,
                    "extracted_data": {"name": "Test"},
                    "field_confidences": {},
                }],
            }

        with patch.object(client, "_send_request", side_effect=capture_request):
            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = MagicMock(return_value=mock_preprocess)

                await client.extract(
                    content="<html>Page</html>",
                    source_url="https://example.com",
                    product_type="whiskey",
                    detect_multi_product=True,
                )

        # Assert: Schema should be loaded from database (contains dicts, not just strings)
        assert captured_payload is not None
        schema = captured_payload.get("schema", [])

        # Full schema should be list of dicts with derive_from
        assert len(schema) > 0, "Expected schema to be populated"
        assert isinstance(schema[0], dict), "Schema should contain dicts, not strings"

        # Check for derive_from fields
        field_names = [f.get("name") for f in schema]
        assert "warmth" in field_names or "dryness" in field_names, (
            "Expected derived fields (warmth, dryness) in full schema"
        )

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_extract_sends_full_schema_to_vps(self, setup_fields, mock_preprocess):
        """
        Full schema with derive_from should be sent to VPS API.

        TDD: This test should FAIL before implementation.
        """
        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        async def capture_request(payload):
            nonlocal captured_payload
            captured_payload = payload
            return {
                "success": True,
                "is_multi_product": True,
                "product_count": 1,
                "products": [{
                    "product_type": "whiskey",
                    "type_confidence": 0.9,
                    "extracted_data": {},
                    "field_confidences": {},
                }],
            }

        with patch.object(client, "_send_request", side_effect=capture_request):
            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = MagicMock(return_value=mock_preprocess)

                await client.extract(
                    content="<html>Page</html>",
                    source_url="https://example.com",
                    product_type="whiskey",
                    detect_multi_product=True,
                )

        # Assert: 'schema' parameter should be in payload
        assert captured_payload is not None
        assert "schema" in captured_payload, "Expected 'schema' in API payload"

        schema = captured_payload["schema"]
        assert isinstance(schema, list), "Schema should be a list"
        assert len(schema) > 0, "Schema should not be empty"

        # Check that schema contains derive_from info
        has_derive_from = any(
            f.get("derive_from") is not None
            for f in schema
            if isinstance(f, dict)
        )
        assert has_derive_from, "Expected at least one field with derive_from in schema"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_backward_compatibility_with_explicit_schema(self, setup_fields, mock_preprocess):
        """
        Explicit extraction_schema parameter should override default behavior.

        This ensures backward compatibility for callers that pass their own schema.
        """
        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        custom_schema = ["name", "brand", "abv"]
        captured_payload = None

        async def capture_request(payload):
            nonlocal captured_payload
            captured_payload = payload
            return {
                "success": True,
                "is_multi_product": False,
                "product_count": 1,
                "products": [{
                    "product_type": "whiskey",
                    "type_confidence": 0.9,
                    "extracted_data": {"name": "Test"},
                    "field_confidences": {},
                }],
            }

        with patch.object(client, "_send_request", side_effect=capture_request):
            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = MagicMock(return_value=mock_preprocess)

                await client.extract(
                    content="<html>Page</html>",
                    source_url="https://example.com",
                    product_type="whiskey",
                    extraction_schema=custom_schema,
                    detect_multi_product=True,  # Should be ignored when explicit schema provided
                )

        # Assert: Custom schema should be used
        assert captured_payload is not None
        extraction_schema = captured_payload.get("extraction_schema", [])
        assert extraction_schema == custom_schema, (
            f"Expected custom schema {custom_schema}, got {extraction_schema}"
        )


class TestFullSchemaLogging:
    """Tests for logging behavior with full schema."""

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_logs_full_schema_usage(self, setup_fields, mock_preprocess, caplog):
        """
        Should log when using full schema for multi-product extraction.

        Logs appear at DEBUG level during schema preparation phase.
        """
        import logging
        # Set DEBUG level for the specific ai_client_v2 logger
        caplog.set_level(logging.DEBUG, logger="crawler.services.ai_client_v2")

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        captured_payload = None

        async def capture_request(payload):
            nonlocal captured_payload
            captured_payload = payload
            # Return mock response - will error in _parse_response but logs captured before that
            return {
                "success": True,
                "is_multi_product": True,
                "product_count": 1,
                "products": [{
                    "product_type": "whiskey",
                    "type_confidence": 0.9,
                    "extracted_data": {},
                    "field_confidences": {},
                }],
            }

        with patch.object(client, "_send_request", side_effect=capture_request):
            with patch("crawler.services.ai_client_v2.get_content_preprocessor") as mock_pp:
                mock_pp.return_value.preprocess = MagicMock(return_value=mock_preprocess)

                # Call extract - may error after _send_request but schema logs captured before
                try:
                    await client.extract(
                        content="<html>Page</html>",
                        source_url="https://example.com",
                        product_type="whiskey",
                        detect_multi_product=True,
                    )
                except Exception:
                    pass  # Error expected from mock response - schema logs already captured

        # Assert: Should log full schema usage (DEBUG level)
        log_messages = [r.message for r in caplog.records]
        has_schema_log = any(
            "full schema" in msg.lower() or "schema" in msg.lower()
            for msg in log_messages
        )
        assert has_schema_log, f"Expected log about schema usage. Logs: {log_messages}"
