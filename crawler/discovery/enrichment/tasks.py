"""
Celery Tasks for Product Enrichment.

Phase 4: Product Enrichment - Async task definitions.
"""

import logging
from typing import Dict, Any, List

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from crawler.models import DiscoveredProduct
from crawler.discovery.serpapi.client import SerpAPIClient
from crawler.discovery.serpapi.rate_limiter import RateLimiter
from .orchestrator import ProductEnricher

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def enrich_product_task(self, product_id: int) -> Dict[str, Any]:
    """
    Enrich a single product by ID.

    Args:
        product_id: ID of the product to enrich

    Returns:
        Result dictionary with success status
    """
    # Check rate limit
    rate_limiter = RateLimiter()
    if not rate_limiter.can_make_request():
        logger.warning(f"Rate limited - cannot enrich product {product_id}")
        return {
            "success": False,
            "rate_limited": True,
            "error": "Rate limit exceeded",
        }

    try:
        product = DiscoveredProduct.objects.get(id=product_id)
    except (DiscoveredProduct.DoesNotExist, ObjectDoesNotExist):
        logger.error(f"Product {product_id} not found")
        return {
            "success": False,
            "error": f"Product {product_id} not found",
        }

    # Create client and enricher
    client = SerpAPIClient()
    enricher = ProductEnricher(client=client)

    # Enrich product
    result = enricher.enrich_product(product)

    return result


@shared_task(bind=True)
def enrich_batch_task(self, product_ids: List[int]) -> Dict[str, Any]:
    """
    Enrich multiple products by ID.

    Args:
        product_ids: List of product IDs to enrich

    Returns:
        Result dictionary with counts
    """
    # Create client and enricher
    client = SerpAPIClient()
    enricher = ProductEnricher(client=client)

    # Fetch products
    products = list(DiscoveredProduct.objects.filter(id__in=product_ids))

    # Enrich batch
    results = enricher.enrich_batch(products)

    # Count results
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "processed": len(results),
        "successful": successful,
        "failed": failed,
    }


@shared_task(bind=True)
def enrich_pending_task(self, limit: int = 50) -> Dict[str, Any]:
    """
    Enrich pending products.

    Args:
        limit: Maximum number of products to process

    Returns:
        Result dictionary with counts
    """
    # Check rate limit
    rate_limiter = RateLimiter()
    if not rate_limiter.can_make_request():
        logger.warning("Rate limited - cannot process pending products")
        return {
            "processed": 0,
            "rate_limited": True,
        }

    # Create client and enricher
    client = SerpAPIClient()
    enricher = ProductEnricher(client=client)

    # Get pending products
    products = ProductEnricher.get_pending_products(limit=limit)

    if not products:
        return {
            "processed": 0,
            "message": "No pending products",
        }

    # Enrich batch
    results = enricher.enrich_batch(products)

    # Count results
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "processed": len(results),
        "successful": successful,
        "failed": failed,
    }


@shared_task(bind=True)
def schedule_enrichment_task(self, limit: int = 100) -> Dict[str, Any]:
    """
    Schedule individual enrichment tasks for pending products.

    This creates separate tasks for each product for better
    parallelization and error isolation.

    Args:
        limit: Maximum number of products to schedule

    Returns:
        Result dictionary with scheduled count
    """
    # Get pending products
    products = ProductEnricher.get_pending_products(limit=limit)

    if not products:
        return {
            "scheduled": 0,
            "message": "No pending products",
        }

    # Schedule individual tasks
    scheduled = 0
    for product in products:
        enrich_product_task.delay(product_id=product.id)
        scheduled += 1

    logger.info(f"Scheduled {scheduled} enrichment tasks")

    return {
        "scheduled": scheduled,
    }


@shared_task(bind=True)
def enrich_prices_only_task(self, product_id: int) -> Dict[str, Any]:
    """
    Enrich only prices for a product.

    Args:
        product_id: ID of the product to enrich

    Returns:
        Result dictionary
    """
    try:
        product = DiscoveredProduct.objects.get(id=product_id)
    except (DiscoveredProduct.DoesNotExist, ObjectDoesNotExist):
        return {
            "success": False,
            "error": f"Product {product_id} not found",
        }

    client = SerpAPIClient()
    enricher = ProductEnricher(client=client)

    result = enricher.enrich_product(
        product,
        enrich_prices=True,
        enrich_reviews=False,
        enrich_images=False,
        enrich_articles=False
    )

    return result


@shared_task(bind=True)
def enrich_images_only_task(self, product_id: int) -> Dict[str, Any]:
    """
    Enrich only images for a product.

    Args:
        product_id: ID of the product to enrich

    Returns:
        Result dictionary
    """
    try:
        product = DiscoveredProduct.objects.get(id=product_id)
    except (DiscoveredProduct.DoesNotExist, ObjectDoesNotExist):
        return {
            "success": False,
            "error": f"Product {product_id} not found",
        }

    client = SerpAPIClient()
    enricher = ProductEnricher(client=client)

    result = enricher.enrich_product(
        product,
        enrich_prices=False,
        enrich_reviews=False,
        enrich_images=True,
        enrich_articles=False
    )

    return result
