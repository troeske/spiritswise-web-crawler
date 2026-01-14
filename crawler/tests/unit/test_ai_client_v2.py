"""
Unit tests for AIClientV2 - AI Service V2 Client.

Phase 3 of V2 Architecture: Tests for the AI client that communicates
with the AI Service V2 /api/v2/extract/ endpoint.

Features tested:
1. ExtractionResultV2 and ExtractedProductV2 dataclasses
2. Request building with content preprocessing
3. Response parsing for single and multi-product responses
4. Error handling (400, 401, 500, timeout, connection)
5. Retry logic with exponential backoff
6. Content preprocessing integration
7. Configuration management

Spec Reference: V2 Architecture Phase 3
"""

import pytest
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import httpx
import asyncio


# =============================================================================
# Fixtures
# =============================================================================

SUCCESS_RESPONSE_SINGLE = {
    "products": [
        {
            "extracted_data": {
                "name": "Ardbeg 10 Year Old",
                "brand": "Ardbeg",
                "abv": 46.0,
                "volume_ml": 700,
                "description": "A powerful Islay single malt",
            },
            "product_type": "whiskey",
            "confidence": 0.92,
            "field_confidences": {
                "name": 0.99,
                "brand": 0.95,
                "abv": 0.90,
                "volume_ml": 0.85,
                "description": 0.88,
            },
        }
    ],
    "extraction_summary": {
        "fields_extracted": 5,
        "fields_attempted": 8,
        "product_count": 1,
        "is_list_page": False,
    },
    "processing_time_ms": 150.5,
    "token_usage": {"prompt": 1200, "completion": 350},
}

SUCCESS_RESPONSE_MULTI = {
    "products": [
        {
            "extracted_data": {
                "name": "Glenfiddich 12 Year Old",
                "brand": "Glenfiddich",
                "abv": 40.0,
            },
            "product_type": "whiskey",
            "confidence": 0.88,
            "field_confidences": {"name": 0.95, "brand": 0.92, "abv": 0.85},
        },
        {
            "extracted_data": {
                "name": "Macallan 12 Year Old",
                "brand": "Macallan",
                "abv": 43.0,
            },
            "product_type": "whiskey",
            "confidence": 0.90,
            "field_confidences": {"name": 0.97, "brand": 0.94, "abv": 0.88},
        },
        {
            "extracted_data": {
                "name": "Glenlivet 12 Year Old",
                "brand": "Glenlivet",
                "abv": 40.0,
            },
            "product_type": "whiskey",
            "confidence": 0.87,
            "field_confidences": {"name": 0.93, "brand": 0.91, "abv": 0.84},
        },
    ],
    "extraction_summary": {
        "fields_extracted": 9,
        "fields_attempted": 9,
        "product_count": 3,
        "is_list_page": True,
    },
    "is_list_page": True,
    "processing_time_ms": 280.3,
    "token_usage": {"prompt": 2500, "completion": 600},
}

EMPTY_PRODUCTS_RESPONSE = {
    "products": [],
    "extraction_summary": {
        "fields_extracted": 0,
        "fields_attempted": 0,
        "product_count": 0,
        "is_list_page": False,
    },
    "processing_time_ms": 50.0,
    "token_usage": {"prompt": 800, "completion": 50},
}

ERROR_RESPONSE_400 = {
    "error": "Validation error",
    "detail": "Missing required field: content",
}

ERROR_RESPONSE_500 = {
    "error": "Internal server error",
    "detail": "AI model unavailable",
}

SAMPLE_HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head><title>Ardbeg 10 Year Old</title></head>
<body>
    <h1>Ardbeg 10 Year Old</h1>
    <p>A powerful Islay single malt with intense smoky character.</p>
    <span class="abv">46% ABV</span>
    <span class="price">$54.99</span>
