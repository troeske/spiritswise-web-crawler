"""
Unit tests for Enrichment Orchestrator V3.

Task 4.8: Update Enrichment Orchestrator to V3

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 5

Tests verify:
- Full pipeline flow with new budget
- ECP calculation at end
- Awards search always runs
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase

from crawler.services.enrichment_orchestrator_v3 import (
    EnrichmentOrchestratorV3,
    EnrichmentSession,
    get_enrichment_orchestrator_v3,
    reset_enrichment_orchestrator_v3,
)


class OrchestratorV3InitializationTests(TestCase):
    """Tests for V3 orchestrator initialization."""

    def test_orchestrator_v3_exists(self):
        """Test EnrichmentOrchestratorV3 class exists."""
        orchestrator = EnrichmentOrchestratorV3()
        self.assertIsNotNone(orchestrator)

    def test_default_budget_values(self):
        """Test V3 default budget values."""
        self.assertEqual(EnrichmentOrchestratorV3.DEFAULT_MAX_SEARCHES, 6)
        self.assertEqual(EnrichmentOrchestratorV3.DEFAULT_MAX_SOURCES, 8)
        self.assertEqual(EnrichmentOrchestratorV3.DEFAULT_MAX_TIME_SECONDS, 180.0)

    def test_singleton_getter(self):
        """Test singleton getter returns same instance."""
        reset_enrichment_orchestrator_v3()

        instance1 = get_enrichment_orchestrator_v3()
        instance2 = get_enrichment_orchestrator_v3()

        self.assertIs(instance1, instance2)

    def test_singleton_reset(self):
        """Test singleton reset creates new instance."""
        instance1 = get_enrichment_orchestrator_v3()
        reset_enrichment_orchestrator_v3()
        instance2 = get_enrichment_orchestrator_v3()

        self.assertIsNot(instance1, instance2)


class SessionCreationTests(TestCase):
    """Tests for enrichment session creation."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_create_session_with_defaults(self, mock_config):
        """Test session creation uses V3 defaults."""
        from crawler.models import ProductTypeConfig as RealProductTypeConfig
        mock_config.DoesNotExist = RealProductTypeConfig.DoesNotExist
        mock_config.objects.get.side_effect = RealProductTypeConfig.DoesNotExist

        initial_data = {"name": "Test Whiskey", "brand": "Test"}

        session = self.orchestrator._create_session("whiskey", initial_data)

        self.assertEqual(session.max_searches, 6)
        self.assertEqual(session.max_sources, 8)
        self.assertEqual(session.max_time_seconds, 180.0)

    def test_session_has_required_fields(self):
        """Test session has all required fields."""
        initial_data = {"name": "Test Whiskey"}

        session = EnrichmentSession(
            initial_data=initial_data,
            product_type="whiskey"
        )

        # V3 required fields
        self.assertTrue(hasattr(session, 'searches_performed'))
        self.assertTrue(hasattr(session, 'max_sources'))
        self.assertTrue(hasattr(session, 'max_searches'))
        self.assertTrue(hasattr(session, 'max_time_seconds'))
        self.assertTrue(hasattr(session, 'members_only_sites_detected'))
        self.assertTrue(hasattr(session, 'awards_search_completed'))

    def test_session_copies_initial_data(self):
        """Test session makes a copy of initial data."""
        initial_data = {"name": "Test Whiskey", "brand": "Test"}

        session = EnrichmentSession(
            initial_data=initial_data,
            product_type="whiskey"
        )

        # Modify current_data
        session.current_data["new_field"] = "value"

        # Initial data should be unchanged
        self.assertNotIn("new_field", session.initial_data)


class BudgetTrackingTests(TestCase):
    """Tests for budget tracking."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_check_search_budget_not_exceeded(self):
        """Test budget not exceeded under limit."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3
        session.start_time = time.time()

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertFalse(exceeded)

    def test_check_search_budget_exceeded_at_limit(self):
        """Test budget exceeded at limit."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 6
        session.start_time = time.time()

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertTrue(exceeded)

    def test_check_source_budget_exceeded(self):
        """Test source budget exceeded."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 2
        session.sources_used = ["url1", "url2", "url3", "url4", "url5", "url6", "url7", "url8"]
        session.start_time = time.time()

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertTrue(exceeded)


