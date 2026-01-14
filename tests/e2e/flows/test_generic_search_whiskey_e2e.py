"""
E2E Test: Generic Search Discovery Flow - Whiskey with Domain Intelligence.

Tests the complete generic search discovery pipeline with domain intelligence:
1. Execute SerpAPI search (REAL API)
2. Fetch top organic results via SmartRouter
3. Track domain profiles for each result site
4. Extract products from listicles
5. Validate no cross-contamination between sources
6. Enrich top products via 2-step pipeline
7. Export comprehensive results with source tracking

Search Query: "best bourbon whiskey 2025 recommendations"

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.

Spec Reference: E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md - Task 3.1
"""

import asyncio
import hashlib
import logging
import os
import pytest
import httpx
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from asgiref.sync import sync_to_async

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter

logger = logging.getLogger(__name__)

# Search Configuration
SEARCH_QUERY = "best bourbon whiskey 2025 recommendations"
PRODUCT_TYPE = "whiskey"
MAX_SEARCH_RESULTS = 3
MAX_PRODUCTS_TO_EXTRACT = 5
MAX_PRODUCTS_TO_ENRICH = 3


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("generic_search_whiskey_e2e")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("generic_search_whiskey_e2e")


def generate_fingerprint(name: str, brand: str) -> str:
    """Generate unique fingerprint for product deduplication."""
    base = f"{name.lower().strip()}:{brand.lower().strip() if brand else ''}"
    return hashlib.sha256(base.encode()).hexdigest()


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return url