</body>
</html>
"""

SAMPLE_PREPROCESSED_CONTENT = "Ardbeg 10 Year Old. A powerful Islay single malt with intense smoky character. 46% ABV. $54.99"

SAMPLE_FIELD_NAMES = ["name", "brand", "abv", "volume_ml", "description"]


def create_mock_preprocessed_content(
    content: str = "Clean text",
    content_type_value: str = "cleaned_text",
    token_estimate: int = 100,
    original_length: int = 1000,
    headings: Optional[List[str]] = None,
    truncated: bool = False,
):
    """Create a mock PreprocessedContent object."""
    mock = MagicMock()
    mock.content = content
    mock.content_type = MagicMock()
    mock.content_type.value = content_type_value
    mock.token_estimate = token_estimate
    mock.original_length = original_length
    mock.headings = headings or []
    mock.truncated = truncated
    return mock


# =============================================================================
# Test Classes
# =============================================================================


class TestExtractionResultV2Dataclass:
    """Tests for ExtractionResultV2 dataclass."""

    def test_creation_with_all_fields(self):
        """Creates ExtractionResultV2 with all fields."""
        from crawler.services.ai_client_v2 import ExtractionResultV2, ExtractedProductV2

        product = ExtractedProductV2(
            extracted_data={"name": "Test Product"},
            product_type="whiskey",
            confidence=0.9,
            field_confidences={"name": 0.95},
        )

        result = ExtractionResultV2(
            success=True,
            products=[product],
            extraction_summary={"fields_extracted": 10},
            processing_time_ms=150.5,
            error=None,
            token_usage={"prompt": 100, "completion": 50},
        )

        assert result.success is True
        assert len(result.products) == 1
        assert result.extraction_summary["fields_extracted"] == 10
        assert result.processing_time_ms == 150.5
        assert result.error is None
        assert result.token_usage["prompt"] == 100

    def test_creation_with_error(self):
        """Creates ExtractionResultV2 with error state."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        result = ExtractionResultV2(
            success=False,
            products=[],
            extraction_summary={},
            processing_time_ms=0.0,
            error="Connection timeout",
            token_usage=None,
        )

        assert result.success is False
        assert result.products == []
        assert result.error == "Connection timeout"

    def test_dataclass_has_success_field(self):
        """ExtractionResultV2 has success field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "success" in field_names

    def test_dataclass_has_products_field(self):
        """ExtractionResultV2 has products field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "products" in field_names

    def test_dataclass_has_extraction_summary_field(self):
        """ExtractionResultV2 has extraction_summary field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "extraction_summary" in field_names

    def test_dataclass_has_processing_time_ms_field(self):
        """ExtractionResultV2 has processing_time_ms field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "processing_time_ms" in field_names

    def test_dataclass_has_error_field(self):
        """ExtractionResultV2 has error field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "error" in field_names

    def test_dataclass_has_token_usage_field(self):
        """ExtractionResultV2 has token_usage field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "token_usage" in field_names

    def test_dataclass_has_is_list_page_field(self):
        """ExtractionResultV2 has is_list_page field."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        field_names = [f.name for f in fields(ExtractionResultV2)]
        assert "is_list_page" in field_names

    def test_default_values(self):
        """ExtractionResultV2 has correct default values."""
        from crawler.services.ai_client_v2 import ExtractionResultV2

        result = ExtractionResultV2(success=True)

        # Verify defaults
        assert result.products == []
        assert result.extraction_summary == {}
        assert result.processing_time_ms == 0.0
        assert result.error is None
        assert result.token_usage is None
        assert result.is_list_page is False


class TestExtractedProductV2:
    """Tests for ExtractedProductV2 dataclass."""

    def test_creation_with_all_fields(self):
        """Creates ExtractedProductV2 with all fields."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        product = ExtractedProductV2(
            extracted_data={
                "name": "Ardbeg 10",
                "brand": "Ardbeg",
                "abv": 46.0,
            },
            product_type="whiskey",
            confidence=0.92,
            field_confidences={
                "name": 0.99,
                "brand": 0.95,
                "abv": 0.90,
            },
        )

        assert product.extracted_data["name"] == "Ardbeg 10"
        assert product.product_type == "whiskey"
        assert product.confidence == 0.92
        assert product.field_confidences["name"] == 0.99

    def test_dataclass_has_extracted_data_field(self):
        """ExtractedProductV2 has extracted_data field."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        field_names = [f.name for f in fields(ExtractedProductV2)]
        assert "extracted_data" in field_names

    def test_dataclass_has_product_type_field(self):
        """ExtractedProductV2 has product_type field."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        field_names = [f.name for f in fields(ExtractedProductV2)]
        assert "product_type" in field_names

    def test_dataclass_has_confidence_field(self):
        """ExtractedProductV2 has confidence field."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        field_names = [f.name for f in fields(ExtractedProductV2)]
        assert "confidence" in field_names

    def test_dataclass_has_field_confidences_field(self):
        """ExtractedProductV2 has field_confidences field."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        field_names = [f.name for f in fields(ExtractedProductV2)]
        assert "field_confidences" in field_names

    def test_default_values(self):
        """ExtractedProductV2 has correct default values."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        product = ExtractedProductV2()

        assert product.extracted_data == {}
        assert product.product_type == ""
        assert product.confidence == 0.0
        assert product.field_confidences == {}

    def test_empty_extracted_data(self):
        """ExtractedProductV2 allows empty extracted_data."""
        from crawler.services.ai_client_v2 import ExtractedProductV2

        product = ExtractedProductV2(
            extracted_data={},
            product_type="unknown",
            confidence=0.0,
        )

        assert product.extracted_data == {}


class TestRequestBuilding:
    """Tests for AIClientV2._build_request() method."""

    def test_build_request_creates_correct_structure(self):
        """_build_request() creates correct request structure."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content()

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert "source_data" in request
        assert "product_type" in request
        assert "extraction_schema" in request
        assert "options" in request

    def test_build_request_includes_source_data(self):
        """_build_request() includes correct source_data."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content(
            content="Clean product text",
            content_type_value="cleaned_text",
        )

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product/123",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["source_data"]["content"] == "Clean product text"
        assert request["source_data"]["url"] == "https://example.com/product/123"
        assert request["source_data"]["content_type"] == "cleaned_text"

    def test_build_request_includes_product_type(self):
        """_build_request() includes product_type."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content()

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="port_wine",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["product_type"] == "port_wine"

    def test_build_request_includes_extraction_schema(self):
        """_build_request() includes extraction_schema."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content()

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["extraction_schema"] == SAMPLE_FIELD_NAMES

    def test_build_request_includes_options(self):
        """_build_request() includes options with confidence and multi-product detection."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content()

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert "include_confidence" in request["options"]
        assert "detect_multi_product" in request["options"]
        assert request["options"]["include_confidence"] is True
        assert request["options"]["detect_multi_product"] is True

    def test_build_request_includes_product_category_when_provided(self):
        """_build_request() includes product_category when provided."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content()

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category="bourbon",
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["product_category"] == "bourbon"

    def test_build_request_includes_headings_when_available(self):
        """_build_request() includes headings when available."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content(
            headings=["Ardbeg 10 Year Old", "Tasting Notes"],
        )

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["source_data"]["headings"] == ["Ardbeg 10 Year Old", "Tasting Notes"]

    def test_build_request_includes_truncated_flag(self):
        """_build_request() includes truncated flag when content was truncated."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content(truncated=True)

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/product",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["source_data"]["truncated"] is True

    def test_build_request_with_structured_html_content_type(self):
        """_build_request() handles structured_html content type."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        preprocessed = create_mock_preprocessed_content(
            content="<div>Product list</div>",
            content_type_value="structured_html",
        )

        request = client._build_request(
            preprocessed=preprocessed,
            source_url="https://example.com/products",
            product_type="whiskey",
            product_category=None,
            extraction_schema=SAMPLE_FIELD_NAMES,
        )

        assert request["source_data"]["content_type"] == "structured_html"


