"""
Enrichment Orchestrator V2 - Progressive multi-source product enrichment.

Phase 4 of V2 Architecture: Implements progressive enrichment using
database-driven EnrichmentConfig for search templates, AIClientV2 for
extraction, and confidence-based data merging.

Features:
- Database-driven enrichment configuration via EnrichmentConfig
- Progressive multi-source enrichment with configurable limits
- Confidence-based data merging (higher confidence wins)
- Integration with AIClientV2 for extraction
- Integration with QualityGateV2 for status assessment
- Automatic stop when COMPLETE status reached or limits exceeded
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
from asgiref.sync import sync_to_async

from crawler.models import EnrichmentConfig, ProductTypeConfig
from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2
from crawler.services.quality_gate_v2 import (
    ProductStatus,
    QualityGateV2,
    get_quality_gate_v2,
)

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of enrichment operation."""

    success: bool
    product_data: Dict[str, Any] = field(default_factory=dict)
    sources_used: List[str] = field(default_factory=list)
    sources_searched: List[str] = field(default_factory=list)
    fields_enriched: List[str] = field(default_factory=list)
    status_before: str = ""
    status_after: str = ""
    searches_performed: int = 0
    time_elapsed_seconds: float = 0.0
    error: Optional[str] = None
    # Track sources that were rejected due to product mismatch
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EnrichmentSession:
    """Tracks state during enrichment."""

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any]
    field_confidences: Dict[str, float]
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)
    fields_enriched: List[str] = field(default_factory=list)
    searches_performed: int = 0
    max_sources: int = 5
    max_searches: int = 3
    max_time_seconds: float = 120.0
    start_time: float = 0.0


