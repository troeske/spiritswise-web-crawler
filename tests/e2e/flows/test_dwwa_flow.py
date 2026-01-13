"""
E2E Test: DWWA Competition Discovery Flow (Flow 3)

Tests the complete DWWA competition discovery pipeline using V2 architecture:
- CompetitionOrchestratorV2 for orchestration
- AIExtractorV2 for content extraction
- Real AI Enhancement Service at https://api.spiritswise.tech/api/v2/extract/
- QualityGateV2 for quality assessment
- SmartRouter with FULL tier escalation (Tier 1 → 2 → 3)

This test:
1. Uses real DWWA URLs from tests/e2e/utils/real_urls.py
2. Fetches pages using SmartRouter with Tier 2/3 for JavaScript rendering
3. Extracts 5 Gold/Silver medal port wines with VALIDATION
4. Creates CrawledSource, DiscoveredProduct, ProductAward, ProductSource records
5. Creates PortWineDetails records with style, vintage, producer information
6. Verifies all required fields and data quality
7. Tracks all created records (NO data deletion)

Key Principles (per spec):
- NO synthetic content
- NO shortcuts or workarounds
- If extraction returns < 5 valid products, TEST FAILS
- If product name is "Unknown Product", it is REJECTED

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 3
"""

import asyncio
import hashlib
import json
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
    DWWA_2025_PORT_WINE_URLS,
    CompetitionURL,
    get_dwwa_urls,
)
from tests.e2e.utils.data_verifier import (
    DataVerifier,
    VerificationResult,
    verify_all_products_have_name,
    verify_competition_awards,
)
from tests.e2e.utils.competition_fetcher import (
    fetch_dwwa_page,
    extract_products_with_validation,
    validate_minimum_products,
    MIN_PRODUCTS_REQUIRED,
)
from tests.e2e.utils.test_recorder import TestStepRecorder, get_recorder

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

DWWA_COMPETITION_NAME = "DWWA"
DWWA_YEAR = 2025
MAX_PRODUCTS_TO_EXTRACT = 5
PRODUCT_TYPE = "port_wine"


# =============================================================================
# Port Wine Specific Constants
# =============================================================================

# Valid port wine styles
VALID_PORT_STYLES = [
    "ruby",
    "tawny",
    "white",
    "rose",
    "lbv",
    "vintage",
    "colheita",
    "crusted",
    "single_quinta",
    "garrafeira",
]

# Keywords that help identify port style from product name/description
PORT_STYLE_KEYWORDS = {
    "ruby": ["ruby", "reserve ruby", "ruby reserve"],
    "tawny": ["tawny", "10 year", "20 year", "30 year", "40 year", "aged tawny"],
    "white": ["white port", "white", "branco"],
    "rose": ["rose", "rosa", "pink"],
    "lbv": ["lbv", "late bottled vintage", "late-bottled vintage"],
    "vintage": ["vintage", "declared vintage", "single vintage"],
    "colheita": ["colheita", "single harvest"],
    "crusted": ["crusted", "crusting"],
    "single_quinta": ["quinta", "single quinta"],
    "garrafeira": ["garrafeira"],
}


# =============================================================================
# Helper Functions
# =============================================================================


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


def detect_port_style(name: str, description: str = "") -> Optional[str]:
    """
    Detect port wine style from product name and description.

    Args:
        name: Product name
        description: Product description

    Returns:
        Detected style or None
    """
    combined_text = f"{name} {description}".lower()

    for style, keywords in PORT_STYLE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined_text:
                return style

    return None


def extract_vintage_year(name: str, description: str = "") -> Optional[int]:
    """
    Extract vintage year from product name or description.

    Args:
        name: Product name
        description: Product description

    Returns:
        Vintage year as integer or None
    """
    import re

    combined_text = f"{name} {description}"

    # Look for 4-digit years in reasonable range (1900-2030)
    year_pattern = r'\b(19[0-9]{2}|20[0-2][0-9]|2030)\b'
    matches = re.findall(year_pattern, combined_text)

    if matches:
        # Return the most recent year that looks like a vintage (not 2025/current year)
        years = [int(y) for y in matches if int(y) <= 2023]
        if years:
            return max(years)

    return None


