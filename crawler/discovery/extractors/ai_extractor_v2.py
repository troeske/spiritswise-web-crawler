"""
AI Extractor V2 for Award Site Detail Pages.

Uses AIClientV2 for extraction with database-backed configuration.
Integrates with V2 architecture for quality assessment and enrichment.

Phase 7: Competition Flow Update
"""

import logging
from typing import Any, Dict, Optional

from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2

logger = logging.getLogger(__name__)


class AIExtractorV2:
    """
    V2 AI extractor for award site detail pages.

    Uses AIClientV2 for extraction with:
    - Content preprocessing (93% token savings)
    - Database-backed field schemas
    - Field confidence scores
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(self, ai_client: Optional[AIClientV2] = None):
        """
        Initialize with optional AI client.

        Args:
            ai_client: AIClientV2 instance. If not provided, uses singleton.
        """
        self.ai_client = ai_client or get_ai_client_v2()

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
            Dict with extracted product data including field confidences
        """
        try:
            # Fetch page content
            content = await self._fetch_content(url)
            if not content:
                return {
                    "error": "Failed to fetch content",
                    "source_url": url,
                }

            # Determine product type from context
            product_type = context.get("product_type_hint", "whiskey")
            product_category = self._infer_category(context, product_type)

            # Call AIClientV2 for extraction
            result = await self.ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                product_category=product_category,
            )

            if not result.success or not result.products:
                return {
                    "error": result.error or "No products extracted",
                    "source_url": url,
                }

            # Get primary product
            primary = result.products[0]
            extracted_data = primary.extracted_data.copy()

            # Add source metadata
            extracted_data["source_url"] = url
            extracted_data["extraction_source"] = context.get("source", "unknown")
            extracted_data["field_confidences"] = primary.field_confidences
            extracted_data["overall_confidence"] = primary.confidence

            # Add context hints if not already present
            if "medal_hint" in context and "award_medal" not in extracted_data:
                extracted_data["award_medal"] = context["medal_hint"]
            if "score_hint" in context and "award_score" not in extracted_data:
                try:
                    extracted_data["award_score"] = int(context["score_hint"])
                except (ValueError, TypeError):
                    pass

            return extracted_data

        except Exception as e:
            logger.exception("Extraction failed for %s: %s", url, e)
            return {
                "error": str(e),
                "source_url": url,
            }

    async def _fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch page content using SmartRouter or httpx.

        Args:
            url: URL to fetch

        Returns:
            Page content as string, or None on failure
        """
        try:
            # Try SmartRouter first
            try:
                from crawler.fetchers.smart_router import SmartRouter
                router = SmartRouter()
                result = await router.fetch(url)
                if result.success:
                    return result.content
            except ImportError:
                pass

            # Fallback to httpx
            import httpx
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; SpiritswiseCrawler/2.0)"
                    }
                )
                response.raise_for_status()
                return response.text

        except Exception as e:
            logger.error("Failed to fetch content from %s: %s", url, e)
            raise

    def _infer_category(
        self,
        context: Dict[str, Any],
        product_type: str
    ) -> Optional[str]:
        """
        Infer product category from context hints.

        Args:
            context: Extraction context with hints
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            Inferred category or None
        """
        source = context.get("source", "").lower()
        medal_hint = (context.get("medal_hint") or "").lower()

        # IWSC often has scotch and bourbon
        if source == "iwsc":
            return "single_malt"  # Default for IWSC whiskey

        # SFWSC often has bourbon
        if source == "sfwsc" and product_type == "whiskey":
            return "bourbon"

        # DWWA is primarily port wine
        if source == "dwwa" and product_type == "port_wine":
            return "tawny"

        return None


# Singleton getter
_ai_extractor_v2: Optional[AIExtractorV2] = None


def get_ai_extractor_v2() -> AIExtractorV2:
    """Get or create singleton AIExtractorV2 instance."""
    global _ai_extractor_v2
    if _ai_extractor_v2 is None:
        _ai_extractor_v2 = AIExtractorV2()
    return _ai_extractor_v2


def reset_ai_extractor_v2():
    """Reset singleton instance (for testing)."""
    global _ai_extractor_v2
    _ai_extractor_v2 = None
