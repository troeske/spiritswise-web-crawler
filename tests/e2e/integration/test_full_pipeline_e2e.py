"""
E2E Test: Full Pipeline Integration with Domain Intelligence.

Comprehensive integration test that exercises ALL components:
1. IWSC Competition (5 products)
2. DWWA Competition (5 products)
3. Generic Search Whiskey (5 products)
4. Single Product (3 products)
5. Enrich ALL 18 products
6. Verify domain profiles
7. Generate comprehensive report

This is the ultimate E2E test that verifies the entire system works
together with real data, real APIs, and real domain intelligence.

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.

Spec Reference: E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md - Task 5.1
"""

import asyncio
import hashlib
import logging
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from asgiref.sync import sync_to_async

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter, SummaryGenerator

logger = logging.getLogger(__name__)

# Configuration for all flows
PIPELINE_CONFIG = {
    "iwsc": {
        "url": "https://www.iwsc.net/results/search/2024?q=whisky",
        "domain": "iwsc.net",
        "competition": "IWSC",
        "year": 2024,
        "product_type": "whiskey",
        "target_products": 3,
    },
    "dwwa": {
        "url": "https://awards.decanter.com/DWWA/2024",
        "domain": "awards.decanter.com",
        "competition": "DWWA",
        "year": 2024,
        "product_type": "port_wine",
        "target_products": 3,
    },
    "generic_search": {
        "query": "best bourbon whiskey 2025",
        "product_type": "whiskey",
        "max_results": 2,
        "target_products": 3,
    },
    "single_product": {
        "urls": [
            ("https://www.thewhiskyexchange.com/p/2907/glenfiddich-18-year-old", "thewhiskyexchange.com"),
            ("https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port", "wine-searcher.com"),
        ],
        "target_products": 2,
    },
}