class TestResponseParsing:
    """Tests for AIClientV2._parse_response() method."""

    def test_parse_response_handles_success_response(self):
        """_parse_response() handles success response."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert result.success is True
        assert len(result.products) == 1
        assert result.products[0].extracted_data["name"] == "Ardbeg 10 Year Old"

    def test_parse_response_handles_single_product(self):
        """_parse_response() correctly parses single product response."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert len(result.products) == 1
        assert result.products[0].product_type == "whiskey"
        assert result.products[0].confidence == 0.92
        assert result.extraction_summary["is_list_page"] is False

    def test_parse_response_handles_multi_product(self):
        """_parse_response() correctly parses multi-product response."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_MULTI

        result = client._parse_response(mock_response)

        assert len(result.products) == 3
        assert result.products[0].extracted_data["name"] == "Glenfiddich 12 Year Old"
        assert result.products[1].extracted_data["name"] == "Macallan 12 Year Old"
        assert result.products[2].extracted_data["name"] == "Glenlivet 12 Year Old"
        assert result.is_list_page is True

    def test_parse_response_handles_empty_products(self):
        """_parse_response() handles empty products array."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = EMPTY_PRODUCTS_RESPONSE

        result = client._parse_response(mock_response)

        assert result.success is True
        assert result.products == []
        assert result.extraction_summary["product_count"] == 0

    def test_parse_response_maps_field_confidences(self):
        """_parse_response() correctly maps field_confidences."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert result.products[0].field_confidences["name"] == 0.99
        assert result.products[0].field_confidences["brand"] == 0.95
        assert result.products[0].field_confidences["abv"] == 0.90

    def test_parse_response_handles_extraction_summary(self):
        """_parse_response() correctly parses extraction_summary."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert result.extraction_summary["fields_extracted"] == 5
        assert result.extraction_summary["fields_attempted"] == 8
        assert result.extraction_summary["product_count"] == 1

    def test_parse_response_handles_processing_time(self):
        """_parse_response() correctly parses processing_time_ms."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert result.processing_time_ms == 150.5

    def test_parse_response_handles_token_usage(self):
        """_parse_response() correctly parses token_usage."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

        result = client._parse_response(mock_response)

        assert result.token_usage["prompt"] == 1200
        assert result.token_usage["completion"] == 350