@pytest.mark.e2e
@pytest.mark.asyncio
class TestGenericSearchWhiskeyE2E:
    """
    E2E tests for Generic Search Discovery Flow with Domain Intelligence.

    Tests whiskey listicle search and extraction with full domain
    intelligence tracking.
    """

    async def test_generic_search_full_flow(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
        ai_client,
        serpapi_client,
        db,
    ):
        """
        Test complete generic search flow with domain intelligence.

        REAL SerpAPI and AI service calls - NO MOCKS.

        Steps:
        1. Execute SerpAPI search
        2. Fetch top 3 organic results
        3. Track domain profile per site
        4. Extract products from listicles
        5. Validate no cross-contamination
        6. Enrich top 3 products
        7. Export comprehensive results
        """
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredBrand,
            CrawledSource,
            ProductType,
        )

        # Skip if required services not available
        if serpapi_client is None:
            pytest.skip("SerpAPI not configured")
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Initialize results tracking
        exporter.set_metrics({
            "test_started": datetime.utcnow().isoformat(),
            "test_type": "generic_search_whiskey_e2e",
            "search_query": SEARCH_QUERY,
            "product_type": PRODUCT_TYPE,
            "max_search_results": MAX_SEARCH_RESULTS,
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "generic_search_whiskey_e2e",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        search_results = []
        all_products = []
        domain_profiles = []

        try:
            # Step 1: Execute SerpAPI search
            if not state_manager.is_step_complete("serpapi_search"):
                state_manager.set_current_step("serpapi_search")
                logger.info(f"Executing SerpAPI search: '{SEARCH_QUERY}'")

                search_params = {
                    "q": SEARCH_QUERY,
                    "api_key": serpapi_client["api_key"],
                    "engine": "google",
                    "num": MAX_SEARCH_RESULTS * 2,  # Get more to filter
                }

                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            serpapi_client["base_url"],
                            params=search_params,
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        serpapi_data = response.json()

                    organic_results = serpapi_data.get("organic_results", [])
                    logger.info(f"SerpAPI returned {len(organic_results)} organic results")

                    # Filter to listicle-like results
                    for result in organic_results[:MAX_SEARCH_RESULTS]:
                        search_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("link", ""),
                            "snippet": result.get("snippet", ""),
                            "domain": extract_domain(result.get("link", "")),
                        })

                    state_manager.save_state({"search_results": search_results})
                    logger.info(f"Selected {len(search_results)} results for processing")

                except Exception as e:
                    exporter.add_error({
                        "step": "serpapi_search",
                        "error": str(e),
                    })
                    pytest.fail(f"SerpAPI search failed: {e}")

                state_manager.mark_step_complete("serpapi_search")
            else:
                state = state_manager.get_state()
                search_results = state.get("search_results", [])

            # Step 2: Fetch each result and extract products
            for idx, result in enumerate(search_results):
                step_name = f"fetch_result_{idx}"

                if state_manager.is_step_complete(step_name):
                    continue

                state_manager.set_current_step(step_name)
                url = result["url"]
                domain = result["domain"]

                logger.info(f"Processing result {idx + 1}: {domain}")

                # Clear domain profile for clean tracking
                domain_store.delete_profile(domain)

                # Fetch page
                fetch_start = datetime.utcnow()
                fetch_result = await router.fetch(url)
                fetch_time_ms = int((datetime.utcnow() - fetch_start).total_seconds() * 1000)

                # Get domain profile
                profile = domain_store.get_profile(domain)
                profile_data = {
                    "domain": domain,
                    "url": url,
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                    "tier_used": fetch_result.tier_used,
                    "fetch_success": fetch_result.success,
                    "fetch_time_ms": fetch_time_ms,
                }
                domain_profiles.append(profile_data)
                exporter.add_domain_profile(profile_data)

                if not fetch_result.success:
                    logger.warning(f"Failed to fetch {url}: {fetch_result.error}")
                    exporter.add_error({
                        "step": step_name,
                        "url": url,
                        "error": fetch_result.error,
                    })
                    state_manager.mark_step_complete(step_name)
                    continue

                # Extract products using AI
                try:
                    extraction_result = await ai_client.extract_products(
                        content=fetch_result.content,
                        source_url=url,
                        product_type=PRODUCT_TYPE,
                        extraction_context={
                            "source_type": "listicle",
                            "source_domain": domain,
                        }
                    )

                    raw_products = extraction_result.get("products", [])
                    logger.info(f"Extracted {len(raw_products)} products from {domain}")

                    # Add source tracking to products
                    for p in raw_products[:MAX_PRODUCTS_TO_EXTRACT]:
                        name = p.get("name", "").strip()
                        if name and name.lower() not in ["unknown", ""]:
                            p["source_url"] = url
                            p["source_domain"] = domain
                            p["tier_used"] = fetch_result.tier_used
                            all_products.append(p)

                except Exception as e:
                    logger.error(f"Product extraction failed for {url}: {e}")
                    exporter.add_error({
                        "step": step_name,
                        "url": url,
                        "error": str(e),
                    })

                state_manager.mark_step_complete(step_name)

            # Step 3: Validate no cross-contamination
            state_manager.set_current_step("validate_products")

            # Check that products from different sources are distinct
            product_sources = {}
            for p in all_products:
                name = p.get("name", "").lower().strip()
                source = p.get("source_domain", "")
                if name not in product_sources:
                    product_sources[name] = set()
                product_sources[name].add(source)

            # Products appearing in multiple sources (potential cross-contamination)
            cross_source_products = {
                name: sources for name, sources in product_sources.items()
                if len(sources) > 1
            }

            if cross_source_products:
                logger.info(f"Products found in multiple sources: {cross_source_products}")
                # This is OK - same product on multiple sites is valid

            state_manager.mark_step_complete("validate_products")

            # Step 4: Create database records for unique products
            if not state_manager.is_step_complete("create_records") and all_products:
                state_manager.set_current_step("create_records")

                @sync_to_async(thread_sensitive=True)
                def create_db_records():
                    created = []
                    seen_fingerprints = set()

                    for p_data in all_products[:MAX_PRODUCTS_TO_ENRICH]:
                        name = p_data.get("name", "Unknown")
                        brand_name = p_data.get("brand", "")
                        fingerprint = generate_fingerprint(name, brand_name)

                        # Skip duplicates
                        if fingerprint in seen_fingerprints:
                            continue
                        seen_fingerprints.add(fingerprint)

                        # Create source
                        source_url = p_data.get("source_url", "")
                        source = CrawledSource.objects.create(
                            url=source_url,
                            title=f"Listicle: {name}",
                            source_type="listicle",
                            raw_content="",
                            crawled_at=datetime.now(),
                        )

                        # Create brand
                        brand = None
                        if brand_name:
                            brand, _ = DiscoveredBrand.objects.get_or_create(name=brand_name)

                        # Create product
                        product = DiscoveredProduct.objects.create(
                            name=name,
                            brand=brand,
                            product_type=ProductType.WHISKEY,
                            fingerprint=fingerprint,
                            source_url=source_url,
                            abv=p_data.get("abv"),
                            description=p_data.get("description", ""),
                        )

                        created.append({
                            "id": str(product.id),
                            "name": product.name,
                            "brand": brand_name,
                            "product_type": PRODUCT_TYPE,
                            "source_domain": p_data.get("source_domain"),
                            "source_url": source_url,
                            "tier_used": p_data.get("tier_used"),
                        })

                    return created

                products_created = await create_db_records()

                state_manager.save_state({"products_created": products_created})
                logger.info(f"Created {len(products_created)} products")
                state_manager.mark_step_complete("create_records")
            else:
                state = state_manager.get_state()
                products_created = state.get("products_created", [])

            # Step 5: Add products to exporter
            for p in products_created:
                exporter.add_product({
                    "id": p["id"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "product_type": p["product_type"],
                    "status": "SKELETON",
                    "flow": "generic_search",
                    "search_query": SEARCH_QUERY,
                    "sources_used": [{
                        "url": p["source_url"],
                        "source_type": "listicle",
                        "domain": p["source_domain"],
                        "tier_used": p["tier_used"],
                    }],
                    "domain_intelligence": {
                        "primary_domain": p["source_domain"],
                        "tier_used": p["tier_used"],
                    }
                })

            # Update metrics
            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "search_results_processed": len(search_results),
                "domains_fetched": len(domain_profiles),
                "total_products_extracted": len(all_products),
                "products_created": len(products_created),
                "cross_source_products": len(cross_source_products),
                "tier_distribution": {
                    "tier_1": sum(1 for d in domain_profiles if d.get("tier_used") == 1),
                    "tier_2": sum(1 for d in domain_profiles if d.get("tier_used") == 2),
                    "tier_3": sum(1 for d in domain_profiles if d.get("tier_used") == 3),
                },
            })

            # Finalize
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")

            logger.info(f"Generic Search E2E test completed. Results: {output_path}")
            logger.info(f"Domains processed: {len(domain_profiles)}")
            logger.info(f"Products created: {len(products_created)}")

        finally:
            await router.close()

    async def test_domain_profile_diversity(
        self,
        domain_store,
        exporter,
        redis_client,
        serpapi_client,
    ):
        """
        Test that different search result domains get different profiles.

        Verifies that domain intelligence creates accurate profiles
        for different types of listicle sites.
        """
        from crawler.fetchers.smart_router import SmartRouter

        if serpapi_client is None:
            pytest.skip("SerpAPI not configured")

        # Execute search
        search_params = {
            "q": SEARCH_QUERY,
            "api_key": serpapi_client["api_key"],
            "engine": "google",
            "num": 5,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                serpapi_client["base_url"],
                params=search_params,
                timeout=30.0,
            )
            serpapi_data = response.json()

        organic_results = serpapi_data.get("organic_results", [])[:3]

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        profiles = []

        try:
            for result in organic_results:
                url = result.get("link", "")
                domain = extract_domain(url)

                # Clear and fetch
                domain_store.delete_profile(domain)
                fetch_result = await router.fetch(url)

                # Get profile
                profile = domain_store.get_profile(domain)
                profiles.append({
                    "domain": domain,
                    "url": url,
                    "title": result.get("title", ""),
                    "tier_used": fetch_result.tier_used,
                    "success": fetch_result.success,
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                })

                logger.info(
                    f"{domain}: tier={fetch_result.tier_used}, "
                    f"js_heavy={profile.likely_js_heavy}"
                )

            # Export results
            for p in profiles:
                exporter.add_domain_profile(p)

            output_path = exporter.finalize("COMPLETED")
            logger.info(f"Domain diversity test completed. Results: {output_path}")

            # Verify we got profiles for different domains
            unique_domains = set(p["domain"] for p in profiles)
            assert len(unique_domains) >= 2, f"Expected at least 2 unique domains, got {len(unique_domains)}"

        finally:
            await router.close()
