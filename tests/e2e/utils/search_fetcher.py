"""
Search Fetcher for E2E Testing - Generic Search Discovery Flow.

This module provides SerpAPI search execution and URL fetching for the generic
search discovery flow. It mirrors the competition_fetcher.py approach but for
search-based product discovery.

Key Principles (per E2E_TEST_SPECIFICATION_V2.md):
1. NO synthetic content - All tests use real SerpAPI results
2. NO shortcuts or workarounds - If search/fetch fails, investigate root cause
3. Use ACTUAL implementations (SerpAPI, SmartRouter with tier escalation)
4. Record intermediate steps for debugging

Recording:
This module integrates with TestStepRecorder to capture intermediate outputs.
Pass a recorder to functions to record what each step does.
"""

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.e2e.utils.test_recorder import TestStepRecorder

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum number of VALID products required from search results
MIN_PRODUCTS_REQUIRED = 3

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

# Maximum URLs to process from search results
MAX_URLS_TO_PROCESS = 5


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SearchResult:
    """Result of a SerpAPI search execution."""
    success: bool
    query: str
    organic_results: List[Dict[str, Any]]
    total_results: int
    error: Optional[str] = None
    search_time_ms: float = 0.0


@dataclass
class FetchResult:
    """Result of a page fetch operation."""
    success: bool
    content: Optional[str]
    url: str
    tier_used: int
    error: Optional[str] = None
    content_length: int = 0
    has_product_indicators: bool = False


@dataclass
class ExtractionResult:
    """Result of product extraction from search result pages."""
    success: bool
    products: List[Dict[str, Any]]
    valid_products: List[Dict[str, Any]]
    rejected_products: List[Dict[str, Any]]
    sources_crawled: List[str] = field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# SerpAPI Search Execution
# =============================================================================

async def execute_serpapi_search(
    query: str,
    max_results: int = 10,
    recorder: Optional["TestStepRecorder"] = None,
) -> SearchResult:
    """
    Execute a SerpAPI search and return organic results only.

    This function uses the project's SerpAPIClient which makes direct HTTP
    requests to SerpAPI. It does NOT mock results.
    If SerpAPI fails, raises an error for investigation.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default 10)
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        SearchResult with organic results

    Raises:
        RuntimeError: If SerpAPI search fails
    """
    from crawler.discovery.serpapi.client import SerpAPIClient

    # Start recording if recorder provided
    if recorder:
        recorder.start_step(
            "serpapi_search",
            f"SerpAPI search: {query[:50]}...",
            {"query": query, "max_results": max_results}
        )

    # Check for API key in environment (also checked by SerpAPIClient)
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        error_msg = (
            "SERPAPI_API_KEY or SERPAPI_KEY not configured. "
            "This is required for generic search E2E tests. "
            "Do NOT use synthetic fallback."
        )
        if recorder:
            recorder.complete_step(output_data={}, success=False, error=error_msg)
        raise RuntimeError(error_msg)

    search_start = time.time()

    try:
        # Use the project's SerpAPIClient
        client = SerpAPIClient(api_key=api_key)
        results = client.google_search(
            query=query,
            num_results=max_results,
            gl="us",
            hl="en",
        )

        search_time_ms = (time.time() - search_start) * 1000

        # Extract organic results only (no ads per spec)
        organic_results = results.get("organic_results", [])

        logger.info(
            f"SerpAPI search complete: '{query}' returned {len(organic_results)} organic results "
            f"in {search_time_ms:.0f}ms"
        )

        search_result = SearchResult(
            success=True,
            query=query,
            organic_results=organic_results[:max_results],
            total_results=len(organic_results),
            search_time_ms=search_time_ms,
        )

        # Record successful search
        if recorder:
            recorder.complete_step(
                output_data={
                    "organic_results_count": len(organic_results),
                    "search_time_ms": round(search_time_ms, 1),
                    "top_urls": [r.get("link", "")[:80] for r in organic_results[:3]],
                    "top_titles": [r.get("title", "")[:60] for r in organic_results[:3]],
                },
                success=True
            )

        return search_result

    except Exception as e:
        error_msg = f"SerpAPI search failed for '{query}': {e}"
        logger.error(error_msg)

        if recorder:
            recorder.complete_step(
                output_data={},
                success=False,
                error=error_msg
            )

        raise RuntimeError(
            f"{error_msg}. "
            f"Check SerpAPI API key and quota. "
            f"Do NOT use synthetic fallback."
        )


