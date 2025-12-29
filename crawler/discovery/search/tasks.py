"""
Celery Tasks - Automated generic search discovery.

Phase 3: Generic Search Discovery

Tasks:
- run_generic_discovery: Execute searches for a product type
- queue_target_for_scraping: Queue discovered URLs for scraping
- run_all_generic_discovery: Run discovery for all product types
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(queue="search")
def run_generic_discovery(product_type: str = "whiskey") -> dict:
    """
    Run generic search discovery for a product type.

    Searches for generic terms like "best whisky 2025" and queues
    discovered target URLs for scraping.

    Args:
        product_type: "whiskey" or "port_wine"

    Returns:
        Dict with status, queries executed, targets found/queued
    """
    from .config import SearchConfig
    from .scheduler import SearchScheduler
    from .target_extractor import TargetURLExtractor
    from crawler.discovery.serpapi.client import SerpAPIClient
    from crawler.discovery.serpapi.rate_limiter import RateLimiter

    # Initialize components
    rate_limiter = RateLimiter()
    scheduler = SearchScheduler(rate_limiter)
    config = SearchConfig()
    extractor = TargetURLExtractor(config)

    # Get queries to execute
    queries = scheduler.get_next_queries(product_type, count=5)

    if not queries:
        logger.info(f"No queries available for {product_type}")
        return {"status": "no_queries", "product_type": product_type}

    # Initialize SerpAPI client
    try:
        client = SerpAPIClient()
    except ValueError as e:
        logger.error(f"Failed to initialize SerpAPI client: {e}")
        return {"status": "error", "error": str(e), "product_type": product_type}

    all_targets = []

    for query in queries:
        # Check if we can make another request
        if not scheduler.can_execute_search():
            logger.warning("Daily search quota exhausted")
            break

        try:
            logger.info(f"Searching: {query}")
            results = client.google_search(query)

            # Record the API request
            rate_limiter.record_request()

            # Mark query as executed
            scheduler.mark_executed(query)

            # Extract targets from results
            targets = extractor.extract_targets(results)
            all_targets.extend(targets)

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            continue

    # Deduplicate targets from multiple searches
    unique_targets = extractor.deduplicate_across_searches(all_targets)

    # Queue targets for scraping (limit per run)
    queued = 0
    for target in unique_targets[:20]:
        queue_target_for_scraping.delay(target)
        queued += 1

    logger.info(
        f"Generic discovery complete: {len(queries)} searches, "
        f"{len(all_targets)} targets found, {queued} queued"
    )

    return {
        "status": "completed",
        "product_type": product_type,
        "queries_executed": len(queries),
        "targets_found": len(all_targets),
        "targets_queued": queued,
    }


@shared_task(queue="search")
def queue_target_for_scraping(target: dict) -> None:
    """
    Queue a target URL for scraping.

    Creates a CrawledURL entry if the URL hasn't been crawled before.

    Args:
        target: Dict with url, title, source, priority
    """
    from crawler.models import CrawledURL

    url = target.get("url", "")
    if not url:
        return

    # Compute URL hash for deduplication
    url_hash = CrawledURL.compute_url_hash(url)

    # Check if already crawled
    if CrawledURL.objects.filter(url_hash=url_hash).exists():
        logger.debug(f"URL already crawled: {url}")
        return

    # Create pending crawl entry
    try:
        CrawledURL.objects.create(
            url=url,
            url_hash=url_hash,
            is_product_page=False,  # Will be determined during crawl
            was_processed=False,
        )
        logger.info(f"Queued target for scraping: {url}")
    except Exception as e:
        logger.error(f"Failed to queue target {url}: {e}")


@shared_task(queue="search")
def run_all_generic_discovery() -> dict:
    """
    Run generic discovery for all product types.

    Returns:
        Dict mapping product type to discovery result
    """
    product_types = ["whiskey", "port_wine"]

    results = {}
    for ptype in product_types:
        result = run_generic_discovery(ptype)
        results[ptype] = result

    return results
