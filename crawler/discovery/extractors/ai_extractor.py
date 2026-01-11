"""
AI Extractor for Award Site Detail Pages.

Unified AI extractor that uses LLM prompts to extract structured product data
from award site detail pages. Supports multiple sources with source-specific
prompt templates.

Features:
- Source-specific prompt selection (IWSC, DWWA, general)
- Product type aware extraction
- Robust JSON parsing with markdown handling
- Content truncation for token limits
- Source metadata tracking
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Union

from .extraction_prompts import (
    IWSC_EXTRACTION_PROMPT,
    DWWA_PORT_EXTRACTION_PROMPT,
    GENERAL_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)


class AIExtractor:
    """
    Unified AI extractor for award site detail pages.

    Uses LLM to extract structured product data from HTML content.
    Selects appropriate prompts based on source and product type.
    """

    # Maximum content length to prevent token overflow
    MAX_CONTENT_LENGTH = 15000

    def __init__(self, ai_client=None):
        """
        Initialize with optional AI client.

        Args:
            ai_client: AI client for extraction. If not provided,
                      creates AIEnhancementClient from crawler.services.
        """
        self.ai_client = ai_client
        if self.ai_client is None:
            from crawler.services.ai_client import AIEnhancementClient
            self.ai_client = AIEnhancementClient()

    async def extract(
        self,
        url: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract product data from a URL.

        Args:
            url: Detail page URL to extract from
            context: Dict with source, year, medal_hint, score_hint, product_type_hint

        Returns:
            Dict with extracted product data including source metadata
        """
        # Fetch page content
        content = await self._fetch_content(url)

        # Select appropriate prompt based on source and product type
        source = context.get("source", "general")
        product_type = context.get("product_type_hint", "unknown")
        prompt_template = self._select_prompt(source, product_type)

        # Format prompt with context values
        prompt = prompt_template.format(
            year=context.get("year", "Unknown"),
            medal_hint=context.get("medal_hint", "Unknown"),
            score_hint=context.get("score_hint", "Unknown"),
            product_type_hint=product_type,
            content=content[:self.MAX_CONTENT_LENGTH],
        )

        # Call AI for extraction
        response = await self._call_ai(prompt)

        # Parse response into structured data
        data = self._parse_ai_response(response)

        # Add source metadata
        data["source_url"] = url
        data["extraction_source"] = source

        return data

    def _select_prompt(self, source: str, product_type: str) -> str:
        """
        Select the appropriate extraction prompt based on source and product type.

        Args:
            source: Source identifier (iwsc, dwwa, etc.)
            product_type: Product type hint (whiskey, port_wine, etc.)

        Returns:
            Prompt template string
        """
        source_lower = source.lower() if source else ""

        if source_lower == "iwsc":
            return IWSC_EXTRACTION_PROMPT
        elif source_lower == "dwwa" and product_type == "port_wine":
            return DWWA_PORT_EXTRACTION_PROMPT
        else:
            return GENERAL_EXTRACTION_PROMPT

    async def _fetch_content(self, url: str) -> str:
        """
        Fetch page content using SmartRouter.

        Args:
            url: URL to fetch

        Returns:
            Page content as string, empty string on failure
        """
        try:
            from crawler.fetchers.smart_router import SmartRouter
            router = SmartRouter()
            result = await router.fetch(url)
            return result.content if result.success else ""
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return ""

    async def _call_ai(self, prompt: str) -> Union[str, Dict[str, Any]]:
        """
        Call AI service for extraction.

        Args:
            prompt: Formatted extraction prompt

        Returns:
            AI response (string or dict depending on client implementation)
        """
        try:
            # Use the enhance_from_crawler method for extraction
            result = await self.ai_client.enhance_from_crawler(
                content=prompt,
                source_url="extraction_prompt",
                product_type_hint=None,
            )
            if result.success:
                return result.extracted_data
            else:
                logger.warning(f"AI extraction failed: {result.error}")
                return {"error": result.error}
        except Exception as e:
            logger.error(f"AI service call failed: {e}")
            return {"error": str(e)}

    def _parse_ai_response(
        self, response: Union[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Parse AI response into structured data.

        Handles:
        - Dict passthrough
        - Plain JSON strings
        - JSON wrapped in markdown code blocks

        Args:
            response: AI response (string or dict)

        Returns:
            Parsed dict, or error dict if parsing fails
        """
        # If already a dict, pass through
        if isinstance(response, dict):
            return response

        # Convert to string for processing
        response_str = str(response)

        # Handle markdown code blocks: ```json ... ``` or ``` ... ```
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_str)
        if json_match:
            response_str = json_match.group(1)

        # Try to parse as JSON
        try:
            return json.loads(response_str.strip())
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse AI response as JSON: {response_str[:200]}... "
                f"Error: {e}"
            )
            return {"raw_response": response_str, "parse_error": True}
