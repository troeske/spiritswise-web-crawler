"""
2-Step Enrichment Pipeline V3 for Generic Search Discovery.

This module implements the V3 enrichment pipeline specifically designed for
products discovered through generic search (listicles, "best of" articles).
It differs from the Competition Flow's 3-step pipeline because generic search
results contain inline product text rather than detail page links.

Task Reference: GENERIC_SEARCH_V3_TASKS.md Task 1.3
Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.1 (FEAT-001)

Pipeline Steps:
    Step 1 - Producer Page Search:
        Searches for the official producer/brand page using the query pattern
        "{brand} {name} official". Filters results to prioritize official sites
        over retailers. Validates extracted data matches target product.
        Confidence boost: +0.10 (capped at 0.95) for producer data.

    Step 2 - Review Site Enrichment:
        If product is not COMPLETE after Step 1, searches review sites using
        EnrichmentConfig templates. Iterates through configs by priority until
        COMPLETE status is reached or limits are hit. Uses 0.75 confidence
        for review site data.

Key Differences from Competition Flow (3-step):
    - No detail page step (listicles have inline text, no detail_url)
    - Starts with producer search instead of detail extraction
    - Only 2 steps instead of 3 (Detail -> Producer -> Review becomes Producer -> Review)

Integration Points:
    - ProductMatchValidator: Prevents cross-contamination between similar products
    - ConfidenceBasedMerger: Intelligent field merging based on source confidence
    - QualityGateV3: Status assessment with 90% ECP threshold for COMPLETE

Example:
    >>> pipeline = EnrichmentPipelineV3()
    >>> result = await pipeline.enrich_product(
    ...     product_data={"name": "Lagavulin 16", "brand": "Lagavulin"},
    ...     product_type="whiskey",
    ... )
    >>> print(result.status_after)
    "COMPLETE"
    >>> print(result.sources_used)
    ["https://lagavulin.com/16-year-old", "https://whiskyadvocate.com/lagavulin-16"]

Usage:
    from crawler.services.enrichment_pipeline_v3 import get_enrichment_pipeline_v3

    pipeline = get_enrichment_pipeline_v3()
    result = await pipeline.enrich_product(product_data, product_type)

    if result.success:
        # Access enriched data and tracking info
        enriched_data = result.product_data
        sources = result.sources_used
        fields = result.fields_enriched
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


# Known retailer domains to deprioritize in producer search.
# These sites sell products but are not authoritative sources for product information.
# URLs containing these domains are sorted to the end of search results.
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
    Tracks state during a 2-step enrichment operation.

    This session dataclass maintains all state needed during enrichment,
    including the current product data, field confidences, step completion
    status, source tracking, and resource limits.

    The session is specific to the Generic Search 2-step pipeline and
    tracks both producer page (Step 1) and review site (Step 2) enrichment.

    Attributes:
        product_type: Product type for extraction schema (e.g., "whiskey", "port_wine").
        initial_data: Original product data at session start (immutable reference).
        current_data: Current product data being enriched (mutated during session).
        field_confidences: Dict mapping field names to confidence scores (0.0-1.0).
        step_1_completed: True if producer page search step has completed.
        step_2_completed: True if review site enrichment step has completed.
        sources_searched: List of all URLs that were searched/fetched.
        sources_used: List of URLs that contributed data to enrichment.
        sources_rejected: List of dicts with 'url' and 'reason' for rejected sources.
        status_progression: List of status values showing progression (e.g., ["PARTIAL", "BASELINE", "COMPLETE"]).
        fields_enriched: List of field names that were enriched during session.
        field_provenance: Dict mapping field names to the source URL that provided them.
        searches_performed: Counter of SerpAPI searches executed.
        max_searches: Maximum allowed SerpAPI searches (from ProductTypeConfig).
        max_sources: Maximum source URLs to use per product.
        max_time_seconds: Maximum time allowed for enrichment.
        start_time: Unix timestamp when session started.
    """

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any] = field(default_factory=dict)
    field_confidences: Dict[str, float] = field(default_factory=dict)

    # 2-Step tracking
    step_1_completed: bool = False  # Producer page search
    step_2_completed: bool = False  # Review site enrichment

    # Source tracking per spec Section 5.6
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)

    # Status tracking
    status_progression: List[str] = field(default_factory=list)

    # Fields tracking for audit trail
    fields_enriched: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Resource limits (from ProductTypeConfig or defaults)
    searches_performed: int = 0
    max_searches: int = 3
    max_sources: int = 5
    max_time_seconds: float = 120.0
    start_time: float = 0.0

    def __post_init__(self) -> None:
        """Initialize current_data from initial_data if empty."""
        if not self.current_data:
            self.current_data = dict(self.initial_data)
        if self.start_time == 0.0:
            self.start_time = time.time()


