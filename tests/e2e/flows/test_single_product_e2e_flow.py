"""
E2E Test: Single Product Page Flow (Upgraded)

Tests the complete single product extraction and enrichment pipeline using V2 architecture:
- SmartRouter with FULL tier escalation for page fetching
- AIClientV2 for product extraction
- EnrichmentOrchestratorV2 for taste profile enrichment
- QualityGateV2 for quality assessment

This test:
1. Fetches Frank August Small Batch Kentucky Straight Bourbon product page
2. Extracts product data using AI with VALIDATION
3. Creates CrawledSource, DiscoveredProduct, ProductSource records
4. Enriches the product via SerpAPI + AI extraction
5. Exports enriched product to JSON for inspection
6. Tracks all steps for debugging

Key Principles (per E2E_TEST_SPECIFICATION_V2.md):
- NO synthetic content - All data from real external services
- NO shortcuts or workarounds - Fix root cause if services fail
- Real SmartRouter tier escalation
- Real AI service calls
- Real SerpAPI enrichment
- Record intermediate steps to file for debugging

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 6
Status Tracking: specs/SINGLE_PRODUCT_E2E_STATUS.md
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from tests.e2e.utils.single_product_fetcher import (
    FetchResult,
    ExtractionResult,
    DiscoveryResult,
    discover_and_extract_product,
    fetch_product_page,
    extract_product_from_page,
    PRODUCT_SEARCH_TEMPLATES,
    get_search_templates,
)
from tests.e2e.utils.test_recorder import TestStepRecorder, get_recorder
from tests.e2e.utils.data_verifier import DataVerifier
from tests.e2e.utils.test_products import (
    PRODUCT_TYPE_CONFIGS,
    PRODUCT_TYPE_IDS,
    get_primary_test_product,
    get_test_config,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

# Source type for product pages
SOURCE_TYPE = "retailer_page"


# =============================================================================
# Helper Functions (Database Operations)
# =============================================================================

@sync_to_async
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = SOURCE_TYPE,
) -> "CrawledSource":
    """Create a CrawledSource record for the product page."""
    from crawler.models import CrawledSource, ExtractionStatusChoices
    from django.db import OperationalError
    import time as time_module

    content_hash = hashlib.sha256(raw_content.encode()).hexdigest()
    max_retries = 5
    retry_delay = 1

    for attempt in range(max_retries):
        try:
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
                source.title = title
                source.raw_content = raw_content
                source.content_hash = content_hash
                source.save()

            action = "Created" if created else "Updated"
            logger.info(f"{action} CrawledSource: {source.id} for {url[:50]}...")
            return source

        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying in {retry_delay}s")
                time_module.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


@sync_to_async
def create_discovered_product(
    name: str,
    brand: str,
    source_url: str,
    product_type: str = "whiskey",
    extracted_data: Optional[Dict[str, Any]] = None,
    quality_status: str = "skeleton",
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

    # Check for existing product with same fingerprint
    existing = DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()
    if existing:
        logger.info(f"Found existing product with fingerprint: {existing.id}")
        # Update with new data
        skip_fields = {"brand", "source", "crawl_job", "whiskey_details", "port_details"}
        if extracted_data:
            for field, value in extracted_data.items():
                if field in skip_fields:
                    continue
                if hasattr(existing, field) and value is not None:
                    try:
                        setattr(existing, field, value)
                    except (TypeError, ValueError):
                        pass
        existing.status = status
        existing.save()
        return existing

    # Build product data
    product_data = {
        "name": name,
        "brand_id": None,
        "source_url": source_url,
        "fingerprint": fingerprint,
        "product_type": ProductType.WHISKEY if product_type == "whiskey" else ProductType.PORT_WINE,
        "raw_content": "",
        "raw_content_hash": "",
        "status": status,
        "discovery_source": "direct",
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

    product = DiscoveredProduct.objects.create(**product_data)
    logger.info(f"Created DiscoveredProduct: {product.id} - {name}")
    return product


@sync_to_async
def update_discovered_product(
    product_id: UUID,
    extracted_data: Dict[str, Any],
    quality_status: str,
) -> "DiscoveredProduct":
    """Update a DiscoveredProduct with enriched data."""
    from crawler.models import DiscoveredProduct, DiscoveredProductStatus

    product = DiscoveredProduct.objects.get(id=product_id)

    status_map = {
        "rejected": DiscoveredProductStatus.REJECTED,
        "skeleton": DiscoveredProductStatus.INCOMPLETE,
        "partial": DiscoveredProductStatus.PARTIAL,
        "complete": DiscoveredProductStatus.COMPLETE,
        "enriched": DiscoveredProductStatus.VERIFIED,
    }
    product.status = status_map.get(quality_status, product.status)

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
        "primary_aromas": "primary_aromas",
    }

    for src_field, dst_field in field_mapping.items():
        if src_field in extracted_data and extracted_data[src_field] is not None:
            value = extracted_data[src_field]
            if src_field == "abv" and value:
                try:
                    value = Decimal(str(value))
                except Exception:
                    continue
            if value:
                setattr(product, dst_field, value)

    product.save()
    logger.info(f"Updated DiscoveredProduct: {product.id} with enriched data (status: {quality_status})")
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
def get_discovered_product_by_id(product_id: UUID) -> "DiscoveredProduct":
    """Get a DiscoveredProduct by its ID."""
    from crawler.models import DiscoveredProduct
    return DiscoveredProduct.objects.get(pk=product_id)


@sync_to_async
def get_product_sources(product: "DiscoveredProduct") -> List["ProductSource"]:
    """Get all ProductSource links for a product."""
    from crawler.models import ProductSource
    return list(ProductSource.objects.filter(product=product).select_related("source"))


# =============================================================================
# Test Class
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSingleProductE2EFlow:
    """
    E2E test for Single Product Page Flow.

    Parameterized to test multiple product types (whiskey, port_wine).
    Each product type uses its primary test product for extraction and enrichment.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.product_id: Optional[UUID] = None
        self.source_id: Optional[UUID] = None
        self.extraction_result: Optional[Dict[str, Any]] = None
        self.recorder = get_recorder("Single Product Flow")

    async def _setup_enrichment_configs_for_type(self, product_type: str):
        """Create EnrichmentConfig records for the specified product type."""
        from crawler.models import ProductTypeConfig, EnrichmentConfig, QualityGateConfig, FieldDefinition
        from django.core.management import call_command

        config = get_test_config(product_type)

        @sync_to_async
        def create_configs():
            # Load base_fields.json fixture if FieldDefinitions don't exist
            if not FieldDefinition.objects.exists():
                logger.info("Loading base_fields.json fixture...")
                call_command("loaddata", "crawler/fixtures/base_fields.json", verbosity=0)

            product_type_config, _ = ProductTypeConfig.objects.get_or_create(
                product_type=product_type,
                defaults={
                    "display_name": config.display_name,
                    "is_active": True,
                    "max_sources_per_product": 5,
                    "max_serpapi_searches": 3,
                    "max_enrichment_time_seconds": 120,
                }
            )

            QualityGateConfig.objects.get_or_create(
                product_type_config=product_type_config,
                defaults={
                    "skeleton_required_fields": config.skeleton_fields,
                    "partial_required_fields": config.partial_fields,
                    "partial_any_of_count": 2,
                    "partial_any_of_fields": ["description", "abv", "region", "country"],
                    "complete_required_fields": config.complete_fields,
                    "complete_any_of_count": 2,
                    "complete_any_of_fields": ["nose_description", "palate_description", "finish_description", "region"],
                }
            )

            # Product-type-specific enrichment templates
            if product_type == "whiskey":
                templates = [
                    ("tasting_notes", "{name} {brand} tasting notes review",
                     ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors"], 10),
                    ("product_details", "{name} {brand} bourbon abv alcohol content",
                     ["abv", "description", "volume_ml", "age_statement"], 8),
                ]
            elif product_type == "port_wine":
                templates = [
                    ("tasting_notes", "{name} {brand} port wine tasting notes review",
                     ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors"], 10),
                    ("producer_info", "{name} {brand} port house producer quinta",
                     ["producer_house", "quinta", "douro_subregion"], 8),
                ]
            else:
                templates = []

            for template_name, search_template, target_fields, priority in templates:
                EnrichmentConfig.objects.get_or_create(
                    product_type_config=product_type_config,
                    template_name=template_name,
                    defaults={
                        "search_template": search_template,
                        "target_fields": target_fields,
                        "priority": priority,
                        "is_active": True,
                    }
                )

            logger.info(f"Created enrichment configs for {product_type} product type")

        await create_configs()

    @pytest.mark.parametrize("product_type", PRODUCT_TYPE_IDS, ids=PRODUCT_TYPE_IDS)
    async def test_single_product_flow(
        self,
        product_type: str,
        ai_client,
        test_run_tracker,
        report_collector,
        quality_gate,
    ):
        """
        Main test: Discover, extract and enrich a product.

        Parameterized to run for each product type (whiskey, port_wine).
        Uses the primary test product for each type.

        Steps:
        1. Set up enrichment configs for the product type
        2. Search for product page via SerpAPI (template progression)
        3. Fetch product page via SmartRouter
        4. Extract product data using AI
        5. Create database records
        6. Enrich product via SerpAPI + AI
        7. Export enriched product to JSON
        8. Verify all records created
        """
        # Set up configurations for this product type
        await self._setup_enrichment_configs_for_type(product_type)

        # Get test product for this type
        test_product = get_primary_test_product(product_type)
        product_name = test_product.name
        brand = test_product.brand
        search_templates = get_search_templates(product_type)

        start_time = time.time()

        # Skip if services not configured
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        logger.info("=" * 60)
        logger.info(f"Starting Single Product E2E Test ({product_type})")
        logger.info(f"Product: {product_name}")
        logger.info(f"Brand: {brand}")
        logger.info(f"Search Templates: {search_templates}")
        logger.info("=" * 60)

        # Step 1-3: Dynamic discovery (search + fetch + extract)
        logger.info("Starting dynamic product discovery...")
        discovery_result = await discover_and_extract_product(
            product_name=product_name,
            brand=brand,
            product_type=product_type,
            recorder=self.recorder,
        )

        if not discovery_result.success:
            raise RuntimeError(
                f"Failed to discover product '{product_name}'. "
                f"Error: {discovery_result.error}. "
                f"Templates tried: {discovery_result.templates_tried}. "
                f"This needs investigation."
            )

        logger.info(f"Discovery successful!")
        logger.info(f"URL found: {discovery_result.url}")
        logger.info(f"Template used: {discovery_result.template_used}")
        logger.info(f"Fetched via Tier {discovery_result.fetch_result.tier_used}: {discovery_result.fetch_result.content_length} bytes")

        extraction_result = discovery_result.extraction_result
        fetch_result = discovery_result.fetch_result
        product_url = discovery_result.url

        product_data = extraction_result.product_data
        logger.info(f"Extracted: {product_data.get('name', 'Unknown')}")
        logger.info(f"Quality status: {extraction_result.quality_status}")

        # Close connections before database operations
        from django.db import close_old_connections, connection

        @sync_to_async(thread_sensitive=True)
        def force_close_connections():
            close_old_connections()
            connection.close()

        await force_close_connections()
        await asyncio.sleep(2)

        # Step 4: Create CrawledSource
        self.recorder.start_step(
            "db_create_source",
            "Creating CrawledSource record",
            {"url": product_url}
        )

        source = await create_crawled_source(
            url=product_url,
            title=f"Product Page - {product_data.get('name', product_name)}",
            raw_content=fetch_result.content,
            source_type=SOURCE_TYPE,
        )
        self.source_id = source.id
        test_run_tracker.record_source(source.id)

        self.recorder.complete_step(
            output_data={
                "source_id": str(source.id),
                "title": source.title,
                "source_type": SOURCE_TYPE,
            },
            success=True
        )

        # Step 4: Pre-enrichment quality assessment
        from crawler.services.quality_gate_v2 import get_quality_gate_v2
        gate = get_quality_gate_v2()

        field_confidences = product_data.pop("field_confidences", {})
        overall_confidence = product_data.pop("overall_confidence", 0.7)

        pre_assessment = await gate.aassess(
            extracted_data=product_data,
            product_type=product_type,
            field_confidences=field_confidences,
        )

        logger.info(f"PRE-ENRICHMENT Quality: {pre_assessment.status.value}")

        self.recorder.record_quality_assessment(
            product_name=product_data.get("name", product_name),
            status=pre_assessment.status.value,
            completeness_score=pre_assessment.completeness_score,
            missing_fields=pre_assessment.missing_required_fields + pre_assessment.missing_any_of_fields,
            needs_enrichment=pre_assessment.needs_enrichment,
        )

        # Step 5: Create DiscoveredProduct
        extracted_name = product_data.get("name", product_name)
        extracted_brand = product_data.get("brand", brand)

        product = await create_discovered_product(
            name=extracted_name,
            brand=extracted_brand,
            source_url=product_url,
            product_type=product_type,
            extracted_data=product_data,
            quality_status=pre_assessment.status.value,
        )
        self.product_id = product.id
        test_run_tracker.record_product(product.id)

        # Step 6: Create ProductSource link
        fields_extracted = list(product_data.keys())
        await link_product_to_source(
            product=product,
            source=source,
            extraction_confidence=overall_confidence,
            fields_extracted=fields_extracted,
        )

        # Step 7: ENRICHMENT
        logger.info(f"Starting enrichment for {extracted_name}...")
        self.recorder.start_step(
            "enrichment",
            f"Enriching {extracted_name[:30]}... via SerpAPI + AI",
            {"product_name": extracted_name, "product_id": str(product.id)}
        )

        from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
        enrichment_orchestrator = EnrichmentOrchestratorV2()

        enrichment_result = await enrichment_orchestrator.enrich_product(
            product_id=str(product.id),
            product_type=product_type,
            initial_data=product_data.copy(),
            initial_confidences=field_confidences,
        )

        if enrichment_result.success:
            logger.info(
                f"Enrichment complete: {enrichment_result.status_before} -> {enrichment_result.status_after}"
            )
            logger.info(f"Sources used: {enrichment_result.sources_used}")
            if hasattr(enrichment_result, 'sources_rejected') and enrichment_result.sources_rejected:
                logger.warning(f"Sources REJECTED (product mismatch): {enrichment_result.sources_rejected}")

            self.recorder.complete_step(
                output_data={
                    "status_before": enrichment_result.status_before,
                    "status_after": enrichment_result.status_after,
                    "fields_enriched": enrichment_result.fields_enriched,
                    "sources_used_count": len(enrichment_result.sources_used),
                    "sources_used_urls": enrichment_result.sources_used,  # Actual URLs
                    "sources_rejected": getattr(enrichment_result, 'sources_rejected', []),
                    "searches_performed": enrichment_result.searches_performed,
                },
                success=True
            )

            self.recorder.record_enrichment_result(
                product_name=extracted_name,
                status_before=enrichment_result.status_before,
                status_after=enrichment_result.status_after,
                fields_enriched=enrichment_result.fields_enriched,
                sources_used=len(enrichment_result.sources_used),
                searches_performed=enrichment_result.searches_performed,
                time_elapsed=enrichment_result.time_elapsed_seconds,
            )

            # Update product with enriched data
            enriched_data = enrichment_result.product_data
            await update_discovered_product(
                product_id=product.id,
                extracted_data=enriched_data,
                quality_status=enrichment_result.status_after,
            )

            # POST-ENRICHMENT Quality Assessment
            post_assessment = await gate.aassess(
                extracted_data=enriched_data,
                product_type=product_type,
                field_confidences=field_confidences,
            )

            logger.info(f"POST-ENRICHMENT Quality: {post_assessment.status.value}")

            self.recorder.record_quality_assessment(
                product_name=f"{extracted_name} (post-enrichment)",
                status=post_assessment.status.value,
                completeness_score=post_assessment.completeness_score,
                missing_fields=post_assessment.missing_required_fields + post_assessment.missing_any_of_fields,
                needs_enrichment=post_assessment.needs_enrichment,
            )

            final_status = post_assessment.status.value
            final_data = enriched_data
        else:
            logger.warning(f"Enrichment failed: {enrichment_result.error}")
            self.recorder.complete_step(
                output_data={"error": enrichment_result.error},
                success=False,
                error=enrichment_result.error
            )
            final_status = pre_assessment.status.value
            final_data = product_data

        # Store extraction result
        self.extraction_result = {
            "product_id": product.id,
            "source_id": source.id,
            "product_data": final_data,
            "quality_status_before": pre_assessment.status.value,
            "quality_status_after": final_status,
            "enrichment_success": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
            # Include enrichment source URLs for verification
            "enrichment_sources_used": enrichment_result.sources_used if enrichment_result.success else [],
            "enrichment_sources_rejected": getattr(enrichment_result, 'sources_rejected', []),
        }

        # Record in report collector
        report_collector.add_product({
            "id": str(product.id),
            "name": extracted_name,
            "brand": extracted_brand,
            "product_type": product_type,
            "status": final_status,
            "source_url": product_url,
            "enriched": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
        })

        # Step 8: Verify product
        await self._verify_product(report_collector)

        # Record flow result
        duration = time.time() - start_time
        test_run_tracker.record_flow_result(
            flow_name="Single Product",
            success=True,
            products_created=1,
            duration_seconds=duration,
            details={
                "product_name": extracted_name,
                "product_type": product_type,
                "product_id": str(product.id),
                "source_id": str(source.id),
                "enrichment_success": enrichment_result.success,
            }
        )

        report_collector.record_flow_duration("Single Product", duration)

        logger.info("=" * 60)
        logger.info(f"Single Product Flow completed in {duration:.1f}s")
        logger.info(f"Product: {extracted_name}")
        logger.info(f"Status: {pre_assessment.status.value} -> {final_status}")
        logger.info(f"Enrichment: {'SUCCESS' if enrichment_result.success else 'FAILED'}")
        if enrichment_result.success:
            logger.info(f"Fields enriched: {len(enrichment_result.fields_enriched)}")
        logger.info("=" * 60)

        # Save recorder output
        self.recorder.set_summary({
            "product_name": extracted_name,
            "product_id": str(product.id),
            "source_id": str(source.id),
            "status_before": pre_assessment.status.value,
            "status_after": final_status,
            "duration_seconds": duration,
            "enrichment_success": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
        })
        output_path = self.recorder.save()
        logger.info(f"Test recording saved to: {output_path}")

        # Export enriched product to JSON
        json_output_path = await self._export_enriched_product_to_json(extracted_name, product_type)
        logger.info(f"Enriched product exported to: {json_output_path}")

        # Assert product was created
        assert self.product_id is not None, "Product was not created"

    async def _verify_product(self, report_collector):
        """Verify the created product meets requirements."""
        logger.info("=" * 40)
        logger.info("Verifying created product")
        logger.info("=" * 40)

        product = await get_discovered_product_by_id(self.product_id)

        # Verify name field
        result = self.verifier.verify_product_required_fields(
            {"name": product.name, "brand": str(product.brand) if product.brand else ""},
            required_fields={"name"},
        )
        report_collector.record_verification(f"name_populated:{self.product_id}", result.passed)
        assert result.passed, f"Product {self.product_id} missing name field"

        # Verify source_url
        has_valid_source = bool(product.source_url)
        report_collector.record_verification(f"source_url_valid:{self.product_id}", has_valid_source)

        # Verify ProductSource exists
        product_sources = await get_product_sources(product)
        has_source_link = len(product_sources) > 0
        report_collector.record_verification(f"has_source_link:{self.product_id}", has_source_link)
        assert has_source_link, f"Product {self.product_id} has no ProductSource link"

        # Verify source has raw_content
        for ps in product_sources:
            has_content = ps.source.raw_content is not None and len(ps.source.raw_content) > 0
            report_collector.record_verification(f"source_has_content:{ps.source_id}", has_content)

        logger.info(f"Verified product {self.product_id}: {product.name}")

    async def _export_enriched_product_to_json(self, product_name: str, product_type: str) -> str:
        """Export the enriched product to a JSON file for inspection."""
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = output_dir / f"enriched_product_{product_type}_{timestamp}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "product_name": product_name,
            "product_type": product_type,
            "product": self._serialize_product_data(self.extraction_result) if self.extraction_result else {},
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported enriched product to {output_path}")
        return str(output_path)

    def _serialize_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize product data for JSON export."""
        serialized = {}
        for key, value in data.items():
            if isinstance(value, Decimal):
                serialized[key] = float(value)
            elif isinstance(value, UUID):
                serialized[key] = str(value)
            elif isinstance(value, (list, tuple)):
                serialized[key] = [
                    self._serialize_product_data(v) if isinstance(v, dict) else v
                    for v in value
                ]
            elif isinstance(value, dict):
                serialized[key] = self._serialize_product_data(value)
            else:
                serialized[key] = value
        return serialized


# =============================================================================
# Standalone Test Functions
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_product_search_templates_configured():
    """Verify product search templates are properly configured for dynamic discovery."""
    from tests.e2e.utils.single_product_fetcher import PRODUCT_SEARCH_TEMPLATES

    # Verify templates are defined
    assert len(PRODUCT_SEARCH_TEMPLATES) >= 1, (
        f"Expected at least 1 search template, got {len(PRODUCT_SEARCH_TEMPLATES)}"
    )

    # Verify templates have required placeholders
    for template in PRODUCT_SEARCH_TEMPLATES:
        assert "{name}" in template, f"Template missing {{name}} placeholder: {template}"

    # Verify official/direct search template exists first
    first_template = PRODUCT_SEARCH_TEMPLATES[0]
    assert "official" in first_template.lower() or "site" in first_template.lower(), (
        f"First template should prioritize official sources: {first_template}"
    )

    logger.info(f"Verified {len(PRODUCT_SEARCH_TEMPLATES)} search templates configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_single_product_fetcher_available():
    """Verify single_product_fetcher module is available."""
    from tests.e2e.utils.single_product_fetcher import (
        fetch_product_page,
        extract_product_from_page,
    )
    assert fetch_product_page is not None
    assert extract_product_from_page is not None
    logger.info("single_product_fetcher module is available")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_enrichment_orchestrator_v2_available():
    """Verify EnrichmentOrchestratorV2 is available."""
    from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
    orchestrator = EnrichmentOrchestratorV2()
    assert orchestrator is not None
    assert hasattr(orchestrator, "enrich_product")
    logger.info("EnrichmentOrchestratorV2 is available")
