"""
Celery tasks for the web crawler.

Task Group 6 Implementation:
- check_due_sources: Periodic task to find and process due sources
- check_due_keywords: Periodic task for keyword-based searches
- crawl_source: Worker task to crawl a source
- trigger_manual_crawl: Manual crawl trigger task

Task Group 7 Integration:
- Uses ContentProcessor for AI Enhancement Service integration
- Tracks costs via CrawlCost model

Task Group 31 Implementation:
- archive_to_wayback: Archive CrawledSource to Wayback Machine
- process_pending_wayback: Batch process pending archives

V2 Migration Update:
- Uses CompetitionOrchestratorV2 for competition crawling (V2 quality assessment)
- Uses get_ai_client_v2 for AI Enhancement (V2 extraction schema with tasting notes)
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlerKeyword,
    CrawlJob,
    CrawlJobStatus,
    DiscoveredProduct,
    DiscoveredProductStatus,
    ProductType,
    CrawlError,
    ErrorType,
    SourceCategory,
    APICrawlJob,
)

# V2 Components for competition orchestration
from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

logger = logging.getLogger(__name__)

# Whiskey-related keywords for filtering competition results
WHISKEY_KEYWORDS = ['whisky', 'whiskey', 'bourbon', 'scotch', 'malt', 'rye']


@shared_task(name="crawler.tasks.check_due_sources")
def check_due_sources() -> Dict[str, Any]:
    """
    Periodic task to check for sources due for crawling.

    Runs every 5 minutes via Celery Beat.
    Queries CrawlerSource where is_active=True AND next_crawl_at <= now().
    Creates CrawlJob for each due source and dispatches to crawl queue.

    Returns:
        Dict with checked status and count of sources found
    """
    logger.info("Checking for due sources...")

    now = timezone.now()
    sources_found = 0
    jobs_created = []

    # Query for due sources
    due_sources = CrawlerSource.objects.filter(
        is_active=True,
    ).filter(
        # next_crawl_at is null (never crawled) or <= now
        models_next_crawl_at_due(now)
    )

    for source in due_sources:
        try:
            # Create CrawlJob for this source
            with transaction.atomic():
                job = CrawlJob.objects.create(source=source)
                jobs_created.append(str(job.id))
                sources_found += 1

            # Dispatch to crawl queue
            crawl_source.apply_async(
                args=[str(source.id), str(job.id)],
                queue="crawl",
            )

            logger.info(f"Dispatched crawl job {job.id} for source {source.name}")

        except Exception as e:
            logger.error(f"Failed to create job for source {source.name}: {e}")
            continue

    logger.info(f"Due source check complete: {sources_found} sources dispatched")

    return {
        "checked": True,
        "sources_found": sources_found,
        "jobs_created": jobs_created,
        "timestamp": now.isoformat(),
    }


def models_next_crawl_at_due(now):
    """
    Build query filter for sources that are due for crawling.

    Returns sources where:
    - next_crawl_at is NULL (never crawled), OR
    - next_crawl_at <= now
    """
    from django.db.models import Q

    return Q(next_crawl_at__isnull=True) | Q(next_crawl_at__lte=now)


@shared_task(name="crawler.tasks.check_due_keywords")
def check_due_keywords() -> Dict[str, Any]:
    """
    Periodic task to check for keywords due for searching.

    Runs every 15 minutes via Celery Beat.
    Queries CrawlerKeyword where is_active=True AND next_search_at <= now().
    Executes searches and queues discovered URLs.

    Returns:
        Dict with checked status and count of keywords found
    """
    logger.info("Checking for due keywords...")

    now = timezone.now()
    keywords_found = 0
    searches_dispatched = []

    # Query for due keywords
    from django.db.models import Q

    due_keywords = CrawlerKeyword.objects.filter(
        is_active=True,
    ).filter(
        Q(next_search_at__isnull=True) | Q(next_search_at__lte=now)
    )

    for keyword in due_keywords:
        try:
            # Dispatch keyword search task
            keyword_search.apply_async(
                args=[str(keyword.id)],
                queue="search",
            )

            searches_dispatched.append({
                "keyword_id": str(keyword.id),
                "keyword": keyword.keyword,
            })
            keywords_found += 1

            logger.info(f"Dispatched search for keyword: {keyword.keyword}")

        except Exception as e:
            logger.error(f"Failed to dispatch search for keyword {keyword.keyword}: {e}")
            continue

    logger.info(f"Due keyword check complete: {keywords_found} keywords dispatched")

    return {
        "checked": True,
        "keywords_found": keywords_found,
        "searches_dispatched": searches_dispatched,
        "timestamp": now.isoformat(),
    }


@shared_task(name="crawler.tasks.crawl_source", bind=True)
def crawl_source(self, source_id: str, job_id: str) -> Dict[str, Any]:
    """
    Crawl worker task - fetches URLs from source via Smart Router.

    Uses ContentProcessor for standard sources, CompetitionOrchestratorV2 for
    competition sources.

    Args:
        source_id: UUID of the CrawlerSource to process
        job_id: UUID of the CrawlJob tracking this crawl

    Returns:
        Dict with crawl results and metrics
    """
    logger.info(f"Starting crawl for source {source_id}, job {job_id}")

    # Import here to avoid circular imports
    import asyncio
    from crawler.fetchers.smart_router import SmartRouter
    from crawler.queue.url_frontier import get_url_frontier

    # Load source and job
    try:
        source = CrawlerSource.objects.get(id=source_id)
        job = CrawlJob.objects.get(id=job_id)
    except (CrawlerSource.DoesNotExist, CrawlJob.DoesNotExist) as e:
        logger.error(f"Source or job not found: {e}")
        return {"error": str(e), "status": "failed"}

    # Mark job as running
    job.start()

    # Check if this is a competition source - use different processing
    if source.category == SourceCategory.COMPETITION:
        return _crawl_competition_source(source, job)

    metrics = {
        "pages_crawled": 0,
        "products_found": 0,
        "products_new": 0,
        "products_updated": 0,
        "errors_count": 0,
    }

    try:
        # Get URL frontier
        frontier = get_url_frontier()

        # Initialize with base URL if queue is empty
        if frontier.is_empty(source.slug):
            frontier.add_url(
                queue_id=source.slug,
                url=source.base_url,
                priority=source.priority,
                source_id=str(source.id),
            )

        # Process URLs from frontier
        router = SmartRouter()

        # Run async fetch in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            metrics = loop.run_until_complete(
                _process_source_urls(source, job, router, frontier, metrics)
            )
        finally:
            # Cleanup router resources on the SAME event loop
            loop.run_until_complete(router.close())
            loop.close()

        # Update job metrics
        job.pages_crawled = metrics["pages_crawled"]
        job.products_found = metrics["products_found"]
        job.products_new = metrics["products_new"]
        job.products_updated = metrics["products_updated"]
        job.errors_count = metrics["errors_count"]
        job.complete(success=True)

        logger.info(
            f"Crawl completed for {source.name}: "
            f"{metrics['pages_crawled']} pages, {metrics['products_found']} products"
        )

    except Exception as e:
        logger.error(f"Crawl failed for {source.name}: {e}")
        logger.error(traceback.format_exc())

        # Log error
        CrawlError.objects.create(
            source=source,
            url=source.base_url,
            error_type=ErrorType.UNKNOWN,
            message=str(e),
            stack_trace=traceback.format_exc(),
        )

        job.errors_count = metrics["errors_count"] + 1
        job.complete(success=False, error_message=str(e))
        metrics["errors_count"] += 1

    return {
        "source_id": source_id,
        "job_id": job_id,
        "status": job.status,
        "metrics": metrics,
    }


def _crawl_competition_source(source: CrawlerSource, job: CrawlJob) -> Dict[str, Any]:
    """
    Process a competition source using CompetitionOrchestratorV2.

    For IWSC and similar competitions, iterates through whiskey-related keywords
    to filter results. Implements deduplication using product name + year as key.

    Args:
        source: Competition CrawlerSource to process
        job: CrawlJob tracking this crawl

    Returns:
        Dict with crawl results and metrics
    """
    import asyncio
    import re
    from urllib.parse import urlparse, urlencode, urlunparse
    from crawler.fetchers.smart_router import SmartRouter

    logger.info(f"Processing competition source: {source.name}")

    metrics = {
        "pages_crawled": 0,
        "products_found": 0,
        "products_new": 0,
        "products_updated": 0,
        "errors_count": 0,
        "keywords_searched": 0,
        "duplicates_skipped": 0,
    }

    # Track seen products for deduplication (key: product_name + year)
    seen_products = set()

    try:
        # Determine competition year from URL or use current year
        year = datetime.now().year

        # Check if URL contains year pattern
        year_match = re.search(r'/(\d{4})(?:/|$)', source.base_url)
        if year_match:
            year = int(year_match.group(1))

        # Determine competition key from slug
        # For "international-wine-spirit-competition-iwsc", extract "iwsc" (last segment)
        # This matches the parser registration key
        competition_key = source.slug.split('-')[-1] if '-' in source.slug else source.slug

        # Initialize router and V2 orchestrator
        router = SmartRouter()
        orchestrator = CompetitionOrchestratorV2()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Check if this is an IWSC-style source that supports keyword filtering
            is_iwsc = 'iwsc' in source.base_url.lower() or 'iwsc' in source.slug.lower()

            if is_iwsc:
                # Process each keyword
                for keyword in WHISKEY_KEYWORDS:
                    logger.info(f"Searching IWSC for keyword: {keyword}")
                    metrics["keywords_searched"] += 1

                    # Build keyword URL
                    # URL pattern: https://www.iwsc.net/results/search/{year}/{page}?type=3&q={keyword}
                    parsed = urlparse(source.base_url)

                    # Start with page 1
                    page = 1
                    has_more_pages = True

                    while has_more_pages:
                        # Build URL with keyword and page
                        # IWSC URL pattern: /results/search/{year}/{page}?type=3&q={keyword}
                        # Keep the year in the path, only append page number
                        base_path = parsed.path.rstrip('/')

                        # For IWSC: /results/search/2025 -> /results/search/2025/1
                        # Don't remove the year! Only add page number
                        page_path = f"{base_path}/{page}"

                        # Build query string with type=3 and q=keyword
                        query_params = {'type': '3', 'q': keyword}
                        query_string = urlencode(query_params)

                        keyword_url = urlunparse((
                            parsed.scheme,
                            parsed.netloc,
                            page_path,
                            '',
                            query_string,
                            ''
                        ))

                        logger.info(f"Fetching: {keyword_url}")

                        # Fetch the competition page
                        fetch_result = loop.run_until_complete(
                            router.fetch(keyword_url, source=source, crawl_job=job)
                        )

                        if not fetch_result.success:
                            logger.warning(f"Failed to fetch {keyword_url}: {fetch_result.error}")
                            metrics["errors_count"] += 1
                            break

                        metrics["pages_crawled"] += 1

                        # Run competition discovery with deduplication callback
                        result = loop.run_until_complete(
                            orchestrator.run_competition_discovery(
                                competition_url=keyword_url,
                                crawl_job=job,
                                html_content=fetch_result.content,
                                competition_key=competition_key,
                                year=year,
                            )
                        )

                        # Process results with deduplication
                        new_products = 0

                        # Get awards data from result if available
                        if hasattr(result, 'awards_data') and result.awards_data:
                            for award in result.awards_data:
                                # Create deduplication key
                                product_name = award.get('product_name', '').strip().lower()
                                dedup_key = f"{product_name}|{year}"

                                if dedup_key not in seen_products:
                                    seen_products.add(dedup_key)
                                    new_products += 1
                                else:
                                    metrics["duplicates_skipped"] += 1
                        else:
                            # Fallback: count all as new if no detailed data
                            new_products = result.awards_found

                        metrics["products_found"] += new_products
                        metrics["products_new"] += result.skeletons_created
                        metrics["products_updated"] += result.skeletons_updated
                        metrics["errors_count"] += len(result.errors) if result.errors else 0

                        # Check if there are more pages
                        # If no results found or very few, stop pagination
                        if result.awards_found == 0 or page >= 50:  # Safety limit
                            has_more_pages = False
                        else:
                            page += 1

                        logger.info(
                            f"Keyword '{keyword}' page {page-1}: {result.awards_found} awards found, "
                            f"{new_products} new (after dedup)"
                        )
            else:
                # Non-IWSC competition: use original single-URL logic
                fetch_result = loop.run_until_complete(
                    router.fetch(source.base_url, source=source, crawl_job=job)
                )

                if not fetch_result.success:
                    raise Exception(f"Failed to fetch competition page: {fetch_result.error}")

                metrics["pages_crawled"] = 1

                # Run competition discovery
                result = loop.run_until_complete(
                    orchestrator.run_competition_discovery(
                        competition_url=source.base_url,
                        crawl_job=job,
                        html_content=fetch_result.content,
                        competition_key=competition_key,
                        year=year,
                    )
                )

                metrics["products_found"] = result.awards_found
                metrics["products_new"] = result.skeletons_created
                metrics["products_updated"] = result.skeletons_updated
                metrics["errors_count"] = len(result.errors) if result.errors else 0

            logger.info(
                f"Competition discovery complete for {source.name}: "
                f"{metrics['products_found']} products, {metrics['keywords_searched']} keywords searched, "
                f"{metrics['duplicates_skipped']} duplicates skipped"
            )

        finally:
            loop.run_until_complete(router.close())
            loop.close()

        # Update job metrics
        job.pages_crawled = metrics["pages_crawled"]
        job.products_found = metrics["products_found"]
        job.products_new = metrics["products_new"]
        job.products_updated = metrics["products_updated"]
        job.errors_count = metrics["errors_count"]
        job.complete(success=True)

    except Exception as e:
        logger.error(f"Competition crawl failed for {source.name}: {e}")
        logger.error(traceback.format_exc())

        CrawlError.objects.create(
            source=source,
            url=source.base_url,
            error_type=ErrorType.UNKNOWN,
            message=str(e),
            stack_trace=traceback.format_exc(),
        )

        job.errors_count = 1
        job.complete(success=False, error_message=str(e))
        metrics["errors_count"] = 1

    return {
        "source_id": str(source.id),
        "job_id": str(job.id),
        "status": job.status,
        "metrics": metrics,
        "competition": True,
        "keywords_searched": metrics.get("keywords_searched", 0),
        "duplicates_skipped": metrics.get("duplicates_skipped", 0),
    }


async def _process_source_urls(
    source: CrawlerSource,
    job: CrawlJob,
    router,
    frontier,
    metrics: Dict[str, int],
    max_pages: int = 100,
) -> Dict[str, int]:
    """
    Process URLs from the frontier for a source.

    Uses ContentProcessor for AI Enhancement Service integration.

    Args:
        source: CrawlerSource to process
        job: CrawlJob tracking this crawl
        router: SmartRouter instance
        frontier: URLFrontier instance
        metrics: Metrics dictionary to update
        max_pages: Maximum pages to process per crawl

    Returns:
        Updated metrics dictionary
    """
    # Import ContentProcessor for AI Enhancement integration
    from crawler.services.content_processor import ContentProcessor

    pages_processed = 0
    content_processor = ContentProcessor()

    while pages_processed < max_pages:
        # Get next URL from frontier
        url_entry = frontier.get_next_url(source.slug)

        if url_entry is None:
            # Queue is empty
            break

        url = url_entry["url"]
        logger.debug(f"Processing URL: {url}")

        try:
            # Fetch the URL via Smart Router
            result = await router.fetch(url, source=source, crawl_job=job)

            if result.success:
                metrics["pages_crawled"] += 1
                pages_processed += 1

                # Process content through AI Enhancement pipeline
                processing_result = await content_processor.process(
                    url=url,
                    raw_content=result.content,
                    source=source,
                    crawl_job=job,
                )

                if processing_result.success:
                    metrics["products_found"] += 1
                    if processing_result.is_new:
                        metrics["products_new"] += 1
                    else:
                        metrics["products_updated"] += 1
                else:
                    logger.warning(
                        f"AI processing failed for {url}: {processing_result.error}"
                    )

            else:
                metrics["errors_count"] += 1
                logger.warning(f"Failed to fetch {url}: {result.error}")

        except Exception as e:
            metrics["errors_count"] += 1
            logger.error(f"Error processing {url}: {e}")

            # Log error to database
            CrawlError.objects.create(
                source=source,
                url=url,
                error_type=ErrorType.UNKNOWN,
                message=str(e),
                stack_trace=traceback.format_exc(),
            )

    return metrics


@shared_task(name="crawler.tasks.keyword_search", bind=True)
def keyword_search(self, keyword_id: str) -> Dict[str, Any]:
    """
    Execute a keyword-based SerpAPI search.

    Args:
        keyword_id: UUID of the CrawlerKeyword to search

    Returns:
        Dict with search results
    """
    logger.info(f"Executing keyword search for {keyword_id}")

    import asyncio
    from crawler.discovery.serpapi_client import SerpAPIClient
    from crawler.queue.url_frontier import get_url_frontier

    try:
        keyword = CrawlerKeyword.objects.get(id=keyword_id)
    except CrawlerKeyword.DoesNotExist:
        logger.error(f"Keyword {keyword_id} not found")
        return {"error": "Keyword not found", "status": "failed"}

    urls_found = 0
    urls_queued = 0

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            client = SerpAPIClient()
            results = loop.run_until_complete(
                client.search(query=keyword.keyword, num_results=10)
            )

            frontier = get_url_frontier()

            for result in results:
                urls_found += 1

                # Add to frontier with keyword priority
                added = frontier.add_url(
                    queue_id="keyword-discovery",
                    url=result.url,
                    priority=keyword.priority,
                    metadata={
                        "keyword": keyword.keyword,
                        "search_context": keyword.search_context,
                    },
                )

                if added:
                    urls_queued += 1

        finally:
            loop.close()

        # Update keyword tracking
        keyword.total_results_found += urls_found
        keyword.update_next_search_time()

        logger.info(
            f"Keyword search complete for '{keyword.keyword}': "
            f"{urls_found} found, {urls_queued} queued"
        )

    except Exception as e:
        logger.error(f"Keyword search failed for {keyword.keyword}: {e}")
        return {
            "keyword_id": keyword_id,
            "status": "failed",
            "error": str(e),
        }

    return {
        "keyword_id": keyword_id,
        "keyword": keyword.keyword,
        "status": "completed",
        "urls_found": urls_found,
        "urls_queued": urls_queued,
    }


@shared_task(name="crawler.tasks.trigger_manual_crawl", bind=True)
def trigger_manual_crawl(self, source_id: str) -> Dict[str, Any]:
    """
    Trigger an immediate crawl for a specific source.

    Args:
        source_id: UUID of the CrawlerSource to crawl

    Returns:
        Dict with job_id for status tracking
    """
    logger.info(f"Manual crawl triggered for source {source_id}")

    try:
        source = CrawlerSource.objects.get(id=source_id)
    except CrawlerSource.DoesNotExist:
        logger.error(f"Source {source_id} not found")
        return {"error": "Source not found", "status": "failed"}

    # Create CrawlJob
    job = CrawlJob.objects.create(source=source)

    # Dispatch to crawl queue immediately
    crawl_source.apply_async(
        args=[str(source.id), str(job.id)],
        queue="crawl",
    )

    logger.info(f"Manual crawl dispatched: job {job.id} for {source.name}")

    return {
        "source_id": source_id,
        "source_name": source.name,
        "job_id": str(job.id),
        "status": "dispatched",
    }


# Competition enrichment tasks
@shared_task(name="crawler.tasks.enrich_skeletons", bind=True)
def enrich_skeletons(self, limit: int = 50) -> Dict[str, Any]:
    """
    Periodic task to run SerpAPI searches for skeleton products.

    Finds skeleton products that haven't been enriched and searches for
    articles, reviews, and official sites to gather more information.

    Args:
        limit: Maximum number of skeletons to process in this run

    Returns:
        Dict with enrichment results
    """
    logger.info(f"Starting skeleton enrichment, limit={limit}")

    import asyncio

    try:
        orchestrator = CompetitionOrchestratorV2()

        # Check pending count first
        pending_count = orchestrator.get_pending_skeletons_count()

        if pending_count == 0:
            logger.info("No skeletons need enrichment")
            return {
                "status": "completed",
                "skeletons_processed": 0,
                "urls_discovered": 0,
                "urls_queued": 0,
                "message": "No skeletons pending enrichment",
            }

        # Run async enrichment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                orchestrator.process_skeletons_for_enrichment(limit=limit)
            )
        finally:
            loop.close()

        logger.info(
            f"Skeleton enrichment complete: {result.skeletons_processed} processed, "
            f"{result.urls_discovered} URLs discovered"
        )

        return {
            "status": "completed",
            "skeletons_processed": result.skeletons_processed,
            "urls_discovered": result.urls_discovered,
            "urls_queued": result.urls_queued,
            "errors": len(result.errors) if result.errors else 0,
        }

    except Exception as e:
        logger.error(f"Skeleton enrichment failed: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "failed",
            "error": str(e),
            "skeletons_processed": 0,
        }


@shared_task(name="crawler.tasks.process_enrichment_queue", bind=True)
def process_enrichment_queue(self, max_urls: int = 100) -> Dict[str, Any]:
    """
    Periodic task to process URLs from the enrichment queue.

    Fetches and processes URLs discovered during skeleton enrichment
    to extract detailed product information, tasting notes, etc.

    Args:
        max_urls: Maximum URLs to process in this run

    Returns:
        Dict with processing results
    """
    logger.info(f"Processing enrichment queue, max_urls={max_urls}")

    import asyncio
    from crawler.fetchers.smart_router import SmartRouter
    from crawler.queue.url_frontier import get_url_frontier
    from crawler.services.content_processor import ContentProcessor

    frontier = get_url_frontier()
    queue_size = frontier.get_queue_size("enrichment")

    if queue_size == 0:
        logger.info("Enrichment queue is empty")
        return {
            "status": "completed",
            "urls_processed": 0,
            "skeletons_enriched": 0,
            "message": "Enrichment queue empty",
        }

    urls_processed = 0
    skeletons_enriched = 0
    errors = 0

    try:
        router = SmartRouter()
        processor = ContentProcessor()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while urls_processed < max_urls:
                # Get next URL from enrichment queue
                url_entry = frontier.get_next_url("enrichment")

                if url_entry is None:
                    break

                url = url_entry.get("url")
                metadata = url_entry.get("metadata", {})
                skeleton_id = metadata.get("skeleton_id")

                try:
                    # Fetch the URL
                    fetch_result = loop.run_until_complete(
                        router.fetch(url)
                    )

                    if fetch_result.success:
                        urls_processed += 1

                        # Process content to extract enrichment data
                        process_result = loop.run_until_complete(
                            processor.process(
                                url=url,
                                raw_content=fetch_result.content,
                            )
                        )

                        if process_result.success and skeleton_id:
                            # Update skeleton with enriched data to individual columns
                            try:
                                skeleton = DiscoveredProduct.objects.get(id=skeleton_id)
                                if process_result.enriched_data:
                                    # Map enriched data to individual columns
                                    enriched = process_result.enriched_data
                                    update_fields = ['status']
                                    if enriched.get('nose_description') and not skeleton.nose_description:
                                        skeleton.nose_description = enriched['nose_description']
                                        update_fields.append('nose_description')
                                    if enriched.get('palate_description') and not skeleton.palate_description:
                                        skeleton.palate_description = enriched['palate_description']
                                        update_fields.append('palate_description')
                                    if enriched.get('finish_description') and not skeleton.finish_description:
                                        skeleton.finish_description = enriched['finish_description']
                                        update_fields.append('finish_description')
                                    skeleton.status = DiscoveredProductStatus.ENRICHED
                                    skeleton.save(update_fields=update_fields)
                                    skeletons_enriched += 1
                            except DiscoveredProduct.DoesNotExist:
                                logger.warning(f"Skeleton {skeleton_id} not found for URL {url}")

                    else:
                        errors += 1
                        logger.warning(f"Failed to fetch enrichment URL {url}: {fetch_result.error}")

                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing enrichment URL {url}: {e}")

        finally:
            loop.run_until_complete(router.close())
            loop.close()

        logger.info(
            f"Enrichment queue processing complete: {urls_processed} URLs, "
            f"{skeletons_enriched} skeletons enriched"
        )

        return {
            "status": "completed",
            "urls_processed": urls_processed,
            "skeletons_enriched": skeletons_enriched,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Enrichment queue processing failed: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "failed",
            "error": str(e),
            "urls_processed": urls_processed,
        }


# Legacy placeholder tasks - kept for backward compatibility
@shared_task(name="crawler.tasks.process_source", bind=True)
def process_source(self, source_id: str) -> Dict[str, Any]:
    """
    Process a single crawler source.

    This is a legacy task name. New code should use crawl_source.

    Args:
        source_id: ID of the CrawlerSource to process
    """
    logger.warning("process_source is deprecated, use crawl_source instead")

    try:
        source = CrawlerSource.objects.get(id=source_id)
        job = CrawlJob.objects.create(source=source)

        # Delegate to new task
        return crawl_source(str(source.id), str(job.id))

    except CrawlerSource.DoesNotExist:
        return {"error": "Source not found", "status": "failed"}


@shared_task(name="crawler.tasks.debug_task", bind=True)
def debug_task(self) -> Dict[str, Any]:
    """Debug task for testing Celery configuration."""
    logger.info(f"Debug task executed. Request: {self.request!r}")
    return {"status": "success", "message": "Debug task completed"}


# ============================================================
# Task Group 31: Wayback Machine Integration Tasks
# ============================================================


@shared_task(
    name="crawler.tasks.archive_to_wayback",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute delay, will use exponential backoff
)
def archive_to_wayback(self, crawled_source_id: str) -> Dict[str, Any]:
    """
    Archive a CrawledSource URL to the Wayback Machine.

    Task Group 31: Async Celery task for Wayback Machine archiving.
    Triggers after successful crawl. Implements exponential backoff retry
    with maximum 3 retries before marking as failed.

    Args:
        crawled_source_id: UUID of the CrawledSource to archive

    Returns:
        Dict with archive result status
    """
    from crawler.models import CrawledSource, WaybackStatusChoices
    from crawler.services.wayback import save_to_wayback, mark_wayback_failed

    logger.info(f"Archiving CrawledSource {crawled_source_id} to Wayback Machine")

    try:
        crawled_source = CrawledSource.objects.get(id=crawled_source_id)
    except CrawledSource.DoesNotExist:
        logger.error(f"CrawledSource {crawled_source_id} not found")
        return {
            "crawled_source_id": crawled_source_id,
            "status": "failed",
            "error": "CrawledSource not found",
        }

    # Skip if already saved or marked as not applicable
    if crawled_source.wayback_status in [
        WaybackStatusChoices.SAVED,
        WaybackStatusChoices.NOT_APPLICABLE,
    ]:
        logger.info(
            f"Skipping Wayback archive for {crawled_source.url}: "
            f"status is '{crawled_source.wayback_status}'"
        )
        return {
            "crawled_source_id": crawled_source_id,
            "status": "skipped",
            "wayback_status": crawled_source.wayback_status,
        }

    # Attempt to save to Wayback Machine
    result = save_to_wayback(crawled_source)

    if result["success"]:
        logger.info(
            f"Successfully archived {crawled_source.url} to Wayback Machine: "
            f"{result['wayback_url']}"
        )
        return {
            "crawled_source_id": crawled_source_id,
            "url": crawled_source.url,
            "status": "success",
            "wayback_url": result["wayback_url"],
        }
    else:
        # Retry with exponential backoff
        retry_count = self.request.retries
        logger.warning(
            f"Wayback archive failed for {crawled_source.url}, "
            f"retry {retry_count + 1}/{self.max_retries}: {result.get('error')}"
        )

        if retry_count < self.max_retries:
            # Exponential backoff: 60s, 120s, 240s
            countdown = self.default_retry_delay * (2 ** retry_count)
            raise self.retry(countdown=countdown)
        else:
            # Max retries exceeded - mark as failed
            mark_wayback_failed(crawled_source)
            logger.error(
                f"Wayback archive failed permanently for {crawled_source.url} "
                f"after {self.max_retries} retries"
            )
            return {
                "crawled_source_id": crawled_source_id,
                "url": crawled_source.url,
                "status": "failed",
                "error": result.get("error"),
                "retries_exhausted": True,
            }


@shared_task(name="crawler.tasks.process_pending_wayback")
def process_pending_wayback(limit: int = 50) -> Dict[str, Any]:
    """
    Process pending Wayback Machine archives in batch.

    Task Group 31: Periodic task to find CrawledSource records with
    wayback_status='pending' and extraction_status='processed', then
    trigger archive_to_wayback for each.

    Args:
        limit: Maximum number of sources to process in this batch

    Returns:
        Dict with batch processing results
    """
    from crawler.services.wayback import get_pending_wayback_sources

    logger.info(f"Processing pending Wayback archives, limit={limit}")

    pending_sources = get_pending_wayback_sources(limit=limit)
    dispatched = 0

    for source in pending_sources:
        try:
            # Dispatch archive task
            archive_to_wayback.apply_async(
                args=[str(source.id)],
                queue="wayback",
            )
            dispatched += 1
            logger.debug(f"Dispatched Wayback archive for: {source.url}")

        except Exception as e:
            logger.error(f"Failed to dispatch Wayback archive for {source.url}: {e}")

    logger.info(f"Wayback batch processing: {dispatched}/{len(pending_sources)} dispatched")

    return {
        "status": "completed",
        "pending_found": len(pending_sources),
        "dispatched": dispatched,
        "timestamp": timezone.now().isoformat(),
    }


# ============================================================
# Unified Scheduling Tasks (replaces separate check_due_* tasks)
# ============================================================


@shared_task(name="crawler.tasks.check_due_schedules")
def check_due_schedules() -> Dict[str, Any]:
    """
    Unified periodic task to check for schedules due for execution.

    Runs every 5 minutes via Celery Beat.
    Handles all schedule categories (competition, discovery, retailer).

    Returns:
        Dict with check results and dispatched jobs
    """
    from django.db.models import Q
    from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory

    logger.info("Checking for due schedules (unified)...")

    now = timezone.now()
    jobs_dispatched = []

    # Find all due schedules
    due_schedules = CrawlSchedule.objects.filter(
        is_active=True,
    ).filter(
        Q(next_run__isnull=True) | Q(next_run__lte=now)
    ).order_by("-priority", "next_run")

    for schedule in due_schedules:
        try:
            # Create job record
            job = CrawlJob.objects.create(schedule=schedule)

            # Dispatch to appropriate queue based on category
            queue = "crawl" if schedule.category == ScheduleCategory.COMPETITION else "discovery"

            run_scheduled_job.apply_async(
                args=[str(schedule.id), str(job.id)],
                queue=queue,
            )

            jobs_dispatched.append({
                "schedule_id": str(schedule.id),
                "job_id": str(job.id),
                "category": schedule.category,
                "name": schedule.name,
            })

            logger.info(f"Dispatched job {job.id} for schedule: {schedule.name}")

        except Exception as e:
            logger.error(f"Failed to dispatch schedule {schedule.name}: {e}")

    logger.info(f"Due schedule check complete: {len(jobs_dispatched)} jobs dispatched")

    return {
        "checked_at": now.isoformat(),
        "jobs_dispatched": len(jobs_dispatched),
        "details": jobs_dispatched,
    }


@shared_task(name="crawler.tasks.run_scheduled_job", bind=True)
def run_scheduled_job(self, schedule_id: str, job_id: str) -> Dict[str, Any]:
    """
    Execute a scheduled crawl job.

    Routes to appropriate orchestrator based on schedule category.

    Args:
        schedule_id: UUID of the CrawlSchedule
        job_id: UUID of the CrawlJob

    Returns:
        Dict with job results
    """
    from crawler.models import CrawlSchedule, CrawlJob, CrawlJobStatus, ScheduleCategory

    logger.info(f"Running scheduled job {job_id} for schedule {schedule_id}")

    schedule = CrawlSchedule.objects.get(id=schedule_id)
    job = CrawlJob.objects.get(id=job_id)

    job.status = CrawlJobStatus.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        # Route to appropriate orchestrator
        if schedule.category == ScheduleCategory.COMPETITION:
            result = run_competition_flow(schedule, job)
        elif schedule.category == ScheduleCategory.DISCOVERY:
            result = run_discovery_flow(schedule, job)
        else:
            raise ValueError(f"Unknown category: {schedule.category}")

        # Update job with results
        job.status = CrawlJobStatus.COMPLETED
        job.completed_at = timezone.now()
        job.products_found = result.get("products_found", 0)
        job.products_new = result.get("products_new", 0)
        job.results_summary = result
        job.save()

        # Update schedule stats
        schedule.update_next_run()
        schedule.record_run_stats(
            products_found=job.products_found,
            products_new=job.products_new,
            products_duplicate=result.get("products_duplicate", 0),
            errors=job.errors_count,
        )

        logger.info(f"Scheduled job {job_id} completed: {result}")
        return result

    except Exception as e:
        job.status = CrawlJobStatus.FAILED
        job.completed_at = timezone.now()
        job.error_message = str(e)
        job.save()

        schedule.total_errors += 1
        schedule.save(update_fields=["total_errors"])

        logger.error(f"Scheduled job {job_id} failed: {e}")
        raise


def run_discovery_flow(schedule, job, enrich: bool = False) -> Dict[str, Any]:
    """
    Execute discovery search flow using DiscoveryOrchestrator.

    Args:
        schedule: CrawlSchedule instance
        job: CrawlJob instance (used for tracking, orchestrator creates its own DiscoveryJob)
        enrich: Whether to run verification pipeline on extracted products

    Returns:
        Dict with discovery results
    """
    from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

    # DiscoveryOrchestrator accepts CrawlSchedule directly
    # Note: enrich parameter is stored on schedule, not passed to __init__
    orchestrator = DiscoveryOrchestrator(schedule=schedule)

    # Run discovery - orchestrator creates and manages its own DiscoveryJob
    discovery_job = orchestrator.run()

    # Return results in the format expected by run_scheduled_job
    return {
        "products_found": discovery_job.products_new + discovery_job.products_updated,
        "products_new": discovery_job.products_new,
        "products_duplicate": discovery_job.products_updated,
        "serpapi_calls": discovery_job.serpapi_calls_used,
        "discovery_job_id": str(discovery_job.id),
    }


def run_competition_flow(schedule, job) -> Dict[str, Any]:
    """
    Execute competition crawl flow using CompetitionOrchestratorV2.

    This flow:
    1. Fetches competition results page
    2. Parses awards and creates skeleton products
    3. If schedule.enrich=True: enriches skeletons with full product data

    Args:
        schedule: CrawlSchedule instance
        job: CrawlJob instance

    Returns:
        Dict with competition results including enrichment stats
    """
    import asyncio
    from crawler.fetchers.smart_router import SmartRouter

    orchestrator = CompetitionOrchestratorV2()
    results = {
        "products_found": 0,
        "products_new": 0,
        "products_duplicate": 0,
        "products_filtered": 0,
        "competitions_processed": [],
        "product_types_filter": schedule.product_types or [],
        "enrichment": {
            "enabled": schedule.enrich,
            "skeletons_processed": 0,
            "urls_discovered": 0,
            "urls_processed": 0,
            "products_enriched": 0,
        },
    }

    # Get product types filter from schedule
    product_types_filter = schedule.product_types or []
    max_results = schedule.max_results_per_term or 10

    # Parse search_terms as "competition:year" format
    for term in schedule.search_terms:
        if ":" in term:
            competition_key, year = term.split(":", 1)
            year = int(year)
        else:
            competition_key = term
            year = timezone.now().year

        try:
            # Fetch competition page
            router = SmartRouter()

            # Build URL with filtering params based on competition
            if schedule.base_url:
                url = f"{schedule.base_url}{year}/"

                # IWSC-specific: Add type=3 for spirits category
                if competition_key.lower() == 'iwsc':
                    # type=3 = Spirits category on IWSC
                    # Also search for whisky to get relevant results
                    url = f"{schedule.base_url}{year}/?type=3"
                    if 'whiskey' in product_types_filter or 'whisky' in product_types_filter:
                        url += "&q=whisky"
                    elif 'port_wine' in product_types_filter:
                        url += "&q=port"
            else:
                url = None

            if not url:
                logger.warning(f"No base_url for competition: {competition_key}")
                continue

            logger.info(f"Fetching competition URL: {url}")

            # router.fetch() returns FetchResult object, extract .content
            fetch_result = asyncio.run(router.fetch(url))
            if not fetch_result.success:
                logger.error(f"Failed to fetch {url}: {fetch_result.error}")
                results["errors"] = results.get("errors", []) + [f"Fetch failed: {fetch_result.error}"]
                continue

            html_content = fetch_result.content

            # Run competition discovery with product type filtering
            comp_result = asyncio.run(
                orchestrator.run_competition_discovery(
                    competition_url=url,
                    crawl_job=job,
                    html_content=html_content,
                    competition_key=competition_key,
                    year=year,
                    product_types=product_types_filter,
                    max_results=max_results,
                )
            )

            results["products_found"] += comp_result.awards_found
            results["products_new"] += comp_result.skeletons_created
            results["products_filtered"] += getattr(comp_result, 'products_filtered', 0)
            results["competitions_processed"].append(comp_result.to_dict())

        except Exception as e:
            logger.error(f"Error processing competition {competition_key}:{year}: {e}")
            results["errors"] = results.get("errors", []) + [str(e)]

    # ================================================================
    # ENRICHMENT PHASE: Enrich skeleton products with full data
    # (Processes URLs directly in memory - no Redis required)
    # ================================================================
    if schedule.enrich and results["products_new"] > 0:
        logger.info(f"Starting enrichment for {results['products_new']} skeleton products...")

        try:
            # Import required modules
            from crawler.fetchers.smart_router import SmartRouter
            from crawler.services.content_processor import ContentProcessor
            from crawler.models import DiscoveredProduct, DiscoveredProductStatus
            from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher

            # Initialize enrichment components (API key from settings.SERPAPI_API_KEY)
            enrichment_searcher = EnrichmentSearcher(
                api_key=None,  # Uses settings.SERPAPI_API_KEY
                results_per_search=5,
            )
            router = SmartRouter()
            processor = ContentProcessor()

            # Get skeleton products created in this run
            skeletons = list(DiscoveredProduct.objects.filter(
                status=DiscoveredProductStatus.SKELETON,
                crawl_job=job,
            ).order_by('-discovered_at')[:results["products_new"]])

            logger.info(f"Found {len(skeletons)} skeleton products to enrich")

            # Collect all URLs in memory (no Redis)
            url_queue = []  # List of (skeleton_id, url, metadata) tuples

            # Step 1: Search SerpAPI for each skeleton
            logger.info("Step 1: Searching for product information via SerpAPI...")

            async def search_all_skeletons():
                for skeleton in skeletons:
                    try:
                        search_results = await enrichment_searcher.search_for_enrichment(
                            product_name=skeleton.name,
                            crawl_job=job,
                        )
                        for result in search_results:
                            url_queue.append((str(skeleton.id), result.get('url'), result))
                        logger.info(f"  Found {len(search_results)} URLs for '{skeleton.name}'")
                    except Exception as e:
                        logger.error(f"  Search failed for '{skeleton.name}': {e}")

            asyncio.run(search_all_skeletons())

            results["enrichment"]["skeletons_processed"] = len(skeletons)
            results["enrichment"]["urls_discovered"] = len(url_queue)
            logger.info(f"Enrichment search complete: {len(skeletons)} skeletons, {len(url_queue)} URLs found")

            # Step 2: Process URLs directly (no Redis queue)
            # Use AI Enhancement client V2 for extraction
            if url_queue:
                logger.info(f"Step 2: Processing {len(url_queue)} URLs (fetching, extracting data)...")

                from crawler.services.ai_client_v2 import get_ai_client_v2
                ai_client = get_ai_client_v2()

                urls_processed = 0
                products_enriched = 0
                enriched_skeleton_ids = set()  # Track which skeletons have been enriched

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    for skeleton_id, url, metadata in url_queue:
                        # Skip if skeleton already enriched
                        if skeleton_id in enriched_skeleton_ids:
                            continue

                        if not url:
                            continue

                        try:
                            # Fetch URL content
                            fetch_result = loop.run_until_complete(router.fetch(url))

                            if fetch_result.success:
                                urls_processed += 1

                                # Extract content using trafilatura
                                try:
                                    import trafilatura
                                    extracted_content = trafilatura.extract(fetch_result.content) or fetch_result.content[:50000]
                                except ImportError:
                                    # Fall back to raw content if trafilatura not available
                                    extracted_content = fetch_result.content[:50000]

                                # Get skeleton's product type for hint
                                skeleton = DiscoveredProduct.objects.get(id=skeleton_id)
                                product_type_hint = skeleton.product_type

                                # Call AI Enhancement V2 to get extracted data
                                extract_result = loop.run_until_complete(
                                    ai_client.extract(
                                        content=extracted_content,
                                        source_url=url,
                                        product_type=product_type_hint,
                                    )
                                )

                                if extract_result.success and extract_result.products:
                                    # Get the primary product's extracted data
                                    enriched = extract_result.products[0].extracted_data
                                    update_fields = []

                                    # Map enrichment data to skeleton fields
                                    if enriched.get('abv') and not skeleton.abv:
                                        skeleton.abv = enriched['abv']
                                        update_fields.append('abv')
                                    if enriched.get('age_statement') and not skeleton.age_statement:
                                        skeleton.age_statement = str(enriched['age_statement'])
                                        update_fields.append('age_statement')
                                    if enriched.get('description') and not skeleton.description:
                                        skeleton.description = enriched['description']
                                        update_fields.append('description')
                                    if enriched.get('region') and not skeleton.region:
                                        skeleton.region = enriched['region']
                                        update_fields.append('region')
                                    if enriched.get('country') and not skeleton.country:
                                        skeleton.country = enriched['country']
                                        update_fields.append('country')

                                    # Tasting notes - check nested structure first
                                    tasting_notes = enriched.get('tasting_notes', {})
                                    if isinstance(tasting_notes, dict):
                                        if tasting_notes.get('nose') and not skeleton.nose_description:
                                            skeleton.nose_description = tasting_notes['nose']
                                            update_fields.append('nose_description')
                                        if tasting_notes.get('palate') and not skeleton.palate_description:
                                            skeleton.palate_description = tasting_notes['palate']
                                            update_fields.append('palate_description')
                                        if tasting_notes.get('finish') and not skeleton.finish_description:
                                            skeleton.finish_description = tasting_notes['finish']
                                            update_fields.append('finish_description')

                                    # Also check top-level tasting note fields
                                    if enriched.get('nose_description') and not skeleton.nose_description:
                                        skeleton.nose_description = enriched['nose_description']
                                        if 'nose_description' not in update_fields:
                                            update_fields.append('nose_description')
                                    if enriched.get('palate_description') and not skeleton.palate_description:
                                        skeleton.palate_description = enriched['palate_description']
                                        if 'palate_description' not in update_fields:
                                            update_fields.append('palate_description')
                                    if enriched.get('finish_description') and not skeleton.finish_description:
                                        skeleton.finish_description = enriched['finish_description']
                                        if 'finish_description' not in update_fields:
                                            update_fields.append('finish_description')

                                    # Flavor arrays from flavor_profile
                                    flavor_profile = enriched.get('flavor_profile', {})
                                    if isinstance(flavor_profile, dict):
                                        if flavor_profile.get('primary_flavors') and not skeleton.palate_flavors:
                                            skeleton.palate_flavors = flavor_profile['primary_flavors']
                                            update_fields.append('palate_flavors')

                                    # Update source URL if not set
                                    if url and not skeleton.source_url:
                                        skeleton.source_url = url
                                        update_fields.append('source_url')

                                    # Mark as partial/complete if we got significant data
                                    if len(update_fields) >= 2:  # At least 2 fields enriched
                                        # Use PARTIAL for now (COMPLETE requires palate per model docs)
                                        skeleton.status = DiscoveredProductStatus.PARTIAL
                                        update_fields.append('status')

                                        # Add serpapi_enrichment to discovery_sources
                                        sources = skeleton.discovery_sources or []
                                        if 'serpapi_enrichment' not in sources:
                                            sources.append('serpapi_enrichment')
                                            skeleton.discovery_sources = sources
                                            update_fields.append('discovery_sources')

                                        skeleton.save(update_fields=update_fields)
                                        products_enriched += 1
                                        enriched_skeleton_ids.add(skeleton_id)
                                        logger.info(f"Enriched '{skeleton.name}': {update_fields}")
                                    else:
                                        logger.debug(f"Not enough data from {url}: got fields {list(enriched.keys())}")
                                else:
                                    logger.debug(f"AI Enhancement V2 failed for {url}: {extract_result.error}")

                            else:
                                logger.debug(f"Failed to fetch URL {url}: {fetch_result.error}")

                        except DiscoveredProduct.DoesNotExist:
                            logger.warning(f"Skeleton {skeleton_id} not found")
                        except Exception as e:
                            logger.error(f"Error processing URL {url}: {e}")

                finally:
                    loop.run_until_complete(router.close())
                    loop.close()

                results["enrichment"]["urls_processed"] = urls_processed
                results["enrichment"]["products_enriched"] = products_enriched

                logger.info(
                    f"Enrichment complete: {urls_processed} URLs processed, "
                    f"{products_enriched}/{len(skeletons)} products enriched"
                )

        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            results["enrichment"]["error"] = str(e)

    return results


@shared_task(name="crawler.tasks.trigger_scheduled_job_manual", bind=True)
def trigger_scheduled_job_manual(self, schedule_id: str) -> Dict[str, Any]:
    """
    Manually trigger a scheduled job immediately.

    Args:
        schedule_id: UUID of the CrawlSchedule to run

    Returns:
        Dict with dispatch status
    """
    from crawler.models import CrawlSchedule, CrawlJob, ScheduleCategory

    logger.info(f"Manual trigger for schedule {schedule_id}")

    try:
        schedule = CrawlSchedule.objects.get(id=schedule_id)
    except CrawlSchedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found")
        return {
            "triggered": False,
            "error": f"Schedule {schedule_id} not found",
        }

    # Create job
    job = CrawlJob.objects.create(schedule=schedule)

    # Dispatch to appropriate queue
    queue = "crawl" if schedule.category == ScheduleCategory.COMPETITION else "discovery"

    run_scheduled_job.apply_async(
        args=[str(schedule.id), str(job.id)],
        queue=queue,
    )

    logger.info(f"Manual job dispatched for: {schedule.name}")

    return {
        "triggered": True,
        "schedule_id": str(schedule.id),
        "job_id": str(job.id),
        "schedule_name": schedule.name,
    }


# ============================================================
# End Unified Scheduling Tasks
# ============================================================


@shared_task(name="crawler.tasks.cleanup_raw_content_batch")
def cleanup_raw_content_batch(limit: int = 100) -> Dict[str, Any]:
    """
    Batch cleanup of raw_content for successfully archived sources.

    Task Group 31: Periodic task to find CrawledSource records with
    wayback_status='saved' and raw_content_cleared=False, then clear
    raw_content to save storage.

    Args:
        limit: Maximum number of sources to clean up in this batch

    Returns:
        Dict with cleanup results
    """
    from crawler.models import CrawledSource, WaybackStatusChoices
    from crawler.services.wayback import cleanup_raw_content

    logger.info(f"Starting raw_content batch cleanup, limit={limit}")

    # Find sources ready for cleanup
    sources_to_cleanup = CrawledSource.objects.filter(
        wayback_status=WaybackStatusChoices.SAVED,
        raw_content_cleared=False,
    ).exclude(
        raw_content__isnull=True,
    ).exclude(
        raw_content="",
    )[:limit]

    cleaned = 0
    errors = 0

    for source in sources_to_cleanup:
        try:
            if cleanup_raw_content(source):
                cleaned += 1
        except Exception as e:
            errors += 1
            logger.error(f"Failed to cleanup raw_content for {source.url}: {e}")

    logger.info(f"Raw content cleanup: {cleaned} cleaned, {errors} errors")

    return {
        "status": "completed",
        "sources_found": len(sources_to_cleanup),
        "cleaned": cleaned,
        "errors": errors,
        "timestamp": timezone.now().isoformat(),
    }


# ============================================================
# Phase 6: API Triggered Award Crawl Task
# ============================================================

def _get_verification_pipeline():
    """Get VerificationPipeline instance (lazy import to avoid circular imports)."""
    from crawler.verification.pipeline import VerificationPipeline
    return VerificationPipeline()


@shared_task(name="crawler.tasks.trigger_award_crawl", bind=True)
def trigger_award_crawl(
    self,
    job_id: str,
    source: str,
    year: int,
    product_types: Optional[List[str]] = None,
    enrich: bool = False
) -> Dict[str, Any]:
    """
    Celery task to perform award site crawl.

    Unified Pipeline Phase 7: Async award crawl triggered via REST API.

    Args:
        job_id: APICrawlJob.job_id to update
        source: Award source identifier (iwsc, dwwa, sfwsc, wwa)
        year: Competition year to crawl
        product_types: Optional list of product types to filter
        enrich: Whether to run verification pipeline on extracted products

    Returns:
        Dict with crawl results
    """
    logger.info(f"Starting award crawl: job_id={job_id}, source={source}, year={year}")

    try:
        # Update job status to running
        job = APICrawlJob.objects.get(job_id=job_id)
        job.status = 'running'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])

        # Get the collector for this source
        from crawler.discovery.collectors import get_collector
        collector = get_collector(source)

        # Collect award detail URLs
        detail_urls = collector.collect(
            year=year,
            product_types=product_types or [],
        )

        products_found = 0
        products_saved = 0
        errors = []

        # Get AI extractor
        from crawler.discovery.extractors import AIExtractor
        extractor = AIExtractor()

        for url_info in detail_urls:
            try:
                # Extract product data
                product_data = extractor.extract(
                    url=url_info.url,
                    context={
                        'source': source,
                        'year': year,
                        'medal_hint': getattr(url_info, 'medal_hint', None),
                        'product_type_hint': getattr(url_info, 'product_type_hint', None),
                    }
                )

                if product_data:
                    products_found += 1

                    # Save to database using individual columns
                    try:
                        product = DiscoveredProduct.objects.create(
                            name=product_data.get('name'),
                            source_url=url_info.url,
                            product_type=product_data.get('product_type', 'whiskey'),
                            status='partial',
                            abv=product_data.get('abv'),
                            age_statement=product_data.get('age_statement'),
                            country=product_data.get('country'),
                            region=product_data.get('region'),
                            nose_description=product_data.get('nose_description'),
                            palate_description=product_data.get('palate_description'),
                            finish_description=product_data.get('finish_description'),
                        )
                        products_saved += 1

                        # Run verification if enrich=True
                        if enrich:
                            try:
                                pipeline = _get_verification_pipeline()
                                pipeline.verify_product(product)
                            except Exception as e:
                                logger.error(f"Verification failed for {product.name}: {e}")

                    except Exception as e:
                        errors.append({
                            'url': url_info.url,
                            'error': f'Save failed: {str(e)}'
                        })

                # Update progress
                job.progress = {
                    'products_found': products_found,
                    'products_saved': products_saved,
                    'errors_count': len(errors),
                }
                job.save(update_fields=['progress'])

            except Exception as e:
                errors.append({
                    'url': url_info.url,
                    'error': str(e)
                })
                logger.error(f"Failed to extract from {url_info.url}: {e}")

        # Mark job as completed
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress = {
            'products_found': products_found,
            'products_saved': products_saved,
            'errors_count': len(errors),
        }
        job.save(update_fields=['status', 'completed_at', 'progress'])

        logger.info(
            f"Award crawl completed: job_id={job_id}, "
            f"products_found={products_found}, products_saved={products_saved}"
        )

        return {
            'status': 'completed',
            'job_id': job_id,
            'source': source,
            'year': year,
            'products_found': products_found,
            'products_saved': products_saved,
            'errors': errors,
        }

    except Exception as e:
        logger.error(f"Award crawl failed: job_id={job_id}, error={e}")

        # Mark job as failed
        try:
            job = APICrawlJob.objects.get(job_id=job_id)
            job.status = 'failed'
            job.error = str(e)
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'error', 'completed_at'])
        except APICrawlJob.DoesNotExist:
            pass

        return {
            'status': 'failed',
            'job_id': job_id,
            'error': str(e),
        }


# ============================================================
# Phase 7: Health Check Tasks
# ============================================================

# Known sources for health checking
HEALTH_CHECK_SOURCES = ['iwsc', 'dwwa', 'sfwsc', 'wwa']


def _get_selector_health_checker():
    """Lazy load SelectorHealthChecker to avoid circular imports."""
    from crawler.discovery.health.selector_health import SelectorHealthChecker
    return SelectorHealthChecker()


def _get_ai_extractor():
    """Lazy load AIExtractor to avoid circular imports."""
    from crawler.discovery.extractors import AIExtractor
    return AIExtractor()


def _send_alert(source: str, message: str, severity: str = 'warning'):
    """Send alert via Sentry and optionally Slack."""
    try:
        from crawler.discovery.health.alerts import (
            StructureChangeAlertHandler,
            StructureAlert,
            AlertSeverity,
        )

        severity_map = {
            'info': AlertSeverity.INFO,
            'warning': AlertSeverity.WARNING,
            'critical': AlertSeverity.CRITICAL,
        }

        alert = StructureAlert(
            source=source,
            severity=severity_map.get(severity, AlertSeverity.WARNING),
            message=message,
        )

        handler = StructureChangeAlertHandler(config={})
        handler.send_alert(alert)
    except ImportError:
        # Fallback to logging if alert handler not available
        logger.warning(f"Alert for {source}: {message}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


@shared_task(name="crawler.tasks.check_source_health", bind=True)
def check_source_health(
    self,
    source: Optional[str] = None,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Celery task to check health of award site sources.

    Unified Pipeline Phase 7: Periodic health check for sources.
    Runs via Celery Beat to detect structural changes before crawls fail.

    Args:
        source: Optional specific source to check. If None, checks all sources.
        year: Optional year for the check. Defaults to current year.

    Returns:
        Dict with health check results
    """
    from crawler.models import SourceHealthCheck

    if year is None:
        year = timezone.now().year

    checker = _get_selector_health_checker()

    if source:
        # Check single source
        logger.info(f"Checking health for source: {source}, year: {year}")

        try:
            report = checker.check_source(source, year)

            # Save to database
            SourceHealthCheck.objects.create(
                source=source,
                check_type='selector',
                is_healthy=report.is_healthy,
                details={
                    'sample_url': report.sample_url,
                    'selectors_tested': report.selectors_tested,
                    'selectors_healthy': report.selectors_healthy,
                    'failed_selectors': report.failed_selectors,
                    'timestamp': report.timestamp,
                },
            )

            result = {
                'source': source,
                'is_healthy': report.is_healthy,
                'selectors_tested': report.selectors_tested,
                'selectors_healthy': report.selectors_healthy,
                'sample_url': report.sample_url,
            }

            if not report.is_healthy:
                result['failures'] = report.failed_selectors
                # Send alert for unhealthy source
                _send_alert(
                    source,
                    f"Source {source} health check failed: {report.failed_selectors}",
                    severity='critical' if report.selectors_healthy == 0 else 'warning',
                )

            return result

        except Exception as e:
            logger.error(f"Health check failed for {source}: {e}")
            return {
                'source': source,
                'is_healthy': False,
                'error': str(e),
            }
    else:
        # Check all sources
        logger.info("Checking health for all sources")

        results = []
        total_healthy = 0

        for src in HEALTH_CHECK_SOURCES:
            try:
                report = checker.check_source(src, year)

                SourceHealthCheck.objects.create(
                    source=src,
                    check_type='selector',
                    is_healthy=report.is_healthy,
                    details={
                        'failed_selectors': report.failed_selectors,
                    },
                )

                results.append({
                    'source': src,
                    'is_healthy': report.is_healthy,
                })

                if report.is_healthy:
                    total_healthy += 1
                else:
                    _send_alert(
                        src,
                        f"Source {src} health check failed",
                        severity='warning',
                    )

            except Exception as e:
                logger.error(f"Health check failed for {src}: {e}")
                results.append({
                    'source': src,
                    'is_healthy': False,
                    'error': str(e),
                })

        return {
            'sources_checked': len(results),
            'total_healthy': total_healthy,
            'results': results,
        }


