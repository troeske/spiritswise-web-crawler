"""
AI Enhancement Service API Client.

Task 7.2: Implements async httpx client for /api/v1/enhance/from-crawler/ endpoint.

Features:
- Async httpx client with configurable timeout
- Bearer token authentication
- Request format: { content, source_url, product_type_hint }
- Graceful error handling for API failures
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class EnhancementResult:
    """Result of AI Enhancement API call."""

    success: bool
    product_type: str = ""
    confidence: float = 0.0
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    enrichment: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    error: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None


class AIEnhancementClient:
    """
    Async HTTP client for the AI Enhancement Service.

    Calls the /api/v1/enhance/from-crawler/ endpoint to extract
    and enrich product data from crawled content.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize the AI Enhancement client.

        Args:
            base_url: AI Enhancement Service URL (defaults to settings.AI_ENHANCEMENT_SERVICE_URL)
            api_key: API key for authentication (defaults to settings.AI_ENHANCEMENT_SERVICE_TOKEN)
            timeout: Request timeout in seconds (default 60s)
        """
        self.base_url = base_url or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_URL", "http://localhost:8000"
        )
        self.api_key = api_key or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_TOKEN", ""
        )
        self.timeout = timeout

        # Ensure base URL doesn't have trailing slash
        self.base_url = self.base_url.rstrip("/")

        # Endpoint path
        self.enhance_endpoint = f"{self.base_url}/api/v1/enhance/from-crawler/"

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def enhance_from_crawler(
        self,
        content: str,
        source_url: str,
        product_type_hint: Optional[str] = None,
    ) -> EnhancementResult:
        """
        Send crawled content to AI Enhancement Service for extraction and enrichment.

        Args:
            content: Raw HTML or text content from crawler
            source_url: URL where content was crawled from
            product_type_hint: Optional hint for product type (whiskey, port_wine, etc.)

        Returns:
            EnhancementResult with extracted and enriched product data
        """
        # Build request payload
        payload = {
            "content": content,
            "source_url": source_url,
        }

        if product_type_hint:
            payload["product_type_hint"] = product_type_hint

        headers = self._get_headers()

        logger.debug(
            f"Calling AI Enhancement Service for {source_url} "
            f"(content length: {len(content)} chars)"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.enhance_endpoint,
                    json=payload,
                    headers=headers,
                )

                return self._parse_response(response)

        except httpx.TimeoutException as e:
            logger.error(f"AI Enhancement Service timeout: {e}")
            return EnhancementResult(
                success=False,
                error=f"Request timeout after {self.timeout}s",
            )

        except httpx.ConnectError as e:
            logger.error(f"AI Enhancement Service connection error: {e}")
            return EnhancementResult(
                success=False,
                error=f"Connection error: {str(e)}",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"AI Enhancement Service HTTP error: {e}")
            return EnhancementResult(
                success=False,
                error=f"HTTP error {e.response.status_code}: {str(e)}",
            )

        except Exception as e:
            logger.exception(f"Unexpected error calling AI Enhancement Service: {e}")
            return EnhancementResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    def _parse_response(self, response: httpx.Response) -> EnhancementResult:
        """
        Parse API response into EnhancementResult.

        Args:
            response: httpx Response object

        Returns:
            EnhancementResult with parsed data or error
        """
        # Check HTTP status
        if response.status_code != 200:
            error_msg = f"API returned status {response.status_code}"

            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = f"{error_msg}: {error_data['error']}"
            except Exception:
                error_msg = f"{error_msg}: {response.text[:200]}"

            logger.warning(error_msg)
            return EnhancementResult(
                success=False,
                error=error_msg,
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to parse AI service response: {e}")
            return EnhancementResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
            )

        # Extract response fields
        product_type = data.get("product_type", "unknown")
        confidence = data.get("confidence", 0.0)
        extracted_data = data.get("extracted_data", {})
        enrichment = data.get("enrichment", {})
        processing_time_ms = data.get("processing_time_ms", 0.0)

        # Check for error in response body
        if "error" in data:
            return EnhancementResult(
                success=False,
                error=data["error"],
                product_type=product_type,
            )

        logger.info(
            f"AI Enhancement successful: {product_type} "
            f"(confidence: {confidence:.2f}, time: {processing_time_ms:.0f}ms)"
        )

        return EnhancementResult(
            success=True,
            product_type=product_type,
            confidence=confidence,
            extracted_data=extracted_data,
            enrichment=enrichment,
            processing_time_ms=processing_time_ms,
        )

    async def health_check(self) -> bool:
        """
        Check if AI Enhancement Service is available.

        Returns:
            True if service responds, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/health/",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"AI Enhancement Service health check failed: {e}")
            return False


def get_ai_client() -> AIEnhancementClient:
    """
    Factory function to get configured AI Enhancement client.

    Returns:
        AIEnhancementClient configured from Django settings
    """
    return AIEnhancementClient(
        base_url=getattr(settings, "AI_ENHANCEMENT_SERVICE_URL", None),
        api_key=getattr(settings, "AI_ENHANCEMENT_SERVICE_TOKEN", None),
        timeout=60.0,
    )
