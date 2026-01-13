"""
Competition Page Fetcher for E2E Testing.

This module provides proper page fetching using the SmartRouter with full tier escalation.
It does NOT fall back to raw httpx if SmartRouter fails - it escalates through all tiers
and raises an error if fetching ultimately fails.

Key Principles (per E2E_TEST_SPECIFICATION_V2.md):
1. NO synthetic content - All tests use real URLs
2. NO shortcuts or workarounds - If fetching fails, investigate root cause
3. Use the ACTUAL implementation (SmartRouter with tier escalation)
4. JavaScript-heavy pages MUST use Tier 2 (Playwright) or Tier 3 (ScrapingBee)

Recording:
This module integrates with TestStepRecorder to capture intermediate outputs.
Pass a recorder to fetch/extract functions to record what each step does.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.e2e.utils.test_recorder import TestStepRecorder

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum number of VALID products required per competition flow
MIN_PRODUCTS_REQUIRED = 5

# Invalid product names that should be rejected
INVALID_PRODUCT_NAMES = [
    "unknown product",
    "unknown",
    "n/a",
    "none",
    "",
    "product",
    "test",
    "example",
]

# Minimum confidence threshold for accepting extracted products
MIN_CONFIDENCE_THRESHOLD = 0.3


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FetchResult:
    """Result of a page fetch operation."""
    success: bool
    content: Optional[str]
    tier_used: int
    error: Optional[str] = None
    content_length: int = 0
    has_product_indicators: bool = False


@dataclass
class ExtractionResult:
    """Result of product extraction from a page."""
    success: bool
    products: List[Dict[str, Any]]
    valid_products: List[Dict[str, Any]]
    rejected_products: List[Dict[str, Any]]
    error: Optional[str] = None
    extraction_method: str = "ai_client_v2"


# =============================================================================
# Page Fetching (Using SmartRouter with Tier Escalation)
# =============================================================================

async def fetch_competition_page(
    url: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    force_tier: Optional[int] = None,
    recorder: Optional["TestStepRecorder"] = None,
) -> FetchResult:
    """
    Fetch a competition page using SmartRouter with full tier escalation.

    This function uses the ACTUAL SmartRouter implementation which:
    - Tier 1: httpx with cookies (fast, no JS)
    - Tier 2: Playwright browser (JavaScript rendering)
    - Tier 3: ScrapingBee proxy (for blocked sites)

    Does NOT fall back to raw httpx. If SmartRouter fails completely,
    raises an error for investigation.

    Args:
        url: URL to fetch
        max_retries: Number of retry attempts (default 3)
        retry_delay: Initial delay between retries in seconds (default 5.0)
        force_tier: Force a specific tier (1, 2, or 3). If None, use automatic escalation.
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        FetchResult with content and metadata

    Raises:
        RuntimeError: If all fetch attempts fail across all tiers
    """
    # Start recording if recorder provided
    if recorder:
        recorder.start_step(
            "fetch",
            f"Fetching competition page (force_tier={force_tier or 'auto'})",
            {"url": url, "max_retries": max_retries, "force_tier": force_tier}
        )
    from crawler.fetchers.smart_router import SmartRouter

    last_error = None
    tier_used = 0

    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = retry_delay * (2 ** (attempt - 1))
            logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay...")
            await asyncio.sleep(wait_time)

        try:
            # Use SmartRouter with tier escalation
            router = SmartRouter()

            # If force_tier specified, use it
            if force_tier:
                logger.info(f"Fetching {url} with forced Tier {force_tier}")
                result = await router.fetch(url, force_tier=force_tier)
            else:
                logger.info(f"Fetching {url} with automatic tier escalation")
                result = await router.fetch(url)

            if result.success and result.content:
                content = result.content
                tier_used = getattr(result, 'tier_used', 1)

                # Check if content looks like it has product data
                has_indicators = _check_product_indicators(content)

                logger.info(
                    f"Successfully fetched {url} via Tier {tier_used} "
                    f"(content={len(content)} bytes, has_indicators={has_indicators})"
                )

                fetch_result = FetchResult(
                    success=True,
                    content=content,
                    tier_used=tier_used,
                    content_length=len(content),
                    has_product_indicators=has_indicators,
                )

                # Record successful fetch
                if recorder:
                    recorder.complete_step(
                        output_data={
                            "tier_used": tier_used,
                            "tier_name": {1: "httpx", 2: "Playwright", 3: "ScrapingBee"}.get(tier_used, "Unknown"),
                            "content_length_bytes": len(content),
                            "content_length_kb": round(len(content) / 1024, 1),
                            "has_product_indicators": has_indicators,
                            "content_preview": content[:500] if content else None,
                        },
                        success=True
                    )

                return fetch_result
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                tier_used = getattr(result, 'tier_used', 3)
                logger.warning(f"SmartRouter returned failure for {url}: {error_msg}")
                last_error = error_msg

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1} failed to fetch {url}: {e}")

    # Record failed fetch
    error_message = (
        f"Failed to fetch competition page after {max_retries} attempts. "
        f"URL: {url}. Last error: {last_error}. "
        f"SmartRouter exhausted all tiers (1→2→3). "
        f"This needs investigation - check: "
        f"1) Is Playwright installed and configured? "
        f"2) Is ScrapingBee API key valid? "
        f"3) Is the URL accessible? "
        f"Do NOT use synthetic fallback."
    )

    if recorder:
        recorder.complete_step(
            output_data={
                "tier_used": tier_used,
                "attempts": max_retries,
            },
            success=False,
            error=error_message
        )

    # All retries exhausted - raise error for investigation
    raise RuntimeError(error_message)


async def fetch_with_scrapingbee(
    url: str,
    render_js: bool = True,
    wait_for: Optional[str] = None,
) -> FetchResult:
    """
    Fetch a page directly using ScrapingBee (Tier 3).

    Use this when you KNOW the page requires JavaScript rendering
    and want to skip Tier 1 and Tier 2 attempts.

    Args:
        url: URL to fetch
        render_js: Whether to render JavaScript (default True)
        wait_for: Optional CSS selector to wait for before returning

    Returns:
        FetchResult with content and metadata
    """
    from crawler.fetchers.smart_router import SmartRouter

    try:
        router = SmartRouter()
        result = await router.fetch(url, force_tier=3)

        if result.success and result.content:
            return FetchResult(
                success=True,
                content=result.content,
                tier_used=3,
                content_length=len(result.content),
                has_product_indicators=_check_product_indicators(result.content),
            )
        else:
            error_msg = getattr(result, 'error', 'ScrapingBee returned empty content')
            return FetchResult(
                success=False,
                content=None,
                tier_used=3,
                error=error_msg,
            )
    except Exception as e:
        return FetchResult(
            success=False,
            content=None,
            tier_used=3,
            error=str(e),
        )


def _check_product_indicators(content: str) -> bool:
    """
    Check if HTML content appears to contain product data.

    Looks for common indicators that the page has rendered product content,
    not just a JavaScript shell.
    """
    if not content:
        return False

    content_lower = content.lower()

    # Product-related keywords
    product_keywords = [
        "whisky", "whiskey", "bourbon", "scotch", "malt",
        "port", "tawny", "ruby", "vintage", "colheita",
        "gold medal", "silver medal", "bronze medal",
        "abv", "alcohol", "distillery", "producer",
        "tasting notes", "palate", "nose", "finish",
    ]

    # Count keyword matches
    matches = sum(1 for kw in product_keywords if kw in content_lower)

    # Also check for structural indicators
    has_product_structure = any([
        "product" in content_lower and "name" in content_lower,
        "item" in content_lower and "title" in content_lower,
        '<h2' in content_lower or '<h3' in content_lower,
        'class="product' in content_lower,
        'class="item' in content_lower,
        'data-product' in content_lower,
    ])

    # Need at least 3 keyword matches OR structural indicators
    return matches >= 3 or has_product_structure


# =============================================================================
# Product Extraction with Validation
# =============================================================================

async def extract_products_with_validation(
    content: str,
    url: str,
    product_type: str,
    product_category: Optional[str] = None,
    min_products: int = MIN_PRODUCTS_REQUIRED,
    recorder: Optional["TestStepRecorder"] = None,
) -> ExtractionResult:
    """
    Extract products from page content and validate them.

    Uses AIClientV2 for extraction (which includes ContentPreprocessor for
    intelligent content cleaning with ~93% token savings), then validates
    each product to ensure:
    - Product has a valid name (not "Unknown Product")
    - Product has minimum required fields
    - Product meets confidence threshold

    NOTE: Content preprocessing is handled by AIClientV2 internally via
    ContentPreprocessor. This ensures E2E tests use the exact same code
    path as production.

    Args:
        content: HTML content to extract from (raw, will be preprocessed by AIClientV2)
        url: Source URL for context
        product_type: Expected product type (whiskey, port_wine)
        product_category: Optional category filter
        min_products: Minimum number of valid products required
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        ExtractionResult with valid and rejected products

    Raises:
        RuntimeError: If extraction fails or returns fewer than min_products valid products
    """
    from crawler.services.ai_client_v2 import get_ai_client_v2

    # NOTE: We pass raw content to AIClientV2 - it handles preprocessing via
    # ContentPreprocessor which uses trafilatura for ~93% token savings and
    # intelligently detects list pages to preserve structure when needed.
    # This ensures E2E tests exercise the exact same code path as production.
    original_length = len(content)
    logger.info(
        f"Passing content to AIClientV2 for preprocessing and extraction: {original_length:,} chars"
    )

    # Start recording extraction step
    if recorder:
        recorder.start_step(
            "ai_extract",
            f"AI extraction for {product_type} products (with ContentPreprocessor)",
            {
                "url": url,
                "product_type": product_type,
                "product_category": product_category,
                "original_content_length": original_length,
            }
        )

    extraction_start = time.time()
    client = get_ai_client_v2()

    # Call AI extraction - uses full schema from database (all DiscoveredProduct + details fields)
    try:
        result = await client.extract(
            content=content,
            source_url=url,
            product_type=product_type,
            product_category=product_category,
            detect_multi_product=True,
        )
    except Exception as e:
        raise RuntimeError(
            f"AI extraction failed for {url}: {e}. "
            f"Check AI service connectivity and configuration."
        )

    if not result.success:
        raise RuntimeError(
            f"AI extraction returned failure for {url}. "
            f"Error: {result.error}. "
            f"This needs investigation - check AI service logs."
        )

    extraction_time_ms = (time.time() - extraction_start) * 1000

    # Record AI extraction completion
    if recorder:
        recorder.complete_step(
            output_data={
                "total_products_from_ai": len(result.products),
                "extraction_time_ms": round(extraction_time_ms, 1),
                "ai_success": result.success,
            },
            success=True
        )

    # Start validation step
    if recorder:
        recorder.start_step(
            "validate",
            f"Validating {len(result.products)} extracted products",
            {"min_products_required": min_products}
        )

    # Process and validate each product
    valid_products = []
    rejected_products = []

    for idx, extracted in enumerate(result.products):
        product_data = extracted.extracted_data.copy()
        product_data["field_confidences"] = extracted.field_confidences
        product_data["overall_confidence"] = extracted.confidence
        product_data["source_url"] = url

        # Validate the product
        is_valid, rejection_reason = _validate_product(product_data)

        if is_valid:
            valid_products.append(product_data)
        else:
            product_data["rejection_reason"] = rejection_reason
            rejected_products.append(product_data)
            logger.warning(f"Rejected product: {product_data.get('name', 'N/A')} - {rejection_reason}")

        # Record each product
        if recorder:
            recorder.record_product(
                index=idx,
                product_data=product_data,
                is_valid=is_valid,
                rejection_reason=rejection_reason,
            )

    # Complete validation step
    if recorder:
        recorder.complete_step(
            output_data={
                "total_products": len(result.products),
                "valid_products": len(valid_products),
                "rejected_products": len(rejected_products),
                "validation_pass_rate": f"{(len(valid_products) / len(result.products) * 100):.1f}%" if result.products else "N/A",
            },
            success=len(valid_products) >= min_products
        )

    logger.info(
        f"Extraction result: {len(valid_products)} valid, {len(rejected_products)} rejected "
        f"from {url}"
    )

    # Check minimum product count
    if len(valid_products) < min_products:
        raise RuntimeError(
            f"Extraction returned only {len(valid_products)} valid products, "
            f"but {min_products} are required. "
            f"Rejected products: {len(rejected_products)}. "
            f"URL: {url}. "
            f"Rejection reasons: {[p.get('rejection_reason') for p in rejected_products[:5]]}. "
            f"This indicates the page may not contain enough product data or "
            f"JavaScript rendering is required. Check SmartRouter tier escalation."
        )

    return ExtractionResult(
        success=True,
        products=valid_products + rejected_products,
        valid_products=valid_products,
        rejected_products=rejected_products,
    )


def _validate_product(product_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a single extracted product.

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    # Check name exists and is valid
    name = product_data.get("name", "").strip().lower()

    if not name:
        return False, "Missing product name"

    if name in INVALID_PRODUCT_NAMES:
        return False, f"Invalid product name: '{name}'"

    # Check name is not too short (likely garbage)
    if len(name) < 3:
        return False, f"Product name too short: '{name}'"

    # Check confidence threshold
    confidence = product_data.get("overall_confidence", 0.0)
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        return False, f"Confidence too low: {confidence} < {MIN_CONFIDENCE_THRESHOLD}"

    # Check for at least one meaningful field besides name
    meaningful_fields = ["brand", "description", "abv", "region", "country"]
    has_meaningful_data = any(
        product_data.get(field) not in [None, "", [], {}]
        for field in meaningful_fields
    )

    if not has_meaningful_data:
        return False, "No meaningful data besides name"

    return True, None


def validate_minimum_products(
    products: List[Dict[str, Any]],
    min_count: int = MIN_PRODUCTS_REQUIRED,
    context: str = "competition",
) -> None:
    """
    Validate that we have the minimum required number of products.

    Raises RuntimeError if validation fails.
    """
    if len(products) < min_count:
        raise RuntimeError(
            f"{context} extraction failed: Got {len(products)} products, "
            f"but {min_count} are required per spec. "
            f"This needs investigation - do NOT accept partial results."
        )


# =============================================================================
# Competition-Specific Fetching
# =============================================================================

async def fetch_iwsc_page(url: str, recorder: Optional["TestStepRecorder"] = None) -> FetchResult:
    """
    Fetch IWSC competition page.

    IWSC pages are JavaScript-heavy SPAs. We force Tier 2 or 3 to ensure
    proper JavaScript rendering.

    Args:
        url: URL to fetch
        recorder: Optional TestStepRecorder to record intermediate outputs
    """
    logger.info(f"Fetching IWSC page (forcing Tier 2+ for JS rendering): {url}")

    # Try Tier 2 (Playwright) first, fall back to Tier 3 (ScrapingBee)
    try:
        result = await fetch_competition_page(url, force_tier=2, recorder=recorder)
        if result.success and result.has_product_indicators:
            return result
    except Exception as e:
        logger.warning(f"Tier 2 failed for IWSC: {e}, trying Tier 3")

    # Fall back to ScrapingBee
    return await fetch_competition_page(url, force_tier=3, recorder=recorder)


async def fetch_sfwsc_page(url: str, recorder: Optional["TestStepRecorder"] = None) -> FetchResult:
    """
    Fetch SFWSC competition page.

    SFWSC pages may require JavaScript rendering.

    Args:
        url: URL to fetch
        recorder: Optional TestStepRecorder to record intermediate outputs
    """
    logger.info(f"Fetching SFWSC page: {url}")

    # Try automatic tier escalation first
    result = await fetch_competition_page(url, recorder=recorder)

    # If content looks empty (JS shell), retry with forced tier
    if result.success and not result.has_product_indicators:
        logger.warning("SFWSC content appears to be JS shell, retrying with Tier 3")
        result = await fetch_competition_page(url, force_tier=3, recorder=recorder)

    return result


async def fetch_dwwa_page(url: str, recorder: Optional["TestStepRecorder"] = None) -> FetchResult:
    """
    Fetch DWWA competition page.

    DWWA (Decanter) pages are JavaScript-heavy. Force Tier 2 or 3.

    Args:
        url: URL to fetch
        recorder: Optional TestStepRecorder to record intermediate outputs
    """
    logger.info(f"Fetching DWWA page (forcing Tier 2+ for JS rendering): {url}")

    # Try Tier 2 (Playwright) first, fall back to Tier 3 (ScrapingBee)
    try:
        result = await fetch_competition_page(url, force_tier=2, recorder=recorder)
        if result.success and result.has_product_indicators:
            return result
    except Exception as e:
        logger.warning(f"Tier 2 failed for DWWA: {e}, trying Tier 3")

    # Fall back to ScrapingBee
    return await fetch_competition_page(url, force_tier=3, recorder=recorder)
