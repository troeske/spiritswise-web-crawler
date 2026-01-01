"""
ScrapingBee API Client for Integration Tests.

Handles web crawling through ScrapingBee proxy service.
"""
import time
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from .config import (
    SCRAPINGBEE_API_KEY,
    SCRAPINGBEE_BASE_URL,
    REQUEST_DELAY_SECONDS,
)


class ScrapingBeeClient:
    """Client for ScrapingBee web scraping API."""

    def __init__(self):
        self.api_key = SCRAPINGBEE_API_KEY
        self.base_url = SCRAPINGBEE_BASE_URL
        self.session = requests.Session()
        self.last_request_time = 0
        self.request_count = 0
        self.failed_requests = []

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self.last_request_time = time.time()

    def fetch_page(
        self,
        url: str,
        render_js: bool = True,
        premium_proxy: bool = False,
        wait_for: Optional[str] = None,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """
        Fetch a page using ScrapingBee.

        Args:
            url: The URL to fetch
            render_js: Whether to render JavaScript (uses more credits)
            premium_proxy: Use premium residential proxies
            wait_for: CSS selector to wait for before returning
            timeout: Request timeout in milliseconds

        Returns:
            Dict with 'success', 'content', 'status_code', 'credits_used'
        """
        self._rate_limit()

        params = {
            "api_key": self.api_key,
            "url": url,
            "render_js": str(render_js).lower(),
            "premium_proxy": str(premium_proxy).lower(),
            "timeout": timeout,
        }

        if wait_for:
            params["wait_for"] = wait_for

        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=timeout / 1000 + 10,  # Add buffer to timeout
            )

            self.request_count += 1

            # Check for ScrapingBee-specific headers
            credits_used = int(response.headers.get("Spb-Cost", 1))

            if response.status_code == 200:
                return {
                    "success": True,
                    "content": response.text,
                    "status_code": response.status_code,
                    "credits_used": credits_used,
                    "url": url,
                }
            else:
                error_info = {
                    "success": False,
                    "content": response.text,
                    "status_code": response.status_code,
                    "credits_used": credits_used,
                    "url": url,
                    "error": f"HTTP {response.status_code}",
                }
                self.failed_requests.append(error_info)
                return error_info

        except requests.exceptions.Timeout:
            error_info = {
                "success": False,
                "content": None,
                "status_code": None,
                "credits_used": 0,
                "url": url,
                "error": "Request timeout",
            }
            self.failed_requests.append(error_info)
            return error_info

        except requests.exceptions.RequestException as e:
            error_info = {
                "success": False,
                "content": None,
                "status_code": None,
                "credits_used": 0,
                "url": url,
                "error": str(e),
            }
            self.failed_requests.append(error_info)
            return error_info

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "total_requests": self.request_count,
            "failed_requests": len(self.failed_requests),
            "success_rate": (
                (self.request_count - len(self.failed_requests)) / self.request_count
                if self.request_count > 0
                else 0
            ),
        }
