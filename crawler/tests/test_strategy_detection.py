"""
Tests for Crawl Strategy Auto-Detection.

Task Group 30: Crawl Strategy Auto-Detection
These tests verify the obstacle detection and escalation workflow functionality.

Tests focus on:
- Age gate detection
- JS-rendered content detection
- CAPTCHA detection
- Escalation workflow
"""

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from crawler.models import (
    DiscoverySourceConfig,
    CrawledSource,
    CrawlStrategyChoices,
)
from crawler.services.strategy_detection import (
    ObstacleType,
    detect_obstacles,
    StrategyEscalationService,
)
from crawler.services.scrapingbee_client import ScrapingBeeClient, ScrapingBeeMode


class ObstacleDetectionAgeGateTestCase(TestCase):
    """Test age gate detection patterns."""

    def test_detect_age_gate_verify_your_age(self):
        """Test detection of 'verify your age' age gate pattern."""
        html_content = """
        <html>
        <body>
            <div class="age-gate">
                <h2>Please verify your age</h2>
                <button>I am 21 or older</button>
            </div>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.AGE_GATE, [o.obstacle_type for o in obstacles])
        age_gate = next(o for o in obstacles if o.obstacle_type == ObstacleType.AGE_GATE)
        self.assertIn("verify your age", age_gate.detected_pattern.lower())

    def test_detect_age_gate_21_plus(self):
        """Test detection of '21+' age gate pattern."""
        html_content = """
        <html>
        <body>
            <div id="modal">
                <p>You must be 21+ to enter this site</p>
                <button id="enter">Enter</button>
            </div>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.AGE_GATE, [o.obstacle_type for o in obstacles])

    def test_detect_age_gate_legal_drinking_age(self):
        """Test detection of 'legal drinking age' pattern."""
        html_content = """
        <html>
        <body>
            <div class="age-verification">
                <h1>Are you of legal drinking age?</h1>
                <button>Yes, I am</button>
                <button>No</button>
            </div>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.AGE_GATE, [o.obstacle_type for o in obstacles])


class ObstacleDetectionJSRenderedTestCase(TestCase):
    """Test JS-rendered content detection."""

    def test_detect_js_rendered_short_content(self):
        """Test detection of JS-rendered content by short content length."""
        # Content less than threshold (e.g., 500 chars) indicates JS rendering needed
        html_content = "<html><body><div id='app'></div></body></html>"

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.JS_RENDERED, [o.obstacle_type for o in obstacles])

    def test_detect_js_rendered_missing_expected_elements(self):
        """Test detection when expected product elements are missing."""
        html_content = """
        <html>
        <head><script src="app.js"></script></head>
        <body>
            <div id="root"></div>
            <script>ReactDOM.render()</script>
        </body>
        </html>
        """

        obstacles = detect_obstacles(
            html_content,
            status_code=200,
            expected_elements=["product-name", "product-price"]
        )

        self.assertIn(ObstacleType.JS_RENDERED, [o.obstacle_type for o in obstacles])

    def test_no_js_detection_for_full_content(self):
        """Test that full content does not trigger JS detection."""
        html_content = """
        <html>
        <body>
            <div class="product">
                <h1 class="product-name">Macallan 18 Year</h1>
                <span class="product-price">$299.99</span>
                <p class="description">Rich and complex whisky with notes of
                dried fruits, spice, and oak. Full-bodied with a long finish.
                This exceptional single malt has been aged for 18 years in
                sherry-seasoned oak casks.</p>
            </div>
        </body>
        </html>
        """ * 2  # Make content sufficiently long

        obstacles = detect_obstacles(html_content, status_code=200)

        js_obstacles = [o for o in obstacles if o.obstacle_type == ObstacleType.JS_RENDERED]
        self.assertEqual(len(js_obstacles), 0)


class ObstacleDetectionCAPTCHATestCase(TestCase):
    """Test CAPTCHA detection patterns."""

    def test_detect_captcha_keyword(self):
        """Test detection of CAPTCHA keyword."""
        html_content = """
        <html>
        <body>
            <form>
                <div class="captcha">
                    <img src="/captcha.png" alt="Enter the captcha" />
                    <input name="captcha" />
                </div>
            </form>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.CAPTCHA, [o.obstacle_type for o in obstacles])

    def test_detect_recaptcha_script(self):
        """Test detection of reCAPTCHA script."""
        html_content = """
        <html>
        <head>
            <script src="https://www.google.com/recaptcha/api.js"></script>
        </head>
        <body>
            <div class="g-recaptcha" data-sitekey="abc123"></div>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=200)

        self.assertIn(ObstacleType.CAPTCHA, [o.obstacle_type for o in obstacles])


class ObstacleDetectionRateLimitTestCase(TestCase):
    """Test rate limiting and geo-blocking detection."""

    def test_detect_rate_limit_http_429(self):
        """Test detection of HTTP 429 rate limit status."""
        html_content = "<html><body>Too Many Requests</body></html>"

        obstacles = detect_obstacles(html_content, status_code=429)

        self.assertIn(ObstacleType.RATE_LIMITED, [o.obstacle_type for o in obstacles])

    def test_detect_geo_blocked_http_403(self):
        """Test detection of geo-blocking via HTTP 403."""
        html_content = """
        <html>
        <body>
            <h1>Access Denied</h1>
            <p>This content is not available in your region.</p>
        </body>
        </html>
        """

        obstacles = detect_obstacles(html_content, status_code=403)

        self.assertIn(ObstacleType.GEO_BLOCKED, [o.obstacle_type for o in obstacles])


class EscalationWorkflowTestCase(TestCase):
    """Test the crawl strategy escalation workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.source = DiscoverySourceConfig.objects.create(
            name="Test Source",
            base_url="https://test.com",
            source_type="review_blog",
            crawl_priority=5,
            crawl_frequency="weekly",
            reliability_score=7,
            crawl_strategy=CrawlStrategyChoices.SIMPLE,
        )
        self.escalation_service = StrategyEscalationService()

    def test_escalation_step_1_simple(self):
        """Test that escalation starts with simple strategy."""
        self.assertEqual(
            self.escalation_service.get_strategy_for_step(1),
            CrawlStrategyChoices.SIMPLE
        )

    def test_escalation_step_2_js_render(self):
        """Test that step 2 escalates to js_render."""
        self.assertEqual(
            self.escalation_service.get_strategy_for_step(2),
            CrawlStrategyChoices.JS_RENDER
        )

    def test_escalation_step_3_stealth(self):
        """Test that step 3 escalates to stealth."""
        self.assertEqual(
            self.escalation_service.get_strategy_for_step(3),
            CrawlStrategyChoices.STEALTH
        )

    def test_escalation_step_4_manual(self):
        """Test that step 4 results in manual flagging."""
        self.assertEqual(
            self.escalation_service.get_strategy_for_step(4),
            CrawlStrategyChoices.MANUAL
        )

    def test_escalation_workflow_success_on_simple(self):
        """Test that successful crawl on step 1 (simple) succeeds."""
        # Mock the _simple_crawl method to return valid content
        valid_content = "<html><body><h1>Product</h1>" + "X" * 600 + "</body></html>"

        with patch.object(
            self.escalation_service,
            '_simple_crawl',
            return_value={
                "success": True,
                "content": valid_content,
                "status_code": 200,
            }
        ):
            result = self.escalation_service.escalate_and_crawl(
                url="https://test.com/product",
                source=self.source,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.final_strategy, CrawlStrategyChoices.SIMPLE)
            self.assertEqual(result.escalation_steps, 1)

    def test_escalation_logs_detected_obstacles(self):
        """Test that detected obstacles are logged at each step."""
        # First step: simple crawl returns age gate
        # Second step: mock client returns valid content
        age_gate_content = "<html><body>Please verify your age</body></html>"
        valid_content = "<html><body><h1>Product</h1>" + "X" * 600 + "</body></html>"

        mock_client = MagicMock()
        mock_client.fetch.return_value = {
            "success": True,
            "content": valid_content,
            "status_code": 200,
        }

        with patch.object(
            self.escalation_service,
            '_simple_crawl',
            return_value={
                "success": True,
                "content": age_gate_content,
                "status_code": 200,
            }
        ):
            # Replace the client property to return our mock
            self.escalation_service._client = mock_client

            result = self.escalation_service.escalate_and_crawl(
                url="https://test.com/product",
                source=self.source,
            )

            # Should have detected obstacles
            self.assertIsNotNone(result.detected_obstacles)
            self.assertTrue(len(result.detected_obstacles) > 0)

            # Should have succeeded on step 2 (js_render)
            self.assertTrue(result.success)
            self.assertEqual(result.escalation_steps, 2)


