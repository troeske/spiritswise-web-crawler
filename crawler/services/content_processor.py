"""
Content Processing Pipeline.

Task 7.3: Implements content processing for AI Enhancement integration.

Pipeline steps:
1. Clean raw HTML content using trafilatura extraction
2. Determine product_type_hint from CrawlerSource.product_types
3. Call AI Enhancement Service
4. Parse response and update DiscoveredProduct.extracted_data
5. Track costs for AI calls
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlCost,
    CostService,
)
from crawler.services.ai_client import AIEnhancementClient, EnhancementResult, get_ai_client

logger = logging.getLogger(__name__)

# Trafilatura import with fallback
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not available, will use raw content")


@dataclass
class ProcessingResult:
    """Result of content processing."""

    success: bool
    product_id: Optional[str] = None
    is_new: bool = False
    product_type: str = ""
    confidence: float = 0.0
    error: Optional[str] = None
    cost_cents: int = 0


class ContentProcessor:
    """
    Content processing pipeline for AI Enhancement integration.

    Handles the full flow from raw HTML to enriched DiscoveredProduct:
    1. Extract main content from HTML using trafilatura
    2. Determine product type hint from source configuration
    3. Call AI Enhancement Service
    4. Create/update DiscoveredProduct
    5. Track API costs
    """

    # Estimated cost per AI enhancement call in cents
    # Based on average GPT-4 usage (~2000 tokens @ $0.03/1k input + $0.06/1k output)
    ESTIMATED_COST_CENTS = 12

    def __init__(self, ai_client: Optional[AIEnhancementClient] = None):
        """
        Initialize content processor.

        Args:
            ai_client: Optional pre-configured AI Enhancement client
        """
        self.ai_client = ai_client or get_ai_client()

    def extract_content(self, raw_html: str) -> str:
        """
        Extract main content from raw HTML using trafilatura.

        Args:
            raw_html: Raw HTML content from crawler

        Returns:
            Cleaned text content
        """
        if not TRAFILATURA_AVAILABLE or not raw_html:
            return raw_html

        try:
            # Use trafilatura to extract main content
            extracted = trafilatura.extract(
                raw_html,
                include_links=False,
                include_images=False,
                include_tables=True,
                output_format="txt",
            )

            if extracted and len(extracted) >= 50:
                logger.debug(f"Extracted {len(extracted)} chars from {len(raw_html)} char HTML")
                return extracted

            # If extraction is too short, fall back to raw HTML
            logger.debug("Trafilatura extraction too short, using raw HTML")
            return raw_html

        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {e}, using raw HTML")
            return raw_html

    def determine_product_type_hint(self, source: Optional[CrawlerSource]) -> str:
        """
        Determine product type hint from CrawlerSource.product_types.

        Args:
            source: CrawlerSource instance

        Returns:
            Product type string (e.g., 'whiskey', 'port_wine')
        """
        if not source:
            return "whiskey"

        product_types = source.product_types or []

        if not product_types:
            return "whiskey"

        # Return the first product type
        return product_types[0]

    async def process(
        self,
        url: str,
        raw_content: str,
        source: Optional[CrawlerSource] = None,
        crawl_job: Optional[CrawlJob] = None,
    ) -> ProcessingResult:
        """
        Process crawled content through the AI Enhancement pipeline.

        Args:
            url: Source URL of the content
            raw_content: Raw HTML content from crawler
            source: CrawlerSource instance
            crawl_job: CrawlJob instance for tracking

        Returns:
            ProcessingResult with outcome
        """
        logger.info(f"Processing content from {url}")

        # Step 1: Extract content using trafilatura
        extracted_content = self.extract_content(raw_content)

        # Limit content size
        max_content_length = 50000
        if len(extracted_content) > max_content_length:
            extracted_content = extracted_content[:max_content_length]

        # Step 2: Determine product type hint
        product_type_hint = self.determine_product_type_hint(source)

        # Step 3: Call AI Enhancement Service
        result = await self.ai_client.enhance_from_crawler(
            content=extracted_content,
            source_url=url,
            product_type_hint=product_type_hint,
        )

        # Step 4: Track costs
        await self._track_cost(crawl_job, result)

        # Handle failure
        if not result.success:
            logger.warning(f"AI Enhancement failed for {url}: {result.error}")
            return ProcessingResult(
                success=False,
                error=result.error,
                cost_cents=self.ESTIMATED_COST_CENTS,
            )

        # Step 5: Create/update DiscoveredProduct
        product_id, is_new = await self._save_product(
            url=url,
            raw_content=raw_content,
            result=result,
            source=source,
            crawl_job=crawl_job,
        )

        return ProcessingResult(
            success=True,
            product_id=product_id,
            is_new=is_new,
            product_type=result.product_type,
            confidence=result.confidence,
            cost_cents=self.ESTIMATED_COST_CENTS,
        )

    async def _track_cost(
        self,
        crawl_job: Optional[CrawlJob],
        result: EnhancementResult,
    ) -> None:
        """
        Track AI Enhancement API cost.

        Creates CrawlCost record for budget monitoring.

        Args:
            crawl_job: CrawlJob to link cost to
            result: EnhancementResult from API
        """
        try:
            @sync_to_async
            def create_cost():
                CrawlCost.objects.create(
                    service=CostService.OPENAI,
                    cost_cents=self.ESTIMATED_COST_CENTS,
                    crawl_job=crawl_job,
                    request_count=1,
                    timestamp=timezone.now(),
                )

            await create_cost()
            logger.debug(f"Tracked AI cost: {self.ESTIMATED_COST_CENTS} cents")

        except Exception as e:
            # Don't fail if cost tracking fails
            logger.warning(f"Failed to track AI cost: {e}")

    async def _save_product(
        self,
        url: str,
        raw_content: str,
        result: EnhancementResult,
        source: Optional[CrawlerSource],
        crawl_job: Optional[CrawlJob],
    ) -> Tuple[str, bool]:
        """
        Save or update DiscoveredProduct from AI Enhancement result.

        Args:
            url: Source URL
            raw_content: Raw HTML content
            result: EnhancementResult from AI service
            source: CrawlerSource instance
            crawl_job: CrawlJob instance

        Returns:
            Tuple of (product_id, is_new)
        """
        extracted_data = result.extracted_data.copy()
        extracted_data["source_url"] = url

        # Compute fingerprint for deduplication
        fingerprint = DiscoveredProduct.compute_fingerprint(extracted_data)

        # Compute content hash
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        @sync_to_async
        def save_product():
            with transaction.atomic():
                # Check for existing product with same fingerprint
                existing = DiscoveredProduct.objects.filter(
                    fingerprint=fingerprint
                ).first()

                if existing:
                    # Update existing product with additional data
                    existing.enriched_data = {
                        **existing.enriched_data,
                        **result.enrichment,
                        "additional_sources": existing.enriched_data.get(
                            "additional_sources", []
                        ) + [url],
                    }
                    existing.extraction_confidence = max(
                        existing.extraction_confidence or 0,
                        result.confidence,
                    )
                    existing.save(
                        update_fields=["enriched_data", "extraction_confidence"]
                    )

                    logger.info(
                        f"Updated existing product {existing.id} with data from {url}"
                    )
                    return str(existing.id), False

                else:
                    # Create new product
                    product_type = result.product_type

                    # Validate product type
                    valid_types = [pt.value for pt in ProductType]
                    if product_type not in valid_types:
                        product_type = ProductType.WHISKEY

                    product = DiscoveredProduct.objects.create(
                        source=source,
                        source_url=url,
                        crawl_job=crawl_job,
                        product_type=product_type,
                        raw_content=raw_content[:50000],  # Limit stored content
                        raw_content_hash=content_hash,
                        extracted_data=extracted_data,
                        enriched_data=result.enrichment,
                        extraction_confidence=result.confidence,
                        fingerprint=fingerprint,
                        status=DiscoveredProductStatus.PENDING,
                        discovery_source=DiscoverySource.DIRECT,
                    )

                    logger.info(
                        f"Created new product {product.id}: "
                        f"{extracted_data.get('name', 'Unknown')}"
                    )
                    return str(product.id), True

        return await save_product()


def get_content_processor() -> ContentProcessor:
    """
    Factory function to get configured ContentProcessor.

    Returns:
        ContentProcessor configured from Django settings
    """
    return ContentProcessor()
