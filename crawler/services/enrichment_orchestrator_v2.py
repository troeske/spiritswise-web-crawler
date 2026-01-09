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
    fields_enriched: List[str] = field(default_factory=list)
    status_before: str = ""
    status_after: str = ""
    searches_performed: int = 0
    time_elapsed_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class EnrichmentSession:
    """Tracks state during enrichment."""

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any]
    field_confidences: Dict[str, float]
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
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
            session = self._create_session(
                product_type,
                initial_data,
                initial_confidences or {},
            )

            status_before = self._assess_status(
                session.current_data,
                product_type,
                session.field_confidences,
            )

            logger.debug(
                "Initial status: %s, fields: %d",
                status_before,
                len(session.current_data),
            )

            configs = self._load_enrichment_configs(product_type)

            if not configs:
                logger.warning(
                    "No enrichment configs found for product_type=%s",
                    product_type,
                )

            for config in configs:
                if not self._check_limits(session):
                    logger.info(
                        "Enrichment limits reached: searches=%d, sources=%d, time=%.1fs",
                        session.searches_performed,
                        len(session.sources_used),
                        time.time() - session.start_time,
                    )
                    break

                current_status = self._assess_status(
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

            status_after = self._assess_status(
                session.current_data,
                product_type,
                session.field_confidences,
            )

            elapsed = time.time() - session.start_time

            logger.info(
                "Enrichment complete for %s: status %s -> %s, "
                "fields enriched=%d, sources=%d, searches=%d, time=%.1fs",
                product_id,
                status_before,
                status_after,
                len(set(session.fields_enriched)),
                len(session.sources_used),
                session.searches_performed,
                elapsed,
            )

            return EnrichmentResult(
                success=True,
                product_data=session.current_data,
                sources_used=session.sources_used,
                fields_enriched=list(set(session.fields_enriched)),
                status_before=status_before,
                status_after=status_after,
                searches_performed=session.searches_performed,
                time_elapsed_seconds=elapsed,
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

    def _assess_status(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        confidences: Dict[str, float],
    ) -> str:
        """
        Assess product status using QualityGateV2.

        Returns:
            Status string (skeleton, partial, complete, enriched)
        """
        try:
            quality_gate = self._get_quality_gate()
            assessment = quality_gate.assess(
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
