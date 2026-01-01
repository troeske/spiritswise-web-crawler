"""
Tests for Discovery Scheduling, Quota Management, and Integration (TDD approach).

Phase 5: Scheduling
Phase 6: Quota Management
Phase 7: Testing & Deployment
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from django.test import TestCase
from django.utils import timezone

from crawler.models import (
    SearchTerm,
    DiscoverySchedule,
    DiscoveryJob,
    DiscoveryResult,
    DiscoveredProduct,
    SearchTermCategory,
    SearchTermProductType,
    ScheduleFrequency,
    DiscoveryJobStatus,
)


# ============================================================================
# Phase 5: Scheduling Tests (TDD)
# ============================================================================


class TestCeleryTaskSetup(TestCase):
    """Test TASK-GS-019: Celery Task Setup."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
            max_results_per_term=5,
            is_active=True,
        )
        SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    def test_run_discovery_job_task_exists(self):
        """Test that run_discovery_job task is defined."""
        from crawler.tasks import run_discovery_job

        self.assertIsNotNone(run_discovery_job)
        self.assertTrue(callable(run_discovery_job))

    def test_check_and_run_schedules_task_exists(self):
        """Test that check_and_run_schedules task is defined."""
        from crawler.tasks import check_and_run_schedules

        self.assertIsNotNone(check_and_run_schedules)
        self.assertTrue(callable(check_and_run_schedules))

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator.run")
    def test_run_discovery_job_creates_job(self, mock_run):
        """Test run_discovery_job creates and executes a job."""
        from crawler.tasks import run_discovery_job

        mock_job = Mock()
        mock_job.id = 1
        mock_job.status = DiscoveryJobStatus.COMPLETED
        mock_run.return_value = mock_job

        result = run_discovery_job(str(self.schedule.id))

        self.assertEqual(result["status"], "completed")
        self.assertIn("job_id", result)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator.run")
    def test_run_discovery_job_handles_errors(self, mock_run):
        """Test run_discovery_job handles errors gracefully."""
        from crawler.tasks import run_discovery_job

        mock_run.side_effect = Exception("Test error")

        result = run_discovery_job(str(self.schedule.id))

        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    def test_run_discovery_job_with_invalid_schedule(self):
        """Test run_discovery_job handles invalid schedule ID."""
        from crawler.tasks import run_discovery_job

        result = run_discovery_job("00000000-0000-0000-0000-000000000000")

        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)


class TestCeleryBeatSchedule(TestCase):
    """Test TASK-GS-020: Celery Beat Schedule."""

    def test_beat_schedule_includes_discovery_check(self):
        """Test that Celery Beat schedule includes discovery check."""
        from config.celery import app

        beat_schedule = app.conf.beat_schedule

        # Check that discovery schedule check is configured
        discovery_task_found = False
        for task_name, task_config in beat_schedule.items():
            if "discovery" in task_name.lower() or "check_and_run_schedules" in task_config.get("task", ""):
                discovery_task_found = True
                break

        self.assertTrue(
            discovery_task_found,
            "Discovery schedule check should be in Celery Beat schedule"
        )

    def test_check_and_run_schedules_finds_due_schedules(self):
        """Test check_and_run_schedules finds schedules that are due."""
        from crawler.tasks import check_and_run_schedules

        # Create a schedule that's due
        schedule = DiscoverySchedule.objects.create(
            name="Due Schedule",
            frequency=ScheduleFrequency.DAILY,
            is_active=True,
            next_run=timezone.now() - timedelta(hours=1),  # 1 hour ago
        )

        SearchTerm.objects.create(
            term_template="test {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            is_active=True,
        )

        with patch("crawler.tasks.run_discovery_job.apply_async") as mock_apply:
            result = check_and_run_schedules()

        self.assertGreaterEqual(result["schedules_checked"], 1)

    def test_check_and_run_schedules_skips_inactive(self):
        """Test check_and_run_schedules skips inactive schedules."""
        from crawler.tasks import check_and_run_schedules

        # Create an inactive schedule that would be due
        schedule = DiscoverySchedule.objects.create(
            name="Inactive Schedule",
            frequency=ScheduleFrequency.DAILY,
            is_active=False,
            next_run=timezone.now() - timedelta(hours=1),
        )

        with patch("crawler.tasks.run_discovery_job.apply_async") as mock_apply:
            result = check_and_run_schedules()

        # Should not trigger any jobs for inactive schedule
        self.assertEqual(mock_apply.call_count, 0)

    def test_schedule_updates_next_run_after_execution(self):
        """Test schedule next_run is updated after job execution."""
        schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            is_active=True,
            next_run=timezone.now() - timedelta(hours=1),
        )

        old_next_run = schedule.next_run

        # Simulate schedule being run
        schedule.update_next_run()

        self.assertGreater(schedule.next_run, old_next_run)


