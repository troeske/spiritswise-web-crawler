"""
Tests for V1 to V2 migration of tasks.py competition functions.

Task 1.1: Verify that competition-related functions in tasks.py use V2 components:
- CompetitionOrchestratorV2 instead of CompetitionOrchestrator
- QualityGateV2 for quality assessment
- Tasting notes extraction in the extraction schema

Task 1.2: Verify that discovery-related functions use DiscoveryOrchestratorV2:
- run_discovery_flow uses DiscoveryOrchestratorV2
- V1 DiscoveryOrchestrator is not imported

Tasks 1.3 & 1.4: Verify AI Client and AI Extractor V1 imports are not in tasks.py
(These don't exist in tasks.py, verified complete by design)

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
                from crawler.models import CrawlerSource, Job, JobType, JobStatus, SourceCategory

                source = MagicMock(spec=CrawlerSource)
                source.id = "test-source-id"
                source.name = "Test Competition"
                source.base_url = "https://test.com/results/2025"
                source.slug = "test-iwsc"
                source.category = SourceCategory.COMPETITION

                job = MagicMock(spec=Job)
                job.id = "test-job-id"
                job.job_type = JobType.CRAWL

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
        Verify AIClientV2 extraction schema includes tasting notes fields.

        The _get_default_schema method loads from ProductTypeSchema in the database.
        This test sets up a proper schema fixture with tasting notes.
        """
        from crawler.services.ai_client_v2 import AIClientV2
        from crawler.models import ProductTypeSchema
        from crawler.services.schema_builder import get_schema_builder

        # Create ProductTypeSchema with tasting notes in base_fields
        ProductTypeSchema.objects.update_or_create(
            product_type='whiskey',
            defaults={
                'display_name': 'Whiskey',
                'is_active': True,
                'schema': {
                    'base_fields': [
                        'name', 'brand', 'description', 'abv', 'country', 'region',
                        'nose_description', 'palate_description', 'finish_description',
                        'primary_aromas', 'palate_flavors', 'finish_flavors',
                    ],
                    'type_specific_fields': [],
                    'fingerprint_fields': ['name', 'brand', 'abv'],
                }
            }
        )

        # Invalidate schema cache to ensure fresh load
        get_schema_builder().invalidate_cache('whiskey')

        # Create client and get default schema
        client = AIClientV2()

        # Get the schema (sync method)
        schema = client._get_default_schema("whiskey")

        # Schema is a list of field dicts - extract field names
        field_names = {field.get('name', field.get('field_name', '')) for field in schema}

        # Assert: Tasting notes are in schema
        assert 'nose_description' in field_names, "Schema must include nose_description"
        assert 'palate_description' in field_names, "Schema must include palate_description"
        assert 'finish_description' in field_names, "Schema must include finish_description"

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


# ============================================================================
# Task 1.2: Discovery Orchestrator V2 Migration Tests
# ============================================================================


