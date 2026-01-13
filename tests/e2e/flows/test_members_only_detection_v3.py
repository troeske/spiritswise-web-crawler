"""
E2E tests for Members-Only Site Detection V3.

Task 5.3: E2E Test - Members-Only Detection (SMWS)

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4.2

Tests verify:
- SMWS brand triggers detection
- Search budget refunded
- Tasting notes still extracted from review sites
"""

import time
from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.services.enrichment_orchestrator_v3 import (
    EnrichmentOrchestratorV3,
    EnrichmentSession,
)
from crawler.services.members_only_detector import MembersOnlyDetector


class SMWSDetectionTests(TestCase):
    """Tests for SMWS (Scotch Malt Whisky Society) detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_detects_smws_login_page(self):
        """Test SMWS login page is detected as members-only."""
        content = '''
        <html>
            <h1>SMWS Members Area</h1>
            <form action="/members/login" method="POST">
                <input type="text" name="email" placeholder="Email">
                <input type="password" name="password" placeholder="Password">
                <button type="submit">Sign In</button>
            </form>
            <p>Log in to access exclusive tasting notes</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_smws_member_exclusive(self):
        """Test SMWS member exclusive content is detected."""
        content = '''
        <html>
            <h1>Cask No. 1.292</h1>
            <p>Member Exclusive - Tasting Notes</p>
            <p>Join the Society to access full details.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_does_not_detect_normal_whisky_page(self):
        """Test normal whisky review page is not detected."""
        content = '''
        <html>
            <h1>SMWS 1.292 Review</h1>
            <p>Rating: 92/100</p>
            <p>Tasting notes: Honey, smoke, and citrus with a long finish.</p>
            <p>This bottling from Glenfarclas is excellent.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)


class BudgetRefundOnSMWSTests(TestCase):
    """Tests for budget refund when SMWS site detected."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_budget_refunded_on_smws_detection(self, mock_get_detector):
        """Test search budget is refunded when SMWS detected."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = True
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "SMWS 1.292", "brand": "SMWS"},
            product_type="whiskey"
        )
        session.searches_performed = 3
        session.start_time = time.time()

        result = self.orchestrator._check_and_refund_if_members_only(
            session,
            url="https://smws.com/cask/1.292",
            content="<html>Members Only</html>",
            status_code=200
        )

        self.assertTrue(result)
        self.assertEqual(session.searches_performed, 2)  # Refunded

    def test_smws_url_tracked_in_session(self):
        """Test SMWS URL is tracked in members_only_sites_detected."""
        session = EnrichmentSession(
            initial_data={"name": "SMWS 1.292", "brand": "SMWS"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector') as mock_get:
            mock_detector = MagicMock()
            mock_detector.check_response.return_value = True
            mock_get.return_value = mock_detector

            self.orchestrator._check_and_refund_if_members_only(
                session,
                url="https://smws.com/cask/1.292",
                content="<html>Members Only</html>",
                status_code=200
            )

        self.assertIn("https://smws.com/cask/1.292", session.members_only_sites_detected)


class ReviewSiteFallbackTests(TestCase):
    """Tests for fallback to review sites when members-only detected."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_whiskybase_not_members_only(self):
        """Test Whiskybase review page is not members-only."""
        content = '''
        <html>
            <h1>SMWS 1.292 - Speyside Review</h1>
            <div class="rating">Score: 87/100</div>
            <div class="tasting">
                <h3>Tasting Notes</h3>
                <p>Nose: Honey, vanilla, light smoke</p>
                <p>Palate: Rich malt, dried fruits</p>
                <p>Finish: Long, warming</p>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)

    def test_master_of_malt_not_members_only(self):
        """Test Master of Malt product page is not members-only."""
        content = '''
        <html>
            <h1>SMWS 1.292</h1>
            <div class="product-info">
                <p>ABV: 56.8%</p>
                <p>Size: 700ml</p>
            </div>
            <div class="product-description">
                <p>A beautiful Speyside single malt from cask #292...</p>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)


class HTTPStatusDetectionTests(TestCase):
    """Tests for HTTP status code detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_401_triggers_refund(self, mock_get_detector):
        """Test HTTP 401 triggers budget refund."""
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
            url="https://members.site/page",
            content="",
            status_code=401
        )

        self.assertTrue(result)
        self.assertEqual(session.searches_performed, 1)

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_403_triggers_refund(self, mock_get_detector):
        """Test HTTP 403 triggers budget refund."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = True
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 4

        result = self.orchestrator._check_and_refund_if_members_only(
            session,
            url="https://restricted.site/page",
            content="",
            status_code=403
        )

        self.assertTrue(result)
        self.assertEqual(session.searches_performed, 3)


class MultipleRefundsTests(TestCase):
    """Tests for handling multiple members-only sites."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    @patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector')
    def test_multiple_sites_tracked(self, mock_get_detector):
        """Test multiple members-only sites are tracked."""
        mock_detector = MagicMock()
        mock_detector.check_response.return_value = True
        mock_get_detector.return_value = mock_detector

        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 5

        # First site
        self.orchestrator._check_and_refund_if_members_only(
            session, "https://smws.com/page1", "Members Only", 200
        )
        # Second site
        self.orchestrator._check_and_refund_if_members_only(
            session, "https://club.com/page2", "Login Required", 200
        )

        self.assertEqual(session.searches_performed, 3)  # 5 - 2
        self.assertEqual(len(session.members_only_sites_detected), 2)
        self.assertIn("https://smws.com/page1", session.members_only_sites_detected)
        self.assertIn("https://club.com/page2", session.members_only_sites_detected)
