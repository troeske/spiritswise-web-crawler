"""
Tier 3 Content Fetcher - ScrapingBee API.

Used as a last resort when Tier 1 and Tier 2 fail due to anti-bot protections.
Provides premium proxy rotation and JavaScript rendering.
Tracks costs per request for budget monitoring.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from django.conf import settings
from django.utils import timezone

from .tier1_httpx import FetchResponse

logger = logging.getLogger(__name__)


class Tier3ScrapingBeeFetcher:
    """
    Tier 3 fetcher using ScrapingBee API.

    Features:
    - Premium proxy rotation
    - JavaScript rendering
    - Cost tracking per request
    - Automatic retry handling by ScrapingBee
    """

    # Cost per request in cents (based on ScrapingBee pricing)
    # Standard request: 1 credit = ~$0.0049
    # Premium proxy: 10 credits = ~$0.049
    # JavaScript rendering: 5 credits = ~$0.0245
    COST_PER_REQUEST_CENTS = 5  # Estimate for premium + JS

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize Tier 3 fetcher.

        Args:
            api_key: ScrapingBee API key (defaults to settings)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or getattr(settings, "SCRAPINGBEE_API_KEY", "")
        self.timeout = timeout or getattr(settings, "CRAWLER_REQUEST_TIMEOUT", 30)

        self._client = None

    def _init_client(self):
        """Initialize ScrapingBee client."""
        if not self.api_key:
            raise ValueError(
                "ScrapingBee API key not configured. "
                "Set SCRAPINGBEE_API_KEY in settings."
            )

        try:
            from scrapingbee import ScrapingBeeClient
            self._client = ScrapingBeeClient(api_key=self.api_key)
            logger.info("ScrapingBee client initialized for Tier 3 fetching")
        except ImportError:
            raise RuntimeError(
                "ScrapingBee package not installed. "
                "Install with: pip install scrapingbee"
            )

    async def fetch(
        self,
        url: str,
        cookies: Optional[Dict[str, str]] = None,
        crawl_job=None,
        render_js: bool = True,
        premium_proxy: bool = True,
        stealth_proxy: bool = True,
    ) -> FetchResponse:
        """
        Fetch URL content using ScrapingBee API.

        Args:
            url: URL to fetch
            cookies: Cookies to include in request
            crawl_job: CrawlJob instance for cost tracking
            render_js: Whether to render JavaScript
            premium_proxy: Whether to use premium proxies
            stealth_proxy: Whether to use stealth mode (avoids detection)

        Returns:
            FetchResponse with content from ScrapingBee
        """
        if self._client is None:
            self._init_client()

        try:
            # Build ScrapingBee parameters
            params = {
                "render_js": render_js,
                "premium_proxy": premium_proxy,
                "stealth_proxy": stealth_proxy,
                "timeout": self.timeout * 1000,  # ScrapingBee uses milliseconds
            }

            # Add cookies if provided
            if cookies:
                cookie_str = "; ".join(
                    f"{name}={value}" for name, value in cookies.items()
                )
                params["cookies"] = cookie_str

            # Make request (ScrapingBee client is synchronous)
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.get(url, params=params)
            )

            # Track cost
            await self._track_cost(crawl_job)

            # Parse response
            if response.ok:
                return FetchResponse(
                    content=response.text,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    success=True,
                    tier=3,
                )
            else:
                logger.warning(
                    f"ScrapingBee returned {response.status_code} for {url}"
                )
                return FetchResponse(
                    content="",
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    success=False,
                    error=f"ScrapingBee HTTP {response.status_code}",
                    tier=3,
                )

        except Exception as e:
            logger.error(f"Tier 3 ScrapingBee error for {url}: {e}")
            return FetchResponse(
                content="",
                status_code=0,
                headers={},
                success=False,
                error=str(e),
                tier=3,
            )

    async def _track_cost(self, crawl_job=None):
        """
        Track API usage cost.

        Creates a CrawlCost record for the request.

        Args:
            crawl_job: Associated CrawlJob for cost attribution
        """
        try:
            from asgiref.sync import sync_to_async
            from crawler.models import CrawlCost

            @sync_to_async
            def create_cost_record():
                CrawlCost.objects.create(
                    service="scrapingbee",
                    cost_cents=self.COST_PER_REQUEST_CENTS,
                    crawl_job=crawl_job,
                    request_count=1,
                    timestamp=timezone.now(),
                )

            await create_cost_record()
            logger.debug(
                f"Tracked ScrapingBee cost: {self.COST_PER_REQUEST_CENTS} cents"
            )

        except Exception as e:
            # Don't fail the fetch if cost tracking fails
            logger.warning(f"Failed to track ScrapingBee cost: {e}")
