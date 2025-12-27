"""
Daily error rate monitoring for the crawler.

Task 9.4 Implementation:
- Calculates error rate per day (errors / total requests)
- Alert threshold: > 10% error rate
- Logs alert to Sentry

Usage:
    from crawler.monitoring import check_daily_error_rate

    # Check and alert if threshold exceeded
    rate_info = check_daily_error_rate()
    # Returns: {"error_rate": 0.05, "errors": 50, "total": 1000, "threshold_exceeded": False}
"""

import logging
from datetime import timedelta
from typing import Dict, Any, Optional

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default threshold for daily error rate (10%)
DEFAULT_ERROR_RATE_THRESHOLD = 0.10


def check_daily_error_rate(
    threshold: Optional[float] = None,
    source_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check the daily error rate and alert if threshold is exceeded.

    Calculates the ratio of failed requests to total requests for the
    current day. Triggers a Sentry alert if the rate exceeds the threshold.

    Args:
        threshold: Error rate threshold (default: 0.10 = 10%)
        source_id: Optionally limit to a specific source

    Returns:
        Dict with error rate metrics and threshold status
    """
    from .sentry_integration import capture_alert
    from crawler.models import CrawlJob, CrawlJobStatus, CrawlError

    if threshold is None:
        threshold = getattr(
            settings, "CRAWLER_ERROR_RATE_THRESHOLD", DEFAULT_ERROR_RATE_THRESHOLD
        )

    # Get start of current day
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Build query filters
    job_filters = Q(created_at__gte=today_start)
    error_filters = Q(timestamp__gte=today_start)

    if source_id:
        job_filters &= Q(source_id=source_id)
        error_filters &= Q(source_id=source_id)

    # Count total jobs
    total_jobs = CrawlJob.objects.filter(job_filters).count()

    # Count failed jobs
    failed_jobs = CrawlJob.objects.filter(
        job_filters,
        status=CrawlJobStatus.FAILED,
    ).count()

    # Count errors from CrawlError table
    total_errors = CrawlError.objects.filter(error_filters).count()

    # Calculate error rate
    if total_jobs == 0:
        error_rate = 0.0
    else:
        error_rate = failed_jobs / total_jobs

    # Check threshold
    threshold_exceeded = error_rate > threshold

    result = {
        "error_rate": round(error_rate, 4),
        "failed_jobs": failed_jobs,
        "total_jobs": total_jobs,
        "total_errors": total_errors,
        "threshold": threshold,
        "threshold_exceeded": threshold_exceeded,
        "date": today_start.date().isoformat(),
    }

    if source_id:
        result["source_id"] = source_id

    # Alert if threshold exceeded
    if threshold_exceeded:
        _alert_high_error_rate(result)

    logger.info(
        f"Daily error rate check: {error_rate:.2%} "
        f"({failed_jobs}/{total_jobs} jobs failed)"
    )

    return result


def _alert_high_error_rate(rate_info: Dict[str, Any]) -> None:
    """
    Send alert for high error rate.

    Args:
        rate_info: Dict with error rate metrics
    """
    from .sentry_integration import capture_alert

    error_rate = rate_info["error_rate"]
    threshold = rate_info["threshold"]
    source_id = rate_info.get("source_id")

    if source_id:
        message = (
            f"High error rate for source {source_id}: "
            f"{error_rate:.2%} (threshold: {threshold:.2%})"
        )
    else:
        message = (
            f"High daily error rate: {error_rate:.2%} "
            f"(threshold: {threshold:.2%})"
        )

    logger.warning(message)

    capture_alert(
        message=message,
        level="warning",
        source_id=source_id,
        extra_data={
            "error_rate": error_rate,
            "threshold": threshold,
            "failed_jobs": rate_info["failed_jobs"],
            "total_jobs": rate_info["total_jobs"],
            "total_errors": rate_info["total_errors"],
            "date": rate_info["date"],
        },
    )


def get_error_rate_by_source(
    days: int = 7,
) -> Dict[str, Dict[str, Any]]:
    """
    Get error rates broken down by source for the specified period.

    Args:
        days: Number of days to include

    Returns:
        Dict mapping source IDs to error rate metrics
    """
    from crawler.models import CrawlJob, CrawlJobStatus

    start_date = timezone.now() - timedelta(days=days)

    # Get job counts by source
    jobs_by_source = (
        CrawlJob.objects.filter(created_at__gte=start_date)
        .values("source_id")
        .annotate(
            total=Count("id"),
            failed=Count("id", filter=Q(status=CrawlJobStatus.FAILED)),
        )
    )

    results = {}
    for row in jobs_by_source:
        source_id = str(row["source_id"])
        total = row["total"]
        failed = row["failed"]

        error_rate = failed / total if total > 0 else 0.0

        results[source_id] = {
            "error_rate": round(error_rate, 4),
            "failed_jobs": failed,
            "total_jobs": total,
        }

    return results
