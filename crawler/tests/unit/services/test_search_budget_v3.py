"""
Unit tests for V3 Search Budget Defaults.

Task 4.1: Update Search Budget Defaults

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4.1

Tests verify:
- max_serpapi_searches = 6
- max_sources_per_product = 8
- max_enrichment_time_seconds = 180
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase


class SearchBudgetDefaultsTests(TestCase):
    """Tests for V3 search budget defaults."""

    def test_default_max_serpapi_searches_is_6(self):
        """Test default max_serpapi_searches is 6 in V3."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        orchestrator = EnrichmentOrchestratorV3()

        self.assertEqual(orchestrator.DEFAULT_MAX_SEARCHES, 6)

    def test_default_max_sources_per_product_is_8(self):
        """Test default max_sources_per_product is 8 in V3."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        orchestrator = EnrichmentOrchestratorV3()

        self.assertEqual(orchestrator.DEFAULT_MAX_SOURCES, 8)

    def test_default_max_enrichment_time_is_180(self):
        """Test default max_enrichment_time_seconds is 180 in V3."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        orchestrator = EnrichmentOrchestratorV3()

        self.assertEqual(orchestrator.DEFAULT_MAX_TIME_SECONDS, 180.0)


class SearchBudgetFromConfigTests(TestCase):
    """Tests for loading budget from PipelineConfig."""

    def setUp(self):
        """Set up test fixtures."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_uses_pipeline_config_max_searches(
        self, mock_product_type_config, mock_pipeline_config
    ):
        """Test uses max_serpapi_searches from PipelineConfig."""
        mock_config = MagicMock()
        mock_config.max_serpapi_searches = 10
        mock_config.max_sources_per_product = 8
        mock_config.max_enrichment_time_seconds = 180
        mock_pipeline_config.objects.get.return_value = mock_config
        mock_product_type_config.DoesNotExist = Exception

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 10)

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_uses_pipeline_config_max_sources(
        self, mock_product_type_config, mock_pipeline_config
    ):
        """Test uses max_sources_per_product from PipelineConfig."""
        mock_config = MagicMock()
        mock_config.max_serpapi_searches = 6
        mock_config.max_sources_per_product = 12
        mock_config.max_enrichment_time_seconds = 180
        mock_pipeline_config.objects.get.return_value = mock_config
        mock_product_type_config.DoesNotExist = Exception

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_sources"], 12)

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    @patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig')
    def test_uses_pipeline_config_max_time(
        self, mock_product_type_config, mock_pipeline_config
    ):
        """Test uses max_enrichment_time_seconds from PipelineConfig."""
        mock_config = MagicMock()
        mock_config.max_serpapi_searches = 6
        mock_config.max_sources_per_product = 8
        mock_config.max_enrichment_time_seconds = 300
        mock_pipeline_config.objects.get.return_value = mock_config
        mock_product_type_config.DoesNotExist = Exception

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_time"], 300.0)

    @patch('crawler.services.enrichment_orchestrator_v3.PipelineConfig')
    def test_falls_back_to_defaults_when_no_config(self, mock_pipeline_config):
        """Test falls back to V3 defaults when no PipelineConfig."""
        from crawler.models import PipelineConfig as RealPipelineConfig
        mock_pipeline_config.DoesNotExist = RealPipelineConfig.DoesNotExist
        mock_pipeline_config.objects.get.side_effect = RealPipelineConfig.DoesNotExist

        limits = self.orchestrator._get_budget_limits("whiskey")

        self.assertEqual(limits["max_searches"], 6)
        self.assertEqual(limits["max_sources"], 8)
        self.assertEqual(limits["max_time"], 180.0)


class BudgetComparisonTests(TestCase):
    """Tests comparing V2 and V3 budget defaults."""

    def test_v3_has_higher_search_limit_than_v2(self):
        """Test V3 has more searches allowed than V2."""
        from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        v2 = EnrichmentOrchestratorV2()
        v3 = EnrichmentOrchestratorV3()

        self.assertGreater(v3.DEFAULT_MAX_SEARCHES, v2.DEFAULT_MAX_SEARCHES)
        self.assertEqual(v2.DEFAULT_MAX_SEARCHES, 3)
        self.assertEqual(v3.DEFAULT_MAX_SEARCHES, 6)

    def test_v3_has_higher_source_limit_than_v2(self):
        """Test V3 allows more sources than V2."""
        from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        v2 = EnrichmentOrchestratorV2()
        v3 = EnrichmentOrchestratorV3()

        self.assertGreater(v3.DEFAULT_MAX_SOURCES, v2.DEFAULT_MAX_SOURCES)
        self.assertEqual(v2.DEFAULT_MAX_SOURCES, 5)
        self.assertEqual(v3.DEFAULT_MAX_SOURCES, 8)

    def test_v3_has_longer_time_limit_than_v2(self):
        """Test V3 has longer enrichment time than V2."""
        from crawler.services.enrichment_orchestrator_v2 import EnrichmentOrchestratorV2
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3

        v2 = EnrichmentOrchestratorV2()
        v3 = EnrichmentOrchestratorV3()

        self.assertGreater(v3.DEFAULT_MAX_TIME_SECONDS, v2.DEFAULT_MAX_TIME_SECONDS)
        self.assertEqual(v2.DEFAULT_MAX_TIME_SECONDS, 120.0)
        self.assertEqual(v3.DEFAULT_MAX_TIME_SECONDS, 180.0)


class BudgetTrackingTests(TestCase):
    """Tests for budget tracking during enrichment."""

    def setUp(self):
        """Set up test fixtures."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_session_tracks_searches_performed(self):
        """Test enrichment session tracks searches performed."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentSession

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )

        self.assertEqual(session.searches_performed, 0)

        session.searches_performed += 1
        self.assertEqual(session.searches_performed, 1)

    def test_session_tracks_sources_used(self):
        """Test enrichment session tracks sources used."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentSession

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )

        self.assertEqual(len(session.sources_used), 0)

        session.sources_used.append("https://example.com/review")
        self.assertEqual(len(session.sources_used), 1)

    def test_check_budget_exceeded_for_searches(self):
        """Test budget exceeded check for searches."""
        import time
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentSession

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 6  # At limit
        session.start_time = time.time()  # Set current time

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}

        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertTrue(exceeded)

    def test_check_budget_not_exceeded_under_limit(self):
        """Test budget not exceeded when under limits."""
        import time
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentSession

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3  # Under limit
        session.start_time = time.time()  # Set current time

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}

        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertFalse(exceeded)
