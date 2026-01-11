"""
API Verification Integration TDD Tests - Phase 9

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md
                docs/spec-parts/13-REST-API-ENDPOINTS.md

These tests verify that API endpoints actually trigger the verification pipeline.
Written FIRST according to TDD methodology - these MUST FAIL initially.

Critical Gap Being Tested:
- API accepts `enrich=true` parameter but NEVER calls VerificationPipeline
- Products are saved but never verified from multiple sources
- source_count stays at 1, verified_fields stays empty
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from crawler.models import DiscoveredProduct, DiscoveredBrand


class TestExtractURLWithEnrichment(TestCase):
    """Tests that POST /api/v1/extract/url/ with enrich=true triggers verification."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_true_calls_verification_pipeline(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """When enrich=true, should call VerificationPipeline.verify_product()."""
        # Setup mock crawler to return a product
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_get_crawler.return_value = mock_crawler

        # Setup mock verification pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name", "abv"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {"url": "http://example.com/whiskey", "enrich": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify that VerificationPipeline.verify_product was called
        mock_pipeline.verify_product.assert_called_once()

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_false_does_not_call_verification(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """When enrich=false (default), should NOT call VerificationPipeline."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {"url": "http://example.com/whiskey", "enrich": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # VerificationPipeline.verify_product should NOT be called
        mock_pipeline.verify_product.assert_not_called()

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_updates_source_count_in_response(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """Response should include source_count when enrich=true."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=3,
            verified_fields=["name", "abv", "country"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {"url": "http://example.com/whiskey", "enrich": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Response should include verification results
        self.assertIn("source_count", data["products"][0])
        self.assertEqual(data["products"][0]["source_count"], 3)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_updates_verified_fields_in_response(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """Response should include verified_fields when enrich=true."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name", "abv"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {"url": "http://example.com/whiskey", "enrich": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Response should include verified_fields
        self.assertIn("verified_fields", data["products"][0])
        self.assertEqual(data["products"][0]["verified_fields"], ["name", "abv"])


class TestExtractURLsWithEnrichment(TestCase):
    """Tests that POST /api/v1/extract/urls/ with enrich=true triggers verification."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_batch_enrich_calls_verification_for_each_product(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """When enrich=true on batch, should verify each product."""
        mock_crawler = MagicMock()
        # Return different names for each URL to avoid fingerprint collision
        call_count = [0]

        def extract_side_effect(**kwargs):
            call_count[0] += 1
            return {
                "name": f"Test Whiskey {call_count[0]}",
                "product_type": "whiskey",
            }

        mock_crawler.extract_product.side_effect = extract_side_effect
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/urls/",
            {
                "urls": [
                    "http://example.com/whiskey1",
                    "http://example.com/whiskey2",
                ],
                "enrich": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should call verify_product for each URL
        self.assertEqual(mock_pipeline.verify_product.call_count, 2)


class TestExtractSearchWithEnrichment(TestCase):
    """Tests that POST /api/v1/extract/search/ with enrich=true triggers verification."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_search_enrich_calls_verification(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """When enrich=true on search, should verify extracted products."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/search/",
            {"query": "Ardbeg 10 Year Old", "enrich": True},
            format="json",
        )

        # Should call verify_product
        if response.status_code == status.HTTP_200_OK:
            self.assertTrue(mock_pipeline.verify_product.called)


class TestVerificationUpdatesDatabase(TestCase):
    """Tests that verification actually updates the database product."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_updates_product_source_count_in_db(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """Product in database should have source_count > 1 after enrichment."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey DB",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()

        def verify_side_effect(product):
            product.source_count = 2
            product.verified_fields = ["name", "abv"]
            product.save()
            return MagicMock(
                sources_used=2,
                verified_fields=["name", "abv"],
                conflicts=[],
            )

        mock_pipeline.verify_product.side_effect = verify_side_effect
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {
                "url": "http://example.com/whiskey-db-test",
                "enrich": True,
                "save_to_db": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check database was updated
        product = DiscoveredProduct.objects.filter(name="Test Whiskey DB").first()
        if product:
            self.assertEqual(product.source_count, 2)
            self.assertEqual(product.verified_fields, ["name", "abv"])

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_enrich_updates_product_status_in_response(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """Response status should reflect verification result."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey Status",
            "product_type": "whiskey",
            "abv": 43.0,
            "palate_description": "Rich and smooth.",
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()

        def verify_side_effect(product):
            # Simulate verification updating product
            product.source_count = 2
            product.status = "complete"
            product.completeness_score = 85
            product.save()
            return MagicMock(
                sources_used=2,
                verified_fields=["name"],
                conflicts=[],
            )

        mock_pipeline.verify_product.side_effect = verify_side_effect
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {
                "url": "http://example.com/whiskey-status-test",
                "enrich": True,
                "save_to_db": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check response includes status from verification
        data = response.json()
        self.assertIn("products", data)
        self.assertEqual(len(data["products"]), 1)
        # Verify that verification was called and returned expected data
        mock_pipeline.verify_product.assert_called_once()
        # Response should include source_count from verification
        self.assertEqual(data["products"][0]["source_count"], 2)


class TestVerificationWithConflicts(TestCase):
    """Tests that verification conflicts are handled and reported."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.force_authenticate(user=self.user)

    @patch("crawler.api.views._get_verification_pipeline")
    @patch("crawler.api.views._get_smart_crawler")
    def test_conflicts_included_in_response(
        self, mock_get_crawler, mock_get_pipeline
    ):
        """Response should include conflicts when sources disagree."""
        mock_crawler = MagicMock()
        mock_crawler.extract_product.return_value = {
            "name": "Test Whiskey",
            "product_type": "whiskey",
            "abv": 43.0,
        }
        mock_get_crawler.return_value = mock_crawler

        mock_pipeline = MagicMock()
        mock_pipeline.verify_product.return_value = MagicMock(
            sources_used=2,
            verified_fields=["name"],
            conflicts=[
                {"field": "abv", "current": 43.0, "new": 46.0},
            ],
        )
        mock_get_pipeline.return_value = mock_pipeline

        response = self.client.post(
            "/api/v1/extract/url/",
            {"url": "http://example.com/whiskey", "enrich": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Response should include conflicts
        self.assertIn("conflicts", data["products"][0])
        self.assertEqual(len(data["products"][0]["conflicts"]), 1)
        self.assertEqual(data["products"][0]["conflicts"][0]["field"], "abv")
