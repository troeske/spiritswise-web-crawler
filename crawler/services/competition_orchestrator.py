"""
Competition Orchestrator - Orchestrates the complete award/competition discovery pipeline.

Pipeline flow:
1. Crawl competition sites (IWSC, SFWSC, WWA) -> Extract award winners
2. Create skeleton products from award data
3. Search for articles about award products (via SerpAPI)
4. Queue discovered URLs for crawling
5. Crawl those URLs to get full product details and tasting notes

Phase 4 Update: Uses ProductAward records instead of JSON awards field.
"""

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

logger = logging.getLogger(__name__)


@dataclass
class CompetitionDiscoveryResult:
    """Result of competition discovery process."""

    competition: str
    year: int
    awards_found: int = 0
    skeletons_created: int = 0
    skeletons_updated: int = 0
    errors: List[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "competition": self.competition,
            "year": self.year,
            "awards_found": self.awards_found,
            "skeletons_created": self.skeletons_created,
            "skeletons_updated": self.skeletons_updated,
            "errors": self.errors,
            "success": self.success,
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

    async def run_competition_discovery(
        self,
        competition_url: str,
        crawl_job: CrawlJob,
        html_content: str,
        competition_key: str,
        year: int,
    ) -> CompetitionDiscoveryResult:
        """
        Run competition discovery: parse results and create skeleton products.

        Args:
            competition_url: URL of the competition results page
            crawl_job: CrawlJob tracking this crawl
            html_content: Raw HTML content of the competition results page
            competition_key: Key for the competition parser (e.g., "iwsc")
            year: Competition year

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
            # Get unenriched skeleton products
            skeletons = self.skeleton_manager.get_unenriched_skeletons(limit=limit)

            if not skeletons:
                logger.info("No unenriched skeleton products found")
                return result

            logger.info(f"Processing {len(skeletons)} skeleton products for enrichment")

            for skeleton in skeletons:
                try:
                    # Get product name from individual column or extracted_data
                    product_name = skeleton.name or skeleton.extracted_data.get("name", "")
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
                    # (Store search metadata in enriched_data)
                    skeleton.enriched_data = {
                        "enrichment_searched_at": timezone.now().isoformat(),
                        "enrichment_urls_found": len(search_results),
                        "enrichment_urls_queued": queued,
                    }
                    skeleton.save(update_fields=["enriched_data"])

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
            Number of skeleton products with empty enriched_data
        """
        return DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            enriched_data={},
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
            enriched_data={},
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
COMPETITION_SOURCES = [
    {
        "name": "IWSC (International Wine & Spirit Competition)",
        "slug": "iwsc",
        "base_url": "https://iwsc.net/results/search/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey", "gin", "rum", "vodka", "brandy"],
        "priority": 8,
        "crawl_frequency_hours": 720,  # Monthly
        "notes": "Major international spirits competition. Parse year-specific results pages.",
    },
    {
        "name": "SFWSC (San Francisco World Spirits Competition)",
        "slug": "sfwsc",
        "base_url": "https://thetastingalliance.com/results/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["whiskey", "gin", "rum", "vodka", "tequila", "brandy"],
        "priority": 8,
        "crawl_frequency_hours": 720,  # Monthly
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
        "notes": "Premier whisky awards. Categories include World's Best Single Malt, etc.",
    },
    {
        "name": "Decanter World Wine Awards",
        "slug": "decanter-wwa",
        "base_url": "https://awards.decanter.com/",
        "category": SourceCategory.COMPETITION,
        "product_types": ["port_wine"],
        "priority": 7,
        "crawl_frequency_hours": 720,  # Monthly
        "notes": "Major wine competition. Filter for Port wine category.",
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
            )
            created += 1
            logger.info(f"Created competition source: {source_data['name']}")

    return created
