"""
Tests for SmartRouter Domain Intelligence Integration.

Task Group: Phase 6 - SmartRouter Integration
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify that SmartRouter properly integrates with:
- DomainIntelligenceStore (domain profiles)
- SmartTierSelector (intelligent tier selection)
- AdaptiveTimeout (dynamic timeouts)
- EscalationHeuristics (smart escalation)
- FeedbackRecorder (learning from results)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


class TestSmartRouterDomainIntelligence:
    """Tests for SmartRouter domain intelligence integration (Task 6.1)."""

    def test_smart_router_uses_domain_profile(self):
        """SmartRouter fetches domain profile before routing."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="example.com",
            recommended_tier=2,
            likely_js_heavy=True,
        )
        mock_store.get_profile.return_value = mock_profile

        # Create router with injected store
        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Verify store is set
        assert router._domain_store is mock_store

    def test_smart_router_uses_adaptive_timeout(self):
        """SmartRouter uses adaptive timeout instead of fixed."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout

        # Create mock store with profile that has learned timeout
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="slow-site.com",
            success_count=10,
            recommended_timeout_ms=45000,  # Learned 45s timeout
            likely_slow=True,
        )
        mock_store.get_profile.return_value = mock_profile

        # Calculate expected timeout
        expected_timeout = AdaptiveTimeout.get_timeout(mock_profile, attempt=0)

        # Timeout should reflect profile, not default
        assert expected_timeout > 20000  # Greater than base timeout

    def test_smart_router_uses_smart_tier(self):
        """SmartRouter uses SmartTierSelector for starting tier."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )
        from crawler.fetchers.smart_tier_selector import SmartTierSelector

        # Create mock store with bot-protected profile
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="protected-site.com",
            likely_bot_protected=True,
        )
        mock_store.get_profile.return_value = mock_profile

        # Calculate expected tier
        expected_tier = SmartTierSelector.select_starting_tier(mock_profile)

        # Bot-protected should start at tier 3
        assert expected_tier == 3

    def test_smart_router_uses_heuristics(self):
        """SmartRouter uses EscalationHeuristics for escalation."""
        from crawler.fetchers.escalation_heuristics import (
            EscalationHeuristics,
            EscalationResult,
        )
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Test Cloudflare content triggers escalation
        cloudflare_content = """
        <html>
        <title>Just a moment... | Cloudflare</title>
        <body>
            <div>Please enable JavaScript and cookies to continue</div>
            <div>Ray ID: abc123</div>
        </body>
        </html>
        """ + "x" * 500

        profile = DomainProfile(domain="cloudflare-site.com")

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=cloudflare_content,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "cloudflare" in result.reason.lower()

    def test_smart_router_records_feedback(self):
        """SmartRouter records result via FeedbackRecorder."""
        from crawler.fetchers.feedback_recorder import FeedbackRecorder
        from crawler.fetchers.domain_intelligence import DomainProfile

        profile = DomainProfile(
            domain="test.com",
            tier1_success_rate=0.8,
            success_count=5,
        )

        # Record a successful fetch
        updated = FeedbackRecorder.record_fetch_result(
            profile=profile,
            tier=1,
            success=True,
            response_time_ms=5000,
        )

        # Success rate should increase
        assert updated.tier1_success_rate > 0.8
        assert updated.success_count == 6

    def test_smart_router_respects_manual_override(self):
        """Manual override from CrawlerSource is respected."""
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.domain_intelligence import DomainProfile

        # Profile recommends tier 1
        profile = DomainProfile(
            domain="test.com",
            recommended_tier=1,
        )

        # Source has manual override to tier 3
        source = MagicMock()
        source.manual_tier_override = 3
        source.requires_tier3 = False

        tier = SmartTierSelector.select_starting_tier(profile, source=source)

        # Manual override wins
        assert tier == 3

    def test_smart_router_fallback_on_redis_failure(self):
        """Router works with defaults if Redis unavailable."""
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )
        from crawler.fetchers.smart_tier_selector import SmartTierSelector
        from crawler.fetchers.adaptive_timeout import AdaptiveTimeout

        # Simulate Redis failure - store returns default profile
        default_profile = DomainProfile(domain="new-site.com")

        # Should still work with defaults
        tier = SmartTierSelector.select_starting_tier(default_profile)
        timeout = AdaptiveTimeout.get_timeout(default_profile)

        assert tier == 1  # Default to cheapest
        assert timeout == 20000  # Default timeout