# =============================================================================
# URL Fetching (Using SmartRouter with Tier Escalation)
# =============================================================================

async def fetch_search_result_page(
    url: str,
    max_retries: int = 3,
    retry_delay: float = 3.0,
    force_tier: Optional[int] = None,
    recorder: Optional["TestStepRecorder"] = None,
) -> FetchResult:
    """
    Fetch a search result page using SmartRouter with full tier escalation.

    This function uses the ACTUAL SmartRouter implementation which:
    - Tier 1: httpx with cookies (fast, no JS)
    - Tier 2: Playwright browser (JavaScript rendering)
    - Tier 3: ScrapingBee proxy (for blocked sites)

    Does NOT fall back to raw httpx. If SmartRouter fails completely,
    returns a failure result.

    Args:
        url: URL to fetch
        max_retries: Number of retry attempts (default 3)
        retry_delay: Initial delay between retries in seconds (default 3.0)
        force_tier: Force a specific tier (1, 2, or 3). If None, use automatic escalation.
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        FetchResult with content and metadata
    """
    # Start recording if recorder provided
    if recorder:
        recorder.start_step(
            "fetch_url",
            f"Fetching: {url[:60]}...",
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
            router = SmartRouter()

            if force_tier:
                logger.info(f"Fetching {url[:60]}... with forced Tier {force_tier}")
                result = await router.fetch(url, force_tier=force_tier)
            else:
                logger.info(f"Fetching {url[:60]}... with automatic tier escalation")
                result = await router.fetch(url)

            if result.success and result.content:
                content = result.content
                tier_used = getattr(result, 'tier_used', 1)
                has_indicators = _check_product_indicators(content)

                logger.info(
                    f"Successfully fetched {url[:60]}... via Tier {tier_used} "
                    f"(content={len(content)} bytes, has_indicators={has_indicators})"
                )

                fetch_result = FetchResult(
                    success=True,
                    content=content,
                    url=url,
                    tier_used=tier_used,
                    content_length=len(content),
                    has_product_indicators=has_indicators,
                )

                if recorder:
                    recorder.complete_step(
                        output_data={
                            "tier_used": tier_used,
                            "tier_name": {1: "httpx", 2: "Playwright", 3: "ScrapingBee"}.get(tier_used, "Unknown"),
                            "content_length_bytes": len(content),
                            "content_length_kb": round(len(content) / 1024, 1),
                            "has_product_indicators": has_indicators,
                        },
                        success=True
                    )

                return fetch_result
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                tier_used = getattr(result, 'tier_used', 3)
                logger.warning(f"SmartRouter returned failure for {url[:60]}...: {error_msg}")
                last_error = error_msg

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1} failed to fetch {url[:60]}...: {e}")

    # All retries exhausted - return failure (don't raise, continue with other URLs)
    error_message = f"Failed to fetch {url[:60]}... after {max_retries} attempts: {last_error}"
    logger.error(error_message)

    if recorder:
        recorder.complete_step(
            output_data={"tier_used": tier_used, "attempts": max_retries},
            success=False,
            error=error_message
        )

    return FetchResult(
        success=False,
        content=None,
        url=url,
        tier_used=tier_used,
        error=error_message,
    )


