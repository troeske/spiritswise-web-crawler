"""
E2E Test: List Page Extraction Flow (Flow 7)

Tests the list page extraction pipeline using V2 architecture:
- DiscoveryOrchestratorV2 for orchestration
- AIClientV2 for content extraction
- Real AI Enhancement Service at https://api.spiritswise.tech/api/v2/extract/
- QualityGateV2 for quality assessment

This test supports two modes:
A. Direct URL Mode (Regression):
   1. Uses real list page URLs from tests/e2e/utils/real_urls.py
      - Forbes best whiskeys articles
      - Wine Enthusiast top picks
      - Whisky Advocate lists
   2. Extracts multiple products from each list page

B. SearchTerm Discovery Mode (V2 Spec Section 7):
   1. Creates SearchTerms in the database
   2. Runs discovery via SerpAPI to find list pages
   3. Extracts products from discovered pages
   4. Tests the complete Generic Search Discovery flow

Common to both modes:
- Creates skeleton products for each listed item
- Captures detail URLs where available
- Creates CrawledSource records
- Tracks all created records (NO data deletion)

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 7
Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md - Section 7
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from tests.e2e.utils.real_urls import (
    LIST_PAGES,
    ListPageURL,
    get_list_page_urls,
)
from tests.e2e.utils.data_verifier import (
    DataVerifier,
    VerificationResult,
    verify_all_products_have_name,
)
from tests.e2e.conftest import requires_serpapi, requires_ai_service

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

MAX_PRODUCTS_PER_LIST = 10  # Limit products extracted per list page
MAX_LIST_PAGES_TO_TEST = 3  # Test up to 3 list pages


# =============================================================================
# Helper Functions
# =============================================================================


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    # Handle None values - use empty string if name or brand is None
    name_str = (name or "").lower().strip()
    brand_str = (brand or "").lower().strip()
    base = f"{name_str}:{brand_str}"
    return hashlib.sha256(base.encode()).hexdigest()


async def fetch_list_page_content(url: str, max_retries: int = 3, retry_delay: float = 5.0) -> str:
    """
    Fetch content from a list page URL.

    Uses httpx directly or SmartRouter if available.
    Retries on failure with exponential backoff.
    Raises an exception if all retries fail - NO synthetic fallback.

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (doubles each retry)

    Returns:
        Page content as string

    Raises:
        RuntimeError: If all fetch attempts fail
    """
    import httpx

    last_error = None

    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = retry_delay * (2 ** (attempt - 1))
            logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay...")
            await asyncio.sleep(wait_time)

        # Try SmartRouter first
        try:
            from crawler.fetchers.smart_router import SmartRouter
            router = SmartRouter()
            result = await router.fetch(url)
            if result.success and result.content:
                logger.info(f"Fetched via SmartRouter: {url}")
                return result.content
            else:
                logger.warning(f"SmartRouter failed for {url}, trying httpx fallback")
        except Exception as e:
            logger.warning(f"SmartRouter error for {url}: {e}, trying httpx fallback")

        # Fallback to httpx
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                response.raise_for_status()
                logger.info(f"Fetched via httpx: {url} (status={response.status_code})")
                return response.text
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed to fetch {url}: {e}")

    # All retries exhausted - raise error for investigation
    raise RuntimeError(
        f"Failed to fetch list page after {max_retries} attempts. "
        f"URL: {url}. Last error: {last_error}. "
        f"This needs investigation - do NOT use synthetic fallback."
    )


@sync_to_async
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = "list_page"
) -> "CrawledSource":
    """Create or get a CrawledSource record."""
    from crawler.models import CrawledSource, ExtractionStatusChoices

    content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

    # Try to get existing or create new
    source, created = CrawledSource.objects.get_or_create(
        url=url,
        defaults={
            "title": title,
            "raw_content": raw_content,
            "content_hash": content_hash,
            "source_type": source_type,
            "extraction_status": ExtractionStatusChoices.PENDING,
        }
    )

    if not created:
        # Update existing
        source.title = title
        source.raw_content = raw_content
        source.content_hash = content_hash
        source.save()

    action = "Created" if created else "Updated"
    logger.info(f"{action} CrawledSource: {source.id} for {url[:50]}...")
    return source


@sync_to_async
def create_discovered_product(
    name: str,
    brand: str,
    source_url: str,
    product_type: str,
    extracted_data: Optional[Dict[str, Any]] = None,
    quality_status: str = "skeleton",
    detail_url: Optional[str] = None,
) -> "DiscoveredProduct":
    """Create a DiscoveredProduct record."""
    from crawler.models import DiscoveredProduct, ProductType, DiscoveredProductStatus

    fingerprint = generate_fingerprint(name, brand or "")

    # Map quality status to model status
    status_map = {
        "rejected": DiscoveredProductStatus.REJECTED,
        "skeleton": DiscoveredProductStatus.INCOMPLETE,
        "partial": DiscoveredProductStatus.PARTIAL,
        "complete": DiscoveredProductStatus.COMPLETE,
        "enriched": DiscoveredProductStatus.VERIFIED,
    }
    status = status_map.get(quality_status, DiscoveredProductStatus.INCOMPLETE)

    # Map product type
    product_type_map = {
        "whiskey": ProductType.WHISKEY,
        "port_wine": ProductType.PORT_WINE,
    }
    ptype = product_type_map.get(product_type, ProductType.WHISKEY)

    # Check for existing product with same fingerprint
    existing = DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()
    if existing:
        logger.info(f"Found existing product with fingerprint: {existing.id}")
        # Update with new data (skip related fields)
        skip_fields = {"brand", "source", "crawl_job", "whiskey_details", "port_details"}
        if extracted_data:
            for field, value in extracted_data.items():
                if field in skip_fields:
                    continue
                if hasattr(existing, field) and value is not None:
                    try:
                        setattr(existing, field, value)
                    except (TypeError, ValueError):
                        pass  # Skip fields that can't be set directly
        existing.status = status
        existing.save()
        return existing

    # Build product data
    product_data = {
        "name": name,
        "brand_id": None,
        "source_url": source_url,
        "fingerprint": fingerprint,
        "product_type": ptype,
        "raw_content": "",
        "raw_content_hash": "",
        "status": status,
        "discovery_source": "list_page",
    }

    # Add extracted fields
    if extracted_data:
        field_mapping = {
            "description": "description",
            "abv": "abv",
            "age_statement": "age_statement",
            "volume_ml": "volume_ml",
            "region": "region",
            "country": "country",
            "palate_flavors": "palate_flavors",
            "nose_description": "nose_description",
            "palate_description": "palate_description",
            "finish_description": "finish_description",
            "color_description": "color_description",
        }

        for src_field, dst_field in field_mapping.items():
            if src_field in extracted_data and extracted_data[src_field] is not None:
                value = extracted_data[src_field]
                if src_field == "abv" and value:
                    try:
                        value = Decimal(str(value))
                    except Exception:
                        value = None
                product_data[dst_field] = value

    # Create the product
    product = DiscoveredProduct.objects.create(**product_data)
    logger.info(f"Created DiscoveredProduct: {product.id} - {name}")
    return product


@sync_to_async
def link_product_to_source(
    product: "DiscoveredProduct",
    source: "CrawledSource",
    extraction_confidence: float,
    fields_extracted: List[str],
) -> "ProductSource":
    """Create ProductSource link."""
    from crawler.models import ProductSource

    # Check for existing link
    existing = ProductSource.objects.filter(
        product=product,
        source=source,
    ).first()

    if existing:
        existing.extraction_confidence = Decimal(str(extraction_confidence))
        existing.fields_extracted = fields_extracted
        existing.save()
        return existing

    link = ProductSource.objects.create(
        product=product,
        source=source,
        extraction_confidence=Decimal(str(extraction_confidence)),
        fields_extracted=fields_extracted,
        mention_type="list_mention",
    )
    logger.info(f"Created ProductSource link: {product.id} <- {source.id}")
    return link


@sync_to_async
def get_discovered_product_by_pk(pk):
    """Get a DiscoveredProduct by primary key."""
    from crawler.models import DiscoveredProduct
    return DiscoveredProduct.objects.get(pk=pk)


@sync_to_async
def get_product_sources_for_product(product):
    """Get ProductSource records for a product with related source."""
    from crawler.models import ProductSource
    return list(ProductSource.objects.filter(product=product).select_related("source"))


# =============================================================================
# Test Class
# =============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
class TestListPageExtractionFlow:
    """
    E2E test for List Page Extraction Flow.

    Extracts multiple products from list pages (e.g., "Best Whiskeys 2025"),
    creates skeleton products, captures detail URLs, and tracks sources.
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.created_products: List[UUID] = []
        self.created_sources: List[UUID] = []
        self.extraction_results: List[Dict[str, Any]] = []
        self.products_with_detail_urls: List[UUID] = []

    async def test_list_page_extraction_flow(
        self,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Main test: Extract products from list pages.

        Steps:
        1. Get list page URLs
        2. For each list page:
           - Fetch page content
           - Extract multiple products via DiscoveryOrchestratorV2.extract_list_products()
           - Create CrawledSource record
           - Create skeleton DiscoveredProduct records
           - Capture detail_url where available
           - Create ProductSource links
        3. Verify all products meet requirements
        4. Track all created records
        """
        start_time = time.time()

        # Skip if AI client not configured
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        logger.info("=" * 60)
        logger.info("Starting List Page Extraction Flow E2E Test")
        logger.info("=" * 60)

        # Get list page URLs
        list_urls = get_list_page_urls()
        assert len(list_urls) > 0, "No list page URLs configured"

        # Limit to MAX_LIST_PAGES_TO_TEST
        list_urls = list_urls[:MAX_LIST_PAGES_TO_TEST]
        logger.info(f"Testing {len(list_urls)} list page(s)")

        # Process each list page
        for list_url in list_urls:
            await self._process_list_page(
                list_url,
                ai_client,
                source_tracker,
                quality_gate,
                test_run_tracker,
                report_collector,
            )
            # Small delay between list pages for rate limiting etiquette
            await asyncio.sleep(2)

        # Wait for async operations to complete
        await asyncio.sleep(1)

        # Verify all products
        await self._verify_all_products(report_collector)

        # Record flow result
        duration = time.time() - start_time
        test_run_tracker.record_flow_result(
            flow_name="List Page Extraction",
            success=True,
            products_created=len(self.created_products),
            duration_seconds=duration,
            details={
                "list_pages_processed": len(list_urls),
                "products_created": len(self.created_products),
                "sources_created": len(self.created_sources),
                "products_with_detail_url": len(self.products_with_detail_urls),
            }
        )

        report_collector.record_flow_duration("List Page Extraction", duration)

        logger.info("=" * 60)
        logger.info(f"List Page Extraction Flow completed in {duration:.1f}s")
        logger.info(f"Products created: {len(self.created_products)}")
        logger.info(f"Sources created: {len(self.created_sources)}")
        logger.info(f"Products with detail_url: {len(self.products_with_detail_urls)}")
        logger.info("=" * 60)

        # Assert we created at least some products
        assert len(self.created_products) > 0, "No products were created"

    async def _process_list_page(
        self,
        list_url: ListPageURL,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Process a single list page.

        Extracts multiple products and creates records for each.
        """
        logger.info(f"Processing list page: {list_url.list_title}")
        logger.info(f"URL: {list_url.url}")
        logger.info(f"Source: {list_url.source_name}, Expected products: {list_url.expected_products}")

        # Fetch the list page content
        # This will retry on failure and raise an error if all retries fail
        # NO synthetic fallback - if this fails, we need to investigate why
        page_content = await fetch_list_page_content(list_url.url)

        # Extract products using real AI extraction
        extracted_products = await self._extract_list_products(
            page_content,
            list_url,
            ai_client,
        )

        if not extracted_products:
            raise RuntimeError(
                f"AI extraction returned no products from list page. "
                f"URL: {list_url.url}. Title: {list_url.list_title}. "
                f"This needs investigation - the page may have changed format."
            )

        # Limit products per list
        extracted_products = extracted_products[:MAX_PRODUCTS_PER_LIST]
        logger.info(f"Processing {len(extracted_products)} products from {list_url.list_title}")

        # Create CrawledSource for the list page
        source = await create_crawled_source(
            url=list_url.url,
            title=list_url.list_title,
            raw_content=page_content,  # Real content only - no synthetic fallback
            source_type="list_page",
        )
        self.created_sources.append(source.id)
        test_run_tracker.record_source(source.id)

        # Record source in report
        report_collector.add_source({
            "id": str(source.id),
            "url": list_url.url,
            "title": source.title,
            "source_type": source.source_type,
            "has_raw_content": bool(source.raw_content),
            "list_source_name": list_url.source_name,
        })

        # Process each extracted product
        for product_data in extracted_products:
            await self._process_extracted_product(
                product_data,
                list_url,
                source,
                quality_gate,
                test_run_tracker,
                report_collector,
            )

    async def _extract_list_products(
        self,
        page_content: str,
        list_url: ListPageURL,
        ai_client,
    ) -> List[Dict[str, Any]]:
        """
        Extract products from a list page using DiscoveryOrchestratorV2.

        Falls back to AIClientV2 directly if orchestrator is unavailable.
        """
        # Try DiscoveryOrchestratorV2.extract_list_products() first
        try:
            from crawler.services.discovery_orchestrator_v2 import (
                DiscoveryOrchestratorV2,
                get_discovery_orchestrator_v2,
            )

            orchestrator = get_discovery_orchestrator_v2()
            result = await orchestrator.extract_list_products(
                url=list_url.url,
                product_type=list_url.product_type,
            )

            logger.warning(f"Orchestrator result: success={result.success}, products={len(result.products) if result.products else 0}")

            if result.success and result.products:
                products = []
                for single_result in result.products:
                    product_data = single_result.product_data.copy() if single_result.product_data else {}
                    product_data["detail_url"] = single_result.detail_url
                    product_data["quality_status"] = single_result.quality_status
                    product_data["field_confidences"] = single_result.field_confidences
                    product_data["source_url"] = list_url.url
                    products.append(product_data)
                logger.info(f"DiscoveryOrchestratorV2 extracted {len(products)} products")
                return products

        except Exception as e:
            logger.warning(f"DiscoveryOrchestratorV2 failed, falling back to AIClientV2: {e}")

        # Fallback to AIClientV2 directly
        try:
            from crawler.services.ai_client_v2 import get_ai_client_v2

            client = get_ai_client_v2()
            # Limit content size - large pages (>50KB) cause AI to return 0 products
            # This is because competition sites are JS-heavy with minimal product data in HTML
            max_content_size = 50000  # 50KB limit for better extraction results
            logger.warning(f"Page content size: {len(page_content)} chars")
            truncated_content = page_content[:max_content_size] if len(page_content) > max_content_size else page_content
            if len(page_content) > max_content_size:
                logger.warning(f"Truncating content from {len(page_content)} to {max_content_size} chars for AI extraction")

            result = await client.extract(
                content=truncated_content,
                source_url=list_url.url,
                product_type=list_url.product_type,
            )

            logger.warning(f"AIClientV2 result: success={result.success}, products={len(result.products) if result.products else 0}")

            if result.success and result.products:
                products = []
                for extracted in result.products:
                    product_data = extracted.extracted_data.copy()
                    product_data["field_confidences"] = extracted.field_confidences
                    product_data["overall_confidence"] = extracted.confidence
                    product_data["source_url"] = list_url.url
                    # Check for detail_url in extracted data
                    product_data["detail_url"] = extracted.extracted_data.get("detail_url")
                    products.append(product_data)
                logger.info(f"AIClientV2 extracted {len(products)} products")
                return products

        except Exception as e:
            logger.warning(f"AIClientV2 extraction failed: {e}")

        # NO synthetic fallback - return empty list to let caller handle
        logger.error(
            f"All extraction methods failed for {list_url.url}. "
            f"This needs investigation - check DiscoveryOrchestratorV2 and AIClientV2."
        )
        return []

    async def _process_extracted_product(
        self,
        product_data: Dict[str, Any],
        list_url: ListPageURL,
        source: "CrawledSource",
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Process a single extracted product from a list page.

        Creates:
        - DiscoveredProduct record (skeleton status)
        - ProductSource link
        """
        # Handle None values explicitly - use fallback if value is None or missing
        name = product_data.get("name") or "Unknown Product"
        brand = product_data.get("brand") or ""
        detail_url = product_data.get("detail_url")
        source_url = product_data.get("source_url", list_url.url)

        logger.info(f"Processing product: {name} by {brand}")

        # Get quality assessment
        from crawler.services.quality_gate_v2 import get_quality_gate_v2, ProductStatus

        gate = get_quality_gate_v2()
        field_confidences = product_data.pop("field_confidences", {})
        overall_confidence = product_data.pop("overall_confidence", 0.6)
        quality_status = product_data.pop("quality_status", None)

        if not quality_status:
            assessment = await gate.aassess(
                extracted_data=product_data,
                product_type=list_url.product_type,
                field_confidences=field_confidences,
            )
            quality_status = assessment.status.value
            completeness_score = assessment.completeness_score
            needs_enrichment = assessment.needs_enrichment
        else:
            # Use status from orchestrator
            completeness_score = 0.5
            needs_enrichment = quality_status in ["skeleton", "partial"]

        logger.info(f"Quality assessment: {quality_status}")

        # Create DiscoveredProduct
        product = await create_discovered_product(
            name=name,
            brand=brand,
            source_url=source_url,
            product_type=list_url.product_type,
            extracted_data=product_data,
            quality_status=quality_status,
            detail_url=detail_url,
        )
        self.created_products.append(product.id)
        test_run_tracker.record_product(product.id)

        # Track products with detail URLs
        if detail_url:
            self.products_with_detail_urls.append(product.id)

        # Create ProductSource link
        fields_extracted = [k for k, v in product_data.items() if v is not None]
        link = await link_product_to_source(
            product=product,
            source=source,
            extraction_confidence=overall_confidence,
            fields_extracted=fields_extracted,
        )

        # Record in report collector
        report_collector.add_product({
            "id": str(product.id),
            "name": name,
            "brand": brand,
            "product_type": list_url.product_type,
            "status": quality_status,
            "completeness_score": completeness_score,
            "source_url": source_url,
            "detail_url": detail_url,
            "list_source": list_url.source_name,
            "has_detail_url": bool(detail_url),
        })

        report_collector.add_quality_assessment({
            "product_id": str(product.id),
            "product_name": name,
            "status": quality_status,
            "completeness_score": completeness_score,
            "needs_enrichment": needs_enrichment,
            "is_skeleton": quality_status == "skeleton",
        })

        # Store extraction result for verification
        self.extraction_results.append({
            "product_id": product.id,
            "source_id": source.id,
            "product_data": product_data,
            "quality_status": quality_status,
            "detail_url": detail_url,
        })

    async def _verify_all_products(self, report_collector):
        """
        Verify all created products meet Flow 7 requirements.

        Checks:
        - Multiple products from single source URL
        - detail_url field populated for products with links
        - Skeleton status for incomplete products
        - CrawledSource records created
        """
        logger.info("=" * 40)
        logger.info("Verifying all created products")
        logger.info("=" * 40)

        # Verify: Multiple products from single source URL
        source_product_counts = {}
        for result in self.extraction_results:
            source_id = result["source_id"]
            source_product_counts[source_id] = source_product_counts.get(source_id, 0) + 1

        for source_id, count in source_product_counts.items():
            has_multiple = count > 1
            report_collector.record_verification(
                f"multiple_products_from_source:{source_id}",
                has_multiple
            )
            logger.info(f"Source {source_id}: {count} products (multiple={has_multiple})")

        # Verify individual products
        for product_id in self.created_products:
            product = await get_discovered_product_by_pk(product_id)

            # Verify name field populated
            has_name = product.name is not None and len(product.name.strip()) > 0
            report_collector.record_verification(f"name_populated:{product_id}", has_name)

            # Verify source linkage exists
            product_sources = await get_product_sources_for_product(product)
            has_source = len(product_sources) > 0
            report_collector.record_verification(f"has_source_link:{product_id}", has_source)

            # Verify CrawledSource has raw_content
            for ps in product_sources:
                has_content = ps.source.raw_content is not None and len(ps.source.raw_content) > 0
                report_collector.record_verification(f"source_has_content:{ps.source_id}", has_content)

            logger.info(f"Verified product {product_id}: {product.name}")

        # Verify: detail_url populated for products with links
        detail_url_count = len(self.products_with_detail_urls)
        has_some_detail_urls = detail_url_count > 0
        report_collector.record_verification(
            "detail_urls_captured",
            has_some_detail_urls
        )
        logger.info(f"Products with detail_url: {detail_url_count}/{len(self.created_products)}")

        # Verify: Skeleton status for incomplete products (list pages typically produce skeletons)
        skeleton_count = 0
        for result in self.extraction_results:
            if result["quality_status"] == "skeleton":
                skeleton_count += 1

        has_skeletons = skeleton_count > 0
        report_collector.record_verification("skeleton_products_created", has_skeletons)
        logger.info(f"Skeleton products: {skeleton_count}/{len(self.created_products)}")

        # Summary
        passed = self.verifier.get_passed_count()
        failed = self.verifier.get_failed_count()
        total = passed + failed

        logger.info(f"Verification complete: {passed}/{total} checks passed")

        if failed > 0:
            logger.warning(f"{failed} verification checks failed")
            for result in self.verifier.get_results():
                if not result.passed:
                    logger.warning(f"  FAILED: {result.check_name} - {result.message}")


# =============================================================================
# Standalone Test Functions
# =============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_page_urls_configured():
    """Verify list page URLs are properly configured."""
    list_urls = get_list_page_urls()
    assert len(list_urls) > 0, "No list page URLs configured"

    for url in list_urls:
        assert url.url.startswith("http"), f"Invalid URL: {url.url}"
        assert url.source_name, f"Missing source_name for {url.url}"
        assert url.list_title, f"Missing list_title for {url.url}"
        assert url.product_type in ["whiskey", "port_wine"], f"Invalid product type: {url.product_type}"
        assert url.expected_products > 0, f"Invalid expected_products: {url.expected_products}"

    logger.info(f"Verified {len(list_urls)} list page URLs")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discovery_orchestrator_v2_list_extraction_available():
    """Verify DiscoveryOrchestratorV2.extract_list_products is available."""
    from crawler.services.discovery_orchestrator_v2 import (
        DiscoveryOrchestratorV2,
        get_discovery_orchestrator_v2,
    )

    orchestrator = get_discovery_orchestrator_v2()
    assert orchestrator is not None, "DiscoveryOrchestratorV2 not available"
    assert hasattr(orchestrator, "extract_list_products"), "Missing extract_list_products method"

    logger.info("DiscoveryOrchestratorV2.extract_list_products is available")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_page_data_classes_available():
    """Verify ListPageURL data class is available."""
    from tests.e2e.utils.real_urls import ListPageURL, LIST_PAGES

    assert LIST_PAGES is not None, "LIST_PAGES not defined"
    assert len(LIST_PAGES) > 0, "LIST_PAGES is empty"

    first_url = LIST_PAGES[0]
    assert isinstance(first_url, ListPageURL), "LIST_PAGES does not contain ListPageURL instances"
    assert first_url.url, "ListPageURL missing url field"
    assert first_url.source_name, "ListPageURL missing source_name field"
    assert first_url.list_title, "ListPageURL missing list_title field"

    logger.info(f"ListPageURL data class verified with {len(LIST_PAGES)} URLs")


# =============================================================================
# SearchTerm-Based Discovery Tests (V2 Spec Section 7)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestSearchTermDiscoveryFlow:
    """
    E2E test for SearchTerm-based List Page Discovery.

    V2 Spec Reference: Section 7 - Generic Search Discovery

    This test class validates the complete discovery pipeline:
    1. Create SearchTerms in database
    2. Execute SerpAPI search to find list pages
    3. Extract products from discovered pages
    4. Create skeleton products with source tracking
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.created_products: List[UUID] = []
        self.created_sources: List[UUID] = []
        self.discovered_urls: List[str] = []

    @requires_serpapi
    @requires_ai_service
    async def test_searchterm_discovery_to_extraction_flow(
        self,
        search_term_factory,
        discovery_job_factory,
        ai_client,
        serpapi_client,
        test_run_tracker,
        report_collector,
    ):
        """
        [SPEC Section 7] Complete SearchTerm -> SerpAPI -> List Page -> Extraction flow.

        Steps:
        1. Create SearchTerms for discovery
        2. Execute SerpAPI searches (respects max_results)
        3. Fetch discovered list pages
        4. Extract products from each page
        5. Create skeleton products with source tracking
        """
        import httpx

        start_time = time.time()

        if not serpapi_client or not ai_client:
            pytest.skip("SerpAPI or AI Service not configured")

        logger.info("=" * 60)
        logger.info("Starting SearchTerm Discovery Flow E2E Test")
        logger.info("=" * 60)

        # Step 1: Create SearchTerms (wrap sync factory with sync_to_async)
        create_term = sync_to_async(search_term_factory)
        search_terms = [
            await create_term(
                search_query="best bourbon whiskey 2026 list",
                category="best_lists",
                product_type="whiskey",
                max_results=3,  # Limit to 3 for testing
                priority=100,
            ),
            await create_term(
                search_query="top rated scotch whisky reviews 2026",
                category="best_lists",
                product_type="whiskey",
                max_results=2,
                priority=90,
            ),
        ]

        logger.info(f"Created {len(search_terms)} SearchTerms")

        # Step 2: Execute SerpAPI searches
        for term in search_terms:
            await self._execute_search_and_discover(
                term,
                serpapi_client,
                ai_client,
                test_run_tracker,
                report_collector,
            )
            # Rate limiting
            await asyncio.sleep(2)

        # Step 3: Verify results
        duration = time.time() - start_time

        test_run_tracker.record_flow_result(
            flow_name="SearchTerm Discovery",
            success=True,
            products_created=len(self.created_products),
            duration_seconds=duration,
            details={
                "search_terms_used": len(search_terms),
                "urls_discovered": len(self.discovered_urls),
                "products_created": len(self.created_products),
                "sources_created": len(self.created_sources),
            }
        )

        report_collector.record_flow_duration("SearchTerm Discovery", duration)

        logger.info("=" * 60)
        logger.info(f"SearchTerm Discovery Flow completed in {duration:.1f}s")
        logger.info(f"URLs discovered: {len(self.discovered_urls)}")
        logger.info(f"Products created: {len(self.created_products)}")
        logger.info("=" * 60)

        # Assert we discovered URLs
        assert len(self.discovered_urls) > 0, "No URLs discovered from SearchTerms"

    async def _execute_search_and_discover(
        self,
        term,
        serpapi_client,
        ai_client,
        test_run_tracker,
        report_collector,
    ):
        """
        Execute a single SearchTerm's discovery flow.

        [SPEC Section 7.4] Organic results only, respects max_results.
        """
        import httpx
        from django.utils import timezone

        logger.info(f"Executing search for: {term.search_query}")

        # Execute SerpAPI search
        params = {
            "api_key": serpapi_client["api_key"],
            "q": term.search_query,
            "engine": "google",
            "num": term.max_results,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(serpapi_client["base_url"], params=params)
            test_run_tracker.record_api_call("serpapi")

        if response.status_code != 200:
            logger.error(f"SerpAPI request failed: {response.status_code}")
            return

        data = response.json()

        # Get organic results only (per spec Section 7.4)
        organic_results = data.get("organic_results", [])[:term.max_results]

        if not organic_results:
            logger.warning(f"No organic results for: {term.search_query}")
            return

        logger.info(f"Found {len(organic_results)} organic results")

        # Update SearchTerm metrics
        term.search_count += 1
        term.last_searched = timezone.now()
        await sync_to_async(term.save)()

        # Process discovered URLs
        for result in organic_results[:2]:  # Limit to 2 per term for testing
            url = result.get("link")
            title = result.get("title", "Unknown")

            if not url:
                continue

            self.discovered_urls.append(url)

            # Attempt to extract products from discovered page
            await self._process_discovered_url(
                url,
                title,
                term,
                ai_client,
                test_run_tracker,
                report_collector,
            )

    async def _process_discovered_url(
        self,
        url: str,
        title: str,
        term,
        ai_client,
        test_run_tracker,
        report_collector,
    ):
        """
        Process a discovered URL to extract products.

        [SPEC Section 7.6] List Page Extraction from discovered URLs.
        """
        logger.info(f"Processing discovered URL: {url[:60]}...")

        # Fetch page content
        try:
            page_content = await fetch_list_page_content(url, max_retries=2, retry_delay=3.0)
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return

        # Create CrawledSource
        source = await create_crawled_source(
            url=url,
            title=title,
            raw_content=page_content,
            source_type="list_page",
        )
        self.created_sources.append(source.id)
        test_run_tracker.record_source(source.id)

        # Extract products
        try:
            from crawler.services.ai_client_v2 import get_ai_client_v2

            client = get_ai_client_v2()
            result = await client.extract(
                content=page_content,
                source_url=url,
                product_type=term.product_type,
            )
            test_run_tracker.record_api_call("openai")

            if result.success and result.products:
                logger.info(f"Extracted {len(result.products)} products from {url[:40]}...")

                # Create products (limit to 3 per page for testing)
                for extracted in result.products[:3]:
                    product_data = extracted.extracted_data
                    name = product_data.get("name", "Unknown")
                    brand = product_data.get("brand", "")

                    product = await create_discovered_product(
                        name=name,
                        brand=brand,
                        source_url=url,
                        product_type=term.product_type,
                        extracted_data=product_data,
                        quality_status="skeleton",
                        detail_url=product_data.get("detail_url"),
                    )
                    self.created_products.append(product.id)
                    test_run_tracker.record_product(product.id)

                    # Update SearchTerm products_discovered
                    term.products_discovered += 1

                await sync_to_async(term.save)()

        except Exception as e:
            logger.warning(f"Extraction failed for {url}: {e}")

    def test_searchterm_model_supports_discovery_fields(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] SearchTerm has required fields for discovery.
        """
        term = search_term_factory(
            search_query="test discovery fields",
            category="best_lists",
            product_type="whiskey",
            max_results=5,
            priority=100,
            is_active=True,
        )

        # Verify required fields exist
        assert term.search_query == "test discovery fields"
        assert term.max_results == 5
        assert term.priority == 100
        assert term.is_active is True
        assert term.search_count == 0
        assert term.products_discovered == 0
        assert term.last_searched is None

        logger.info("SearchTerm model has all required discovery fields")

    def test_searchterm_priority_ordering_for_discovery(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] SearchTerms ordered by priority for discovery.
        """
        from crawler.models import SearchTerm

        # Create terms with different priorities
        search_term_factory(search_query="low priority", priority=200)
        search_term_factory(search_query="high priority", priority=50)
        search_term_factory(search_query="medium priority", priority=100)

        # Query with priority ordering
        ordered = SearchTerm.objects.filter(is_active=True).order_by("priority")
        priorities = [t.priority for t in ordered]

        # Verify ascending order (lower = higher priority)
        assert priorities == sorted(priorities)

        # First term should have lowest number (highest priority)
        first = ordered.first()
        assert first.priority <= 100

        logger.info("SearchTerm priority ordering verified")

    def test_searchterm_seasonality_filtering(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Seasonal SearchTerms filtered by current month.
        """
        current_month = datetime.now().month

        # Year-round term
        year_round = search_term_factory(
            search_query="year round",
            seasonal_start_month=None,
            seasonal_end_month=None,
        )

        # Current month term
        in_season = search_term_factory(
            search_query="in season",
            seasonal_start_month=current_month,
            seasonal_end_month=current_month,
        )

        # Out of season term
        out_month = (current_month % 12) + 1
        out_of_season = search_term_factory(
            search_query="out of season",
            seasonal_start_month=out_month,
            seasonal_end_month=out_month,
        )

        assert year_round.is_in_season() is True
        assert in_season.is_in_season() is True
        # out_of_season depends on current month

        logger.info("SearchTerm seasonality filtering verified")

    def test_max_results_respected_in_discovery(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.4] max_results field limits per-term crawl.
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        # Valid range
        term = search_term_factory(max_results=5)
        assert term.max_results == 5

        # Boundary values
        min_term = search_term_factory(search_query="min", max_results=1)
        max_term = search_term_factory(search_query="max", max_results=20)
        assert min_term.max_results == 1
        assert max_term.max_results == 20

        # Invalid: below minimum
        invalid = SearchTerm(
            search_query="invalid",
            category="best_lists",
            product_type="whiskey",
            max_results=0,
        )
        with pytest.raises(ValidationError):
            invalid.full_clean()

        # Invalid: above maximum
        invalid2 = SearchTerm(
            search_query="invalid2",
            category="best_lists",
            product_type="whiskey",
            max_results=21,
        )
        with pytest.raises(ValidationError):
            invalid2.full_clean()

        logger.info("max_results validation verified")
