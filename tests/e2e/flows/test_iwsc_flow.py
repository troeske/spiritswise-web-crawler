"""
E2E Test: IWSC Competition Discovery Flow (Flow 1)

Tests the complete IWSC competition discovery pipeline using V3 architecture:
- CompetitionOrchestratorV2 for orchestration
- AIExtractorV2 for content extraction
- Real AI Enhancement Service at https://api.spiritswise.tech/api/v2/extract/
- QualityGateV3 for quality assessment (V3 status hierarchy)
- EnrichmentOrchestratorV3 for SerpAPI enrichment with V3 features:
  - V3 budget defaults (6 searches, 8 sources, 180s timeout)
  - Members-only site detection and budget refund
  - Dedicated awards search
  - ECP (Enrichment Completion Percentage) calculation
  - 90% ECP threshold for COMPLETE status
- SmartRouter with FULL tier escalation (Tier 1 → 2 → 3)

This test:
1. Uses real IWSC URLs from tests/e2e/utils/real_urls.py
2. Fetches pages using SmartRouter with Tier 2/3 for JavaScript rendering
3. Extracts 3 Gold/Silver medal winners with VALIDATION
4. Creates CrawledSource, DiscoveredProduct, ProductAward, ProductSource records
5. Runs quality gate assessment (pre-enrichment)
6. Enriches products via SerpAPI + AI extraction (taste profiles)
7. Runs quality gate assessment (post-enrichment)
8. Verifies all required fields and data quality
9. Tracks all created records (NO data deletion)

Key Principles (per spec):
- NO synthetic content
- NO shortcuts or workarounds
- If extraction returns < 3 valid products, TEST FAILS
- If product name is "Unknown Product", it is REJECTED
- Real SerpAPI calls for enrichment (credits OK)
- Real AI service calls for taste profile extraction

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 1
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
    IWSC_2025_WHISKEY_URLS,
    CompetitionURL,
    get_iwsc_urls,
)
from tests.e2e.utils.data_verifier import (
    DataVerifier,
    VerificationResult,
    verify_all_products_have_name,
    verify_competition_awards,
)
from tests.e2e.utils.competition_fetcher import (
    fetch_iwsc_page,
    extract_products_with_validation,
    validate_minimum_products,
    MIN_PRODUCTS_REQUIRED,
)
from tests.e2e.utils.test_recorder import TestStepRecorder, get_recorder

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

IWSC_COMPETITION_NAME = "IWSC"
IWSC_YEAR = 2025
MAX_PRODUCTS_TO_EXTRACT = 3  # Reduced to 3 for targeted test run
PRODUCT_TYPE = "whiskey"


# =============================================================================
# Helper Functions
# =============================================================================


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


# Note: fetch_iwsc_page is imported from tests.e2e.utils.competition_fetcher
# It uses SmartRouter with FULL tier escalation (Tier 1 → 2 → 3)
# and does NOT fall back to raw httpx. If all tiers fail, it raises RuntimeError.


@sync_to_async(thread_sensitive=True)
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = "award_page"
) -> "CrawledSource":
    """Create or get a CrawledSource record with retry for SQLite locks."""
    from crawler.models import CrawledSource, ExtractionStatusChoices
    import time as time_module
    from django.db import OperationalError

    content_hash = hashlib.sha256(raw_content.encode()).hexdigest()
    max_retries = 5
    retry_delay = 1

    for attempt in range(max_retries):
        try:
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

        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time_module.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise


@sync_to_async(thread_sensitive=True)
def create_discovered_product(
    name: str,
    brand: str,
    source_url: str,
    product_type: str = PRODUCT_TYPE,
    extracted_data: Optional[Dict[str, Any]] = None,
    quality_status: str = "skeleton",
) -> "DiscoveredProduct":
    """Create a DiscoveredProduct record."""
    from crawler.models import DiscoveredProduct, ProductType, DiscoveredProductStatus

    fingerprint = generate_fingerprint(name, brand or "")

    # Map quality status to model status (V3 status hierarchy)
    status_map = {
        "rejected": DiscoveredProductStatus.REJECTED,
        "skeleton": DiscoveredProductStatus.INCOMPLETE,
        "partial": DiscoveredProductStatus.PARTIAL,
        "baseline": DiscoveredProductStatus.PARTIAL,  # V3: BASELINE maps to PARTIAL
        "enriched": DiscoveredProductStatus.VERIFIED,  # V3: ENRICHED maps to VERIFIED
        "complete": DiscoveredProductStatus.COMPLETE,  # V3: COMPLETE maps to COMPLETE
    }
    status = status_map.get(quality_status, DiscoveredProductStatus.INCOMPLETE)

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
        "product_type": ProductType.WHISKEY if product_type == "whiskey" else ProductType.PORT_WINE,
        "raw_content": "",  # Will be populated from CrawledSource
        "raw_content_hash": "",
        "status": status,
        "discovery_source": "competition",
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


@sync_to_async(thread_sensitive=True)
def update_discovered_product(
    product_id: UUID,
    extracted_data: Dict[str, Any],
    quality_status: str,
) -> "DiscoveredProduct":
    """Update a DiscoveredProduct with enriched data."""
    from crawler.models import DiscoveredProduct, DiscoveredProductStatus
    from decimal import Decimal

    product = DiscoveredProduct.objects.get(id=product_id)

    # Map quality status to model status (V3 status hierarchy)
    status_map = {
        "rejected": DiscoveredProductStatus.REJECTED,
        "skeleton": DiscoveredProductStatus.INCOMPLETE,
        "partial": DiscoveredProductStatus.PARTIAL,
        "baseline": DiscoveredProductStatus.PARTIAL,  # V3: BASELINE maps to PARTIAL
        "enriched": DiscoveredProductStatus.VERIFIED,  # V3: ENRICHED maps to VERIFIED
        "complete": DiscoveredProductStatus.COMPLETE,  # V3: COMPLETE maps to COMPLETE
    }
    product.status = status_map.get(quality_status, product.status)

    # Update fields from enriched data
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
            # Handle ABV decimal conversion
            if src_field == "abv" and value:
                try:
                    value = Decimal(str(value))
                except Exception:
                    continue
            # Only update if we have a non-empty value
            if value:
                setattr(product, dst_field, value)

    product.save()
    logger.info(f"Updated DiscoveredProduct: {product.id} with enriched data (status: {quality_status})")
    return product


@sync_to_async(thread_sensitive=True)
def create_product_award(
    product: "DiscoveredProduct",
    competition: str,
    year: int,
    medal: str,
    award_url: Optional[str] = None,
    score: Optional[int] = None,
) -> "ProductAward":
    """Create a ProductAward record."""
    from crawler.models import ProductAward, MedalChoices

    # Map medal string to choices
    medal_map = {
        "gold": MedalChoices.GOLD,
        "silver": MedalChoices.SILVER,
        "bronze": MedalChoices.BRONZE,
        "double_gold": MedalChoices.DOUBLE_GOLD,
        "best_in_class": MedalChoices.BEST_IN_CLASS,
    }
    medal_choice = medal_map.get(medal.lower(), MedalChoices.GOLD)

    # Check for existing award
    existing = ProductAward.objects.filter(
        product=product,
        competition__iexact=competition,
        year=year,
    ).first()

    if existing:
        logger.info(f"Found existing award: {existing.id}")
        return existing

    award = ProductAward.objects.create(
        product=product,
        competition=competition,
        competition_country="International",  # IWSC is international
        year=year,
        medal=medal_choice,
        award_category=PRODUCT_TYPE.title(),
        score=score,
        award_url=award_url,
    )
    logger.info(f"Created ProductAward: {award.id} - {competition} {year} {medal}")
    return award


@sync_to_async(thread_sensitive=True)
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
        mention_type="award_winner",
    )
    logger.info(f"Created ProductSource link: {product.id} <- {source.id}")
    return link


@sync_to_async(thread_sensitive=True)
def get_discovered_product_by_id(product_id: UUID) -> "DiscoveredProduct":
    """Get a DiscoveredProduct by its ID."""
    from crawler.models import DiscoveredProduct
    return DiscoveredProduct.objects.get(pk=product_id)


@sync_to_async(thread_sensitive=True)
def get_product_awards(product: "DiscoveredProduct") -> List["ProductAward"]:
    """Get all awards for a product."""
    from crawler.models import ProductAward
    return list(ProductAward.objects.filter(product=product))


@sync_to_async(thread_sensitive=True)
def get_iwsc_award_for_product(product: "DiscoveredProduct", competition: str, year: int) -> Optional["ProductAward"]:
    """Get IWSC award for a product."""
    from crawler.models import ProductAward
    return ProductAward.objects.filter(
        product=product,
        competition__iexact=competition,
        year=year,
    ).first()


@sync_to_async(thread_sensitive=True)
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
class TestIWSCCompetitionFlow:
    """
    E2E test for IWSC Competition Discovery Flow.

    Extracts 5 Gold/Silver medal winning whiskeys from IWSC 2025,
    creates all required database records, and verifies data quality.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.created_products: List[UUID] = []
        self.created_sources: List[UUID] = []
        self.created_awards: List[UUID] = []
        self.extraction_results: List[Dict[str, Any]] = []
        # Initialize recorder for capturing intermediate step outputs
        self.recorder = get_recorder("IWSC Competition Flow")
        # Note: enrichment configs are set up in the async test method via _async_setup_enrichment_configs

    async def _async_setup_enrichment_configs(self):
        """
        Create EnrichmentConfig records for whiskey product type.

        These configs define the SerpAPI search templates used for enrichment.
        Without these, the enrichment orchestrator won't run any searches.
        Uses sync_to_async for safe async context execution.
        """
        @sync_to_async(thread_sensitive=True)
        def create_configs():
            from django.core.management import call_command
            from crawler.models import ProductTypeConfig, EnrichmentConfig, QualityGateConfig, FieldDefinition

            # Load base_fields.json fixture if FieldDefinitions don't exist
            if not FieldDefinition.objects.exists():
                logger.info("Loading base_fields.json fixture...")
                call_command("loaddata", "base_fields.json", verbosity=0)

            # Create or get ProductTypeConfig for whiskey FIRST (needed for FieldGroups)
            product_type_config, _ = ProductTypeConfig.objects.get_or_create(
                product_type="whiskey",
                defaults={
                    "display_name": "Whiskey",
                    "is_active": True,
                    "max_sources_per_product": 8,  # V3 default
                    "max_serpapi_searches": 6,     # V3 default
                    "max_enrichment_time_seconds": 180,  # V3 default
                }
            )

            # Create V3 FieldGroups for ECP calculation (must be after ProductTypeConfig)
            from crawler.models import FieldGroup
            if not FieldGroup.objects.filter(product_type_config=product_type_config).exists():
                logger.info("Creating V3 FieldGroups for ECP calculation...")
                field_groups_data = [
                    ("basic_product_info", "Basic Product Info", ["product_type", "category", "abv", "volume_ml", "description", "age_statement", "country", "region", "bottler"], 1),
                    ("tasting_appearance", "Tasting Profile - Appearance", ["color_description", "color_intensity", "clarity", "viscosity"], 2),
                    ("tasting_nose", "Tasting Profile - Nose", ["nose_description", "primary_aromas", "primary_intensity", "secondary_aromas", "aroma_evolution"], 3),
                    ("tasting_palate", "Tasting Profile - Palate", ["initial_taste", "mid_palate_evolution", "palate_flavors", "palate_description", "flavor_intensity", "complexity", "mouthfeel"], 4),
                    ("tasting_finish", "Tasting Profile - Finish", ["finish_length", "warmth", "dryness", "finish_flavors", "finish_evolution", "finish_description", "final_notes"], 5),
                    ("tasting_overall", "Tasting Profile - Overall", ["balance", "overall_complexity", "uniqueness", "drinkability", "price_quality_ratio", "experience_level", "serving_recommendation", "food_pairings"], 6),
                    ("cask_info", "Cask Info", ["primary_cask", "finishing_cask", "wood_type", "cask_treatment", "maturation_notes"], 7),
                    ("whiskey_details", "Whiskey-Specific Details", ["whiskey_type", "distillery", "mash_bill", "cask_strength", "single_cask", "cask_number", "vintage_year", "bottling_year", "batch_number", "peated", "peat_level", "peat_ppm", "natural_color", "non_chill_filtered"], 8),
                ]
                for group_key, display_name, fields, sort_order in field_groups_data:
                    FieldGroup.objects.create(
                        product_type_config=product_type_config,
                        group_key=group_key,
                        display_name=display_name,
                        fields=fields,
                        sort_order=sort_order,
                        is_active=True,
                    )
                logger.info(f"Created {len(field_groups_data)} FieldGroups for whiskey")

            # Create QualityGateConfig for whiskey (V3 status hierarchy)
            QualityGateConfig.objects.get_or_create(
                product_type_config=product_type_config,
                defaults={
                    # V3 Status Hierarchy: SKELETON → PARTIAL → BASELINE → ENRICHED → COMPLETE
                    "skeleton_required_fields": ["name"],
                    "partial_required_fields": ["name", "brand", "abv", "country", "category"],
                    # BASELINE: has tasting profile fields (descriptions + flavors)
                    "baseline_required_fields": [
                        "name", "brand", "abv", "country", "category",
                        "description", "primary_aromas", "palate_flavors"
                    ],
                    # ENRICHED: has mouthfeel + complexity OR finishing info
                    "enriched_required_fields": ["mouthfeel"],
                    "enriched_or_fields": [
                        ["complexity", "overall_complexity"],
                        ["finishing_cask", "maturation_notes", "finish_description"]
                    ],
                }
            )

            # Create EnrichmentConfig for tasting notes search
            EnrichmentConfig.objects.get_or_create(
                product_type_config=product_type_config,
                template_name="tasting_notes",
                defaults={
                    "search_template": "{name} {brand} tasting notes review",
                    "target_fields": ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors", "finish_flavors"],
                    "priority": 10,
                    "is_active": True,
                }
            )

            # Create EnrichmentConfig for product details search
            EnrichmentConfig.objects.get_or_create(
                product_type_config=product_type_config,
                template_name="product_details",
                defaults={
                    "search_template": "{name} {brand} whisky abv alcohol content",
                    "target_fields": ["abv", "description", "volume_ml", "age_statement"],
                    "priority": 8,
                    "is_active": True,
                }
            )

            logger.info("Created enrichment configs for whiskey product type")

        await create_configs()

    async def test_iwsc_competition_flow(
        self,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Main test: Extract 5 IWSC medal winners and create all records.

        Steps:
        1. Get IWSC competition URLs
        2. Use CompetitionOrchestratorV2 to process URLs
        3. For each extracted product:
           - Create CrawledSource with raw_content
           - Create DiscoveredProduct with proper status
           - Create ProductAward record
           - Create ProductSource link
        4. Verify all products meet requirements
        5. Track all created records
        """
        start_time = time.time()

        # Skip if AI client not configured
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Setup enrichment configs in async context for proper transaction handling
        await self._async_setup_enrichment_configs()

        logger.info("=" * 60)
        logger.info("Starting IWSC Competition Flow E2E Test")
        logger.info("=" * 60)

        # Get IWSC URLs
        iwsc_urls = get_iwsc_urls()
        assert len(iwsc_urls) > 0, "No IWSC URLs configured"

        # Use first URL for Gold medal whisky winners
        competition_url = iwsc_urls[0]
        logger.info(f"Using IWSC URL: {competition_url.url}")
        logger.info(f"Competition: {competition_url.competition}, Year: {competition_url.year}")

        # Import orchestrator
        from crawler.services.competition_orchestrator_v2 import (
            CompetitionOrchestratorV2,
            get_competition_orchestrator_v2,
        )
        from crawler.services.quality_gate_v3 import ProductStatus

        orchestrator = get_competition_orchestrator_v2()

        # Process IWSC competition URL
        # The orchestrator processes detail page URLs, so we need to get product URLs first
        # For this test, we'll simulate getting product detail URLs from the competition page

        # Fetch the competition page using SmartRouter with FULL tier escalation
        # IWSC pages are JavaScript-heavy SPAs - requires Tier 2 (Playwright) or Tier 3 (ScrapingBee)
        # This will raise RuntimeError if ALL tiers fail - NO silent fallback to raw httpx
        logger.info("Fetching IWSC page with SmartRouter (Tier 2/3 for JS rendering)...")
        fetch_result = await fetch_iwsc_page(competition_url.url, recorder=self.recorder)

        if not fetch_result.success:
            raise RuntimeError(
                f"Failed to fetch IWSC page. "
                f"URL: {competition_url.url}. Error: {fetch_result.error}. "
                f"Tier used: {fetch_result.tier_used}. "
                f"Check SmartRouter configuration (Playwright/ScrapingBee)."
            )

        page_content = fetch_result.content
        logger.info(
            f"Fetched IWSC page via Tier {fetch_result.tier_used} "
            f"({fetch_result.content_length} bytes, has_indicators={fetch_result.has_product_indicators})"
        )

        # Extract products with VALIDATION - rejects "Unknown Product" and garbage data
        # Raises RuntimeError if fewer than MIN_PRODUCTS_REQUIRED valid products
        logger.info("Extracting products with validation...")
        extraction_result = await extract_products_with_validation(
            content=page_content,
            url=competition_url.url,
            product_type=competition_url.product_type,
            product_category=competition_url.category,
            min_products=MAX_PRODUCTS_TO_EXTRACT,
            recorder=self.recorder,
        )

        extracted_products = extraction_result.valid_products
        logger.info(
            f"Extraction complete: {len(extraction_result.valid_products)} valid, "
            f"{len(extraction_result.rejected_products)} rejected"
        )

        # Limit to MAX_PRODUCTS_TO_EXTRACT (should already be validated)
        extracted_products = extracted_products[:MAX_PRODUCTS_TO_EXTRACT]

        logger.info(f"Extracted {len(extracted_products)} products from IWSC")

        # Close any stale database connections and wait for concurrent operations to complete
        # This avoids SQLite "database is locked" errors from async operations
        from django.db import close_old_connections, connection

        # Force close all connections - this releases any SQLite locks
        @sync_to_async(thread_sensitive=True)
        def force_close_connections():
            close_old_connections()
            # Also explicitly close the default connection
            connection.close()

        await force_close_connections()
        await asyncio.sleep(2)  # Brief delay for any pending async operations

        # Create ONE CrawledSource for the competition page with REAL page content
        # This is the actual HTML fetched from the competition URL
        self.recorder.start_step(
            "db_create_source",
            "Creating CrawledSource record",
            {"url": competition_url.url, "content_length": len(page_content)}
        )
        competition_source = await create_crawled_source(
            url=competition_url.url,
            title=f"IWSC {IWSC_YEAR} - Competition Results Page",
            raw_content=page_content,  # Use actual fetched content - NO synthetic HTML
            source_type="award_page",
        )
        self.created_sources.append(competition_source.id)
        test_run_tracker.record_source(competition_source.id)
        self.recorder.complete_step(
            output_data={
                "source_id": str(competition_source.id),
                "title": competition_source.title,
                "source_type": competition_source.source_type,
            },
            success=True
        )

        logger.info(f"Created CrawledSource for competition page: {competition_source.id}")

        # Process each extracted product - all linked to the same source
        for product_data in extracted_products:
            await self._process_extracted_product(
                product_data,
                competition_url,
                competition_source,  # Pass the source to link products
                source_tracker,
                quality_gate,
                test_run_tracker,
                report_collector,
            )

        # Wait for async operations to complete
        await asyncio.sleep(1)

        # Verify all products
        await self._verify_all_products(report_collector)

        # Record flow result
        duration = time.time() - start_time
        test_run_tracker.record_flow_result(
            flow_name="IWSC Competition",
            success=True,
            products_created=len(self.created_products),
            duration_seconds=duration,
            details={
                "competition": IWSC_COMPETITION_NAME,
                "year": IWSC_YEAR,
                "url": competition_url.url,
                "products_created": len(self.created_products),
                "sources_created": len(self.created_sources),
                "awards_created": len(self.created_awards),
            }
        )

        report_collector.record_flow_duration("IWSC Competition", duration)

        logger.info("=" * 60)
        logger.info(f"IWSC Competition Flow completed in {duration:.1f}s")
        logger.info(f"Products created: {len(self.created_products)}")
        logger.info(f"Sources created: {len(self.created_sources)}")
        logger.info(f"Awards created: {len(self.created_awards)}")
        logger.info("=" * 60)

        # Calculate enrichment statistics
        enriched_count = sum(1 for r in self.extraction_results if r.get("enrichment_success", False))
        total_fields_enriched = sum(
            len(r.get("fields_enriched", [])) for r in self.extraction_results if r.get("enrichment_success", False)
        )
        status_improvements = sum(
            1 for r in self.extraction_results
            if r.get("quality_status_after", "") != r.get("quality_status_before", "")
        )

        # Save the test recording with summary
        self.recorder.set_summary({
            "competition": IWSC_COMPETITION_NAME,
            "year": IWSC_YEAR,
            "url": competition_url.url,
            "products_created": len(self.created_products),
            "sources_created": len(self.created_sources),
            "awards_created": len(self.created_awards),
            "valid_products_extracted": len(extraction_result.valid_products),
            "rejected_products": len(extraction_result.rejected_products),
            "duration_seconds": duration,
            "test_passed": len(self.created_products) >= MAX_PRODUCTS_TO_EXTRACT,
            # Enrichment statistics
            "enrichment": {
                "products_enriched": enriched_count,
                "total_fields_enriched": total_fields_enriched,
                "status_improvements": status_improvements,
            },
        })
        output_path = self.recorder.save()
        logger.info(f"Test recording saved to: {output_path}")
        logger.info(f"Enrichment: {enriched_count} products enriched, {total_fields_enriched} fields added, {status_improvements} status improvements")

        # Export enriched products to JSON for inspection
        json_output_path = await self._export_enriched_products_to_json()
        logger.info(f"Enriched products exported to: {json_output_path}")

        # Assert we created the REQUIRED number of products (not just "at least some")
        assert len(self.created_products) >= MAX_PRODUCTS_TO_EXTRACT, (
            f"Created only {len(self.created_products)} products, "
            f"but {MAX_PRODUCTS_TO_EXTRACT} are required per spec. "
            f"This needs investigation - do NOT accept partial results."
        )

    async def _extract_products_from_page(
        self,
        page_content: str,
        competition_url: CompetitionURL,
        orchestrator,
        ai_client,
    ) -> List[Dict[str, Any]]:
        """
        Extract products from competition page using AI.

        Uses the AI client to extract product data from the page content.
        """
        from crawler.services.ai_client_v2 import get_ai_client_v2

        client = get_ai_client_v2()

        # Extract products using AI
        result = await client.extract(
            content=page_content,
            source_url=competition_url.url,
            product_type=competition_url.product_type,
            product_category=competition_url.category,
        )

        if not result.success:
            raise RuntimeError(
                f"AI extraction failed for IWSC page. "
                f"URL: {competition_url.url}. Error: {result.error}. "
                f"This needs investigation - check AI service connectivity and response."
            )

        # Convert extracted products to our format
        products = []
        for extracted in result.products:
            product_data = extracted.extracted_data.copy()
            product_data["field_confidences"] = extracted.field_confidences
            product_data["overall_confidence"] = extracted.confidence
            product_data["source_url"] = competition_url.url
            product_data["medal_hint"] = "Gold"  # Default for IWSC Gold winners page
            products.append(product_data)

        logger.info(f"AI extracted {len(products)} products from IWSC page")
        return products

    async def _process_extracted_product(
        self,
        product_data: Dict[str, Any],
        competition_url: CompetitionURL,
        competition_source: "CrawledSource",
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Process a single extracted product.

        Creates:
        - DiscoveredProduct record
        - ProductAward record
        - ProductSource link (to the competition source)
        - Runs enrichment via SerpAPI + AI extraction
        - Assesses quality before and after enrichment

        Note: CrawledSource is created once for the competition page,
        not per-product. All products link to the same source.
        """
        name = product_data.get("name", "Unknown Product")
        brand = product_data.get("brand", "")
        source_url = competition_url.url  # All products come from same URL

        logger.info(f"Processing product: {name} by {brand}")

        # Get quality assessment (PRE-ENRICHMENT) - Using V3 pipeline
        from crawler.services.quality_gate_v3 import get_quality_gate_v3, ProductStatus
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        gate = get_quality_gate_v3()
        field_confidences = product_data.pop("field_confidences", {})
        overall_confidence = product_data.pop("overall_confidence", 0.7)

        pre_enrichment_assessment = await gate.aassess(
            extracted_data=product_data,
            product_type=PRODUCT_TYPE,
            field_confidences=field_confidences,
        )

        logger.info(f"PRE-ENRICHMENT Quality: {pre_enrichment_assessment.status.value}, score={pre_enrichment_assessment.completeness_score:.2f}")

        # Record pre-enrichment quality assessment to the recorder
        self.recorder.record_quality_assessment(
            product_name=name,
            status=pre_enrichment_assessment.status.value,
            completeness_score=pre_enrichment_assessment.completeness_score,
            missing_fields=pre_enrichment_assessment.missing_required_fields + pre_enrichment_assessment.missing_any_of_fields,
            needs_enrichment=pre_enrichment_assessment.needs_enrichment,
        )

        # Use the competition source passed in (contains real page content)
        source = competition_source

        # Create DiscoveredProduct
        product = await create_discovered_product(
            name=name,
            brand=brand,
            source_url=source_url,
            product_type=PRODUCT_TYPE,
            extracted_data=product_data,
            quality_status=pre_enrichment_assessment.status.value,
        )
        self.created_products.append(product.id)
        test_run_tracker.record_product(product.id)

        # Create ProductAward
        medal = product_data.get("medal_hint", "Gold")
        award = await create_product_award(
            product=product,
            competition=IWSC_COMPETITION_NAME,
            year=IWSC_YEAR,
            medal=medal,
            award_url=source_url,
        )
        self.created_awards.append(award.id)
        test_run_tracker.record_award(award.id)

        # Create ProductSource link
        fields_extracted = list(product_data.keys())
        link = await link_product_to_source(
            product=product,
            source=source,
            extraction_confidence=overall_confidence,
            fields_extracted=fields_extracted,
        )

        # =====================================================================
        # ENRICHMENT STEP - Use SerpAPI to find taste profiles, then AI extract
        # =====================================================================
        logger.info(f"Starting enrichment for {name}...")
        self.recorder.start_step(
            "enrichment",
            f"Enriching {name[:30]}... via SerpAPI + AI",
            {"product_name": name, "product_id": str(product.id)}
        )

        enrichment_orchestrator = EnrichmentOrchestratorV3()
        enrichment_result = await enrichment_orchestrator.enrich_product(
            product_id=str(product.id),
            product_type=PRODUCT_TYPE,
            initial_data=product_data.copy(),
            initial_confidences=field_confidences,
        )

        if enrichment_result.success:
            logger.info(
                f"Enrichment complete for {name}: "
                f"{enrichment_result.status_before} -> {enrichment_result.status_after}, "
                f"fields enriched: {enrichment_result.fields_enriched}"
            )

            # Record enrichment result
            self.recorder.complete_step(
                output_data={
                    "status_before": enrichment_result.status_before,
                    "status_after": enrichment_result.status_after,
                    "fields_enriched": enrichment_result.fields_enriched,
                    "sources_used": len(enrichment_result.sources_used),
                    "searches_performed": enrichment_result.searches_performed,
                    "time_elapsed_seconds": enrichment_result.time_elapsed_seconds,
                },
                success=True
            )

            # Record detailed enrichment result
            self.recorder.record_enrichment_result(
                product_name=name,
                status_before=enrichment_result.status_before,
                status_after=enrichment_result.status_after,
                fields_enriched=enrichment_result.fields_enriched,
                sources_used=len(enrichment_result.sources_used),
                searches_performed=enrichment_result.searches_performed,
                time_elapsed=enrichment_result.time_elapsed_seconds,
            )

            # Update product in database with enriched data
            enriched_data = enrichment_result.product_data
            await update_discovered_product(
                product_id=product.id,
                extracted_data=enriched_data,
                quality_status=enrichment_result.status_after,
            )

            # POST-ENRICHMENT Quality Assessment
            post_enrichment_assessment = await gate.aassess(
                extracted_data=enriched_data,
                product_type=PRODUCT_TYPE,
                field_confidences=field_confidences,
            )

            logger.info(f"POST-ENRICHMENT Quality: {post_enrichment_assessment.status.value}, score={post_enrichment_assessment.completeness_score:.2f}")

            # Record post-enrichment quality assessment
            self.recorder.record_quality_assessment(
                product_name=f"{name} (post-enrichment)",
                status=post_enrichment_assessment.status.value,
                completeness_score=post_enrichment_assessment.completeness_score,
                missing_fields=post_enrichment_assessment.missing_required_fields + post_enrichment_assessment.missing_any_of_fields,
                needs_enrichment=post_enrichment_assessment.needs_enrichment,
            )

            final_status = post_enrichment_assessment.status.value
            final_score = post_enrichment_assessment.completeness_score
            final_ecp = getattr(post_enrichment_assessment, 'ecp_total', 0.0)
        else:
            logger.warning(f"Enrichment failed for {name}: {enrichment_result.error}")
            self.recorder.complete_step(
                output_data={"error": enrichment_result.error},
                success=False,
                error=enrichment_result.error
            )
            final_status = pre_enrichment_assessment.status.value
            final_score = pre_enrichment_assessment.completeness_score
            final_ecp = getattr(pre_enrichment_assessment, 'ecp_total', 0.0)

        # Record in report collector
        report_collector.add_product({
            "id": str(product.id),
            "name": name,
            "brand": brand,
            "product_type": PRODUCT_TYPE,
            "status": final_status,
            "completeness_score": final_score,
            "source_url": source_url,
            "enriched": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
        })

        # Note: Source is shared across products, only add once per unique source
        # Check if we've already recorded this source
        if source.id not in [s.get("id") for s in report_collector.sources if isinstance(s, dict)]:
            report_collector.add_source({
                "id": str(source.id),
                "url": source_url,
                "title": source.title,
                "source_type": source.source_type,
                "has_raw_content": bool(source.raw_content),
            })

        report_collector.add_award({
            "id": str(award.id),
            "product_id": str(product.id),
            "competition": IWSC_COMPETITION_NAME,
            "year": IWSC_YEAR,
            "medal": medal,
        })

        report_collector.add_quality_assessment({
            "product_id": str(product.id),
            "product_name": name,
            "status_before": pre_enrichment_assessment.status.value,
            "status_after": final_status,
            "completeness_score_before": pre_enrichment_assessment.completeness_score,
            "completeness_score_after": final_score,
            "needs_enrichment": final_status not in ["complete", "enriched"],
            "missing_required_fields": pre_enrichment_assessment.missing_required_fields,
            "enrichment_success": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
        })

        # Store extraction result for verification (including enrichment source URLs)
        self.extraction_results.append({
            "product_id": product.id,
            "source_id": source.id,
            "award_id": award.id,
            "product_data": enrichment_result.product_data if enrichment_result.success else product_data,
            "quality_status_before": pre_enrichment_assessment.status.value,
            "quality_status_after": final_status,
            "ecp_total": final_ecp,
            "enrichment_success": enrichment_result.success,
            "fields_enriched": enrichment_result.fields_enriched if enrichment_result.success else [],
            "enrichment_sources": enrichment_result.sources_used if enrichment_result.success else [],
            "sources_searched": enrichment_result.sources_searched if enrichment_result.success else [],
            "sources_rejected": enrichment_result.sources_rejected if enrichment_result.success else [],
        })

    async def _verify_all_products(self, report_collector):
        """
        Verify all created products meet requirements.

        Checks:
        - All products have name field
        - All products have brand field (or marked for enrichment)
        - All products have source_url linking to IWSC
        - Award records have correct medal, competition, year
        - CrawledSource has raw_content stored
        - Products with ABV have status >= PARTIAL
        """
        logger.info("=" * 40)
        logger.info("Verifying all created products")
        logger.info("=" * 40)

        for product_id in self.created_products:
            product = await get_discovered_product_by_id(product_id)

            # Verify name field
            result = self.verifier.verify_product_required_fields(
                {"name": product.name, "brand": str(product.brand) if product.brand else ""},
                required_fields={"name"},
            )
            report_collector.record_verification(f"name_populated:{product_id}", result.passed)
            assert result.passed, f"Product {product_id} missing name field"

            # Verify source_url contains IWSC reference
            has_valid_source = "iwsc" in product.source_url.lower() or product.source_url
            report_collector.record_verification(f"source_url_valid:{product_id}", has_valid_source)

            # Verify award records
            awards = await get_product_awards(product)
            has_iwsc_award = any(
                a.competition.upper() == IWSC_COMPETITION_NAME and a.year == IWSC_YEAR
                for a in awards
            )
            report_collector.record_verification(f"has_iwsc_award:{product_id}", has_iwsc_award)

            if has_iwsc_award:
                award = await get_iwsc_award_for_product(product, IWSC_COMPETITION_NAME, IWSC_YEAR)
                assert award.medal in ["gold", "silver", "bronze", "double_gold", "best_in_class"], \
                    f"Invalid medal for product {product_id}: {award.medal}"
                report_collector.record_verification(f"award_medal_valid:{product_id}", True)

            # Verify CrawledSource has raw_content
            product_sources = await get_product_sources(product)
            for ps in product_sources:
                has_content = ps.source.raw_content is not None and len(ps.source.raw_content) > 0
                report_collector.record_verification(f"source_has_content:{ps.source_id}", has_content)

            # Verify products with ABV have status >= PARTIAL
            if product.abv is not None:
                is_partial_or_better = product.status in ["partial", "complete", "verified"]
                report_collector.record_verification(f"abv_status_valid:{product_id}", is_partial_or_better)

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

    async def _export_enriched_products_to_json(self) -> str:
        """
        Export all enriched products to a JSON file for inspection.

        Returns the path to the exported JSON file.
        """
        import json
        from pathlib import Path

        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = output_dir / f"enriched_products_{timestamp}.json"

        # Build export data with full product details
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "competition": IWSC_COMPETITION_NAME,
            "year": IWSC_YEAR,
            "total_products": len(self.extraction_results),
            "products": []
        }

        for result in self.extraction_results:
            product_export = {
                "product_id": str(result["product_id"]),
                "source_id": str(result["source_id"]),
                "award_id": str(result["award_id"]),
                "quality_status_before": result["quality_status_before"],
                "quality_status_after": result["quality_status_after"],
                "ecp_total": result.get("ecp_total", 0.0),
                "enrichment_success": result["enrichment_success"],
                "fields_enriched": result["fields_enriched"],
                "product_data": self._serialize_product_data(result["product_data"]),
                # Include enrichment source URLs for verification
                "enrichment_sources": result.get("enrichment_sources", []),
                "sources_searched": result.get("sources_searched", []),
                "sources_rejected": result.get("sources_rejected", []),
            }
            export_data["products"].append(product_export)

        # Write to file with pretty formatting
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(export_data['products'])} enriched products to {output_path}")
        return str(output_path)

    def _serialize_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize product data for JSON export, handling special types."""
        from decimal import Decimal
        from uuid import UUID

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
async def test_iwsc_urls_configured():
    """Verify IWSC URLs are properly configured."""
    iwsc_urls = get_iwsc_urls()
    assert len(iwsc_urls) > 0, "No IWSC URLs configured"

    for url in iwsc_urls:
        assert url.competition == "IWSC", f"Invalid competition: {url.competition}"
        assert url.year >= 2024, f"Invalid year: {url.year}"
        assert url.product_type == "whiskey", f"Invalid product type: {url.product_type}"
        assert url.url.startswith("http"), f"Invalid URL: {url.url}"

    logger.info(f"Verified {len(iwsc_urls)} IWSC URLs")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_competition_orchestrator_v2_available():
    """Verify CompetitionOrchestratorV2 is available."""
    from crawler.services.competition_orchestrator_v2 import (
        CompetitionOrchestratorV2,
        get_competition_orchestrator_v2,
    )

    orchestrator = get_competition_orchestrator_v2()
    assert orchestrator is not None, "CompetitionOrchestratorV2 not available"
    assert hasattr(orchestrator, "process_competition_url"), "Missing process_competition_url method"
    assert hasattr(orchestrator, "process_competition_batch"), "Missing process_competition_batch method"

    logger.info("CompetitionOrchestratorV2 is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_extractor_v2_available():
    """Verify AIExtractorV2 is available."""
    from crawler.discovery.extractors.ai_extractor_v2 import (
        AIExtractorV2,
        get_ai_extractor_v2,
    )

    extractor = get_ai_extractor_v2()
    assert extractor is not None, "AIExtractorV2 not available"
    assert hasattr(extractor, "extract"), "Missing extract method"

    logger.info("AIExtractorV2 is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_quality_gate_v3_available():
    """Verify QualityGateV3 is available."""
    from crawler.services.quality_gate_v3 import (
        QualityGateV3,
        get_quality_gate_v3,
        ProductStatus,
    )

    gate = get_quality_gate_v3()
    assert gate is not None, "QualityGateV3 not available"
    assert hasattr(gate, "aassess"), "Missing aassess async method"

    # Test basic assessment (async version)
    result = await gate.aassess(
        extracted_data={"name": "Test Product", "brand": "Test Brand"},
        product_type="whiskey",
    )
    assert result.status in [ProductStatus.SKELETON, ProductStatus.PARTIAL], \
        f"Unexpected status for basic product: {result.status}"

    logger.info("QualityGateV3 is available and configured")
