"""
Yield Monitor for Award Site Crawlers.

Runtime monitoring of item yield during crawls. Detects when pages
consistently return fewer items than expected, which may indicate:
- Structural changes on the site
- Pagination issues
- Anti-bot measures being triggered

Usage:
    monitor = YieldMonitor(source="iwsc")
    for page_url in pages_to_crawl:
        items = crawl_page(page_url)
        if not monitor.record_page(len(items), page_url):
            # Abort crawl - too many low-yield pages
            break

    print(monitor.get_summary())
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class YieldMonitor:
    """
    Monitor item yield during crawls and detect problems.

    Tracks items collected per page and aborts crawl after too many
    consecutive low-yield pages. This helps detect structural changes
    or anti-bot measures during runtime.

    Attributes:
        source: Source name being monitored (e.g., 'iwsc')
        expected_min_per_page: Minimum items expected per page
        expected_avg_per_page: Expected average items per page
        consecutive_low_threshold: Number of low pages before abort

    Usage:
        monitor = YieldMonitor(source="iwsc")
        for page in pages:
            if not monitor.record_page(items_found, page.url):
                break  # Abort
        summary = monitor.get_summary()
    """

    source: str
    expected_min_per_page: int = 10
    expected_avg_per_page: int = 25
    consecutive_low_threshold: int = 3

    # Tracking state
    pages_processed: int = 0
    total_items_collected: int = 0
    consecutive_low_pages: int = 0
    alerts: List[str] = field(default_factory=list)
    page_history: List[Dict[str, Any]] = field(default_factory=list)

    # Timestamps
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_page_at: str = None

    def record_page(self, items_collected: int, page_url: str) -> bool:
        """
        Record results from a crawled page.

        Tracks items collected and updates consecutive low-yield counter.
        Returns False if crawl should abort.

        Args:
            items_collected: Number of items found on the page
            page_url: URL of the page (for logging)

        Returns:
            True if crawl should continue, False if should abort
        """
        self.pages_processed += 1
        self.total_items_collected += items_collected
        self.last_page_at = datetime.utcnow().isoformat() + "Z"

        # Track page history
        self.page_history.append({
            "url": page_url,
            "items": items_collected,
            "timestamp": self.last_page_at,
        })

        # Check if page yield is below threshold
        if items_collected < self.expected_min_per_page:
            self.consecutive_low_pages += 1
            logger.warning(
                f"[{self.source}] Low yield on page {self.pages_processed}: "
                f"{items_collected} items (expected >= {self.expected_min_per_page}). "
                f"Consecutive low: {self.consecutive_low_pages}/{self.consecutive_low_threshold}"
            )

            # Check if we should abort
            if self.consecutive_low_pages >= self.consecutive_low_threshold:
                alert_msg = (
                    f"Aborting {self.source} crawl after {self.consecutive_low_pages} "
                    f"consecutive low-yield pages. Last URL: {page_url}"
                )
                self.alerts.append(alert_msg)
                logger.error(alert_msg)
                return False  # Abort crawling
        else:
            # Reset counter on healthy page
            if self.consecutive_low_pages > 0:
                logger.info(
                    f"[{self.source}] Healthy yield reset after {items_collected} items. "
                    f"Previous consecutive low: {self.consecutive_low_pages}"
                )
            self.consecutive_low_pages = 0

        return True  # Continue crawling

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for the monitored crawl.

        Returns:
            Dictionary with crawl statistics including:
            - source: Source name
            - pages_processed: Total pages crawled
            - total_items: Total items collected
            - avg_per_page: Average items per page
            - consecutive_low_pages: Current consecutive low count
            - alerts: List of alert messages
            - health_status: 'healthy', 'warning', or 'critical'
        """
        avg = (
            self.total_items_collected / self.pages_processed
            if self.pages_processed > 0
            else 0.0
        )

        # Determine health status
        if self.consecutive_low_pages >= self.consecutive_low_threshold:
            health_status = "critical"
        elif self.consecutive_low_pages > 0 or avg < self.expected_min_per_page:
            health_status = "warning"
        else:
            health_status = "healthy"

        return {
            "source": self.source,
            "pages_processed": self.pages_processed,
            "total_items": self.total_items_collected,
            "avg_per_page": round(avg, 1),
            "consecutive_low_pages": self.consecutive_low_pages,
            "alerts": self.alerts,
            "health_status": health_status,
            "started_at": self.started_at,
            "last_page_at": self.last_page_at,
        }

    def get_recent_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent page history entries.

        Args:
            n: Number of recent entries to return

        Returns:
            List of recent page records (url, items, timestamp)
        """
        return self.page_history[-n:]

    def should_alert(self) -> bool:
        """
        Check if current state warrants an alert.

        Returns:
            True if should send alert (critical state or has alerts)
        """
        return (
            self.consecutive_low_pages >= self.consecutive_low_threshold
            or len(self.alerts) > 0
        )

    def reset(self) -> None:
        """Reset the monitor state for a new crawl."""
        self.pages_processed = 0
        self.total_items_collected = 0
        self.consecutive_low_pages = 0
        self.alerts = []
        self.page_history = []
        self.started_at = datetime.utcnow().isoformat() + "Z"
        self.last_page_at = None