# Known products for verification (ground truth)
KNOWN_PRODUCTS = {
    'iwsc': [
        {
            'url': 'https://www.iwsc.net/results/detail/157656/10-yo-tawny-nv',
            'expected': {
                'name_contains': '10 Year',
                'medal': 'Gold',
                'has_tasting_notes': True,
            },
        },
    ],
    'dwwa': [
        {
            'url': 'https://awards.decanter.com/DWWA/2025/wines/768949',
            'expected': {
                'name_contains': 'Galpin Peak',
                'medal_in': ['Gold', 'Silver', 'Bronze', 'Platinum'],
                'has_tasting_notes': True,
            },
        },
    ],
}


def _verify_single_product(extractor, url: str, expected: Dict[str, Any]) -> Dict[str, Any]:
    """Verify extraction for a single known product."""
    try:
        extracted = extractor.extract_from_url(url)

        checks = []
        for key, exp_value in expected.items():
            if key == 'name_contains':
                actual = extracted.get('name', '')
                passed = exp_value.lower() in actual.lower() if actual else False
                checks.append({'check': key, 'passed': passed})
            elif key == 'medal_in':
                actual = extracted.get('medal', '')
                passed = actual in exp_value
                checks.append({'check': key, 'passed': passed})
            elif key == 'medal':
                actual = extracted.get('medal', '')
                passed = actual == exp_value
                checks.append({'check': key, 'passed': passed})
            elif key == 'has_tasting_notes':
                has_notes = bool(
                    extracted.get('palate_description') or
                    extracted.get('nose_description') or
                    extracted.get('finish_description')
                )
                passed = has_notes == exp_value
                checks.append({'check': key, 'passed': passed})

        all_passed = all(c['passed'] for c in checks)
        return {
            'url': url,
            'passed': all_passed,
            'checks': checks,
        }
    except Exception as e:
        return {
            'url': url,
            'passed': False,
            'error': str(e),
            'checks': [],
        }


