"""
Enhancement Client - Client for AI Enhancement Service.

Phase 11: Integration Failure Validators - Enhancement Retry Logic

This module provides a client interface for the AI Enhancement Service
with retry logic for handling null critical fields.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EnhancementClient:
    """
    Client wrapper for AI Enhancement Service.

    Provides methods for enhancing product data with retry logic
    for handling cases where critical fields are null.
    """

    # Critical fields that must be present for a valid response
    CRITICAL_FIELDS = ["name", "brand"]

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the enhancement client.

        Args:
            base_url: AI Enhancement Service URL
            api_key: API key for authentication
        """
        from django.conf import settings

        self.base_url = base_url or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_URL", "http://localhost:8000"
        )
        self.api_key = api_key or getattr(
            settings, "AI_ENHANCEMENT_SERVICE_TOKEN", None
        )

    def _has_critical_fields(self, data: Dict[str, Any]) -> bool:
        """
        Check if response has all critical fields populated.

        Args:
            data: Response data dictionary

        Returns:
            True if all critical fields are present and non-null
        """
        for field in self.CRITICAL_FIELDS:
            if not data.get(field):
                return False
        return True

    def enhance_with_retry(
        self,
        content: str,
        product_type: str,
        product_name: Optional[str] = None,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Enhance product data with retry logic for null critical fields.

        Phase 11: Integration Failure Validators

        If critical fields (name, brand) are null after first attempt,
        retries up to max_retries times.

        Args:
            content: Raw HTML/text content to enhance
            product_type: Type of product (whiskey, port_wine, etc.)
            product_name: Optional product name hint
            max_retries: Maximum retry attempts (default: 2)

        Returns:
            Enhanced data dictionary, or None if all retries fail
        """
        last_result = None

        for attempt in range(max_retries + 1):
            try:
                result = self._call_enhancement_api(content, product_type, product_name)

                if result and self._has_critical_fields(result):
                    return result

                last_result = result

                if attempt < max_retries:
                    logger.warning(
                        f"Enhancement retry {attempt + 1}/{max_retries}: "
                        f"missing critical fields for {product_name or 'unknown'}"
                    )

            except Exception as e:
                logger.error(f"Enhancement API error: {e}")
                if attempt < max_retries:
                    continue

        # Return last result even if incomplete
        if last_result:
            logger.warning(
                f"Enhancement gave up after {max_retries} retries, "
                f"returning incomplete data for {product_name or 'unknown'}"
            )
        return last_result

    def _call_enhancement_api(
        self,
        content: str,
        product_type: str,
        product_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the AI Enhancement API.

        Args:
            content: Raw content to enhance
            product_type: Product type
            product_name: Optional product name hint

        Returns:
            Enhanced data dictionary
        """
        import requests

        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                f"{self.base_url}/api/v1/enhance",
                json={
                    "content": content,
                    "product_type": product_type,
                    "product_name": product_name,
                },
                headers=headers,
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data") or data

            logger.error(
                f"Enhancement API error: HTTP {response.status_code}"
            )
            return None

        except requests.RequestException as e:
            logger.error(f"Enhancement API request failed: {e}")
            return None
