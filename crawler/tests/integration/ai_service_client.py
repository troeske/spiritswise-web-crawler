"""
AI Enhancement Service Client for Integration Tests.

Handles communication with the AI Enhancement API on VPS.
"""
import time
import requests
from typing import Optional, Dict, Any, List

from .config import (
    AI_SERVICE_BASE_URL,
    AI_SERVICE_USERNAME,
    AI_SERVICE_PASSWORD,
)


class AIEnhancementClient:
    """Client for AI Enhancement Service API."""

    def __init__(self):
        self.base_url = AI_SERVICE_BASE_URL
        self.username = AI_SERVICE_USERNAME
        self.password = AI_SERVICE_PASSWORD
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.request_count = 0
        self.failed_requests = []

    def _ensure_authenticated(self):
        """Ensure we have a valid access token."""
        if self.access_token and time.time() < self.token_expiry - 60:
            return True

        # Get new token
        try:
            response = self.session.post(
                f"{self.base_url}/api/token/",
                json={
                    "username": self.username,
                    "password": self.password,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access"]
                self.refresh_token = data.get("refresh")
                # Tokens are typically valid for 30 days based on settings
                self.token_expiry = time.time() + (30 * 24 * 60 * 60)
                return True
            else:
                raise Exception(f"Authentication failed: {response.status_code}")

        except Exception as e:
            raise Exception(f"Failed to authenticate: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        self._ensure_authenticated()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def enhance_from_crawler(
        self,
        content: str,
        source_url: str,
        product_type_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enhance product data from crawled content.

        Args:
            content: Raw HTML/text content from crawler
            source_url: Original URL of the content
            product_type_hint: Optional hint about product type (whiskey, port_wine)

        Returns:
            Dict with enhancement results or error info
        """
        self.request_count += 1

        try:
            payload = {
                "content": content,
                "source_url": source_url,
            }
            if product_type_hint:
                payload["product_type_hint"] = product_type_hint

            response = self.session.post(
                f"{self.base_url}/api/v1/enhance/from-crawler/",
                headers=self._get_headers(),
                json=payload,
                timeout=120,  # AI processing can take time
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                    "source_url": source_url,
                }
            else:
                error_info = {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                    "source_url": source_url,
                }
                self.failed_requests.append(error_info)
                return error_info

        except requests.exceptions.Timeout:
            error_info = {
                "success": False,
                "error": "Request timeout",
                "status_code": None,
                "source_url": source_url,
            }
            self.failed_requests.append(error_info)
            return error_info

        except Exception as e:
            error_info = {
                "success": False,
                "error": str(e),
                "status_code": None,
                "source_url": source_url,
            }
            self.failed_requests.append(error_info)
            return error_info

    def enhance_batch(
        self,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit batch enhancement job.

        Args:
            items: List of items to enhance, each with 'content' and 'source_url'

        Returns:
            Dict with job_id for status tracking
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/enhance/batch/",
                headers=self._get_headers(),
                json={"items": items},
                timeout=30,
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": None,
            }

    def get_batch_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a batch job."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/enhance/status/{job_id}/",
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": None,
            }

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
