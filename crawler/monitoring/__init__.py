"""
Monitoring and alerting module for the web crawler.

Task Group 9 Implementation:
- Sentry error tracking with crawl context
- Consecutive failure tracking via Redis
- Daily error rate monitoring
- Detailed error context logging

Thresholds (configurable):
- Consecutive failures: 5 per source
- Daily error rate: 10%
"""

from .sentry_integration import capture_crawl_error, add_crawl_breadcrumb
from .failure_tracker import FailureTracker, get_failure_tracker
from .error_logger import create_crawl_error_record, log_error_with_context
from .error_rate_monitor import check_daily_error_rate

__all__ = [
    "capture_crawl_error",
    "add_crawl_breadcrumb",
    "FailureTracker",
    "get_failure_tracker",
    "create_crawl_error_record",
    "log_error_with_context",
    "check_daily_error_rate",
]