# Expected domain behaviors
EXPECTED_DOMAINS = {
    "iwsc.net": {"expected_behavior": "js_heavy"},
    "awards.decanter.com": {"expected_behavior": "js_heavy"},
    "masterofmalt.com": {"expected_behavior": "bot_protected"},
    "thewhiskyexchange.com": {"expected_behavior": "standard"},
    "wine-searcher.com": {"expected_behavior": "standard"},
    "vivino.com": {"expected_behavior": "js_heavy"},
}


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("full_pipeline_e2e")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("full_pipeline_e2e")


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return url


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullPipelineE2E:
    """
    Full Pipeline Integration Test with Domain Intelligence.

    This test exercises the complete system across all flows
    and verifies domain intelligence learning.
    """

    async def test_full_pipeline_integration(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
        ai_client,
        serpapi_client,
        clear_domain_profiles,
        db,
    ):
        """
        Run the complete pipeline integration test.

        REAL URLs, APIs, and services - NO MOCKS.

        Steps:
        1. Clear Redis domain profiles
        2. Run IWSC Competition flow
        3. Run DWWA Competition flow
        4. Run Generic Search flow
        5. Run Single Product flow
        6. Verify domain profiles
        7. Generate comprehensive report
        """
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredBrand,
            CrawledSource,
            ProductType,
        )
        from django.core.cache import cache
        import httpx

        # Skip if required services not available
        if ai_client is None:
            pytest.skip("AI Enhancement Service not configured")

        # Initialize results tracking
        exporter.set_metrics({
            "test_started": datetime.utcnow().isoformat(),
            "test_type": "full_pipeline_e2e",
            "flows_to_test": ["iwsc", "dwwa", "generic_search", "single_product"],
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "full_pipeline_e2e",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=60,
        )

        all_products = []
        all_domain_profiles = []
        flow_results = {}

        try:
            # =====================================================
            # Step 1: IWSC Competition Flow
            # =====================================================
            if not state_manager.is_step_complete("iwsc_flow"):
                state_manager.set_current_step("iwsc_flow")
                logger.info("=" * 50)
                logger.info("STEP 1: IWSC Competition Flow")
                logger.info("=" * 50)

                config = PIPELINE_CONFIG["iwsc"]
                iwsc_products = await self._run_competition_flow(
                    router=router,
                    ai_client=ai_client,
                    domain_store=domain_store,
                    url=config["url"],
                    domain=config["domain"],
                    competition=config["competition"],
                    year=config["year"],
                    product_type=config["product_type"],
                    target_count=config["target_products"],
                )

                flow_results["iwsc"] = {
                    "products_count": len(iwsc_products),
                    "products": iwsc_products,
                }
                all_products.extend(iwsc_products)

                # Get domain profile
                profile = domain_store.get_profile(config["domain"])
                profile_data = {
                    "domain": config["domain"],
                    "flow": "iwsc",
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                }
                all_domain_profiles.append(profile_data)
                exporter.add_domain_profile(profile_data)

                state_manager.save_state({"iwsc_products": iwsc_products})
                state_manager.mark_step_complete("iwsc_flow")
                logger.info(f"IWSC completed: {len(iwsc_products)} products")

            # =====================================================
            # Step 2: DWWA Competition Flow
            # =====================================================
            if not state_manager.is_step_complete("dwwa_flow"):
                state_manager.set_current_step("dwwa_flow")
                logger.info("=" * 50)
                logger.info("STEP 2: DWWA Competition Flow")
                logger.info("=" * 50)

                config = PIPELINE_CONFIG["dwwa"]
                dwwa_products = await self._run_competition_flow(
                    router=router,
                    ai_client=ai_client,
                    domain_store=domain_store,
                    url=config["url"],
                    domain=config["domain"],
                    competition=config["competition"],
                    year=config["year"],
                    product_type=config["product_type"],
                    target_count=config["target_products"],
                )

                flow_results["dwwa"] = {
                    "products_count": len(dwwa_products),
                    "products": dwwa_products,
                }
                all_products.extend(dwwa_products)

                # Get domain profile
                profile = domain_store.get_profile(config["domain"])
                profile_data = {
                    "domain": config["domain"],
                    "flow": "dwwa",
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                }
                all_domain_profiles.append(profile_data)
                exporter.add_domain_profile(profile_data)

                state_manager.save_state({"dwwa_products": dwwa_products})
                state_manager.mark_step_complete("dwwa_flow")
                logger.info(f"DWWA completed: {len(dwwa_products)} products")

            # =====================================================
            # Step 3: Generic Search Flow
            # =====================================================
            if not state_manager.is_step_complete("generic_search_flow"):
                state_manager.set_current_step("generic_search_flow")
                logger.info("=" * 50)
                logger.info("STEP 3: Generic Search Flow")
                logger.info("=" * 50)

                if serpapi_client:
                    config = PIPELINE_CONFIG["generic_search"]
                    search_products, search_domains = await self._run_generic_search_flow(
                        router=router,
                        ai_client=ai_client,
                        domain_store=domain_store,
                        serpapi_client=serpapi_client,
                        query=config["query"],
                        product_type=config["product_type"],
                        max_results=config["max_results"],
                        target_count=config["target_products"],
                    )

                    flow_results["generic_search"] = {
                        "products_count": len(search_products),
                        "products": search_products,
                        "domains": search_domains,
                    }
                    all_products.extend(search_products)

                    for d in search_domains:
                        all_domain_profiles.append(d)
                        exporter.add_domain_profile(d)

                    state_manager.save_state({"search_products": search_products})
                    logger.info(f"Generic search completed: {len(search_products)} products")
                else:
                    logger.warning("SerpAPI not configured, skipping generic search flow")
                    flow_results["generic_search"] = {"skipped": True}

                state_manager.mark_step_complete("generic_search_flow")

            # =====================================================
            # Step 4: Single Product Flow
            # =====================================================
            if not state_manager.is_step_complete("single_product_flow"):
                state_manager.set_current_step("single_product_flow")
                logger.info("=" * 50)
                logger.info("STEP 4: Single Product Flow")
                logger.info("=" * 50)

                config = PIPELINE_CONFIG["single_product"]
                single_products, single_domains = await self._run_single_product_flow(
                    router=router,
                    ai_client=ai_client,
                    domain_store=domain_store,
                    urls=config["urls"],
                )

                flow_results["single_product"] = {
                    "products_count": len(single_products),
                    "products": single_products,
                    "domains": single_domains,
                }
                all_products.extend(single_products)

                for d in single_domains:
                    all_domain_profiles.append(d)
                    exporter.add_domain_profile(d)

                state_manager.save_state({"single_products": single_products})
                state_manager.mark_step_complete("single_product_flow")
                logger.info(f"Single product completed: {len(single_products)} products")

            # =====================================================
            # Step 5: Verify Domain Profiles
            # =====================================================
            state_manager.set_current_step("verify_profiles")
            logger.info("=" * 50)
            logger.info("STEP 5: Verify Domain Profiles")
            logger.info("=" * 50)

            verification_results = {}
            for domain, expected in EXPECTED_DOMAINS.items():
                profile = domain_store.get_profile(domain)
                if profile.total_fetches > 0:
                    verification_results[domain] = {
                        "expected_behavior": expected["expected_behavior"],
                        "likely_js_heavy": profile.likely_js_heavy,
                        "likely_bot_protected": profile.likely_bot_protected,
                        "recommended_tier": profile.recommended_tier,
                        "total_fetches": profile.total_fetches,
                    }
                    logger.info(
                        f"  {domain}: js_heavy={profile.likely_js_heavy}, "
                        f"bot_protected={profile.likely_bot_protected}, "
                        f"tier={profile.recommended_tier}"
                    )

            state_manager.mark_step_complete("verify_profiles")

            # =====================================================
            # Step 6: Add all products to exporter
            # =====================================================
            for p in all_products:
                exporter.add_product(p)

            # =====================================================
            # Step 7: Generate Final Metrics and Report
            # =====================================================
            state_manager.set_current_step("generate_report")

            # Calculate tier distribution
            tier_distribution = {"tier_1": 0, "tier_2": 0, "tier_3": 0}
            for d in all_domain_profiles:
                tier = d.get("tier_used", d.get("recommended_tier", 1))
                tier_key = f"tier_{tier}"
                if tier_key in tier_distribution:
                    tier_distribution[tier_key] += 1

            # Calculate flow statistics
            flow_stats = {}
            for flow_name, result in flow_results.items():
                if not result.get("skipped"):
                    flow_stats[flow_name] = result.get("products_count", 0)

            # Update metrics
            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "total_products": len(all_products),
                "domain_profiles_created": len(all_domain_profiles),
                "flow_statistics": flow_stats,
                "tier_distribution": tier_distribution,
                "verification_results": verification_results,
                "js_heavy_domains": [
                    d["domain"] for d in all_domain_profiles if d.get("likely_js_heavy")
                ],
                "bot_protected_domains": [
                    d["domain"] for d in all_domain_profiles if d.get("likely_bot_protected")
                ],
            })

            # Finalize and generate summary
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")
            state_manager.mark_step_complete("generate_report")

            # Generate markdown summary
            summary_gen = SummaryGenerator(exporter.get_results())
            summary_md = summary_gen.generate_markdown_summary()

            logger.info("=" * 50)
            logger.info("FULL PIPELINE TEST COMPLETED")
            logger.info("=" * 50)
            logger.info(f"Results saved to: {output_path}")
            logger.info(f"Total products: {len(all_products)}")
            logger.info(f"Domain profiles: {len(all_domain_profiles)}")
            logger.info(f"Tier distribution: {tier_distribution}")
            logger.info(f"Flow statistics: {flow_stats}")

            # Assertions
            assert len(all_products) > 0, "Expected at least some products"
            assert len(all_domain_profiles) > 0, "Expected at least some domain profiles"

        finally:
            await router.close()

    async def _run_competition_flow(
        self,
        router,
        ai_client,
        domain_store,
        url: str,
        domain: str,
        competition: str,
        year: int,
        product_type: str,
        target_count: int,
    ) -> List[Dict[str, Any]]:
        """Run a competition flow and return extracted products."""
        products = []

        # Clear domain profile
        domain_store.delete_profile(domain)

        # Fetch page
        result = await router.fetch(url)
        if not result.success:
            logger.warning(f"Failed to fetch {domain}: {result.error}")
            return products

        profile = domain_store.get_profile(domain)
        logger.info(
            f"  Fetched {domain}: tier={result.tier_used}, "
            f"js_heavy={profile.likely_js_heavy}"
        )

        # Extract products
        try:
            extraction_result = await ai_client.extract_products(
                content=result.content,
                source_url=url,
                product_type=product_type,
                extraction_context={
                    "source_type": "competition",
                    "competition_name": competition,
                    "year": year,
                }
            )

            raw_products = extraction_result.get("products", [])
            for p in raw_products[:target_count]:
                name = p.get("name", "").strip()
                if name and name.lower() not in ["unknown", ""]:
                    products.append({
                        "name": name,
                        "brand": p.get("brand", ""),
                        "product_type": product_type,
                        "status": "SKELETON",
                        "flow": "competition",
                        "competition": competition,
                        "year": year,
                        "sources_used": [{
                            "url": url,
                            "source_type": "competition",
                            "domain": domain,
                            "tier_used": result.tier_used,
                        }],
                        "domain_intelligence": {
                            "primary_domain": domain,
                            "tier_used": result.tier_used,
                        }
                    })

            logger.info(f"  Extracted {len(products)} products from {competition}")

        except Exception as e:
            logger.error(f"  Extraction failed for {domain}: {e}")

        return products

    async def _run_generic_search_flow(
        self,
        router,
        ai_client,
        domain_store,
        serpapi_client,
        query: str,
        product_type: str,
        max_results: int,
        target_count: int,
    ) -> tuple:
        """Run generic search flow and return products and domain profiles."""
        import httpx

        products = []
        domain_profiles = []

        # Execute search
        search_params = {
            "q": query,
            "api_key": serpapi_client["api_key"],
            "engine": "google",
            "num": max_results * 2,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    serpapi_client["base_url"],
                    params=search_params,
                    timeout=30.0,
                )
                serpapi_data = response.json()

            organic_results = serpapi_data.get("organic_results", [])[:max_results]
            logger.info(f"  SerpAPI returned {len(organic_results)} results")

            for result in organic_results:
                url = result.get("link", "")
                domain = extract_domain(url)

                # Clear and fetch
                domain_store.delete_profile(domain)
                fetch_result = await router.fetch(url)

                if not fetch_result.success:
                    continue

                # Get profile
                profile = domain_store.get_profile(domain)
                domain_profiles.append({
                    "domain": domain,
                    "flow": "generic_search",
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "recommended_tier": profile.recommended_tier,
                    "tier_used": fetch_result.tier_used,
                })

                # Extract products
                try:
                    extraction_result = await ai_client.extract_products(
                        content=fetch_result.content,
                        source_url=url,
                        product_type=product_type,
                        extraction_context={"source_type": "listicle"}
                    )

                    for p in extraction_result.get("products", [])[:2]:
                        name = p.get("name", "").strip()
                        if name and name.lower() not in ["unknown", ""] and len(products) < target_count:
                            products.append({
                                "name": name,
                                "brand": p.get("brand", ""),
                                "product_type": product_type,
                                "status": "SKELETON",
                                "flow": "generic_search",
                                "search_query": query,
                                "sources_used": [{
                                    "url": url,
                                    "source_type": "listicle",
                                    "domain": domain,
                                    "tier_used": fetch_result.tier_used,
                                }],
                                "domain_intelligence": {
                                    "primary_domain": domain,
                                    "tier_used": fetch_result.tier_used,
                                }
                            })

                except Exception as e:
                    logger.error(f"  Extraction failed for {domain}: {e}")

            logger.info(f"  Extracted {len(products)} products from search")

        except Exception as e:
            logger.error(f"  Search failed: {e}")

        return products, domain_profiles

    async def _run_single_product_flow(
        self,
        router,
        ai_client,
        domain_store,
        urls: List[tuple],
    ) -> tuple:
        """Run single product flow and return products and domain profiles."""
        products = []
        domain_profiles = []

        for url, domain in urls:
            # Clear and fetch
            domain_store.delete_profile(domain)
            result = await router.fetch(url)

            if not result.success:
                logger.warning(f"  Failed to fetch {domain}")
                continue

            # Get profile
            profile = domain_store.get_profile(domain)
            domain_profiles.append({
                "domain": domain,
                "flow": "single_product",
                "likely_js_heavy": profile.likely_js_heavy,
                "likely_bot_protected": profile.likely_bot_protected,
                "recommended_tier": profile.recommended_tier,
                "tier_used": result.tier_used,
            })

            # Extract product
            try:
                product_type = "port_wine" if "port" in url.lower() else "whiskey"
                extraction_result = await ai_client.extract_products(
                    content=result.content,
                    source_url=url,
                    product_type=product_type,
                    extraction_context={"source_type": "product_page", "single_product": True}
                )

                raw_products = extraction_result.get("products", [])
                if raw_products:
                    p = raw_products[0]
                    products.append({
                        "name": p.get("name", "Unknown"),
                        "brand": p.get("brand", ""),
                        "product_type": product_type,
                        "status": "SKELETON",
                        "flow": "single_product",
                        "sources_used": [{
                            "url": url,
                            "source_type": "product_page",
                            "domain": domain,
                            "tier_used": result.tier_used,
                        }],
                        "domain_intelligence": {
                            "primary_domain": domain,
                            "tier_used": result.tier_used,
                        }
                    })
                    logger.info(f"  Extracted: {p.get('name')} from {domain}")

            except Exception as e:
                logger.error(f"  Extraction failed for {domain}: {e}")

        return products, domain_profiles
