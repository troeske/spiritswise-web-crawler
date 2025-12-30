"""
Crawler API views.

Includes health check endpoint for monitoring and load balancer checks.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from crawler.models import CrawlerMetrics


def get_redis_connection():
    """
    Get Redis connection for health check.

    Returns:
        Redis client if available, None if not configured.
    """
    try:
        import django_redis
        from django.core.cache import cache

        # Check if cache is configured with Redis
        if hasattr(cache, "client"):
            return cache.client.get_client()
        return None
    except (ImportError, Exception):
        return None


def get_celery_worker_count():
    """
    Get the count of active Celery workers.

    Returns:
        int: Number of active workers, 0 if Celery not available.
    """
    try:
        from config.celery import app as celery_app

        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            return len(active)
        return 0
    except Exception:
        return 0


def health_check(request):
    """
    Health check endpoint for the crawler service.

    Returns comprehensive system status information for monitoring
    and load balancer health checks.

    Endpoint: GET /api/health/
    No authentication required (for load balancer checks).

    Response fields:
        - status: "healthy" or "unhealthy"
        - database: "connected" or "error"
        - redis: "connected", "not_configured", or "error"
        - celery_workers: integer count of active workers
        - queue_depth: current queue depth (from latest metrics)
        - last_crawl: ISO timestamp of last crawl activity
        - crawl_success_rate_24h: crawl success rate percentage
        - extraction_success_rate_24h: extraction success rate percentage

    Returns:
        JsonResponse: JSON response with system status
        HTTP 200 for healthy, HTTP 503 for unhealthy
    """
    status = "healthy"
    http_status = 200

    # Check database connection
    database_status = "connected"
    try:
        connection.ensure_connection()
    except Exception:
        database_status = "error"
        status = "unhealthy"
        http_status = 503

    # Check Redis connection (graceful degradation)
    redis_status = "not_configured"
    try:
        redis_client = get_redis_connection()
        if redis_client is not None:
            if redis_client.ping():
                redis_status = "connected"
            else:
                redis_status = "error"
    except Exception:
        redis_status = "not_configured"

    # Check Celery workers (graceful degradation)
    celery_workers = 0
    try:
        celery_workers = get_celery_worker_count()
    except Exception:
        celery_workers = 0

    # Get metrics from last 24 hours
    queue_depth = 0
    last_crawl = None
    crawl_success_rate_24h = None
    extraction_success_rate_24h = None

    try:
        # Get the most recent metrics record
        today = date.today()
        yesterday = today - timedelta(days=1)

        latest_metrics = CrawlerMetrics.objects.filter(
            date__gte=yesterday
        ).order_by("-date").first()

        if latest_metrics:
            queue_depth = latest_metrics.queue_depth or 0
            last_crawl = str(latest_metrics.date)

            if latest_metrics.crawl_success_rate is not None:
                crawl_success_rate_24h = float(latest_metrics.crawl_success_rate)

            if latest_metrics.extraction_success_rate is not None:
                extraction_success_rate_24h = float(latest_metrics.extraction_success_rate)
    except Exception:
        # If metrics retrieval fails, continue with null values
        pass

    response_data = {
        "status": status,
        "database": database_status,
        "redis": redis_status,
        "celery_workers": celery_workers,
        "queue_depth": queue_depth,
        "last_crawl": last_crawl,
        "crawl_success_rate_24h": crawl_success_rate_24h,
        "extraction_success_rate_24h": extraction_success_rate_24h,
    }

    return JsonResponse(response_data, status=http_status)
