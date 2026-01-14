"""
Tests for Escalation Heuristics.

Task Group: Phase 2 - Heuristic Escalation Triggers
Spec Reference: DYNAMIC_SITE_ADAPTATION_TASKS.md

These tests verify the heuristics for detecting when to escalate
from a lower tier to a higher tier based on response characteristics.
"""

import pytest
from unittest.mock import MagicMock


class TestEscalationHeuristics:
    """Tests for EscalationHeuristics class (Task 2.1)."""

    def test_escalate_on_403(self):
        """403 status triggers immediate escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=403,
            content="Forbidden",
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "403" in result.reason or "forbidden" in result.reason.lower()

    def test_escalate_on_429(self):
        """429 rate limit triggers escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=429,
            content="Too Many Requests",
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "429" in result.reason or "rate" in result.reason.lower()

    def test_escalate_on_cloudflare(self):
        """Cloudflare challenge page triggers escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        cloudflare_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Just a moment...</title></head>
        <body>
        <div>Checking your browser before accessing example.com</div>
        <noscript>Please enable JavaScript</noscript>
        </body>
        </html>
        """

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=cloudflare_content,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "cloudflare" in result.reason.lower()

    def test_escalate_on_captcha(self):
        """CAPTCHA page triggers escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        captcha_content = """
        <!DOCTYPE html>
        <html>
        <body>
        <div class="g-recaptcha" data-sitekey="xxx"></div>
        <form><input type="hidden" name="captcha"></form>
        </body>
        </html>
        """

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=captcha_content,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "captcha" in result.reason.lower()

    def test_escalate_on_js_placeholder(self):
        """JS framework placeholder triggers escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        react_placeholder = """
        <!DOCTYPE html>
        <html>
        <head><title>React App</title></head>
        <body>
        <div id="root"></div>
        <script src="/static/js/main.js"></script>
        </body>
        </html>
        """

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=react_placeholder,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "javascript" in result.reason.lower() or "js" in result.reason.lower()

    def test_escalate_on_low_success_rate(self):
        """Domain with <50% tier success triggers escalation."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        profile = MagicMock()
        profile.tier1_success_rate = 0.3  # 30% - below 50% threshold

        # Use content that's long enough to not trigger empty/loading detection
        good_content = """
        <html>
        <head><title>Product Page</title></head>
        <body>
        <h1>Ardbeg 10 Year Old</h1>
        <p>A classic Islay single malt whisky with a rich, smoky character.
        This expression showcases the classic Ardbeg profile with intense peat smoke,
        balanced by citrus and vanilla notes. The finish is long and complex.</p>
        <div class="product-details">
            <span>ABV: 46%</span>
            <span>Region: Islay</span>
        </div>
        </body>
        </html>
        """

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=good_content,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is True
        assert "success rate" in result.reason.lower()

    def test_no_escalate_on_success(self):
        """Successful fetch with content doesn't escalate."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        good_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Ardbeg 10 Year Old | WhiskyBase</title></head>
        <body>
        <h1>Ardbeg 10 Year Old</h1>
        <p>A classic Islay single malt with smoky, peaty character.</p>
        <div class="product-details">
            <span>ABV: 46%</span>
            <span>Region: Islay</span>
        </div>
        </body>
        </html>
        """

        profile = MagicMock()
        profile.tier1_success_rate = 0.9

        result = EscalationHeuristics.should_escalate(
            status_code=200,
            content=good_content,
            domain_profile=profile,
            current_tier=1,
        )

        assert result.should_escalate is False
        assert result.reason is None

    def test_returns_reason(self):
        """Escalation returns machine-readable reason."""
        from crawler.fetchers.escalation_heuristics import (
            EscalationHeuristics,
            EscalationResult,
        )

        profile = MagicMock()
        profile.tier1_success_rate = 1.0

        result = EscalationHeuristics.should_escalate(
            status_code=403,
            content="Forbidden",
            domain_profile=profile,
            current_tier=1,
        )

        # Result should be structured
        assert isinstance(result, EscalationResult)
        assert result.should_escalate is True
        assert result.reason is not None
        assert isinstance(result.reason, str)

    def test_no_escalate_from_tier3(self):
        """Can't escalate beyond tier 3."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        profile = MagicMock()
        profile.tier3_success_rate = 0.1  # Low success rate

        result = EscalationHeuristics.should_escalate(
            status_code=403,
            content="Forbidden",
            domain_profile=profile,
            current_tier=3,
        )

        # Even with escalation triggers, can't go beyond tier 3
        assert result.should_escalate is False


