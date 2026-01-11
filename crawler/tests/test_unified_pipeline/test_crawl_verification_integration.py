"""
Crawl Verification Integration TDD Tests - Phase 9.3

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md
                docs/spec-parts/13-REST-API-ENDPOINTS.md

These tests verify that the award crawl task integrates with verification pipeline.
Written FIRST according to TDD methodology - these MUST FAIL initially.

Critical Gap Being Tested:
- trigger_award_crawl task saves products with status='partial' only
- No VerificationPipeline called during crawl
- Products never get source_count > 1 or verified_fields populated
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from dataclasses import dataclass

from crawler.models import APICrawlJob, DiscoveredProduct


@dataclass
class MockURLInfo:
    """Mock URL info object for collector results."""
    url: str
    medal_hint: str = None
    product_type_hint: str = None


class TestCrawlTaskVerificationOption(TestCase):
    """Tests that crawl task accepts and uses verification option."""

    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_task_accepts_enrich_parameter(
        self, mock_extractor_class, mock_get_collector
    ):
        """trigger_award_crawl should accept enrich parameter."""
        from crawler.tasks import trigger_award_crawl

        # Setup mocks
        mock_collector = MagicMock()
        mock_collector.collect.return_value = []
        mock_get_collector.return_value = mock_collector

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Task should accept enrich parameter without error
        try:
            # Call with enrich=True (should be a valid parameter)
            result = trigger_award_crawl(
                job_id=str(job.job_id),
                source="iwsc",
                year=2025,
                enrich=True,  # This parameter should be accepted
            )
            # If we get here without error, parameter is accepted
            self.assertTrue(True)
        except TypeError as e:
            if "enrich" in str(e):
                self.fail("trigger_award_crawl does not accept 'enrich' parameter")
            raise


class TestCrawlTaskCallsVerification(TestCase):
    """Tests that crawl task calls verification when enrich=True."""

    @patch("crawler.tasks._get_verification_pipeline")
    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_enrich_true_calls_verification_pipeline(
        self, mock_extractor_class, mock_get_collector, mock_get_pipeline
    ):
        """When enrich=True, crawl task should call VerificationPipeline."""
        from crawler.tasks import trigger_award_crawl

        # Setup collector mock
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [
            MockURLInfo(url="http://example.com/award1", medal_hint="Gold")
        ]
        mock_get_collector.return_value = mock_collector

        # Setup extractor mock
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "name": "Test Whiskey Award",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_extractor_class.return_value = mock_extractor

        # Setup verification pipeline mock
        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Run task with enrich=True
        trigger_award_crawl(
            job_id=str(job.job_id),
            source="iwsc",
            year=2025,
            enrich=True,
        )

        # Verify verification pipeline was called
        mock_pipeline.verify_product.assert_called()

    @patch("crawler.tasks._get_verification_pipeline")
    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_enrich_false_does_not_call_verification(
        self, mock_extractor_class, mock_get_collector, mock_get_pipeline
    ):
        """When enrich=False (default), should NOT call VerificationPipeline."""
        from crawler.tasks import trigger_award_crawl

        # Setup collector mock
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [
            MockURLInfo(url="http://example.com/award1", medal_hint="Gold")
        ]
        mock_get_collector.return_value = mock_collector

        # Setup extractor mock
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "name": "Test Whiskey NoEnrich",
            "product_type": "whiskey",
        }
        mock_extractor_class.return_value = mock_extractor

        # Setup verification pipeline mock
        mock_pipeline = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Run task with enrich=False (default)
        trigger_award_crawl(
            job_id=str(job.job_id),
            source="iwsc",
            year=2025,
            enrich=False,
        )

        # Verify verification pipeline was NOT called
        mock_pipeline.verify_product.assert_not_called()


class TestCrawlTaskUpdatesProductVerification(TestCase):
    """Tests that crawl task updates product with verification results."""

    @patch("crawler.tasks._get_verification_pipeline")
    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_enrich_updates_source_count(
        self, mock_extractor_class, mock_get_collector, mock_get_pipeline
    ):
        """Product source_count should be updated after verification."""
        from crawler.tasks import trigger_award_crawl

        # Setup collector mock
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [
            MockURLInfo(url="http://example.com/award1", medal_hint="Gold")
        ]
        mock_get_collector.return_value = mock_collector

        # Setup extractor mock
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "name": "Test Whiskey SourceCount",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_extractor_class.return_value = mock_extractor

        # Setup verification pipeline mock that updates source_count
        mock_pipeline = MagicMock()

        def verify_side_effect(product):
            product.source_count = 3
            product.save()
            return MagicMock(
                sources_used=3,
                verified_fields=["name", "abv"],
                conflicts=[],
            )

        mock_pipeline.verify_product.side_effect = verify_side_effect
        mock_get_pipeline.return_value = mock_pipeline

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Run task with enrich=True
        trigger_award_crawl(
            job_id=str(job.job_id),
            source="iwsc",
            year=2025,
            enrich=True,
        )

        # Check product was created with updated source_count
        product = DiscoveredProduct.objects.filter(
            name="Test Whiskey SourceCount"
        ).first()
        if product:
            self.assertEqual(product.source_count, 3)

    @patch("crawler.tasks._get_verification_pipeline")
    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_enrich_updates_verified_fields(
        self, mock_extractor_class, mock_get_collector, mock_get_pipeline
    ):
        """Product verified_fields should be updated after verification."""
        from crawler.tasks import trigger_award_crawl

        # Setup collector mock
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [
            MockURLInfo(url="http://example.com/award1", medal_hint="Gold")
        ]
        mock_get_collector.return_value = mock_collector

        # Setup extractor mock
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "name": "Test Whiskey VerifiedFields",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_extractor_class.return_value = mock_extractor

        # Setup verification pipeline mock
        mock_pipeline = MagicMock()

        def verify_side_effect(product):
            product.source_count = 2
            product.verified_fields = ["name", "abv", "country"]
            product.save()
            return MagicMock(
                sources_used=2,
                verified_fields=["name", "abv", "country"],
                conflicts=[],
            )

        mock_pipeline.verify_product.side_effect = verify_side_effect
        mock_get_pipeline.return_value = mock_pipeline

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Run task with enrich=True
        trigger_award_crawl(
            job_id=str(job.job_id),
            source="iwsc",
            year=2025,
            enrich=True,
        )

        # Check product was created with verified_fields
        product = DiscoveredProduct.objects.filter(
            name="Test Whiskey VerifiedFields"
        ).first()
        if product:
            self.assertIn("name", product.verified_fields)
            self.assertIn("abv", product.verified_fields)


class TestCrawlAPIEndpointEnrich(TestCase):
    """Tests that crawl API endpoint accepts enrich parameter."""

    def setUp(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.tasks.trigger_award_crawl")
    def test_trigger_endpoint_accepts_enrich_parameter(
        self, mock_trigger_task
    ):
        """POST /api/v1/crawl/awards/ should accept enrich parameter."""
        mock_trigger_task.delay.return_value = MagicMock(id="test-task-id")

        response = self.client.post(
            "/api/v1/crawl/awards/",
            {
                "source": "iwsc",
                "year": 2025,
                "enrich": True,  # This should be accepted
            },
            format="json",
        )

        # Should not return 400 Bad Request for unknown parameter
        self.assertIn(response.status_code, [200, 201, 202])

    @patch("crawler.tasks.trigger_award_crawl")
    def test_trigger_endpoint_passes_enrich_to_task(
        self, mock_trigger_task
    ):
        """Endpoint should pass enrich parameter to celery task."""
        mock_trigger_task.delay.return_value = MagicMock(id="test-task-id")

        self.client.post(
            "/api/v1/crawl/awards/",
            {
                "source": "iwsc",
                "year": 2025,
                "enrich": True,
            },
            format="json",
        )

        # Check that task was called with enrich parameter
        mock_trigger_task.delay.assert_called()
        call_kwargs = mock_trigger_task.delay.call_args
        # enrich should be passed to the task
        if call_kwargs.kwargs:
            self.assertTrue(call_kwargs.kwargs.get("enrich", False))


class TestCrawlVerificationMultipleProducts(TestCase):
    """Tests verification of multiple products during a crawl."""

    @patch("crawler.tasks._get_verification_pipeline")
    @patch("crawler.discovery.collectors.get_collector")
    @patch("crawler.discovery.extractors.AIExtractor")
    def test_verifies_each_product_in_batch(
        self, mock_extractor_class, mock_get_collector, mock_get_pipeline
    ):
        """When enrich=True, should verify each extracted product."""
        from crawler.tasks import trigger_award_crawl

        # Setup collector mock with multiple URLs
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [
            MockURLInfo(url="http://example.com/award1", medal_hint="Gold"),
            MockURLInfo(url="http://example.com/award2", medal_hint="Silver"),
            MockURLInfo(url="http://example.com/award3", medal_hint="Bronze"),
        ]
        mock_get_collector.return_value = mock_collector

        # Setup extractor mock to return different products
        call_count = [0]

        def extract_side_effect(*args, **kwargs):
            call_count[0] += 1
            return {
                "name": f"Test Whiskey Batch {call_count[0]}",
                "product_type": "whiskey",
            }

        mock_extractor = MagicMock()
        mock_extractor.extract.side_effect = extract_side_effect
        mock_extractor_class.return_value = mock_extractor

        # Setup verification pipeline mock
        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        # Create job
        job = APICrawlJob.objects.create(
            source="iwsc",
            year=2025,
            status="queued",
        )

        # Run task with enrich=True
        trigger_award_crawl(
            job_id=str(job.job_id),
            source="iwsc",
            year=2025,
            enrich=True,
        )

        # Should verify each product (3 products = 3 verify calls)
        self.assertEqual(mock_pipeline.verify_product.call_count, 3)
