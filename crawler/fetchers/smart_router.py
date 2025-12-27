"""
Smart Router - Multi-tiered content fetching orchestration.

Orchestrates fetching across three tiers:
- Tier 1: httpx + cookies (fastest, lowest cost)
- Tier 2: Playwright headless browser (JavaScript, age gates)
- Tier 3: ScrapingBee proxy service (blocked sites)

Features:
- Tier escalation on failure
- Age gate detection and bypass
- requires_tier3 flag for skipping lower tiers
- Error logging to CrawlError model
- Monitoring integration (Task Group 9)
"""

import logging
import traceback
from dataclasses import dataclass
from typing import Dict, Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from .age_gate import detect_age_gate
from .tier1_httpx import Tier1HttpxFetcher, FetchResponse
from .tier2_playwright import Tier2PlaywrightFetcher
from .tier3_scrapingbee import Tier3ScrapingBeeFetcher

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of Smart Router fetch operation."""

    content: str
    status_code: int
    headers: Dict[str, str]
    success: bool
    tier_used: int
    error: Optional[str] = None
    age_gate_detected: bool = False
    age_gate_bypassed: bool = False


class SmartRouter:
    """
    Smart Router for multi-tiered content fetching.

    Orchestrates fetching across three tiers with automatic escalation:
    1. Tier 1 (httpx + cookies) - First attempt for all requests
    2. Tier 2 (Playwright) - On age gate detection or JavaScript requirement
    3. Tier 3 (ScrapingBee) - On persistent blocking

    Sources marked with requires_tier3=True skip directly to Tier 3.

    Integrates with monitoring system for:
    - Sentry error capture with context
    - Consecutive failure tracking
    - CrawlError record creation
    """

    def __init__(
        self,
        redis_client=None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize Smart Router.

        Args:
            redis_client: Redis client for cookie caching
            timeout: Request timeout (shared across tiers)
        """
        self.timeout = timeout or getattr(
            settings, "CRAWLER_REQUEST_TIMEOUT", 30
        )
        self.redis_client = redis_client

        # Lazy initialization of fetchers
        self._tier1_fetcher: Optional[Tier1HttpxFetcher] = None
        self._tier2_fetcher: Optional[Tier2PlaywrightFetcher] = None
        self._tier3_fetcher: Optional[Tier3ScrapingBeeFetcher] = None

        # Lazy initialization of failure tracker
        self._failure_tracker = None

    def _get_tier1_fetcher(self) -> Tier1HttpxFetcher:
        """Get or create Tier 1 fetcher."""
        if self._tier1_fetcher is None:
            self._tier1_fetcher = Tier1HttpxFetcher(timeout=self.timeout)
        return self._tier1_fetcher

    def _get_tier2_fetcher(self) -> Tier2PlaywrightFetcher:
        """Get or create Tier 2 fetcher."""
        if self._tier2_fetcher is None:
            self._tier2_fetcher = Tier2PlaywrightFetcher(
                timeout=self.timeout,
                redis_client=self.redis_client,
            )
        return self._tier2_fetcher

    def _get_tier3_fetcher(self) -> Tier3ScrapingBeeFetcher:
        """Get or create Tier 3 fetcher."""
        if self._tier3_fetcher is None:
            self._tier3_fetcher = Tier3ScrapingBeeFetcher(timeout=self.timeout)
        return self._tier3_fetcher

    def _get_failure_tracker(self):
        """Get or create failure tracker."""
        if self._failure_tracker is None:
            try:
                from crawler.monitoring import get_failure_tracker
                self._failure_tracker = get_failure_tracker()
            except Exception as e:
                logger.warning(f"Failed to initialize failure tracker: {e}")
        return self._failure_tracker

    async def close(self):
        """Close all fetcher connections."""
        if self._tier1_fetcher:
            await self._tier1_fetcher.close()
        if self._tier2_fetcher:
            await self._tier2_fetcher.close()

    async def fetch(
        self,
        url: str,
        source=None,
        crawl_job=None,
        force_tier: Optional[int] = None,
    ) -> FetchResult:
        """
        Fetch URL content using Smart Router tier escalation.

        Args:
            url: URL to fetch
            source: CrawlerSource instance (for cookies and tier3 flag)
            crawl_job: CrawlJob instance (for cost tracking)
            force_tier: Force specific tier (1, 2, or 3)

        Returns:
            FetchResult with content and metadata
        """
        # Add Sentry breadcrumb for this fetch
        self._add_fetch_breadcrumb(url, source)

        # Get source configuration
        cookies = {}
        requires_tier3 = False

        if source:
            cookies = source.age_gate_cookies or {}
            requires_tier3 = source.requires_tier3

        # Determine starting tier
        if force_tier:
            start_tier = force_tier
        elif requires_tier3:
            start_tier = 3
            logger.info(f"Skipping to Tier 3 for {url} (requires_tier3=True)")
        else:
            start_tier = 1

        # Attempt tiers in sequence
        result = None
        last_error = None
        tier_used = start_tier

        for tier in range(start_tier, 4):
            tier_used = tier

            try:
                if tier == 1:
                    result = await self._try_tier1(url, cookies)
                elif tier == 2:
                    result = await self._try_tier2(url, cookies)
                elif tier == 3:
                    result = await self._try_tier3(url, cookies, crawl_job, source)

                if result and result.success:
                    # Check for age gate
                    if tier < 3:
                        age_gate = detect_age_gate(result.content)
                        if age_gate.is_age_gate:
                            logger.info(
                                f"Age gate detected at Tier {tier} for {url}: "
                                f"{age_gate.reason}"
                            )
                            # Escalate to next tier
                            continue

                    # Success - reset failure counter
                    await self._record_success(source)

                    return FetchResult(
                        content=result.content,
                        status_code=result.status_code,
                        headers=result.headers,
                        success=True,
                        tier_used=tier,
                    )

                else:
                    # Fetch failed - log and escalate
                    last_error = result.error if result else "Unknown error"
                    logger.warning(
                        f"Tier {tier} failed for {url}: {last_error}"
                    )

            except Exception as e:
                last_error = str(e)
                logger.error(f"Tier {tier} exception for {url}: {e}")

        # All tiers failed - record failure and log error
        await self._record_failure(source, url, tier_used)
        await self._log_error(
            source=source,
            url=url,
            error_type="blocked" if tier_used == 3 else "connection",
            message=f"All tiers failed: {last_error}",
            tier_used=tier_used,
        )

        return FetchResult(
            content="",
            status_code=0,
            headers={},
            success=False,
            tier_used=tier_used,
            error=last_error,
        )

    def _add_fetch_breadcrumb(self, url: str, source) -> None:
        """Add Sentry breadcrumb for fetch operation."""
        try:
            from crawler.monitoring import add_crawl_breadcrumb

            source_name = source.name if source else "Unknown"
            add_crawl_breadcrumb(
                source_name=source_name,
                url=url,
                tier=0,  # Will be updated on completion
                message=f"Fetching {url}",
                level="info",
            )
        except Exception:
            # Don't fail fetch if breadcrumb fails
            pass

    async def _record_failure(self, source, url: str, tier_used: int) -> None:
        """Record failure to monitoring system."""
        if source is None:
            return

        try:
            from crawler.monitoring import capture_crawl_error

            tracker = self._get_failure_tracker()
            if tracker:
                def _record():
                    tracker.record_failure(
                        source_id=str(source.id),
                        source_name=source.name,
                    )
                await sync_to_async(_record)()

            # Create synthetic exception for Sentry capture
            error = Exception(f"Fetch failed at tier {tier_used} for {url}")
            capture_crawl_error(
                error=error,
                source=source,
                url=url,
                tier=tier_used,
            )

        except Exception as e:
            logger.warning(f"Failed to record failure to monitoring: {e}")

    async def _record_success(self, source) -> None:
        """Record success to reset failure counter."""
        if source is None:
            return

        try:
            tracker = self._get_failure_tracker()
            if tracker:
                def _record():
                    tracker.record_success(str(source.id))
                await sync_to_async(_record)()

        except Exception as e:
            logger.warning(f"Failed to record success to monitoring: {e}")

    async def _try_tier1(
        self,
        url: str,
        cookies: Dict[str, str],
    ) -> FetchResponse:
        """Attempt Tier 1 fetch."""
        logger.debug(f"Trying Tier 1 for {url}")
        fetcher = self._get_tier1_fetcher()
        return await fetcher.fetch(url, cookies=cookies)

    async def _try_tier2(
        self,
        url: str,
        cookies: Dict[str, str],
    ) -> FetchResponse:
        """Attempt Tier 2 fetch."""
        logger.debug(f"Trying Tier 2 for {url}")
        fetcher = self._get_tier2_fetcher()
        return await fetcher.fetch(url, cookies=cookies, solve_age_gate=True)

    async def _try_tier3(
        self,
        url: str,
        cookies: Dict[str, str],
        crawl_job,
        source,
    ) -> FetchResponse:
        """
        Attempt Tier 3 fetch.

        On success, marks source as requires_tier3=True for future requests.
        """
        logger.debug(f"Trying Tier 3 for {url}")
        fetcher = self._get_tier3_fetcher()
        result = await fetcher.fetch(url, cookies=cookies, crawl_job=crawl_job)

        # Mark source as requiring Tier 3 on success
        if result.success and source:
            await self._mark_requires_tier3(source)

        return result

    async def _mark_requires_tier3(self, source):
        """Mark source as requiring Tier 3 for future requests."""
        try:

            def _update_source():
                source.requires_tier3 = True
                source.save(update_fields=["requires_tier3"])

            await sync_to_async(_update_source)()
            logger.info(f"Marked {source.name} as requires_tier3=True")
        except Exception as e:
            logger.warning(f"Failed to mark source as requires_tier3: {e}")

    async def _log_error(
        self,
        source,
        url: str,
        error_type: str,
        message: str,
        tier_used: int,
        response_status: Optional[int] = None,
        response_headers: Optional[Dict] = None,
    ):
        """Log error to CrawlError model via monitoring system."""
        try:
            from crawler.monitoring import create_crawl_error_record

            def _create_error():
                create_crawl_error_record(
                    source=source,
                    url=url,
                    error_type=error_type,
                    message=message,
                    tier_used=tier_used,
                    response_status=response_status,
                    response_headers=response_headers,
                    stack_trace=traceback.format_exc(),
                )

            await sync_to_async(_create_error)()
            logger.debug(f"Logged CrawlError for {url}")

        except Exception as e:
            # Don't fail if error logging fails
            logger.warning(f"Failed to log CrawlError: {e}")
