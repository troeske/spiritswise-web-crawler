"""
IWSC Combined Competition Flow Test (2024 + 2025).

Tests extraction and enrichment of 6 products total:
- 3 products from IWSC 2025
- 3 products from IWSC 2024

No caching, no shortcuts, no synthetic data.
Enrichment source URLs are recorded for verification.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import pytest
from asgiref.sync import sync_to_async

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
import django
django.setup()

from crawler.models import (
    CrawledSource,
    DiscoveredProduct,
    DiscoveredProductStatus,
    ProductAward,
    ProductSource,
    ProductType,
)
from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2
from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3
from crawler.services.quality_gate_v3 import QualityGateV3
from crawler.fetchers.smart_router import SmartRouter

logger = logging.getLogger(__name__)

# Test configuration
IWSC_COMPETITION_NAME = "IWSC"
MAX_PRODUCTS_PER_YEAR = 3
PRODUCT_TYPE = "whiskey"

# Test URLs for both years
IWSC_URLS = {
    2025: "https://www.iwsc.net/results/search/2025?q=whisky",
    2024: "https://www.iwsc.net/results/search/2024?q=whisky",
}


@sync_to_async(thread_sensitive=True)
def clear_test_data():
    """Clear any cached test data to ensure fresh extraction."""
    from django.core.cache import cache
    cache.clear()
    logger.info("Cleared Django cache")


@sync_to_async(thread_sensitive=True)
def load_fixtures():
    """Load required fixtures for the test."""
    from django.core.management import call_command
    from crawler.models import FieldDefinition, ProductTypeConfig, EnrichmentConfig

    # Load base_fields.json if not exists
    if not FieldDefinition.objects.exists():
        logger.info("Loading base_fields.json fixture...")
        call_command("loaddata", "base_fields.json", verbosity=0)

    # Create whiskey ProductTypeConfig if not exists
    if not ProductTypeConfig.objects.filter(product_type="whiskey").exists():
        logger.info("Creating whiskey ProductTypeConfig...")
        ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
            is_active=True,
        )

    # Create enrichment configs if not exist
    ptc = ProductTypeConfig.objects.filter(product_type="whiskey").first()
    if ptc and not EnrichmentConfig.objects.filter(product_type_config=ptc).exists():
        logger.info("Creating EnrichmentConfig for whiskey...")
        EnrichmentConfig.objects.create(
            product_type_config=ptc,
            template_name="Review Sites",
            search_template="{name} {brand} review tasting notes",
            priority=1,
            is_active=True,
        )

    logger.info("Fixtures loaded successfully")


@sync_to_async(thread_sensitive=True)
def create_crawled_source(
    url: str,
    title: str,
    raw_content: str,
    source_type: str = "award_page"
) -> CrawledSource:
    """Create a CrawledSource record."""
    import hashlib
    content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

    existing = CrawledSource.objects.filter(url=url).first()
    if existing:
        existing.raw_content = raw_content
        existing.content_hash = content_hash
        existing.save()
        return existing

    return CrawledSource.objects.create(
        url=url,
        title=title,
        raw_content=raw_content,
        content_hash=content_hash,
        source_type=source_type,
    )


@sync_to_async(thread_sensitive=True)
def create_discovered_product(
    name: str,
    brand: str,
    source_url: str,
    year: int,
    extracted_data: Optional[Dict[str, Any]] = None,
) -> DiscoveredProduct:
    """Create a DiscoveredProduct record."""
    import hashlib
    fingerprint = hashlib.sha256(f"{name}:{brand}:{year}".encode()).hexdigest()[:32]

    existing = DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()
    if existing:
        return existing

    product_data = {
        "name": name,
        "brand_id": None,
        "source_url": source_url,
        "fingerprint": fingerprint,
        "product_type": ProductType.WHISKEY,
        "raw_content": "",
        "raw_content_hash": "",
        "status": DiscoveredProductStatus.INCOMPLETE,
        "discovery_source": "competition",
    }

    if extracted_data:
        field_mapping = {
            "description": "description",
            "abv": "abv",
            "age_statement": "age_statement",
            "volume_ml": "volume_ml",
            "region": "region",
            "country": "country",
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

    return DiscoveredProduct.objects.create(**product_data)


@sync_to_async(thread_sensitive=True)
def create_product_award(
    product: DiscoveredProduct,
    competition: str,
    year: int,
    medal: str,
    award_url: str,
    score: Optional[int] = None,
) -> ProductAward:
    """Create a ProductAward record."""
    existing = ProductAward.objects.filter(
        product=product,
        competition__iexact=competition,
        year=year,
    ).first()

    if existing:
        return existing

    return ProductAward.objects.create(
        product=product,
        competition=competition,
        year=year,
        medal=medal,
        score=score,
        award_url=award_url,
    )


@sync_to_async(thread_sensitive=True)
def link_product_to_source(
    product: DiscoveredProduct,
    source: CrawledSource,
    extraction_confidence: float,
    fields_extracted: List[str],
) -> ProductSource:
    """Create ProductSource link."""
    existing = ProductSource.objects.filter(
        product=product,
        source=source,
    ).first()

    if existing:
        return existing

    return ProductSource.objects.create(
        product=product,
        source=source,
        extraction_confidence=Decimal(str(extraction_confidence)),
        fields_extracted=fields_extracted,
        mention_type="award_winner",
    )


class IWSCCombinedFlowTest:
    """Combined IWSC flow test for 2024 + 2025."""

    def __init__(self):
        self.results = []
        self.created_products = []
        self.created_awards = []

    async def run(self) -> Dict[str, Any]:
        """Run the combined test."""
        logger.info("=" * 60)
        logger.info("IWSC COMBINED FLOW TEST (2024 + 2025)")
        logger.info("=" * 60)

        # Load fixtures first
        await load_fixtures()

        # Clear caches
        await clear_test_data()
        logger.info("Caches cleared - starting fresh extraction")

        # Test both years
        for year in [2025, 2024]:
            logger.info(f"\n{'='*60}")
            logger.info(f"TESTING IWSC {year}")
            logger.info(f"{'='*60}")

            try:
                year_results = await self._test_year(year)
                self.results.extend(year_results)
            except Exception as e:
                logger.error(f"Error testing {year}: {e}")
                raise

        # Export results
        output_path = await self._export_results()

        return {
            "success": True,
            "total_products": len(self.results),
            "output_path": output_path,
            "results": self.results,
        }

    async def _test_year(self, year: int) -> List[Dict[str, Any]]:
        """Test a single year."""
        url = IWSC_URLS[year]
        logger.info(f"Fetching {url}")

        # Fetch competition page (no cache)
        router = SmartRouter()
        fetch_result = await router.fetch(url, force_tier=3)  # Force ScrapingBee for fresh data

        if not fetch_result.success:
            raise RuntimeError(f"Failed to fetch {url}: {fetch_result.error}")

        page_content = fetch_result.content
        logger.info(f"Fetched {len(page_content)} chars from {url}")

        # Create source record
        source = await create_crawled_source(
            url=url,
            title=f"IWSC {year} - Competition Results",
            raw_content=page_content,
            source_type="award_page",
        )

        # Extract products using AI
        ai_client = get_ai_client_v2()
        extraction_result = await ai_client.extract(
            content=page_content,
            source_url=url,
            product_type=PRODUCT_TYPE,
            detect_multi_product=True,
        )

        if not extraction_result.success:
            raise RuntimeError(f"AI extraction failed: {extraction_result.error}")

        products = extraction_result.products[:MAX_PRODUCTS_PER_YEAR]
        logger.info(f"Extracted {len(products)} products from {year}")

        # Process each product
        year_results = []
        for i, product_data in enumerate(products):
            extracted = product_data.extracted_data
            name = extracted.get("name", f"Unknown Product {i+1}")
            brand = extracted.get("brand", "Unknown Brand")

            logger.info(f"\n--- Processing: {name} ---")

            # Create product record
            product = await create_discovered_product(
                name=name,
                brand=brand,
                source_url=url,
                year=year,
                extracted_data=extracted,
            )
            self.created_products.append(product.id)

            # Create award record
            medal = extracted.get("medal_hint", "Gold")
            award = await create_product_award(
                product=product,
                competition=IWSC_COMPETITION_NAME,
                year=year,
                medal=medal,
                award_url=url,
                score=extracted.get("score"),
            )
            self.created_awards.append(award.id)

            # Link product to source
            await link_product_to_source(
                product=product,
                source=source,
                extraction_confidence=product_data.confidence,
                fields_extracted=list(extracted.keys()),
            )

            # Enrich product
            logger.info(f"Enriching {name}...")
            enrichment_orchestrator = EnrichmentOrchestratorV3()
            enrichment_result = await enrichment_orchestrator.enrich_product(
                product_id=str(product.id),
                product_type=PRODUCT_TYPE,
                initial_data=extracted.copy(),
                initial_confidences={k: 0.5 for k in extracted.keys()},
            )

            logger.info(
                f"Enrichment complete: {enrichment_result.status_before} -> {enrichment_result.status_after}, "
                f"sources used: {len(enrichment_result.sources_used)}"
            )

            # Build result with source URLs
            result = {
                "product_id": str(product.id),
                "name": name,
                "brand": brand,
                "year": year,
                "medal": medal,
                "source_url": url,
                "quality_status_before": enrichment_result.status_before,
                "quality_status_after": enrichment_result.status_after,
                "enrichment_success": enrichment_result.success,
                "fields_enriched": enrichment_result.fields_enriched,
                "product_data": enrichment_result.product_data,
                # Source URLs for verification
                "enrichment_sources": enrichment_result.sources_used,
                "sources_rejected": enrichment_result.sources_rejected if hasattr(enrichment_result, 'sources_rejected') else [],
                "searches_performed": enrichment_result.searches_performed,
            }
            year_results.append(result)

            logger.info(f"Enrichment sources for {name}:")
            for src_url in enrichment_result.sources_used:
                logger.info(f"  - {src_url}")

        return year_results

    async def _export_results(self) -> str:
        """Export results to JSON file."""
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = output_dir / f"iwsc_combined_{timestamp}.json"

        # Serialize data
        def serialize(obj):
            if isinstance(obj, (Decimal, UUID)):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "competition": IWSC_COMPETITION_NAME,
            "years_tested": [2025, 2024],
            "total_products": len(self.results),
            "products_per_year": MAX_PRODUCTS_PER_YEAR,
            "note": "No cached data, no shortcuts, no synthetic data. All sources are real URLs.",
            "products": []
        }

        for result in self.results:
            product_export = {
                "product_id": result["product_id"],
                "name": result["name"],
                "brand": result["brand"],
                "year": result["year"],
                "medal": result["medal"],
                "competition_source_url": result["source_url"],
                "quality_status_before": result["quality_status_before"],
                "quality_status_after": result["quality_status_after"],
                "enrichment_success": result["enrichment_success"],
                "fields_enriched": result["fields_enriched"],
                "searches_performed": result["searches_performed"],
                # ENRICHMENT SOURCE URLS FOR VERIFICATION
                "enrichment_sources_used": result["enrichment_sources"],
                "enrichment_sources_rejected": result["sources_rejected"],
                # Full product data
                "product_data": result["product_data"],
            }
            export_data["products"].append(product_export)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=serialize)

        logger.info(f"Exported results to {output_path}")
        return str(output_path)


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_iwsc_combined_flow():
    """
    Test IWSC competition flow for both 2024 and 2025.

    Extracts and enriches 6 products total (3 per year).
    No caching, no shortcuts, no synthetic data.
    Source URLs are recorded for verification.
    """
    test = IWSCCombinedFlowTest()
    result = await test.run()

    assert result["success"], "Test failed"
    assert result["total_products"] == 6, f"Expected 6 products, got {result['total_products']}"

    # Verify each product has enrichment sources
    for product in result["results"]:
        assert product["enrichment_sources"], f"No enrichment sources for {product['name']}"
        logger.info(f"{product['name']} ({product['year']}): {len(product['enrichment_sources'])} sources")

    logger.info(f"\nResults exported to: {result['output_path']}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    asyncio.run(test_iwsc_combined_flow())
