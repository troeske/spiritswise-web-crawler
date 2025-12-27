"""
Sentry error tracking integration for the web crawler.

Task 9.2 Implementation:
- Configures Sentry SDK (already done in settings/base.py)
- Adds breadcrumbs for crawl context (source, URL, tier)
- Filters sensitive data (cookies, API keys)
- Captures exceptions with proper context

Usage:
    from crawler.monitoring import capture_crawl_error, add_crawl_breadcrumb

    try:
        result = await fetch_url(url)
    except Exception as e:
        capture_crawl_error(
            error=e,
            source=source,
            url=url,
            tier=tier_used,
        )
"""

import logging
from typing import Dict, Any, Optional

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None

logger = logging.getLogger(__name__)

# Sensitive fields to filter from Sentry events
SENSITIVE_FIELDS = {
    "cookies",
    "cookie",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "auth",
    "password",
    "secret",
    "token",
    "x-api-key",
}


def _filter_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter sensitive data from a dictionary.

    Replaces values for keys that match sensitive field names.

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dictionary with sensitive values replaced
    """
    if not isinstance(data, dict):
        return data

    filtered = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if this is a sensitive field
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            filtered[key] = "[Filtered]"
        elif isinstance(value, dict):
            # Recursively filter nested dicts
            filtered[key] = _filter_sensitive_data(value)
        else:
            filtered[key] = value

    return filtered


def add_crawl_breadcrumb(
    source_name: str,
    url: str,
    tier: int,
    message: str = "Crawl operation",
    level: str = "info",
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Add a breadcrumb to Sentry for crawl context.

    Breadcrumbs help trace the sequence of operations leading to an error.

    Args:
        source_name: Name of the CrawlerSource
        url: URL being crawled
        tier: Fetching tier used (1, 2, or 3)
        message: Description of the operation
        level: Log level (info, warning, error)
        extra_data: Additional context data
    """
    if not SENTRY_AVAILABLE or sentry_sdk is None:
        logger.debug(f"Sentry not available, skipping breadcrumb: {message}")
        return

    breadcrumb_data = {
        "source": source_name,
        "url": url,
        "tier": tier,
    }

    # Add extra data if provided (filter sensitive fields)
    if extra_data:
        filtered_extra = _filter_sensitive_data(extra_data)
        breadcrumb_data.update(filtered_extra)

    try:
        sentry_sdk.add_breadcrumb(
            category="crawl",
            message=message,
            level=level,
            data=breadcrumb_data,
        )
    except Exception as e:
        logger.warning(f"Failed to add Sentry breadcrumb: {e}")


def capture_crawl_error(
    error: Exception,
    source=None,
    url: Optional[str] = None,
    tier: Optional[int] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Capture a crawl error to Sentry with full context.

    Adds breadcrumb for the error context and captures the exception.

    Args:
        error: The exception that occurred
        source: CrawlerSource instance (optional)
        url: URL where error occurred
        tier: Fetching tier used (1, 2, or 3)
        extra_context: Additional context (will be filtered for sensitive data)
    """
    if not SENTRY_AVAILABLE or sentry_sdk is None:
        logger.warning(f"Sentry not available, logging error locally: {error}")
        return

    source_name = source.name if source else "Unknown"
    source_id = str(source.id) if source else None

    # Add breadcrumb with error context
    add_crawl_breadcrumb(
        source_name=source_name,
        url=url or "Unknown",
        tier=tier or 0,
        message=f"Error: {type(error).__name__}",
        level="error",
        extra_data=_filter_sensitive_data(extra_context or {}),
    )

    # Set Sentry scope with crawl context
    try:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("crawler.source", source_name)
            scope.set_tag("crawler.tier", tier or 0)

            if source_id:
                scope.set_extra("source_id", source_id)
            if url:
                scope.set_extra("crawl_url", url)
            if extra_context:
                filtered = _filter_sensitive_data(extra_context)
                scope.set_extra("crawl_context", filtered)

            sentry_sdk.capture_exception(error)

    except Exception as e:
        logger.warning(f"Failed to capture exception to Sentry: {e}")


def capture_alert(
    message: str,
    level: str = "warning",
    source_id: Optional[str] = None,
    source_name: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Capture an alert message to Sentry.

    Used for threshold breaches and monitoring alerts.

    Args:
        message: Alert message
        level: Severity level (warning, error)
        source_id: CrawlerSource ID
        source_name: CrawlerSource name
        extra_data: Additional alert data
    """
    if not SENTRY_AVAILABLE or sentry_sdk is None:
        logger.warning(f"Sentry not available, logging alert locally: {message}")
        return

    try:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("alert.type", "threshold_breach")

            if source_name:
                scope.set_tag("crawler.source", source_name)
            if source_id:
                scope.set_extra("source_id", source_id)
            if extra_data:
                filtered = _filter_sensitive_data(extra_data)
                scope.set_extra("alert_data", filtered)

            sentry_sdk.capture_message(message, level=level)

    except Exception as e:
        logger.warning(f"Failed to capture alert to Sentry: {e}")