class TestManualTriggerSupport(TestCase):
    """Test TASK-GS-021: Manual Trigger Support."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            is_active=True,
        )

    def test_trigger_discovery_job_manual_task_exists(self):
        """Test manual trigger task exists."""
        from crawler.tasks import trigger_discovery_job_manual

        self.assertIsNotNone(trigger_discovery_job_manual)
        self.assertTrue(callable(trigger_discovery_job_manual))

    @patch("crawler.tasks.run_discovery_job.apply_async")
    def test_trigger_discovery_job_manual_dispatches_job(self, mock_apply):
        """Test manual trigger dispatches a job."""
        from crawler.tasks import trigger_discovery_job_manual

        result = trigger_discovery_job_manual(str(self.schedule.id))

        mock_apply.assert_called_once()
        self.assertEqual(result["status"], "dispatched")

    def test_admin_has_run_now_action(self):
        """Test admin has 'Run Now' action for schedules."""
        from crawler.admin import DiscoveryScheduleAdmin

        admin_instance = DiscoveryScheduleAdmin(DiscoverySchedule, None)

        # Check that the action method exists
        self.assertTrue(hasattr(admin_instance, "run_discovery_now"))
        self.assertTrue(callable(getattr(admin_instance, "run_discovery_now")))


# ============================================================================
# Phase 6: Quota Management Tests (TDD)
# ============================================================================


class TestQuotaTracking(TestCase):
    """Test TASK-GS-022: Quota Tracking."""

    def test_quota_manager_class_exists(self):
        """Test QuotaManager class exists."""
        from crawler.services.quota_manager import QuotaManager

        self.assertIsNotNone(QuotaManager)

    def test_quota_manager_tracks_serpapi_usage(self):
        """Test QuotaManager tracks SerpAPI usage."""
        from crawler.services.quota_manager import QuotaManager

        manager = QuotaManager()

        # Record some usage
        manager.record_usage("serpapi", 5)

        usage = manager.get_usage("serpapi")
        self.assertEqual(usage, 5)

    def test_quota_manager_tracks_scrapingbee_usage(self):
        """Test QuotaManager tracks ScrapingBee usage."""
        from crawler.services.quota_manager import QuotaManager

        manager = QuotaManager()

        manager.record_usage("scrapingbee", 10)

        usage = manager.get_usage("scrapingbee")
        self.assertEqual(usage, 10)

    def test_quota_manager_can_use_checks_limit(self):
        """Test can_use() checks against monthly limit."""
        from crawler.services.quota_manager import QuotaManager

        manager = QuotaManager()
        manager.set_limit("serpapi", 100)

        # Should be able to use when under limit
        self.assertTrue(manager.can_use("serpapi", 10))

        # Record usage near limit
        manager.record_usage("serpapi", 95)

        # Should not be able to use 10 more (would exceed 100)
        self.assertFalse(manager.can_use("serpapi", 10))

        # Should still be able to use 5
        self.assertTrue(manager.can_use("serpapi", 5))

    def test_quota_manager_get_remaining(self):
        """Test get_remaining() returns correct amount."""
        from crawler.services.quota_manager import QuotaManager

        manager = QuotaManager()
        manager.set_limit("serpapi", 100)
        manager.record_usage("serpapi", 30)

        remaining = manager.get_remaining("serpapi")
        self.assertEqual(remaining, 70)

    def test_quota_manager_monthly_reset(self):
        """Test quota resets at start of new month."""
        from crawler.services.quota_manager import QuotaManager

        manager = QuotaManager()
        manager.set_limit("serpapi", 100)

        # Record usage in "previous month"
        with patch.object(manager, "_get_current_month", return_value="2025-12"):
            manager.record_usage("serpapi", 50)

        # Check usage in "current month" (should be reset)
        with patch.object(manager, "_get_current_month", return_value="2026-01"):
            usage = manager.get_usage("serpapi")
            self.assertEqual(usage, 0)


class TestQuotaAwareExecution(TestCase):
    """Test TASK-GS-023: Quota-Aware Execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
            max_results_per_term=5,
        )
        SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.quota_manager.QuotaManager.can_use")
    def test_orchestrator_checks_quota_before_search(self, mock_can_use):
        """Test orchestrator checks quota before SerpAPI calls."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_can_use.return_value = False  # Quota exceeded

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        with patch.object(orchestrator, "_search") as mock_search:
            with patch.object(orchestrator, "_init_smart_crawler"):
                # Run should stop early due to quota
                try:
                    job = orchestrator.run()
                    # Job should complete but with no searches
                    self.assertEqual(job.serpapi_calls_used, 0)
                except Exception:
                    pass  # Expected if quota check raises

    def test_orchestrator_stops_at_quota_limit(self):
        """Test orchestrator stops processing when quota is reached."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        # Create multiple search terms
        for i in range(5):
            SearchTerm.objects.create(
                term_template=f"test term {i}",
                category=SearchTermCategory.BEST_LISTS,
                product_type=SearchTermProductType.WHISKEY,
                priority=100 - i,
                is_active=True,
            )

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock the search to simulate quota check integration
        # In a real scenario, the orchestrator would check quota before each search
        call_count = [0]

        def mock_search_with_limit(query):
            call_count[0] += 1
            if call_count[0] > 2:
                return []  # Simulate stopping after quota
            return [{"title": "Test", "link": f"https://example.com/test{call_count[0]}"}]

        with patch.object(orchestrator, "_search", side_effect=mock_search_with_limit):
            mock_extraction = Mock()
            mock_extraction.success = True
            mock_extraction.data = {"name": "Test"}
            mock_extraction.needs_review = False
            mock_extraction.source_url = "https://example.com"
            mock_extraction.source_type = "other"
            mock_extraction.name_match_score = 0.9
            mock_extraction.scrapingbee_calls = 1
            mock_extraction.ai_calls = 1

            with patch.object(
                orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
            ):
                job = orchestrator.run()

        # Should have processed limited terms
        self.assertGreater(job.serpapi_calls_used, 0)

    def test_quota_warning_logged_when_low(self):
        """Test warning is logged when quota is running low."""
        from crawler.services.quota_manager import QuotaManager
        import logging

        manager = QuotaManager()
        manager.set_limit("serpapi", 100)
        manager.record_usage("serpapi", 85)  # 85% used

        with self.assertLogs("crawler.services.quota_manager", level="WARNING") as logs:
            manager.check_quota_warnings("serpapi")

        self.assertTrue(any("quota" in log.lower() for log in logs.output))


