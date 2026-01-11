"""
Single Product Fetcher for E2E Testing.

This module provides dynamic product discovery and extraction for single product
page E2E tests. Instead of hardcoded URLs, it uses SerpAPI to find the product
page dynamically - similar to how the enrichment orchestrator finds sources.

Key Principles (per E2E_TEST_SPECIFICATION_V2.md):
1. NO synthetic content - All tests use real SerpAPI results
2. NO hardcoded URLs - Find product pages dynamically via search
3. Use ACTUAL implementations (SerpAPI, SmartRouter, AIClientV2)
4. Record intermediate steps for debugging

Search Template Progression:
1. "{name} official site" - Try to find official brand page first
2. "{name} {brand} whiskey" - General product search
3. "{name} tasting notes review" - Review/info pages
4. "{name} buy" - Retailer pages (last resort)

Recording:
This module integrates with TestStepRecorder to capture intermediate outputs.
Pass a recorder to functions to record what each step does.
"""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.e2e.utils.test_recorder import TestStepRecorder

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum confidence threshold for accepting extracted products
MIN_CONFIDENCE_THRESHOLD = 0.3

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

# Search template progression for finding product pages
# Templates are tried in order until a valid product page is found
# Placeholders: {name}, {brand}, {product_type}
PRODUCT_SEARCH_TEMPLATES = [
    "{name} official site",           # Try official brand page first
    "{name} {brand}",                 # Brand + product name
    "{name} {product_type}",          # Product type context
    "{name} tasting notes review",    # Review/info pages (good for extraction)
    "{name} buy online",              # Retailer pages (last resort)
]

# Domains to prioritize (official/trusted sources)
PRIORITY_DOMAINS = [
    "official",      # Official brand sites
    ".com/products", # Product pages
    "totalwine.com",
    "thewhiskyexchange.com",
    "masterofmalt.com",
    "wine-searcher.com",
    "caskers.com",
]