class TestDiscoveryUsesV2:
    """Test that discovery functions use DiscoveryOrchestratorV2."""

    @pytest.mark.django_db
    def test_run_discovery_flow_uses_v2_orchestrator(self):
        """
        Verify run_discovery_flow uses DiscoveryOrchestratorV2.

        The function should import and use DiscoveryOrchestratorV2
        instead of the V1 DiscoveryOrchestrator.
        """
        # Patch the V2 orchestrator at its import location in tasks.py
        # The function does a local import, so we need to patch in the discovery_orchestrator_v2 module
        with patch(
            'crawler.services.discovery_orchestrator_v2.DiscoveryOrchestratorV2'
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock the run method to return a valid DiscoveryJob-like result
            mock_job = MagicMock()
            mock_job.id = "test-discovery-job-id"
            mock_job.products_new = 5
            mock_job.products_updated = 2
            mock_job.serpapi_calls_used = 3
            mock_orchestrator.run = MagicMock(return_value=mock_job)

            # Mock schedule and job
            schedule = MagicMock()
            schedule.search_terms = ["bourbon whiskey"]
            schedule.product_types = ["whiskey"]
            schedule.enrich = False

            job = MagicMock()
            job.id = "test-job-id"

            # Act: Import and call the function (reload to get fresh import)
            import importlib
            import crawler.tasks
            importlib.reload(crawler.tasks)
            from crawler.tasks import run_discovery_flow
            result = run_discovery_flow(schedule, job, enrich=False)

            # Assert: V2 orchestrator was instantiated
            mock_orchestrator_class.assert_called()

    def test_v1_discovery_orchestrator_not_imported(self):
        """
        Verify V1 DiscoveryOrchestrator is not imported in tasks.py.

        After migration, the V1 import:
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator
        should be replaced with V2.
        """
        import crawler.tasks as tasks_module
        import inspect

        source = inspect.getsource(tasks_module)

        v1_import = "from crawler.services.discovery_orchestrator import DiscoveryOrchestrator"
        assert v1_import not in source, (
            "tasks.py should NOT import V1 DiscoveryOrchestrator after migration"
        )

    def test_tasks_module_has_v2_discovery_orchestrator_import(self):
        """
        Verify tasks.py imports DiscoveryOrchestratorV2.

        After migration, the import should be:
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2
        """
        import crawler.tasks as tasks_module
        import importlib

        # Reload to pick up any changes
        importlib.reload(tasks_module)

        # Check source for the V2 import (import might be local to function)
        import inspect
        source = inspect.getsource(tasks_module)

        v2_import = "from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2"
        assert v2_import in source, (
            "tasks.py should import DiscoveryOrchestratorV2"
        )


class TestDiscoveryOrchestratorV2BackwardCompatibility:
    """Test that DiscoveryOrchestratorV2 has backward-compatible methods."""

    def test_v2_orchestrator_has_run_method(self):
        """
        Verify DiscoveryOrchestratorV2 has a run() method for backward compatibility.

        The V1 interface is:
            orchestrator = DiscoveryOrchestrator(schedule=schedule)
            discovery_job = orchestrator.run()

        V2 should support the same interface.
        """
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        # Create orchestrator with a mock schedule
        schedule = MagicMock()
        schedule.search_terms = ["test whiskey"]
        schedule.product_types = ["whiskey"]

        orchestrator = DiscoveryOrchestratorV2(schedule=schedule)

        # Assert: run method exists
        assert hasattr(orchestrator, 'run'), (
            "DiscoveryOrchestratorV2 must have run() method for backward compatibility"
        )
        assert callable(orchestrator.run)

    def test_v2_orchestrator_accepts_schedule_parameter(self):
        """
        Verify DiscoveryOrchestratorV2 __init__ accepts schedule parameter.

        The V1 interface passes schedule to constructor:
            DiscoveryOrchestrator(schedule=schedule)
        """
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        schedule = MagicMock()
        schedule.search_terms = ["test whiskey"]

        # This should not raise an error
        orchestrator = DiscoveryOrchestratorV2(schedule=schedule)

        # Assert: Schedule is stored
        assert orchestrator.schedule == schedule


class TestNoV1ImportsInTasks:
    """
    Verify all V1 imports have been removed from tasks.py.

    Tasks 1.2, 1.3, 1.4 combined - ensure no V1 components are imported.
    """

    def test_no_v1_imports_remain(self):
        """
        Comprehensive check that no V1 component imports remain in tasks.py.

        Checks for:
        - discovery_orchestrator (V1)
        - ai_client (V1)
        - ai_extractor (V1)
        """
        import crawler.tasks as tasks_module
        import inspect

        source = inspect.getsource(tasks_module)

        # V1 imports that should NOT exist
        v1_imports = [
            "from crawler.services.discovery_orchestrator import DiscoveryOrchestrator",
            "from crawler.services.ai_client import",
            "from crawler.discovery.extractors.ai_extractor import AIExtractor",
        ]

        for v1_import in v1_imports:
            assert v1_import not in source, (
                f"tasks.py should NOT contain V1 import: {v1_import}"
            )