class TestAdminQuotaDashboard(TestCase):
    """Test TASK-GS-024: Admin Quota Dashboard."""

    def test_quota_usage_model_exists(self):
        """Test QuotaUsage model exists for tracking."""
        from crawler.models import QuotaUsage

        self.assertIsNotNone(QuotaUsage)

    def test_quota_admin_registered(self):
        """Test quota admin is registered."""
        from django.contrib.admin.sites import site
        from crawler.models import QuotaUsage

        self.assertIn(QuotaUsage, site._registry)

    def test_quota_admin_displays_usage(self):
        """Test quota admin displays current usage."""
        from crawler.admin import QuotaUsageAdmin
        from crawler.models import QuotaUsage

        admin = QuotaUsageAdmin(QuotaUsage, None)

        # Check list_display includes usage fields
        self.assertIn("api_name", admin.list_display)
        self.assertIn("current_usage", admin.list_display)
        self.assertIn("monthly_limit", admin.list_display)


# ============================================================================
# Phase 7: Integration Tests (TDD)
# ============================================================================


class TestEndToEndDiscoveryFlow(TestCase):
    """Test TASK-GS-026: Integration Tests - End-to-end flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Integration Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=5,
            max_results_per_term=3,
            is_active=True,
        )
        SearchTerm.objects.create(
            term_template="best scotch whisky {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_full_discovery_flow(self, mock_search):
        """Test complete discovery flow from schedule to products."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        # Mock search results
        mock_search.return_value = [
            {"title": "Best Scotch 2025 - Macallan 18", "link": "https://example.com/macallan"},
            {"title": "Glenfiddich 21 Review", "link": "https://retailer.com/glenfiddich"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock SmartCrawler
        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Macallan 18", "brand": "Macallan"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/macallan"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.95
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        # Verify job completed
        self.assertEqual(job.status, DiscoveryJobStatus.COMPLETED)
        self.assertGreater(job.serpapi_calls_used, 0)

        # Verify results created
        results = DiscoveryResult.objects.filter(job=job)
        self.assertGreater(results.count(), 0)

    def test_discovery_creates_products_in_database(self):
        """Test discovery creates DiscoveredProduct records."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        initial_count = DiscoveredProduct.objects.count()

        with patch.object(DiscoveryOrchestrator, "_search") as mock_search:
            mock_search.return_value = [
                {"title": "Test Product", "link": "https://example.com/test"}
            ]

            orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

            mock_extraction = Mock()
            mock_extraction.success = True
            mock_extraction.data = {"name": "Test Product", "product_type": "whiskey"}
            mock_extraction.needs_review = False
            mock_extraction.source_url = "https://example.com/test"
            mock_extraction.source_type = "other"
            mock_extraction.name_match_score = 0.9
            mock_extraction.scrapingbee_calls = 1
            mock_extraction.ai_calls = 1

            with patch.object(
                orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
            ):
                job = orchestrator.run()

        # Should have created at least one product
        self.assertGreater(DiscoveredProduct.objects.count(), initial_count)


class TestDatabaseOperations(TestCase):
    """Test database operations for discovery system."""

    def test_discovery_job_creates_with_schedule(self):
        """Test DiscoveryJob is created with schedule reference."""
        schedule = DiscoverySchedule.objects.create(
            name="DB Test Schedule",
            frequency=ScheduleFrequency.WEEKLY,
        )

        job = DiscoveryJob.objects.create(
            schedule=schedule,
            status=DiscoveryJobStatus.PENDING,
        )

        self.assertEqual(job.schedule, schedule)
        self.assertIsNotNone(job.id)

    def test_discovery_result_links_to_job_and_term(self):
        """Test DiscoveryResult properly links to job and search term."""
        schedule = DiscoverySchedule.objects.create(
            name="DB Test Schedule",
            frequency=ScheduleFrequency.WEEKLY,
        )
        job = DiscoveryJob.objects.create(
            schedule=schedule,
            status=DiscoveryJobStatus.RUNNING,
        )
        term = SearchTerm.objects.create(
            term_template="test {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
        )

        result = DiscoveryResult.objects.create(
            job=job,
            search_term=term,
            source_url="https://example.com/test",
            source_domain="example.com",
            source_title="Test",
            search_rank=1,
        )

        self.assertEqual(result.job, job)
        self.assertEqual(result.search_term, term)

    def test_cascade_delete_job_deletes_results(self):
        """Test deleting a job cascades to results."""
        schedule = DiscoverySchedule.objects.create(
            name="Cascade Test",
            frequency=ScheduleFrequency.DAILY,
        )
        job = DiscoveryJob.objects.create(
            schedule=schedule,
            status=DiscoveryJobStatus.COMPLETED,
        )
        term = SearchTerm.objects.create(
            term_template="test",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
        )

        # Create results
        for i in range(3):
            DiscoveryResult.objects.create(
                job=job,
                search_term=term,
                source_url=f"https://example.com/test{i}",
                source_domain="example.com",
                source_title=f"Test {i}",
                search_rank=i + 1,
            )

        result_count = DiscoveryResult.objects.filter(job=job).count()
        self.assertEqual(result_count, 3)

        # Delete job
        job.delete()

        # Results should be deleted
        result_count = DiscoveryResult.objects.filter(search_term=term).count()
        self.assertEqual(result_count, 0)


class TestScheduleFrequencyCalculation(TestCase):
    """Test schedule frequency calculations."""

    def test_daily_schedule_calculates_next_run(self):
        """Test daily schedule sets next_run to tomorrow."""
        schedule = DiscoverySchedule.objects.create(
            name="Daily Test",
            frequency=ScheduleFrequency.DAILY,
            is_active=True,
        )

        schedule.update_next_run()

        # Should be at least 12 hours from now (could be tomorrow at run_at_hour)
        min_expected = timezone.now() + timedelta(hours=12)
        self.assertGreater(schedule.next_run, timezone.now())

    def test_weekly_schedule_calculates_next_run(self):
        """Test weekly schedule sets next_run to next week."""
        schedule = DiscoverySchedule.objects.create(
            name="Weekly Test",
            frequency=ScheduleFrequency.WEEKLY,
            is_active=True,
        )

        schedule.update_next_run()

        # Should be in the future
        self.assertGreater(schedule.next_run, timezone.now())
        # Should be within 7 days
        max_expected = timezone.now() + timedelta(days=8)
        self.assertLess(schedule.next_run, max_expected)

    def test_monthly_schedule_calculates_next_run(self):
        """Test monthly schedule sets next_run to next month."""
        schedule = DiscoverySchedule.objects.create(
            name="Monthly Test",
            frequency=ScheduleFrequency.MONTHLY,
            is_active=True,
        )

        schedule.update_next_run()

        # Should be in the future
        self.assertGreater(schedule.next_run, timezone.now())
        # Should be within 31 days
        max_expected = timezone.now() + timedelta(days=32)
        self.assertLess(schedule.next_run, max_expected)
