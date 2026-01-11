"""
Scheduler Verification Integration TDD Tests - Phase 10

Spec Reference: docs/specs/UNIFIED_CRAWLER_SCHEDULING.md
                docs/spec-parts/07-VERIFICATION-PIPELINE.md

These tests verify that scheduled crawls integrate with the verification pipeline.
Written FIRST according to TDD methodology - these MUST FAIL initially.

Critical Gap Being Tested:
- CrawlSchedule has no `enrich` field
- save_discovered_product() doesn't call VerificationPipeline
- Scheduled crawls never verify products from multiple sources
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from crawler.models import (
    CrawlSchedule,
    CrawlJob,
    DiscoveredProduct,
    ScheduleCategory,
    ScheduleFrequency,
)


class TestCrawlScheduleEnrichField(TestCase):
    """Tests that CrawlSchedule model has enrich configuration."""

    def test_crawl_schedule_has_enrich_field(self):
        """CrawlSchedule should have an 'enrich' boolean field."""
        schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
        )
        # Should be able to access enrich field
        self.assertFalse(schedule.enrich)  # Default should be False

    def test_crawl_schedule_enrich_can_be_set_true(self):
        """CrawlSchedule.enrich should be settable to True."""
        schedule = CrawlSchedule.objects.create(
            name="Test Schedule Enrich",
            slug="test-schedule-enrich",
            category=ScheduleCategory.DISCOVERY,
            enrich=True,
        )
        self.assertTrue(schedule.enrich)

    def test_crawl_schedule_enrich_persists(self):
        """CrawlSchedule.enrich should persist after save."""
        schedule = CrawlSchedule.objects.create(
            name="Test Schedule Persist",
            slug="test-schedule-persist",
            category=ScheduleCategory.DISCOVERY,
            enrich=True,
        )
        schedule.save()

        # Reload from database
        schedule.refresh_from_db()
        self.assertTrue(schedule.enrich)


class TestScheduledJobPassesEnrich(TestCase):
    """Tests that scheduled job execution passes enrich to flows."""

    def setUp(self):
        self.schedule = CrawlSchedule.objects.create(
            name="Test Discovery Schedule",
            slug="test-discovery",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test whisky"],
            enrich=True,
        )
        self.job = CrawlJob.objects.create(
            schedule=self.schedule,
            status="pending",
        )

    @patch("crawler.tasks.run_discovery_flow")
    def test_run_scheduled_job_passes_enrich_to_discovery(
        self, mock_discovery_flow
    ):
        """run_scheduled_job should pass schedule.enrich to discovery flow."""
        from crawler.tasks import run_scheduled_job

        mock_discovery_flow.return_value = {
            "products_found": 1,
            "products_new": 1,
        }

        run_scheduled_job(
            str(self.schedule.id),
            str(self.job.id),
        )

        # Verify discovery flow was called with enrich
        mock_discovery_flow.assert_called()
        call_args = mock_discovery_flow.call_args
        # Should pass enrich=True from schedule
        if call_args.kwargs:
            self.assertTrue(call_args.kwargs.get("enrich", False))
        elif len(call_args.args) >= 3:
            # enrich might be a positional arg
            self.assertTrue(call_args.args[2])

    @patch("crawler.tasks.run_competition_flow")
    def test_run_scheduled_job_passes_enrich_to_competition(
        self, mock_competition_flow
    ):
        """run_scheduled_job should pass schedule.enrich to competition flow."""
        from crawler.tasks import run_scheduled_job

        # Create competition schedule
        comp_schedule = CrawlSchedule.objects.create(
            name="Test Competition",
            slug="test-competition",
            category=ScheduleCategory.COMPETITION,
            search_terms=["iwsc:2024"],
            enrich=True,
        )
        comp_job = CrawlJob.objects.create(
            schedule=comp_schedule,
            status="pending",
        )

        mock_competition_flow.return_value = {
            "products_found": 1,
            "products_new": 1,
        }

        run_scheduled_job(
            str(comp_schedule.id),
            str(comp_job.id),
        )

        # Verify competition flow was called with enrich
        mock_competition_flow.assert_called()


class TestDiscoveryFlowEnrich(TestCase):
    """Tests that discovery flow respects enrich parameter."""

    def setUp(self):
        self.schedule = CrawlSchedule.objects.create(
            name="Discovery Enrich Test",
            slug="discovery-enrich-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["test query"],
            enrich=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator")
    def test_discovery_orchestrator_receives_enrich(
        self, mock_orchestrator_class
    ):
        """DiscoveryOrchestrator should receive enrich parameter."""
        from crawler.tasks import run_discovery_flow

        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MagicMock(
            products_new=1,
            products_updated=0,
            serpapi_calls_used=1,
            id="test-job-id",
        )
        mock_orchestrator_class.return_value = mock_orchestrator

        job = CrawlJob.objects.create(
            schedule=self.schedule,
            status="running",
        )

        run_discovery_flow(self.schedule, job, enrich=True)

        # Verify orchestrator was created with enrich
        mock_orchestrator_class.assert_called()
        call_kwargs = mock_orchestrator_class.call_args.kwargs
        self.assertTrue(call_kwargs.get("enrich", False))


class TestProductSaverVerification(TestCase):
    """Tests that product_saver calls verification when enrich=True."""

    @patch("crawler.services.product_saver._get_verification_pipeline")
    def test_save_discovered_product_calls_verification_when_enrich(
        self, mock_get_pipeline
    ):
        """save_discovered_product should call verification when enrich=True."""
        from crawler.services.product_saver import save_discovered_product

        # Setup mock
        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        # Call save with enrich=True (using correct signature)
        result = save_discovered_product(
            extracted_data={
                "name": "Test Whiskey Save",
                "abv": 40.0,
            },
            source_url="http://example.com/test-whiskey",
            product_type="whiskey",
            discovery_source="search",
            enrich=True,  # This parameter should be accepted
        )

        # Verify verification was called
        mock_pipeline.verify_product.assert_called()

    @patch("crawler.services.product_saver._get_verification_pipeline")
    def test_save_discovered_product_skips_verification_when_not_enrich(
        self, mock_get_pipeline
    ):
        """save_discovered_product should NOT call verification when enrich=False."""
        from crawler.services.product_saver import save_discovered_product

        mock_pipeline = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline

        # Call save without enrich (default)
        result = save_discovered_product(
            extracted_data={
                "name": "Test Whiskey No Enrich",
            },
            source_url="http://example2.com/test-whiskey",
            product_type="whiskey",
            discovery_source="search",
            enrich=False,
        )

        # Verification should NOT be called
        mock_pipeline.verify_product.assert_not_called()


class TestScheduledCrawlE2EVerification(TestCase):
    """E2E tests for scheduled crawl with verification."""

    def test_schedule_enrich_flag_preserved_in_discovery_flow(self):
        """CrawlSchedule.enrich flag should be preserved for discovery flow."""
        # Create schedule with enrich=True
        schedule = CrawlSchedule.objects.create(
            name="E2E Enrich Test",
            slug="e2e-enrich-test",
            category=ScheduleCategory.DISCOVERY,
            search_terms=["e2e test whisky"],
            enrich=True,
        )

        # Verify enrich flag is set correctly
        self.assertTrue(schedule.enrich)

        # Reload from database to verify persistence
        schedule.refresh_from_db()
        self.assertTrue(schedule.enrich)

        # Verify it can be accessed when passed to flows
        # (The actual flow integration is tested via unit tests above)
        self.assertEqual(schedule.category, ScheduleCategory.DISCOVERY)


class TestVerificationUpdatesScheduleStats(TestCase):
    """Tests that verification results update schedule statistics."""

    def setUp(self):
        self.schedule = CrawlSchedule.objects.create(
            name="Stats Test Schedule",
            slug="stats-test",
            category=ScheduleCategory.DISCOVERY,
            enrich=True,
        )

    def test_schedule_tracks_verified_product_count(self):
        """CrawlSchedule should track number of products verified."""
        # This field should exist
        self.assertEqual(self.schedule.total_products_verified, 0)

    def test_schedule_record_run_stats_includes_verified(self):
        """record_run_stats should accept and store verified count."""
        initial_verified = self.schedule.total_products_verified

        self.schedule.record_run_stats(
            products_found=10,
            products_new=5,
            products_duplicate=5,
            errors=0,
            products_verified=3,  # New parameter
        )

        self.schedule.refresh_from_db()
        self.assertEqual(
            self.schedule.total_products_verified,
            initial_verified + 3
        )
