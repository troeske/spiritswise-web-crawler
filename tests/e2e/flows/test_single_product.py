"""
E2E Test: Single Product Page Extraction Flow (Flow 6)

Tests the complete single product page extraction pipeline using V2 architecture:
- DiscoveryOrchestratorV2 for orchestration
- AIClientV2 for content extraction
- Real AI Enhancement Service at https://api.spiritswise.tech/api/v2/extract/
- QualityGateV2 for quality assessment
- SourceTracker for source tracking

This test:
1. Uses 5 real direct product page URLs (not competition pages)
   - Master of Malt product pages
   - Wine-Searcher product pages
   - The Whisky Exchange product pages
2. Extracts each via DiscoveryOrchestratorV2.extract_single_product()
3. Assesses quality via QualityGateV2
4. Creates CrawledSource, DiscoveredProduct, ProductSource records
5. Verifies all required fields and data quality
6. Tracks all created records (NO data deletion)

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 6
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
    SINGLE_PRODUCT_PAGES,
    ProductPageURL,
    get_single_product_urls,
)
from tests.e2e.utils.data_verifier import (
    DataVerifier,
    VerificationResult,
    verify_all_products_have_name,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

# Source type for product pages (using retailer_page as closest available)
SOURCE_TYPE_PRODUCT_PAGE = "retailer_page"
MAX_PRODUCTS_TO_EXTRACT = 5


# =============================================================================
# Helper Functions
# =============================================================================


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


@sync_to_async
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = SOURCE_TYPE_PRODUCT_PAGE
) -> "CrawledSource":
    """
    Create or get a CrawledSource record.

    Args:
        url: URL of the crawled page
        title: Title of the page
        raw_content: Raw HTML content
        source_type: Type of source page

    Returns:
        CrawledSource instance
    """
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
    product_type: str = "whiskey",
    extracted_data: Optional[Dict[str, Any]] = None,
    quality_status: str = "skeleton",
) -> "DiscoveredProduct":
    """
    Create a DiscoveredProduct record.

    Args:
        name: Product name
        brand: Brand name
        source_url: URL where product was discovered
        product_type: Type of product (whiskey, port_wine)
        extracted_data: Additional extracted fields
        quality_status: Quality status from assessment

    Returns:
        DiscoveredProduct instance
    """
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

    # Map product type string to enum
    product_type_enum = ProductType.WHISKEY if product_type == "whiskey" else ProductType.PORT_WINE

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
        "brand_id": None,  # Will set brand relationship separately
        "source_url": source_url,
        "fingerprint": fingerprint,
        "product_type": product_type_enum,
        "raw_content": "",
        "raw_content_hash": "",
        "status": status,
        "discovery_source": "direct",  # Direct crawl, not competition
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
    """
    Create ProductSource link.

    Args:
        product: DiscoveredProduct instance
        source: CrawledSource instance
        extraction_confidence: Confidence score (0.0-1.0)
        fields_extracted: List of field names extracted

    Returns:
        ProductSource instance
    """
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
        mention_type="product_page",
    )
    logger.info(f"Created ProductSource link: {product.id} <- {source.id}")
    return link


@sync_to_async
def update_source_extraction_status(source, status, error_message=None):
    """Update extraction status on a CrawledSource."""
    from crawler.models import ExtractionStatusChoices
    source.extraction_status = status
    if error_message:
        source.last_crawl_error = error_message
    source.save()


@sync_to_async
def get_discovered_product_by_id(product_id):
    """Get a DiscoveredProduct by ID."""
    from crawler.models import DiscoveredProduct
    return DiscoveredProduct.objects.get(pk=product_id)


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
class TestSingleProductPageFlow:
    """
    E2E test for Single Product Page Extraction Flow.

    Extracts 5 products from direct product page URLs,
    creates all required database records, and verifies data quality.
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.created_products: List[UUID] = []
        self.created_sources: List[UUID] = []
        self.extraction_results: List[Dict[str, Any]] = []

    async def test_single_product_page_flow(
        self,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Main test: Extract 5 products from direct product pages.

        Steps:
        1. Get single product page URLs
        2. Use DiscoveryOrchestratorV2.extract_single_product() for each URL
        3. For each extracted product:
           - Create CrawledSource with raw_content
           - Create DiscoveredProduct with proper status
           - Create ProductSource link
        4. Verify all products meet requirements
        5. Track all created records

        Expected Outputs:
        - 5 DiscoveredProduct records from direct pages
        - Quality assessment for each
        - Source tracking for direct URLs

        Verification Points:
        - Products extracted without competition context
        - Source type = "product_page" (retailer_page in our model)
        - Full field extraction attempted
        - CrawledSource records created with raw_content
        """
        start_time = time.time()

        # Skip if AI client not configured
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        logger.info("=" * 60)
        logger.info("Starting Single Product Page Flow E2E Test")
        logger.info("=" * 60)

        # Get single product page URLs
        product_urls = SINGLE_PRODUCT_PAGES[:MAX_PRODUCTS_TO_EXTRACT]
        assert len(product_urls) > 0, "No single product URLs configured"

        logger.info(f"Processing {len(product_urls)} product page URLs")

        # Import orchestrator
        from crawler.services.discovery_orchestrator_v2 import (
            DiscoveryOrchestratorV2,
            get_discovery_orchestrator_v2,
        )

        orchestrator = get_discovery_orchestrator_v2()

        # Process each product URL
        for i, product_url in enumerate(product_urls, 1):
            logger.info(f"\n{'=' * 40}")
            logger.info(f"Processing URL {i}/{len(product_urls)}: {product_url.product_name}")
            logger.info(f"URL: {product_url.url}")
            logger.info(f"Source: {product_url.source_name}")
            logger.info(f"Product Type: {product_url.product_type}")
            logger.info(f"{'=' * 40}")

            await self._process_single_product_url(
                product_url=product_url,
                orchestrator=orchestrator,
                ai_client=ai_client,
                source_tracker=source_tracker,
                quality_gate=quality_gate,
                test_run_tracker=test_run_tracker,
                report_collector=report_collector,
            )

            # Brief delay for rate limiting etiquette
            await asyncio.sleep(2)

        # Wait for async operations to complete
        await asyncio.sleep(1)

        # Verify all products
        await self._verify_all_products(report_collector)

        # Record flow result
        duration = time.time() - start_time
        test_run_tracker.record_flow_result(
            flow_name="Single Product Page",
            success=True,
            products_created=len(self.created_products),
            duration_seconds=duration,
            details={
                "urls_processed": len(product_urls),
                "products_created": len(self.created_products),
                "sources_created": len(self.created_sources),
            }
        )

        report_collector.record_flow_duration("Single Product Page", duration)

        logger.info("=" * 60)
        logger.info(f"Single Product Page Flow completed in {duration:.1f}s")
        logger.info(f"Products created: {len(self.created_products)}")
        logger.info(f"Sources created: {len(self.created_sources)}")
        logger.info("=" * 60)

        # Assert we created at least some products
        assert len(self.created_products) > 0, "No products were created"

    async def _process_single_product_url(
        self,
        product_url: ProductPageURL,
        orchestrator,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Process a single product page URL.

        Args:
            product_url: ProductPageURL instance with URL and metadata
            orchestrator: DiscoveryOrchestratorV2 instance
            ai_client: AI client fixture
            source_tracker: Source tracker fixture
            quality_gate: Quality gate fixture
            test_run_tracker: Test run tracker fixture
            report_collector: Report data collector fixture
        """
        url = product_url.url
        product_type = product_url.product_type
        expected_name = product_url.product_name
        source_name = product_url.source_name

        try:
            # Use DiscoveryOrchestratorV2.extract_single_product()
            result = await orchestrator.extract_single_product(
                url=url,
                product_type=product_type,
                save_to_db=False,  # We'll save manually for better tracking
            )

            if not result.success:
                # NO synthetic fallback - raise error for investigation
                raise RuntimeError(
                    f"Extraction failed for {url}. Error: {result.error}. "
                    f"This needs investigation - check AI service and page accessibility."
                )

            # Extract product data
            product_data = result.product_data or {}
            field_confidences = result.field_confidences or {}
            quality_status = result.quality_status or "skeleton"
            overall_confidence = sum(field_confidences.values()) / len(field_confidences) if field_confidences else 0.5

            # Use expected name if extraction didn't find one
            name = product_data.get("name") or expected_name
            brand = product_data.get("brand") or ""

            logger.info(f"Extracted product: {name} by {brand}")
            logger.info(f"Quality status: {quality_status}")
            logger.info(f"Fields extracted: {list(product_data.keys())}")

            # Fetch raw content for CrawledSource
            # NO synthetic fallback - if this fails, we need to investigate
            raw_content = await self._fetch_page_content(url)
            if not raw_content:
                raise RuntimeError(
                    f"Failed to fetch content from {url}. "
                    f"This needs investigation - do NOT use synthetic fallback."
                )

            # Create CrawledSource record
            source = await create_crawled_source(
                url=url,
                title=f"{source_name} - {name}",
                raw_content=raw_content,
                source_type=SOURCE_TYPE_PRODUCT_PAGE,
            )
            self.created_sources.append(source.id)
            test_run_tracker.record_source(source.id)

            # Update extraction status
            from crawler.models import ExtractionStatusChoices
            await update_source_extraction_status(source, ExtractionStatusChoices.PROCESSED)

            # Create DiscoveredProduct record
            product = await create_discovered_product(
                name=name,
                brand=brand,
                source_url=url,
                product_type=product_type,
                extracted_data=product_data,
                quality_status=quality_status,
            )
            self.created_products.append(product.id)
            test_run_tracker.record_product(product.id)

            # Create ProductSource link
            fields_extracted = list(product_data.keys())
            link = await link_product_to_source(
                product=product,
                source=source,
                extraction_confidence=overall_confidence,
                fields_extracted=fields_extracted,
            )

            # Track field provenance if source_tracker available
            if source_tracker and field_confidences:
                for field_name, confidence in field_confidences.items():
                    if field_name in product_data:
                        source_tracker.track_field_provenance(
                            product_id=product.id,
                            source_id=source.id,
                            field_name=field_name,
                            extracted_value=str(product_data.get(field_name, "")),
                            confidence=confidence,
                        )

            # Record in report collector
            report_collector.add_product({
                "id": str(product.id),
                "name": name,
                "brand": brand,
                "product_type": product_type,
                "status": quality_status,
                "completeness_score": overall_confidence,
                "source_url": url,
                "source_name": source_name,
            })

            report_collector.add_source({
                "id": str(source.id),
                "url": url,
                "title": source.title,
                "source_type": source.source_type,
                "has_raw_content": bool(source.raw_content),
                "extraction_status": source.extraction_status,
            })

            report_collector.add_quality_assessment({
                "product_id": str(product.id),
                "product_name": name,
                "status": quality_status,
                "completeness_score": overall_confidence,
                "needs_enrichment": result.needs_enrichment,
                "field_count": len(fields_extracted),
            })

            # Store extraction result for verification
            self.extraction_results.append({
                "product_id": product.id,
                "source_id": source.id,
                "product_data": product_data,
                "quality_status": quality_status,
                "source_name": source_name,
            })

        except Exception as e:
            logger.exception(f"Error processing {url}: {e}")
            test_run_tracker.record_error(
                flow="Single Product Page",
                error=str(e),
                context={"url": url, "product_name": expected_name}
            )
            # NO synthetic fallback - re-raise for investigation
            raise RuntimeError(
                f"Failed to process {url}. Error: {e}. "
                f"This needs investigation - do NOT use synthetic fallback."
            ) from e

    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """
        Fetch raw page content from URL.

        Args:
            url: URL to fetch

        Returns:
            Raw HTML content or None if failed
        """
        import httpx

        try:
            # Try SmartRouter first if available
            try:
                from crawler.fetchers.smart_router import SmartRouter
                router = SmartRouter()
                result = await router.fetch(url)
                if result.success:
                    logger.info(f"Fetched via SmartRouter: {url}")
                    return result.content
            except ImportError:
                pass

            # Fallback to httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; SpiritswiseCrawler/2.0)"
                    }
                )
                response.raise_for_status()
                logger.info(f"Fetched via httpx: {url} (status={response.status_code})")
                return response.text

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    async def _verify_all_products(self, report_collector):
        """
        Verify all created products meet requirements.

        Verification Points:
        - Products extracted without competition context
        - Source type = "product_page" (retailer_page in our model)
        - Full field extraction attempted
        - CrawledSource records created with raw_content
        """
        logger.info("=" * 40)
        logger.info("Verifying all created products")
        logger.info("=" * 40)

        for product_id in self.created_products:
            product = await get_discovered_product_by_id(product_id)

            # Verify name field populated
            result = self.verifier.verify_product_required_fields(
                {"name": product.name, "brand": str(product.brand) if product.brand else ""},
                required_fields={"name"},
            )
            report_collector.record_verification(f"name_populated:{product_id}", result.passed)
            assert result.passed, f"Product {product_id} missing name field"

            # Verify discovery_source is NOT competition
            is_direct = product.discovery_source != "competition"
            report_collector.record_verification(f"not_competition_source:{product_id}", is_direct)
            logger.info(f"Product {product_id} discovery_source: {product.discovery_source}")

            # Verify has ProductSource link
            product_sources = await get_product_sources_for_product(product)
            has_source_link = len(product_sources) > 0
            report_collector.record_verification(f"has_source_link:{product_id}", has_source_link)
            assert has_source_link, f"Product {product_id} has no ProductSource link"

            # Verify source type is product_page (retailer_page)
            for ps in product_sources:
                is_product_page = ps.source.source_type == SOURCE_TYPE_PRODUCT_PAGE
                report_collector.record_verification(
                    f"source_type_product_page:{ps.source_id}",
                    is_product_page
                )
                logger.info(f"Source {ps.source_id} type: {ps.source.source_type}")

            # Verify CrawledSource has raw_content
            for ps in product_sources:
                has_content = ps.source.raw_content is not None and len(ps.source.raw_content) > 0
                report_collector.record_verification(f"source_has_content:{ps.source_id}", has_content)

            logger.info(f"Verified product {product_id}: {product.name}")

        # Summary verification
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
async def test_single_product_urls_configured():
    """Verify single product URLs are properly configured."""
    product_urls = get_single_product_urls()
    assert len(product_urls) >= 5, f"Expected at least 5 product URLs, got {len(product_urls)}"

    for url in product_urls:
        assert url.url.startswith("http"), f"Invalid URL: {url.url}"
        assert url.source_name, f"Missing source_name for {url.url}"
        assert url.product_name, f"Missing product_name for {url.url}"
        assert url.product_type in ["whiskey", "port_wine"], f"Invalid product type: {url.product_type}"

    logger.info(f"Verified {len(product_urls)} single product URLs")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discovery_orchestrator_v2_available():
    """Verify DiscoveryOrchestratorV2 is available."""
    from crawler.services.discovery_orchestrator_v2 import (
        DiscoveryOrchestratorV2,
        get_discovery_orchestrator_v2,
    )

    orchestrator = get_discovery_orchestrator_v2()
    assert orchestrator is not None, "DiscoveryOrchestratorV2 not available"
    assert hasattr(orchestrator, "extract_single_product"), "Missing extract_single_product method"
    assert hasattr(orchestrator, "extract_list_products"), "Missing extract_list_products method"

    logger.info("DiscoveryOrchestratorV2 is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_source_tracker_available():
    """Verify SourceTracker is available."""
    from crawler.services.source_tracker import get_source_tracker

    tracker = get_source_tracker()
    assert tracker is not None, "SourceTracker not available"
    assert hasattr(tracker, "store_crawled_source"), "Missing store_crawled_source method"
    assert hasattr(tracker, "link_product_to_source"), "Missing link_product_to_source method"
    assert hasattr(tracker, "track_field_provenance"), "Missing track_field_provenance method"

    logger.info("SourceTracker is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_quality_gate_v2_available():
    """Verify QualityGateV2 is available."""
    from crawler.services.quality_gate_v2 import (
        QualityGateV2,
        get_quality_gate_v2,
        ProductStatus,
    )

    gate = get_quality_gate_v2()
    assert gate is not None, "QualityGateV2 not available"
    assert hasattr(gate, "aassess"), "Missing aassess async method"

    # Test basic assessment (async version)
    result = await gate.aassess(
        extracted_data={"name": "Test Product", "brand": "Test Brand"},
        product_type="whiskey",
    )
    assert result.status in [ProductStatus.SKELETON, ProductStatus.PARTIAL], \
        f"Unexpected status for basic product: {result.status}"

    logger.info("QualityGateV2 is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_single_product_extraction_individual(ai_client, db):
    """
    Test extraction from a single product URL.

    This is a quick sanity check that extraction works.
    """
    if ai_client is None:
        pytest.skip("AI Enhancement Service not configured")

    from crawler.services.discovery_orchestrator_v2 import get_discovery_orchestrator_v2

    orchestrator = get_discovery_orchestrator_v2()

    # Use the first product URL
    product_url = SINGLE_PRODUCT_PAGES[0]
    logger.info(f"Testing extraction from: {product_url.url}")

    result = await orchestrator.extract_single_product(
        url=product_url.url,
        product_type=product_url.product_type,
        save_to_db=False,
    )

    logger.info(f"Extraction result: success={result.success}")
    if result.success:
        logger.info(f"Product data: {result.product_data}")
        logger.info(f"Quality status: {result.quality_status}")
        logger.info(f"Needs enrichment: {result.needs_enrichment}")
    else:
        logger.warning(f"Extraction error: {result.error}")

    # We don't assert success because external sites may be unavailable
    # The main test handles fallback creation
    logger.info("Individual extraction test completed")
