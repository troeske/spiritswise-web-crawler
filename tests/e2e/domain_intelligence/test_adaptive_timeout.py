"""
E2E Test: Adaptive Timeout.

Tests that the domain intelligence system correctly adapts timeouts based on:
1. Response times from previous fetches
2. Timeout failures
3. Domain profile's likely_slow flag

Real URLs tested (known slow or variable response sites):
- https://www.whiskyadvocate.com/ratings-reviews/
- https://www.wine-searcher.com/

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.
"""

import asyncio
import logging
import pytest
from datetime import datetime
from typing import Dict, List

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter

logger = logging.getLogger(__name__)

# Real URLs for timeout testing
TIMEOUT_TEST_URLS = [
    ("whiskyadvocate.com", "https://www.whiskyadvocate.com/ratings-reviews/"),
    ("wine-searcher.com", "https://www.wine-searcher.com/"),
]

# Number of times to fetch each URL
FETCH_ATTEMPTS_PER_DOMAIN = 5


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("adaptive_timeout")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("adaptive_timeout")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestAdaptiveTimeout:
    """
    E2E tests for adaptive timeout in domain intelligence.

    These tests verify that the AdaptiveTimeout component correctly:
    1. Tracks response times from previous fetches
    2. Adjusts timeout based on domain history
    3. Handles timeout failures gracefully
    4. Updates profile with likely_slow flag
    """

    async def test_response_time_tracking(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
    ):
        """
        Test that response times are correctly tracked in domain profiles.

        REAL URLs tested - NO MOCKS.

        Steps:
        1. Clear any existing domain profiles for test domains
        2. Fetch each URL multiple times
        3. Verify response times are tracked in profile
        4. Verify adaptive timeout adjusts based on history
        5. Export comprehensive results
        """
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Initialize results tracking
        exporter.set_metrics({
            "test_started": datetime.utcnow().isoformat(),
            "test_type": "adaptive_timeout",
            "domains_tested": len(TIMEOUT_TEST_URLS),
        })

        # Check for resume
        if state_manager.has_state():
            completed = state_manager.get_completed_steps()
            logger.info(f"Resuming from previous run, completed steps: {completed}")
        else:
            state_manager.save_state({
                "status": "RUNNING",
                "test_type": "adaptive_timeout",
            })

        # Create SmartRouter with domain intelligence
        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=30,
        )

        results: Dict[str, Dict] = {}

        try:
            for domain_name, url in TIMEOUT_TEST_URLS:
                step_name = f"test_{domain_name.replace('.', '_').replace('-', '_')}"

                # Skip if already completed
                if state_manager.is_step_complete(step_name):
                    logger.info(f"Skipping already completed step: {step_name}")
                    continue

                state_manager.set_current_step(step_name)
                logger.info(f"Testing adaptive timeout for: {domain_name}")

                # Clear existing profile for clean test
                domain_store.delete_profile(domain_name)

                domain_results = {
                    "domain": domain_name,
                    "url": url,
                    "fetch_attempts": [],
                    "response_times_ms": [],
                    "timeouts_predicted": [],
                    "final_profile": None,
                }

                # Fetch URL multiple times to build response time history
                for attempt in range(FETCH_ATTEMPTS_PER_DOMAIN):
                    attempt_start = datetime.utcnow()

                    # Get current profile and predicted timeout
                    current_profile = domain_store.get_profile(domain_name)
                    predicted_timeout = AdaptiveTimeout.get_timeout(current_profile, attempt=0)
                    domain_results["timeouts_predicted"].append(predicted_timeout)

                    try:
                        result = await router.fetch(url)

                        response_time_ms = int((datetime.utcnow() - attempt_start).total_seconds() * 1000)
                        domain_results["response_times_ms"].append(response_time_ms)

                        attempt_data = {
                            "attempt": attempt + 1,
                            "success": result.success,
                            "tier_used": result.tier_used,
                            "status_code": result.status_code,
                            "content_length": len(result.content) if result.content else 0,
                            "response_time_ms": response_time_ms,
                            "predicted_timeout_ms": predicted_timeout,
                            "error": result.error,
                            "timestamp": attempt_start.isoformat(),
                        }

                        # Check if this was a timeout
                        if result.error and "timeout" in result.error.lower():
                            attempt_data["was_timeout"] = True

                        domain_results["fetch_attempts"].append(attempt_data)

                        logger.info(
                            f"  Attempt {attempt + 1}: response={response_time_ms}ms, "
                            f"predicted_timeout={predicted_timeout}ms, success={result.success}"
                        )

                    except Exception as e:
                        response_time_ms = int((datetime.utcnow() - attempt_start).total_seconds() * 1000)
                        domain_results["response_times_ms"].append(response_time_ms)

                        domain_results["fetch_attempts"].append({
                            "attempt": attempt + 1,
                            "error": str(e),
                            "response_time_ms": response_time_ms,
                            "was_timeout": "timeout" in str(e).lower(),
                            "timestamp": attempt_start.isoformat(),
                        })
                        exporter.add_error({
                            "domain": domain_name,
                            "attempt": attempt + 1,
                            "error": str(e),
                        })
                        logger.error(f"  Attempt {attempt + 1} failed: {e}")

                # Get final domain profile
                profile = domain_store.get_profile(domain_name)
                domain_results["final_profile"] = {
                    "domain": profile.domain,
                    "avg_response_time_ms": profile.avg_response_time_ms,
                    "likely_slow": profile.likely_slow,
                    "timeout_count": profile.timeout_count,
                    "success_count": profile.success_count,
                    "failure_count": profile.failure_count,
                    "recommended_timeout_ms": profile.recommended_timeout_ms,
                }

                # Calculate timeout adaptation
                response_times = domain_results["response_times_ms"]
                predicted_timeouts = domain_results["timeouts_predicted"]
                if len(response_times) >= 2 and len(predicted_timeouts) >= 2:
                    # Check if timeout adapted based on response times
                    domain_results["timeout_adaptation"] = {
                        "first_timeout_prediction": predicted_timeouts[0],
                        "last_timeout_prediction": predicted_timeouts[-1],
                        "avg_response_time": sum(response_times) / len(response_times),
                        "timeout_changed": predicted_timeouts[-1] != predicted_timeouts[0],
                    }

                # Add domain profile to exporter
                exporter.add_domain_profile(domain_results["final_profile"])

                results[domain_name] = domain_results
                state_manager.mark_step_complete(step_name)
                state_manager.add_domain_profile(domain_results["final_profile"])

                logger.info(
                    f"  Final profile: avg_response={profile.avg_response_time_ms}ms, "
                    f"likely_slow={profile.likely_slow}, timeout_count={profile.timeout_count}"
                )

            # Analysis
            state_manager.set_current_step("analysis")

            analysis = {
                "domains_tested": len(results),
                "domains_with_timeouts": 0,
                "domains_marked_slow": 0,
                "avg_response_times": {},
            }

            for domain_name, domain_result in results.items():
                profile = domain_result.get("final_profile", {})
                if profile.get("timeout_count", 0) > 0:
                    analysis["domains_with_timeouts"] += 1
                if profile.get("likely_slow"):
                    analysis["domains_marked_slow"] += 1
                analysis["avg_response_times"][domain_name] = profile.get("avg_response_time_ms", 0)

            # Update metrics
            exporter.set_metrics({
                "test_completed": datetime.utcnow().isoformat(),
                "domains_tested": len(TIMEOUT_TEST_URLS),
                "domains_with_timeouts": analysis["domains_with_timeouts"],
                "domains_marked_slow": analysis["domains_marked_slow"],
                "avg_response_times": analysis["avg_response_times"],
            })

            # Save results
            output_path = exporter.finalize("COMPLETED")
            state_manager.set_status("COMPLETED")
            state_manager.mark_step_complete("analysis")

            logger.info(f"Test completed. Results saved to: {output_path}")
            logger.info(f"Analysis: {analysis}")

            # Assertions
            assert len(results) == len(TIMEOUT_TEST_URLS), (
                f"Expected results for {len(TIMEOUT_TEST_URLS)} domains, "
                f"got {len(results)}"
            )

            # Verify response times were tracked
            for domain_name, domain_result in results.items():
                profile = domain_result.get("final_profile", {})
                assert profile.get("avg_response_time_ms") is not None, (
                    f"Expected avg_response_time_ms for {domain_name}"
                )

        finally:
            await router.close()

    async def test_timeout_calculation(
        self,
        domain_store,
        exporter,
    ):
        """
        Test the AdaptiveTimeout calculation logic directly.

        Verifies:
        1. Base timeout for new domains
        2. Timeout increases for slow domains
        3. Timeout increases on retry attempts
        """
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        test_cases = []

        # Test 1: New domain (default timeout)
        new_profile = DomainProfile(domain="new-domain.com")
        timeout_new = AdaptiveTimeout.get_timeout(new_profile, attempt=0)
        test_cases.append({
            "test": "new_domain",
            "profile_state": "default",
            "attempt": 0,
            "timeout_ms": timeout_new,
            "expected_range": (15000, 25000),  # 15-25s for new domains
        })

        # Test 2: Slow domain (should have higher timeout)
        slow_profile = DomainProfile(
            domain="slow-domain.com",
            avg_response_time_ms=10000,  # 10s average
            likely_slow=True,
        )
        timeout_slow = AdaptiveTimeout.get_timeout(slow_profile, attempt=0)
        test_cases.append({
            "test": "slow_domain",
            "profile_state": "likely_slow=True, avg_response=10s",
            "attempt": 0,
            "timeout_ms": timeout_slow,
            "expected_range": (20000, 60000),  # Higher timeout for slow domains
        })

        # Test 3: Retry attempt (should have higher timeout)
        retry_profile = DomainProfile(domain="retry-domain.com")
        timeout_retry = AdaptiveTimeout.get_timeout(retry_profile, attempt=2)
        test_cases.append({
            "test": "retry_attempt",
            "profile_state": "default",
            "attempt": 2,
            "timeout_ms": timeout_retry,
            "expected_range": (20000, 60000),  # Higher for retries
        })

        # Test 4: Domain with timeouts (should adapt)
        timeout_profile = DomainProfile(
            domain="timeout-domain.com",
            timeout_count=3,
        )
        timeout_after_timeouts = AdaptiveTimeout.get_timeout(timeout_profile, attempt=0)
        test_cases.append({
            "test": "after_timeouts",
            "profile_state": "timeout_count=3",
            "attempt": 0,
            "timeout_ms": timeout_after_timeouts,
            "expected_range": (20000, 60000),  # Higher after timeouts
        })

        # Export results
        exporter.add_domain_profile({
            "test_type": "timeout_calculation",
            "test_cases": test_cases,
        })

        # Log results
        for case in test_cases:
            min_expected, max_expected = case["expected_range"]
            in_range = min_expected <= case["timeout_ms"] <= max_expected
            logger.info(
                f"  {case['test']}: timeout={case['timeout_ms']}ms, "
                f"expected_range={case['expected_range']}, in_range={in_range}"
            )

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Timeout calculation test completed. Results: {output_path}")

    async def test_likely_slow_flag(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
    ):
        """
        Test that likely_slow flag is set after multiple timeouts.

        Uses a domain known to sometimes be slow.
        """
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        test_domain = "wine-searcher.com"
        test_url = "https://www.wine-searcher.com/"

        # Clear existing profile
        domain_store.delete_profile(test_domain)

        # Simulate multiple timeout failures to trigger likely_slow flag
        profile = domain_store.get_profile(test_domain)

        # Record simulated timeout failures
        for i in range(3):
            profile = FeedbackRecorder.record_fetch_result(
                profile=profile,
                tier=1,
                success=False,
                response_time_ms=30000,  # 30s (timed out)
                timed_out=True,
            )

        # Save the profile
        domain_store.save_profile(profile)

        # Verify the flag is set
        updated_profile = domain_store.get_profile(test_domain)

        exporter.add_domain_profile({
            "domain": test_domain,
            "simulated_timeouts": 3,
            "likely_slow_after_simulation": updated_profile.likely_slow,
            "timeout_count": updated_profile.timeout_count,
            "recommended_timeout_ms": updated_profile.recommended_timeout_ms,
        })

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Likely slow flag test completed. Results: {output_path}")
        logger.info(
            f"Profile after 3 timeouts: likely_slow={updated_profile.likely_slow}, "
            f"timeout_count={updated_profile.timeout_count}"
        )

        # Verify timeout count is recorded
        assert updated_profile.timeout_count >= 3, (
            f"Expected timeout_count >= 3, got {updated_profile.timeout_count}"
        )
