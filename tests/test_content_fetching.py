"""
Tests for content fetching system (Multi-Tiered Smart Router).

Task Group 3: Multi-Tiered Smart Router
These tests verify the content fetching tiers and Smart Router orchestration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from asgiref.sync import sync_to_async


class TestTier1HttpxFetcher:
    """Tests for Tier 1 httpx fetcher with cookie injection."""

    @pytest.mark.asyncio
    async def test_tier1_injects_cookies_from_source(self):
        """Tier 1 fetcher injects cookies from CrawlerSource.age_gate_cookies."""
        from crawler.fetchers.tier1_httpx import Tier1HttpxFetcher, FetchResponse

        source_cookies = {
            "age_verified": "true",
            "consent": "yes",
        }

        # Create fetcher
        fetcher = Tier1HttpxFetcher(timeout=10.0, max_retries=1)

        # Mock the _fetch_with_retry method and prevent http client init
        mock_response = MagicMock()
        mock_response.text = "<html><body>Product Page Content</body></html>" * 10
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}

        # Patch both the http client init and fetch method
        with patch.object(fetcher, "_init_http_client", new_callable=AsyncMock), \
             patch.object(fetcher, "_fetch_with_retry", new_callable=AsyncMock) as mock_fetch:

            mock_fetch.return_value = mock_response

            result = await fetcher.fetch(
                url="https://example.com/product",
                cookies=source_cookies,
                use_default_cookies=False,
            )

            # Verify cookies were passed
            call_args = mock_fetch.call_args
            cookies_passed = call_args.kwargs.get("cookies", {})
            assert "age_verified" in cookies_passed
            assert cookies_passed["age_verified"] == "true"
            assert "consent" in cookies_passed
            assert result.success is True
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_tier1_uses_default_cookies_when_source_cookies_empty(self):
        """Tier 1 fetcher uses default age cookies when source provides none."""
        from crawler.fetchers.tier1_httpx import Tier1HttpxFetcher

        fetcher = Tier1HttpxFetcher(timeout=10.0, max_retries=1)

        # Mock the _fetch_with_retry method
        mock_response = MagicMock()
        mock_response.text = "<html><body>Normal content</body></html>" * 10
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}

        with patch.object(fetcher, "_init_http_client", new_callable=AsyncMock), \
             patch.object(fetcher, "_fetch_with_retry", new_callable=AsyncMock) as mock_fetch:

            mock_fetch.return_value = mock_response

            result = await fetcher.fetch(
                url="https://example.com/product",
                cookies={},
                use_default_cookies=True,
            )

            # Verify default cookies were used
            call_args = mock_fetch.call_args
            cookies_used = call_args.kwargs.get("cookies", {})
            # Default cookies should include age verification cookies
            assert "age_verified" in cookies_used or "over21" in cookies_used


class TestAgeGateDetection:
    """Tests for age gate detection logic."""

    def test_detects_age_gate_by_content_length(self):
        """Age gate detected when content length < 500 chars."""
        from crawler.fetchers.age_gate import detect_age_gate

        short_content = "Please verify your age to continue."
        result = detect_age_gate(short_content)

        assert result.is_age_gate is True
        # Check for "content length" in the reason (with space)
        assert "content length" in result.reason.lower()

    def test_detects_age_gate_by_keywords(self):
        """Age gate detected when content contains age verification keywords."""
        from crawler.fetchers.age_gate import detect_age_gate

        # Content long enough to pass length check, but contains keywords
        content = """
        <html>
        <head><title>Age Verification</title></head>
        <body>
            <h1>Are you of legal drinking age?</h1>
            <p>You must be 21 years or older to enter this site.</p>
            <button>Yes, I am 21+</button>
            <button>No</button>
            <!-- Padding to ensure content is long enough -->
            Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
            Nisi ut aliquip ex ea commodo consequat.
        </body>
        </html>
        """
        result = detect_age_gate(content)

        assert result.is_age_gate is True
        assert "keyword" in result.reason.lower()

    def test_no_age_gate_for_normal_product_page(self):
        """Normal product pages should not be flagged as age gates."""
        from crawler.fetchers.age_gate import detect_age_gate

        product_content = """
        <html>
        <head><title>Glenfiddich 18 Year Old Single Malt Scotch Whisky</title></head>
        <body>
            <h1>Glenfiddich 18 Year Old</h1>
            <p class="price">$89.99</p>
            <p class="description">
                This 18 year old expression is a cornerstone of the Glenfiddich range.
                It has a rich and fruity character with notes of oak and a long,
                mellow finish. The whisky spends its final maturation period in
                Oloroso sherry casks, giving it a distinctive warmth and complexity.
                ABV: 40%. Volume: 750ml. Region: Speyside, Scotland.
                Tasting notes include apple, pear, dried fruit, and subtle oak spice.
            </p>
            <div class="details">
                <span>Distillery: Glenfiddich</span>
                <span>Age: 18 Years</span>
                <span>Cask Type: Oloroso Sherry</span>
            </div>
            <button>Add to Cart</button>
        </body>
        </html>
        """
        result = detect_age_gate(product_content)

        assert result.is_age_gate is False


class TestTierEscalation:
    """Tests for tier escalation on failure."""

    @pytest.mark.asyncio
    async def test_smart_router_escalates_from_tier1_to_tier2_on_age_gate(self):
        """Smart Router escalates to Tier 2 when Tier 1 detects age gate."""
        from crawler.fetchers.smart_router import SmartRouter

        router = SmartRouter()

        # Mock Tier 1 to return age gate content
        age_gate_content = "Please verify your age."
        with patch.object(router, "_tier1_fetcher") as mock_tier1, \
             patch.object(router, "_tier2_fetcher") as mock_tier2:

            # Tier 1 returns short content (age gate)
            mock_tier1.fetch = AsyncMock(return_value=MagicMock(
                content=age_gate_content,
                status_code=200,
                headers={},
                success=True,
            ))

            # Tier 2 returns full content after handling age gate
            mock_tier2.fetch = AsyncMock(return_value=MagicMock(
                content="<html><body>Full product page content with details</body></html>" * 20,
                status_code=200,
                headers={},
                success=True,
            ))

            result = await router.fetch(
                url="https://whisky-site.com/product/123",
                source=None,
            )

            # Verify Tier 2 was called after Tier 1 detected age gate
            mock_tier2.fetch.assert_called()
            assert result.tier_used >= 2


class TestRequiresTier3Marking:
    """Tests for requires_tier3 flag marking on successful Tier 3 fetch."""

    @pytest.mark.asyncio
    async def test_marks_source_requires_tier3_on_tier3_success(self):
        """Source is marked requires_tier3=True when Tier 3 succeeds."""
        from crawler.fetchers.smart_router import SmartRouter

        # Create a mock source object
        mock_source = MagicMock()
        mock_source.age_gate_cookies = {}
        mock_source.requires_tier3 = False
        mock_source.name = "Blocked Site"

        router = SmartRouter()

        # Mock all tiers and the _mark_requires_tier3 method
        with patch.object(router, "_tier1_fetcher") as mock_tier1, \
             patch.object(router, "_tier2_fetcher") as mock_tier2, \
             patch.object(router, "_tier3_fetcher") as mock_tier3, \
             patch.object(router, "_mark_requires_tier3", new_callable=AsyncMock) as mock_mark:

            # Tier 1 fails with 403
            mock_tier1.fetch = AsyncMock(return_value=MagicMock(
                content="",
                status_code=403,
                headers={},
                success=False,
                error="Blocked",
            ))

            # Tier 2 also fails
            mock_tier2.fetch = AsyncMock(return_value=MagicMock(
                content="",
                status_code=403,
                headers={},
                success=False,
                error="Blocked",
            ))

            # Tier 3 succeeds
            mock_tier3.fetch = AsyncMock(return_value=MagicMock(
                content="<html><body>Full product content here with all the details</body></html>" * 20,
                status_code=200,
                headers={},
                success=True,
            ))

            result = await router.fetch(
                url="https://blocked-site.com/product/123",
                source=mock_source,
            )

            # Verify _mark_requires_tier3 was called with the source
            mock_mark.assert_called_once_with(mock_source)
            assert result.tier_used == 3
            assert result.success is True


class TestSmartRouterSkipsTiers:
    """Tests for Smart Router skipping lower tiers when requires_tier3 is set."""

    @pytest.mark.asyncio
    async def test_skips_lower_tiers_when_requires_tier3_is_true(self):
        """Smart Router skips Tier 1 and 2 when source has requires_tier3=True."""
        from crawler.fetchers.smart_router import SmartRouter

        # Create a mock source marked as requiring Tier 3
        mock_source = MagicMock()
        mock_source.age_gate_cookies = {}
        mock_source.requires_tier3 = True
        mock_source.name = "Tier 3 Only Site"

        router = SmartRouter()

        # Mock all tiers
        with patch.object(router, "_tier1_fetcher") as mock_tier1, \
             patch.object(router, "_tier2_fetcher") as mock_tier2, \
             patch.object(router, "_tier3_fetcher") as mock_tier3:

            mock_tier3.fetch = AsyncMock(return_value=MagicMock(
                content="<html><body>Content from Tier 3</body></html>" * 20,
                status_code=200,
                headers={},
                success=True,
            ))

            result = await router.fetch(
                url="https://tier3-only.com/product/456",
                source=mock_source,
            )

            # Verify Tier 1 and 2 were NOT called
            mock_tier1.fetch.assert_not_called()
            mock_tier2.fetch.assert_not_called()
            # Verify Tier 3 was called directly
            mock_tier3.fetch.assert_called_once()
            assert result.tier_used == 3