class TestCloudflareDetection:
    """Tests for Cloudflare challenge detection (Task 2.2)."""

    def test_detect_cloudflare_browser_check(self):
        """Detects 'Checking your browser' page."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "Checking your browser before accessing example.com"
        assert EscalationHeuristics.is_cloudflare_challenge(content) is True

    def test_detect_cloudflare_just_a_moment(self):
        """Detects 'Just a moment...' title."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "<title>Just a moment...</title>"
        assert EscalationHeuristics.is_cloudflare_challenge(content) is True

    def test_detect_cloudflare_cf_chl(self):
        """Detects cf_chl challenge token."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<input type="hidden" name="cf_chl_opt" value="xxx">'
        assert EscalationHeuristics.is_cloudflare_challenge(content) is True

    def test_no_cloudflare_on_normal_page(self):
        """Normal page is not flagged as Cloudflare."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "<html><body><h1>Welcome to our site</h1></body></html>"
        assert EscalationHeuristics.is_cloudflare_challenge(content) is False


class TestCaptchaDetection:
    """Tests for CAPTCHA page detection (Task 2.2)."""

    def test_detect_recaptcha(self):
        """Detects Google reCAPTCHA."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<div class="g-recaptcha" data-sitekey="xxx"></div>'
        assert EscalationHeuristics.is_captcha_page(content) is True

    def test_detect_hcaptcha(self):
        """Detects hCaptcha."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<div class="h-captcha" data-sitekey="xxx"></div>'
        assert EscalationHeuristics.is_captcha_page(content) is True

    def test_detect_captcha_form_field(self):
        """Detects captcha form field."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<input type="hidden" name="captcha_token">'
        assert EscalationHeuristics.is_captcha_page(content) is True

    def test_no_captcha_on_normal_page(self):
        """Normal page is not flagged as CAPTCHA."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "<html><body><form><input type='text' name='search'></form></body></html>"
        assert EscalationHeuristics.is_captcha_page(content) is False


class TestJavaScriptPlaceholderDetection:
    """Tests for JS framework placeholder detection (Task 2.2)."""

    def test_detect_react_root(self):
        """Detects React empty root div."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<div id="root"></div>'
        assert EscalationHeuristics.is_javascript_placeholder(content) is True

    def test_detect_vue_app(self):
        """Detects Vue empty app div."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<div id="app"></div>'
        assert EscalationHeuristics.is_javascript_placeholder(content) is True

    def test_detect_angular_root(self):
        """Detects Angular app-root element."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = '<app-root></app-root>'
        assert EscalationHeuristics.is_javascript_placeholder(content) is True

    def test_detect_noscript_required(self):
        """Detects noscript message requiring JS."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "<noscript>You need to enable JavaScript to run this app.</noscript>"
        assert EscalationHeuristics.is_javascript_placeholder(content) is True

    def test_no_placeholder_with_content(self):
        """Page with real content is not flagged as placeholder."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = """
        <html>
        <body>
        <div id="root">
            <h1>Ardbeg 10 Year Old</h1>
            <p>Description of the whisky...</p>
        </div>
        </body>
        </html>
        """
        assert EscalationHeuristics.is_javascript_placeholder(content) is False


class TestEmptyOrLoadingDetection:
    """Tests for empty/loading page detection."""

    def test_detect_empty_body(self):
        """Detects empty body tag."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = "<html><head></head><body></body></html>"
        assert EscalationHeuristics.is_empty_or_loading(content) is True

    def test_detect_loading_spinner(self):
        """Detects loading spinner only."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = """
        <html><body>
        <div class="loading-spinner"></div>
        </body></html>
        """
        assert EscalationHeuristics.is_empty_or_loading(content) is True

    def test_not_empty_with_content(self):
        """Page with real content is not flagged as empty."""
        from crawler.fetchers.escalation_heuristics import EscalationHeuristics

        content = """
        <html><body>
        <h1>Product Title</h1>
        <p>This is a description with meaningful content about the product.</p>
        </body></html>
        """
        assert EscalationHeuristics.is_empty_or_loading(content) is False
