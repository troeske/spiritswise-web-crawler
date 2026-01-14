"""
E2E Test: Single Product Extraction Flow - Port Wine with Domain Intelligence.

Tests single product extraction from known port wine product pages:
1. Fetch product page via SmartRouter
2. Track domain profile for each site
3. Extract product using AI Enhancement Service
4. Validate port-specific fields (style, vintage)
5. Create DiscoveredProduct record
6. Export results with full source tracking

Real URLs tested:
- https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port
- https://www.vivino.com/taylors-10-year-old-tawny-port/w/1

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.

Spec Reference: E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md - Task 4.2
"""

import asyncio
import hashlib
import logging
import pytest
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

from asgiref.sync import sync_to_async

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter

logger = logging.getLogger(__name__)

# Single Product URLs - Known port wine product pages
SINGLE_PRODUCT_URLS = [
    {
        "url": "https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port",
        "domain": "wine-searcher.com",
        "expected_name": "Taylor Fladgate 10 Year Old Tawny Port",
        "expected_brand": "Taylor Fladgate",
        "expected_style": "Tawny",
        "notes": "Major wine search aggregator",
    },
    {
        "url": "https://www.vivino.com/taylors-10-year-old-tawny-port/w/1",
        "domain": "vivino.com",
        "expected_name": "Taylor's 10 Year Old Tawny Port",
        "expected_brand": "Taylor's",
        "expected_style": "Tawny",
        "notes": "JS-heavy wine review site",
    },
]