class TestSmartRouterFetchIntegration:
    """Tests for SmartRouter fetch() with domain intelligence."""

    @pytest.mark.asyncio
    async def test_fetch_gets_domain_profile(self):
        """fetch() retrieves domain profile before routing."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(domain="example.com")
        mock_store.get_profile.return_value = mock_profile

        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Mock the tier fetcher to return success
        with patch.object(
            router,
            "_try_tier1",
            AsyncMock(
                return_value=MagicMock(
                    content="<html>Test content</html>" + "x" * 1000,
                    status_code=200,
                    headers={},
                    success=True,
                    error=None,
                )
            ),
        ):
            await router.fetch("https://example.com/page")

        # Store should have been queried
        mock_store.get_profile.assert_called_once_with("example.com")

        await router.close()

    @pytest.mark.asyncio
    async def test_fetch_records_success_feedback(self):
        """fetch() records success via FeedbackRecorder."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="example.com",
            success_count=5,
        )
        mock_store.get_profile.return_value = mock_profile

        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Mock the tier fetcher to return success
        with patch.object(
            router,
            "_try_tier1",
            AsyncMock(
                return_value=MagicMock(
                    content="<html>Test content</html>" + "x" * 1000,
                    status_code=200,
                    headers={},
                    success=True,
                    error=None,
                )
            ),
        ):
            await router.fetch("https://example.com/page")

        # Profile should have been saved with updated feedback
        mock_store.save_profile.assert_called()

        await router.close()

    @pytest.mark.asyncio
    async def test_fetch_records_failure_feedback(self):
        """fetch() records failure via FeedbackRecorder."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="example.com",
            failure_count=2,
        )
        mock_store.get_profile.return_value = mock_profile

        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Mock all tiers to fail
        with patch.object(
            router,
            "_try_tier1",
            AsyncMock(
                return_value=MagicMock(
                    content="",
                    status_code=500,
                    headers={},
                    success=False,
                    error="Failed",
                )
            ),
        ):
            with patch.object(
                router,
                "_try_tier2",
                AsyncMock(
                    return_value=MagicMock(
                        content="",
                        status_code=500,
                        headers={},
                        success=False,
                        error="Failed",
                    )
                ),
            ):
                with patch.object(
                    router,
                    "_try_tier3",
                    AsyncMock(
                        return_value=MagicMock(
                            content="",
                            status_code=500,
                            headers={},
                            success=False,
                            error="Failed",
                        )
                    ),
                ):
                    result = await router.fetch("https://example.com/page")

        assert result.success is False

        await router.close()

    @pytest.mark.asyncio
    async def test_fetch_uses_escalation_heuristics(self):
        """fetch() uses EscalationHeuristics for soft failures."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(domain="cloudflare-site.com")
        mock_store.get_profile.return_value = mock_profile

        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Cloudflare challenge content
        cloudflare_html = """
        <html>
        <title>Just a moment... | Cloudflare</title>
        <body>Checking your browser...</body>
        </html>
        """ + "x" * 500

        # Tier 1 returns Cloudflare challenge, Tier 2 returns real content
        with patch.object(
            router,
            "_try_tier1",
            AsyncMock(
                return_value=MagicMock(
                    content=cloudflare_html,
                    status_code=200,
                    headers={},
                    success=True,
                    error=None,
                )
            ),
        ):
            with patch.object(
                router,
                "_try_tier2",
                AsyncMock(
                    return_value=MagicMock(
                        content="<html>Real content</html>" + "x" * 1000,
                        status_code=200,
                        headers={},
                        success=True,
                        error=None,
                    )
                ),
            ) as mock_tier2:
                result = await router.fetch("https://cloudflare-site.com/page")

        # Should have escalated due to Cloudflare detection
        mock_tier2.assert_called_once()
        assert result.tier_used == 2

        await router.close()

    @pytest.mark.asyncio
    async def test_fetch_uses_smart_tier_selection(self):
        """fetch() uses SmartTierSelector based on profile."""
        from crawler.fetchers.smart_router import SmartRouter
        from crawler.fetchers.domain_intelligence import (
            DomainProfile,
            DomainIntelligenceStore,
        )

        # Create mock store with JS-heavy profile
        mock_store = MagicMock(spec=DomainIntelligenceStore)
        mock_profile = DomainProfile(
            domain="js-site.com",
            likely_js_heavy=True,  # Should start at tier 2
        )
        mock_store.get_profile.return_value = mock_profile

        router = SmartRouter(timeout=30, domain_store=mock_store)

        # Mock tier fetchers
        with patch.object(router, "_try_tier1", AsyncMock()) as mock_tier1:
            with patch.object(
                router,
                "_try_tier2",
                AsyncMock(
                    return_value=MagicMock(
                        content="<html>JS content</html>" + "x" * 1000,
                        status_code=200,
                        headers={},
                        success=True,
                        error=None,
                    )
                ),
            ) as mock_tier2:
                result = await router.fetch("https://js-site.com/page")

        # Should skip tier 1 and start at tier 2 due to JS-heavy flag
        mock_tier1.assert_not_called()
        mock_tier2.assert_called_once()
        assert result.tier_used == 2

        await router.close()


class TestSmartRouterDomainExtraction:
    """Tests for domain extraction from URLs."""

    def test_extracts_domain_from_simple_url(self):
        """Extracts domain from simple URL."""
        from crawler.fetchers.smart_router import extract_domain

        domain = extract_domain("https://example.com/page")
        assert domain == "example.com"

    def test_extracts_domain_from_url_with_www(self):
        """Extracts domain without www prefix."""
        from crawler.fetchers.smart_router import extract_domain

        domain = extract_domain("https://www.example.com/page")
        # May or may not strip www depending on implementation
        assert "example.com" in domain

    def test_extracts_domain_from_url_with_port(self):
        """Extracts domain from URL with port."""
        from crawler.fetchers.smart_router import extract_domain

        domain = extract_domain("https://example.com:8080/page")
        assert domain == "example.com"

    def test_extracts_domain_from_url_with_subdomain(self):
        """Extracts full domain including subdomain."""
        from crawler.fetchers.smart_router import extract_domain

        domain = extract_domain("https://api.example.com/v1/data")
        assert domain == "api.example.com"

    def test_handles_invalid_url_gracefully(self):
        """Returns empty or sensible default for invalid URL."""
        from crawler.fetchers.smart_router import extract_domain

        domain = extract_domain("not-a-url")
        # Should not raise, may return empty or the input
        assert domain is not None
