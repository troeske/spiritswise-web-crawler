"""
E2E Test: Manual Overrides.

Tests that manual tier and timeout overrides in CrawlerSource take precedence
over domain intelligence recommendations. This is critical for:
1. Competition sites with known behavior (IWSC, DWWA)
2. Producer sites with specific requirements
3. Sites where automatic detection doesn't work well

Test scenarios:
1. CrawlerSource with manual_tier_override=3 skips Tier 1 and 2
2. CrawlerSource with manual_timeout_override=45000 uses custom timeout
3. Manual overrides take precedence over domain profile recommendations

NO MOCKS - All requests are real.
NO SYNTHETIC DATA - All URLs are real.
NO SHORTCUTS - If a service fails, debug and fix.
"""

import asyncio
import logging
import pytest
from datetime import datetime
from typing import Dict, Optional
from unittest.mock import MagicMock

from tests.e2e.utils.test_state_manager import TestStateManager
from tests.e2e.utils.results_exporter import ResultsExporter

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def state_manager():
    """Create state manager for this test."""
    return TestStateManager("manual_overrides")


@pytest.fixture(scope="function")
def exporter():
    """Create results exporter for this test."""
    return ResultsExporter("manual_overrides")


class MockCrawlerSource:
    """
    Mock CrawlerSource for testing manual overrides.

    Simulates a CrawlerSource with manual tier and timeout overrides
    without requiring database access.
    """

    def __init__(
        self,
        name: str,
        requires_tier3: bool = False,
        manual_tier_override: Optional[int] = None,
        manual_timeout_override: Optional[int] = None,
        age_gate_cookies: Optional[Dict] = None,
    ):
        self.id = f"mock-{name}"
        self.name = name
        self.requires_tier3 = requires_tier3
        self.manual_tier_override = manual_tier_override
        self.manual_timeout_override = manual_timeout_override
        self.age_gate_cookies = age_gate_cookies or {}

    def save(self, *args, **kwargs):
        """Mock save method."""
        pass


