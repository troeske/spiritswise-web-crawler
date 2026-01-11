"""
Tests for V1 to V2 migration of tasks.py competition functions.

Task 1.1: Verify that competition-related functions in tasks.py use V2 components:
- CompetitionOrchestratorV2 instead of CompetitionOrchestrator
- QualityGateV2 for quality assessment
- Tasting notes extraction in the extraction schema

TDD Approach: These tests should FAIL initially, then PASS after migration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


class TestProcessCompetitionSourceUsesV2Orchestrator:
    """Test 1: Verify process_competition_source uses CompetitionOrchestratorV2."""

    @pytest.mark.django_db
    def test_crawl_competition_source_uses_v2_orchestrator(self):
        """
        Verify _crawl_competition_source uses CompetitionOrchestratorV2.

        The function should import and instantiate CompetitionOrchestratorV2
        instead of the V1 CompetitionOrchestrator.
        """
        # Arrange: Mock the V2 orchestrator
        with patch(
            'crawler.tasks.CompetitionOrchestratorV2'
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock the async method to return a valid result
            mock_result = MagicMock()
            mock_result.awards_found = 5
            mock_result.skeletons_created = 3
            mock_result.skeletons_updated = 2
            mock_result.errors = []
            mock_result.awards_data = []
            mock_result.to_dict = MagicMock(return_value={})
            mock_orchestrator.run_competition_discovery = AsyncMock(return_value=mock_result)

            # Mock SmartRouter at its source module (imported locally in functions)
            with patch('crawler.fetchers.smart_router.SmartRouter') as mock_router_class:
                mock_router = AsyncMock()
                mock_router_class.return_value = mock_router
                mock_fetch_result = MagicMock()
                mock_fetch_result.success = True
                mock_fetch_result.content = "<html></html>"
                mock_router.fetch = AsyncMock(return_value=mock_fetch_result)
                mock_router.close = AsyncMock()

                # Mock source and job
                from crawler.models import CrawlerSource, CrawlJob, SourceCategory

                source = MagicMock(spec=CrawlerSource)
                source.id = "test-source-id"
                source.name = "Test Competition"
                source.base_url = "https://test.com/results/2025"
                source.slug = "test-iwsc"
                source.category = SourceCategory.COMPETITION

                job = MagicMock(spec=CrawlJob)
                job.id = "test-job-id"

                # Act: Import and call the function
                from crawler.tasks import _crawl_competition_source
                result = _crawl_competition_source(source, job)

                # Assert: V2 orchestrator was instantiated
                mock_orchestrator_class.assert_called()

    @pytest.mark.django_db
    def test_enrich_skeletons_uses_v2_orchestrator(self):
        """
        Verify enrich_skeletons task uses CompetitionOrchestratorV2.
        """
        with patch(
            'crawler.tasks.CompetitionOrchestratorV2'
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator.get_pending_skeletons_count = MagicMock(return_value=0)

            # Act: Import and call the function
            from crawler.tasks import enrich_skeletons
            result = enrich_skeletons()

            # Assert: V2 orchestrator was instantiated
            mock_orchestrator_class.assert_called()

    @pytest.mark.django_db
    def test_run_competition_flow_uses_v2_orchestrator(self):
        """
        Verify run_competition_flow uses CompetitionOrchestratorV2.
        """
        with patch(
            'crawler.tasks.CompetitionOrchestratorV2'
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock the async method
            mock_result = MagicMock()
            mock_result.awards_found = 5
            mock_result.skeletons_created = 3
            mock_result.skeletons_updated = 2
            mock_result.errors = []
            mock_result.to_dict = MagicMock(return_value={})
            mock_orchestrator.run_competition_discovery = AsyncMock(return_value=mock_result)

            # Mock SmartRouter at its source module (imported locally in functions)
            with patch('crawler.fetchers.smart_router.SmartRouter') as mock_router_class:
                mock_router = MagicMock()
                mock_router_class.return_value = mock_router
                mock_fetch_result = MagicMock()
                mock_fetch_result.success = True
                mock_fetch_result.content = "<html></html>"
                mock_router.fetch = MagicMock(return_value=mock_fetch_result)

                # Mock schedule and job
                schedule = MagicMock()
                schedule.search_terms = ["iwsc:2025"]
                schedule.base_url = "https://www.iwsc.net/results/search/"
                schedule.product_types = ["whiskey"]
                schedule.max_results_per_term = 10
                schedule.enrich = False

                job = MagicMock()
                job.id = "test-job-id"

                # Act: Import and call the function
                from crawler.tasks import run_competition_flow
                result = run_competition_flow(schedule, job)

                # Assert: V2 orchestrator was instantiated
                mock_orchestrator_class.assert_called()


class TestCompetitionUsesV2QualityGate:
    """Test 2: Verify competition extraction uses QualityGateV2."""

    def test_v2_orchestrator_uses_quality_gate_v2(self):
        """
        Verify CompetitionOrchestratorV2 uses QualityGateV2 for quality assessment.

        This is an indirect test - we verify the V2 orchestrator's internal
        components are V2 versions.
        """
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2
        from crawler.services.quality_gate_v2 import QualityGateV2

        # Act: Create orchestrator
        orchestrator = CompetitionOrchestratorV2()

        # Assert: Quality gate is V2 version
        assert isinstance(orchestrator.quality_gate, QualityGateV2)

    def test_v2_orchestrator_assess_quality_method_exists(self):
        """
        Verify CompetitionOrchestratorV2 has quality assessment capability.
        """
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        # Assert: Method exists
        assert hasattr(orchestrator, '_assess_quality')
        assert callable(orchestrator._assess_quality)


class TestCompetitionExtractsTastingNotes:
    """Test 3: Verify tasting notes are in extraction schema."""

    @pytest.mark.django_db
    def test_ai_client_v2_fallback_schema_includes_tasting_notes(self):
        """
        Verify AIClientV2 fallback schema includes tasting notes fields.

        The _get_default_schema method should return a list that includes
        nose_description, palate_description, finish_description fields.
        """
        from crawler.services.ai_client_v2 import AIClientV2

        # Create client and get default schema
        client = AIClientV2()

        # Get the fallback schema (sync method)
        schema = client._get_default_schema("whiskey")

        # Assert: Tasting notes are in fallback schema
        assert 'nose_description' in schema, "Schema must include nose_description"
        assert 'palate_description' in schema, "Schema must include palate_description"
        assert 'finish_description' in schema, "Schema must include finish_description"

    def test_competition_extraction_result_can_hold_tasting_notes(self):
        """
        Verify CompetitionExtractionResult dataclass can hold tasting notes.
        """
        from crawler.services.competition_orchestrator_v2 import CompetitionExtractionResult

        # Create result with tasting notes in product_data
        result = CompetitionExtractionResult(
            success=True,
            product_data={
                'name': 'Test Whisky',
                'nose_description': 'Sweet caramel and vanilla',
                'palate_description': 'Rich honey with oak',
                'finish_description': 'Long and warming',
            }
        )

        # Assert: Tasting notes are stored correctly
        assert result.product_data['nose_description'] == 'Sweet caramel and vanilla'
        assert result.product_data['palate_description'] == 'Rich honey with oak'
        assert result.product_data['finish_description'] == 'Long and warming'


class TestV2ImportsInTasksFile:
    """Test that tasks.py imports V2 components."""

    def test_tasks_module_has_v2_orchestrator_import(self):
        """
        Verify tasks.py imports CompetitionOrchestratorV2.

        After migration, the import should be:
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2
        """
        import crawler.tasks as tasks_module
        import importlib

        # Reload to pick up any changes
        importlib.reload(tasks_module)

        # Check if CompetitionOrchestratorV2 is accessible in the module
        assert hasattr(tasks_module, 'CompetitionOrchestratorV2'), (
            "tasks.py should import CompetitionOrchestratorV2"
        )

    def test_v1_orchestrator_not_imported(self):
        """
        Verify tasks.py no longer imports V1 CompetitionOrchestrator.

        After migration, the V1 import should be removed.
        """
        import crawler.tasks as tasks_module
        import inspect

        # Get the source code of the tasks module
        source = inspect.getsource(tasks_module)

        # Check that V1 import is not present (but allow V2 import line)
        v1_import = "from crawler.services.competition_orchestrator import CompetitionOrchestrator"
        assert v1_import not in source, (
            "tasks.py should NOT import V1 CompetitionOrchestrator after migration"
        )
