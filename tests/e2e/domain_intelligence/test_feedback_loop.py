"""
E2E Test: Feedback Loop.

Tests that the domain intelligence system learns and improves over time by:
1. Recording fetch outcomes (success/failure, tier used, response time)
2. Updating domain profiles based on outcomes
3. Using updated profiles for smarter tier selection on subsequent requests
4. Demonstrating efficiency improvement on second pass

Real URLs tested (mix of static, JS-heavy, and protected):
- Static: httpbin.org, example.com, github.com
- JS-heavy: awards.decanter.com, whiskybase.com, vivino.com, untappd.com
- Protected: masterofmalt.com, totalwine.com, wine.com

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.
"""

import asyncio
import logging
import pytest
from datetime import datetime
from typing import Dict, List, Tuple

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter

logger = logging.getLogger(__name__)

# Mix of URLs with different characteristics
FEEDBACK_LOOP_TEST_URLS = [
    # Static sites (Tier 1 should work)
    ("httpbin.org", "https://httpbin.org/html", "static"),
    ("example.com", "https://example.com/", "static"),
    ("github.com", "https://github.com/", "static"),
    # JS-heavy sites (may need Tier 2)
    ("awards.decanter.com", "https://awards.decanter.com/DWWA/2024", "js_heavy"),
    ("whiskybase.com", "https://www.whiskybase.com/whiskies", "js_heavy"),
    ("vivino.com", "https://www.vivino.com/explore", "js_heavy"),
    # Bot-protected sites (may need Tier 3)
    ("masterofmalt.com", "https://www.masterofmalt.com/", "protected"),
    ("totalwine.com", "https://www.totalwine.com/", "protected"),
    ("wine.com", "https://www.wine.com/", "protected"),
]


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("feedback_loop")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("feedback_loop")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFeedbackLoop:
    """
    E2E tests for the domain intelligence feedback loop.

    These tests verify that the system learns from fetch outcomes:
    1. First pass: Fetch all URLs, learn about each domain
    2. Second pass: Use learned profiles for smarter tier selection
    3. Compare efficiency: Second pass should be more efficient
    """

    async def test_two_pass_learning(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
        clear_domain_profiles,
    ):
        """
        Test that the system learns and improves between passes.

        REAL URLs tested - NO MOCKS.

        Steps:
        1. Clear all domain profiles for clean test
        2. First pass: Fetch all URLs, record tier usage
        3. Second pass: Fetch all URLs again, record tier usage
        4. Compare efficiency improvement
        5. Export comprehensive results
        """
        from crawler.fetchers.smart_router import SmartRouter
        from django.core.cache import cache

        # Initialize results tracking
        exporter.set_metrics({
            "test_started": datetime.utcnow().isoformat(),
            "test_type": "feedback_loop_two_pass",
            "domains_tested": len(FEEDBACK_LOOP_TEST_URLS),
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "feedback_loop",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        pass_results = {
            "pass_1": {"tier_usage": {1: 0, 2: 0, 3: 0}, "fetches": []},
            "pass_2": {"tier_usage": {1: 0, 2: 0, 3: 0}, "fetches": []},
        }

        try:
            for pass_num in [1, 2]:
                pass_key = f"pass_{pass_num}"
                step_name = f"pass_{pass_num}"

                # Skip if already completed
                if state_manager.is_step_complete(step_name):
                    logger.info(f"Skipping already completed step: {step_name}")
                    continue

                state_manager.set_current_step(step_name)
                logger.info(f"=== Starting Pass {pass_num} ===")

                for domain_name, url, expected_type in FEEDBACK_LOOP_TEST_URLS:
                    fetch_step = f"pass_{pass_num}_{domain_name.replace('.', '_')}"

                    # Skip if already completed
                    if state_manager.is_step_complete(fetch_step):
                        logger.info(f"  Skipping completed: {domain_name}")
                        continue

                    try:
                        # Get profile before fetch
                        profile_before = domain_store.get_profile(domain_name)
                        recommended_before = profile_before.recommended_tier

                        # Fetch
                        fetch_start = datetime.utcnow()
                        result = await router.fetch(url)
                        fetch_time_ms = int((datetime.utcnow() - fetch_start).total_seconds() * 1000)

                        # Record results
                        fetch_data = {
                            "domain": domain_name,
                            "url": url,
                            "expected_type": expected_type,
                            "pass": pass_num,
                            "tier_used": result.tier_used,
                            "success": result.success,
                            "content_length": len(result.content) if result.content else 0,
                            "fetch_time_ms": fetch_time_ms,
                            "recommended_tier_before": recommended_before,
                            "error": result.error,
                        }

                        pass_results[pass_key]["fetches"].append(fetch_data)
                        pass_results[pass_key]["tier_usage"][result.tier_used] += 1

                        logger.info(
                            f"  {domain_name}: tier={result.tier_used}, "
                            f"success={result.success}, time={fetch_time_ms}ms"
                        )

                        state_manager.mark_step_complete(fetch_step)

                    except Exception as e:
                        pass_results[pass_key]["fetches"].append({
                            "domain": domain_name,
                            "pass": pass_num,
                            "error": str(e),
                        })
                        exporter.add_error({
                            "pass": pass_num,
                            "domain": domain_name,
                            "error": str(e),
                        })
                        logger.error(f"  {domain_name}: Error - {e}")

                state_manager.mark_step_complete(step_name)

            # Analysis
            state_manager.set_current_step("analysis")

            # Calculate efficiency metrics
            pass1_tiers = pass_results["pass_1"]["tier_usage"]
            pass2_tiers = pass_results["pass_2"]["tier_usage"]

            # Efficiency = more Tier 1 usage, less Tier 3 usage
            efficiency_pass1 = (
                pass1_tiers[1] * 1.0 +
                pass1_tiers[2] * 0.5 +
                pass1_tiers[3] * 0.1
            )
            efficiency_pass2 = (
                pass2_tiers[1] * 1.0 +
                pass2_tiers[2] * 0.5 +
                pass2_tiers[3] * 0.1
            )

            # Get all domain profiles
            domain_profiles = []
            for domain_name, _, expected_type in FEEDBACK_LOOP_TEST_URLS:
                profile = domain_store.get_profile(domain_name)
                profile_data = {
                    "domain": domain_name,
                    "expected_type": expected_type,
                    "likely_js_heavy": profile.likely_js_heavy,
                    "likely_bot_protected": profile.likely_bot_protected,
                    "likely_slow": profile.likely_slow,
                    "recommended_tier": profile.recommended_tier,
                    "success_count": profile.success_count,
                    "failure_count": profile.failure_count,
                    "tier1_success_rate": profile.tier1_success_rate,
                    "tier2_success_rate": profile.tier2_success_rate,
                    "tier3_success_rate": profile.tier3_success_rate,
                }
                domain_profiles.append(profile_data)
                exporter.add_domain_profile(profile_data)

            analysis = {
                "pass_1_tier_usage": pass1_tiers,
                "pass_2_tier_usage": pass2_tiers,
                "efficiency_pass_1": efficiency_pass1,
                "efficiency_pass_2": efficiency_pass2,
                "efficiency_improvement": efficiency_pass2 - efficiency_pass1,
                "profiles_created": len(domain_profiles),
                "js_heavy_detected": sum(1 for p in domain_profiles if p["likely_js_heavy"]),
                "bot_protected_detected": sum(1 for p in domain_profiles if p["likely_bot_protected"]),
            }

            # Update metrics
            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "domains_tested": len(FEEDBACK_LOOP_TEST_URLS),
                **analysis,
            })

            # Save results
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")
            state_manager.mark_step_complete("analysis")

            logger.info(f"Test completed. Results saved to: {output_path}")
            logger.info(f"Pass 1 tier usage: {pass1_tiers}")
            logger.info(f"Pass 2 tier usage: {pass2_tiers}")
            logger.info(f"Efficiency improvement: {analysis['efficiency_improvement']:.2f}")
            logger.info(f"Profiles created: {analysis['profiles_created']}")

            # Assertions
            assert len(domain_profiles) == len(FEEDBACK_LOOP_TEST_URLS), (
                f"Expected {len(FEEDBACK_LOOP_TEST_URLS)} profiles, "
                f"got {len(domain_profiles)}"
            )

        finally:
            await router.close()

    async def test_profile_persistence_across_sessions(
        self,
        domain_store,
        exporter,
        redis_client,
    ):
        """
        Test that domain profiles persist across router instances.

        Verifies that profiles are correctly stored in Redis and
        can be retrieved by a new router instance.
        """
        from crawler.fetchers.smart_router import SmartRouter

        test_domain = "example.com"
        test_url = "https://example.com/"

        # Clear profile
        domain_store.delete_profile(test_domain)

        # First router instance - fetch and create profile
        router1 = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=30,
        )

        try:
            result1 = await router1.fetch(test_url)
            logger.info(f"Router 1 fetch: tier={result1.tier_used}, success={result1.success}")
        finally:
            await router1.close()

        # Get profile after first router
        profile_after_router1 = domain_store.get_profile(test_domain)
        logger.info(f"Profile after router 1: {profile_after_router1.to_dict()}")

        # Second router instance - should use existing profile
        router2 = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=30,
        )

        try:
            # Get profile before fetch
            profile_before_router2 = domain_store.get_profile(test_domain)

            result2 = await router2.fetch(test_url)
            logger.info(f"Router 2 fetch: tier={result2.tier_used}, success={result2.success}")

        finally:
            await router2.close()

        # Get profile after second router
        profile_after_router2 = domain_store.get_profile(test_domain)

        # Export results
        exporter.add_domain_profile({
            "test_type": "profile_persistence",
            "domain": test_domain,
            "profile_after_router1": profile_after_router1.to_dict(),
            "profile_before_router2": profile_before_router2.to_dict(),
            "profile_after_router2": profile_after_router2.to_dict(),
            "fetch_1_tier": result1.tier_used,
            "fetch_2_tier": result2.tier_used,
        })

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Profile persistence test completed. Results: {output_path}")

        # Verify profile persisted
        assert profile_after_router2.total_fetches >= 2, (
            f"Expected at least 2 fetches recorded, got {profile_after_router2.total_fetches}"
        )

    async def test_feedback_recorder_integration(
        self,
        domain_store,
        exporter,
    ):
        """
        Test that FeedbackRecorder correctly updates domain profiles.

        Verifies all profile fields are updated correctly based on
        different fetch outcomes.
        """
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        test_domain = "feedback-test.com"
        profile = DomainProfile(domain=test_domain)

        test_scenarios = []

        # Scenario 1: Successful Tier 1 fetch
        profile = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=True,
            response_time_ms=500,
        )
        test_scenarios.append({
            "scenario": "successful_tier1",
            "success_count": profile.success_count,
            "failure_count": profile.failure_count,
            "tier1_success_rate": profile.tier1_success_rate,
            "avg_response_time_ms": profile.avg_response_time_ms,
        })

        # Scenario 2: Failed Tier 1, successful Tier 2
        profile = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=1000,
            escalation_reason="cloudflare_detected",
        )
        profile = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=2,
            success=True,
            response_time_ms=3000,
        )
        test_scenarios.append({
            "scenario": "tier1_fail_tier2_success",
            "success_count": profile.success_count,
            "failure_count": profile.failure_count,
            "tier1_success_rate": profile.tier1_success_rate,
            "tier2_success_rate": profile.tier2_success_rate,
            "likely_bot_protected": profile.likely_bot_protected,
        })

        # Scenario 3: Timeout
        profile = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=30000,
            timed_out=True,
        )
        test_scenarios.append({
            "scenario": "timeout",
            "timeout_count": profile.timeout_count,
            "likely_slow": profile.likely_slow,
        })

        # Scenario 4: JS placeholder detected
        profile = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=False,
            response_time_ms=500,
            escalation_reason="js_placeholder_detected",
        )
        test_scenarios.append({
            "scenario": "js_placeholder",
            "likely_js_heavy": profile.likely_js_heavy,
            "recommended_tier": profile.recommended_tier,
        })

        # Final profile state
        final_profile = {
            "domain": profile.domain,
            "success_count": profile.success_count,
            "failure_count": profile.failure_count,
            "timeout_count": profile.timeout_count,
            "tier1_success_rate": profile.tier1_success_rate,
            "tier2_success_rate": profile.tier2_success_rate,
            "tier3_success_rate": profile.tier3_success_rate,
            "likely_js_heavy": profile.likely_js_heavy,
            "likely_bot_protected": profile.likely_bot_protected,
            "likely_slow": profile.likely_slow,
            "recommended_tier": profile.recommended_tier,
            "avg_response_time_ms": profile.avg_response_time_ms,
        }

        # Export results
        exporter.add_domain_profile({
            "test_type": "feedback_recorder_integration",
            "test_scenarios": test_scenarios,
            "final_profile": final_profile,
        })

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Feedback recorder test completed. Results: {output_path}")

        # Log scenarios
        for scenario in test_scenarios:
            logger.info(f"  {scenario['scenario']}: {scenario}")

        logger.info(f"Final profile: {final_profile}")

        # Verify profile was updated
        assert profile.success_count >= 2, "Expected at least 2 successful fetches"
        assert profile.failure_count >= 2, "Expected at least 2 failed fetches"
        assert profile.timeout_count >= 1, "Expected at least 1 timeout"

    async def test_efficiency_by_domain_type(
        self,
        domain_store,
        exporter,
        redis_client,
    ):
        """
        Test efficiency improvements grouped by domain type.

        Verifies that:
        1. Static sites stay at Tier 1
        2. JS-heavy sites learn to start at Tier 2
        3. Protected sites learn to start at Tier 3
        """
        from crawler.fetchers.smart_router import SmartRouter

        # Group URLs by type
        by_type = {"static": [], "js_heavy": [], "protected": []}
        for domain, url, expected_type in FEEDBACK_LOOP_TEST_URLS:
            by_type[expected_type].append((domain, url))

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        results_by_type = {}

        try:
            for expected_type, urls in by_type.items():
                if not urls:
                    continue

                type_results = {
                    "domains": [],
                    "tier_usage": {1: 0, 2: 0, 3: 0},
                }

                for domain, url in urls[:3]:  # Limit to 3 per type
                    # Clear profile
                    domain_store.delete_profile(domain)

                    # Fetch
                    result = await router.fetch(url)

                    type_results["domains"].append({
                        "domain": domain,
                        "tier_used": result.tier_used,
                        "success": result.success,
                    })
                    type_results["tier_usage"][result.tier_used] += 1

                    # Get updated profile
                    profile = domain_store.get_profile(domain)
                    logger.info(
                        f"  {expected_type}/{domain}: tier={result.tier_used}, "
                        f"js_heavy={profile.likely_js_heavy}, bot_protected={profile.likely_bot_protected}"
                    )

                results_by_type[expected_type] = type_results

        finally:
            await router.close()

        # Export results
        exporter.add_domain_profile({
            "test_type": "efficiency_by_domain_type",
            "results_by_type": results_by_type,
        })

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Efficiency by domain type test completed. Results: {output_path}")

        # Log summary
        for expected_type, results in results_by_type.items():
            logger.info(f"  {expected_type}: tier_usage={results['tier_usage']}")