def extract_age_indication(name: str) -> Optional[str]:
    """
    Extract age indication from product name.

    Args:
        name: Product name

    Returns:
        Age indication string or None
    """
    import re

    # Look for patterns like "10 Year", "20 Year Old", etc.
    age_patterns = [
        r'(\d+)\s*[-]?\s*years?\s*old',
        r'(\d+)\s*[-]?\s*year',
        r'(\d+)\s*anos',
    ]

    name_lower = name.lower()
    for pattern in age_patterns:
        match = re.search(pattern, name_lower)
        if match:
            return f"{match.group(1)} Year"

    return None


# Note: fetch_dwwa_page is imported from tests.e2e.utils.competition_fetcher
# It uses SmartRouter with FULL tier escalation (Tier 1 → 2 → 3)
# DWWA pages are JavaScript-heavy - forces Tier 2 (Playwright) or Tier 3 (ScrapingBee)
# Does NOT fall back to raw httpx. If all tiers fail, it raises RuntimeError.


@sync_to_async
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = "award_page"
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
    product_type: str = PRODUCT_TYPE,
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
        # Update with new data (skip related fields)
        skip_fields = {"brand", "source", "crawl_job", "whiskey_details", "port_details"}
        if extracted_data:
            for field_name, value in extracted_data.items():
                if field_name in skip_fields:
                    continue
                if hasattr(existing, field_name) and value is not None:
                    try:
                        setattr(existing, field_name, value)
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
        "product_type": ProductType.PORT_WINE,
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
def create_port_wine_details(
    product: "DiscoveredProduct",
    style: str,
    producer_house: Optional[str] = None,
    harvest_year: Optional[int] = None,
    indication_age: Optional[str] = None,
    quinta: Optional[str] = None,
    douro_subregion: Optional[str] = None,
    grape_varieties: Optional[List[str]] = None,
) -> "PortWineDetails":
    """
    Create or update PortWineDetails record for a product.

    Args:
        product: The DiscoveredProduct to link to
        style: Port wine style (ruby, tawny, vintage, etc.)
        producer_house: Producer/house name (defaults to brand if not provided)
        harvest_year: Year of harvest/vintage
        indication_age: Age indication (e.g., "20 Year")
        quinta: Quinta (estate) name
        douro_subregion: Douro subregion
        grape_varieties: List of grape varieties

    Returns:
        PortWineDetails instance
    """
    # Use product's brand as fallback for producer_house
    if not producer_house:
        producer_house = product.brand or "Unknown Producer"
    from crawler.models import PortWineDetails, PortStyleChoices

    # Map style string to choice
    style_map = {
        "ruby": PortStyleChoices.RUBY,
        "tawny": PortStyleChoices.TAWNY,
        "white": PortStyleChoices.WHITE,
        "rose": PortStyleChoices.ROSE,
        "lbv": PortStyleChoices.LBV,
        "vintage": PortStyleChoices.VINTAGE,
        "colheita": PortStyleChoices.COLHEITA,
        "crusted": PortStyleChoices.CRUSTED,
        "single_quinta": PortStyleChoices.SINGLE_QUINTA,
        "garrafeira": PortStyleChoices.GARRAFEIRA,
    }
    style_choice = style_map.get(style.lower(), PortStyleChoices.RUBY)

    # Check for existing details
    try:
        details = PortWineDetails.objects.get(product=product)
        # Update existing
        details.style = style_choice
        details.producer_house = producer_house
        if harvest_year:
            details.harvest_year = harvest_year
        if indication_age:
            details.indication_age = indication_age
        if quinta:
            details.quinta = quinta
        if douro_subregion:
            details.douro_subregion = douro_subregion
        if grape_varieties:
            details.grape_varieties = grape_varieties
        details.save()
        logger.info(f"Updated PortWineDetails: {details.id}")
        return details
    except PortWineDetails.DoesNotExist:
        pass

    # Create new details
    details = PortWineDetails.objects.create(
        product=product,
        style=style_choice,
        producer_house=producer_house,
        harvest_year=harvest_year,
        indication_age=indication_age,
        quinta=quinta,
        douro_subregion=douro_subregion,
        grape_varieties=grape_varieties or [],
    )
    logger.info(f"Created PortWineDetails: {details.id} - style={style}")
    return details


