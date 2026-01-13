"""
Unit tests for Single Product Celery Task (Task 1.5).

Tests the task skeleton and routing for single product enrichment.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 8
"""

from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from django.test import TestCase

from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
from crawler.tasks import run_single_product_flow
from crawler.services.single_product_types import SingleProductResult, SingleProductJobResult


class RunSingleProductFlowTests(TestCase):
    """Tests for run_single_product_flow function."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Single Product Schedule",
            slug="test-single-product",
            category=ScheduleCategory.SINGLE_PRODUCT,
            search_terms=[
                {"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
                {"name": "Glenfiddich 21", "brand": "Glenfiddich", "product_type": "whiskey"},
            ],
            config={
                "focus_recent_reviews": True,
                "max_review_age_days": 180,
            },
        )
        self.job = CrawlJob.objects.create(schedule=self.schedule)

    def _create_mock_job_result(self, count: int = 2) -> SingleProductJobResult:
        """Create a mock job result with specified product count."""
        job_result = SingleProductJobResult(
            job_id=self.job.id,
            schedule_id=self.schedule.id,
        )
        for i in range(count):
            result = SingleProductResult(
                success=True,
                product_id=uuid4(),
                product_name=f"Product {i}",
                is_new_product=True,
            )
            job_result.add_result(result)
        job_result.finalize()
        return job_result

    @patch('crawler.services.single_product_orchestrator.get_single_product_orchestrator')
    def test_returns_result_dict(self, mock_get_orchestrator):
        """Test that flow returns a result dictionary."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_schedule = AsyncMock(return_value=self._create_mock_job_result(2))
        mock_get_orchestrator.return_value = mock_orchestrator

        result = run_single_product_flow(self.schedule, self.job)

        self.assertIsInstance(result, dict)
        self.assertIn("products_found", result)
        self.assertIn("products_new", result)
        self.assertIn("products_duplicate", result)
        self.assertIn("single_product_job_result", result)

    @patch('crawler.services.single_product_orchestrator.get_single_product_orchestrator')
    def test_processes_all_entries(self, mock_get_orchestrator):
        """Test that flow processes all product entries."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_schedule = AsyncMock(return_value=self._create_mock_job_result(2))
        mock_get_orchestrator.return_value = mock_orchestrator

        result = run_single_product_flow(self.schedule, self.job)

        # Should process 2 entries
        self.assertEqual(result["products_found"], 2)

    @patch('crawler.services.single_product_orchestrator.get_single_product_orchestrator')
    def test_job_result_contains_individual_results(self, mock_get_orchestrator):
        """Test that job result contains individual product results."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_schedule = AsyncMock(return_value=self._create_mock_job_result(2))
        mock_get_orchestrator.return_value = mock_orchestrator

        result = run_single_product_flow(self.schedule, self.job)

        job_result = result["single_product_job_result"]
        self.assertEqual(len(job_result["results"]), 2)

    @patch('crawler.services.single_product_orchestrator.get_single_product_orchestrator')
    def test_handles_empty_search_terms(self, mock_get_orchestrator):
        """Test flow handles schedule with no product entries."""
        empty_schedule = CrawlSchedule.objects.create(
            name="Empty Schedule",
            slug="empty-schedule",
            category=ScheduleCategory.SINGLE_PRODUCT,
            search_terms=[],
        )
        job = CrawlJob.objects.create(schedule=empty_schedule)

        mock_orchestrator = MagicMock()
        mock_orchestrator.process_schedule = AsyncMock(return_value=self._create_mock_job_result(0))
        mock_get_orchestrator.return_value = mock_orchestrator

        result = run_single_product_flow(empty_schedule, job)

        self.assertEqual(result["products_found"], 0)
        self.assertEqual(result["products_failed"], 0)


class ScheduledJobRoutingTests(TestCase):
    """Tests for run_scheduled_job routing to single product flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Single Product Schedule",
            slug="test-sp-routing",
            category=ScheduleCategory.SINGLE_PRODUCT,
            search_terms=[
                {"name": "Test Whiskey", "brand": "Test", "product_type": "whiskey"},
            ],
        )
        self.job = CrawlJob.objects.create(schedule=self.schedule)

    @patch('crawler.tasks.run_single_product_flow')
    def test_routes_to_single_product_flow(self, mock_flow):
        """Test that SINGLE_PRODUCT category routes to single product flow."""
        mock_flow.return_value = {
            "products_found": 1,
            "products_new": 1,
            "products_duplicate": 0,
        }

        from crawler.tasks import run_scheduled_job

        # Run the task synchronously
        run_scheduled_job(str(self.schedule.id), str(self.job.id))

        # Verify it called run_single_product_flow
        mock_flow.assert_called_once()
        call_args = mock_flow.call_args
        self.assertEqual(call_args[0][0].id, self.schedule.id)
        self.assertEqual(call_args[0][1].id, self.job.id)
