"""
Competition Orchestrator V2 - Orchestrates competition discovery with V2 components.

Phase 7 of V2 Architecture: Integrates AIExtractorV2, QualityGateV2 for
award/competition discovery pipeline.

Features:
- Uses AIExtractorV2 for content extraction
- Uses QualityGateV2 for quality assessment
- Preserves award data (medal, competition, year)
- Determines enrichment needs for incomplete products
- Backward compatible with V1 pipeline methods (run_competition_discovery, etc.)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async

from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2, get_ai_extractor_v2
from crawler.services.quality_gate_v2 import (
    ProductStatus,
    QualityGateV2,
    QualityAssessment,
    get_quality_gate_v2,
)

logger = logging.getLogger(__name__)


@dataclass
class CompetitionExtractionResult:
    """Result of single competition URL extraction."""

    success: bool
    product_data: Optional[Dict[str, Any]] = None
    quality_status: Optional[str] = None
    needs_enrichment: bool = False
    error: Optional[str] = None
    field_confidences: Dict[str, float] = field(default_factory=dict)
    award_data: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None


@dataclass
class CompetitionBatchResult:
    """Result of batch competition processing."""

    success: bool
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    needs_enrichment: int = 0
    complete: int = 0
    errors: List[str] = field(default_factory=list)
    results: List[CompetitionExtractionResult] = field(default_factory=list)


@dataclass
class CompetitionDiscoveryResult:
    """Result of competition discovery process (V1 compatibility)."""

    competition: str
    year: int
    awards_found: int = 0
    skeletons_created: int = 0
    skeletons_updated: int = 0
    products_created: int = 0
    products_updated: int = 0
    products_filtered: int = 0
    errors: List[str] = field(default_factory=list)
    success: bool = True
    awards_data: List[Dict[str, Any]] = field(default_factory=list)
    health_status: Optional[Dict[str, Any]] = None
    yield_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "competition": self.competition,
            "year": self.year,
            "awards_found": self.awards_found,
            "products_filtered": self.products_filtered,
            "skeletons_created": self.skeletons_created,
            "skeletons_updated": self.skeletons_updated,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "errors": self.errors,
            "success": self.success,
            "health_status": self.health_status,
            "yield_summary": self.yield_summary,
        }


@dataclass
class EnrichmentResult:
    """Result of skeleton enrichment process."""

    skeletons_processed: int = 0
    urls_discovered: int = 0
    urls_queued: int = 0
    errors: List[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skeletons_processed": self.skeletons_processed,
            "urls_discovered": self.urls_discovered,
            "urls_queued": self.urls_queued,
            "errors": self.errors,
            "success": self.success,
        }


class CompetitionOrchestratorV2:
    """
    V2 Competition Orchestrator using V2 architecture components.

    Orchestrates:
    - Award page extraction via AIExtractorV2
    - Quality assessment via QualityGateV2
    - Enrichment queue decisions
    - Award data preservation
    - V1 compatibility for run_competition_discovery() and enrichment
    """

    def __init__(
        self,
        ai_extractor: Optional[AIExtractorV2] = None,
        quality_gate: Optional[QualityGateV2] = None,
        serpapi_key: Optional[str] = None,
        results_per_search: int = 5,
    ):
        """
        Initialize the Competition Orchestrator V2.

        Args:
            ai_extractor: AIExtractorV2 instance (optional, creates default)
            quality_gate: QualityGateV2 instance (optional, creates default)
            serpapi_key: Optional SerpAPI key for enrichment searches
            results_per_search: Number of results per enrichment search
        """
        self.ai_extractor = ai_extractor or get_ai_extractor_v2()
        self.quality_gate = quality_gate or get_quality_gate_v2()

        # Initialize V1 components for backward compatibility
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher
        from crawler.queue.url_frontier import get_url_frontier

        self.skeleton_manager = SkeletonProductManager()
        self.enrichment_searcher = EnrichmentSearcher(
            api_key=serpapi_key,
            results_per_search=results_per_search,
        )
        self.url_frontier = get_url_frontier()

        logger.debug("CompetitionOrchestratorV2 initialized")

    async def process_competition_url(
        self,
        url: str,
        source: str,
        year: int,
        medal_hint: Optional[str] = None,
        score_hint: Optional[str] = None,
        product_type: str = "whiskey",
        product_category: Optional[str] = None,
    ) -> CompetitionExtractionResult:
        """
        Process a single competition URL with V2 components.

        Args:
            url: Detail page URL to extract from
            source: Competition source (iwsc, sfwsc, dwwa, etc.)
            year: Competition year
            medal_hint: Optional medal hint (Gold, Silver, etc.)
            score_hint: Optional score hint
            product_type: Product type (whiskey, port_wine)
            product_category: Optional category (bourbon, single_malt, etc.)

        Returns:
            CompetitionExtractionResult with extraction and quality data
        """
        logger.info("Processing competition URL: %s (source=%s, year=%s)", url, source, year)

        try:
            # Build context for extraction
            context = {
                "source": source,
                "year": year,
                "medal_hint": medal_hint,
                "score_hint": score_hint,
                "product_type_hint": product_type,
                "product_category_hint": product_category,
            }

            # Extract using AIExtractorV2
            extracted = await self.ai_extractor.extract(url=url, context=context)

            if "error" in extracted and not extracted.get("name"):
                return CompetitionExtractionResult(
                    success=False,
                    error=extracted.get("error", "Extraction failed"),
                    source_url=url,
                )

            # Get field confidences
            field_confidences = extracted.pop("field_confidences", {})
            overall_confidence = extracted.pop("overall_confidence", 0.0)

            # Assess quality
            assessment = self._assess_quality(
                product_data=extracted,
                field_confidences=field_confidences,
                product_type=product_type,
            )

            # Determine enrichment need
            needs_enrichment = self._should_enrich(assessment.status)

            # Build award data
            award_data = {
                "medal": medal_hint,
                "competition": source.upper(),
                "year": year,
                "score": extracted.get("award_score"),
            }

            return CompetitionExtractionResult(
                success=True,
                product_data=extracted,
                quality_status=assessment.status.value,
                needs_enrichment=needs_enrichment,
                field_confidences=field_confidences,
                award_data=award_data,
                source_url=url,
            )

        except Exception as e:
            logger.exception("Error processing competition URL %s: %s", url, e)
            return CompetitionExtractionResult(
                success=False,
                error=str(e),
                source_url=url,
            )

    async def process_competition_batch(
        self,
        urls: List[Dict[str, Any]],
        source: str,
        year: int,
        product_type: str = "whiskey",
    ) -> CompetitionBatchResult:
        """
        Process a batch of competition URLs.

        Args:
            urls: List of dicts with url, medal_hint, score_hint
            source: Competition source
            year: Competition year
            product_type: Product type

        Returns:
            CompetitionBatchResult with batch statistics
        """
        result = CompetitionBatchResult(success=True)

        for url_info in urls:
            try:
                extraction_result = await self.process_competition_url(
                    url=url_info.get("url") or url_info.get("detail_url"),
                    source=source,
                    year=year,
                    medal_hint=url_info.get("medal_hint"),
                    score_hint=url_info.get("score_hint"),
                    product_type=product_type,
                )

                result.total_processed += 1
                result.results.append(extraction_result)

                if extraction_result.success:
                    result.successful += 1
                    if extraction_result.needs_enrichment:
                        result.needs_enrichment += 1
                    else:
                        result.complete += 1
                else:
                    result.failed += 1
                    if extraction_result.error:
                        result.errors.append(extraction_result.error)

            except Exception as e:
                result.failed += 1
                result.errors.append(str(e))
                result.total_processed += 1

        return result

    async def run_competition_discovery(
        self,
        competition_url: str,
        crawl_job,
        html_content: str,
        competition_key: str,
        year: int,
        product_types: list = None,
        max_results: int = 10,
    ) -> CompetitionDiscoveryResult:
        """
        Run competition discovery: parse results and create skeleton products.

        V1-compatible method that uses V2 quality assessment internally.

        Args:
            competition_url: URL of the competition results page
            crawl_job: CrawlJob tracking this crawl
            html_content: Raw HTML content of the competition results page
            competition_key: Key for the competition parser (e.g., "iwsc")
            year: Competition year
            product_types: List of product types to filter for
            max_results: Maximum number of products to create

        Returns:
            CompetitionDiscoveryResult with statistics
        """
        from crawler.discovery.competitions.parsers import get_parser
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus, ProductAward

        result = CompetitionDiscoveryResult(
            competition=competition_key.upper(),
            year=year,
        )

        try:
            # Get appropriate parser
            parser = get_parser(competition_key)
            if not parser:
                result.errors.append(f"No parser found for competition: {competition_key}")
                result.success = False
                return result

            # Parse competition results
            logger.info(f"Parsing {competition_key.upper()} results for year {year}")
            award_data_list = parser.parse(html_content, year)
            result.awards_found = len(award_data_list)
            result.awards_data = award_data_list

            # Filter by product type if specified
            if product_types:
                filtered_list = self._filter_awards_by_product_type(award_data_list, product_types)
                result.products_filtered = len(award_data_list) - len(filtered_list)
                award_data_list = filtered_list
                logger.info(f"Filtered to {len(award_data_list)} awards matching product_types: {product_types}")

            # Limit results
            if max_results and len(award_data_list) > max_results:
                logger.info(f"Limiting from {len(award_data_list)} to {max_results} results")
                award_data_list = award_data_list[:max_results]

            if not award_data_list:
                logger.warning(f"No awards found for {competition_key.upper()} {year}")
                return result

            # Get source for this competition
            source = crawl_job.source if crawl_job else None

            # Create skeleton products from awards
            for award_data in award_data_list:
                try:
                    # Get award count before creation for comparison
                    existing_product = await sync_to_async(
                        lambda: DiscoveredProduct.objects.filter(
                            fingerprint=self.skeleton_manager._compute_skeleton_fingerprint(award_data),
                            status=DiscoveredProductStatus.SKELETON,
                        ).first(),
                        thread_sensitive=True,
                    )()

                    award_count_before = 0
                    if existing_product:
                        award_count_before = await sync_to_async(
                            lambda: ProductAward.objects.filter(product=existing_product).count(),
                            thread_sensitive=True,
                        )()

                    # Wrap sync ORM call for async context
                    create_skeleton = sync_to_async(
                        self.skeleton_manager.create_skeleton_product,
                        thread_sensitive=True,
                    )
                    product = await create_skeleton(
                        award_data=award_data,
                        source=source,
                        crawl_job=crawl_job,
                    )

                    # Check if this was a new creation or update using ProductAward count
                    award_count_after = await sync_to_async(
                        lambda: ProductAward.objects.filter(product=product).count(),
                        thread_sensitive=True,
                    )()

                    if not existing_product:
                        result.skeletons_created += 1
                    elif award_count_after > award_count_before:
                        result.skeletons_updated += 1

                except Exception as e:
                    error_msg = f"Failed to create skeleton for {award_data.get('product_name')}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            logger.info(
                f"Competition discovery complete: {result.awards_found} awards, "
                f"{result.skeletons_created} new skeletons, {result.skeletons_updated} updated"
            )

        except Exception as e:
            result.errors.append(f"Competition discovery failed: {e}")
            result.success = False
            logger.error(f"Competition discovery failed: {e}")

        return result

    def _filter_awards_by_product_type(
        self,
        award_data_list: List[Dict[str, Any]],
        product_types: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Filter awards to only include products matching the specified types.

        Args:
            award_data_list: List of award data dictionaries from parser
            product_types: List of product types to keep

        Returns:
            Filtered list of award data
        """
        if not product_types:
            return award_data_list

        # Define keywords for each product type
        type_keywords = {
            'whiskey': [
                'whisky', 'whiskey', 'bourbon', 'scotch', 'rye whiskey',
                'single malt', 'blended malt', 'irish whiskey', 'tennessee',
                'canadian whisky', 'japanese whisky', 'malt whisky',
            ],
            'whisky': [
                'whisky', 'whiskey', 'bourbon', 'scotch', 'rye whiskey',
                'single malt', 'blended malt', 'irish whiskey', 'tennessee',
                'canadian whisky', 'japanese whisky', 'malt whisky',
            ],
            'port_wine': [
                'port', 'porto', 'tawny', 'ruby port', 'vintage port',
                'late bottled vintage', 'lbv', 'colheita', 'white port',
            ],
            'brandy': [
                'brandy', 'cognac', 'armagnac', 'calvados', 'pisco',
                'grappa', 'eau de vie',
            ],
            'rum': ['rum', 'rhum', 'cachaca', 'ron'],
            'gin': ['gin', 'genever', 'london dry'],
            'vodka': ['vodka'],
            'tequila': ['tequila', 'mezcal', 'sotol'],
        }

        # Build set of keywords to match
        keywords_to_match = set()
        for product_type in product_types:
            keywords = type_keywords.get(product_type.lower(), [])
            keywords_to_match.update(kw.lower() for kw in keywords)

        if not keywords_to_match:
            logger.warning(f"No keywords found for product_types: {product_types}")
            return award_data_list

        # Negative keywords to filter out
        negative_keywords = [
            'winery', 'vineyard', 'wine cellar', 'chateau', 'domaine',
            'bodega', 'vino', 'estate wine', 'wine estate',
        ]

        filtered = []
        filtered_count = 0

        for award_data in award_data_list:
            product_name = (award_data.get('product_name') or '').lower()
            category = (award_data.get('category') or '').lower()
            combined_text = f"{product_name} {category}"

            # Check negative keywords first
            has_negative = False
            for neg in negative_keywords:
                if neg in combined_text:
                    # Exception: 'wine' in 'port wine' is OK
                    if neg == 'wine' and 'port' in combined_text:
                        continue
                    has_negative = True
                    break

            if has_negative:
                filtered_count += 1
                continue

            # Check positive keywords
            matches = False
            for keyword in keywords_to_match:
                if keyword in product_name or keyword in category:
                    matches = True
                    break

            if matches:
                filtered.append(award_data)
            else:
                filtered_count += 1

        if filtered_count > 0:
            logger.info(
                f"Product type filter: {len(award_data_list)} -> {len(filtered)} "
                f"(filtered {filtered_count}, types: {product_types})"
            )

        return filtered

    async def process_skeletons_for_enrichment(
        self,
        limit: int = 50,
        crawl_job=None,
    ) -> EnrichmentResult:
        """
        Process skeleton products for enrichment via SerpAPI searches.

        Args:
            limit: Maximum number of skeletons to process
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            EnrichmentResult with statistics
        """
        from crawler.discovery.competitions.enrichment_searcher import ENRICHMENT_PRIORITY

        result = EnrichmentResult()

        try:
            # Get unenriched skeleton products
            get_skeletons = sync_to_async(
                self.skeleton_manager.get_unenriched_skeletons,
                thread_sensitive=True,
            )
            skeletons = await get_skeletons(limit=limit)

            if not skeletons:
                logger.info("No unenriched skeleton products found")
                return result

            logger.info(f"Processing {len(skeletons)} skeleton products for enrichment")

            for skeleton in skeletons:
                try:
                    product_name = skeleton.name or ""
                    if not product_name:
                        continue

                    # Run enrichment search
                    search_results = await self.enrichment_searcher.search_for_enrichment(
                        product_name=product_name,
                        crawl_job=crawl_job,
                    )

                    result.skeletons_processed += 1
                    result.urls_discovered += len(search_results)

                    # Queue discovered URLs
                    queued = await self._queue_enrichment_urls(
                        search_results,
                        skeleton_id=str(skeleton.id),
                    )
                    result.urls_queued += queued

                    # Mark skeleton as having been searched
                    sources = skeleton.discovery_sources or []
                    if 'serpapi_enrichment' not in sources:
                        sources.append('serpapi_enrichment')
                        skeleton.discovery_sources = sources
                        save_skeleton = sync_to_async(
                            skeleton.save,
                            thread_sensitive=True,
                        )
                        await save_skeleton(update_fields=["discovery_sources"])

                except Exception as e:
                    error_msg = f"Enrichment failed for skeleton {skeleton.id}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            logger.info(
                f"Enrichment processing complete: {result.skeletons_processed} skeletons, "
                f"{result.urls_discovered} URLs found, {result.urls_queued} queued"
            )

        except Exception as e:
            result.errors.append(f"Enrichment processing failed: {e}")
            result.success = False
            logger.error(f"Enrichment processing failed: {e}")

        return result

    async def _queue_enrichment_urls(
        self,
        enrichment_results: List[Dict[str, Any]],
        skeleton_id: Optional[str] = None,
    ) -> int:
        """
        Queue URLs from enrichment search results.

        Args:
            enrichment_results: List of enrichment search result dicts
            skeleton_id: Optional skeleton product ID for metadata

        Returns:
            Number of URLs successfully queued
        """
        from crawler.discovery.competitions.enrichment_searcher import ENRICHMENT_PRIORITY

        queued = 0

        for result in enrichment_results:
            url = result.get("url", "")
            if not url:
                continue

            try:
                metadata = {
                    "search_type": result.get("search_type"),
                    "product_name": result.get("product_name"),
                    "domain": result.get("domain"),
                    "source": "enrichment_search",
                }

                if skeleton_id:
                    metadata["skeleton_id"] = skeleton_id

                added = self.url_frontier.add_url(
                    queue_id="enrichment",
                    url=url,
                    priority=ENRICHMENT_PRIORITY,
                    metadata=metadata,
                )

                if added:
                    queued += 1

            except Exception as e:
                logger.warning(f"Failed to queue URL {url}: {e}")

        return queued

    def get_pending_skeletons_count(self) -> int:
        """
        Get count of skeleton products awaiting enrichment.

        Returns:
            Number of skeleton products that haven't been enriched
        """
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus

        return DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            source_url="",
        ).count()

    def get_skeleton_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about skeleton products.

        Returns:
            Dictionary with skeleton statistics
        """
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus, ProductAward

        total = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
        ).count()

        awaiting_enrichment = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            source_url="",
        ).count()

        enriched = total - awaiting_enrichment

        # Get breakdown by competition using ProductAward table
        from django.db.models import Count
        by_competition = (
            ProductAward.objects.filter(
                product__status=DiscoveredProductStatus.SKELETON,
            )
            .values("competition")
            .annotate(count=Count("product", distinct=True))
            .order_by("-count")
        )

        return {
            "total_skeletons": total,
            "awaiting_enrichment": awaiting_enrichment,
            "enriched": enriched,
            "by_competition": list(by_competition),
        }

    def _assess_quality(
        self,
        product_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        product_type: str,
    ) -> QualityAssessment:
        """
        Assess product quality using QualityGateV2.

        Args:
            product_data: Extracted product data
            field_confidences: Field confidence scores
            product_type: Product type

        Returns:
            QualityAssessment with status and recommendations
        """
        return self.quality_gate.assess(
            extracted_data=product_data,
            product_type=product_type,
            field_confidences=field_confidences,
        )

    def _should_enrich(self, status: ProductStatus) -> bool:
        """
        Determine if product should be enriched.

        Args:
            status: Product quality status

        Returns:
            True if enrichment is needed
        """
        return status in [ProductStatus.SKELETON, ProductStatus.PARTIAL]


# Singleton instance
_competition_orchestrator_v2: Optional[CompetitionOrchestratorV2] = None


def get_competition_orchestrator_v2() -> CompetitionOrchestratorV2:
    """Get or create singleton CompetitionOrchestratorV2 instance."""
    global _competition_orchestrator_v2
    if _competition_orchestrator_v2 is None:
        _competition_orchestrator_v2 = CompetitionOrchestratorV2()
    return _competition_orchestrator_v2


def reset_competition_orchestrator_v2():
    """Reset singleton instance (for testing)."""
    global _competition_orchestrator_v2
    _competition_orchestrator_v2 = None

# Competition source definitions for database seeding
# Migrated from V1 for unified access
from crawler.models import SourceCategory

COMPETITION_SOURCES = [
    {
        "name": "IWSC (International Wine & Spirit Competition)",
        "slug": "iwsc",
        "base_url": "https://www.iwsc.net/results/search/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey", "port_wine"],
        "priority": 8,
        "crawl_frequency_hours": 720,
        "requires_javascript": True,
        "notes": "IWSC is a JavaScript-heavy SPA. Use /results/search/{year}?q=whisky. Requires Tier 2/3.",
    },
    {
        "name": "SFWSC (San Francisco World Spirits Competition)",
        "slug": "sfwsc",
        "base_url": "https://thetastingalliance.com/results/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey", "gin", "rum", "vodka", "tequila", "brandy"],
        "priority": 8,
        "crawl_frequency_hours": 720,
        "requires_javascript": False,
        "notes": "Prestigious US spirits competition. Double Gold is highest award.",
    },
    {
        "name": "World Whiskies Awards",
        "slug": "wwa",
        "base_url": "https://www.worldwhiskiesawards.com/winners",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey"],
        "priority": 9,
        "crawl_frequency_hours": 720,
        "requires_javascript": False,
        "notes": "Premier whisky awards. Categories include World's Best Single Malt, etc.",
    },
    {
        "name": "Decanter World Wine Awards",
        "slug": "decanter-wwa",
        "base_url": "https://awards.decanter.com/DWWA/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["port_wine"],
        "priority": 7,
        "crawl_frequency_hours": 720,
        "requires_javascript": True,
        "notes": "DWWA is a JavaScript-heavy SPA. Use /DWWA/{year}/search/wines?type=port. Requires Tier 2/3.",
    },
]


def ensure_competition_sources_exist() -> int:
    """
    Ensure competition sources exist in the database.

    Creates competition sources if they don't exist.

    Returns:
        Number of sources created
    """
    from crawler.models import CrawlerSource

    created = 0

    for source_data in COMPETITION_SOURCES:
        slug = source_data["slug"]

        if not CrawlerSource.objects.filter(slug=slug).exists():
            CrawlerSource.objects.create(
                name=source_data["name"],
                slug=slug,
                base_url=source_data["base_url"],
                category=source_data["category"],
                product_types=source_data["product_types"],
                priority=source_data["priority"],
                crawl_frequency_hours=source_data["crawl_frequency_hours"],
                notes=source_data.get("notes", ""),
                is_active=True,
                robots_txt_compliant=True,
                tos_compliant=True,
                requires_javascript=source_data.get("requires_javascript", False),
            )
            created += 1
            logger.info(f"Created competition source: {source_data['name']}")

    return created