@shared_task(name="crawler.tasks.verify_known_products", bind=True)
def verify_known_products(
    self,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Celery task to verify extraction on known products.

    Unified Pipeline Phase 7: Weekly verification of extraction accuracy
    using ground truth products.

    Args:
        source: Optional specific source to verify. If None, verifies all sources.

    Returns:
        Dict with verification results
    """
    from crawler.models import SourceHealthCheck

    extractor = _get_ai_extractor()

    if source:
        # Verify single source
        if source not in KNOWN_PRODUCTS:
            return {'error': f'No known products for {source}'}

        logger.info(f"Verifying known products for source: {source}")

        products = KNOWN_PRODUCTS[source]
        results = []

        for product in products:
            result = _verify_single_product(
                extractor,
                product['url'],
                product['expected'],
            )
            results.append(result)

        passed = sum(1 for r in results if r['passed'])
        is_healthy = passed == len(results)

        # Save to database
        SourceHealthCheck.objects.create(
            source=source,
            check_type='known_product',
            is_healthy=is_healthy,
            details={
                'total': len(results),
                'passed': passed,
                'details': results,
            },
        )

        return {
            'source': source,
            'total': len(results),
            'passed': passed,
            'health': 'HEALTHY' if is_healthy else 'DEGRADED',
            'details': results,
        }
    else:
        # Verify all sources
        logger.info("Verifying known products for all sources")

        all_results = {}
        for src in KNOWN_PRODUCTS.keys():
            try:
                products = KNOWN_PRODUCTS[src]
                results = []

                for product in products:
                    result = _verify_single_product(
                        extractor,
                        product['url'],
                        product['expected'],
                    )
                    results.append(result)

                passed = sum(1 for r in results if r['passed'])
                is_healthy = passed == len(results)

                SourceHealthCheck.objects.create(
                    source=src,
                    check_type='known_product',
                    is_healthy=is_healthy,
                    details={
                        'total': len(results),
                        'passed': passed,
                    },
                )

                all_results[src] = {
                    'total': len(results),
                    'passed': passed,
                    'health': 'HEALTHY' if is_healthy else 'DEGRADED',
                }

            except Exception as e:
                logger.error(f"Verification failed for {src}: {e}")
                all_results[src] = {'error': str(e)}

        return {
            'sources_verified': list(all_results.keys()),
            'results': all_results,
        }