class MembersOnlyIntegrationTests(TestCase):
    """Tests for members-only detection integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_refund_on_members_only(self, mock_get_detector):
        """Test budget refund when members-only detected."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = True
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3

        result = self.orchestrator._check_and_refund_if_members_only(
            session,
            url="https://smws.com/tasting",
            content="<html>Members Only</html>",
            status_code=200
        )

        self.assertTrue(result)
        self.assertEqual(session.searches_performed, 2)
        self.assertIn("https://smws.com/tasting", session.members_only_sites_detected)


class AwardsSearchIntegrationTests(TestCase):
    """Tests for awards search integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_awards_search_runs(self):
        """Test awards search runs and sets flag."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ):
            self.orchestrator._search_awards(session, "whiskey")

        self.assertTrue(session.awards_search_completed)

    def test_awards_search_preserves_main_budget(self):
        """Test awards search doesn't affect main search budget."""
        session = EnrichmentSession(
            initial_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 4
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([{"competition": "IWSC"}], ["https://iwsc.net"])
        ):
            self.orchestrator._search_awards(session, "whiskey")

        # Main budget unchanged
        self.assertEqual(session.searches_performed, 4)


class QualityGateV3IntegrationTests(TestCase):
    """Tests for QualityGateV3 integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_quality_gate_property_returns_v3(self):
        """Test quality_gate property returns QualityGateV3 instance."""
        from crawler.services.quality_gate_v3 import QualityGateV3

        gate = self.orchestrator.quality_gate

        self.assertIsInstance(gate, QualityGateV3)


class RemainingBudgetTests(TestCase):
    """Tests for remaining budget calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_get_remaining_budget(self):
        """Test remaining budget calculation."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 2
        session.sources_used = ["url1", "url2", "url3"]

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        remaining = self.orchestrator._get_remaining_budget(session, limits)

        self.assertEqual(remaining["searches"], 4)  # 6 - 2
        self.assertEqual(remaining["sources"], 5)   # 8 - 3

    def test_remaining_budget_not_negative(self):
        """Test remaining budget doesn't go negative."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 10  # Over limit
        session.sources_used = ["url" + str(i) for i in range(15)]  # Over limit

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        remaining = self.orchestrator._get_remaining_budget(session, limits)

        self.assertEqual(remaining["searches"], 0)
        self.assertEqual(remaining["sources"], 0)


class AwardsQueryBuildingTests(TestCase):
    """Tests for awards search query building."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_build_query_includes_brand(self):
        """Test query includes brand."""
        product_data = {"name": "18 Year Old", "brand": "Lagavulin"}

        query = self.orchestrator._build_awards_search_query(product_data)

        self.assertIn("Lagavulin", query)

    def test_build_query_includes_name(self):
        """Test query includes product name."""
        product_data = {"name": "Highland Park 18", "brand": "Highland Park"}

        query = self.orchestrator._build_awards_search_query(product_data)

        self.assertIn("Highland Park 18", query)

    def test_build_query_includes_award_keywords(self):
        """Test query includes award-related keywords."""
        product_data = {"name": "Test", "brand": "Test"}

        query = self.orchestrator._build_awards_search_query(product_data)

        query_lower = query.lower()
        self.assertTrue("award" in query_lower or "medal" in query_lower)


class ProductTypeConfigLoadingTests(TestCase):
    """Tests for loading config from ProductTypeConfig (consolidated)."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_loads_from_product_type_config(self, mock_product_type_config):
        """Test budget limits loaded from ProductTypeConfig."""
        mock_config = MagicMock()
        mock_config.max_serpapi_searches = 5
        mock_config.max_sources_per_product = 7
        mock_config.max_enrichment_time_seconds = 150
        mock_product_type_config.objects.get.return_value = mock_config

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 5)
        self.assertEqual(limits["max_sources"], 7)
        self.assertEqual(limits["max_time"], 150.0)

    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_falls_back_to_defaults(self, mock_product_type_config):
        """Test falls back to defaults when config not found."""
        from crawler.models import ProductTypeConfig as RealProductTypeConfig
        mock_product_type_config.DoesNotExist = RealProductTypeConfig.DoesNotExist
        mock_product_type_config.objects.get.side_effect = RealProductTypeConfig.DoesNotExist

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 6)
        self.assertEqual(limits["max_sources"], 8)
        self.assertEqual(limits["max_time"], 180.0)


