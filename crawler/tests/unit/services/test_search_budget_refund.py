"""
Unit tests for Search Budget Refund.

Task 4.3: Implement Search Budget Refund

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4.2

Tests verify:
- Budget decremented then refunded on members-only
- members_only_sites_detected populated
- Remaining budget correct after refund
"""

import time
from unittest.mock import MagicMock, patch, AsyncMock

from django.test import TestCase

from crawler.services.enrichment_orchestrator_v3 import (
    EnrichmentOrchestratorV3,
    EnrichmentSession,
)


class BudgetRefundOnMembersOnlyTests(TestCase):
    """Tests for budget refund when members-only detected."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_refund_search_budget_method_exists(self):
        """Test _refund_search_budget method exists."""
        self.assertTrue(hasattr(self.orchestrator, '_refund_search_budget'))

    def test_refund_decrements_searches_performed(self):
        """Test refund decrements searches_performed count."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3

        self.orchestrator._refund_search_budget(session, "https://smws.com/tasting")

        self.assertEqual(session.searches_performed, 2)

    def test_refund_does_not_go_below_zero(self):
        """Test refund doesn't make searches_performed negative."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 0

        self.orchestrator._refund_search_budget(session, "https://smws.com/tasting")

        self.assertEqual(session.searches_performed, 0)

    def test_refund_adds_to_members_only_detected(self):
        """Test refund adds URL to members_only_sites_detected."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )

        self.orchestrator._refund_search_budget(session, "https://smws.com/tasting")

        self.assertIn("https://smws.com/tasting", session.members_only_sites_detected)

    def test_multiple_refunds_tracked(self):
        """Test multiple members-only sites are tracked."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3

        self.orchestrator._refund_search_budget(session, "https://smws.com/tasting1")
        self.orchestrator._refund_search_budget(session, "https://smws.com/tasting2")

        self.assertEqual(session.searches_performed, 1)
        self.assertEqual(len(session.members_only_sites_detected), 2)


class MembersOnlySitesDetectedTests(TestCase):
    """Tests for members_only_sites_detected tracking."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_session_has_members_only_sites_detected_field(self):
        """Test EnrichmentSession has members_only_sites_detected field."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )

        self.assertTrue(hasattr(session, 'members_only_sites_detected'))
        self.assertEqual(session.members_only_sites_detected, [])

    def test_members_only_sites_preserved_in_session(self):
        """Test members-only sites are preserved throughout session."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.members_only_sites_detected.append("https://smws.com")
        session.members_only_sites_detected.append("https://club.com")

        self.assertEqual(len(session.members_only_sites_detected), 2)
        self.assertIn("https://smws.com", session.members_only_sites_detected)
        self.assertIn("https://club.com", session.members_only_sites_detected)


class RemainingBudgetTests(TestCase):
    """Tests for remaining budget calculations after refunds."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_remaining_searches_after_refund(self):
        """Test remaining searches calculated correctly after refund."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 4
        session.start_time = time.time()

        # Refund one search
        self.orchestrator._refund_search_budget(session, "https://smws.com")

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        # 3 searches performed, 6 max = not exceeded
        self.assertFalse(exceeded)

    def test_budget_not_exceeded_after_refund(self):
        """Test budget not exceeded after refund when at limit."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 6  # At limit
        session.start_time = time.time()

        # Refund one search
        self.orchestrator._refund_search_budget(session, "https://smws.com")

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        # Now at 5, under limit
        self.assertFalse(exceeded)

    def test_get_remaining_budget_method(self):
        """Test _get_remaining_budget returns correct values."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 2
        session.sources_used = ["url1", "url2", "url3"]
        session.start_time = time.time()

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}

        remaining = self.orchestrator._get_remaining_budget(session, limits)

        self.assertEqual(remaining["searches"], 4)  # 6 - 2
        self.assertEqual(remaining["sources"], 5)  # 8 - 3


class IntegrationWithMembersOnlyDetectorTests(TestCase):
    """Tests for integration with MembersOnlyDetector."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_check_and_refund_if_members_only(self, mock_get_detector):
        """Test _check_and_refund_if_members_only method."""
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

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_no_refund_when_not_members_only(self, mock_get_detector):
        """Test no refund when content is not members-only."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = False
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3

        result = self.orchestrator._check_and_refund_if_members_only(
            session,
            url="https://whiskybase.com/review",
            content="<html>Normal review content</html>",
            status_code=200
        )

        self.assertFalse(result)
        self.assertEqual(session.searches_performed, 3)
        self.assertEqual(len(session.members_only_sites_detected), 0)

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_refund_on_401_status(self, mock_get_detector):
        """Test refund on HTTP 401 status."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = True
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 2

        result = self.orchestrator._check_and_refund_if_members_only(
            session,
            url="https://members.site/content",
            content="",
            status_code=401
        )

        self.assertTrue(result)
        self.assertEqual(session.searches_performed, 1)