class ScrapingBeeClientInterfaceTestCase(TestCase):
    """Test the ScrapingBee client interface."""

    def test_scrapingbee_mode_js_render(self):
        """Test JS render mode configuration."""
        self.assertEqual(ScrapingBeeMode.JS_RENDER.value, "js_render")

    def test_scrapingbee_mode_stealth(self):
        """Test stealth mode configuration."""
        self.assertEqual(ScrapingBeeMode.STEALTH.value, "stealth")

    def test_scrapingbee_client_instantiation(self):
        """Test ScrapingBee client can be instantiated."""
        client = ScrapingBeeClient(api_key="test_key")
        self.assertIsNotNone(client)

    def test_scrapingbee_client_js_render_params(self):
        """Test that JS render mode sets correct parameters."""
        client = ScrapingBeeClient(api_key="test_key")
        params = client.get_params_for_mode(ScrapingBeeMode.JS_RENDER)

        self.assertTrue(params.get("render_js"))

    def test_scrapingbee_client_stealth_params(self):
        """Test that stealth mode sets correct parameters."""
        client = ScrapingBeeClient(api_key="test_key")
        params = client.get_params_for_mode(ScrapingBeeMode.STEALTH)

        self.assertTrue(params.get("render_js"))
        self.assertTrue(params.get("premium_proxy"))
        self.assertTrue(params.get("stealth_proxy"))