@dataclass
class EnrichmentResultV3:
    """
    Result of a 2-step enrichment operation.

    Contains the enriched product data along with comprehensive tracking
    information for audit, debugging, and quality assessment.

    Attributes:
        success: True if enrichment completed without errors.
        product_data: Final enriched product data dict.
        quality_status: Final quality status (e.g., "COMPLETE", "PARTIAL").
        step_1_completed: True if producer page step completed.
        step_2_completed: True if review site step completed.
        sources_searched: All URLs that were searched/fetched.
        sources_used: URLs that contributed data.
        sources_rejected: List of dicts with rejection reasons.
        fields_enriched: Field names that were enriched.
        field_provenance: Maps field names to source URLs.
        status_before: Quality status before enrichment.
        status_after: Quality status after enrichment.
        status_progression: List of status transitions.
        searches_performed: Number of SerpAPI searches used.
        time_elapsed_seconds: Total enrichment time.
        error: Error message if success is False.

    Spec Reference: Section 5.6 (FEAT-006) for source tracking fields.
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

    Implements the 2-step enrichment pipeline from spec Section 5.1. This
    pipeline is designed for products discovered through generic search
    (listicles, "best of" articles) which have inline product text rather
    than links to detail pages.

    Pipeline Steps:
        Step 1 - Producer Page Search:
            Searches for official producer/brand pages using "{brand} {name} official".
            Filters results to prioritize official sites over retailers.
            Validates extracted data using ProductMatchValidator.
            Applies confidence boost (+0.10) for authoritative producer data.

        Step 2 - Review Site Enrichment:
            Only runs if product is not COMPLETE after Step 1.
            Uses EnrichmentConfig templates ordered by priority.
            Continues until COMPLETE status or limits reached.
            Uses 0.75 confidence for review site data.

    Key Features:
        - ProductMatchValidator integration prevents cross-contamination
        - ConfidenceBasedMerger ensures high-quality data is preserved
        - Early exit when COMPLETE (90% ECP) is reached
        - Comprehensive source tracking for audit trail
        - Configurable limits from ProductTypeConfig

    Comparison with Competition Flow (3-step):
        Competition Flow: Detail Page -> Producer Search -> Review Sites
        Generic Search V3: Producer Search -> Review Sites (no detail page)

        The difference is because competition results link to detail pages
        with structured data, while generic search results are listicles
        with inline product text.

    Attributes:
        ai_client: AIClientV2 for content extraction.
        DEFAULT_TIMEOUT: HTTP request timeout (30 seconds).
        DEFAULT_MAX_SOURCES: Maximum sources per product (5).
        DEFAULT_MAX_SEARCHES: Maximum SerpAPI searches (3).
        DEFAULT_MAX_TIME_SECONDS: Maximum enrichment time (120 seconds).
        PRODUCER_CONFIDENCE_BOOST: Confidence boost for producer data (+0.10).
        PRODUCER_CONFIDENCE_MAX: Maximum producer confidence (0.95).
        REVIEW_SITE_CONFIDENCE: Default review site confidence (0.75).

    Example:
        >>> pipeline = EnrichmentPipelineV3()
        >>> result = await pipeline.enrich_product(
        ...     {"name": "Glenfiddich 18", "brand": "Glenfiddich"},
        ...     "whiskey"
        ... )
        >>> if result.success:
        ...     print(f"Enriched to {result.status_after}")
        ...     print(f"Used {len(result.sources_used)} sources")
    """

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_SOURCES = 5
    DEFAULT_MAX_SEARCHES = 3
    DEFAULT_MAX_TIME_SECONDS = 120.0

    # Confidence settings per spec
    PRODUCER_CONFIDENCE_BOOST = 0.10  # Added to base confidence for producer pages
    PRODUCER_CONFIDENCE_MAX = 0.95    # Cap to avoid overconfidence
    REVIEW_SITE_CONFIDENCE = 0.75     # Default confidence for review site data

    def __init__(
        self,
        ai_client: Optional[AIClientV2] = None,
        serp_client: Optional[Any] = None,
        quality_gate: Optional[QualityGateV3] = None,
        product_match_validator: Optional[ProductMatchValidator] = None,
        confidence_merger: Optional[ConfidenceBasedMerger] = None,
    ) -> None:
        """
        Initialize the 2-step enrichment pipeline.

        All dependencies are optional and will be lazily initialized from
        singletons if not provided. This allows for easy testing with mocks.

        Args:
            ai_client: AIClientV2 for content extraction. If None, uses
                get_ai_client_v2() singleton.
            serp_client: SerpAPI client for search. If None, creates new
                SerpAPIClient instance on first use.
            quality_gate: QualityGateV3 for status assessment. If None,
                uses get_quality_gate_v3() singleton.
            product_match_validator: Validator for product matching. If None,
                uses get_product_match_validator() singleton.
            confidence_merger: Merger for confidence-based data merging.
                If None, uses get_confidence_merger() singleton.
        """
        self.ai_client = ai_client
        self._serp_client = serp_client
        self._quality_gate = quality_gate
        self._validator = product_match_validator
        self._merger = confidence_merger

        logger.debug("EnrichmentPipelineV3 initialized")

    @property
    def serp_client(self) -> Any:
        """Lazy-load SerpAPI client on first access."""
        if self._serp_client is None:
            from crawler.discovery.serpapi_client import SerpAPIClient
            self._serp_client = SerpAPIClient()
        return self._serp_client

    def _get_ai_client(self) -> AIClientV2:
        """Get or create AI client from singleton."""
        if self.ai_client is None:
            self.ai_client = get_ai_client_v2()
        return self.ai_client

    def _get_quality_gate(self) -> QualityGateV3:
        """Get or create quality gate from singleton."""
        if self._quality_gate is None:
            self._quality_gate = get_quality_gate_v3()
        return self._quality_gate

    def _get_validator(self) -> ProductMatchValidator:
        """Get or create product match validator from singleton."""
        if self._validator is None:
            self._validator = get_product_match_validator()
        return self._validator

    def _get_merger(self) -> ConfidenceBasedMerger:
        """Get or create confidence merger from singleton."""
        if self._merger is None:
            self._merger = get_confidence_merger()
        return self._merger

    # =========================================================================
    # Step 1: Producer Page Search
    # Spec Reference: Section 5.1 Step 1
    # =========================================================================

    def _build_producer_search_query(self, product_data: Dict[str, Any]) -> str:
        """
        Build search query for producer page search.

        Constructs query in format "{brand} {name} official" to find
        official producer/brand pages rather than retailers or review sites.

        Args:
            product_data: Product data with 'name' and 'brand' fields.

        Returns:
            Search query string. Returns "official" if both brand and name
            are empty (which will be caught by caller).

        Example:
            >>> pipeline._build_producer_search_query(
            ...     {"name": "Lagavulin 16", "brand": "Lagavulin"}
            ... )
            "Lagavulin Lagavulin 16 official"
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

        Sorts URLs into three priority tiers:
        1. Official sites (brand/producer name in domain) - highest priority
        2. Non-retailers (blogs, review sites) - medium priority
        3. Retailers (from RETAILER_DOMAINS) - lowest priority

        This ensures we try official sources first, as they have the most
        authoritative product information.

        Args:
            urls: List of URLs from search results.
            brand: Product brand name for domain matching.
            producer: Product producer name for domain matching.

        Returns:
            Sorted list with official sites first, then non-retailers,
            then retailers last.

        Example:
            >>> urls = [
            ...     "https://masterofmalt.com/lagavulin-16",
            ...     "https://lagavulin.com/16-year-old",
            ...     "https://whiskyadvocate.com/reviews/lagavulin-16",
            ... ]
            >>> filtered = pipeline._filter_producer_urls(urls, "Lagavulin", "Lagavulin")
            >>> print(filtered[0])
            "https://lagavulin.com/16-year-old"  # Official site first
        """
        # Normalize brand/producer for domain matching
        brand_lower = brand.lower().replace(" ", "").replace("'", "").replace("-", "")
        producer_lower = (producer or "").lower().replace(" ", "").replace("'", "").replace("-", "")

        def get_domain(url: str) -> str:
            """Extract normalized domain from URL."""
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")

        def is_retailer(url: str) -> bool:
            """Check if URL is from a known retailer domain."""
            domain = get_domain(url)
            return any(r in domain for r in RETAILER_DOMAINS)

        def is_likely_official(url: str) -> bool:
            """Check if brand/producer name appears in domain (likely official site)."""
            domain = get_domain(url).replace("-", "").replace(".", "")
            # Require minimum 4 chars to avoid false positives
            if brand_lower and len(brand_lower) > 3 and brand_lower in domain:
                return True
            if producer_lower and len(producer_lower) > 3 and producer_lower in domain:
                return True
            return False

        # Categorize URLs into priority tiers
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

        Producer/official pages are considered more authoritative than
        review sites or retailers, so we boost their confidence by +0.10
        (capped at 0.95 to avoid overconfidence).

        Args:
            confidences: Original field confidences from extraction.

        Returns:
            New dict with boosted confidences. Original dict is not modified.
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
            product_data: Current product data (needs 'name', 'brand').
            product_type: Product type for extraction schema.
            session: Current enrichment session for tracking.

        Returns:
            Tuple of (extracted_data, field_confidences). Returns empty dicts
            if no valid producer page is found or all fail validation.
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

            # Filter and prioritize URLs (official sites first)
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
                    # Extract with full schema, passing target product for matching
                    extracted, confidences = await self._fetch_and_extract(
                        url, product_type, [], target_product=product_data
                    )

                    if extracted:
                        # Validate product match to prevent cross-contamination
                        is_match, reason = self._validate_and_track(
                            product_data, extracted
                        )

                        if is_match:
                            # Boost confidence for official site data
                            boosted = self._apply_producer_confidence_boost(confidences)
                            session.sources_used.append(url)

                            # Track which URL provided which fields
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
    # Step 2: Review Site Enrichment
    # Spec Reference: Section 5.1 Step 2
    # =========================================================================

    def _get_review_site_confidence(self) -> float:
        """
        Get confidence score for review site data.

        Review sites are less authoritative than producer pages but more
        authoritative than retailers or generic search results.

        Returns:
            Confidence score (default 0.75, range 0.70-0.80).
        """
        return self.REVIEW_SITE_CONFIDENCE

    async def _load_enrichment_configs(
        self,
        product_type: str,
    ) -> List[EnrichmentConfig]:
        """
        Load EnrichmentConfig entries for product type ordered by priority.

        EnrichmentConfigs define search templates for different review sites
        and are configured per product type in the admin.

        Args:
            product_type: Product type (e.g., "whiskey", "port_wine").

        Returns:
            List of active EnrichmentConfig instances ordered by priority
            (highest first). Returns empty list if none found.
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

        Iterates through EnrichmentConfigs by priority, executing searches
        and extracting data from results. Continues until COMPLETE status
        is reached or resource limits are hit.

        Process:
        1. Load EnrichmentConfigs by priority
        2. For each config: build search query from template, execute search
        3. For each URL: fetch, extract, validate product match
        4. If match: merge by confidence (0.75 for review sites)
        5. Stop when COMPLETE or limits reached

        Args:
            product_data: Current product data to enrich.
            product_type: Product type for extraction schema.
            session: Current enrichment session for tracking.

        Returns:
            Tuple of (merged_data, updated_confidences).
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

            # Check status - stop if already COMPLETE
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
                    # Get target fields from config if available
                    target_fields = (
                        config.target_fields
                        if hasattr(config, "target_fields") and config.target_fields
                        else []
                    )

                    extracted, confidences = await self._fetch_and_extract(
                        url, product_type, target_fields, target_product=merged_data
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

        Substitutes placeholders like {name}, {brand} with values from
        product_data. Removes any unsubstituted placeholders.

        Args:
            config: EnrichmentConfig with search_template field.
            product_data: Product data for substitution.

        Returns:
            Completed search query string. May be empty if template
            contains only unsubstituted placeholders.

        Example:
            >>> config.search_template = "{brand} {name} review whisky advocate"
            >>> query = pipeline._build_config_search_query(
            ...     config, {"brand": "Lagavulin", "name": "16 Year Old"}
            ... )
            >>> print(query)
            "Lagavulin 16 Year Old review whisky advocate"
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
    # Main Orchestration
    # Spec Reference: Section 5.1 Main Flow
    # =========================================================================

    async def enrich_product(
        self,
        product_data: Dict[str, Any],
        product_type: str,
        initial_confidences: Optional[Dict[str, float]] = None,
    ) -> EnrichmentResultV3:
        """
        Execute 2-step enrichment pipeline for a product.

        Main entry point for the V3 enrichment pipeline. Executes both steps
        in order, with early exit if COMPLETE status is reached after Step 1.

        Steps:
        1. Search for official producer/brand page
        2. If not COMPLETE: Search review sites for additional data

        Args:
            product_data: Initial product data (skeleton from listicle extraction).
                Must have at least 'name' and preferably 'brand'.
            product_type: Product type for schema selection (e.g., "whiskey").
            initial_confidences: Optional initial field confidence scores.
                If None, all existing fields assumed to have 0.0 confidence.

        Returns:
            EnrichmentResultV3 with enriched data and comprehensive tracking
            including sources_used, fields_enriched, status_progression, etc.

        Example:
            >>> pipeline = EnrichmentPipelineV3()
            >>> result = await pipeline.enrich_product(
            ...     {"name": "Macallan 18", "brand": "The Macallan"},
            ...     "whiskey"
            ... )
            >>> print(f"Status: {result.status_before} -> {result.status_after}")
            >>> print(f"Enriched fields: {result.fields_enriched}")
        """
        logger.info(
            "Starting 2-step enrichment for product: %s (type=%s)",
            product_data.get("name", "unknown"),
            product_type,
        )

        # Create session with limits from config
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
                # Merge producer data with base confidence of 0.85
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
        """
        Create enrichment session with limits from ProductTypeConfig.

        Loads configuration limits from the database or uses defaults if
        no config is found.

        Args:
            product_type: Product type for config lookup.
            initial_data: Initial product data to enrich.
            initial_confidences: Optional initial field confidences.

        Returns:
            Configured EnrichmentSessionV3 ready for enrichment.
        """
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
        Check if enrichment should continue within resource limits.

        Enforces max_searches, max_sources, and max_time limits to prevent
        runaway enrichment operations.

        Args:
            session: Current enrichment session.

        Returns:
            True if within all limits, False if any limit is exceeded.
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
        Check if pipeline should continue to Step 2 (review sites).

        Step 2 is skipped if product reached COMPLETE status after Step 1,
        as there's no need to search review sites for additional data.

        Args:
            status: Current product status after Step 1.

        Returns:
            False if COMPLETE, True for all other statuses.
        """
        return status != ProductStatus.COMPLETE

    def _validate_and_track(
        self,
        target_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Validate product match using ProductMatchValidator.

        Wrapper around the validator that provides logging and tracking.

        Args:
            target_data: Target product data being enriched.
            extracted_data: Data extracted from a source.

        Returns:
            Tuple of (is_match, reason) from ProductMatchValidator.
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

        Wrapper around the merger that provides consistent interface.

        Args:
            existing_data: Current product data.
            existing_confidences: Current field confidences.
            new_data: New data to merge.
            new_confidence: Confidence for new data source.

        Returns:
            Tuple of (merged_data, enriched_fields).
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

        Uses the V3 quality gate which includes category-specific requirements
        and 90% ECP threshold for COMPLETE status.

        Args:
            product_data: Product data to assess.
            product_type: Product type for requirements.
            confidences: Field confidences for assessment.

        Returns:
            ProductStatus enum value (SKELETON, PARTIAL, BASELINE, ENRICHED, COMPLETE).
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

        Requests up to 10 results but adjusts based on remaining source capacity.

        Args:
            query: Search query string.
            session: Current enrichment session for limit checking.

        Returns:
            List of URLs to extract from. Excludes URLs already searched.
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

    def _find_best_matching_product(
        self,
        products: List[Any],
        target_data: Dict[str, Any],
    ) -> Optional[Any]:
        """
        Find the product from extraction results that best matches the target.

        When a page contains multiple products (e.g., bulleit.com lists Bourbon,
        Rye, etc.), this method finds the one that matches our target product
        instead of blindly taking products[0].

        Matching criteria (in order of importance):
        1. Name token overlap (>= 30% of target name tokens)
        2. Brand match (case-insensitive)
        3. Category match (bourbon vs rye, single malt vs blended)

        Args:
            products: List of ExtractedProduct from AI extraction.
            target_data: Target product data with 'name', 'brand', 'category'.

        Returns:
            Best matching product, or None if no good match found.
        """
        if not products:
            return None

        if len(products) == 1:
            return products[0]

        target_name = (target_data.get("name") or "").lower()
        target_brand = (target_data.get("brand") or "").lower()
        target_category = (target_data.get("category") or "").lower()

        # Tokenize target name for overlap calculation
        target_tokens = set(target_name.split())

        best_match = None
        best_score = -1

        for product in products:
            extracted = product.extracted_data or {}
            extracted_name = (extracted.get("name") or "").lower()
            extracted_brand = (extracted.get("brand") or "").lower()
            extracted_category = (extracted.get("category") or "").lower()

            score = 0

            # Name token overlap (most important)
            extracted_tokens = set(extracted_name.split())
            if target_tokens and extracted_tokens:
                overlap = len(target_tokens & extracted_tokens)
                overlap_ratio = overlap / len(target_tokens)
                score += overlap_ratio * 50  # Up to 50 points

            # Brand match
            if target_brand and extracted_brand:
                if target_brand == extracted_brand:
                    score += 30  # Exact match
                elif target_brand in extracted_brand or extracted_brand in target_brand:
                    score += 20  # Partial match

            # Category match (penalize mismatches)
            if target_category and extracted_category:
                # Check for mutually exclusive categories
                bourbon_keywords = {"bourbon"}
                rye_keywords = {"rye"}
                single_malt_keywords = {"single malt", "singlemalt"}
                blended_keywords = {"blend", "blended"}

                target_is_bourbon = any(k in target_category for k in bourbon_keywords)
                extracted_is_rye = any(k in extracted_category for k in rye_keywords)

                target_is_single_malt = any(k in target_category for k in single_malt_keywords)
                extracted_is_blended = any(k in extracted_category for k in blended_keywords)

                # Penalize category mismatches
                if target_is_bourbon and extracted_is_rye:
                    score -= 40
                elif target_is_single_malt and extracted_is_blended:
                    score -= 40
                elif target_category == extracted_category:
                    score += 20  # Exact category match bonus

            logger.debug(
                "Product match score for '%s': %.1f (target: '%s')",
                extracted_name[:30],
                score,
                target_name[:30],
            )

            if score > best_score:
                best_score = score
                best_match = product

        # Only return if we have a reasonable match (score > 10)
        # Minimum score of 10 ensures at least some token overlap or brand match
        # to prevent cross-contamination from completely unrelated products
        MIN_MATCH_SCORE = 10.0

        if best_score >= MIN_MATCH_SCORE:
            logger.info(
                "Selected best matching product: '%s' (score: %.1f)",
                (best_match.extracted_data or {}).get("name", "Unknown")[:40],
                best_score,
            )
            return best_match

        # No good match - return None to prevent cross-contamination
        # This is safer than falling back to products[0] which caused issues
        logger.warning(
            "No good product match found (best score: %.1f < min %.1f), "
            "rejecting all %d extracted products to prevent cross-contamination",
            best_score,
            MIN_MATCH_SCORE,
            len(products),
        )
        return None

    async def _fetch_and_extract(
        self,
        url: str,
        product_type: str,
        target_fields: List[str],
        target_product: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Fetch URL content and extract product data.

        Uses httpx for fetching and AIClientV2 for extraction. When multiple
        products are extracted from a page, uses target_product to select the
        best matching one instead of blindly taking the first.

        Args:
            url: Source URL to fetch.
            product_type: Product type for extraction schema.
            target_fields: Fields to prioritize in extraction (from EnrichmentConfig).
            target_product: Target product data for matching (name, brand, category).
                If provided and multiple products extracted, selects best match.

        Returns:
            Tuple of (extracted_data, field_confidences). Returns empty dicts
            on any error or if no products are found.
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

            # Select best matching product when multiple are found
            if len(result.products) > 1 and target_product:
                logger.info(
                    "Multiple products (%d) extracted from %s, selecting best match",
                    len(result.products),
                    url,
                )
                product = self._find_best_matching_product(
                    result.products, target_product
                )
                # If no good match found, return empty to prevent cross-contamination
                if product is None:
                    logger.info(
                        "No matching product found in %d extracted products from %s",
                        len(result.products),
                        url,
                    )
                    return {}, {}
            else:
                product = result.products[0]

            extracted_data = product.extracted_data or {}
            field_confidences = product.field_confidences or {}

            if not field_confidences:
                # Use overall product confidence if no field-level confidences
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


# Singleton instance for module-level access
_pipeline_instance: Optional[EnrichmentPipelineV3] = None


def get_enrichment_pipeline_v3(**kwargs) -> EnrichmentPipelineV3:
    """
    Get or create EnrichmentPipelineV3 singleton.

    Creates a new instance on first call, then returns the same instance
    on subsequent calls. Accepts keyword arguments for initial configuration.

    Args:
        **kwargs: Passed to EnrichmentPipelineV3 constructor on first call.

    Returns:
        The shared EnrichmentPipelineV3 instance.

    Example:
        >>> pipeline = get_enrichment_pipeline_v3()
        >>> result = await pipeline.enrich_product(data, "whiskey")
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = EnrichmentPipelineV3(**kwargs)
    return _pipeline_instance


def reset_enrichment_pipeline_v3() -> None:
    """
    Reset singleton for testing.

    Clears the singleton so the next call to get_enrichment_pipeline_v3()
    creates a fresh instance.
    """
    global _pipeline_instance
    _pipeline_instance = None
