"""
Discovery Orchestrator V2 - Orchestrates product discovery with V2 components.

Phase 5 of V2 Architecture: Integrates AIClientV2, QualityGateV2,
EnrichmentOrchestratorV2, and SourceTracker for complete product discovery.

Features:
- Single product extraction with quality assessment
- List page extraction with skeleton product creation
- Source tracking and field provenance
- Enrichment queue decision logic
- Content preprocessing integration
- URL resolution for relative links
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from crawler.fetchers.smart_router import SmartRouter
from crawler.services.ai_client_v2 import AIClientV2, ExtractionResultV2, get_ai_client_v2
from crawler.services.quality_gate_v2 import ProductStatus, QualityGateV2, get_quality_gate_v2
from crawler.services.enrichment_orchestrator_v2 import (
    EnrichmentOrchestratorV2,
    get_enrichment_orchestrator_v2,
)
from crawler.services.source_tracker import SourceTracker, get_source_tracker

logger = logging.getLogger(__name__)


@dataclass
class SingleProductResult:
    """Result of single product extraction."""

    success: bool
    product_data: Optional[Dict[str, Any]] = None
    quality_status: Optional[str] = None
    needs_enrichment: bool = False
    error: Optional[str] = None
    product_id: Optional[int] = None
    field_confidences: Dict[str, float] = field(default_factory=dict)
    detail_url: Optional[str] = None


@dataclass
class ListProductResult:
    """Result of list page extraction."""

    success: bool
    products: List[SingleProductResult] = field(default_factory=list)
    error: Optional[str] = None
    source_url: Optional[str] = None


class DiscoveryOrchestratorV2:
    """
    V2 Discovery Orchestrator integrating all V2 components.

    Orchestrates:
    - Page fetching and content preprocessing
    - AI extraction via AIClientV2
    - Quality assessment via QualityGateV2
    - Enrichment decisions and queueing
    - Source tracking and field provenance

    Supports both single product pages and list pages.
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        ai_client: Optional[AIClientV2] = None,
        quality_gate: Optional[QualityGateV2] = None,
        enrichment_orchestrator: Optional[EnrichmentOrchestratorV2] = None,
        source_tracker: Optional[SourceTracker] = None,
    ):
        """
        Initialize the Discovery Orchestrator V2.

        Args:
            ai_client: AIClientV2 instance (optional, creates default)
            quality_gate: QualityGateV2 instance (optional, creates default)
            enrichment_orchestrator: EnrichmentOrchestratorV2 instance (optional)
            source_tracker: SourceTracker instance (optional, creates default)
        """
        self.ai_client = ai_client or get_ai_client_v2()
        self.quality_gate = quality_gate or get_quality_gate_v2()
        self.enrichment_orchestrator = enrichment_orchestrator or get_enrichment_orchestrator_v2()
        self.source_tracker = source_tracker or get_source_tracker()

        logger.debug("DiscoveryOrchestratorV2 initialized with V2 components")

    async def extract_single_product(
        self,
        url: str,
        product_type: str,
        product_category: Optional[str] = None,
        save_to_db: bool = False,
    ) -> SingleProductResult:
        """
        Extract a single product from a URL.

        Args:
            url: URL of the product page
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint
            save_to_db: Whether to save the product to the database

        Returns:
            SingleProductResult with extraction results and quality assessment
        """
        logger.info("Extracting single product from %s (type=%s)", url, product_type)

        try:
            # Step 1: Fetch page content
            content = await self._fetch_page(url)
            if not content:
                return SingleProductResult(
                    success=False,
                    error="Failed to fetch page content"
                )

            # Step 2: Extract using AIClientV2
            extraction_result = await self.ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                product_category=product_category,
            )

            if not extraction_result.success or not extraction_result.products:
                return SingleProductResult(
                    success=False,
                    error=extraction_result.error or "No products extracted"
                )

            # Step 3: Get the primary product
            primary_product = extraction_result.products[0]
            product_data = primary_product.extracted_data
            field_confidences = primary_product.field_confidences

            # Step 4: Assess quality
            quality_status = self._assess_quality(
                product_data=product_data,
                field_confidences=field_confidences,
                product_type=product_type
            )

            # Step 5: Determine enrichment need
            needs_enrichment = self._should_enrich(quality_status)

            # Step 6: Optionally save to database
            product_id = None
            if save_to_db:
                product_id = await self._save_product(
                    url=url,
                    product_data=product_data,
                    product_type=product_type,
                    quality_status=quality_status,
                    field_confidences=field_confidences,
                    raw_content=content,
                )

            return SingleProductResult(
                success=True,
                product_data=product_data,
                quality_status=quality_status,
                needs_enrichment=needs_enrichment,
                product_id=product_id,
                field_confidences=field_confidences,
            )

        except Exception as e:
            logger.exception("Error extracting single product from %s: %s", url, e)
            return SingleProductResult(
                success=False,
                error=str(e)
            )

    async def extract_list_products(
        self,
        url: str,
        product_type: str,
        product_category: Optional[str] = None,
    ) -> ListProductResult:
        """
        Extract multiple products from a list page.

        Args:
            url: URL of the list page
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint

        Returns:
            ListProductResult with all extracted products
        """
        logger.info("Extracting list products from %s (type=%s)", url, product_type)

        try:
            # Step 1: Fetch page content
            content = await self._fetch_page(url)
            if not content:
                return ListProductResult(
                    success=False,
                    error="Failed to fetch page content",
                    source_url=url
                )

            # Step 2: Extract using AIClientV2
            extraction_result = await self.ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                product_category=product_category,
            )

            if not extraction_result.success:
                return ListProductResult(
                    success=False,
                    error=extraction_result.error or "Extraction failed",
                    source_url=url
                )

            # Step 3: Process each extracted product
            product_results = []
            for extracted_product in extraction_result.products:
                product_data = extracted_product.extracted_data
                field_confidences = extracted_product.field_confidences

                # Assess quality
                quality_status = self._assess_quality(
                    product_data=product_data,
                    field_confidences=field_confidences,
                    product_type=product_type
                )

                # Resolve relative URL if present
                detail_url = self._resolve_url(
                    base_url=url,
                    relative_url=product_data.get("detail_url")
                )

                # Determine enrichment need
                needs_enrichment = self._should_enrich(quality_status)

                product_results.append(SingleProductResult(
                    success=True,
                    product_data=product_data,
                    quality_status=quality_status,
                    needs_enrichment=needs_enrichment,
                    field_confidences=field_confidences,
                    detail_url=detail_url,
                ))

            return ListProductResult(
                success=True,
                products=product_results,
                source_url=url
            )

        except Exception as e:
            logger.exception("Error extracting list products from %s: %s", url, e)
            return ListProductResult(
                success=False,
                error=str(e),
                source_url=url
            )

    async def _fetch_page(self, url: str, use_javascript: bool = True) -> Optional[str]:
        """
        Fetch page content from URL using SmartRouter for JavaScript rendering.

        Uses SmartRouter which supports:
        - Tier 1: httpx (fast, for static pages)
        - Tier 2: Playwright (JavaScript rendering)
        - Tier 3: ScrapingBee (premium proxy + JS rendering for blocked sites)

        Args:
            url: URL to fetch
            use_javascript: If True, force Tier 3 (ScrapingBee) for JavaScript rendering

        Returns:
            HTML content or None if failed
        """
        try:
            # Use SmartRouter for fetching - it handles JavaScript rendering
            router = SmartRouter(timeout=self.DEFAULT_TIMEOUT)

            # For JavaScript-heavy pages (like competition sites), use Tier 3
            # which has ScrapingBee with render_js and wait capabilities
            force_tier = 3 if use_javascript else None

            result = await router.fetch(url, force_tier=force_tier)

            if result.success and result.content:
                logger.info(
                    "Fetched %s via SmartRouter (tier=%s, content_size=%d)",
                    url, result.tier_used, len(result.content)
                )
                return result.content
            else:
                logger.warning(
                    "SmartRouter failed for %s: %s (tier=%s)",
                    url, result.error, result.tier_used
                )
                # Fallback to httpx for simple pages
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
            logger.error("Failed to fetch %s: %s", url, e)
            raise
        finally:
            # Clean up SmartRouter connections
            try:
                await router.close()
            except Exception:
                pass

    def _assess_quality(
        self,
        product_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        product_type: str,
    ) -> str:
        """
        Assess product data quality using QualityGateV2.

        Args:
            product_data: Extracted product data
            field_confidences: Field confidence scores
            product_type: Product type

        Returns:
            Quality status string (e.g., "complete", "partial", "skeleton")
        """
        try:
            assessment = self.quality_gate.assess(
                extracted_data=product_data,
                product_type=product_type,
                field_confidences=field_confidences,
            )
            return assessment.status.value
        except Exception as e:
            logger.warning("Quality assessment failed: %s, defaulting to rejected", e)
            return ProductStatus.REJECTED.value

    def _should_enrich(self, quality_status: str) -> bool:
        """
        Determine if a product should be enriched based on quality status.

        Enrichment is needed for:
        - SKELETON: Minimal data, needs significant enrichment
        - PARTIAL: Missing some required fields

        No enrichment for:
        - COMPLETE: Has all required fields
        - ENRICHED: Already enriched
        - REJECTED: Invalid data, not worth enriching

        Args:
            quality_status: Quality status string

        Returns:
            True if enrichment is needed
        """
        status_needs_enrichment = {
            ProductStatus.SKELETON.value: True,
            ProductStatus.PARTIAL.value: True,
            ProductStatus.COMPLETE.value: False,
            ProductStatus.ENRICHED.value: False,
            ProductStatus.REJECTED.value: False,
        }
        return status_needs_enrichment.get(quality_status, False)

    def _resolve_url(
        self,
        base_url: str,
        relative_url: Optional[str]
    ) -> Optional[str]:
        """
        Resolve a relative URL to absolute.

        Args:
            base_url: Base URL for resolution
            relative_url: Relative URL to resolve

        Returns:
            Absolute URL or None
        """
        if not relative_url:
            return None

        # Already absolute
        if relative_url.startswith(("http://", "https://")):
            return relative_url

        return urljoin(base_url, relative_url)

    async def _save_product(
        self,
        url: str,
        product_data: Dict[str, Any],
        product_type: str,
        quality_status: str,
        field_confidences: Dict[str, float],
        raw_content: str,
    ) -> Optional[int]:
        """
        Save extracted product to database.

        Args:
            url: Source URL
            product_data: Extracted product data
            product_type: Product type
            quality_status: Quality status
            field_confidences: Field confidences
            raw_content: Raw HTML content

        Returns:
            Product ID if saved, None otherwise
        """
        try:
            from crawler.models import DiscoveredProduct, DiscoveredBrand

            # Find or create brand
            brand_name = product_data.get("brand")
            brand = None
            if brand_name:
                brand, _ = DiscoveredBrand.objects.get_or_create(
                    name=brand_name,
                    defaults={"slug": brand_name.lower().replace(" ", "-")}
                )

            # Create product
            product = DiscoveredProduct.objects.create(
                name=product_data.get("name", "Unknown"),
                brand=brand,
                abv=product_data.get("abv"),
                product_type=product_type,
                description=product_data.get("description"),
                data_quality_status=quality_status,
                confidence_score=sum(field_confidences.values()) / len(field_confidences) if field_confidences else 0.0,
            )

            # Track source
            try:
                source = self.source_tracker.store_crawled_source(
                    url=url,
                    title=product_data.get("name", ""),
                    raw_content=raw_content,
                    source_type="product_page",
                )
                self.source_tracker.link_product_to_source(
                    product_id=product.id,
                    source_id=source.id,
                    extraction_confidence=product_data.get("confidence", 0.0),
                    fields_extracted=list(product_data.keys()),
                )
            except Exception as e:
                logger.warning("Failed to track source: %s", e)

            logger.info("Saved product %s (id=%s)", product.name, product.id)
            return product.id

        except Exception as e:
            logger.exception("Failed to save product: %s", e)
            return None


# Singleton instance
_discovery_orchestrator_v2: Optional[DiscoveryOrchestratorV2] = None


def get_discovery_orchestrator_v2() -> DiscoveryOrchestratorV2:
    """Get or create the singleton DiscoveryOrchestratorV2 instance."""
    global _discovery_orchestrator_v2
    if _discovery_orchestrator_v2 is None:
        _discovery_orchestrator_v2 = DiscoveryOrchestratorV2()
    return _discovery_orchestrator_v2


def reset_discovery_orchestrator_v2():
    """Reset the singleton instance (for testing)."""
    global _discovery_orchestrator_v2
    _discovery_orchestrator_v2 = None