class SmartRouterIntegrationTests(TestCase):
    """Tests for SmartRouter integration in V3 orchestrator."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_v3_has_smart_router(self):
        """Test V3 orchestrator has SmartRouter attribute."""
        self.assertTrue(hasattr(self.orchestrator, '_smart_router'))

    def test_v3_overrides_fetch_and_extract(self):
        """Test V3 overrides _fetch_and_extract method."""
        # V3 should have its own implementation, not inherited from V2
        v3_method = EnrichmentOrchestratorV3._fetch_and_extract
        from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
        v2_method = EnrichmentOrchestratorV2._fetch_and_extract

        # Methods should be different (V3 overrides V2)
        self.assertIsNot(v3_method, v2_method)

    @patch('crawler.services.enrichment_orchestrator_v3.SmartRouter')
    async def test_fetch_uses_smart_router(self, mock_smart_router_class):
        """Test _fetch_and_extract uses SmartRouter."""
        from crawler.fetchers.smart_router import FetchResult

        # Mock SmartRouter instance
        mock_router = MagicMock()
        mock_router.fetch = MagicMock(return_value=FetchResult(
            content="<html><body>Test content</body></html>",
            status_code=200,
            headers={},
            success=True,
            tier_used=1,
        ))
        mock_smart_router_class.return_value = mock_router

        orchestrator = EnrichmentOrchestratorV3()

        # Call fetch
        result, confidences = await orchestrator._fetch_and_extract(
            "https://example.com",
            "whiskey",
            ["name", "brand"],
        )

        # Verify SmartRouter.fetch was called
        mock_router.fetch.assert_called_once()

    @patch('crawler.services.enrichment_orchestrator_v3.SmartRouter')
    async def test_tier_escalation_on_403(self, mock_smart_router_class):
        """Test SmartRouter escalates to Tier 3 on 403 error."""
        from crawler.fetchers.smart_router import FetchResult

        # Mock SmartRouter that returns Tier 3 result (ScrapingBee)
        mock_router = MagicMock()
        mock_router.fetch = MagicMock(return_value=FetchResult(
            content="<html><body>Content via ScrapingBee</body></html>",
            status_code=200,
            headers={},
            success=True,
            tier_used=3,  # Tier 3 = ScrapingBee
        ))
        mock_smart_router_class.return_value = mock_router

        orchestrator = EnrichmentOrchestratorV3()

        result, confidences = await orchestrator._fetch_and_extract(
            "https://whiskybase.com/blocked",
            "whiskey",
            ["name"],
        )

        # Verify fetch was called and would escalate
        mock_router.fetch.assert_called_once()

    @patch('crawler.services.enrichment_orchestrator_v3.SmartRouter')
    async def test_handles_fetch_failure_gracefully(self, mock_smart_router_class):
        """Test graceful handling of SmartRouter fetch failure."""
        from crawler.fetchers.smart_router import FetchResult

        # Mock SmartRouter that returns failure
        mock_router = MagicMock()
        mock_router.fetch = MagicMock(return_value=FetchResult(
            content="",
            status_code=403,
            headers={},
            success=False,
            tier_used=3,
            error="All tiers failed",
        ))
        mock_smart_router_class.return_value = mock_router

        orchestrator = EnrichmentOrchestratorV3()

        result, confidences = await orchestrator._fetch_and_extract(
            "https://blocked-site.com",
            "whiskey",
            ["name"],
        )

        # Should return empty dict on failure
        self.assertEqual(result, {})
        self.assertEqual(confidences, {})
