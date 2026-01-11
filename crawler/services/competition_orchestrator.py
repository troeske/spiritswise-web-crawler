"""
Competition Orchestrator - Orchestrates the complete award/competition discovery pipeline.

Pipeline flow:
1. Crawl competition sites (IWSC, SFWSC, WWA) -> Extract award winners
2. Create skeleton products from award data
3. Search for articles about award products (via SerpAPI)
4. Queue discovered URLs for crawling
5. Crawl those URLs to get full product details and tasting notes

Phase 4 Update: Uses ProductAward records instead of JSON awards field.
Phase 10 Update: Unified Pipeline Integration
- run_with_collectors() method for collector + AI extractor flow
- check_source_health() method for pre-crawl health checks
- YieldMonitor integration for runtime monitoring
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    CrawlJobStatus,
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    SourceCategory,
    CrawlError,
    ErrorType,
    ProductAward,
)
from crawler.discovery.competitions.parsers import (
    get_parser,
    COMPETITION_PARSERS,
    CompetitionResult,
)
from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
from crawler.discovery.competitions.enrichment_searcher import (
    EnrichmentSearcher,
    ENRICHMENT_PRIORITY,
)
from crawler.queue.url_frontier import get_url_frontier
from crawler.discovery.collectors.base_collector import get_collector
from crawler.discovery.health.selector_health import SelectorHealthChecker

logger = logging.getLogger(__name__)

# Negative keywords that indicate a product is NOT whiskey/port (wine products)
NEGATIVE_KEYWORDS = [
    'winery',
    'vineyard',
    'wine cellar',
    'chateau',
    'domaine',
    'bodega',
    'vino',
    'estate wine',
    'wine estate',
    'wine',  # General wine keyword - must be checked carefully
]


@dataclass
class CompetitionDiscoveryResult:
    """Result of competition discovery process."""

    competition: str
    year: int
    awards_found: int = 0
    skeletons_created: int = 0
    skeletons_updated: int = 0
    products_created: int = 0
    products_updated: int = 0
    products_filtered: int = 0  # Count of products filtered out by product_type
    errors: List[str] = field(default_factory=list)
    success: bool = True
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


class CompetitionOrchestrator:
    """
    Orchestrator for the complete competition/award discovery pipeline.

    Coordinates the flow from competition crawling through skeleton creation
    to enrichment search and URL queuing.

    Phase 10 Updates:
    - run_with_collectors(): Uses collectors + AI extractors instead of parsers
    - check_source_health(): Pre-crawl health check
    - Integrated yield monitoring
    """

    def __init__(
        self,
        serpapi_key: Optional[str] = None,
        results_per_search: int = 5,
    ):
        """
        Initialize competition orchestrator.

        Args:
            serpapi_key: Optional SerpAPI key for enrichment searches
            results_per_search: Number of results per enrichment search
        """
        self.skeleton_manager = SkeletonProductManager()
        self.enrichment_searcher = EnrichmentSearcher(
            api_key=serpapi_key,
            results_per_search=results_per_search,
        )
        self.url_frontier = get_url_frontier()

    # ================================================================
    # Phase 10: New Methods for Unified Pipeline
    # ================================================================

    def check_source_health(self, source: str) -> Dict[str, Any]:
        """
        Check the health of a source before crawling.

        Uses SelectorHealthChecker to verify that expected page elements
        are present and functional.

        Args:
            source: Source identifier (e.g., 'iwsc', 'dwwa')

        Returns:
            Dict with health status including:
            - is_healthy: Overall health status
            - source: Source name
            - selector_healthy: Whether selectors are working
            - details: Additional health check details
        """
        try:
            checker = SelectorHealthChecker()
            report = checker.check_source(source)

            return {
                'is_healthy': report.is_healthy,
                'source': source,
                'selector_healthy': report.is_healthy,
                'details': report.details if hasattr(report, 'details') else {},
                'checked_at': timezone.now().isoformat(),
            }
        except ImportError:
            logger.warning(f"SelectorHealthChecker not available for {source}")
            return {
                'is_healthy': True,  # Assume healthy if checker not available
                'source': source,
                'selector_healthy': True,
                'details': {'warning': 'Health checker not available'},
                'checked_at': timezone.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Health check failed for {source}: {e}")
            return {
                'is_healthy': False,
                'source': source,
                'selector_healthy': False,
                'details': {'error': str(e)},
                'checked_at': timezone.now().isoformat(),
            }

    def run_with_collectors(
        self,
        source: str,
        year: int,
        crawl_job: Optional[CrawlJob] = None,
        product_types: Optional[List[str]] = None,
        skip_health_check: bool = True,
    ) -> CompetitionDiscoveryResult:
        """
        Run competition discovery using collectors + AI extractors.

        This is the unified pipeline flow that replaces the old parser-based approach:
        1. Check source health (optional)
        2. Use collector to get detail page URLs
        3. Use AI extractor to extract data from each URL
        4. Save products via unified product saver
        5. Monitor yield and abort if too many failures

        Args:
            source: Source identifier (e.g., 'iwsc', 'dwwa')
            year: Competition year
            crawl_job: Optional CrawlJob for tracking
            product_types: Optional filter by product types
            skip_health_check: Whether to skip pre-crawl health check

        Returns:
            CompetitionDiscoveryResult with statistics
        """
        result = CompetitionDiscoveryResult(
            competition=source.upper(),
            year=year,
        )

        try:
            # Step 1: Health check (optional)
            if not skip_health_check:
                health = self.check_source_health(source)
                result.health_status = health

                if not health.get('is_healthy'):
                    result.success = False
                    result.errors.append(
                        f"Source {source} is unhealthy: {health.get('details', {})}"
                    )
                    return result

            # Step 2: Get collector (using module-level import for testability)
            try:
                collector = get_collector(source)
            except ValueError as e:
                result.success = False
                result.errors.append(str(e))
                return result

            # Step 3: Get AI extractor
            from crawler.discovery.extractors.ai_extractor import AIExtractor
            extractor = AIExtractor()

            # Step 4: Set up yield monitor
            from crawler.discovery.health.yield_monitor import YieldMonitor
            monitor = YieldMonitor(
                source=source,
                expected_min_per_page=5,
                consecutive_low_threshold=3,
            )

            # Step 5: Collect URLs
            logger.info(f"Collecting URLs from {source} for year {year}")
            detail_urls = collector.collect(year, product_types)
            result.awards_found = len(detail_urls)

            if not detail_urls:
                logger.warning(f"No URLs collected from {source} for {year}")
                return result

            # Step 6: Extract from each URL
            products_created = 0
            products_updated = 0

            for url_info in detail_urls:
                try:
                    # Build context for extractor
                    context = {
                        'source': source,
                        'year': year,
                        'medal_hint': url_info.medal_hint,
                        'score_hint': url_info.score_hint,
                        'product_type_hint': url_info.product_type_hint,
                    }

                    # Extract data
                    loop = asyncio.get_event_loop()
                    extracted = loop.run_until_complete(
                        extractor.extract(url_info.detail_url, context)
                    )

                    if not extracted or extracted.get('error'):
                        monitor.record_page(0, url_info.detail_url)
                        continue

                    # Record successful extraction
                    if not monitor.record_page(1, url_info.detail_url):
                        # Abort due to too many low-yield pages
                        result.errors.append("Aborted due to consecutive low-yield pages")
                        break

                    # Save product via unified saver
                    from crawler.services.product_saver import save_discovered_product

                    # Add award info to extracted data
                    extracted['medal'] = url_info.medal_hint
                    extracted['competition'] = source.upper()
                    extracted['year'] = year

                    save_result = save_discovered_product(
                        extracted_data=extracted,
                        source_url=url_info.detail_url,
                        product_type=url_info.product_type_hint,
                        discovery_source='competition',
                        check_existing=True,
                    )

                    if save_result.created:
                        products_created += 1
                    else:
                        products_updated += 1

                except Exception as e:
                    logger.error(f"Failed to extract from {url_info.detail_url}: {e}")
                    result.errors.append(str(e))
                    monitor.record_page(0, url_info.detail_url)

            # Step 7: Record results
            result.products_created = products_created
            result.products_updated = products_updated
            result.yield_summary = monitor.get_summary()
            result.success = True

            logger.info(
                f"Unified pipeline complete for {source} {year}: "
                f"{products_created} created, {products_updated} updated"
            )

        except Exception as e:
            result.errors.append(f"Competition discovery failed: {e}")
            result.success = False
            logger.error(f"Competition discovery failed: {e}")

        return result

    # ================================================================
    # Product Type Filtering
    # ================================================================

    def _filter_awards_by_product_type(
        self,
        award_data_list: List[Dict[str, Any]],
        product_types: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Filter awards to only include products matching the specified types.

        Uses both positive keyword matching (must contain whiskey/port keywords)
        and negative keyword filtering (must NOT contain wine-related keywords).

        Args:
            award_data_list: List of award data dictionaries from parser
            product_types: List of product types to keep (e.g., ['whiskey', 'port_wine'])

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
            'whisky': [  # Alias for whiskey
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
            'rum': [
                'rum', 'rhum', 'cachaça', 'ron',
            ],
            'gin': [
                'gin', 'genever', 'london dry',
            ],
            'vodka': [
                'vodka',
            ],
            'tequila': [
                'tequila', 'mezcal', 'sotol',
            ],
        }

        # Build set of keywords to match
        keywords_to_match = set()
        for product_type in product_types:
            keywords = type_keywords.get(product_type.lower(), [])
            keywords_to_match.update(kw.lower() for kw in keywords)

        if not keywords_to_match:
            logger.warning(f"No keywords found for product_types: {product_types}")
            return award_data_list

        filtered = []
        filtered_count = 0

        for award_data in award_data_list:
            product_name = (award_data.get('product_name') or '').lower()
            category = (award_data.get('category') or '').lower()
            combined_text = f"{product_name} {category}"

            # Check negative keywords first - filter out wine products
            has_negative_keyword = False
            matched_negative = None
            for neg_keyword in NEGATIVE_KEYWORDS:
                if neg_keyword in combined_text:
                    # Special case: 'wine' keyword should not filter out 'port wine'
                    if neg_keyword == 'wine' and 'port' in combined_text:
                        continue
                    has_negative_keyword = True
                    matched_negative = neg_keyword
                    break

            if has_negative_keyword:
                filtered_count += 1
                logger.debug(
                    f"Filtered out (negative keyword '{matched_negative}'): "
                    f"{award_data.get('product_name')} [category: {award_data.get('category')}]"
                )
                continue

            # Check if any positive keyword matches the product name or category
            matches = False
            for keyword in keywords_to_match:
                if keyword in product_name or keyword in category:
                    matches = True
                    break

            if matches:
                filtered.append(award_data)
            else:
                filtered_count += 1
                logger.debug(
                    f"Filtered out (no positive match for {product_types}): "
                    f"{award_data.get('product_name')} [category: {award_data.get('category')}]"
                )

        # Log summary of filtering
        if filtered_count > 0:
            logger.info(
                f"Product type filter: {len(award_data_list)} -> {len(filtered)} "
                f"(filtered {filtered_count}, types: {product_types})"
            )
        else:
            logger.info(f"Product type filter: {len(award_data_list)} -> {len(filtered)} (types: {product_types})")

        return filtered

    # ================================================================
    # Original Methods (maintained for backward compatibility)
    # ================================================================

    async def run_competition_discovery(
        self,
        competition_url: str,
        crawl_job: CrawlJob,
        html_content: str,
        competition_key: str,
        year: int,
        product_types: list = None,
        max_results: int = 10,
    ) -> CompetitionDiscoveryResult:
        """
        Run competition discovery: parse results and create skeleton products.

        Args:
            competition_url: URL of the competition results page
            crawl_job: CrawlJob tracking this crawl
            html_content: Raw HTML content of the competition results page
            competition_key: Key for the competition parser (e.g., "iwsc")
            year: Competition year
            product_types: List of product types to filter for (e.g., ['whiskey', 'port_wine'])
            max_results: Maximum number of products to create

        Returns:
            CompetitionDiscoveryResult with statistics
        """
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

    async def process_skeletons_for_enrichment(
        self,
        limit: int = 50,
        crawl_job: Optional[CrawlJob] = None,
    ) -> EnrichmentResult:
        """
        Process skeleton products for enrichment via SerpAPI searches.

        Finds unenriched skeletons and runs triple search for each.

        Args:
            limit: Maximum number of skeletons to process
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            EnrichmentResult with statistics
        """
        result = EnrichmentResult()

        try:
            # Get unenriched skeleton products (wrap sync ORM call)
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
                    # Get product name from individual column
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

                    # Mark skeleton as having been searched by adding to discovery_sources
                    sources = skeleton.discovery_sources or []
                    if 'serpapi_enrichment' not in sources:
                        sources.append('serpapi_enrichment')
                        skeleton.discovery_sources = sources
                        # Wrap sync ORM call for async context
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

    async def queue_enrichment_urls(
        self,
        enrichment_results: List[Dict[str, Any]],
    ) -> int:
        """
        Queue URLs from enrichment search results.

        Args:
            enrichment_results: List of enrichment search result dicts

        Returns:
            Number of URLs successfully queued
        """
        return await self._queue_enrichment_urls(enrichment_results)

    async def _queue_enrichment_urls(
        self,
        enrichment_results: List[Dict[str, Any]],
        skeleton_id: Optional[str] = None,
    ) -> int:
        """
        Internal method to queue enrichment URLs.

        Args:
            enrichment_results: List of enrichment search result dicts
            skeleton_id: Optional skeleton product ID for metadata

        Returns:
            Number of URLs successfully queued
        """
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

                # Queue with high priority (enrichment URLs get priority 10)
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

    def get_competition_sources(self) -> List[CrawlerSource]:
        """
        Get all active competition sources from the database.

        Returns:
            List of CrawlerSource instances with category='competition'
        """
        return list(
            CrawlerSource.objects.filter(
                category=SourceCategory.COMPETITION,
                is_active=True,
            ).order_by("-priority", "name")
        )

    def get_pending_skeletons_count(self) -> int:
        """
        Get count of skeleton products awaiting enrichment.

        Returns:
            Number of skeleton products that haven't been enriched
        """
        # Look for skeletons without enrichment (source_url empty = not enriched)
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


# Competition source definitions for database seeding
# IMPORTANT: IWSC and DWWA are JavaScript-heavy SPAs that require Tier 2/3 rendering
COMPETITION_SOURCES = [
    {
        "name": "IWSC (International Wine & Spirit Competition)",
        "slug": "iwsc",
        # IWSC URL structure: /results/search/{year} with optional ?q={keyword}
        # JavaScript-heavy SPA - requires Tier 2 (Playwright) or Tier 3 (ScrapingBee)
        # Static HTML contains only page shell, not product data
        "base_url": "https://www.iwsc.net/results/search/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey", "port_wine"],
        "priority": 8,
        "crawl_frequency_hours": 720,  # Monthly
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
        "crawl_frequency_hours": 720,  # Monthly
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
        "crawl_frequency_hours": 720,  # Monthly
        "requires_javascript": False,
        "notes": "Premier whisky awards. Categories include World's Best Single Malt, etc.",
    },
    {
        "name": "Decanter World Wine Awards",
        "slug": "decanter-wwa",
        # DWWA URL structure: /DWWA/{year}/search/wines?type=port&medal=gold
        # JavaScript-heavy SPA - requires Tier 2 (Playwright) or Tier 3 (ScrapingBee)
        "base_url": "https://awards.decanter.com/DWWA/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["port_wine"],
        "priority": 7,
        "crawl_frequency_hours": 720,  # Monthly
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