class TestErrorHandling:
    """Tests for AIClientV2 error handling."""

    def test_handles_400_bad_request(self):
        """Handles 400 Bad Request (validation error)."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = ERROR_RESPONSE_400
        mock_response.text = "Validation error: Missing required field: content"

        result = client._parse_response(mock_response)

        assert result.success is False
        assert "400" in result.error or "Validation" in result.error

    def test_handles_401_unauthorized(self):
        """Handles 401 Unauthorized."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid API key"}
        mock_response.text = "Unauthorized"

        result = client._parse_response(mock_response)

        assert result.success is False
        assert "401" in result.error or "Invalid" in result.error

    def test_handles_500_internal_server_error(self):
        """Handles 500 Internal Server Error."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = ERROR_RESPONSE_500
        mock_response.text = "Internal server error"

        result = client._parse_response(mock_response)

        assert result.success is False
        assert "500" in result.error or "Internal" in result.error

    @pytest.mark.asyncio
    async def test_handles_network_timeout(self):
        """Handles network timeout."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            timeout=1.0,
            max_retries=1,
        )

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="Test content",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert result.success is False
        assert "timeout" in result.error.lower() or "retries" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_connection_error(self):
        """Handles connection error."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=1,
        )

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="Test content",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert result.success is False
        assert "connection" in result.error.lower() or "connect" in result.error.lower()

    def test_handles_malformed_json_response(self):
        """Handles malformed JSON response."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not valid JSON {"

        result = client._parse_response(mock_response)

        assert result.success is False
        assert "JSON" in result.error

    def test_returns_extraction_result_on_failure(self):
        """Returns ExtractionResultV2 with error on failure."""
        from crawler.services.ai_client_v2 import AIClientV2, ExtractionResultV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"error": "Service unavailable"}
        mock_response.text = "Service unavailable"

        result = client._parse_response(mock_response)

        assert isinstance(result, ExtractionResultV2)
        assert result.success is False
        assert result.error is not None
        assert result.products == []

    def test_handles_error_in_response_body(self):
        """Handles error field in response body even with 200 status."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "Extraction failed"}

        result = client._parse_response(mock_response)

        assert result.success is False
        assert "Extraction failed" in result.error


class TestRetryLogic:
    """Tests for AIClientV2 retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_500_errors(self):
        """Retries on 500 errors."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=3,
        )
        # Override retry delay for faster testing
        client.RETRY_BASE_DELAY = 0.01

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.json.return_value = {"error": "Server error"}
                mock_resp.text = "Server error"
                return mock_resp
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = SUCCESS_RESPONSE_SINGLE
                return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert call_count == 3
        assert result.success is True

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """Retries on timeout."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=2,
        )
        client.RETRY_BASE_DELAY = 0.01

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = SUCCESS_RESPONSE_SINGLE
                return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert call_count == 2
        assert result.success is True

    @pytest.mark.asyncio
    async def test_max_retries_limit(self):
        """Max retries limit is respected."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=2,
        )
        client.RETRY_BASE_DELAY = 0.01

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.json.return_value = {"error": "Server error"}
            mock_resp.text = "Server error"
            return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        # Should have called max_retries times
        assert call_count == 2
        assert result.success is False

    @pytest.mark.asyncio
    async def test_no_retry_on_400_errors(self):
        """No retry on 400 errors (client errors)."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=3,
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.json.return_value = ERROR_RESPONSE_400
            mock_resp.text = "Bad request"
            return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        # Should not retry on 400
        assert call_count == 1
        assert result.success is False

    @pytest.mark.asyncio
    async def test_no_retry_on_401_errors(self):
        """No retry on 401 errors (auth errors)."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=3,
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": "Unauthorized"}
            mock_resp.text = "Unauthorized"
            return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        # Should not retry on 401
        assert call_count == 1
        assert result.success is False

    @pytest.mark.asyncio
    async def test_successful_retry_after_transient_failure(self):
        """Successful retry after transient failure."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=3,
        )
        client.RETRY_BASE_DELAY = 0.01

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = SUCCESS_RESPONSE_SINGLE
                return mock_resp

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert call_count == 2
        assert result.success is True
        assert len(result.products) == 1


