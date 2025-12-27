"""
Tier 2 Content Fetcher - Playwright headless browser.

Used when Tier 1 fails due to JavaScript requirements or age gates.
Features semantic age gate click solving and session cookie persistence.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from django.conf import settings

from .age_gate import get_age_gate_button_selectors
from .tier1_httpx import FetchResponse

logger = logging.getLogger(__name__)

# Playwright is imported lazily to avoid startup overhead
_playwright = None
_browser = None


@dataclass
class CookieData:
    """Represents a browser cookie."""

    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    http_only: bool = False


class Tier2PlaywrightFetcher:
    """
    Tier 2 fetcher using Playwright headless browser.

    Features:
    - Lazy Playwright initialization (import on first use)
    - Age gate semantic click solver
    - Session cookie persistence to Redis
    - JavaScript-rendered content capture
    """

    def __init__(
        self,
        timeout: Optional[float] = None,
        redis_client=None,
    ):
        """
        Initialize Tier 2 fetcher.

        Args:
            timeout: Page load timeout in seconds
            redis_client: Redis client for cookie persistence
        """
        self.timeout = timeout or getattr(
            settings, "CRAWLER_REQUEST_TIMEOUT", 30
        )
        self.redis_client = redis_client

        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_playwright()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _init_playwright(self):
        """Initialize Playwright browser (lazy loading)."""
        global _playwright, _browser

        if _browser is not None:
            self._playwright = _playwright
            self._browser = _browser
            return

        try:
            from playwright.async_api import async_playwright

            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self._playwright = _playwright
            self._browser = _browser
            logger.info("Playwright browser initialized for Tier 2 fetching")

        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )

    async def close(self):
        """Close browser and Playwright instance."""
        global _playwright, _browser

        if _browser:
            await _browser.close()
            _browser = None

        if _playwright:
            await _playwright.stop()
            _playwright = None

        self._browser = None
        self._playwright = None

    def _get_redis_cookie_key(self, domain: str) -> str:
        """Get Redis key for domain cookies."""
        return f"crawler:cookies:{domain}"

    async def _load_cookies_from_redis(self, domain: str) -> List[Dict]:
        """Load cached cookies for domain from Redis."""
        if not self.redis_client:
            return []

        try:
            key = self._get_redis_cookie_key(domain)
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to load cookies from Redis: {e}")

        return []

    async def _save_cookies_to_redis(
        self,
        domain: str,
        cookies: List[Dict],
        ttl: int = 86400,  # 24 hours
    ):
        """Save cookies to Redis for persistence."""
        if not self.redis_client:
            return

        try:
            key = self._get_redis_cookie_key(domain)
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(cookies),
            )
            logger.debug(f"Saved {len(cookies)} cookies for {domain} to Redis")
        except Exception as e:
            logger.warning(f"Failed to save cookies to Redis: {e}")

    async def _try_click_age_gate(self, page) -> bool:
        """
        Attempt to click through an age gate.

        Uses semantic button matching to find and click age verification buttons.

        Args:
            page: Playwright page object

        Returns:
            True if age gate was clicked, False otherwise
        """
        selectors = get_age_gate_button_selectors()

        for selector in selectors:
            try:
                # Check if element exists and is visible
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible():
                    logger.info(f"Found age gate button with selector: {selector}")
                    await element.click()

                    # Wait for navigation or content change
                    await asyncio.sleep(1)
                    await page.wait_for_load_state("networkidle", timeout=5000)

                    logger.info("Successfully clicked age gate button")
                    return True

            except Exception as e:
                # Continue to next selector
                logger.debug(f"Selector {selector} not found or not clickable: {e}")
                continue

        return False

    async def fetch(
        self,
        url: str,
        cookies: Optional[Dict[str, str]] = None,
        solve_age_gate: bool = True,
    ) -> FetchResponse:
        """
        Fetch URL content using headless browser.

        Args:
            url: URL to fetch
            cookies: Initial cookies to set
            solve_age_gate: Whether to attempt age gate solving

        Returns:
            FetchResponse with rendered content
        """
        if self._browser is None:
            await self._init_playwright()

        # Extract domain for cookie operations
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc

        # Create new browser context with cookies
        context = await self._browser.new_context()

        try:
            # Load cached cookies from Redis
            cached_cookies = await self._load_cookies_from_redis(domain)
            if cached_cookies:
                await context.add_cookies(cached_cookies)
                logger.debug(f"Loaded {len(cached_cookies)} cached cookies for {domain}")

            # Add provided cookies
            if cookies:
                cookie_list = [
                    {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                    }
                    for name, value in cookies.items()
                ]
                await context.add_cookies(cookie_list)

            # Create page and navigate
            page = await context.new_page()

            try:
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.timeout * 1000,
                )

                # Attempt age gate solving if enabled
                if solve_age_gate:
                    age_gate_clicked = await self._try_click_age_gate(page)
                    if age_gate_clicked:
                        logger.info(f"Age gate solved for {url}")

                # Wait for content to stabilize
                await page.wait_for_load_state("domcontentloaded")

                # Get rendered content
                content = await page.content()
                status_code = response.status if response else 200

                # Save session cookies to Redis
                cookies_to_save = await context.cookies()
                if cookies_to_save:
                    await self._save_cookies_to_redis(domain, cookies_to_save)

                return FetchResponse(
                    content=content,
                    status_code=status_code,
                    headers=dict(response.headers) if response else {},
                    success=200 <= status_code < 400,
                    tier=2,
                )

            except Exception as e:
                logger.error(f"Tier 2 page error for {url}: {e}")
                return FetchResponse(
                    content="",
                    status_code=0,
                    headers={},
                    success=False,
                    error=str(e),
                    tier=2,
                )

            finally:
                await page.close()

        except Exception as e:
            logger.error(f"Tier 2 context error for {url}: {e}")
            return FetchResponse(
                content="",
                status_code=0,
                headers={},
                success=False,
                error=str(e),
                tier=2,
            )

        finally:
            await context.close()
