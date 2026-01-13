"""
SingleProductOrchestrator Service for Single Product Enrichment Flow.

Task 3.1: Main orchestrator for processing individual product entries.

Orchestrates:
- Product duplicate detection via ProductMatcher
- URL discovery via SerpAPI search
- Content extraction via AIClientV2
- Quality assessment via QualityGateV2/V3
- Enrichment for incomplete products

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 8.2
"""

import logging
from dataclasses import field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from asgiref.sync import sync_to_async
from django.utils import timezone

from crawler.models import CrawlJob, CrawlSchedule, DiscoveredProduct
from crawler.services.product_matcher import ProductMatcher, get_product_matcher
from crawler.services.quality_gate_v2 import ProductStatus, QualityGateV2, get_quality_gate_v2
from crawler.services.single_product_types import SingleProductResult, SingleProductJobResult
from crawler.services.refresh_enricher import RefreshEnricher, get_refresh_enricher

logger = logging.getLogger(__name__)


class SingleProductOrchestrator:
    """
    Orchestrator for Single Product Enrichment flow.

    Handles:
    1. Product entry processing (search, extract, create/update)
    2. Duplicate detection via ProductMatcher
    3. Refresh enrichment for existing products
    4. Skip logic for recently enriched products

    Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 8.2
    """

    # Default search templates for new product discovery
    NEW_PRODUCT_SEARCH_TEMPLATES = [
        "{brand} {name} official",
        "{name} {brand} review",
        "{name} whisky magazine",
    ]

    # Search templates for refresh (recent reviews)
    REFRESH_SEARCH_TEMPLATES = [
        "{brand} {name} review {year}",
        "{name} {year} tasting notes",
        "{name} latest review",
    ]

    def __init__(
        self,
        product_matcher: Optional[ProductMatcher] = None,
        quality_gate: Optional[QualityGateV2] = None,
        refresh_enricher: Optional[RefreshEnricher] = None,
        ai_client=None,
        enrichment_pipeline=None,
        serpapi_key: Optional[str] = None,
    ):
        """
        Initialize SingleProductOrchestrator.

        Args:
            product_matcher: ProductMatcher for duplicate detection
            quality_gate: QualityGateV2/V3 for quality assessment
            refresh_enricher: RefreshEnricher for existing product updates
            ai_client: AIClientV2 for extraction (lazy loaded)
            enrichment_pipeline: EnrichmentPipelineV3 (lazy loaded)
            serpapi_key: Optional SerpAPI key override
        """
        self.product_matcher = product_matcher or get_product_matcher()
        self.quality_gate = quality_gate or get_quality_gate_v2()
        self.refresh_enricher = refresh_enricher or get_refresh_enricher()
        self._ai_client = ai_client
        self._enrichment_pipeline = enrichment_pipeline
        self._serpapi_key = serpapi_key

        logger.debug("SingleProductOrchestrator initialized")

    @property
    def ai_client(self):
        """Lazy load AI client."""
        if self._ai_client is None:
            from crawler.services.ai_client_v2 import get_ai_client_v2
            self._ai_client = get_ai_client_v2()
        return self._ai_client

    @property
    def enrichment_pipeline(self):
        """Lazy load enrichment pipeline."""
        if self._enrichment_pipeline is None:
            from crawler.services.enrichment_pipeline_v3 import get_enrichment_pipeline_v3
            self._enrichment_pipeline = get_enrichment_pipeline_v3()
        return self._enrichment_pipeline

    async def process_product_entry(
        self,
        product_entry: Dict[str, Any],
        config: Dict[str, Any],
    ) -> SingleProductResult:
        """
        Process a single product entry (name/brand/product_type).

        Flow:
        1. Check for existing product via ProductMatcher
        2. If new: search for sources, extract, create, enrich
        3. If existing: optionally refresh with recent data

        Args:
            product_entry: Dict with name, brand, product_type
            config: Schedule config (focus_recent_reviews, skip_if_enriched_within_days, etc.)

        Returns:
            SingleProductResult with processing outcome
        """
        name = product_entry.get("name", "")
        brand = product_entry.get("brand", "")
        product_type = product_entry.get("product_type", "whiskey")

        result = SingleProductResult(product_name=name)

        try:
            # Step 1: Check for existing product
            existing_product, match_method, confidence = await self.product_matcher.find_match(
                extracted_data={"name": name, "brand": brand},
                product_type=product_type,
            )

            if existing_product:
                # Existing product found
                result.is_new_product = False
                result.product_id = existing_product.id
                result.match_method = match_method
                result.match_confidence = confidence
                result.status_before = existing_product.status

                # Check skip logic for recently enriched
                skip_days = config.get("skip_if_enriched_within_days", 30)
                if self._should_skip_enrichment(existing_product, skip_days):
                    result.success = True
                    result.status_after = existing_product.status
                    result.warnings = result.warnings or []
                    result.warnings.append("skipped_recent_enrichment")
                    logger.info(
                        "Skipping recently enriched product: %s (enriched %s ago)",
                        name, self._days_since_enrichment(existing_product)
                    )
                    return result

                # Refresh existing product
                await self._refresh_existing_product(
                    existing_product, product_type, config, result
                )

            else:
                # New product - search, extract, create
                result.is_new_product = True
                await self._process_new_product(
                    name, brand, product_type, config, result
                )

            result.success = True

        except Exception as e:
            logger.exception("Error processing product entry: %s", name)
            result.success = False
            result.error = str(e)

        return result

    async def process_schedule(
        self,
        schedule: CrawlSchedule,
        job: CrawlJob,
    ) -> SingleProductJobResult:
        """
        Process all product entries in a schedule.

        Args:
            schedule: CrawlSchedule with search_terms containing product entries
            job: CrawlJob for tracking

        Returns:
            SingleProductJobResult with aggregated results
        """
        job_result = SingleProductJobResult(
            job_id=job.id,
            schedule_id=schedule.id,
        )

        # Get product entries from schedule
        product_entries = schedule.get_product_entries()
        config = schedule.get_single_product_config()

        logger.info(
            "Processing %d product entries for schedule: %s",
            len(product_entries), schedule.name
        )

        for entry in product_entries:
            try:
                result = await self.process_product_entry(entry, config)
                job_result.add_result(result)

            except Exception as e:
                logger.error("Failed to process entry %s: %s", entry.get("name"), e)
                # Create failed result
                failed_result = SingleProductResult(
                    success=False,
                    product_name=entry.get("name", "Unknown"),
                    error=str(e),
                )
                job_result.add_result(failed_result)

        job_result.finalize()
        return job_result

    async def _process_new_product(
        self,
        name: str,
        brand: str,
        product_type: str,
        config: Dict[str, Any],
        result: SingleProductResult,
    ):
        """Process a new product: search, extract, create, enrich."""
        # Search for sources
        focus_recent = config.get("focus_recent_reviews", False)
        urls = await self._search_for_product(name, brand, product_type, focus_recent)

        result.sources_searched = len(urls)

        if not urls:
            # No sources found - create minimal product
            product, _ = await self.product_matcher.find_or_create(
                extracted_data={"name": name, "brand": brand},
                product_type=product_type,
                source_url="",
            )
            result.product_id = product.id
            result.status_after = "skeleton"
            return

        # Extract from discovered URLs
        best_data = {}
        best_confidences = {}

        for url in urls[:3]:  # Limit to top 3 URLs
            try:
                extracted, confidences = await self._fetch_and_extract(
                    url, product_type
                )
                if extracted:
                    # Merge with existing data
                    for field_name, value in extracted.items():
                        if field_name not in best_data or confidences.get(field_name, 0) > best_confidences.get(field_name, 0):
                            best_data[field_name] = value
                            best_confidences[field_name] = confidences.get(field_name, 0.7)
                    result.sources_used = (result.sources_used or 0) + 1

            except Exception as e:
                logger.warning("Extraction failed for %s: %s", url, e)

        # Ensure we have at least name and brand
        if "name" not in best_data:
            best_data["name"] = name
        if "brand" not in best_data:
            best_data["brand"] = brand

        # Create or find product
        product, is_new = await self.product_matcher.find_or_create(
            extracted_data=best_data,
            product_type=product_type,
            source_url=urls[0] if urls else "",
        )

        result.product_id = product.id
        result.fields_enriched = list(best_data.keys())

        # Assess quality
        assessment = self.quality_gate.assess(
            extracted_data=best_data,
            product_type=product_type,
            field_confidences=best_confidences,
        )
        result.status_after = assessment.status.value

    async def _refresh_existing_product(
        self,
        product: DiscoveredProduct,
        product_type: str,
        config: Dict[str, Any],
        result: SingleProductResult,
    ):
        """Refresh an existing product with recent data using RefreshEnricher."""
        # Get brand name in sync context
        @sync_to_async
        def get_brand_name():
            if product.brand_id:
                return product.brand.name if product.brand else ""
            return ""

        brand_name = await get_brand_name()

        # Search for recent sources
        focus_recent = config.get("focus_recent_reviews", True)
        urls = await self._search_for_product(
            product.name, brand_name, product_type, focus_recent=focus_recent
        )

        result.sources_searched = len(urls)

        if not urls:
            result.status_after = product.status
            return

        # Extract from recent sources
        all_extracted = {}
        all_confidences = {}

        for url in urls[:2]:  # Limit for refresh
            try:
                extracted, confidences = await self._fetch_and_extract(
                    url, product_type
                )
                if extracted:
                    # Accumulate extractions (higher confidence wins)
                    for field, value in extracted.items():
                        if field not in all_extracted or confidences.get(field, 0) > all_confidences.get(field, 0):
                            all_extracted[field] = value
                            all_confidences[field] = confidences.get(field, 0.7)
                    result.sources_used = (result.sources_used or 0) + 1

            except Exception as e:
                logger.warning("Refresh extraction failed for %s: %s", url, e)

        # Use RefreshEnricher to merge with existing data
        if all_extracted:
            refresh_result = await self.refresh_enricher.refresh_product(
                existing_product=product,
                new_extraction=all_extracted,
                new_confidences=all_confidences,
                focus_recent=focus_recent,
            )

            if refresh_result.success:
                result.fields_enriched = refresh_result.fields_enriched
                # Update product status based on refresh
                assessment = self.quality_gate.assess(
                    extracted_data=refresh_result.product_data,
                    product_type=product_type,
                    field_confidences=refresh_result.confidences,
                )
                result.status_after = assessment.status.value
            else:
                result.status_after = product.status
        else:
            result.status_after = product.status

    async def _search_for_product(
        self,
        name: str,
        brand: str,
        product_type: str,
        focus_recent: bool = False,
    ) -> List[str]:
        """
        Search for product information using SerpAPI.

        Args:
            name: Product name
            brand: Brand name
            product_type: Product type
            focus_recent: If True, focus on recent reviews

        Returns:
            List of discovered URLs
        """
        from datetime import datetime
        import os
        from django.conf import settings

        # Get SerpAPI key
        api_key = self._serpapi_key or getattr(settings, "SERPAPI_KEY", None) or os.getenv("SERPAPI_KEY")
        if not api_key:
            logger.warning("No SerpAPI key available for product search")
            return []

        # Select search templates
        templates = self.REFRESH_SEARCH_TEMPLATES if focus_recent else self.NEW_PRODUCT_SEARCH_TEMPLATES

        # Build search queries
        year = datetime.now().year
        queries = []
        for template in templates[:2]:  # Limit searches
            query = template.format(name=name, brand=brand, year=year)
            queries.append(query)

        # Execute searches
        urls = []
        for query in queries:
            try:
                search_urls = await self._execute_serpapi_search(query, api_key)
                urls.extend(search_urls)
            except Exception as e:
                logger.warning("SerpAPI search failed: %s", e)

        # Deduplicate
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls[:10]  # Limit total URLs

    async def _execute_serpapi_search(
        self,
        query: str,
        api_key: str,
    ) -> List[str]:
        """Execute a single SerpAPI search."""
        import httpx

        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 5,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        urls = []
        for result in data.get("organic_results", []):
            url = result.get("link")
            if url:
                urls.append(url)

        return urls

    async def _fetch_and_extract(
        self,
        url: str,
        product_type: str,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Fetch URL content and extract product data.

        Args:
            url: URL to fetch
            product_type: Product type for extraction

        Returns:
            Tuple of (extracted_data, field_confidences)
        """
        from crawler.fetchers.smart_router import SmartRouter

        # Fetch content
        router = SmartRouter()
        fetch_result = await router.fetch(url)

        if not fetch_result.success or not fetch_result.content:
            return {}, {}

        # Extract using AI client
        extraction = await self.ai_client.extract(
            url=url,
            content=fetch_result.content,
            product_type=product_type,
        )

        if "error" in extraction:
            return {}, {}

        # Get confidences
        confidences = extraction.pop("field_confidences", {})

        return extraction, confidences

    def _should_skip_enrichment(
        self,
        product: DiscoveredProduct,
        skip_days: int,
    ) -> bool:
        """Check if product was enriched recently enough to skip."""
        if not product.last_enrichment_at:
            return False

        cutoff = timezone.now() - timedelta(days=skip_days)
        return product.last_enrichment_at > cutoff

    def _days_since_enrichment(self, product: DiscoveredProduct) -> str:
        """Get human-readable time since last enrichment."""
        if not product.last_enrichment_at:
            return "never"

        delta = timezone.now() - product.last_enrichment_at
        return f"{delta.days} days"


# Singleton instance
_single_product_orchestrator: Optional[SingleProductOrchestrator] = None


def get_single_product_orchestrator() -> SingleProductOrchestrator:
    """Get singleton SingleProductOrchestrator instance."""
    global _single_product_orchestrator
    if _single_product_orchestrator is None:
        _single_product_orchestrator = SingleProductOrchestrator()
    return _single_product_orchestrator


def reset_single_product_orchestrator() -> None:
    """Reset singleton (for testing)."""
    global _single_product_orchestrator
    _single_product_orchestrator = None
