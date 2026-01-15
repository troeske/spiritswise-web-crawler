"""
AI Service V2 API Client.

Phase 3 of V2 Architecture: Implements async httpx client for /api/v2/extract/ endpoint
with integrated content preprocessing for token cost reduction.

Features:
- Async httpx client with configurable timeout
- Bearer token authentication
- Content preprocessing integration (93% token savings)
- Schema-driven extraction requests with full field definitions
- Retry with exponential backoff
- Graceful error handling for API failures
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

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

# Extended schema for multi-product extraction (list pages)
# Captures core identification + taste profiles available on listicles
# With GPT-4.1's 32K output token limit, we can include more fields
# Full 76-field schema generates ~1000+ tokens per product
# Extended schema (~30 fields) generates ~500-600 tokens per product
MULTI_PRODUCT_SKELETON_SCHEMA = [
    # Core identification fields (required)
    "name",
    "brand",
    "description",
    # Key product attributes
    "abv",
    "country",
    "region",
    "category",
    "style",
    # Sizing and age
    "volume_ml",
    "age_statement",
    "vintage",
    # Awards (important for competition pages)
    "awards",
    # Producer info
    "producer",
    "distillery",
    # Detail page URL for follow-up extraction
    # Competition sites often have "View Details" links with more info
    "detail_url",
    # Production info
    "cask_type",
    # Taste profile descriptions (prose - source of truth for derived fields)
    # Many listicles include tasting notes that we should capture upfront
    "nose_description",
    "palate_description",
    "finish_description",
    "mouthfeel",
    # Taste profile arrays (extracted flavor notes)
    "primary_aromas",
    "palate_flavors",
    "finish_flavors",
    # Derived taste metrics (1-10 scales) - derived from prose descriptions
    "finish_length",  # derive_from: finish_description
    "warmth",  # derive_from: finish_description
    "dryness",  # derive_from: finish_description
    "flavor_intensity",
    "overall_balance",
    # Derived text fields - derived from finish_description
    "finish_evolution",  # derive_from: finish_description
    "final_notes",  # derive_from: finish_description
    # Price information (often included on listicles)
    "prices",
]

# Type alias for schema - can be list of field names (strings) or full schema dicts
SchemaType = Union[List[str], List[Dict[str, Any]]]


class AIClientError(Exception):
    """Error from AI Client V2 operations."""

    pass


class SchemaConfigurationError(AIClientError):
    """
    Error when extraction schema cannot be loaded from database.

    This error is raised when FieldDefinition lookup fails and indicates
    a critical configuration issue that should be visible in Sentry.
    """

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

    V1->V2 Migration: This class provides backward compatibility with code
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
    - Schema-driven extraction requests with full field definitions
    - Retry with exponential backoff
    - Configurable timeout
    """

    # Increased timeout to handle complex multi-product extractions with full 76-field schema
    # Server-side: nginx proxy_read_timeout 600s, gunicorn timeout 600s
    # Client needs to wait at least as long as the server timeout
    DEFAULT_TIMEOUT = 900.0  # 15 minutes to match VPS gunicorn/nginx/OpenAI timeouts
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
        extraction_schema: Optional[SchemaType] = None,
        detect_multi_product: bool = False,
    ) -> ExtractionResultV2:
        """
        Extract product data from content using AI Service V2.

        Args:
            content: Raw HTML content to process
            source_url: URL where content was fetched
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint (bourbon, tawny, etc.)
            extraction_schema: Optional schema to use - can be list of field names (strings)
                              or full schema dicts with descriptions. Defaults to full schema
                              from database.
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

            # Get extraction schema
            # For multi-product detection, use skeleton schema to stay under 16K output token limit
            # Full 76-field schema generates too many tokens for pages with 5+ products
            if extraction_schema:
                schema = extraction_schema
            elif detect_multi_product:
                schema = MULTI_PRODUCT_SKELETON_SCHEMA
                logger.info(
                    "Using skeleton schema (%d fields) for multi-product extraction",
                    len(schema),
                )
            else:
                schema = await self._aget_default_schema(product_type)

            # Ensure we have full schema with derive_from for the API
            # If schema is list of strings (field names only), load full definitions from database
            full_schema = None
            if schema and isinstance(schema[0], str):
                # Load full schema from database to get derive_from, descriptions, etc.
                try:
                    full_schema = await self._aget_default_schema(product_type)
                    logger.debug(
                        "Loaded full schema (%d fields) for field-name-only extraction schema",
                        len(full_schema),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to load full schema from database: %s. Proceeding with field names only.",
                        str(e),
                    )
            elif schema and isinstance(schema[0], dict):
                # Schema already contains full definitions
                full_schema = schema

            # Build request payload
            payload = self._build_request(
                preprocessed=preprocessed,
                source_url=source_url,
                product_type=product_type,
                product_category=product_category,
                extraction_schema=schema,
                full_schema=full_schema,
            )

            # Send request with retry logic
            response = await self._send_request(payload)

            # Parse response and validate enum fields
            return self._parse_response(response, schema)

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
        extraction_schema: SchemaType,
        full_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build V2 API request payload.

        Args:
            preprocessed: Preprocessed content
            source_url: URL where content was fetched
            product_type: Product type for extraction
            product_category: Optional category hint
            extraction_schema: Fields to extract - can be list of field names or full schema dicts
            full_schema: Full schema with derive_from info (optional, loaded from database)

        Returns:
            Request payload dictionary
        """
        # Convert schema dicts to field names for API
        # The VPS API expects extraction_schema to be a list of strings (field names)
        # If schema contains dicts, extract just the field names AND send full schema
        api_schema = extraction_schema

        if extraction_schema and isinstance(extraction_schema[0], dict):
            api_schema = [field.get("name") for field in extraction_schema if field.get("name")]
            # Use extraction_schema as full_schema if not already provided
            if full_schema is None:
                full_schema = extraction_schema
            logger.debug(
                "Converted %d schema dicts to field names for API, preserving full schema",
                len(api_schema),
            )

        payload = {
            "source_data": {
                "content": preprocessed.content,
                "source_url": source_url,
                "type": preprocessed.content_type.value,
            },
            "product_type": product_type,
            "extraction_schema": api_schema,
            "options": {
                "detect_multi_product": True,
                "max_products": 10,
            },
        }

        # Send full schema with derive_from info for proper derivation (REQUIRED by VPS API)
        if full_schema:
            payload["schema"] = full_schema
            logger.debug("Including full schema with derive_from for %d fields", len(full_schema))
        else:
            logger.warning(
                "No full schema available for request - VPS API may reject. "
                "Ensure schema is loaded from database for product_type=%s",
                product_type,
            )

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

    def _parse_response(
        self,
        response: httpx.Response,
        schema: Optional[SchemaType] = None,
    ) -> ExtractionResultV2:
        """
        Parse V2 API response into ExtractionResultV2.

        Args:
            response: httpx Response object
            schema: Optional extraction schema for enum validation.
                   If provided and contains allowed_values, enum fields
                   will be validated.

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

        # Check if schema has enum fields for validation
        # Only validate if schema is a list of dicts (full schema, not just field names)
        can_validate_enums = (
            schema
            and isinstance(schema, list)
            and len(schema) > 0
            and isinstance(schema[0], dict)
        )

        for product_data in data.get("products", []):
            extracted_data = product_data.get("extracted_data", {})
            api_confidence = product_data.get("confidence", 0.0)

            # Validate enum fields if full schema provided
            if can_validate_enums and extracted_data:
                validated_data, validation_warnings = self._validate_enum_fields(
                    extracted_data, schema
                )
                # Log warnings for invalid enum values (helpful for debugging)
                for warning in validation_warnings:
                    logger.warning("Enum validation: %s", warning)
                extracted_data = validated_data

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

    def _validate_enum_fields(
        self,
        response_data: Dict[str, Any],
        schema: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], List[str]]:
        """
        Validate AI response against schema enum constraints.

        Validates that fields with allowed_values (enum fields) contain valid values.
        Invalid values are set to None and warnings are generated for logging/debugging.
        Case-insensitive matching is used for string enums.

        Args:
            response_data: Dictionary of extracted field values from AI
            schema: List of schema dicts with field definitions

        Returns:
            Tuple of (validated_data, warnings):
            - validated_data: Copy of response_data with invalid enums set to None
            - warnings: List of warning messages for invalid values
        """
        validated = response_data.copy()
        warnings: List[str] = []

        # Build lookup of enum constraints: field_name -> allowed_values (lowercase)
        enum_constraints: Dict[str, List[str]] = {}
        for field_def in schema:
            field_name = field_def.get("name")
            allowed_values = field_def.get("allowed_values")
            if field_name and allowed_values and isinstance(allowed_values, list):
                # Store lowercase versions for case-insensitive matching
                enum_constraints[field_name] = [str(v).lower() for v in allowed_values]

        # Validate each field with enum constraints
        for field_name, allowed_lower in enum_constraints.items():
            value = validated.get(field_name)

            # Skip null/empty values - these are valid (field not extracted)
            if value is None or (isinstance(value, str) and not value.strip()):
                validated[field_name] = None
                continue

            # Normalize string value for comparison
            value_str = str(value).strip()
            value_lower = value_str.lower()

            if value_lower in allowed_lower:
                # Valid match - normalize to lowercase to ensure consistency
                validated[field_name] = value_lower
            else:
                # Invalid value - set to None and log warning
                warnings.append(
                    f"Invalid value '{value}' for enum field '{field_name}'. "
                    f"Expected one of: {[v for v in allowed_lower]}"
                )
                validated[field_name] = None

        return validated, warnings

    def _get_default_schema(self, product_type: str) -> List[Dict[str, Any]]:
        """
        Get full extraction schema from FieldDefinition config.

        Retrieves all active field definitions for the specified product type
        from the database configuration, including shared fields. Returns full
        schema dictionaries with descriptions, examples, derive_from relationships,
        and enum constraints - not just field names.

        This enables the AI service to understand field semantics and constraints
        for better extraction quality.

        Args:
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            List of schema dicts with full field definitions including:
            - name: Field name
            - type: Data type (string, integer, array, etc.)
            - description: Detailed description for AI extraction
            - examples: Sample values (if defined)
            - derive_from: Source field for derivation (if defined)
            - derive_instruction: Human-readable derivation instruction
            - allowed_values: Valid enum values (if defined)
            - enum_instruction: Constraint instruction for enums
            - item_schema: Schema for nested objects (if defined)
            - format_hint: Format specification (if defined)

        Raises:
            SchemaConfigurationError: If schema cannot be loaded from database.
                This error is captured by Sentry for monitoring.
        """
        from crawler.models import FieldDefinition

        try:
            # Use the FieldDefinition.get_schema_for_product_type() classmethod
            # which returns full schema dicts with descriptions, not just field names
            schema = FieldDefinition.get_schema_for_product_type(product_type)

            if schema:
                logger.debug(
                    "Retrieved %d field definitions from FieldDefinition for %s",
                    len(schema),
                    product_type,
                )
                return schema

            # No fields found - this is a configuration error
            error_msg = (
                f"No FieldDefinition entries found for product_type '{product_type}'. "
                "Ensure base_fields.json fixture is loaded: "
                "python manage.py loaddata crawler/fixtures/base_fields.json"
            )
            raise SchemaConfigurationError(error_msg)

        except SchemaConfigurationError:
            # Re-raise our own exception
            raise

        except Exception as e:
            # Database or other error - wrap and report to Sentry
            error_msg = (
                f"Failed to load extraction schema for '{product_type}': {e}. "
                "This indicates a database configuration issue."
            )
            logger.error(error_msg)

            # Capture to Sentry
            try:
                from crawler.monitoring import capture_crawl_error
                schema_error = SchemaConfigurationError(error_msg)
                capture_crawl_error(
                    error=schema_error,
                    extra_context={
                        "product_type": product_type,
                        "original_error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            except ImportError:
                # Sentry monitoring not available
                pass

            raise SchemaConfigurationError(error_msg) from e

    async def _aget_default_schema(self, product_type: str) -> List[Dict[str, Any]]:
        """
        Async-safe version of _get_default_schema.

        Uses sync_to_async to wrap database access for async contexts.

        Args:
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            List of schema dicts with full field definitions
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

        V1->V2 Migration: This method provides a drop-in replacement for the V1
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