class EnrichmentOrchestratorV2:
    """
    Progressive multi-source product enrichment orchestrator.

    Uses database-driven EnrichmentConfig for search templates,
    AIClientV2 for extraction, and confidence-based data merging.
    Stops when COMPLETE status reached or limits exceeded.
    """

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_SOURCES = 5
    DEFAULT_MAX_SEARCHES = 3
    DEFAULT_MAX_TIME_SECONDS = 120.0

    def __init__(
        self,
        ai_client: Optional[AIClientV2] = None,
        serp_client: Optional[Any] = None,
        quality_gate: Optional[QualityGateV2] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            ai_client: AIClientV2 instance (optional, creates default)
            serp_client: SerpAPI client (optional, creates default)
            quality_gate: QualityGateV2 instance (optional, creates default)
        """
        self.ai_client = ai_client
        self._serp_client = serp_client
        self.quality_gate = quality_gate

        logger.debug("EnrichmentOrchestratorV2 initialized")

    @property
    def serp_client(self) -> Any:
        """Lazy-load SerpAPI client."""
        if self._serp_client is None:
            from crawler.discovery.serpapi_client import SerpAPIClient
            self._serp_client = SerpAPIClient()
        return self._serp_client

    def _get_ai_client(self) -> AIClientV2:
        """Get or create AI client."""
        if self.ai_client is None:
            self.ai_client = get_ai_client_v2()
        return self.ai_client

    def _get_quality_gate(self) -> QualityGateV2:
        """Get or create quality gate."""
        if self.quality_gate is None:
            self.quality_gate = get_quality_gate_v2()
        return self.quality_gate

    async def enrich_product(
        self,
        product_id: str,
        product_type: str,
        initial_data: Dict[str, Any],
        initial_confidences: Optional[Dict[str, float]] = None,
    ) -> EnrichmentResult:
        """
        Enrich a product from multiple sources.

        Progressively searches for and extracts data from external sources
        until COMPLETE status is reached or limits are exceeded.

        Args:
            product_id: Product identifier
            product_type: Product type (whiskey, port_wine, etc.)
            initial_data: Current product data to enrich
            initial_confidences: Current field confidence scores

        Returns:
            EnrichmentResult with enriched data and metadata
        """
        logger.info(
            "Starting enrichment for product %s (type=%s)",
            product_id,
            product_type,
        )

        try:
            # Use sync_to_async for database access
            session = await sync_to_async(self._create_session, thread_sensitive=True)(
                product_type,
                initial_data,
                initial_confidences or {},
            )

            status_before = await self._assess_status(
                session.current_data,
                product_type,
                session.field_confidences,
            )

            logger.debug(
                "Initial status: %s, fields: %d",
                status_before,
                len(session.current_data),
            )

            # Use sync_to_async for database access
            configs = await sync_to_async(self._load_enrichment_configs, thread_sensitive=True)(product_type)

            if not configs:
                logger.warning(
                    "No enrichment configs found for product_type=%s",
                    product_type,
                )

            # =================================================================
            # STEP 1: Detail Page Extraction (Competition Site)
            # =================================================================
            detail_url = initial_data.get("detail_url")
            if detail_url:
                logger.info(
                    "Step 1: Detail page extraction from %s",
                    detail_url,
                )
                try:
                    detail_data, detail_confidences = await self._extract_from_detail_page(
                        detail_url,
                        product_type,
                        session,
                    )

                    if detail_data:
                        merged, enriched = self._merge_data(
                            session.current_data,
                            detail_data,
                            session.field_confidences,
                            detail_confidences,
                        )

                        if enriched:
                            session.current_data = merged
                            session.fields_enriched.extend(enriched)
                            logger.info(
                                "Detail page enriched %d fields: %s",
                                len(enriched),
                                enriched[:5],
                            )

                except Exception as e:
                    logger.warning(
                        "Detail page extraction failed for %s: %s",
                        detail_url,
                        str(e),
                    )

            # Check status after detail extraction
            current_status = await self._assess_status(
                session.current_data,
                product_type,
                session.field_confidences,
            )

            # =================================================================
            # STEP 2: Producer/Brand Page Search (Official Site)
            # =================================================================
            if current_status != ProductStatus.COMPLETE.value:
                logger.info("Step 2: Producer page search")
                try:
                    producer_data, producer_confidences = await self._search_and_extract_producer_page(
                        session.current_data,
                        product_type,
                        session,
                    )

                    if producer_data:
                        merged, enriched = self._merge_data(
                            session.current_data,
                            producer_data,
                            session.field_confidences,
                            producer_confidences,
                        )

                        if enriched:
                            session.current_data = merged
                            session.fields_enriched.extend(enriched)
                            logger.info(
                                "Producer page enriched %d fields: %s",
                                len(enriched),
                                enriched[:5],
                            )

                except Exception as e:
                    logger.warning(
                        "Producer page search failed: %s",
                        str(e),
                    )

                # Re-check status after producer page extraction
                current_status = await self._assess_status(
                    session.current_data,
                    product_type,
                    session.field_confidences,
                )

            # =================================================================
            # STEP 3: Review Site Enrichment (Existing Flow)
            # Skip if already COMPLETE from Steps 1 & 2
            # =================================================================
            if current_status == ProductStatus.COMPLETE.value:
                logger.info(
                    "Product COMPLETE after detail/producer extraction, "
                    "skipping review site enrichment"
                )
                configs = []  # Skip the config loop

            for config in configs:
                if not self._check_limits(session):
                    logger.info(
                        "Enrichment limits reached: searches=%d, sources=%d, time=%.1fs",
                        session.searches_performed,
                        len(session.sources_used),
                        time.time() - session.start_time,
                    )
                    break

                current_status = await self._assess_status(
                    session.current_data,
                    product_type,
                    session.field_confidences,
                )

                if current_status == ProductStatus.COMPLETE.value:
                    logger.info(
                        "Product %s reached COMPLETE status, stopping enrichment",
                        product_id,
                    )
                    break

                query = self._build_search_query(config, session.current_data)
                if not query:
                    logger.debug(
                        "Skipping config %s: empty query after substitution",
                        config.template_name,
                    )
                    continue

                logger.debug(
                    "Searching with query: %s (config=%s)",
                    query[:100],
                    config.template_name,
                )

                urls = await self._search_sources(query, session)
                session.searches_performed += 1

                for url in urls:
                    if not self._check_limits(session):
                        break

                    if url in session.sources_searched:
                        continue

                    session.sources_searched.append(url)

                    try:
                        target_fields = (
                            config.target_fields
                            if hasattr(config, "target_fields") and config.target_fields
                            else []
                        )

                        extracted, confidences = await self._fetch_and_extract(
                            url,
                            product_type,
                            target_fields,
                        )

                        if extracted:
                            # Validate that extracted data is for the correct product
                            is_match, match_reason = self._validate_product_match(
                                session.current_data,
                                extracted,
                            )

                            if not is_match:
                                logger.warning(
                                    "PRODUCT MISMATCH - Rejecting enrichment from %s: %s",
                                    url,
                                    match_reason,
                                )
                                session.sources_rejected.append({
                                    "url": url,
                                    "reason": match_reason,
                                    "extracted_name": extracted.get("name", ""),
                                })
                                continue

                            merged, enriched = self._merge_data(
                                session.current_data,
                                extracted,
                                session.field_confidences,
                                confidences,
                            )

                            if enriched:
                                session.current_data = merged
                                session.sources_used.append(url)
                                session.fields_enriched.extend(enriched)

                                logger.debug(
                                    "Enriched %d fields from %s: %s",
                                    len(enriched),
                                    url,
                                    enriched,
                                )

                    except Exception as e:
                        logger.warning("Failed to extract from %s: %s", url, e)

            status_after = await self._assess_status(
                session.current_data,
                product_type,
                session.field_confidences,
            )

            elapsed = time.time() - session.start_time

            logger.info(
                "Enrichment complete for %s: status %s -> %s, "
                "fields enriched=%d, sources=%d (rejected=%d), searches=%d, time=%.1fs",
                product_id,
                status_before,
                status_after,
                len(set(session.fields_enriched)),
                len(session.sources_used),
                len(session.sources_rejected),
                session.searches_performed,
                elapsed,
            )

            if session.sources_rejected:
                logger.info(
                    "Rejected sources due to product mismatch: %s",
                    [r["url"] for r in session.sources_rejected],
                )

            return EnrichmentResult(
                success=True,
                product_data=session.current_data,
                sources_used=session.sources_used,
                sources_searched=session.sources_searched,
                fields_enriched=list(set(session.fields_enriched)),
                status_before=status_before,
                status_after=status_after,
                searches_performed=session.searches_performed,
                time_elapsed_seconds=elapsed,
                sources_rejected=session.sources_rejected,
            )

        except Exception as e:
            logger.exception(
                "Enrichment failed for product %s: %s",
                product_id,
                str(e),
            )
            return EnrichmentResult(
                success=False,
                product_data=initial_data,
                error=str(e),
            )

    def _create_session(
        self,
        product_type: str,
        initial_data: Dict[str, Any],
        initial_confidences: Dict[str, float],
    ) -> EnrichmentSession:
        """Create enrichment session with limits from config."""
        max_sources = self.DEFAULT_MAX_SOURCES
        max_searches = self.DEFAULT_MAX_SEARCHES
        max_time = self.DEFAULT_MAX_TIME_SECONDS

        try:
            config = ProductTypeConfig.objects.get(product_type=product_type)
            max_sources = config.max_sources_per_product or max_sources
            max_searches = config.max_serpapi_searches or max_searches
            max_time = float(config.max_enrichment_time_seconds or max_time)

            logger.debug(
                "Using ProductTypeConfig limits: max_sources=%d, max_searches=%d, max_time=%.0fs",
                max_sources,
                max_searches,
                max_time,
            )

        except ProductTypeConfig.DoesNotExist:
            logger.debug(
                "ProductTypeConfig not found for %s, using defaults",
                product_type,
            )

        return EnrichmentSession(
            product_type=product_type,
            initial_data=initial_data.copy(),
            current_data=initial_data.copy(),
            field_confidences=initial_confidences.copy() if initial_confidences else {},
            max_sources=max_sources,
            max_searches=max_searches,
            max_time_seconds=max_time,
            start_time=time.time(),
        )

    def _load_enrichment_configs(self, product_type: str) -> List[EnrichmentConfig]:
        """
        Load EnrichmentConfig entries for product type.

        Returns configs ordered by priority (descending).
        """
        try:
            configs = list(
                EnrichmentConfig.objects.filter(
                    product_type_config__product_type=product_type,
                    is_active=True,
                ).order_by("-priority")
            )

            logger.debug(
                "Loaded %d enrichment configs for %s",
                len(configs),
                product_type,
            )

            return configs

        except Exception as e:
            logger.warning(
                "Failed to load enrichment configs for %s: %s",
                product_type,
                str(e),
            )
            return []

    def _build_search_query(
        self,
        config: EnrichmentConfig,
        product_data: Dict[str, Any],
    ) -> str:
        """
        Build search query from EnrichmentConfig template.

        Substitutes {name}, {brand}, etc. from product data.
        """
        template = config.search_template

        query = template
        for key, value in product_data.items():
            if value and isinstance(value, str):
                query = query.replace(f"{{{key}}}", value)

        query = re.sub(r"\{[^}]+\}", "", query)

        query = " ".join(query.split())

        return query.strip()

    async def _search_sources(
        self,
        query: str,
        session: EnrichmentSession,
    ) -> List[str]:
        """
        Search for source URLs using SerpAPI.

        Args:
            query: Search query string
            session: Current enrichment session

        Returns:
            List of URLs to extract from
        """
        try:
            remaining_sources = session.max_sources - len(session.sources_used)
            num_results = min(10, max(5, remaining_sources))

            results = await self.serp_client.search(query, num_results=num_results)

            urls = [r.url for r in results if r.url and r.url not in session.sources_searched]

            logger.debug(
                "Search returned %d URLs for query: %s",
                len(urls),
                query[:50],
            )

            return urls

        except Exception as e:
            logger.warning("Search failed for query '%s': %s", query[:50], str(e))
            return []

    async def _fetch_and_extract(
        self,
        url: str,
        product_type: str,
        target_fields: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Fetch URL content and extract product data.

        Args:
            url: Source URL to fetch
            product_type: Product type for extraction
            target_fields: Fields to prioritize in extraction

        Returns:
            Tuple of (extracted_data, field_confidences)
        """
        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    },
                )
                response.raise_for_status()
                content = response.text

        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s", url)
            return {}, {}

        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error fetching %s: %s", url, e.response.status_code)
            return {}, {}

        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, str(e))
            return {}, {}

        if not content:
            return {}, {}

        try:
            ai_client = self._get_ai_client()

            extraction_schema = target_fields if target_fields else None

            result = await ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                extraction_schema=extraction_schema,
            )

            if not result.success or not result.products:
                logger.debug(
                    "No products extracted from %s: %s",
                    url,
                    result.error or "empty result",
                )
                return {}, {}

            product = result.products[0]
            extracted_data = product.extracted_data or {}
            field_confidences = product.field_confidences or {}

            if not field_confidences:
                field_confidences = {
                    k: product.confidence for k in extracted_data.keys()
                }

            logger.debug(
                "Extracted %d fields from %s",
                len(extracted_data),
                url,
            )

            return extracted_data, field_confidences

        except Exception as e:
            logger.warning("Extraction failed for %s: %s", url, str(e))
            return {}, {}

    def _merge_data(
        self,
        existing: Dict[str, Any],
        new_data: Dict[str, Any],
        existing_confidences: Dict[str, float],
        new_confidences: Dict[str, float],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Merge new data into existing based on confidence.

        Rules:
        - Empty field: Always fill from new data
        - Existing field: Replace only if new confidence > existing
        - Arrays: Append unique values
        - Objects: Merge recursively

        Args:
            existing: Current product data
            new_data: Newly extracted data
            existing_confidences: Current field confidences
            new_confidences: New field confidences

        Returns:
            Tuple of (merged_data, list_of_enriched_fields)
        """
        merged = existing.copy()
        enriched_fields = []

        for field_name, new_value in new_data.items():
            if new_value is None:
                continue

            existing_value = merged.get(field_name)
            existing_conf = existing_confidences.get(field_name, 0.0)
            new_conf = new_confidences.get(field_name, 0.5)

            is_empty = (
                existing_value is None
                or existing_value == ""
                or existing_value == []
                or existing_value == {}
            )

            if is_empty:
                merged[field_name] = new_value
                existing_confidences[field_name] = new_conf
                enriched_fields.append(field_name)

            elif new_conf > existing_conf:
                merged[field_name] = new_value
                existing_confidences[field_name] = new_conf
                enriched_fields.append(field_name)

            elif isinstance(existing_value, list) and isinstance(new_value, list):
                added_items = False
                for item in new_value:
                    if item not in existing_value:
                        existing_value.append(item)
                        added_items = True
                if added_items:
                    enriched_fields.append(field_name)

            elif isinstance(existing_value, dict) and isinstance(new_value, dict):
                sub_merged, sub_enriched = self._merge_data(
                    existing_value,
                    new_value,
                    existing_confidences.get(field_name, {}),
                    new_confidences.get(field_name, {}),
                )
                if sub_enriched:
                    merged[field_name] = sub_merged
                    enriched_fields.append(field_name)

        return merged, enriched_fields

    def _check_limits(self, session: EnrichmentSession) -> bool:
        """
        Check if enrichment should continue.

        Returns:
            True if within limits, False if should stop
        """
        if session.searches_performed >= session.max_searches:
            return False

        if len(session.sources_used) >= session.max_sources:
            return False

        elapsed = time.time() - session.start_time
        if elapsed >= session.max_time_seconds:
            return False

        return True

    def _validate_product_match(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Validate that extracted data matches the target product.

        Prevents enrichment from wrong products (e.g., extracting tasting notes
        from "Frank August Rye" when enriching "Frank August Bourbon").

        Args:
            target_data: The product we're trying to enrich
            extracted_data: Data extracted from an enrichment source

        Returns:
            Tuple of (is_match, reason)
        """
        target_name = (target_data.get("name") or "").lower().strip()
        target_brand = (target_data.get("brand") or "").lower().strip()
        extracted_name = (extracted_data.get("name") or "").lower().strip()
        extracted_brand = (extracted_data.get("brand") or "").lower().strip()

        # If extracted data has no name, we can't validate - allow it but log warning
        if not extracted_name:
            logger.debug("No product name in extracted data, allowing enrichment")
            return True, "no_name_extracted"

        # Brand must match if both are present
        if target_brand and extracted_brand:
            if target_brand not in extracted_brand and extracted_brand not in target_brand:
                return False, f"brand_mismatch: target='{target_brand}', extracted='{extracted_brand}'"

        # Check for product type keywords that indicate different products
        # E.g., "bourbon" vs "rye", "single malt" vs "blended"
        product_type_keywords = [
            ("bourbon", "rye"),
            ("bourbon", "wheat"),
            ("single malt", "blended"),
            ("scotch", "bourbon"),
            ("irish", "scotch"),
            ("tawny", "ruby"),
            ("vintage", "lbv"),
            ("10 year", "20 year"),
            ("12 year", "18 year"),
        ]

        for keyword1, keyword2 in product_type_keywords:
            # If target has keyword1 but extracted has keyword2 (or vice versa)
            target_has_k1 = keyword1 in target_name
            target_has_k2 = keyword2 in target_name
            extracted_has_k1 = keyword1 in extracted_name
            extracted_has_k2 = keyword2 in extracted_name

            if target_has_k1 and extracted_has_k2 and not extracted_has_k1:
                return False, f"product_type_mismatch: target has '{keyword1}', extracted has '{keyword2}'"
            if target_has_k2 and extracted_has_k1 and not extracted_has_k2:
                return False, f"product_type_mismatch: target has '{keyword2}', extracted has '{keyword1}'"

        # Check for significant name token overlap
        # Split names into tokens and check overlap
        def tokenize(s: str) -> set:
            # Remove common words and punctuation
            stopwords = {"the", "a", "an", "and", "of", "for", "with", "by", "from"}
            tokens = re.findall(r'\b\w+\b', s.lower())
            return set(t for t in tokens if t not in stopwords and len(t) > 2)

        target_tokens = tokenize(target_name)
        extracted_tokens = tokenize(extracted_name)

        if target_tokens and extracted_tokens:
            overlap = target_tokens & extracted_tokens
            # Require at least 30% token overlap
            min_overlap_ratio = 0.3
            overlap_ratio = len(overlap) / min(len(target_tokens), len(extracted_tokens))

            if overlap_ratio < min_overlap_ratio:
                return False, f"name_mismatch: low overlap ({overlap_ratio:.0%}), target='{target_name}', extracted='{extracted_name}'"

        return True, "match"

    async def _assess_status(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        confidences: Dict[str, float],
    ) -> str:
        """
        Assess product status using QualityGate (async-safe).

        Returns:
            Status string (skeleton, partial, complete, enriched)
        """
        try:
            quality_gate = self._get_quality_gate()
            # Use async aassess method to avoid "cannot call from async context" errors
            assessment = await quality_gate.aassess(
                extracted_data=product_data,
                product_type=product_type,
                field_confidences=confidences,
            )
            return assessment.status.value

        except Exception as e:
            logger.warning(
                "Failed to assess status for %s: %s",
                product_type,
                str(e),
            )
            return "partial"

    # =========================================================================
    # Detail Page and Producer Page Extraction (Steps 1 & 2)
    # =========================================================================

    def _get_base_url(self, source_url: str) -> str:
        """
        Extract base URL (scheme + domain) from source URL.

        Args:
            source_url: Full URL to extract base from

        Returns:
            Base URL like "https://www.iwsc.net"
        """
        from urllib.parse import urlparse
        if not source_url:
            return ""
        parsed = urlparse(source_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _extract_from_detail_page(
        self,
        detail_url: str,
        product_type: str,
        session: EnrichmentSession,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Extract product data from competition detail page.

        Uses SmartRouter for JS rendering and full extraction schema.
        This is Step 1 of the 3-step enrichment pipeline.

        Args:
            detail_url: URL to detail page (may be relative)
            product_type: Product type for extraction
            session: Current enrichment session

        Returns:
            Tuple of (extracted_data, field_confidences)
        """
        from crawler.fetchers.smart_router import SmartRouter

        # Resolve relative URLs
        if detail_url.startswith("/"):
            base_url = self._get_base_url(session.initial_data.get("source_url", ""))
            if base_url:
                detail_url = f"{base_url}{detail_url}"
            else:
                logger.warning("Cannot resolve relative detail_url without source_url")
                return {}, {}

        logger.info("Step 1: Fetching detail page: %s", detail_url)

        try:
            # Use SmartRouter with Tier 2 (Playwright) for JS rendering
            router = SmartRouter()
            result = await router.fetch(detail_url, force_tier=2)

            if not result.success or not result.content:
                logger.warning("Failed to fetch detail page: %s", detail_url)
                return {}, {}

            logger.debug("Detail page fetched: %d chars", len(result.content))

            # Extract with FULL schema (not skeleton) - single product page
            ai_client = self._get_ai_client()
            extraction = await ai_client.extract(
                content=result.content,
                source_url=detail_url,
                product_type=product_type,
                detect_multi_product=False,  # Single product detail page
            )

            if not extraction.success or not extraction.products:
                logger.warning(
                    "No products extracted from detail page: %s",
                    extraction.error or "empty result",
                )
                return {}, {}

            # Return first product with high confidence (authoritative source)
            product = extraction.products[0]
            extracted_data = product.extracted_data or {}

            # Set high confidence (0.95) for detail page data - authoritative source
            confidences = {field: 0.95 for field in extracted_data.keys()}

            session.sources_used.append(detail_url)
            logger.info(
                "Extracted %d fields from detail page: %s",
                len(extracted_data),
                detail_url,
            )

            return extracted_data, confidences

        except Exception as e:
            logger.warning("Detail page extraction failed for %s: %s", detail_url, str(e))
            return {}, {}

    def _filter_producer_urls(
        self,
        urls: List[str],
        brand: str,
        producer: str,
    ) -> List[str]:
        """
        Filter and prioritize URLs for producer page search.

        Prioritizes official brand/producer sites over retailers and review sites.

        Args:
            urls: List of URLs from search results
            brand: Product brand name
            producer: Product producer name

        Returns:
            Sorted list with official sites first
        """
        # Known retailer/review domains to deprioritize
        retailer_domains = {
            "masterofmalt", "thewhiskyexchange", "whiskyexchange",
            "totalwine", "wine.com", "drizly", "reservebar",
            "klwines", "finedrams", "thewhiskyshop",
            "amazon", "ebay", "walmart",
        }

        brand_lower = brand.lower().replace(" ", "").replace("'", "").replace("-", "")
        producer_lower = (producer or "").lower().replace(" ", "").replace("'", "").replace("-", "")

        def get_domain(url: str) -> str:
            """Extract domain from URL."""
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")

        def is_retailer(url: str) -> bool:
            """Check if URL is from a retailer domain."""
            domain = get_domain(url)
            return any(r in domain for r in retailer_domains)

        def is_likely_official(url: str) -> bool:
            """Check if brand/producer name appears in domain."""
            domain = get_domain(url).replace("-", "").replace(".", "")
            if brand_lower and len(brand_lower) > 3 and brand_lower in domain:
                return True
            if producer_lower and len(producer_lower) > 3 and producer_lower in domain:
                return True
            return False

        # Categorize URLs
        official = []
        other = []
        retailers = []

        for url in urls:
            if is_retailer(url):
                retailers.append(url)
            elif is_likely_official(url):
                official.append(url)
            else:
                other.append(url)

        # Return: official sites first, then other non-retailers, then retailers last
        return official + other + retailers

    async def _search_and_extract_producer_page(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        session: EnrichmentSession,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Search for and extract from official producer/brand page.

        This is Step 2 of the 3-step enrichment pipeline.
        Searches SerpAPI for official producer page, filters results
        to prioritize brand domains, and extracts with full schema.

        Args:
            product_data: Current product data (needs name, brand)
            product_type: Product type for extraction
            session: Current enrichment session

        Returns:
            Tuple of (extracted_data, field_confidences)
        """
        brand = product_data.get("brand", "")
        name = product_data.get("name", "")
        producer = product_data.get("producer", "") or brand

        if not brand and not producer:
            logger.debug("No brand/producer for producer page search")
            return {}, {}

        # Build search query for official site
        # Use brand + name + "official" to find producer pages
        query = f"{brand} {name} official".strip()
        if not query or query == "official":
            return {}, {}

        logger.info("Step 2: Searching for producer page: %s", query[:80])

        try:
            # Search with SerpAPI
            urls = await self._search_sources(query, session)
            session.searches_performed += 1

            if not urls:
                logger.debug("No URLs found for producer page search")
                return {}, {}

            # Filter and prioritize producer URLs
            producer_urls = self._filter_producer_urls(urls, brand, producer)
            logger.debug(
                "Producer URL filtering: %d total, prioritized order: %s",
                len(producer_urls),
                [u[:50] for u in producer_urls[:3]],
            )

            # Try top 3 matches
            for url in producer_urls[:3]:
                if url in session.sources_searched:
                    continue
                session.sources_searched.append(url)

                try:
                    # Extract with full schema
                    extracted, confidences = await self._fetch_and_extract(
                        url, product_type, []  # Empty list = full schema
                    )

                    if extracted:
                        # Validate it's the right product
                        is_match, reason = self._validate_product_match(
                            product_data, extracted
                        )

                        if is_match:
                            # Boost confidence for official/producer site
                            boosted_confidences = {
                                k: min(v + 0.1, 0.95) for k, v in confidences.items()
                            }
                            session.sources_used.append(url)
                            logger.info(
                                "Extracted %d fields from producer page: %s",
                                len(extracted),
                                url,
                            )
                            return extracted, boosted_confidences
                        else:
                            logger.debug(
                                "Producer page rejected (mismatch): %s - %s",
                                url,
                                reason,
                            )
                            session.sources_rejected.append({
                                "url": url,
                                "reason": reason,
                            })

                except Exception as e:
                    logger.warning("Failed to extract from producer page %s: %s", url, str(e))

            return {}, {}

        except Exception as e:
            logger.warning("Producer page search failed: %s", str(e))
            return {}, {}


_orchestrator_instance: Optional[EnrichmentOrchestratorV2] = None


def get_enrichment_orchestrator_v2(**kwargs) -> EnrichmentOrchestratorV2:
    """Get or create EnrichmentOrchestratorV2 singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = EnrichmentOrchestratorV2(**kwargs)
    return _orchestrator_instance


def reset_enrichment_orchestrator_v2() -> None:
    """Reset singleton for testing."""
    global _orchestrator_instance
    _orchestrator_instance = None
