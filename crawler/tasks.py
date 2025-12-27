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
    ProductType,
    CrawlError,
    ErrorType,
)

logger = logging.getLogger(__name__)


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

    Uses ContentProcessor for AI Enhancement Service integration.

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

        try:
            # Run async fetch in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                metrics = loop.run_until_complete(
                    _process_source_urls(source, job, router, frontier, metrics)
                )
            finally:
                loop.close()

        finally:
            # Cleanup router resources
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(router.close())
            finally:
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
