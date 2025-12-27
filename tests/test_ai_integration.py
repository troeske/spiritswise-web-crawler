"""
Tests for AI Enhancement Service Integration.

Task Group 7: AI Enhancement Service Integration
These tests verify the AI Enhancement API client and content processing pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestAIEnhancementClientRequestFormatting:
    """Tests for AI Enhancement API client request formatting."""

    @pytest.mark.asyncio
    async def test_formats_request_with_content_url_and_hint(self):
        """
        API client formats request with content, source_url, and product_type_hint.

        Request format: { content, source_url, product_type_hint }
        """
        from crawler.services.ai_client import AIEnhancementClient

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="test-api-key",
        )

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "product_type": "whiskey",
            "confidence": 0.95,
            "extracted_data": {
                "name": "Glenfiddich 18",
                "brand": "Glenfiddich",
                "abv": 40.0,
            },
            "enrichment": {
                "tasting_notes": "Rich and fruity",
            },
            "processing_time_ms": 1200,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.enhance_from_crawler(
                content="<html><body>Glenfiddich 18 Year Old Single Malt</body></html>",
                source_url="https://whisky-shop.com/glenfiddich-18",
                product_type_hint="whiskey",
            )

            # Verify the request was made with correct format
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            # Check endpoint
            endpoint = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
            assert "/api/v1/enhance/from-crawler/" in endpoint

            # Check request body format
            json_payload = call_args.kwargs.get("json", {})
            assert "content" in json_payload
            assert "source_url" in json_payload
            assert "product_type_hint" in json_payload
            assert json_payload["product_type_hint"] == "whiskey"
            assert json_payload["source_url"] == "https://whisky-shop.com/glenfiddich-18"

            # Check authorization header
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-api-key"

    @pytest.mark.asyncio
    async def test_uses_bearer_token_authentication(self):
        """API client uses Bearer token for authentication."""
        from crawler.services.ai_client import AIEnhancementClient

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="secret-token-123",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"product_type": "whiskey", "confidence": 0.9}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.enhance_from_crawler(
                content="Test content",
                source_url="https://example.com",
            )

            call_args = mock_client.post.call_args
            headers = call_args.kwargs.get("headers", {})

            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-token-123"


class TestAIEnhancementClientResponseParsing:
    """Tests for response parsing and DiscoveredProduct update."""

    @pytest.mark.asyncio
    async def test_parses_response_into_enhancement_result(self):
        """Response is parsed into EnhancementResult with extracted and enriched data."""
        from crawler.services.ai_client import AIEnhancementClient

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="test-key",
        )

        # Full response from AI service
        api_response = {
            "product_type": "whiskey",
            "confidence": 0.95,
            "extracted_data": {
                "name": "Highland Park 12",
                "brand": "Highland Park",
                "abv": 43.0,
                "volume_ml": 700,
                "age_statement": 12,
                "distillery": "Highland Park",
                "region": "Islands",
            },
            "enrichment": {
                "tasting_notes": "Heather honey, peat smoke, and dark chocolate",
                "flavor_profile": ["smoky", "sweet", "complex"],
                "food_pairings": ["smoked salmon", "dark chocolate"],
                "serving_suggestion": "Neat or with a splash of water",
            },
            "processing_time_ms": 1500,
            "source": "crawler",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.enhance_from_crawler(
                content="Highland Park 12 Year Old Single Malt",
                source_url="https://shop.com/highland-park-12",
                product_type_hint="whiskey",
            )

            # Verify result structure
            assert result.success is True
            assert result.product_type == "whiskey"
            assert result.confidence == 0.95

            # Verify extracted data
            assert result.extracted_data["name"] == "Highland Park 12"
            assert result.extracted_data["brand"] == "Highland Park"
            assert result.extracted_data["abv"] == 43.0

            # Verify enrichment data
            assert "tasting_notes" in result.enrichment
            assert "flavor_profile" in result.enrichment
            assert result.processing_time_ms == 1500


class TestAIEnhancementClientErrorHandling:
    """Tests for error handling on API failures."""

    @pytest.mark.asyncio
    async def test_handles_api_error_response_gracefully(self):
        """API errors return EnhancementResult with success=False and error message."""
        from crawler.services.ai_client import AIEnhancementClient

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="test-key",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.enhance_from_crawler(
                content="Test content",
                source_url="https://example.com",
            )

            # Verify graceful error handling
            assert result.success is False
            assert result.error is not None
            assert "500" in result.error or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_connection_timeout(self):
        """Connection timeouts are handled gracefully with appropriate error message."""
        from crawler.services.ai_client import AIEnhancementClient
        import httpx

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="test-key",
            timeout=5.0,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
            mock_client_class.return_value = mock_client

            result = await client.enhance_from_crawler(
                content="Test content",
                source_url="https://example.com",
            )

            # Verify timeout is handled
            assert result.success is False
            assert result.error is not None
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self):
        """Invalid JSON responses are handled gracefully."""
        from crawler.services.ai_client import AIEnhancementClient

        client = AIEnhancementClient(
            base_url="https://ai-service.example.com",
            api_key="test-key",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Not valid JSON"
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.enhance_from_crawler(
                content="Test content",
                source_url="https://example.com",
            )

            # Verify JSON parse error is handled
            assert result.success is False
            assert result.error is not None