def _check_product_indicators(content: str) -> bool:
    """
    Check if HTML content appears to contain product data.

    Looks for common indicators that the page has product content.
    """
    if not content:
        return False

    content_lower = content.lower()

    # Product-related keywords for whiskey/spirits
    product_keywords = [
        "whisky", "whiskey", "bourbon", "scotch", "malt", "single malt",
        "non-peated", "peated", "speyside", "islay", "highland",
        "abv", "alcohol", "distillery", "distiller",
        "tasting notes", "palate", "nose", "finish",
        "aged", "year old", "matured", "cask",
        "review", "rating", "score",
    ]

    # Count keyword matches
    matches = sum(1 for kw in product_keywords if kw in content_lower)

    # Also check for structural indicators
    has_product_structure = any([
        "product" in content_lower and "name" in content_lower,
        '<article' in content_lower,
        '<h2' in content_lower or '<h3' in content_lower,
        'class="product' in content_lower,
        'data-product' in content_lower,
        '"price"' in content_lower,
    ])

    return matches >= 3 or has_product_structure


# =============================================================================
# Product Extraction from Search Results
# =============================================================================

async def extract_products_from_search_results(
    search_result: SearchResult,
    product_type: str = "whiskey",
    max_urls: int = MAX_URLS_TO_PROCESS,
    min_products: int = MIN_PRODUCTS_REQUIRED,
    recorder: Optional["TestStepRecorder"] = None,
) -> ExtractionResult:
    """
    Fetch and extract products from search result URLs.

    Processes URLs in order until we have enough valid products.

    Args:
        search_result: SerpAPI search result
        product_type: Expected product type (whiskey, port_wine)
        max_urls: Maximum URLs to process
        min_products: Minimum valid products required
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        ExtractionResult with valid and rejected products

    Raises:
        RuntimeError: If not enough valid products extracted
    """
    from crawler.services.ai_client_v2 import get_ai_client_v2

    all_products = []
    valid_products = []
    rejected_products = []
    sources_crawled = []

    ai_client = get_ai_client_v2()

    # Process URLs until we have enough products or exhausted URLs
    urls_to_process = search_result.organic_results[:max_urls]

    for idx, result in enumerate(urls_to_process):
        url = result.get("link", "")
        title = result.get("title", "")

        if not url:
            continue

        logger.info(f"Processing search result {idx + 1}/{len(urls_to_process)}: {title[:50]}...")

        # Fetch the page
        fetch_result = await fetch_search_result_page(url, recorder=recorder)

        if not fetch_result.success:
            logger.warning(f"Failed to fetch {url[:60]}..., skipping")
            continue

        sources_crawled.append(url)

        # Extract products using AI
        if recorder:
            recorder.start_step(
                "ai_extract",
                f"AI extraction from: {title[:40]}...",
                {"url": url, "content_length": fetch_result.content_length}
            )

        extraction_start = time.time()

        try:
            ai_result = await ai_client.extract(
                content=fetch_result.content,
                source_url=url,
                product_type=product_type,
                detect_multi_product=True,
            )

            extraction_time_ms = (time.time() - extraction_start) * 1000

            if not ai_result.success:
                logger.warning(f"AI extraction failed for {url[:60]}...: {ai_result.error}")
                if recorder:
                    recorder.complete_step(
                        output_data={"error": ai_result.error},
                        success=False,
                        error=ai_result.error
                    )
                continue

            if recorder:
                recorder.complete_step(
                    output_data={
                        "products_extracted": len(ai_result.products),
                        "extraction_time_ms": round(extraction_time_ms, 1),
                        "is_list_page": getattr(ai_result, 'is_list_page', False),
                    },
                    success=True
                )

            # Validate and collect products
            for product_idx, extracted in enumerate(ai_result.products):
                product_data = extracted.extracted_data.copy()
                product_data["field_confidences"] = extracted.field_confidences
                product_data["overall_confidence"] = extracted.confidence
                product_data["source_url"] = url
                product_data["source_title"] = title

                is_valid, rejection_reason = _validate_product(product_data)

                all_products.append(product_data)

                if is_valid:
                    valid_products.append(product_data)
                    logger.info(f"  Valid product: {product_data.get('name', 'N/A')[:50]}")
                else:
                    product_data["rejection_reason"] = rejection_reason
                    rejected_products.append(product_data)
                    logger.warning(f"  Rejected product: {product_data.get('name', 'N/A')[:30]} - {rejection_reason}")

                # Record product
                if recorder:
                    recorder.record_product(
                        index=len(all_products) - 1,
                        product_data=product_data,
                        is_valid=is_valid,
                        rejection_reason=rejection_reason,
                    )

        except Exception as e:
            logger.error(f"AI extraction error for {url[:60]}...: {e}")
            if recorder:
                recorder.complete_step(
                    output_data={},
                    success=False,
                    error=str(e)
                )
            continue

        # Check if we have enough valid products
        if len(valid_products) >= min_products:
            logger.info(f"Found {len(valid_products)} valid products, stopping URL processing")
            break

    # Final check
    if len(valid_products) < min_products:
        raise RuntimeError(
            f"Generic search extraction failed: Got {len(valid_products)} valid products, "
            f"but {min_products} are required. "
            f"Processed {len(sources_crawled)} URLs. "
            f"Rejected products: {len(rejected_products)}. "
            f"Query: '{search_result.query}'. "
            f"This needs investigation - pages may not contain enough product data."
        )

    return ExtractionResult(
        success=True,
        products=all_products,
        valid_products=valid_products,
        rejected_products=rejected_products,
        sources_crawled=sources_crawled,
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

    if len(name) < 3:
        return False, f"Product name too short: '{name}'"

    # Check confidence threshold
    confidence = product_data.get("overall_confidence", 0.0)
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        return False, f"Confidence too low: {confidence} < {MIN_CONFIDENCE_THRESHOLD}"

    # Check for at least one meaningful field besides name
    meaningful_fields = ["brand", "description", "abv", "region", "country", "distillery"]
    has_meaningful_data = any(
        product_data.get(field) not in [None, "", [], {}]
        for field in meaningful_fields
    )

    if not has_meaningful_data:
        return False, "No meaningful data besides name"

    return True, None


# =============================================================================
# URL Deduplication
# =============================================================================

def generate_url_hash(url: str) -> str:
    """Generate SHA-256 hash for URL deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()


async def check_url_duplicate(url: str) -> bool:
    """
    Check if URL has already been crawled.

    Returns True if duplicate, False if new.
    """
    from asgiref.sync import sync_to_async
    from crawler.models import CrawledURL

    url_hash = generate_url_hash(url)

    @sync_to_async
    def _check():
        return CrawledURL.objects.filter(url_hash=url_hash).exists()

    return await _check()


async def record_crawled_url(url: str) -> None:
    """Record a URL as crawled to prevent future duplicates."""
    from asgiref.sync import sync_to_async
    from crawler.models import CrawledURL

    url_hash = generate_url_hash(url)

    @sync_to_async
    def _record():
        CrawledURL.objects.get_or_create(
            url_hash=url_hash,
            defaults={"url": url}
        )

    await _record()


# =============================================================================
# Product Fingerprint Deduplication
# =============================================================================

def generate_product_fingerprint(product_data: Dict[str, Any]) -> str:
    """Generate fingerprint for product deduplication."""
    import json

    key_data = json.dumps({
        "name": (product_data.get("name") or "").lower().strip(),
        "brand": (product_data.get("brand") or "").lower().strip(),
    }, sort_keys=True)

    return hashlib.sha256(key_data.encode()).hexdigest()


async def check_product_duplicate(fingerprint: str) -> bool:
    """
    Check if product with fingerprint already exists.

    Returns True if duplicate, False if new.
    """
    from asgiref.sync import sync_to_async
    from crawler.models import DiscoveredProduct

    @sync_to_async
    def _check():
        return DiscoveredProduct.objects.filter(fingerprint=fingerprint).exists()

    return await _check()
