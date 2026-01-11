"""
AI Service V2 API Client.

Phase 3 of V2 Architecture: Implements async httpx client for /api/v2/extract/ endpoint
with integrated content preprocessing for token cost reduction.

Features:
- Async httpx client with configurable timeout
- Bearer token authentication
- Content preprocessing integration (93% token savings)
- Schema-driven extraction requests
- Retry with exponential backoff
- Graceful error handling for API failures
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from django.conf import settings
from django.db.models import Q

from crawler.services.content_preprocessor import (
    ContentPreprocessor,
    ContentType,
    PreprocessedContent,
    get_content_preprocessor,
)

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """Error from AI Client V2 operations."""

    pass


@dataclass
class ExtractedProductV2:
    """Single extracted product from V2 API."""

    extracted_data: Dict[str, Any] = field(default_factory=dict)
    product_type: str = ""
    confidence: float = 0.0
    field_confidences: Dict[str, float] = field(default_factory=dict)


@dataclass
class EnhancementResult:
    """
    V1-compatible result format for backward compatibility with content_processor.py.

    V1→V2 Migration: This class provides backward compatibility with code
    that expects the V1 AIEnhancementClient result format.
    """

    success: bool
    product_type: str = ""
    confidence: float = 0.0
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    enrichment: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    error: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    field_confidences: Optional[Dict[str, float]] = None


@dataclass
class ExtractionResultV2:
    """Result of AI V2 extraction API call."""

    success: bool
    products: List[ExtractedProductV2] = field(default_factory=list)
    extraction_summary: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    error: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    is_list_page: bool = False


class AIClientV2:
    """
    Async HTTP client for AI Service V2 extraction endpoint.

    Features:
    - Content preprocessing for token cost reduction
    - Schema-driven extraction requests
    - Retry with exponential backoff
    - Configurable timeout
    """

    DEFAULT_TIMEOUT = 90.0
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds
    RETRY_CODES = {500, 502, 503, 504}  # HTTP codes to retry
    DEFAULT_MAX_TOKENS = 16000

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        """
        Initialize the AI Client V2.

        Args:
            base_url: AI Service URL (defaults to settings.AI_ENHANCEMENT_SERVICE_URL)
            api_key: API key for authentication (defaults to settings.AI_ENHANCEMENT_SERVICE_TOKEN)
            timeout: Request timeout in seconds (default 90s)
            max_retries: Maximum retry attempts for transient failures
            max_tokens: Maximum tokens for content preprocessing
        """
        self.base_url = base_url or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_URL", "http://localhost:8000"
        )
        self.api_key = api_key or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_TOKEN", ""
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens

        # Ensure base URL doesn't have trailing slash
        self.base_url = self.base_url.rstrip("/")

        # Endpoint path for V2 extraction
        self.extract_endpoint = f"{self.base_url}/api/v2/extract/"

        logger.debug(
            "AIClientV2 initialized: base_url=%s, timeout=%.1fs, max_retries=%d",
            self.base_url,
            self.timeout,
            self.max_retries,
        )

    async def extract(
        self,
        content: str,
        source_url: str = "",
        product_type: str = "whiskey",
        product_category: Optional[str] = None,
        extraction_schema: Optional[List[str]] = None,
        detect_multi_product: bool = False,
    ) -> ExtractionResultV2:
        """
        Extract product data from content using AI Service V2.

        Args:
            content: Raw HTML content to process
            source_url: URL where content was fetched
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint (bourbon, tawny, etc.)
            extraction_schema: Optional list of fields to extract (defaults to all)
            detect_multi_product: Whether to detect if this is a multi-product/list page

        Returns:
            ExtractionResultV2 with extracted products or error
        """
        if not content:
            return ExtractionResultV2(
                success=False,
                error="Empty content provided",
            )

        logger.debug(
            "Starting V2 extraction for %s (type=%s, content_length=%d)",
            source_url,
            product_type,
            len(content),
        )

        try:
            # Preprocess content to reduce token usage
            preprocessed = self._preprocess_content(content, source_url)

            logger.debug(
                "Content preprocessed: type=%s, original=%d, preprocessed=%d, tokens=%d",
                preprocessed.content_type.value,
                preprocessed.original_length,
                len(preprocessed.content),
                preprocessed.token_estimate,
            )

            # Get extraction schema (default if not provided) - use async version
            schema = extraction_schema or await self._aget_default_schema(product_type)

            # Build request payload
            payload = self._build_request(
                preprocessed=preprocessed,
                source_url=source_url,
                product_type=product_type,
                product_category=product_category,
                extraction_schema=schema,
            )

            # Send request with retry logic
            response = await self._send_request(payload)

            # Parse response
            return self._parse_response(response)

        except AIClientError as e:
            logger.error("AI Client V2 error for %s: %s", source_url, str(e))
            return ExtractionResultV2(
                success=False,
                error=str(e),
            )

        except Exception as e:
            logger.exception("Unexpected error in V2 extraction for %s: %s", source_url, str(e))
            return ExtractionResultV2(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    def _preprocess_content(self, content: str, url: str) -> PreprocessedContent:
        """
        Preprocess content to reduce token usage.

        Uses the ContentPreprocessor to clean and optimize content
        for AI extraction, achieving approximately 93% token savings.

        Args:
            content: Raw HTML content
            url: Source URL for list page detection heuristics

        Returns:
            PreprocessedContent with optimized content
        """
        preprocessor = get_content_preprocessor(self.max_tokens)
        return preprocessor.preprocess(content, url=url)

    def _build_request(
        self,
        preprocessed: PreprocessedContent,
        source_url: str,
        product_type: str,
        product_category: Optional[str],
        extraction_schema: List[str],
    ) -> Dict[str, Any]:
        """
        Build V2 API request payload.

        Args:
            preprocessed: Preprocessed content
            source_url: URL where content was fetched
            product_type: Product type for extraction
            product_category: Optional category hint
            extraction_schema: Fields to extract

        Returns:
            Request payload dictionary
        """
        payload = {
            "source_data": {
                "content": preprocessed.content,
                "source_url": source_url,
                "type": preprocessed.content_type.value,
            },
            "product_type": product_type,
            "extraction_schema": extraction_schema,
            "options": {
                "detect_multi_product": True,
                "max_products": 10,
            },
        }

        if product_category:
            payload["product_category"] = product_category

        # Include headings if available for context
        if preprocessed.headings:
            payload["source_data"]["headings"] = preprocessed.headings

        # Include truncation flag if content was truncated
        if preprocessed.truncated:
            payload["source_data"]["truncated"] = True

        return payload

    def _get_headers(self) -> Dict[str, str]:
        """
        Build request headers with Bearer token authentication.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def _send_request(self, payload: Dict[str, Any]) -> httpx.Response:
        """
        Send request with retry logic and exponential backoff.

        Args:
            payload: Request payload

        Returns:
            httpx Response object

        Raises:
            AIClientError: If all retries are exhausted
        """
        last_error: Optional[str] = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.extract_endpoint,
                        json=payload,
                        headers=self._get_headers(),
                    )

                    # Return immediately for non-retryable status codes
                    if response.status_code not in self.RETRY_CODES:
                        return response

                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        "Retryable error on attempt %d/%d: %s",
                        attempt + 1,
                        self.max_retries,
                        last_error,
                    )

            except httpx.TimeoutException as e:
                last_error = f"Request timeout after {self.timeout}s: {str(e)}"
                logger.warning(
                    "Timeout on attempt %d/%d: %s",
                    attempt + 1,
                    self.max_retries,
                    last_error,
                )

            except httpx.ConnectError as e:
                last_error = f"Connection error: {str(e)}"
                logger.warning(
                    "Connection error on attempt %d/%d: %s",
                    attempt + 1,
                    self.max_retries,
                    last_error,
                )

            # Apply exponential backoff before retry
            if attempt < self.max_retries - 1:
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.debug("Waiting %.1fs before retry %d", delay, attempt + 2)
                await asyncio.sleep(delay)

        raise AIClientError(f"Max retries ({self.max_retries}) exceeded: {last_error}")

    def _parse_response(self, response: httpx.Response) -> ExtractionResultV2:
        """
        Parse V2 API response into ExtractionResultV2.

        Args:
            response: httpx Response object

        Returns:
            ExtractionResultV2 with parsed data or error
        """
        # Handle non-200 responses
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"

            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = f"{error_msg}: {error_data['error']}"
                elif "detail" in error_data:
                    error_msg = f"{error_msg}: {error_data['detail']}"
            except Exception:
                error_msg = f"{error_msg}: {response.text[:200]}"

            logger.warning("V2 extraction failed: %s", error_msg)
            return ExtractionResultV2(
                success=False,
                error=error_msg,
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception as e:
            logger.error("Failed to parse V2 API response: %s", str(e))
            return ExtractionResultV2(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
            )

        # Check for error in response body (only if error is non-null)
        if data.get("error"):
            return ExtractionResultV2(
                success=False,
                error=data["error"],
            )

        # Parse products from response
        products = []
        for product_data in data.get("products", []):
            extracted_data = product_data.get("extracted_data", {})
            api_confidence = product_data.get("confidence", 0.0)

            # If API doesn't return confidence, calculate based on extracted fields
            if api_confidence == 0.0 and extracted_data:
                api_confidence = self._calculate_field_confidence(extracted_data)

            product = ExtractedProductV2(
                extracted_data=extracted_data,
                product_type=product_data.get("product_type", ""),
                confidence=api_confidence,
                field_confidences=product_data.get("field_confidences", {}),
            )
            products.append(product)

        # Extract metadata
        processing_time_ms = data.get("processing_time_ms", 0.0)
        token_usage = data.get("token_usage")
        extraction_summary = data.get("extraction_summary", {})
        is_list_page = data.get("is_list_page", False)

        logger.info(
            "V2 extraction successful: %d products extracted (time=%.0fms, list_page=%s)",
            len(products),
            processing_time_ms,
            is_list_page,
        )

        return ExtractionResultV2(
            success=True,
            products=products,
            extraction_summary=extraction_summary,
            processing_time_ms=processing_time_ms,
            token_usage=token_usage,
            is_list_page=is_list_page,
        )

    def _calculate_field_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on extracted field quality.

        Used when the AI API doesn't return explicit confidence scores.
        Scores are based on presence and quality of key fields.

        Args:
            extracted_data: Dictionary of extracted fields

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Required fields - must have at minimum
        required_fields = ["name"]
        # Important fields that significantly boost confidence
        important_fields = ["brand", "description", "abv", "country", "region"]
        # Optional fields that add some confidence
        optional_fields = ["volume_ml", "age_statement", "price", "distillery", "producer"]

        score = 0.0

        # Check required fields (50% of score)
        for field in required_fields:
            value = extracted_data.get(field)
            if value and str(value).strip() and str(value).lower() not in ["unknown", "n/a", "none"]:
                score += 0.5 / len(required_fields)

        # Check important fields (40% of score)
        important_count = 0
        for field in important_fields:
            value = extracted_data.get(field)
            if value and str(value).strip() and str(value).lower() not in ["unknown", "n/a", "none"]:
                important_count += 1
        if important_fields:
            score += 0.4 * (important_count / len(important_fields))

        # Check optional fields (10% of score)
        optional_count = 0
        for field in optional_fields:
            value = extracted_data.get(field)
            if value and str(value).strip():
                optional_count += 1
        if optional_fields:
            score += 0.1 * (optional_count / len(optional_fields))

        # Minimum confidence for having a valid name
        if extracted_data.get("name") and str(extracted_data["name"]).strip():
            score = max(score, 0.35)  # Ensure at least 0.35 if name exists

        return round(score, 2)

    def _get_default_schema(self, product_type: str) -> List[str]:
        """
        Get default extraction schema from FieldDefinition config.

        Retrieves all active field names for the specified product type
        from the database configuration, including shared fields.

        Args:
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            List of field names to extract
        """
        try:
            from crawler.models import FieldDefinition

            # Get fields for this product type OR shared fields (null product_type_config)
            fields = FieldDefinition.objects.filter(
                is_active=True
            ).filter(
                Q(product_type_config__isnull=True) |
                Q(product_type_config__product_type=product_type)
            )

            field_names = list(fields.values_list("field_name", flat=True).distinct())

            if field_names:
                logger.debug(
                    "Retrieved %d fields from FieldDefinition for %s",
                    len(field_names),
                    product_type,
                )
                return field_names

        except Exception as e:
            logger.warning(
                "Failed to retrieve FieldDefinition for %s: %s, using fallback",
                product_type,
                str(e),
            )

        # Fallback to common fields if database lookup fails
        fallback_fields = [
            "name",
            "brand",
            "description",
            "abv",
            "volume_ml",
            "age_statement",
            "price",
            "country",
            "region",
            # Tasting profile fields - critical for complete product data
            "nose_description",
            "palate_description",
            "finish_description",
            "primary_aromas",
            "palate_flavors",
        ]
        logger.debug("Using fallback schema with %d fields", len(fallback_fields))
        return fallback_fields

    async def _aget_default_schema(self, product_type: str) -> List[str]:
        """
        Async-safe version of _get_default_schema.

        Uses sync_to_async to wrap database access for async contexts.
        """
        from asgiref.sync import sync_to_async
        return await sync_to_async(self._get_default_schema, thread_sensitive=True)(product_type)

    async def enhance_from_crawler(
        self,
        content: str,
        source_url: str = "",
        product_type_hint: str = "whiskey",
    ) -> EnhancementResult:
        """
        V1-compatible method for backward compatibility with content_processor.py.

        Wraps the V2 extract() method and converts the result to V1's EnhancementResult format.

        V1→V2 Migration: This method provides a drop-in replacement for the V1
        AIEnhancementClient.enhance_from_crawler() method.

        Args:
            content: Raw HTML or text content to process
            source_url: URL where content was fetched
            product_type_hint: Product type hint (whiskey, port_wine, etc.)

        Returns:
            EnhancementResult in V1-compatible format
        """
        # Call V2 extract method
        v2_result = await self.extract(
            content=content,
            source_url=source_url,
            product_type=product_type_hint,
        )

        # Convert V2 result to V1 EnhancementResult format
        if not v2_result.success:
            return EnhancementResult(
                success=False,
                error=v2_result.error,
                processing_time_ms=v2_result.processing_time_ms,
                token_usage=v2_result.token_usage,
            )

        # Get first product if available (V1 only supported single product)
        if v2_result.products:
            first_product = v2_result.products[0]
            return EnhancementResult(
                success=True,
                product_type=first_product.product_type or product_type_hint,
                confidence=first_product.confidence,
                extracted_data=first_product.extracted_data,
                enrichment={},  # V2 doesn't do inline enrichment
                processing_time_ms=v2_result.processing_time_ms,
                token_usage=v2_result.token_usage,
                field_confidences=first_product.field_confidences,
            )
        else:
            return EnhancementResult(
                success=False,
                error="No products extracted from content",
                processing_time_ms=v2_result.processing_time_ms,
                token_usage=v2_result.token_usage,
            )

    async def health_check(self) -> bool:
        """
        Check if AI Service V2 is available.

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
            logger.warning("AI Service V2 health check failed: %s", str(e))
            return False


# Singleton instance management
_client_instance: Optional[AIClientV2] = None


def get_ai_client_v2(**kwargs) -> AIClientV2:
    """
    Get or create AIClientV2 singleton.

    Args:
        **kwargs: Configuration overrides passed to AIClientV2 constructor
                  (only used on first call when creating instance)

    Returns:
        AIClientV2 singleton instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = AIClientV2(**kwargs)
    return _client_instance


def reset_ai_client_v2() -> None:
    """
    Reset the singleton instance.

    Useful for testing or reconfiguration.
    """
    global _client_instance
    _client_instance = None
