"""
Tier 1 Content Fetcher - httpx with cookie injection.

The fastest and lowest cost fetching tier. Uses async httpx with HTTP/2 support.
Injects age gate cookies from CrawlerSource configuration or default fallbacks.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class FetchResponse:
    """Response from a fetch operation."""

    content: str
    status_code: int
    headers: Dict[str, str]
    success: bool
    error: Optional[str] = None
    tier: int = 1


class Tier1HttpxFetcher:
    """
    Tier 1 fetcher using async httpx with HTTP/2 support.

    Features:
    - Async HTTP client with connection pooling
    - HTTP/2 support for better performance
    - Cookie injection for age gate bypass
    - Configurable timeout and retry logic
    - Default fallback cookies for unknown domains
    """

    # Use a browser User-Agent to avoid bot detection
    # Many sites serve different content or block crawler user agents
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Note: Removed 'br' (brotli) from Accept-Encoding because httpx doesn't
    # decompress brotli by default, resulting in garbled content with null chars.
    # Only request gzip/deflate which httpx handles correctly.
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
    }

    def __init__(
        self,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize Tier 1 fetcher.

        Args:
            timeout: Request timeout in seconds (default from settings)
            max_retries: Maximum retry attempts (default from settings)
            user_agent: Custom User-Agent string
        """
        self.timeout = timeout or getattr(
            settings, "CRAWLER_REQUEST_TIMEOUT", 30
        )
        self.max_retries = max_retries or getattr(
            settings, "CRAWLER_MAX_RETRIES", 3
        )
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_http_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _init_http_client(self):
        """Initialize HTTP client."""
        if self._http_client is None:
            headers = {
                **self.DEFAULT_HEADERS,
                "User-Agent": self.user_agent,
            }

            # Note: http2=False to match original enrichment pipeline behavior
            # Some sites handle HTTP/2 differently and may block H2 requests
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
                follow_redirects=True,
                http2=False,
            )

    async def close(self):
        """Close HTTP client connection."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_default_cookies(self) -> Dict[str, str]:
        """Get default age gate cookies from settings."""
        return getattr(
            settings,
            "CRAWLER_DEFAULT_AGE_COOKIES",
            {
                "age_verified": "true",
                "dob": "1990-01-01",
                "over18": "true",
                "over21": "true",
                "ageverified": "true",
                "av": "1",
            }
        )

    async def fetch(
        self,
        url: str,
        cookies: Optional[Dict[str, str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        use_default_cookies: bool = True,
    ) -> FetchResponse:
        """
        Fetch URL content with cookie injection.

        Args:
            url: URL to fetch
            cookies: Source-specific cookies to inject
            custom_headers: Additional headers to include
            use_default_cookies: Whether to merge default cookies if source cookies are empty

        Returns:
            FetchResponse with content, status, and metadata
        """
        if self._http_client is None:
            await self._init_http_client()

        # Build cookies
        request_cookies = {}
        if use_default_cookies:
            request_cookies.update(self._get_default_cookies())
        if cookies:
            request_cookies.update(cookies)

        # Build headers
        request_headers = {}
        if custom_headers:
            request_headers.update(custom_headers)

        try:
            response = await self._fetch_with_retry(
                url=url,
                cookies=request_cookies,
                headers=request_headers,
            )

            is_success = 200 <= response.status_code < 400
            error_msg = None
            if not is_success:
                error_msg = f"HTTP {response.status_code}"
                logger.warning(f"Tier 1 HTTP {response.status_code} for {url}")

            return FetchResponse(
                content=response.text,
                status_code=response.status_code,
                headers=dict(response.headers),
                success=is_success,
                error=error_msg,
                tier=1,
            )

        except httpx.TimeoutException as e:
            logger.warning(f"Tier 1 timeout fetching {url}: {e}")
            return FetchResponse(
                content="",
                status_code=0,
                headers={},
                success=False,
                error=f"Timeout: {e}",
                tier=1,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(f"Tier 1 HTTP error for {url}: {e.response.status_code}")
            return FetchResponse(
                content="",
                status_code=e.response.status_code,
                headers=dict(e.response.headers),
                success=False,
                error=f"HTTP {e.response.status_code}",
                tier=1,
            )

        except Exception as e:
            logger.error(f"Tier 1 error fetching {url}: {e}")
            return FetchResponse(
                content="",
                status_code=0,
                headers={},
                success=False,
                error=str(e),
                tier=1,
            )

    async def _fetch_with_retry(
        self,
        url: str,
        cookies: Dict[str, str],
        headers: Dict[str, str],
    ) -> httpx.Response:
        """
        Fetch with exponential backoff retry logic.

        Uses exponential backoff on transient failures.
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = await self._http_client.get(
                    url,
                    cookies=cookies,
                    headers=headers,
                )

                # Don't retry on 4xx client errors
                if 400 <= response.status_code < 500:
                    return response

                response.raise_for_status()
                return response

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})"
                )

            except httpx.HTTPStatusError as e:
                # Don't retry client errors
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning(
                    f"HTTP error {e.response.status_code} for {url} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Error fetching {url}: {e} (attempt {attempt + 1}/{self.max_retries})"
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = 2 ** attempt
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_error:
            raise last_error
        raise Exception(f"Failed to fetch {url} after {self.max_retries} attempts")