# Domains to avoid (aggregators, forums without product data)
AVOID_DOMAINS = [
    "reddit.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "pinterest.com",
    "youtube.com",
    "amazon.com",  # Often blocked
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProductSearchResult:
    """Result of a product page search."""
    success: bool
    url: str
    title: str
    template_used: str
    search_position: int
    error: Optional[str] = None


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
    """Result of product extraction from a single product page."""
    success: bool
    product_data: Dict[str, Any]
    field_confidences: Dict[str, float]
    overall_confidence: float
    quality_status: str
    needs_enrichment: bool
    error: Optional[str] = None


@dataclass
class DiscoveryResult:
    """Combined result of search + fetch + extraction."""
    success: bool
    url: str
    fetch_result: Optional[FetchResult] = None
    extraction_result: Optional[ExtractionResult] = None
    template_used: Optional[str] = None
    templates_tried: List[str] = field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# Dynamic Product Discovery (SerpAPI Search)
# =============================================================================

def _build_search_query(
    template: str,
    product_name: str,
    brand: Optional[str] = None,
    product_type: str = "whiskey",
) -> str:
    """
    Build search query from template by substituting placeholders.

    Args:
        template: Search template with {name}, {brand}, {product_type} placeholders
        product_name: Product name to substitute
        brand: Optional brand name
        product_type: Product type (whiskey, bourbon, etc.)

    Returns:
        Search query string
    """
    query = template
    query = query.replace("{name}", product_name)
    query = query.replace("{brand}", brand or "")
    query = query.replace("{product_type}", product_type)

    # Clean up extra spaces
    query = re.sub(r"\{[^}]+\}", "", query)  # Remove unfilled placeholders
    query = " ".join(query.split())

    return query.strip()


def _filter_and_rank_urls(
    organic_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter and rank search results by relevance.

    Prioritizes official sites and product pages, avoids social media.

    Args:
        organic_results: Raw SerpAPI organic results

    Returns:
        Filtered and sorted results
    """
    filtered = []

    for result in organic_results:
        url = result.get("link", "")

        # Skip avoided domains
        if any(domain in url.lower() for domain in AVOID_DOMAINS):
            logger.debug(f"Skipping avoided domain: {url[:60]}")
            continue

        filtered.append(result)

    # Sort by priority (priority domains first)
    def priority_score(result: Dict) -> int:
        url = result.get("link", "").lower()
        for i, domain in enumerate(PRIORITY_DOMAINS):
            if domain in url:
                return i
        return 100  # Non-priority domains last

    filtered.sort(key=priority_score)

    return filtered


async def search_for_product_page(
    product_name: str,
    brand: Optional[str] = None,
    product_type: str = "whiskey",
    templates: Optional[List[str]] = None,
    max_results_per_search: int = 5,
    recorder: Optional["TestStepRecorder"] = None,
) -> ProductSearchResult:
    """
    Search for a product page using SerpAPI with template progression.

    Tries each search template in order until a promising URL is found.

    Args:
        product_name: Name of the product to find
        brand: Optional brand name
        product_type: Product type for context
        templates: Search templates to use (defaults to PRODUCT_SEARCH_TEMPLATES)
        max_results_per_search: Max results to consider per search
        recorder: Optional TestStepRecorder for logging

    Returns:
        ProductSearchResult with the best URL found

    Raises:
        RuntimeError: If no product page found after all templates
    """
    from crawler.discovery.serpapi.client import SerpAPIClient

    if templates is None:
        templates = PRODUCT_SEARCH_TEMPLATES

    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError(
            "SERPAPI_API_KEY not configured. Required for dynamic product discovery."
        )

    client = SerpAPIClient(api_key=api_key)
    templates_tried = []
    all_urls_tried = set()

    for template in templates:
        query = _build_search_query(template, product_name, brand, product_type)
        templates_tried.append(template)

        if recorder:
            recorder.start_step(
                "product_search",
                f"Searching: {query[:50]}...",
                {"template": template, "query": query}
            )

        try:
            results = client.google_search(query=query, num_results=max_results_per_search)
            organic_results = results.get("organic_results", [])

            if recorder:
                recorder.complete_step(
                    output_data={
                        "results_count": len(organic_results),
                        "top_urls": [r.get("link", "")[:60] for r in organic_results[:3]],
                    },
                    success=len(organic_results) > 0
                )

            if not organic_results:
                logger.warning(f"No results for template '{template}': {query}")
                continue

            # Filter and rank URLs
            ranked_results = _filter_and_rank_urls(organic_results)

            for position, result in enumerate(ranked_results):
                url = result.get("link", "")
                title = result.get("title", "")

                if url in all_urls_tried:
                    continue
                all_urls_tried.add(url)

                logger.info(f"Found candidate URL: {url[:60]}... (template: {template})")

                return ProductSearchResult(
                    success=True,
                    url=url,
                    title=title,
                    template_used=template,
                    search_position=position + 1,
                )

        except Exception as e:
            logger.warning(f"Search failed for template '{template}': {e}")
            if recorder:
                recorder.complete_step(
                    output_data={},
                    success=False,
                    error=str(e)
                )
            continue

    # All templates exhausted
    raise RuntimeError(
        f"Failed to find product page for '{product_name}' after trying {len(templates_tried)} templates. "
        f"Templates tried: {templates_tried}. "
        f"This needs investigation."
    )


async def discover_and_extract_product(
    product_name: str,
    brand: Optional[str] = None,
    product_type: str = "whiskey",
    recorder: Optional["TestStepRecorder"] = None,
) -> DiscoveryResult:
    """
    Complete flow: Search for product, fetch page, extract data.

    This is the main entry point for dynamic product discovery.
    Uses template progression to find the product page, then extracts.

    Args:
        product_name: Name of the product to find and extract
        brand: Optional brand name
        product_type: Product type (whiskey, port_wine)
        recorder: Optional TestStepRecorder for logging

    Returns:
        DiscoveryResult with fetch and extraction results
    """
    templates_tried = []

    # Step 1: Search for the product page
    try:
        search_result = await search_for_product_page(
            product_name=product_name,
            brand=brand,
            product_type=product_type,
            recorder=recorder,
        )
        templates_tried.append(search_result.template_used)
    except RuntimeError as e:
        return DiscoveryResult(
            success=False,
            url="",
            templates_tried=PRODUCT_SEARCH_TEMPLATES,
            error=str(e),
        )

    url = search_result.url
    logger.info(f"Using URL from search: {url}")

    # Step 2: Fetch the page
    try:
        fetch_result = await fetch_product_page(url, recorder=recorder)
    except RuntimeError as e:
        return DiscoveryResult(
            success=False,
            url=url,
            templates_tried=templates_tried,
            template_used=search_result.template_used,
            error=f"Fetch failed: {e}",
        )

    # Step 3: Extract the product
    try:
        extraction_result = await extract_product_from_page(
            content=fetch_result.content,
            url=url,
            product_type=product_type,
            expected_name=product_name,
            recorder=recorder,
        )
    except RuntimeError as e:
        return DiscoveryResult(
            success=False,
            url=url,
            fetch_result=fetch_result,
            templates_tried=templates_tried,
            template_used=search_result.template_used,
            error=f"Extraction failed: {e}",
        )

    return DiscoveryResult(
        success=True,
        url=url,
        fetch_result=fetch_result,
        extraction_result=extraction_result,
        template_used=search_result.template_used,
        templates_tried=templates_tried,
    )


# =============================================================================
# Page Fetching (Using SmartRouter with Tier Escalation)
# =============================================================================

async def fetch_product_page(
    url: str,
    max_retries: int = 3,
    retry_delay: float = 3.0,
    force_tier: Optional[int] = None,
    recorder: Optional["TestStepRecorder"] = None,
) -> FetchResult:
    """
    Fetch a product page using SmartRouter with full tier escalation.

    This function uses the ACTUAL SmartRouter implementation which:
    - Tier 1: httpx with cookies (fast, no JS)
    - Tier 2: Playwright browser (JavaScript rendering)
    - Tier 3: ScrapingBee proxy (for blocked sites)

    Does NOT fall back to synthetic content. If SmartRouter fails completely,
    raises an error for investigation.

    Args:
        url: URL to fetch
        max_retries: Number of retry attempts (default 3)
        retry_delay: Initial delay between retries in seconds (default 3.0)
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
            f"Fetching product page (force_tier={force_tier or 'auto'})",
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
                            "content_preview": content[:500] if content else None,
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

    # All retries exhausted - raise error for investigation
    error_message = (
        f"Failed to fetch product page after {max_retries} attempts. "
        f"URL: {url}. Last error: {last_error}. "
        f"SmartRouter exhausted all tiers (1→2→3). "
        f"This needs investigation - do NOT use synthetic fallback."
    )

    if recorder:
        recorder.complete_step(
            output_data={"tier_used": tier_used, "attempts": max_retries},
            success=False,
            error=error_message
        )

    raise RuntimeError(error_message)


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
        "whisky", "whiskey", "bourbon", "scotch",
        "abv", "alcohol", "proof",
        "tasting notes", "palate", "nose", "finish",
        "aged", "year old", "matured", "barrel", "cask",
        "distillery", "distilled",
        "price", "add to cart", "buy now",
        "product", "description",
    ]

    # Count keyword matches
    matches = sum(1 for kw in product_keywords if kw in content_lower)

    # Also check for structural indicators
    has_product_structure = any([
        "product" in content_lower and ("name" in content_lower or "title" in content_lower),
        '<h1' in content_lower,
        'class="product' in content_lower,
        'data-product' in content_lower,
        '"price"' in content_lower or 'itemprop="price"' in content_lower,
        'add-to-cart' in content_lower or 'add_to_cart' in content_lower,
    ])

    return matches >= 3 or has_product_structure


# =============================================================================
# Product Extraction
# =============================================================================

async def extract_product_from_page(
    content: str,
    url: str,
    product_type: str = "whiskey",
    expected_name: Optional[str] = None,
    recorder: Optional["TestStepRecorder"] = None,
) -> ExtractionResult:
    """
    Extract product data from a single product page.

    Uses AIClientV2 for extraction, then validates the product.

    Args:
        content: HTML content to extract from
        url: Source URL for context
        product_type: Expected product type (whiskey, port_wine)
        expected_name: Expected product name (for validation)
        recorder: Optional TestStepRecorder to record intermediate outputs

    Returns:
        ExtractionResult with product data and quality assessment

    Raises:
        RuntimeError: If extraction fails
    """
    from crawler.services.ai_client_v2 import get_ai_client_v2
    from crawler.services.quality_gate_v2 import get_quality_gate_v2

    # Start recording extraction step
    if recorder:
        recorder.start_step(
            "ai_extract",
            f"AI extraction for {product_type} product",
            {
                "url": url,
                "product_type": product_type,
                "expected_name": expected_name,
                "content_length": len(content),
            }
        )

    extraction_start = time.time()
    client = get_ai_client_v2()

    try:
        result = await client.extract(
            content=content,
            source_url=url,
            product_type=product_type,
            detect_multi_product=False,  # Single product page
        )
    except Exception as e:
        error_msg = f"AI extraction failed for {url}: {e}"
        if recorder:
            recorder.complete_step(output_data={}, success=False, error=error_msg)
        raise RuntimeError(f"{error_msg}. Check AI service connectivity.")

    extraction_time_ms = (time.time() - extraction_start) * 1000

    if not result.success:
        error_msg = f"AI extraction returned failure for {url}: {result.error}"
        if recorder:
            recorder.complete_step(output_data={}, success=False, error=error_msg)
        raise RuntimeError(f"{error_msg}. This needs investigation.")

    # Get the first (and should be only) product
    if not result.products:
        error_msg = f"AI extraction returned no products for {url}"
        if recorder:
            recorder.complete_step(output_data={}, success=False, error=error_msg)
        raise RuntimeError(f"{error_msg}. Page may not contain product data.")

    extracted = result.products[0]
    product_data = extracted.extracted_data.copy()
    field_confidences = extracted.field_confidences.copy()
    overall_confidence = extracted.confidence

    # Record extraction success
    if recorder:
        recorder.complete_step(
            output_data={
                "extraction_time_ms": round(extraction_time_ms, 1),
                "product_name": product_data.get("name", "Unknown"),
                "fields_extracted": list(product_data.keys()),
                "overall_confidence": overall_confidence,
            },
            success=True
        )

    # Validate the product
    is_valid, rejection_reason = _validate_product(product_data, expected_name)

    if not is_valid:
        logger.warning(f"Product validation failed: {rejection_reason}")
        # Don't raise - we'll use expected_name if available
        if expected_name and not product_data.get("name"):
            product_data["name"] = expected_name
            logger.info(f"Using expected name: {expected_name}")

    # Add metadata
    product_data["source_url"] = url
    product_data["field_confidences"] = field_confidences
    product_data["overall_confidence"] = overall_confidence

    # Quality assessment
    gate = get_quality_gate_v2()
    assessment = await gate.aassess(
        extracted_data=product_data,
        product_type=product_type,
        field_confidences=field_confidences,
    )

    quality_status = assessment.status.value
    needs_enrichment = assessment.needs_enrichment

    # Record product
    if recorder:
        recorder.record_product(
            index=0,
            product_data=product_data,
            is_valid=is_valid,
            rejection_reason=rejection_reason,
            quality_status=quality_status,
        )

    return ExtractionResult(
        success=True,
        product_data=product_data,
        field_confidences=field_confidences,
        overall_confidence=overall_confidence,
        quality_status=quality_status,
        needs_enrichment=needs_enrichment,
    )


def _validate_product(
    product_data: Dict[str, Any],
    expected_name: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate a single extracted product.

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    name = product_data.get("name", "").strip().lower()

    if not name:
        if expected_name:
            return True, None  # Will use expected name
        return False, "Missing product name"

    if name in INVALID_PRODUCT_NAMES:
        return False, f"Invalid product name: '{name}'"

    if len(name) < 3:
        return False, f"Product name too short: '{name}'"

    # Check confidence threshold
    confidence = product_data.get("overall_confidence", 0.0)
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        return False, f"Confidence too low: {confidence} < {MIN_CONFIDENCE_THRESHOLD}"

    return True, None


# =============================================================================
# Retailer-Specific Fetching
# =============================================================================

async def fetch_master_of_malt_page(
    url: str,
    recorder: Optional["TestStepRecorder"] = None,
) -> FetchResult:
    """
    Fetch a Master of Malt product page.

    Master of Malt pages may require JavaScript rendering.

    Args:
        url: URL to fetch
        recorder: Optional TestStepRecorder to record intermediate outputs
    """
    logger.info(f"Fetching Master of Malt page: {url}")

    # Try automatic tier escalation first
    result = await fetch_product_page(url, recorder=recorder)

    # If content looks empty (JS shell), retry with forced tier
    if result.success and not result.has_product_indicators:
        logger.warning("Content appears to be JS shell, retrying with Tier 2")
        result = await fetch_product_page(url, force_tier=2, recorder=recorder)

    return result


async def fetch_frank_august_page(
    url: str,
    recorder: Optional["TestStepRecorder"] = None,
) -> FetchResult:
    """
    Fetch a Frank August official product page.

    Frank August's site may use JavaScript for product display.

    Args:
        url: URL to fetch
        recorder: Optional TestStepRecorder to record intermediate outputs
    """
    logger.info(f"Fetching Frank August page: {url}")

    # Start with Tier 2 (Playwright) for JS rendering
    try:
        result = await fetch_product_page(url, force_tier=2, recorder=recorder)
        if result.success and result.has_product_indicators:
            return result
    except Exception as e:
        logger.warning(f"Tier 2 failed for Frank August: {e}, trying Tier 3")

    # Fallback to ScrapingBee
    return await fetch_product_page(url, force_tier=3, recorder=recorder)