class TestTimeoutHandling:
    """Tests for AIClientV2 timeout handling."""

    def test_request_timeout_is_configurable(self):
        """Request timeout is configurable."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            timeout=120.0,
        )

        assert client.timeout == 120.0

    def test_default_timeout(self):
        """Default timeout is set."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Default is 90.0 according to implementation
        assert client.timeout == 90.0

    @pytest.mark.asyncio
    async def test_timeout_error_is_caught_gracefully(self):
        """Timeout error is caught gracefully."""
        from crawler.services.ai_client_v2 import AIClientV2, ExtractionResultV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            timeout=1.0,
            max_retries=1,
        )

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert isinstance(result, ExtractionResultV2)
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_returns_error_result_on_timeout(self):
        """Returns error result on timeout."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=1,
        )

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>Test</html>",
                    source_url="https://example.com/",
                    product_type="whiskey",
                )

        assert result.success is False
        assert result.products == []
        assert result.error is not None


class TestContentPreprocessingIntegration:
    """Tests for content preprocessing integration."""

    @pytest.mark.asyncio
    async def test_calls_content_preprocessor_preprocess(self):
        """Calls ContentPreprocessor.preprocess()."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_get_preprocessor:
                mock_preprocessor = MagicMock()
                mock_preprocessor.preprocess.return_value = create_mock_preprocessed_content()
                mock_get_preprocessor.return_value = mock_preprocessor

                await client.extract(
                    content=SAMPLE_HTML_CONTENT,
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

                mock_preprocessor.preprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_url_for_structure_detection(self):
        """Passes URL for structure detection."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_get_preprocessor:
                mock_preprocessor = MagicMock()
                mock_preprocessor.preprocess.return_value = create_mock_preprocessed_content()
                mock_get_preprocessor.return_value = mock_preprocessor

                await client.extract(
                    content=SAMPLE_HTML_CONTENT,
                    source_url="https://example.com/products/whiskey",
                    product_type="whiskey",
                )

                # Check that URL was passed to preprocess
                call_args = mock_preprocessor.preprocess.call_args
                assert call_args.kwargs.get('url') == "https://example.com/products/whiskey"

    @pytest.mark.asyncio
    async def test_uses_preprocessed_content_in_request(self):
        """Uses preprocessed content in request."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        preprocessed_text = "Preprocessed: Ardbeg 10 Year Old whisky details"

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_get_preprocessor:
                mock_preprocessor = MagicMock()
                mock_preprocessor.preprocess.return_value = create_mock_preprocessed_content(
                    content=preprocessed_text
                )
                mock_get_preprocessor.return_value = mock_preprocessor

                await client.extract(
                    content=SAMPLE_HTML_CONTENT,
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

                # Check that post was called with preprocessed content
                post_call_args = mock_client.post.call_args
                request_json = post_call_args.kwargs.get('json', {})
                assert request_json["source_data"]["content"] == preprocessed_text

    @pytest.mark.asyncio
    async def test_handles_preprocessing_failure_gracefully(self):
        """Handles preprocessing failure gracefully."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_get_preprocessor:
            mock_preprocessor = MagicMock()
            mock_preprocessor.preprocess.side_effect = Exception("Preprocessing failed")
            mock_get_preprocessor.return_value = mock_preprocessor

            # Should not raise, should return error result
            result = await client.extract(
                content=SAMPLE_HTML_CONTENT,
                source_url="https://example.com/product",
                product_type="whiskey",
            )

            # Should return a result with error
            assert result is not None
            assert result.success is False
            assert "Preprocessing" in result.error or "Unexpected" in result.error


class TestConfigurationTests:
    """Tests for AIClientV2 configuration."""

    def test_custom_base_url_override(self):
        """Custom base_url override."""
        from crawler.services.ai_client_v2 import AIClientV2

        custom_url = "http://custom-ai:9000"
        client = AIClientV2(base_url=custom_url, api_key="test-key")

        assert client.base_url == custom_url

    def test_custom_timeout_override(self):
        """Custom timeout override."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            timeout=180.0,
        )

        assert client.timeout == 180.0

    def test_custom_max_retries_override(self):
        """Custom max_retries override."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_retries=5,
        )

        assert client.max_retries == 5

    def test_custom_max_tokens_override(self):
        """Custom max_tokens override."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(
            base_url="http://test:8000",
            api_key="test-key",
            max_tokens=8000,
        )

        assert client.max_tokens == 8000

    def test_headers_include_bearer_token(self):
        """Headers include Bearer token."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="my-secret-key")
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my-secret-key"

    def test_headers_include_content_type(self):
        """Headers include Content-Type."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        headers = client._get_headers()

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_headers_include_accept(self):
        """Headers include Accept."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")
        headers = client._get_headers()

        assert "Accept" in headers
        assert headers["Accept"] == "application/json"

    def test_headers_with_empty_api_key_still_works(self):
        """Headers are valid even with empty API key parameter."""
        from crawler.services.ai_client_v2 import AIClientV2

        # Note: When api_key="" is passed but settings has a token,
        # the implementation may still use the settings token.
        # This test verifies headers are always valid regardless.
        client = AIClientV2(base_url="http://test:8000", api_key="")
        headers = client._get_headers()

        # Required headers are always present
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "Accept" in headers

    def test_base_url_trailing_slash_stripped(self):
        """Base URL trailing slash is stripped."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000/", api_key="test-key")

        assert not client.base_url.endswith("/")
        assert client.base_url == "http://test:8000"

    def test_extract_endpoint_path(self):
        """Extract endpoint path is correct."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        assert client.extract_endpoint == "http://test:8000/api/v2/extract/"


@pytest.mark.asyncio
class TestExtractMethod:
    """Tests for the main extract() async method."""

    async def test_extract_success_full_flow(self):
        """Successful extraction returns ExtractionResultV2."""
        from crawler.services.ai_client_v2 import AIClientV2, ExtractionResultV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                result = await client.extract(
                    content="<html>...</html>",
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

        assert isinstance(result, ExtractionResultV2)
        assert result.success is True
        assert len(result.products) == 1

    async def test_extract_sends_request_to_correct_endpoint(self):
        """Extract sends request to correct endpoint."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                await client.extract(
                    content="<html>...</html>",
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

                # Verify correct endpoint was called
                post_call_args = mock_client.post.call_args
                called_url = post_call_args.args[0] if post_call_args.args else post_call_args.kwargs.get('url')
                assert "/api/v2/extract/" in called_url

    async def test_extract_handles_multi_product_detection(self):
        """Extract handles multi-product detection."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_MULTI

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content(
                    content_type_value="structured_html"
                )

                result = await client.extract(
                    content="<html>Product list...</html>",
                    source_url="https://example.com/products/whiskey/",
                    product_type="whiskey",
                )

        assert result.success is True
        assert len(result.products) == 3
        assert result.is_list_page is True

    async def test_extract_with_empty_content_returns_error(self):
        """Extract with empty content returns error."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        result = await client.extract(
            content="",
            source_url="https://example.com/",
            product_type="whiskey",
        )

        assert result.success is False
        assert "Empty content" in result.error

    async def test_extract_with_product_category(self):
        """Extract with product_category hint."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content()

                await client.extract(
                    content="<html>...</html>",
                    source_url="https://example.com/product",
                    product_type="whiskey",
                    product_category="bourbon",
                )

                # Verify product_category was included
                post_call_args = mock_client.post.call_args
                request_json = post_call_args.kwargs.get('json', {})
                assert request_json.get("product_category") == "bourbon"


class TestGetAIClientV2Factory:
    """Tests for get_ai_client_v2() factory function."""

    def teardown_method(self, method):
        """Reset singleton after each test."""
        from crawler.services.ai_client_v2 import reset_ai_client_v2
        reset_ai_client_v2()

    def test_get_ai_client_v2_returns_instance(self):
        """get_ai_client_v2() returns AIClientV2 instance."""
        from crawler.services.ai_client_v2 import get_ai_client_v2, AIClientV2

        client = get_ai_client_v2()

        assert isinstance(client, AIClientV2)

    def test_get_ai_client_v2_returns_singleton(self):
        """get_ai_client_v2() returns the same instance."""
        from crawler.services.ai_client_v2 import get_ai_client_v2

        client1 = get_ai_client_v2()
        client2 = get_ai_client_v2()

        assert client1 is client2

    def test_reset_ai_client_v2_clears_singleton(self):
        """reset_ai_client_v2() clears the singleton."""
        from crawler.services.ai_client_v2 import get_ai_client_v2, reset_ai_client_v2

        client1 = get_ai_client_v2()
        reset_ai_client_v2()
        client2 = get_ai_client_v2()

        assert client1 is not client2


class TestHealthCheck:
    """Tests for AIClientV2.health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self):
        """health_check() returns True on success."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_failure(self):
        """health_check() returns False on failure."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value = mock_client

            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_non_200(self):
        """health_check() returns False on non-200 status."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 503

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_calls_correct_endpoint(self):
        """health_check() calls /health/ endpoint."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            await client.health_check()

            call_args = mock_client.get.call_args
            called_url = call_args.args[0] if call_args.args else call_args.kwargs.get('url')
            assert "/health/" in called_url


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_client_initialization_with_minimal_params(self):
        """Client initialization with minimal parameters."""
        from crawler.services.ai_client_v2 import AIClientV2

        # Should not raise with minimal valid params
        client = AIClientV2(base_url="http://test:8000", api_key="key")
        assert client is not None

    def test_parse_response_with_missing_fields(self):
        """_parse_response handles response with missing optional fields."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Response with minimal fields
        minimal_response = {
            "products": [
                {
                    "extracted_data": {"name": "Test"},
                    "product_type": "whiskey",
                    "confidence": 0.5,
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = minimal_response

        result = client._parse_response(mock_response)

        assert result.success is True
        assert len(result.products) == 1

    def test_parse_response_with_null_field_confidences(self):
        """_parse_response handles null field_confidences."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        response_data = {
            "products": [
                {
                    "extracted_data": {"name": "Test"},
                    "product_type": "whiskey",
                    "confidence": 0.5,
                    "field_confidences": None,
                }
            ],
            "extraction_summary": {},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        result = client._parse_response(mock_response)

        assert result.success is True
        # field_confidences should be empty dict when None
        assert result.products[0].field_confidences == {} or result.products[0].field_confidences is None

    @pytest.mark.asyncio
    async def test_extract_with_very_long_content(self):
        """Extract handles very long content via preprocessing."""
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Create very long content
        long_content = "<html><body>" + "<p>Content</p>" * 10000 + "</body></html>"

        with patch('crawler.services.ai_client_v2.httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = SUCCESS_RESPONSE_SINGLE

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch('crawler.services.ai_client_v2.get_content_preprocessor') as mock_preprocessor:
                mock_preprocessor.return_value.preprocess.return_value = create_mock_preprocessed_content(
                    content="Truncated content...",
                    truncated=True,
                )

                result = await client.extract(
                    content=long_content,
                    source_url="https://example.com/product",
                    product_type="whiskey",
                )

        assert result is not None
        assert result.success is True


class TestGetDefaultSchema:
    """Tests for _get_default_schema method."""

    @pytest.mark.django_db
    def test_get_default_schema_raises_error_when_db_fails(self):
        """_get_default_schema raises SchemaConfigurationError when database query fails."""
        from crawler.services.ai_client_v2 import AIClientV2, SchemaConfigurationError
        from crawler.models import FieldDefinition

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Patch FieldDefinition.objects.filter to simulate DB error
        with patch.object(FieldDefinition.objects, 'filter', side_effect=Exception("DB error")):
            with pytest.raises(SchemaConfigurationError) as exc_info:
                client._get_default_schema("whiskey")

        # Error message should be informative
        assert "Failed to load extraction schema" in str(exc_info.value)
        assert "whiskey" in str(exc_info.value)

    @pytest.mark.django_db
    def test_get_default_schema_raises_error_when_no_fields_found(self):
        """_get_default_schema raises SchemaConfigurationError when no FieldDefinition entries exist."""
        from crawler.services.ai_client_v2 import AIClientV2, SchemaConfigurationError

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # No FieldDefinition entries in test DB
        with pytest.raises(SchemaConfigurationError) as exc_info:
            client._get_default_schema("whiskey")

        # Error message should guide user to load fixtures
        assert "No FieldDefinition entries found" in str(exc_info.value)
        assert "base_fields.json" in str(exc_info.value)

    @pytest.mark.django_db
    def test_get_default_schema_includes_common_fields(self):
        """_get_default_schema returns full schema dicts when FieldDefinition entries exist."""
        from crawler.services.ai_client_v2 import AIClientV2
        from crawler.models import FieldDefinition

        # Create test FieldDefinition entries (shared fields with null product_type_config)
        test_fields = ["name", "brand", "description", "abv", "nose_description"]
        for field_name in test_fields:
            FieldDefinition.objects.create(
                field_name=field_name,
                display_name=field_name.replace("_", " ").title(),
                field_type="text",
                description=f"Description for {field_name}",
                is_active=True,
                product_type_config=None,  # Shared field
            )

        client = AIClientV2(base_url="http://test:8000", api_key="test-key")

        # Get schema from database
        schema = client._get_default_schema("whiskey")

        # Schema should be a list of dicts (not just field names)
        assert isinstance(schema, list)
        assert len(schema) == len(test_fields)
        assert all(isinstance(item, dict) for item in schema)

        # Extract field names from schema dicts
        schema_field_names = [item["name"] for item in schema]

        # Common fields should be present
        assert "name" in schema_field_names
        assert "brand" in schema_field_names
        assert "nose_description" in schema_field_names

        # Each schema item should have required keys
        for item in schema:
            assert "name" in item
            assert "type" in item
            assert "description" in item
