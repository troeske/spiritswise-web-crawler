"""
TDD Tests for unified scheduling Celery tasks.

Tests written BEFORE implementation per TDD approach.
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase
from django.utils import timezone


class TestCheckDueSchedulesTask(TestCase):
    """Tests for check_due_schedules periodic task."""

    def test_check_due_schedules_finds_due_schedules(self):
        """Test that check_due_schedules finds schedules that are due."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from crawler.tasks import check_due_schedules

        now = timezone.now()

        # Create a due schedule
        due = CrawlSchedule.objects.create(
            name="Due Schedule",
            slug="due-schedule",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now - timedelta(hours=1),
        )

        # Create a not-due schedule
        not_due = CrawlSchedule.objects.create(
            name="Future Schedule",
            slug="future-schedule",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now + timedelta(hours=1),
        )

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = check_due_schedules()

        assert result["jobs_dispatched"] == 1
        assert len(result["details"]) == 1
        assert result["details"][0]["schedule_id"] == str(due.id)

    def test_check_due_schedules_finds_never_run(self):
        """Test that schedules that never ran are considered due."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from crawler.tasks import check_due_schedules

        # Create a schedule that never ran (next_run is None)
        never_run = CrawlSchedule.objects.create(
            name="Never Run",
            slug="never-run-task",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=None,
        )

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = check_due_schedules()

        assert result["jobs_dispatched"] == 1
        assert result["details"][0]["schedule_id"] == str(never_run.id)

    def test_check_due_schedules_skips_inactive(self):
        """Test that inactive schedules are skipped."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from crawler.tasks import check_due_schedules

        now = timezone.now()

        # Create an inactive but due schedule
        inactive = CrawlSchedule.objects.create(
            name="Inactive",
            slug="inactive-schedule",
            category=ScheduleCategory.DISCOVERY,
            is_active=False,
            next_run=now - timedelta(hours=1),
        )

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = check_due_schedules()

        assert result["jobs_dispatched"] == 0

    def test_check_due_schedules_creates_crawl_job(self):
        """Test that a CrawlJob is created for each due schedule."""
        from crawler.models import CrawlSchedule, ScheduleCategory, CrawlJob
        from crawler.tasks import check_due_schedules

        now = timezone.now()

        schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-job",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now - timedelta(hours=1),
        )

        initial_job_count = CrawlJob.objects.count()

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = check_due_schedules()

        assert CrawlJob.objects.count() == initial_job_count + 1

    def test_check_due_schedules_dispatches_to_correct_queue(self):
        """Test that tasks are dispatched to the correct queue based on category."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from crawler.tasks import check_due_schedules

        now = timezone.now()

        # Competition schedule
        comp = CrawlSchedule.objects.create(
            name="Competition",
            slug="comp-queue-test",
            category=ScheduleCategory.COMPETITION,
            is_active=True,
            next_run=now - timedelta(hours=1),
        )

        # Discovery schedule
        disc = CrawlSchedule.objects.create(
            name="Discovery",
            slug="disc-queue-test",
            category=ScheduleCategory.DISCOVERY,
            is_active=True,
            next_run=now - timedelta(hours=1),
        )

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = check_due_schedules()

            # Check that apply_async was called with correct queues
            calls = mock_task.apply_async.call_args_list

            queues_used = [call.kwargs.get("queue") for call in calls]
            assert "crawl" in queues_used  # Competition uses crawl queue
            assert "discovery" in queues_used  # Discovery uses discovery queue


class TestRunScheduledJobTask(TestCase):
    """Tests for run_scheduled_job worker task."""

    def test_run_scheduled_job_updates_job_status(self):
        """Test that job status is updated during execution."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory, CrawlJobStatus
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Status Test",
            slug="status-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        job = CrawlJob.objects.create(schedule=schedule)
        assert job.status == CrawlJobStatus.PENDING

        with patch("crawler.tasks.run_discovery_flow") as mock_flow:
            mock_flow.return_value = {
                "products_found": 5,
                "products_new": 3,
                "products_duplicate": 2,
            }
            run_scheduled_job(str(schedule.id), str(job.id))

        job.refresh_from_db()
        assert job.status == CrawlJobStatus.COMPLETED

    def test_run_scheduled_job_routes_to_discovery_orchestrator(self):
        """Test that DISCOVERY category routes to DiscoveryOrchestrator."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Discovery Test",
            slug="discovery-route-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        job = CrawlJob.objects.create(schedule=schedule)

        with patch("crawler.tasks.run_discovery_flow") as mock_disc:
            with patch("crawler.tasks.run_competition_flow") as mock_comp:
                mock_disc.return_value = {"products_found": 0, "products_new": 0, "products_duplicate": 0}
                run_scheduled_job(str(schedule.id), str(job.id))

                mock_disc.assert_called_once()
                mock_comp.assert_not_called()

    def test_run_scheduled_job_routes_to_competition_orchestrator(self):
        """Test that COMPETITION category routes to CompetitionOrchestrator."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Competition Test",
            slug="comp-route-test",
            category=ScheduleCategory.COMPETITION,
            search_terms=["iwsc:2024"],
            base_url="https://iwsc.net/results/",
        )

        job = CrawlJob.objects.create(schedule=schedule)

        with patch("crawler.tasks.run_discovery_flow") as mock_disc:
            with patch("crawler.tasks.run_competition_flow") as mock_comp:
                mock_comp.return_value = {"products_found": 0, "products_new": 0, "products_duplicate": 0}
                run_scheduled_job(str(schedule.id), str(job.id))

                mock_comp.assert_called_once()
                mock_disc.assert_not_called()

    def test_run_scheduled_job_updates_schedule_after_completion(self):
        """Test that schedule.update_next_run is called after completion."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Next Run Test",
            slug="next-run-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        assert schedule.last_run is None
        assert schedule.total_runs == 0

        job = CrawlJob.objects.create(schedule=schedule)

        with patch("crawler.tasks.run_discovery_flow") as mock_flow:
            mock_flow.return_value = {
                "products_found": 5,
                "products_new": 3,
                "products_duplicate": 2,
            }
            run_scheduled_job(str(schedule.id), str(job.id))

        schedule.refresh_from_db()
        assert schedule.last_run is not None
        assert schedule.next_run is not None
        assert schedule.total_runs == 1

    def test_run_scheduled_job_records_stats(self):
        """Test that schedule stats are updated after completion."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Stats Test",
            slug="stats-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        job = CrawlJob.objects.create(schedule=schedule)

        with patch("crawler.tasks.run_discovery_flow") as mock_flow:
            mock_flow.return_value = {
                "products_found": 10,
                "products_new": 7,
                "products_duplicate": 3,
            }
            run_scheduled_job(str(schedule.id), str(job.id))

        schedule.refresh_from_db()
        assert schedule.total_products_found == 10
        assert schedule.total_products_new == 7
        assert schedule.total_products_duplicate == 3

    def test_run_scheduled_job_handles_failure(self):
        """Test that job status is set to FAILED on exception."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory, CrawlJobStatus
        from crawler.tasks import run_scheduled_job

        schedule = CrawlSchedule.objects.create(
            name="Failure Test",
            slug="failure-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        job = CrawlJob.objects.create(schedule=schedule)

        with patch("crawler.tasks.run_discovery_flow") as mock_flow:
            mock_flow.side_effect = Exception("Test error")

            with pytest.raises(Exception):
                run_scheduled_job(str(schedule.id), str(job.id))

        job.refresh_from_db()
        assert job.status == CrawlJobStatus.FAILED
        assert "Test error" in job.error_message


class TestTriggerScheduledJobManual(TestCase):
    """Tests for manual trigger task."""

    def test_trigger_scheduled_job_manual_creates_job(self):
        """Test that manual trigger creates a CrawlJob."""
        from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory
        from crawler.tasks import trigger_scheduled_job_manual

        schedule = CrawlSchedule.objects.create(
            name="Manual Test",
            slug="manual-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        initial_count = CrawlJob.objects.count()

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            trigger_scheduled_job_manual(str(schedule.id))

        assert CrawlJob.objects.count() == initial_count + 1

    def test_trigger_scheduled_job_manual_dispatches_task(self):
        """Test that manual trigger dispatches run_scheduled_job."""
        from crawler.models import CrawlSchedule, ScheduleCategory
        from crawler.tasks import trigger_scheduled_job_manual

        schedule = CrawlSchedule.objects.create(
            name="Manual Dispatch Test",
            slug="manual-dispatch",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
        )

        with patch("crawler.tasks.run_scheduled_job") as mock_task:
            mock_task.apply_async = MagicMock()
            result = trigger_scheduled_job_manual(str(schedule.id))

        mock_task.apply_async.assert_called_once()
        assert result["triggered"] is True


class TestCeleryBeatConfiguration(TestCase):
    """Tests for Celery Beat schedule configuration."""

    def test_check_due_schedules_in_beat_schedule(self):
        """Test that check_due_schedules is in the Beat schedule."""
        from config.celery import app

        beat_schedule = app.conf.beat_schedule

        # Find the task in beat schedule
        task_found = False
        for name, config in beat_schedule.items():
            if config.get("task") == "crawler.tasks.check_due_schedules":
                task_found = True
                break

        assert task_found, "check_due_schedules not found in beat_schedule"

    def test_task_queue_routing(self):
        """Test that tasks are routed to correct queues.

        Note: This is a configuration test. The actual routing is defined
        in config/celery.py and may not be loaded in test settings.
        We verify the tasks exist and can be imported.
        """
        from crawler.tasks import (
            check_due_schedules,
            run_scheduled_job,
            trigger_scheduled_job_manual,
        )

        # Verify tasks are defined and are Celery tasks
        assert hasattr(check_due_schedules, "apply_async")
        assert hasattr(run_scheduled_job, "apply_async")
        assert hasattr(trigger_scheduled_job_manual, "apply_async")

        # Verify task names are correct
        assert check_due_schedules.name == "crawler.tasks.check_due_schedules"
        assert run_scheduled_job.name == "crawler.tasks.run_scheduled_job"
        assert trigger_scheduled_job_manual.name == "crawler.tasks.trigger_scheduled_job_manual"
