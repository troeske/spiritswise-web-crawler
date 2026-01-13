"""
2-Step Enrichment Pipeline V3 for Generic Search Discovery.

Task 1.3: 2-Step Enrichment Pipeline

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.1 (FEAT-001)

Generic Search uses a 2-step pipeline (different from Competition Flow's 3-step):
- Step 1: Producer page search ("{brand} {name} official")
- Step 2: Review site enrichment (if still incomplete)

There is NO detail page step because generic search returns listicles with
inline product text, not detail page links.

Key Features:
- Uses ProductMatchValidator to prevent cross-contamination
- Uses ConfidenceBasedMerger for data merging
- Early exit if COMPLETE (90% ECP) reached after Step 1
- Comprehensive source tracking
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from asgiref.sync import sync_to_async

from crawler.models import EnrichmentConfig, ProductTypeConfig
from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2
from crawler.services.confidence_merger import ConfidenceBasedMerger, get_confidence_merger
from crawler.services.product_match_validator import (
    ProductMatchValidator,
    get_product_match_validator,
)
from crawler.services.quality_gate_v3 import (
    ProductStatus,
    QualityGateV3,
    get_quality_gate_v3,
)

logger = logging.getLogger(__name__)


# Known retailer domains to deprioritize in producer search
RETAILER_DOMAINS = {
    "masterofmalt", "thewhiskyexchange", "whiskyexchange",
    "totalwine", "wine.com", "drizly", "reservebar",
    "klwines", "finedrams", "thewhiskyshop",
    "amazon", "ebay", "walmart", "target",
    "bevmo", "caskers", "liquor.com",
}


@dataclass
class EnrichmentSessionV3:
    """
    Tracks state during 2-step enrichment.

    This session is specific to the Generic Search 2-step pipeline,
    tracking both producer page and review site enrichment progress.
    """

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any] = field(default_factory=dict)
    field_confidences: Dict[str, float] = field(default_factory=dict)

    # 2-Step tracking
    step_1_completed: bool = False  # Producer page search
    step_2_completed: bool = False  # Review site enrichment

    # Source tracking
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)

    # Status tracking
    status_progression: List[str] = field(default_factory=list)

    # Fields tracking
    fields_enriched: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Limits
    searches_performed: int = 0
    max_searches: int = 3
    max_sources: int = 5
    max_time_seconds: float = 120.0
    start_time: float = 0.0

    def __post_init__(self):
        """Initialize current_data from initial_data if empty."""
        if not self.current_data:
            self.current_data = dict(self.initial_data)
        if self.start_time == 0.0:
            self.start_time = time.time()


@dataclass
class EnrichmentResultV3:
    """
    Result of 2-step enrichment operation.

    Includes comprehensive source tracking and status progression
    per spec Section 5.6.
    """

    success: bool
    product_data: Dict[str, Any] = field(default_factory=dict)
    quality_status: str = ""

    # 2-Step tracking
    step_1_completed: bool = False
    step_2_completed: bool = False

    # Source tracking (FEAT-006)
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)

    # Field tracking
    fields_enriched: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Status tracking
    status_before: str = ""
    status_after: str = ""
    status_progression: List[str] = field(default_factory=list)

    # Metrics
    searches_performed: int = 0
    time_elapsed_seconds: float = 0.0
    error: Optional[str] = None


class EnrichmentPipelineV3:
    """
    2-Step Enrichment Pipeline for Generic Search Discovery.

    Implements the 2-step pipeline from spec Section 5.1:
    - Step 1: Producer page search ("{brand} {name} official")
    - Step 2: Review site enrichment (if still incomplete)

    Key Differences from Competition Flow:
    - No detail page step (listicles have inline text, no detail_url)
    - Starts with producer search instead of detail extraction
    - Only 2 steps instead of 3
    """

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_SOURCES = 5
    DEFAULT_MAX_SEARCHES = 3
    DEFAULT_MAX_TIME_SECONDS = 120.0

    # Confidence settings
    PRODUCER_CONFIDENCE_BOOST = 0.10
    PRODUCER_CONFIDENCE_MAX = 0.95
    REVIEW_SITE_CONFIDENCE = 0.75

    def __init__(
        self,
        ai_client: Optional[AIClientV2] = None,
        serp_client: Optional[Any] = None,
        quality_gate: Optional[QualityGateV3] = None,
        product_match_validator: Optional[ProductMatchValidator] = None,
        confidence_merger: Optional[ConfidenceBasedMerger] = None,
    ):
        """
        Initialize the 2-step enrichment pipeline.

        Args:
            ai_client: AIClientV2 for extraction
            serp_client: SerpAPI client for search
            quality_gate: QualityGateV3 for status assessment
            product_match_validator: Validator to prevent cross-contamination
            confidence_merger: Merger for confidence-based data merging
        """
        self.ai_client = ai_client
        self._serp_client = serp_client
        self._quality_gate = quality_gate
        self._validator = product_match_validator
        self._merger = confidence_merger

        logger.debug("EnrichmentPipelineV3 initialized")

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

    def _get_quality_gate(self) -> QualityGateV3:
        """Get or create quality gate."""
        if self._quality_gate is None:
            self._quality_gate = get_quality_gate_v3()
        return self._quality_gate

    def _get_validator(self) -> ProductMatchValidator:
        """Get or create product match validator."""
        if self._validator is None:
            self._validator = get_product_match_validator()
        return self._validator

    def _get_merger(self) -> ConfidenceBasedMerger:
        """Get or create confidence merger."""
        if self._merger is None:
            self._merger = get_confidence_merger()
        return self._merger

    # =========================================================================
    # Step 1: Producer Page Search (Subtask 1.3.2)
    # =========================================================================

    def _build_producer_search_query(self, product_data: Dict[str, Any]) -> str:
        """
        Build search query for producer page search.

        Query format: "{brand} {name} official"

        Args:
            product_data: Product data with name and brand

        Returns:
            Search query string
        """
        brand = product_data.get("brand", "")
        name = product_data.get("name", "")

        parts = []
        if brand:
            parts.append(brand)
        if name:
            parts.append(name)
        parts.append("official")

        query = " ".join(parts).strip()
        logger.debug("Producer search query: %s", query)

        return query

    def _filter_producer_urls(
        self,
        urls: List[str],
        brand: str,
        producer: str,
    ) -> List[str]:
        """
        Filter and prioritize URLs for producer page search.

        Priority order:
        1. Official sites (brand/producer in domain)
        2. Non-retailers (blogs, review sites)
        3. Retailers (deprioritized)

        Args:
            urls: List of URLs from search results
            brand: Product brand name
            producer: Product producer name

        Returns:
            Sorted list with official sites first
        """
        brand_lower = brand.lower().replace(" ", "").replace("'", "").replace("-", "")
        producer_lower = (producer or "").lower().replace(" ", "").replace("'", "").replace("-", "")

        def get_domain(url: str) -> str:
            """Extract domain from URL."""
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")

        def is_retailer(url: str) -> bool:
            """Check if URL is from a retailer domain."""
            domain = get_domain(url)
            return any(r in domain for r in RETAILER_DOMAINS)

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

    def _apply_producer_confidence_boost(
        self,
        confidences: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Apply confidence boost for producer page data.

        Boost by +0.1 but cap at 0.95.

        Args:
            confidences: Original field confidences

        Returns:
            Boosted confidences dict
        """
        boosted = {}
        for field_name, confidence in confidences.items():
            boosted_value = confidence + self.PRODUCER_CONFIDENCE_BOOST
            boosted[field_name] = min(boosted_value, self.PRODUCER_CONFIDENCE_MAX)
        return boosted

    async def _search_and_extract_producer_page(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        session: EnrichmentSessionV3,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Step 1: Search for and extract from official producer/brand page.

        Process:
        1. Build search query: "{brand} {name} official"
        2. Execute SerpAPI search
        3. Filter URLs by priority (official > non-retailer > retailer)
        4. For top 3 matches: fetch, extract, validate product match
        5. If match: return with confidence boost (+0.1, max 0.95)

        Args:
            product_data: Current product data (needs name, brand)
            product_type: Product type for extraction schema
            session: Current enrichment session

        Returns:
            Tuple of (extracted_data, field_confidences)
        """
        brand = product_data.get("brand", "")
        name = product_data.get("name", "")
        producer = product_data.get("producer", "") or brand

        if not brand and not name:
            logger.debug("No brand/name for producer page search")
            return {}, {}

        # Build search query
        query = self._build_producer_search_query(product_data)
        if not query or query == "official":
            return {}, {}

        logger.info("Step 1: Searching for producer page: %s", query[:80])

        try:
            # Search with SerpAPI
            urls = await self._search_sources(query, session)
            session.searches_performed += 1

            if not urls:
                logger.debug("No URLs found for producer page search")
                return {}, {}

            # Filter and prioritize URLs
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
                        url, product_type, []
                    )

                    if extracted:
                        # Validate product match
                        is_match, reason = self._validate_and_track(
                            product_data, extracted
                        )

                        if is_match:
                            # Boost confidence for official site
                            boosted = self._apply_producer_confidence_boost(confidences)
                            session.sources_used.append(url)

                            # Track field provenance
                            for field_name in extracted.keys():
                                session.field_provenance[field_name] = url

                            logger.info(
                                "Step 1: Extracted %d fields from producer page: %s",
                                len(extracted),
                                url,
                            )
                            return extracted, boosted
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
                    logger.warning(
                        "Failed to extract from producer page %s: %s",
                        url,
                        str(e),
                    )

            return {}, {}

        except Exception as e:
            logger.warning("Producer page search failed: %s", str(e))
            return {}, {}

    # =========================================================================
    # Step 2: Review Site Enrichment (Subtask 1.3.3)
    # =========================================================================

    def _get_review_site_confidence(self) -> float:
        """
        Get confidence score for review site data.

        Returns:
            Confidence score (0.70-0.80 range, default 0.75)
        """
        return self.REVIEW_SITE_CONFIDENCE

    async def _load_enrichment_configs(
        self,
        product_type: str,
    ) -> List[EnrichmentConfig]:
        """
        Load EnrichmentConfig entries for product type ordered by priority.

        Args:
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            List of EnrichmentConfig ordered by priority (descending)
        """
        try:
            configs = await sync_to_async(
                lambda: list(
                    EnrichmentConfig.objects.filter(
                        product_type_config__product_type=product_type,
                        is_active=True,
                    ).order_by("-priority")
                ),
                thread_sensitive=True,
            )()

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

    async def _enrich_from_review_sites(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        session: EnrichmentSessionV3,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Step 2: Enrich product from review sites.

        Process:
        1. Load EnrichmentConfigs by priority
        2. For each config: build search query, execute search
        3. For each URL: fetch, extract, validate product match
        4. If match: merge by confidence (0.70-0.80)
        5. Stop when COMPLETE or limits reached

        Args:
            product_data: Current product data
            product_type: Product type for extraction
            session: Current enrichment session

        Returns:
            Tuple of (merged_data, updated_confidences)
        """
        logger.info("Step 2: Starting review site enrichment")

        configs = await self._load_enrichment_configs(product_type)

        if not configs:
            logger.warning(
                "No enrichment configs found for product_type=%s",
                product_type,
            )
            return {}, {}

        merged_data = dict(product_data)
        merged_confidences = dict(session.field_confidences)
        all_enriched_fields = []

        for config in configs:
            # Check limits before each config
            if not self._check_limits(session):
                logger.info(
                    "Step 2: Limits reached, stopping review site enrichment"
                )
                break

            # Check status
            status = await self._assess_status(merged_data, product_type, merged_confidences)
            if status == ProductStatus.COMPLETE:
                logger.info("Step 2: COMPLETE status reached, stopping enrichment")
                break

            # Build search query from config template
            query = self._build_config_search_query(config, merged_data)
            if not query:
                logger.debug(
                    "Skipping config %s: empty query after substitution",
                    config.template_name,
                )
                continue

            logger.debug(
                "Step 2: Searching with query: %s (config=%s)",
                query[:100],
                config.template_name,
            )

            # Execute search
            urls = await self._search_sources(query, session)
            session.searches_performed += 1

            for url in urls:
                # Check limits for each URL
                if not self._check_limits(session):
                    break

                if url in session.sources_searched:
                    continue
                session.sources_searched.append(url)

                try:
                    # Get target fields from config
                    target_fields = (
                        config.target_fields
                        if hasattr(config, "target_fields") and config.target_fields
                        else []
                    )

                    extracted, confidences = await self._fetch_and_extract(
                        url, product_type, target_fields
                    )

                    if extracted:
                        # Validate product match
                        is_match, reason = self._validate_and_track(
                            merged_data, extracted
                        )

                        if not is_match:
                            logger.warning(
                                "Step 2: Rejecting enrichment from %s: %s",
                                url,
                                reason,
                            )
                            session.sources_rejected.append({
                                "url": url,
                                "reason": reason,
                            })
                            continue

                        # Merge with review site confidence
                        review_confidence = self._get_review_site_confidence()
                        new_data, enriched = self._merge_with_confidence(
                            merged_data,
                            merged_confidences,
                            extracted,
                            review_confidence,
                        )

                        if enriched:
                            merged_data = new_data
                            merged_confidences = self._get_merger().get_updated_confidences()
                            session.sources_used.append(url)
                            all_enriched_fields.extend(enriched)

                            # Track field provenance
                            for field_name in enriched:
                                session.field_provenance[field_name] = url

                            logger.debug(
                                "Step 2: Enriched %d fields from %s: %s",
                                len(enriched),
                                url,
                                enriched,
                            )

                except Exception as e:
                    logger.warning("Step 2: Failed to extract from %s: %s", url, str(e))

        session.fields_enriched.extend(all_enriched_fields)
        return merged_data, merged_confidences

    def _build_config_search_query(
        self,
        config: EnrichmentConfig,
        product_data: Dict[str, Any],
    ) -> str:
        """
        Build search query from EnrichmentConfig template.

        Substitutes {name}, {brand}, etc. from product data.

        Args:
            config: EnrichmentConfig with search_template
            product_data: Product data for substitution

        Returns:
            Completed search query string
        """
        import re

        template = config.search_template

        query = template
        for key, value in product_data.items():
            if value and isinstance(value, str):
                query = query.replace(f"{{{key}}}", value)

        # Remove any remaining unsubstituted placeholders
        query = re.sub(r"\{[^}]+\}", "", query)

        # Clean up whitespace
        query = " ".join(query.split())

        return query.strip()

    # =========================================================================
    # Main Orchestration (Subtask 1.3.4)
    # =========================================================================

    async def enrich_product(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        initial_confidences: Optional[Dict[str, float]] = None,
    ) -> EnrichmentResultV3:
        """
        Execute 2-step enrichment pipeline for a product.

        Step 1: Search for official producer/brand page
        Step 2: Search review sites (if still incomplete after Step 1)

        Args:
            product_data: Initial product data (skeleton from listicle)
            product_type: Product type for schema selection

        Returns:
            EnrichmentResultV3 with enriched data and tracking
        """
        logger.info(
            "Starting 2-step enrichment for product: %s (type=%s)",
            product_data.get("name", "unknown"),
            product_type,
        )

        # Create session
        session = await self._create_session(
            product_type, product_data, initial_confidences
        )

        # Record initial status
        status_before = await self._assess_status(
            session.current_data, product_type, session.field_confidences
        )
        session.status_progression.append(status_before.value)

        try:
            # =================================================================
            # Step 1: Producer Page Search
            # =================================================================
            logger.info("Step 1: Producer page search")
            producer_data, producer_confidences = await self._search_and_extract_producer_page(
                session.current_data,
                product_type,
                session,
            )

            if producer_data:
                merged, enriched = self._merge_with_confidence(
                    session.current_data,
                    session.field_confidences,
                    producer_data,
                    0.85,  # Base producer confidence before boost
                )
                if enriched:
                    session.current_data = merged
                    session.field_confidences = self._get_merger().get_updated_confidences()
                    session.fields_enriched.extend(enriched)
                    logger.info(
                        "Step 1: Enriched %d fields from producer page",
                        len(enriched),
                    )

            session.step_1_completed = True

            # Check status after Step 1
            status_after_step1 = await self._assess_status(
                session.current_data, product_type, session.field_confidences
            )
            session.status_progression.append(status_after_step1.value)

            # =================================================================
            # Step 2: Review Site Enrichment (if not COMPLETE)
            # =================================================================
            if self._should_continue_to_step2(status_after_step1):
                logger.info("Step 2: Review site enrichment (status=%s)", status_after_step1.value)
                review_data, review_confidences = await self._enrich_from_review_sites(
                    session.current_data,
                    product_type,
                    session,
                )

                if review_data:
                    session.current_data = review_data
                    session.field_confidences = review_confidences

                session.step_2_completed = True
            else:
                logger.info(
                    "Skipping Step 2: Product reached %s after Step 1",
                    status_after_step1.value,
                )

            # Final status assessment
            status_after = await self._assess_status(
                session.current_data, product_type, session.field_confidences
            )
            session.status_progression.append(status_after.value)

            elapsed = time.time() - session.start_time

            logger.info(
                "Enrichment complete: status %s -> %s, fields=%d, sources=%d (rejected=%d)",
                status_before.value,
                status_after.value,
                len(set(session.fields_enriched)),
                len(session.sources_used),
                len(session.sources_rejected),
            )

            return EnrichmentResultV3(
                success=True,
                product_data=session.current_data,
                quality_status=status_after.value,
                step_1_completed=session.step_1_completed,
                step_2_completed=session.step_2_completed,
                sources_searched=session.sources_searched,
                sources_used=session.sources_used,
                sources_rejected=session.sources_rejected,
                fields_enriched=list(set(session.fields_enriched)),
                field_provenance=session.field_provenance,
                status_before=status_before.value,
                status_after=status_after.value,
                status_progression=session.status_progression,
                searches_performed=session.searches_performed,
                time_elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Enrichment failed: %s", str(e))
            return EnrichmentResultV3(
                success=False,
                product_data=product_data,
                error=str(e),
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _create_session(
        self,
        product_type: str,
        initial_data: Dict[str, Any],
        initial_confidences: Optional[Dict[str, float]] = None,
    ) -> EnrichmentSessionV3:
        """Create enrichment session with limits from config."""
        max_sources = self.DEFAULT_MAX_SOURCES
        max_searches = self.DEFAULT_MAX_SEARCHES
        max_time = self.DEFAULT_MAX_TIME_SECONDS

        try:
            config = await sync_to_async(
                lambda: ProductTypeConfig.objects.get(product_type=product_type),
                thread_sensitive=True,
            )()
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

        return EnrichmentSessionV3(
            product_type=product_type,
            initial_data=initial_data.copy(),
            current_data=initial_data.copy(),
            field_confidences=dict(initial_confidences or {}),
            max_sources=max_sources,
            max_searches=max_searches,
            max_time_seconds=max_time,
            start_time=time.time(),
        )

    def _check_limits(self, session: EnrichmentSessionV3) -> bool:
        """
        Check if enrichment should continue within limits.

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

    def _should_continue_to_step2(self, status: ProductStatus) -> bool:
        """
        Check if pipeline should continue to Step 2.

        Returns:
            False if COMPLETE, True otherwise
        """
        return status != ProductStatus.COMPLETE

    def _validate_and_track(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Validate product match using ProductMatchValidator.

        Args:
            target_data: Target product data
            extracted_data: Extracted data from source

        Returns:
            Tuple of (is_match, reason)
        """
        validator = self._get_validator()
        return validator.validate(target_data, extracted_data)

    def _merge_with_confidence(
        self,
        existing_data: Dict[str, Any],
        existing_confidences: Dict[str, float],
        new_data: Dict[str, Any],
        new_confidence: float,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Merge data using ConfidenceBasedMerger.

        Args:
            existing_data: Current product data
            existing_confidences: Current field confidences
            new_data: New data to merge
            new_confidence: Confidence for new data

        Returns:
            Tuple of (merged_data, enriched_fields)
        """
        merger = self._get_merger()
        return merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

    async def _assess_status(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        confidences: Dict[str, float],
    ) -> ProductStatus:
        """
        Assess product status using QualityGateV3.

        Returns:
            ProductStatus enum value
        """
        try:
            quality_gate = self._get_quality_gate()
            assessment = await quality_gate.aassess(
                extracted_data=product_data,
                product_type=product_type,
                field_confidences=confidences,
            )
            return assessment.status

        except Exception as e:
            logger.warning(
                "Failed to assess status for %s: %s",
                product_type,
                str(e),
            )
            return ProductStatus.PARTIAL

    async def _search_sources(
        self,
        query: str,
        session: EnrichmentSessionV3,
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


# Singleton instance
_pipeline_instance: Optional[EnrichmentPipelineV3] = None


def get_enrichment_pipeline_v3(**kwargs) -> EnrichmentPipelineV3:
    """Get or create EnrichmentPipelineV3 singleton."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = EnrichmentPipelineV3(**kwargs)
    return _pipeline_instance


def reset_enrichment_pipeline_v3() -> None:
    """Reset singleton for testing."""
    global _pipeline_instance
    _pipeline_instance = None