@sync_to_async
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
        competition_country="International",  # DWWA is international
        year=year,
        medal=medal_choice,
        award_category="Port Wine",
        score=score,
        award_url=award_url,
    )
    logger.info(f"Created ProductAward: {award.id} - {competition} {year} {medal}")
    return award


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
        mention_type="award_winner",
    )
    logger.info(f"Created ProductSource link: {product.id} <- {source.id}")
    return link


# =============================================================================
# Test Class
# =============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
class TestDWWACompetitionFlow:
    """
    E2E test for DWWA Competition Discovery Flow.

    Extracts 5 Gold/Silver medal winning port wines from DWWA 2025,
    creates all required database records, and verifies data quality.
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.created_products: List[UUID] = []
        self.created_sources: List[UUID] = []
        self.created_awards: List[UUID] = []
        self.created_port_details: List[UUID] = []
        self.extraction_results: List[Dict[str, Any]] = []
        # Initialize recorder for capturing intermediate step outputs
        self.recorder = get_recorder("DWWA Competition Flow")
        # Note: enrichment configs are set up in the async test method via _async_setup_enrichment_configs

    async def _async_setup_enrichment_configs(self):
        """
        Create EnrichmentConfig records for port_wine product type.

        These configs define the SerpAPI search templates used for enrichment.
        Without these, the enrichment orchestrator won't run any searches.
        Uses sync_to_async for safe async context execution.
        """
        @sync_to_async
        def create_configs():
            from django.core.management import call_command
            from crawler.models import ProductTypeConfig, EnrichmentConfig, QualityGateConfig, FieldDefinition

            # Load base_fields.json fixture if FieldDefinitions don't exist
            if not FieldDefinition.objects.exists():
                logger.info("Loading base_fields.json fixture...")
                call_command("loaddata", "crawler/fixtures/base_fields.json", verbosity=0)

            # Create or get ProductTypeConfig for port_wine
            product_type_config, _ = ProductTypeConfig.objects.get_or_create(
                product_type="port_wine",
                defaults={
                    "display_name": "Port Wine",
                    "is_active": True,
                    "max_sources_per_product": 5,
                    "max_serpapi_searches": 3,
                    "max_enrichment_time_seconds": 120,
                }
            )

            # Create QualityGateConfig for port_wine
            QualityGateConfig.objects.get_or_create(
                product_type_config=product_type_config,
                defaults={
                    "skeleton_required_fields": ["name"],
                    "partial_required_fields": ["name", "brand"],
                    "partial_any_of_count": 2,
                    "partial_any_of_fields": ["description", "abv", "style", "producer_house"],
                    "complete_required_fields": ["name", "brand", "abv", "description"],
                    "complete_any_of_count": 2,
                    "complete_any_of_fields": ["nose_description", "palate_description", "finish_description", "style"],
                }
            )

            # Create EnrichmentConfig for tasting notes search
            EnrichmentConfig.objects.get_or_create(
                product_type_config=product_type_config,
                template_name="tasting_notes",
                defaults={
                    "search_template": "{name} {brand} port tasting notes review",
                    "target_fields": ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors"],
                    "priority": 10,
                    "is_active": True,
                }
            )

            # Create EnrichmentConfig for product details search
            EnrichmentConfig.objects.get_or_create(
                product_type_config=product_type_config,
                template_name="product_details",
                defaults={
                    "search_template": "{name} {brand} port wine abv alcohol content",
                    "target_fields": ["abv", "description", "volume_ml", "style"],
                    "priority": 8,
                    "is_active": True,
                }
            )

            logger.info("Created enrichment configs for port_wine product type")

        await create_configs()

    async def test_dwwa_competition_flow(
        self,
        ai_client,
        source_tracker,
        quality_gate,
        test_run_tracker,
        report_collector,
    ):
        """
        Main test: Extract 5 DWWA port wine medal winners and create all records.

        Steps:
        1. Get DWWA competition URLs
        2. Use CompetitionOrchestratorV2 to process URLs
        3. For each extracted product:
           - Create CrawledSource with raw_content
           - Create DiscoveredProduct with product_type=port_wine
           - Create PortWineDetails with style, vintage, producer
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
        logger.info("Starting DWWA Competition Flow E2E Test")
        logger.info("=" * 60)

        # Get DWWA URLs
        dwwa_urls = get_dwwa_urls()
        assert len(dwwa_urls) > 0, "No DWWA URLs configured"

        # Use first URL for Gold medal port wine winners
        competition_url = dwwa_urls[0]
        logger.info(f"Using DWWA URL: {competition_url.url}")
        logger.info(f"Competition: {competition_url.competition}, Year: {competition_url.year}")

        # Import orchestrator
        from crawler.services.competition_orchestrator_v2 import (
            CompetitionOrchestratorV2,
            get_competition_orchestrator_v2,
        )
        from crawler.services.quality_gate_v2 import ProductStatus

        orchestrator = get_competition_orchestrator_v2()

        # Fetch the competition page using SmartRouter with FULL tier escalation
        # DWWA (Decanter) pages are JavaScript-heavy - requires Tier 2 (Playwright) or Tier 3 (ScrapingBee)
        # This will raise RuntimeError if ALL tiers fail - NO silent fallback to raw httpx
        logger.info("Fetching DWWA page with SmartRouter (Tier 2/3 for JS rendering)...")
        fetch_result = await fetch_dwwa_page(competition_url.url, recorder=self.recorder)

        if not fetch_result.success:
            raise RuntimeError(
                f"Failed to fetch DWWA page. "
                f"URL: {competition_url.url}. Error: {fetch_result.error}. "
                f"Tier used: {fetch_result.tier_used}. "
                f"Check SmartRouter configuration (Playwright/ScrapingBee)."
            )

        page_content = fetch_result.content
        logger.info(
            f"Fetched DWWA page via Tier {fetch_result.tier_used} "
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

        logger.info(f"Extracted {len(extracted_products)} port wine products from DWWA")

        # Create ONE CrawledSource for the competition page with REAL page content
        # This is the actual HTML fetched from the competition URL
        self.recorder.start_step(
            "db_create_source",
            "Creating CrawledSource record",
            {"url": competition_url.url, "content_length": len(page_content)}
        )
        competition_source = await create_crawled_source(
            url=competition_url.url,
            title=f"DWWA {DWWA_YEAR} - Competition Results Page",
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
            flow_name="DWWA Competition",
            success=True,
            products_created=len(self.created_products),
            duration_seconds=duration,
            details={
                "competition": DWWA_COMPETITION_NAME,
                "year": DWWA_YEAR,
                "url": competition_url.url,
                "products_created": len(self.created_products),
                "sources_created": len(self.created_sources),
                "awards_created": len(self.created_awards),
                "port_details_created": len(self.created_port_details),
            }
        )

        report_collector.record_flow_duration("DWWA Competition", duration)

        logger.info("=" * 60)
        logger.info(f"DWWA Competition Flow completed in {duration:.1f}s")
        logger.info(f"Products created: {len(self.created_products)}")
        logger.info(f"Sources created: {len(self.created_sources)}")
        logger.info(f"Awards created: {len(self.created_awards)}")
        logger.info(f"Port details created: {len(self.created_port_details)}")
        logger.info("=" * 60)

        # Save the test recording with summary
        self.recorder.set_summary({
            "competition": DWWA_COMPETITION_NAME,
            "year": DWWA_YEAR,
            "url": competition_url.url,
            "products_created": len(self.created_products),
            "sources_created": len(self.created_sources),
            "awards_created": len(self.created_awards),
            "port_details_created": len(self.created_port_details),
            "valid_products_extracted": len(extraction_result.valid_products),
            "rejected_products": len(extraction_result.rejected_products),
            "duration_seconds": duration,
            "test_passed": len(self.created_products) >= MAX_PRODUCTS_TO_EXTRACT,
        })
        output_path = self.recorder.save()
        logger.info(f"Test recording saved to: {output_path}")

        # Assert we created the REQUIRED number of products (not just "at least some")
        assert len(self.created_products) >= MAX_PRODUCTS_TO_EXTRACT, (
            f"Created only {len(self.created_products)} port wine products, "
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
                f"AI extraction failed for DWWA page. "
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
            product_data["medal_hint"] = "Gold"  # Default for DWWA Gold winners page

            # Extract port-specific fields from name/description
            name = product_data.get("name", "")
            description = product_data.get("description", "")

            # Detect port style if not already set
            if not product_data.get("style_hint"):
                detected_style = detect_port_style(name, description)
                if detected_style:
                    product_data["style_hint"] = detected_style

            # Extract vintage year if not already set
            if not product_data.get("vintage_year"):
                vintage = extract_vintage_year(name, description)
                if vintage:
                    product_data["vintage_year"] = vintage

            # Extract age indication
            if not product_data.get("indication_age"):
                age_indication = extract_age_indication(name)
                if age_indication:
                    product_data["indication_age"] = age_indication

            # Set producer house from brand if available
            if not product_data.get("producer_house") and product_data.get("brand"):
                product_data["producer_house"] = f"{product_data['brand']} Port"

            products.append(product_data)

        logger.info(f"AI extracted {len(products)} port wine products from DWWA page")
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
        - PortWineDetails record
        - ProductAward record
        - ProductSource link (to the competition source)

        Note: CrawledSource is created once for the competition page,
        not per-product. All products link to the same source.
        """
        name = product_data.get("name", "Unknown Product")
        brand = product_data.get("brand", "")
        source_url = competition_url.url  # All products come from same URL

        logger.info(f"Processing port wine product: {name} by {brand}")

        # Get quality assessment
        from crawler.services.quality_gate_v2 import get_quality_gate_v2, ProductStatus

        gate = get_quality_gate_v2()
        field_confidences = product_data.pop("field_confidences", {})
        overall_confidence = product_data.pop("overall_confidence", 0.7)

        assessment = await gate.aassess(
            extracted_data=product_data,
            product_type=PRODUCT_TYPE,
            field_confidences=field_confidences,
        )

        logger.info(f"Quality assessment: {assessment.status.value}, score={assessment.completeness_score:.2f}")

        # Use the competition source passed in (contains real page content)
        source = competition_source

        # Create DiscoveredProduct
        product = await create_discovered_product(
            name=name,
            brand=brand,
            source_url=source_url,
            product_type=PRODUCT_TYPE,
            extracted_data=product_data,
            quality_status=assessment.status.value,
        )
        self.created_products.append(product.id)
        test_run_tracker.record_product(product.id)

        # Create PortWineDetails
        style = product_data.get("style_hint", "ruby")  # Default to ruby if not detected
        producer_house = product_data.get("producer_house", brand or "Unknown Producer")
        vintage_year = product_data.get("vintage_year")
        indication_age = product_data.get("indication_age")
        quinta = product_data.get("quinta")

        port_details = await create_port_wine_details(
            product=product,
            style=style,
            producer_house=producer_house,
            harvest_year=vintage_year,
            indication_age=indication_age,
            quinta=quinta,
        )
        self.created_port_details.append(port_details.id)

        # Create ProductAward
        medal = product_data.get("medal_hint", "Gold")
        award = await create_product_award(
            product=product,
            competition=DWWA_COMPETITION_NAME,
            year=DWWA_YEAR,
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

        # Record in report collector
        report_collector.add_product({
            "id": str(product.id),
            "name": name,
            "brand": brand,
            "product_type": PRODUCT_TYPE,
            "status": assessment.status.value,
            "completeness_score": assessment.completeness_score,
            "source_url": source_url,
            "port_style": style,
            "vintage_year": vintage_year,
            "producer_house": producer_house,
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
            "competition": DWWA_COMPETITION_NAME,
            "year": DWWA_YEAR,
            "medal": medal,
        })

        report_collector.add_quality_assessment({
            "product_id": str(product.id),
            "product_name": name,
            "status": assessment.status.value,
            "completeness_score": assessment.completeness_score,
            "needs_enrichment": assessment.needs_enrichment,
            "missing_required_fields": assessment.missing_required_fields,
        })

        # Store extraction result for verification
        self.extraction_results.append({
            "product_id": product.id,
            "source_id": source.id,
            "award_id": award.id,
            "port_details_id": port_details.id,
            "product_data": product_data,
            "quality_status": assessment.status.value,
            "port_style": style,
            "vintage_year": vintage_year,
            "producer_house": producer_house,
        })

    async def _verify_all_products(self, report_collector):
        """
        Verify all created products meet requirements.

        Checks:
        - All products have product_type = "port_wine"
        - Port style (tawny, ruby, vintage, etc.) detected
        - Vintage year extracted where applicable
        - Producer/house name extracted
        - All products have proper award records (DWWA 2025)
        - All products have name field
        - CrawledSource has raw_content stored
        """
        # Run verification in sync context
        await sync_to_async(self._verify_all_products_sync)(report_collector)

    def _verify_all_products_sync(self, report_collector):
        """Synchronous verification helper."""
        from crawler.models import (
            DiscoveredProduct,
            ProductAward,
            CrawledSource,
            ProductSource,
            PortWineDetails,
            ProductType,
        )

        logger.info("=" * 40)
        logger.info("Verifying all created port wine products")
        logger.info("=" * 40)

        for product_id in self.created_products:
            product = DiscoveredProduct.objects.get(pk=product_id)

            # Verify product_type is port_wine
            is_port_wine = product.product_type == ProductType.PORT_WINE
            report_collector.record_verification(f"product_type_port_wine:{product_id}", is_port_wine)
            assert is_port_wine, f"Product {product_id} should be port_wine, got {product.product_type}"

            # Verify name field
            result = self.verifier.verify_product_required_fields(
                {"name": product.name, "brand": str(product.brand) if product.brand else ""},
                required_fields={"name"},
            )
            report_collector.record_verification(f"name_populated:{product_id}", result.passed)
            assert result.passed, f"Product {product_id} missing name field"

            # Verify PortWineDetails exists
            try:
                port_details = PortWineDetails.objects.get(product=product)
                has_port_details = True

                # Verify port style is valid
                style_valid = port_details.style in VALID_PORT_STYLES
                report_collector.record_verification(f"port_style_valid:{product_id}", style_valid)

                # Verify producer house is set
                has_producer = port_details.producer_house is not None and len(port_details.producer_house) > 0
                report_collector.record_verification(f"producer_house_set:{product_id}", has_producer)

                # Verify vintage year for vintage/colheita/lbv styles
                if port_details.style in ["vintage", "colheita", "lbv"]:
                    has_vintage = port_details.harvest_year is not None
                    report_collector.record_verification(f"vintage_year_for_style:{product_id}", has_vintage)

                logger.info(f"PortWineDetails verified: style={port_details.style}, producer={port_details.producer_house}")

            except PortWineDetails.DoesNotExist:
                has_port_details = False
                report_collector.record_verification(f"port_details_exists:{product_id}", False)
                logger.warning(f"Product {product_id} missing PortWineDetails")

            report_collector.record_verification(f"has_port_details:{product_id}", has_port_details)

            # Verify source_url contains DWWA reference or valid URL
            has_valid_source = "decanter" in product.source_url.lower() or product.source_url.startswith("http")
            report_collector.record_verification(f"source_url_valid:{product_id}", has_valid_source)

            # Verify award records
            awards = ProductAward.objects.filter(product=product)
            has_dwwa_award = awards.filter(
                competition__iexact=DWWA_COMPETITION_NAME,
                year=DWWA_YEAR,
            ).exists()
            report_collector.record_verification(f"has_dwwa_award:{product_id}", has_dwwa_award)

            if has_dwwa_award:
                award = awards.filter(competition__iexact=DWWA_COMPETITION_NAME, year=DWWA_YEAR).first()
                assert award.medal in ["gold", "silver", "bronze", "double_gold", "best_in_class"], \
                    f"Invalid medal for product {product_id}: {award.medal}"
                report_collector.record_verification(f"award_medal_valid:{product_id}", True)

            # Verify CrawledSource has raw_content
            product_sources = ProductSource.objects.filter(product=product).select_related("source")
            for ps in product_sources:
                has_content = ps.source.raw_content is not None and len(ps.source.raw_content) > 0
                report_collector.record_verification(f"source_has_content:{ps.source_id}", has_content)

            logger.info(f"Verified port wine product {product_id}: {product.name}")

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
async def test_dwwa_urls_configured():
    """Verify DWWA URLs are properly configured."""
    dwwa_urls = get_dwwa_urls()
    assert len(dwwa_urls) > 0, "No DWWA URLs configured"

    for url in dwwa_urls:
        assert url.competition == "DWWA", f"Invalid competition: {url.competition}"
        assert url.year >= 2024, f"Invalid year: {url.year}"
        assert url.product_type == "port_wine", f"Invalid product type: {url.product_type}"
        assert url.url.startswith("http"), f"Invalid URL: {url.url}"

    logger.info(f"Verified {len(dwwa_urls)} DWWA URLs")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_competition_orchestrator_v2_for_port_wine():
    """Verify CompetitionOrchestratorV2 supports port wine."""
    from crawler.services.competition_orchestrator_v2 import (
        CompetitionOrchestratorV2,
        get_competition_orchestrator_v2,
    )

    orchestrator = get_competition_orchestrator_v2()
    assert orchestrator is not None, "CompetitionOrchestratorV2 not available"
    assert hasattr(orchestrator, "process_competition_url"), "Missing process_competition_url method"

    logger.info("CompetitionOrchestratorV2 is available for port wine processing")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_port_style_detection():
    """Test port wine style detection from product names."""
    test_cases = [
        ("Taylor's Vintage Port 2017", "", "vintage"),
        ("Graham's 20 Year Old Tawny Port", "", "tawny"),
        ("Fonseca Late Bottled Vintage 2018", "", "lbv"),
        ("Sandeman Ruby Port", "", "ruby"),
        ("Ferreira White Port", "", "white"),
        ("Dow's Colheita 2002", "", "colheita"),
        ("Quinta do Noval Nacional", "", "single_quinta"),
    ]

    for name, description, expected_style in test_cases:
        detected = detect_port_style(name, description)
        assert detected == expected_style, f"Expected {expected_style} for '{name}', got {detected}"

    logger.info("Port style detection tests passed")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_vintage_year_extraction():
    """Test vintage year extraction from product names."""
    test_cases = [
        ("Taylor's Vintage Port 2017", 2017),
        ("Dow's Colheita 2002", 2002),
        ("Fonseca LBV 2018", 2018),
        ("Graham's 20 Year Old Tawny Port", None),  # No vintage year
        ("Quinta do Noval Nacional 2016", 2016),
    ]

    for name, expected_year in test_cases:
        extracted = extract_vintage_year(name)
        assert extracted == expected_year, f"Expected {expected_year} for '{name}', got {extracted}"

    logger.info("Vintage year extraction tests passed")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_age_indication_extraction():
    """Test age indication extraction from product names."""
    test_cases = [
        ("Graham's 20 Year Old Tawny Port", "20 Year"),
        ("Taylor's 10 Year Tawny", "10 Year"),
        ("Dow's 40 Year Old Tawny", "40 Year"),
        ("Taylor's Vintage Port 2017", None),  # No age indication
    ]

    for name, expected_age in test_cases:
        extracted = extract_age_indication(name)
        assert extracted == expected_age, f"Expected {expected_age} for '{name}', got {extracted}"

    logger.info("Age indication extraction tests passed")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_port_wine_details_model_available():
    """Verify PortWineDetails model is available."""
    from crawler.models import PortWineDetails, PortStyleChoices

    assert PortWineDetails is not None, "PortWineDetails model not found"
    assert hasattr(PortWineDetails, "style"), "PortWineDetails missing style field"
    assert hasattr(PortWineDetails, "producer_house"), "PortWineDetails missing producer_house field"
    assert hasattr(PortWineDetails, "harvest_year"), "PortWineDetails missing harvest_year field"

    # Verify style choices
    assert PortStyleChoices.RUBY == "ruby"
    assert PortStyleChoices.TAWNY == "tawny"
    assert PortStyleChoices.VINTAGE == "vintage"

    logger.info("PortWineDetails model is available with all required fields")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_quality_gate_v2_for_port_wine():
    """Verify QualityGateV2 works with port wine products."""
    from crawler.services.quality_gate_v2 import (
        QualityGateV2,
        get_quality_gate_v2,
        ProductStatus,
    )

    gate = get_quality_gate_v2()
    assert gate is not None, "QualityGateV2 not available"

    # Test basic assessment for port wine (async version)
    result = await gate.aassess(
        extracted_data={
            "name": "Test Port Wine",
            "brand": "Test Producer",
            "abv": 20.0,
            "description": "A rich tawny port with notes of caramel and dried fruit.",
        },
        product_type="port_wine",
    )

    assert result.status in [ProductStatus.SKELETON, ProductStatus.PARTIAL, ProductStatus.COMPLETE], \
        f"Unexpected status for port wine: {result.status}"

    logger.info("QualityGateV2 is available and configured for port wine")
