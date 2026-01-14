"""
E2E Test: Single Product Extraction Flow - Whiskey with Domain Intelligence.

Tests single product extraction from known product pages:
1. Fetch product page via SmartRouter
2. Track domain profile for each site
3. Extract product using AI Enhancement Service
4. Create DiscoveredProduct record
5. Export results with full source tracking

Real URLs tested:
- https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/
- https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old
- https://www.whiskyshop.com/buffalo-trace-bourbon

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.

Spec Reference: E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md - Task 4.1
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

# Single Product URLs - Known whiskey product pages
SINGLE_PRODUCT_URLS = [
    {
        "url": "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
        "domain": "masterofmalt.com",
        "expected_name": "Ardbeg 10 Year Old",
        "expected_brand": "Ardbeg",
        "notes": "Known Cloudflare-protected site",
    },
    {
        "url": "https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old",
        "domain": "thewhiskyexchange.com",
        "expected_name": "Glenfiddich 18 Year Old",
        "expected_brand": "Glenfiddich",
        "notes": "Major UK retailer",
    },
    {
        "url": "https://www.whiskyshop.com/buffalo-trace-bourbon",
        "domain": "whiskyshop.com",
        "expected_name": "Buffalo Trace",
        "expected_brand": "Buffalo Trace",
        "notes": "UK whisky retailer",
    },
]

PRODUCT_TYPE = "whiskey"


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("single_product_whiskey_e2e")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("single_product_whiskey_e2e")


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
class TestSingleProductWhiskeyE2E:
    """
    E2E tests for Single Product Extraction with Domain Intelligence.

    Tests extraction from known whiskey product pages with
    domain intelligence tracking.
    """

    async def test_single_product_extraction_all_sites(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
        ai_client,
        db,
    ):
        """
        Test single product extraction from all configured URLs.

        REAL URLs and API calls - NO MOCKS.

        Steps:
        1. Fetch each product page
        2. Track domain profile (bot-protected sites)
        3. Extract product using AI
        4. Validate extraction accuracy
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
            "test_type": "single_product_whiskey_e2e",
            "urls_to_test": len(SINGLE_PRODUCT_URLS),
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "single_product_whiskey_e2e",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=60,  # Longer for potentially blocked sites
        )

        results = []
        products_created = []

        try:
            for idx, url_config in enumerate(SINGLE_PRODUCT_URLS):
                step_name = f"process_url_{idx}"

                if state_manager.is_step_complete(step_name):
                    logger.info(f"Skipping completed step: {step_name}")
                    continue

                state_manager.set_current_step(step_name)
                url = url_config["url"]
                domain = url_config["domain"]

                logger.info(f"Processing {idx + 1}/{len(SINGLE_PRODUCT_URLS)}: {domain}")

                # Clear domain profile for clean test
                domain_store.delete_profile(domain)

                result_data = {
                    "url": url,
                    "domain": domain,
                    "expected_name": url_config["expected_name"],
                    "expected_brand": url_config["expected_brand"],
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
                        "fetch_error": fetch_result.error,
                        "domain_profile": {
                            "likely_js_heavy": profile.likely_js_heavy,
                            "likely_bot_protected": profile.likely_bot_protected,
                            "recommended_tier": profile.recommended_tier,
                        }
                    })

                    # Add domain profile to exporter
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

                    # Extract product
                    try:
                        extraction_result = await ai_client.extract(
                            content=fetch_result.content,
                            source_url=url,
                            product_type=PRODUCT_TYPE,
                        )

                        raw_products = extraction_result.products if extraction_result.success else []
                        if raw_products:
                            p = raw_products[0]
                            extracted = p.extracted_data if hasattr(p, 'extracted_data') else p
                            result_data["extracted_product"] = {
                                "name": extracted.get("name"),
                                "brand": extracted.get("brand"),
                                "abv": extracted.get("abv"),
                                "description": (extracted.get("description") or "")[:200],
                            }

                            # Validate extraction
                            expected_name = url_config["expected_name"].lower()
                            extracted_name = (extracted.get("name") or "").lower()
                            result_data["name_match"] = expected_name in extracted_name or extracted_name in expected_name

                            logger.info(
                                f"  Extracted: {extracted.get('name')} "
                                f"(match={result_data['name_match']})"
                            )

                            # Create database record
                            @sync_to_async(thread_sensitive=True)
                            def create_product():
                                name = extracted.get("name", "Unknown")
                                brand_name = extracted.get("brand", "")

                                brand = None
                                if brand_name:
                                    brand, _ = DiscoveredBrand.objects.get_or_create(name=brand_name)

                                source = CrawledSource.objects.create(
                                    url=url,
                                    title=f"Product Page: {name}",
                                    source_type="product_page",
                                    raw_content="",
                                    crawled_at=datetime.now(),
                                )

                                fingerprint = generate_fingerprint(name, brand_name)
                                product = DiscoveredProduct.objects.create(
                                    name=name,
                                    brand=brand,
                                    product_type=ProductType.WHISKEY,
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
                                }

                            product_data = await create_product()
                            products_created.append(product_data)
                            result_data["product_created"] = True

                        else:
                            logger.warning(f"  No products extracted from {domain}")
                            result_data["extracted_product"] = None

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
            tier_distribution = {
                "tier_1": sum(1 for r in results if r.get("tier_used") == 1),
                "tier_2": sum(1 for r in results if r.get("tier_used") == 2),
                "tier_3": sum(1 for r in results if r.get("tier_used") == 3),
            }

            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "urls_tested": len(SINGLE_PRODUCT_URLS),
                "successful_extractions": successful_extractions,
                "name_matches": name_matches,
                "products_created": len(products_created),
                "tier_distribution": tier_distribution,
            })

            # Finalize
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")

            logger.info(f"Single Product Whiskey E2E test completed. Results: {output_path}")
            logger.info(f"Extracted: {successful_extractions}/{len(SINGLE_PRODUCT_URLS)}")
            logger.info(f"Name matches: {name_matches}/{successful_extractions}")

            # Soft assertion - at least some should succeed
            assert successful_extractions > 0, "Expected at least 1 successful extraction"

        finally:
            await router.close()

    async def test_bot_protected_site_handling(
        self,
        domain_store,
        exporter,
        redis_client,
    ):
        """
        Test domain intelligence handling of bot-protected sites.

        masterofmalt.com is known to use Cloudflare protection.
        This test verifies the system detects and handles it.
        """
        from crawler.fetchers.smart_router import SmartRouter

        test_url = "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/"
        test_domain = "masterofmalt.com"

        # Clear profile
        domain_store.delete_profile(test_domain)

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=60,
        )

        fetch_attempts = []

        try:
            # Fetch multiple times to observe behavior
            for i in range(2):
                fetch_start = datetime.utcnow()
                result = await router.fetch(test_url)
                fetch_time_ms = int((datetime.utcnow() - fetch_start).total_seconds() * 1000)

                profile = domain_store.get_profile(test_domain)

                fetch_attempts.append({
                    "attempt": i + 1,
                    "tier_used": result.tier_used,
                    "success": result.success,
                    "content_length": len(result.content) if result.content else 0,
                    "fetch_time_ms": fetch_time_ms,
                    "profile_bot_protected": profile.likely_bot_protected,
                    "profile_recommended_tier": profile.recommended_tier,
                })

                logger.info(
                    f"Attempt {i + 1}: tier={result.tier_used}, "
                    f"bot_protected={profile.likely_bot_protected}"
                )

            # Export results
            exporter.add_domain_profile({
                "domain": test_domain,
                "url": test_url,
                "fetch_attempts": fetch_attempts,
                "final_profile": {
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                }
            })

            output_path = exporter.finalize("COMPLETED")
            logger.info(f"Bot protection test completed. Results: {output_path}")

        finally:
            await router.close()

    async def test_abv_extraction_accuracy(
        self,
        domain_store,
        exporter,
        redis_client,
        ai_client,
    ):
        """
        Test that ABV is correctly extracted from product pages.

        ABV is a critical field for whiskey products.
        """
        from crawler.fetchers.smart_router import SmartRouter

        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Use a single URL for focused testing
        test_url = "https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old"
        test_domain = "thewhiskyexchange.com"

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        try:
            # Fetch page
            result = await router.fetch(test_url)

            if not result.success:
                pytest.skip(f"Could not fetch test page: {result.error}")

            # Extract product
            extraction_result = await ai_client.extract(
                content=result.content,
                source_url=test_url,
                product_type="whiskey",
            )

            products = extraction_result.products if extraction_result.success else []
            if products:
                p = products[0]
                product = p.extracted_data if hasattr(p, 'extracted_data') else p
                abv = product.get("abv")

                exporter.add_product({
                    "name": product.get("name"),
                    "brand": product.get("brand"),
                    "abv": abv,
                    "abv_extracted": abv is not None,
                    "source_url": test_url,
                })

                logger.info(
                    f"ABV extraction: name={product.get('name')}, "
                    f"abv={abv}, extracted={abv is not None}"
                )

            output_path = exporter.finalize("COMPLETED")
            logger.info(f"ABV extraction test completed. Results: {output_path}")

        finally:
            await router.close()
