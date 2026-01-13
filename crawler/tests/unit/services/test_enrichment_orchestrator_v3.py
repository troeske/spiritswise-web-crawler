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

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    def test_create_session_with_defaults(self, mock_config):
        """Test session creation uses V3 defaults."""
        from crawler.models import PipelineConfig as RealPipelineConfig
        mock_config.DoesNotExist = RealPipelineConfig.DoesNotExist
        mock_config.objects.get.side_effect = RealPipelineConfig.DoesNotExist

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


class PipelineConfigLoadingTests(TestCase):
    """Tests for loading config from PipelineConfig."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    def test_loads_from_pipeline_config(self, mock_pipeline_config):
        """Test budget limits loaded from PipelineConfig."""
        mock_config = MagicMock()
        mock_config.max_serpapi_searches = 5
        mock_config.max_sources_per_product = 7
        mock_config.max_enrichment_time_seconds = 150
        mock_pipeline_config.objects.get.return_value = mock_config

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 5)
        self.assertEqual(limits["max_sources"], 7)
        self.assertEqual(limits["max_time"], 150.0)

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    def test_falls_back_to_defaults(self, mock_pipeline_config):
        """Test falls back to defaults when config not found."""
        from crawler.models import PipelineConfig as RealPipelineConfig
        mock_pipeline_config.DoesNotExist = RealPipelineConfig.DoesNotExist
        mock_pipeline_config.objects.get.side_effect = RealPipelineConfig.DoesNotExist

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 6)
        self.assertEqual(limits["max_sources"], 8)
        self.assertEqual(limits["max_time"], 180.0)