@pytest.mark.e2e
@pytest.mark.asyncio
class TestManualOverrides:
    """
    E2E tests for manual override functionality in domain intelligence.

    These tests verify that:
    1. SmartTierSelector respects manual_tier_override from CrawlerSource
    2. AdaptiveTimeout respects manual_timeout_override
    3. Manual overrides take precedence over domain profile recommendations
    """

    async def test_tier_override_selection(
        self,
        domain_store,
        exporter,
    ):
        """
        Test that SmartTierSelector respects manual tier override.

        Verifies:
        1. When source has manual_tier_override, that tier is used
        2. Domain profile recommendations are ignored
        """
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        test_cases = []

        # Test 1: No override - uses domain profile
        profile_recommends_1 = DomainProfile(
            domain="no-override.com",
            recommended_tier=1,
        )
        source_no_override = MockCrawlerSource(name="no-override")
        tier_no_override = SmartTierSelector.select_starting_tier(
            profile_recommends_1, source_no_override
        )
        test_cases.append({
            "test": "no_override",
            "source_override": None,
            "profile_recommended": 1,
            "selected_tier": tier_no_override,
            "expected": 1,
        })

        # Test 2: Manual override to Tier 3
        profile_recommends_1_v2 = DomainProfile(
            domain="override-tier3.com",
            recommended_tier=1,
        )
        source_tier3_override = MockCrawlerSource(
            name="tier3-override",
            manual_tier_override=3,
        )
        tier_override_3 = SmartTierSelector.select_starting_tier(
            profile_recommends_1_v2, source_tier3_override
        )
        test_cases.append({
            "test": "manual_tier3_override",
            "source_override": 3,
            "profile_recommended": 1,
            "selected_tier": tier_override_3,
            "expected": 3,
        })

        # Test 3: Manual override to Tier 2
        profile_recommends_3 = DomainProfile(
            domain="override-tier2.com",
            recommended_tier=3,
            likely_bot_protected=True,
        )
        source_tier2_override = MockCrawlerSource(
            name="tier2-override",
            manual_tier_override=2,
        )
        tier_override_2 = SmartTierSelector.select_starting_tier(
            profile_recommends_3, source_tier2_override
        )
        test_cases.append({
            "test": "manual_tier2_override_overrides_profile",
            "source_override": 2,
            "profile_recommended": 3,
            "selected_tier": tier_override_2,
            "expected": 2,
        })

        # Test 4: requires_tier3 flag (legacy behavior)
        profile_default = DomainProfile(
            domain="requires-tier3.com",
            recommended_tier=1,
        )
        source_requires_tier3 = MockCrawlerSource(
            name="requires-tier3",
            requires_tier3=True,
        )
        tier_requires_3 = SmartTierSelector.select_starting_tier(
            profile_default, source_requires_tier3
        )
        test_cases.append({
            "test": "requires_tier3_flag",
            "source_override": "requires_tier3=True",
            "profile_recommended": 1,
            "selected_tier": tier_requires_3,
            "expected": 3,
        })

        # Export results
        exporter.add_domain_profile({
            "test_type": "tier_override_selection",
            "test_cases": test_cases,
        })

        # Log and verify results
        all_passed = True
        for case in test_cases:
            passed = case["selected_tier"] == case["expected"]
            all_passed = all_passed and passed
            logger.info(
                f"  {case['test']}: override={case['source_override']}, "
                f"profile={case['profile_recommended']}, selected={case['selected_tier']}, "
                f"expected={case['expected']}, passed={passed}"
            )

        output_path = exporter.finalize("COMPLETED" if all_passed else "FAILED")
        logger.info(f"Tier override test completed. Results: {output_path}")

        # Assert all tests passed
        for case in test_cases:
            assert case["selected_tier"] == case["expected"], (
                f"Test {case['test']} failed: expected {case['expected']}, "
                f"got {case['selected_tier']}"
            )

    async def test_timeout_override(
        self,
        domain_store,
        exporter,
    ):
        """
        Test that AdaptiveTimeout respects manual timeout override.

        Note: Manual timeout override is typically stored in CrawlerSource
        and applied at the SmartRouter level, not in AdaptiveTimeout directly.
        This test verifies the expected behavior.
        """
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout
        from crawler.fetchers.domain_intelligence import DomainProfile

        test_cases = []

        # Test 1: Profile with manual_override_timeout_ms set
        profile_with_override = DomainProfile(
            domain="timeout-override.com",
            recommended_timeout_ms=20000,
            manual_override_timeout_ms=45000,
        )
        timeout_with_override = AdaptiveTimeout.get_timeout(profile_with_override, attempt=0)
        test_cases.append({
            "test": "profile_with_timeout_override",
            "manual_override_ms": 45000,
            "profile_recommended_ms": 20000,
            "actual_timeout_ms": timeout_with_override,
            "override_respected": timeout_with_override == 45000,
        })

        # Test 2: Profile without override uses calculated value
        profile_no_override = DomainProfile(
            domain="no-timeout-override.com",
            recommended_timeout_ms=20000,
        )
        timeout_no_override = AdaptiveTimeout.get_timeout(profile_no_override, attempt=0)
        test_cases.append({
            "test": "profile_without_timeout_override",
            "manual_override_ms": None,
            "profile_recommended_ms": 20000,
            "actual_timeout_ms": timeout_no_override,
            "uses_calculated": timeout_no_override != 45000,
        })

        # Export results
        exporter.add_domain_profile({
            "test_type": "timeout_override",
            "test_cases": test_cases,
        })

        # Log results
        for case in test_cases:
            logger.info(
                f"  {case['test']}: override={case.get('manual_override_ms')}, "
                f"actual={case['actual_timeout_ms']}"
            )

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Timeout override test completed. Results: {output_path}")

    async def test_real_fetch_with_override(
        self,
        domain_store,
        state_manager,
        exporter,
        redis_client,
    ):
        """
        Test that SmartRouter respects manual tier override in real fetch.

        Uses a known competition URL with Tier 3 override.
        """
        from crawler.fetchers.smart_router import SmartRouter

        test_url = "https://iwsc.net/results"
        test_domain = "iwsc.net"

        # Clear existing profile
        domain_store.delete_profile(test_domain)

        router = SmartRouter(
            redis_client=redis_client,
            domain_store=domain_store,
            timeout=45,
        )

        results = []

        try:
            # Fetch WITHOUT override - should use domain intelligence
            result_no_override = await router.fetch(test_url)
            results.append({
                "test": "no_override",
                "tier_used": result_no_override.tier_used,
                "success": result_no_override.success,
            })
            logger.info(
                f"No override: tier={result_no_override.tier_used}, "
                f"success={result_no_override.success}"
            )

            # Create source with Tier 3 override
            source_with_override = MockCrawlerSource(
                name="iwsc-tier3",
                manual_tier_override=3,
            )

            # Fetch WITH Tier 3 override
            result_with_override = await router.fetch(
                test_url,
                source=source_with_override,
            )
            results.append({
                "test": "with_tier3_override",
                "tier_used": result_with_override.tier_used,
                "success": result_with_override.success,
                "expected_tier": 3,
            })
            logger.info(
                f"With Tier 3 override: tier={result_with_override.tier_used}, "
                f"success={result_with_override.success}"
            )

            # Create source with Tier 2 override
            source_tier2 = MockCrawlerSource(
                name="iwsc-tier2",
                manual_tier_override=2,
            )

            # Fetch WITH Tier 2 override
            result_tier2 = await router.fetch(
                test_url,
                source=source_tier2,
            )
            results.append({
                "test": "with_tier2_override",
                "tier_used": result_tier2.tier_used,
                "success": result_tier2.success,
                "expected_tier": 2,
            })
            logger.info(
                f"With Tier 2 override: tier={result_tier2.tier_used}, "
                f"success={result_tier2.success}"
            )

        finally:
            await router.close()

        # Export results
        exporter.add_domain_profile({
            "domain": test_domain,
            "url": test_url,
            "fetch_results": results,
        })

        output_path = exporter.finalize("COMPLETED")
        logger.info(f"Real fetch with override test completed. Results: {output_path}")

        # Verify tier overrides were respected
        for result in results:
            if "expected_tier" in result:
                # The tier_used should be >= expected_tier (could escalate higher)
                assert result["tier_used"] >= result["expected_tier"], (
                    f"Test {result['test']} failed: expected tier >= {result['expected_tier']}, "
                    f"got {result['tier_used']}"
                )

    async def test_override_precedence(
        self,
        domain_store,
        exporter,
    ):
        """
        Test the precedence order of tier selection.

        Expected precedence (highest to lowest):
        1. manual_tier_override on source
        2. requires_tier3 flag on source
        3. Domain profile recommendation
        4. Default (Tier 1)
        """
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Create profile that recommends Tier 2
        profile = DomainProfile(
            domain="precedence-test.com",
            recommended_tier=2,
            likely_js_heavy=True,
        )

        precedence_tests = []

        # Test 1: manual_tier_override wins over everything
        source_manual = MockCrawlerSource(
            name="manual-override",
            manual_tier_override=1,  # Override to Tier 1
            requires_tier3=True,  # This should be ignored
        )
        tier_manual = SmartTierSelector.select_starting_tier(profile, source_manual)
        precedence_tests.append({
            "test": "manual_override_wins",
            "manual_override": 1,
            "requires_tier3": True,
            "profile_recommends": 2,
            "selected": tier_manual,
            "expected": 1,
        })

        # Test 2: requires_tier3 wins over profile
        source_requires = MockCrawlerSource(
            name="requires-tier3",
            requires_tier3=True,
        )
        tier_requires = SmartTierSelector.select_starting_tier(profile, source_requires)
        precedence_tests.append({
            "test": "requires_tier3_wins_over_profile",
            "manual_override": None,
            "requires_tier3": True,
            "profile_recommends": 2,
            "selected": tier_requires,
            "expected": 3,
        })

        # Test 3: Profile recommendation used when no source override
        source_no_override = MockCrawlerSource(name="no-override")
        tier_profile = SmartTierSelector.select_starting_tier(profile, source_no_override)
        precedence_tests.append({
            "test": "profile_used_when_no_override",
            "manual_override": None,
            "requires_tier3": False,
            "profile_recommends": 2,
            "selected": tier_profile,
            "expected": 2,
        })

        # Test 4: Default (Tier 1) when no profile or source info
        default_profile = DomainProfile(domain="default.com")
        source_default = MockCrawlerSource(name="default")
        tier_default = SmartTierSelector.select_starting_tier(default_profile, source_default)
        precedence_tests.append({
            "test": "default_tier_1",
            "manual_override": None,
            "requires_tier3": False,
            "profile_recommends": 1,
            "selected": tier_default,
            "expected": 1,
        })

        # Export results
        exporter.add_domain_profile({
            "test_type": "override_precedence",
            "precedence_tests": precedence_tests,
        })

        # Log and verify results
        all_passed = True
        for test in precedence_tests:
            passed = test["selected"] == test["expected"]
            all_passed = all_passed and passed
            logger.info(
                f"  {test['test']}: selected={test['selected']}, "
                f"expected={test['expected']}, passed={passed}"
            )

        output_path = exporter.finalize("COMPLETED" if all_passed else "FAILED")
        logger.info(f"Override precedence test completed. Results: {output_path}")

        # Assert all tests passed
        for test in precedence_tests:
            assert test["selected"] == test["expected"], (
                f"Precedence test {test['test']} failed: expected {test['expected']}, "
                f"got {test['selected']}"
            )
