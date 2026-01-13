"""
Unit tests for Members-Only Site Detection.

Task 4.2: Implement Members-Only Site Detection

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4.2

Tests verify:
- Login form detection
- "members only" text detection
- Paywall indicator detection
- HTTP 401/403/402 handling
"""

from django.test import TestCase

from crawler.services.members_only_detector import MembersOnlyDetector


class LoginFormDetectionTests(TestCase):
    """Tests for login form detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_login_form(self):
        """Test detects form with login action."""
        content = '''
        <html>
            <form action="/login" method="POST">
                <input type="text" name="username">
                <input type="password" name="password">
                <button type="submit">Sign In</button>
            </form>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_password_input(self):
        """Test detects password input field."""
        content = '''
        <html>
            <form>
                <input type="password" name="pwd">
            </form>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_sign_in_to_view(self):
        """Test detects 'sign in to view' text."""
        content = '''
        <html>
            <div class="restricted">
                <p>Please sign in to view this content</p>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_sign_in_to_access(self):
        """Test detects 'sign in to access' text."""
        content = '''
        <html>
            <p>Sign in to access exclusive tasting notes.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)


class MembershipLanguageDetectionTests(TestCase):
    """Tests for membership language detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_members_only(self):
        """Test detects 'members only' text."""
        content = '''
        <html>
            <div class="members-only">
                This content is for members only.
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_member_exclusive(self):
        """Test detects 'member exclusive' text."""
        content = '''
        <html>
            <p>Member Exclusive: Full tasting notes available</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_join_now_to_access(self):
        """Test detects 'join now to access' text."""
        content = '''
        <html>
            <div>Join Now to access premium content!</div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_subscription_required(self):
        """Test detects 'subscription required' text."""
        content = '''
        <html>
            <p>Subscription Required</p>
            <p>This article requires an active subscription.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)


class PaywallDetectionTests(TestCase):
    """Tests for paywall indicator detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_paywall_class(self):
        """Test detects paywall in class name."""
        content = '''
        <html>
            <div class="paywall">
                <p>This content is behind a paywall</p>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_premium_content(self):
        """Test detects 'premium content' text."""
        content = '''
        <html>
            <div>Premium Content - Subscribe to Read</div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_unlock_content(self):
        """Test detects 'unlock this content' text."""
        content = '''
        <html>
            <p>Unlock this content for $9.99/month</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_unlock_full_article(self):
        """Test detects 'unlock full article' text."""
        content = '''
        <html>
            <button>Unlock Full Article</button>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)


class AccessDeniedDetectionTests(TestCase):
    """Tests for access denied detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_access_denied(self):
        """Test detects 'access denied' text."""
        content = '''
        <html>
            <h1>Access Denied</h1>
            <p>You do not have permission to view this page.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_restricted_area(self):
        """Test detects 'restricted area' text."""
        content = '''
        <html>
            <div class="error">Restricted Area - Login Required</div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_authentication_required(self):
        """Test detects 'authentication required' text."""
        content = '''
        <html>
            <p>Authentication Required. Please log in.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)


class HTTPCodeDetectionTests(TestCase):
    """Tests for HTTP code handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_401_unauthorized(self):
        """Test 401 status code triggers detection."""
        result = self.detector.is_members_only_http_code(401)

        self.assertTrue(result)

    def test_detects_403_forbidden(self):
        """Test 403 status code triggers detection."""
        result = self.detector.is_members_only_http_code(403)

        self.assertTrue(result)

    def test_detects_402_payment_required(self):
        """Test 402 status code triggers detection."""
        result = self.detector.is_members_only_http_code(402)

        self.assertTrue(result)

    def test_200_is_not_members_only(self):
        """Test 200 status code is not members-only."""
        result = self.detector.is_members_only_http_code(200)

        self.assertFalse(result)

    def test_404_is_not_members_only(self):
        """Test 404 status code is not members-only."""
        result = self.detector.is_members_only_http_code(404)

        self.assertFalse(result)

    def test_500_is_not_members_only(self):
        """Test 500 status code is not members-only."""
        result = self.detector.is_members_only_http_code(500)

        self.assertFalse(result)


class NegativeDetectionTests(TestCase):
    """Tests for content that should NOT trigger detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_normal_product_page_not_detected(self):
        """Test normal product page is not detected as members-only."""
        content = '''
        <html>
            <h1>Highland Park 18 Year Old</h1>
            <p>A complex single malt with notes of heather honey and peat smoke.</p>
            <p>ABV: 43%</p>
            <p>Price: $150</p>
            <div class="tasting-notes">
                <h2>Tasting Notes</h2>
                <p>Nose: Honey, smoke, citrus</p>
                <p>Palate: Rich, full-bodied</p>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)

    def test_review_page_not_detected(self):
        """Test normal review page is not detected as members-only."""
        content = '''
        <html>
            <h1>Whiskey Review: Lagavulin 16</h1>
            <p>Rating: 92/100</p>
            <p>This Islay single malt is a benchmark for peated whisky...</p>
            <form action="/newsletter" method="POST">
                <input type="email" placeholder="Subscribe to our newsletter">
                <button>Subscribe</button>
            </form>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)

    def test_search_page_not_detected(self):
        """Test search results page is not detected as members-only."""
        content = '''
        <html>
            <h1>Search Results</h1>
            <div class="results">
                <div class="result">
                    <a href="/product/1">Highland Park 18</a>
                </div>
                <div class="result">
                    <a href="/product/2">Lagavulin 16</a>
                </div>
            </div>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertFalse(result)

    def test_empty_content_not_detected(self):
        """Test empty content is not detected as members-only."""
        result = self.detector.is_members_only("")

        self.assertFalse(result)

    def test_none_content_not_detected(self):
        """Test None content is not detected as members-only."""
        result = self.detector.is_members_only(None)

        self.assertFalse(result)


class SMWSSpecificTests(TestCase):
    """Tests for SMWS (Scotch Malt Whisky Society) specific patterns."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = MembersOnlyDetector()

    def test_detects_smws_login_page(self):
        """Test detects SMWS login page."""
        content = '''
        <html>
            <h1>Welcome to SMWS</h1>
            <p>Log in to access your member tasting notes.</p>
            <form action="/members/login" method="POST">
                <input type="text" name="email">
                <input type="password" name="password">
                <button>Sign In</button>
            </form>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)

    def test_detects_smws_member_exclusive(self):
        """Test detects SMWS member exclusive content."""
        content = '''
        <html>
            <h1>Cask No. 1.292</h1>
            <p>Member Exclusive - Tasting Notes</p>
            <p>Join now to access detailed tasting notes.</p>
        </html>
        '''

        result = self.detector.is_members_only(content)

        self.assertTrue(result)
