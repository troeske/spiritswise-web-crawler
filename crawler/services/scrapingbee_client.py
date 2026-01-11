"""
ScrapingBee Client Wrapper for Web Crawling.

Task Group 30: Provides a client interface for ScrapingBee API integration.

Features:
- JS render mode: render_js=True
- Stealth mode: render_js=True, premium_proxy=True, stealth_proxy=True
- Error handling with structured responses
- Mode-based parameter configuration

This is currently a stub/mock implementation that defines the interface.
Actual ScrapingBee API calls can be enabled by providing a valid API key.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScrapingBeeMode(Enum):
    """
    ScrapingBee crawling modes.

    Each mode represents a different level of anti-blocking capability:
    - JS_RENDER: Renders JavaScript, good for SPA sites
    - STEALTH: Full stealth mode with premium proxies
    """

    JS_RENDER = "js_render"
    STEALTH = "stealth"


@dataclass
class ScrapingBeeResponse:
    """
    Response from ScrapingBee API.

    Attributes:
        success: Whether the request was successful
        content: HTML content of the page
        status_code: HTTP status code
        cost: API credits used
        error: Error message if failed
    """

    success: bool
    content: str
    status_code: int
    cost: int = 0
    error: Optional[str] = None


class ScrapingBeeClient:
    """
    Client wrapper for ScrapingBee API.

    Provides methods for fetching web pages with different modes:
    - JS render mode for JavaScript-heavy sites
    - Stealth mode for sites with aggressive anti-bot measures

    This implementation is a stub that can be extended with actual
    ScrapingBee API integration.
    """

    # ScrapingBee API endpoint
    API_URL = "https://app.scrapingbee.com/api/v1/"

    # Default parameters for each mode
    MODE_PARAMS = {
        ScrapingBeeMode.JS_RENDER: {
            "render_js": True,
            "premium_proxy": False,
            "stealth_proxy": False,
        },
        ScrapingBeeMode.STEALTH: {
            "render_js": True,
            "premium_proxy": True,
            "stealth_proxy": True,
        },
    }

    def __init__(self, api_key: str):
        """
        Initialize the ScrapingBee client.

        Args:
            api_key: ScrapingBee API key
        """
        self.api_key = api_key
        self._mock_mode = not api_key or api_key == "test_key"

        if self._mock_mode:
            logger.warning(
                "ScrapingBee client initialized in mock mode (no valid API key)"
            )

    def get_params_for_mode(self, mode: ScrapingBeeMode) -> Dict[str, Any]:
        """
        Get the parameters for a specific crawling mode.

        Args:
            mode: ScrapingBee crawling mode

        Returns:
            Dictionary of parameters for the mode
        """
        return self.MODE_PARAMS.get(mode, {}).copy()

    def fetch(
        self,
        url: str,
        mode: ScrapingBeeMode = ScrapingBeeMode.JS_RENDER,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a URL using ScrapingBee.

        Args:
            url: URL to fetch
            mode: Crawling mode to use
            extra_params: Additional parameters to pass to ScrapingBee

        Returns:
            Dictionary with success, content, status_code, and optional error
        """
        params = self.get_params_for_mode(mode)

        if extra_params:
            params.update(extra_params)

        logger.info(
            f"ScrapingBee fetch: url={url}, mode={mode.value}, params={params}"
        )

        if self._mock_mode:
            return self._mock_fetch(url, mode, params)

        return self._real_fetch(url, params)

    def _mock_fetch(
        self,
        url: str,
        mode: ScrapingBeeMode,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mock implementation for testing without API calls.

        Args:
            url: URL to fetch
            mode: Crawling mode
            params: Request parameters

        Returns:
            Mock response dictionary
        """
        logger.info(f"Mock fetch for {url} with mode {mode.value}")

        # Return a mock successful response
        return {
            "success": True,
            "content": f"<html><body><h1>Mock content for {url}</h1></body></html>",
            "status_code": 200,
            "cost": 1 if mode == ScrapingBeeMode.JS_RENDER else 5,
        }

    def _real_fetch(
        self,
        url: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Real implementation using ScrapingBee API.

        Args:
            url: URL to fetch
            params: Request parameters

        Returns:
            Response dictionary with success, content, status_code
        """
        import requests

        try:
            request_params = {
                "api_key": self.api_key,
                "url": url,
                **params,
            }

            response = requests.get(
                self.API_URL,
                params=request_params,
                timeout=60,
            )

            # ScrapingBee returns the page content directly
            return {
                "success": response.status_code == 200,
                "content": response.text,
                "status_code": response.status_code,
                "cost": int(response.headers.get("Spb-Cost", 1)),
            }

        except requests.RequestException as e:
            logger.error(f"ScrapingBee API error: {e}")
            return {
                "success": False,
                "content": "",
                "status_code": 0,
                "error": str(e),
            }

    def get_remaining_credits(self) -> Optional[int]:
        """
        Get the remaining API credits.

        Returns:
            Number of remaining credits, or None if unable to check
        """
        if self._mock_mode:
            return 10000  # Mock unlimited credits

        try:
            import requests

            response = requests.get(
                "https://app.scrapingbee.com/api/v1/usage",
                params={"api_key": self.api_key},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("remaining_credits")

        except Exception as e:
            logger.error(f"Error checking ScrapingBee credits: {e}")

        return None

    def supports_mode(self, mode: ScrapingBeeMode) -> bool:
        """
        Check if a mode is supported.

        Args:
            mode: ScrapingBee mode to check

        Returns:
            True if mode is supported
        """
        return mode in self.MODE_PARAMS

    def fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        mode: ScrapingBeeMode = ScrapingBeeMode.JS_RENDER,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Fetch a URL with exponential backoff retry logic.

        Phase 11: Integration Failure Validators - Retry Logic

        Implements retry with exponential backoff for HTTP 5xx errors:
        - Retry 1: 2s delay
        - Retry 2: 4s delay
        - Retry 3: 8s delay

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts (default: 3)
            mode: ScrapingBee crawling mode
            extra_params: Additional parameters for ScrapingBee

        Returns:
            HTML content string if successful, None if all retries fail
        """
        import time

        last_error = None
        base_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                result = self.fetch(url, mode=mode, extra_params=extra_params)

                if result.get("success") and result.get("status_code") == 200:
                    return result.get("content")

                status_code = result.get("status_code", 0)

                # Retry on server errors (5xx)
                if 500 <= status_code < 600:
                    last_error = f"HTTP {status_code}"
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 2, 4, 8 seconds
                        logger.warning(
                            f"ScrapingBee retry {attempt + 1}/{max_retries} for {url}, "
                            f"status={status_code}, waiting {delay}s"
                        )
                        time.sleep(delay)
                        continue

                # Don't retry on client errors (4xx)
                if 400 <= status_code < 500:
                    logger.warning(
                        f"ScrapingBee client error for {url}: HTTP {status_code}"
                    )
                    return None

                # Unknown error - don't retry
                last_error = result.get("error", f"HTTP {status_code}")
                logger.warning(f"ScrapingBee error for {url}: {last_error}")
                return None

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"ScrapingBee exception retry {attempt + 1}/{max_retries} for {url}: {e}, "
                        f"waiting {delay}s"
                    )
                    time.sleep(delay)
                    continue

        logger.error(
            f"ScrapingBee gave up after {max_retries} retries for {url}: {last_error}"
        )
        return None