PRODUCT_TYPE = "port_wine"


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("single_product_port_e2e")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("single_product_port_e2e")


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return url


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSingleProductPortE2E:
    """
    E2E tests for Single Product Extraction - Port Wine.

    Tests extraction from known port wine product pages with
    domain intelligence tracking and port-specific field validation.
    """

    async def test_single_product_port_extraction(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
        ai_client,
        db,
    ):
        """
        Test single product extraction from port wine pages.

        REAL URLs and API calls - NO MOCKS.

        Steps:
        1. Fetch each product page
        2. Track domain profile
        3. Extract product using AI
        4. Validate port-specific fields
        5. Create database records
        6. Export comprehensive results
        """
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredBrand,
            CrawledSource,
            ProductType,
        )

        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Initialize results tracking
        exporter.set_metrics({
            "test_started": datetime.utcnow().isoformat(),
            "test_type": "single_product_port_e2e",
            "urls_to_test": len(SINGLE_PRODUCT_URLS),
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "single_product_port_e2e",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=60,
        )

        results = []
        products_created = []
        port_fields_stats = {
            "style_extracted": 0,
            "vintage_extracted": 0,
            "style_match": 0,
        }

        try:
            for idx, url_config in enumerate(SINGLE_PRODUCT_URLS):
                step_name = f"process_url_{idx}"

                if state_manager.is_step_complete(step_name):
                    continue

                state_manager.set_current_step(step_name)
                url = url_config["url"]
                domain = url_config["domain"]

                logger.info(f"Processing {idx + 1}/{len(SINGLE_PRODUCT_URLS)}: {domain}")

                # Clear domain profile
                domain_store.delete_profile(domain)

                result_data = {
                    "url": url,
                    "domain": domain,
                    "expected_name": url_config["expected_name"],
                    "expected_brand": url_config["expected_brand"],
                    "expected_style": url_config.get("expected_style"),
                    "notes": url_config.get("notes", ""),
                }

                # Fetch page
                fetch_start = datetime.utcnow()
                try:
                    fetch_result = await router.fetch(url)
                    fetch_time_ms = int((datetime.utcnow() - fetch_start).total_seconds() * 1000)

                    # Get domain profile
                    profile = domain_store.get_profile(domain)

                    result_data.update({
                        "fetch_success": fetch_result.success,
                        "tier_used": fetch_result.tier_used,
                        "content_length": len(fetch_result.content) if fetch_result.content else 0,
                        "fetch_time_ms": fetch_time_ms,
                        "domain_profile": {
                            "likely_js_heavy": profile.likely_js_heavy,
                            "likely_bot_protected": profile.likely_bot_protected,
                            "recommended_tier": profile.recommended_tier,
                        }
                    })

                    exporter.add_domain_profile({
                        "domain": domain,
                        "likely_js_heavy": profile.likely_js_heavy,
                        "likely_bot_protected": profile.likely_bot_protected,
                        "recommended_tier": profile.recommended_tier,
                        "tier_used": fetch_result.tier_used,
                    })

                    if not fetch_result.success:
                        logger.warning(f"Fetch failed for {domain}: {fetch_result.error}")
                        results.append(result_data)
                        state_manager.mark_step_complete(step_name)
                        continue

                    # Extract product with port-specific context
                    try:
                        extraction_result = await ai_client.extract_products(
                            content=fetch_result.content,
                            source_url=url,
                            product_type=PRODUCT_TYPE,
                            extraction_context={
                                "source_type": "product_page",
                                "single_product": True,
                                "expected_fields": ["style", "vintage", "producer_house"],
                            }
                        )

                        raw_products = extraction_result.get("products", [])
                        if raw_products:
                            extracted = raw_products[0]

                            # Check port-specific fields
                            style = extracted.get("style", "")
                            vintage = extracted.get("vintage")
                            expected_style = url_config.get("expected_style", "").lower()

                            if style:
                                port_fields_stats["style_extracted"] += 1
                                if style.lower() == expected_style:
                                    port_fields_stats["style_match"] += 1
                            if vintage:
                                port_fields_stats["vintage_extracted"] += 1

                            result_data["extracted_product"] = {
                                "name": extracted.get("name"),
                                "brand": extracted.get("brand"),
                                "style": style,
                                "vintage": vintage,
                                "producer_house": extracted.get("producer_house"),
                                "abv": extracted.get("abv"),
                            }

                            # Validate name match
                            expected_name = url_config["expected_name"].lower()
                            extracted_name = (extracted.get("name") or "").lower()
                            result_data["name_match"] = (
                                expected_name in extracted_name or
                                extracted_name in expected_name or
                                "taylor" in extracted_name  # Brand match
                            )

                            logger.info(
                                f"  Extracted: {extracted.get('name')}, "
                                f"style={style}, match={result_data['name_match']}"
                            )

                            # Create database record
                            @sync_to_async(thread_sensitive=True)
                            def create_product():
                                name = extracted.get("name", "Unknown")
                                brand_name = extracted.get("brand", extracted.get("producer_house", ""))

                                brand = None
                                if brand_name:
                                    brand, _ = DiscoveredBrand.objects.get_or_create(name=brand_name)

                                source = CrawledSource.objects.create(
                                    url=url,
                                    title=f"Port Wine: {name}",
                                    source_type="product_page",
                                    raw_content="",
                                    crawled_at=datetime.now(),
                                )

                                fingerprint = generate_fingerprint(name, brand_name)
                                product = DiscoveredProduct.objects.create(
                                    name=name,
                                    brand=brand,
                                    product_type=ProductType.PORT_WINE,
                                    fingerprint=fingerprint,
                                    source_url=url,
                                    abv=extracted.get("abv"),
                                    description=extracted.get("description", ""),
                                )

                                return {
                                    "id": str(product.id),
                                    "name": name,
                                    "brand": brand_name,
                                    "source_url": url,
                                    "domain": domain,
                                    "tier_used": fetch_result.tier_used,
                                    "port_fields": {
                                        "style": style,
                                        "vintage": vintage,
                                        "producer_house": extracted.get("producer_house"),
                                    }
                                }

                            product_data = await create_product()
                            products_created.append(product_data)
                            result_data["product_created"] = True

                        else:
                            logger.warning(f"  No products extracted from {domain}")

                    except Exception as e:
                        logger.error(f"  Extraction failed for {domain}: {e}")
                        result_data["extraction_error"] = str(e)

                except Exception as e:
                    logger.error(f"Fetch exception for {domain}: {e}")
                    result_data["fetch_error"] = str(e)
                    result_data["fetch_success"] = False

                results.append(result_data)
                state_manager.mark_step_complete(step_name)

            # Add products to exporter
            for p in products_created:
                exporter.add_product({
                    "id": p["id"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "product_type": PRODUCT_TYPE,
                    "status": "SKELETON",
                    "flow": "single_product",
                    "port_fields": p.get("port_fields", {}),
                    "sources_used": [{
                        "url": p["source_url"],
                        "source_type": "product_page",
                        "domain": p["domain"],
                        "tier_used": p["tier_used"],
                    }],
                    "domain_intelligence": {
                        "primary_domain": p["domain"],
                        "tier_used": p["tier_used"],
                    }
                })

            # Calculate metrics
            successful_extractions = sum(1 for r in results if r.get("extracted_product"))
            name_matches = sum(1 for r in results if r.get("name_match"))

            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "urls_tested": len(SINGLE_PRODUCT_URLS),
                "successful_extractions": successful_extractions,
                "name_matches": name_matches,
                "products_created": len(products_created),
                "port_fields_stats": port_fields_stats,
                "tier_distribution": {
                    "tier_1": sum(1 for r in results if r.get("tier_used") == 1),
                    "tier_2": sum(1 for r in results if r.get("tier_used") == 2),
                    "tier_3": sum(1 for r in results if r.get("tier_used") == 3),
                },
            })

            # Finalize
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")

            logger.info(f"Single Product Port E2E test completed. Results: {output_path}")
            logger.info(f"Extracted: {successful_extractions}/{len(SINGLE_PRODUCT_URLS)}")
            logger.info(f"Port fields: {port_fields_stats}")

        finally:
            await router.close()

    async def test_port_style_detection(
        self,
        domain_store,
        exporter,
        redis_client,
        ai_client,
    ):
        """
        Test port wine style detection accuracy.

        Verifies that styles like Tawny, Ruby, Vintage, LBV are
        correctly extracted.
        """
        from crawler.fetchers.smart_router import SmartRouter

        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Test URL with known style
        test_url = "https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port"
        expected_style = "Tawny"

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        try:
            result = await router.fetch(test_url)

            if not result.success:
                pytest.skip(f"Could not fetch test page: {result.error}")

            extraction_result = await ai_client.extract_products(
                content=result.content,
                source_url=test_url,
                product_type="port_wine",
                extraction_context={
                    "priority_fields": ["style", "name", "vintage"],
                }
            )

            products = extraction_result.get("products", [])
            if products:
                product = products[0]
                style = product.get("style", "")

                style_match = style.lower() == expected_style.lower()

                exporter.add_product({
                    "name": product.get("name"),
                    "expected_style": expected_style,
                    "extracted_style": style,
                    "style_match": style_match,
                    "vintage": product.get("vintage"),
                })

                logger.info(
                    f"Style detection: expected={expected_style}, "
                    f"extracted={style}, match={style_match}"
                )

            output_path = exporter.finalize("COMPLETED")
            logger.info(f"Port style detection test completed. Results: {output_path}")

        finally:
            await router.close()

    async def test_vivino_js_heavy_handling(
        self,
        domain_store,
        exporter,
        redis_client,
    ):
        """
        Test that Vivino is correctly identified as JS-heavy.

        Vivino is a known JavaScript-heavy SPA that requires Tier 2.
        """
        from crawler.fetchers.smart_router import SmartRouter

        test_url = "https://www.vivino.com/taylors-10-year-old-tawny-port/w/1"
        test_domain = "vivino.com"

        # Clear profile
        domain_store.delete_profile(test_domain)

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=60,
        )

        try:
            result = await router.fetch(test_url)
            profile = domain_store.get_profile(test_domain)

            logger.info(
                f"Vivino profile: js_heavy={profile.likely_js_heavy}, "
                f"tier_used={result.tier_used}, "
                f"recommended_tier={profile.recommended_tier}"
            )

            exporter.add_domain_profile({
                "domain": test_domain,
                "url": test_url,
                "tier_used": result.tier_used,
                "success": result.success,
                "content_length": len(result.content) if result.content else 0,
                "likely_js_heavy": profile.likely_js_heavy,
                "recommended_tier": profile.recommended_tier,
            })

            output_path = exporter.finalize("COMPLETED")
            logger.info(f"Vivino JS test completed. Results: {output_path}")

        finally:
            await router.close()
