"""
Detailed error context logging for crawl failures.

Task 9.5 Implementation:
- Logs: URL, source, tier_used, response_status, headers
- Creates CrawlError record for every failure
- Includes stack trace for exceptions

Usage:
    from crawler.monitoring import create_crawl_error_record, log_error_with_context

    # Create a database record
    error_record = create_crawl_error_record(
        source=source,
        url=url,
        error_type="blocked",
        message="Request blocked",
        tier_used=2,
        response_status=403,
    )

    # Full logging with Sentry integration
    log_error_with_context(
        error=exception,
        source=source,
        url=url,
        tier_used=2,
    )
"""

import logging
import traceback
from typing import Dict, Any, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


def create_crawl_error_record(
    source,
    url: str,
    error_type: str,
    message: str,
    tier_used: Optional[int] = None,
    response_status: Optional[int] = None,
    response_headers: Optional[Dict[str, str]] = None,
    stack_trace: Optional[str] = None,
):
    """
    Create a CrawlError record in the database.

    Provides persistent storage for crawl failures with full context
    for debugging and analysis.

    Args:
        source: CrawlerSource instance
        url: URL that caused the error
        error_type: Category of error (from ErrorType choices)
        message: Error message
        tier_used: Fetching tier used (1, 2, or 3)
        response_status: HTTP response status code
        response_headers: HTTP response headers
        stack_trace: Full stack trace if available

    Returns:
        CrawlError instance
    """
    from crawler.models import CrawlError, ErrorType

    # Validate error_type against choices
    valid_error_types = [choice[0] for choice in ErrorType.choices]
    if error_type not in valid_error_types:
        # Map common error names to valid choices
        error_type_mapping = {
            "blocked": ErrorType.BLOCKED,
            "timeout": ErrorType.TIMEOUT,
            "connection": ErrorType.CONNECTION,
            "age_gate": ErrorType.AGE_GATE,
            "rate_limit": ErrorType.RATE_LIMIT,
            "parse": ErrorType.PARSE,
            "api": ErrorType.API,
        }
        error_type = error_type_mapping.get(error_type, ErrorType.UNKNOWN)

    try:
        error_record = CrawlError.objects.create(
            source=source,
            url=url,
            error_type=error_type,
            message=message,
            tier_used=tier_used,
            response_status=response_status,
            response_headers=response_headers or {},
            stack_trace=stack_trace or "",
            timestamp=timezone.now(),
            resolved=False,
        )

        logger.debug(
            f"Created CrawlError record {error_record.id} for {url}: {error_type}"
        )

        return error_record

    except Exception as e:
        logger.error(f"Failed to create CrawlError record: {e}")
        return None


def log_error_with_context(
    error: Exception,
    source=None,
    url: Optional[str] = None,
    tier_used: Optional[int] = None,
    response_status: Optional[int] = None,
    response_headers: Optional[Dict[str, str]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """
    Log an error with full context to database and Sentry.

    Combines database logging (CrawlError) with Sentry error capture
    for comprehensive error tracking.

    Args:
        error: The exception that occurred
        source: CrawlerSource instance
        url: URL where error occurred
        tier_used: Fetching tier used (1, 2, or 3)
        response_status: HTTP response status code
        response_headers: HTTP response headers
        extra_context: Additional context for Sentry

    Returns:
        CrawlError instance if database record was created
    """
    from .sentry_integration import capture_crawl_error
    from crawler.models import ErrorType

    # Determine error type from exception
    error_type = _classify_error(error, response_status)

    # Get full stack trace
    stack_trace = traceback.format_exc()

    # Create database record
    error_record = None
    if url:
        error_record = create_crawl_error_record(
            source=source,
            url=url,
            error_type=error_type,
            message=str(error),
            tier_used=tier_used,
            response_status=response_status,
            response_headers=response_headers,
            stack_trace=stack_trace,
        )

    # Capture to Sentry
    capture_crawl_error(
        error=error,
        source=source,
        url=url,
        tier=tier_used,
        extra_context={
            "response_status": response_status,
            "error_type": error_type,
            **(extra_context or {}),
        },
    )

    return error_record


def _classify_error(
    error: Exception,
    response_status: Optional[int] = None,
) -> str:
    """
    Classify an error into an ErrorType category.

    Args:
        error: The exception that occurred
        response_status: HTTP response status code

    Returns:
        ErrorType choice value
    """
    from crawler.models import ErrorType

    error_class = type(error).__name__.lower()
    error_message = str(error).lower()

    # Check response status codes
    if response_status:
        if response_status == 403:
            return ErrorType.BLOCKED
        if response_status == 429:
            return ErrorType.RATE_LIMIT

    # Check exception types
    if "timeout" in error_class or "timeout" in error_message:
        return ErrorType.TIMEOUT

    if any(
        term in error_class
        for term in ["connection", "socket", "network", "dns"]
    ):
        return ErrorType.CONNECTION

    if "age" in error_message and "gate" in error_message:
        return ErrorType.AGE_GATE

    if any(term in error_class for term in ["parse", "json", "decode"]):
        return ErrorType.PARSE

    if "api" in error_message or "api" in error_class:
        return ErrorType.API

    return ErrorType.UNKNOWN
