"""
Alert Handler for Structural Change Detection.

Routes alerts to Sentry when structural changes are detected on
award site pages. Supports different severity levels and alert types.

Usage:
    handler = StructureChangeAlertHandler({})

    # Handle health report
    if not report.is_healthy:
        handler.handle_health_report(report)

    # Handle fingerprint change
    if old_fp != new_fp:
        handler.handle_fingerprint_change("iwsc", old_fp, new_fp)

    # Handle low yield abort
    if monitor.should_alert():
        handler.handle_low_yield_abort(monitor)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Severity levels for structural change alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class StructureAlert:
    """
    Alert for structural changes on award sites.

    Attributes:
        source: Source name (e.g., 'iwsc', 'dwwa')
        severity: Alert severity level
        message: Human-readable alert message
        old_fingerprint: Previous fingerprint (if applicable)
        new_fingerprint: New fingerprint (if applicable)
        failed_selectors: List of failed CSS selectors
        extra_data: Additional context data
        timestamp: ISO timestamp of the alert
    """

    source: str
    severity: AlertSeverity
    message: str
    old_fingerprint: Optional[str] = None
    new_fingerprint: Optional[str] = None
    failed_selectors: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


class StructureChangeAlertHandler:
    """
    Handle and route structural change alerts.

    Routes alerts to Sentry and logs them locally. Supports different
    alert types:
    - Selector health failures (pre-crawl)
    - Fingerprint changes (structural)
    - Low yield aborts (runtime)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the alert handler.

        Args:
            config: Configuration dict (for future use with thresholds, etc.)
        """
        self.config = config
        self._sent_alerts: List[StructureAlert] = []

    def handle_health_report(self, report) -> None:
        """
        Handle a collector health report.

        Sends alerts if the report indicates unhealthy status.

        Args:
            report: CollectorHealthReport from SelectorHealthChecker
        """
        if report.is_healthy:
            logger.debug(f"Health report for {report.source} is healthy, no alert")
            return

        # Create alert
        alert = StructureAlert(
            source=report.source,
            severity=AlertSeverity.CRITICAL if len(report.failed_selectors) > 1 else AlertSeverity.WARNING,
            message=(
                f"Selector health check failed for {report.source}. "
                f"{len(report.failed_selectors)} of {report.selectors_tested} selectors failed. "
                f"Failed: {', '.join(report.failed_selectors)}"
            ),
            failed_selectors=report.failed_selectors,
            extra_data={
                "sample_url": report.sample_url,
                "selectors_tested": report.selectors_tested,
                "selectors_healthy": report.selectors_healthy,
                "check_timestamp": report.timestamp,
            },
        )

        self._send_alert(alert)

    def handle_fingerprint_change(
        self, source: str, old_fingerprint: str, new_fingerprint: str
    ) -> None:
        """
        Handle a structural fingerprint change.

        Args:
            source: Source name
            old_fingerprint: Previous fingerprint hash
            new_fingerprint: New fingerprint hash
        """
        alert = StructureAlert(
            source=source,
            severity=AlertSeverity.CRITICAL,
            message=(
                f"Structural change detected on {source}. "
                f"Page fingerprint changed from {old_fingerprint[:8]}... to {new_fingerprint[:8]}... "
                f"Collectors may need updating."
            ),
            old_fingerprint=old_fingerprint,
            new_fingerprint=new_fingerprint,
        )

        self._send_alert(alert)

    def handle_low_yield_abort(self, monitor) -> None:
        """
        Handle a low yield abort from YieldMonitor.

        Args:
            monitor: YieldMonitor that triggered the abort
        """
        summary = monitor.get_summary()

        alert = StructureAlert(
            source=monitor.source,
            severity=AlertSeverity.WARNING,
            message=(
                f"Crawl aborted for {monitor.source} due to low yield. "
                f"Processed {summary['pages_processed']} pages, "
                f"collected {summary['total_items']} items "
                f"(avg {summary['avg_per_page']} per page). "
                f"{monitor.consecutive_low_pages} consecutive low-yield pages."
            ),
            extra_data={
                "pages_processed": summary["pages_processed"],
                "total_items": summary["total_items"],
                "avg_per_page": summary["avg_per_page"],
                "consecutive_low_pages": monitor.consecutive_low_pages,
                "threshold": monitor.consecutive_low_threshold,
                "alerts": monitor.alerts,
                "recent_pages": monitor.get_recent_history(5),
            },
        )

        self._send_alert(alert)

    def _send_alert(self, alert: StructureAlert) -> None:
        """
        Send an alert to all configured channels.

        Args:
            alert: StructureAlert to send
        """
        self._sent_alerts.append(alert)

        # Log locally
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.ERROR,
        }.get(alert.severity, logging.WARNING)

        logger.log(log_level, f"Structure alert [{alert.source}]: {alert.message}")

        # Send to Sentry
        self._send_sentry(alert)

    def _send_sentry(self, alert: StructureAlert) -> None:
        """
        Send alert to Sentry.

        Args:
            alert: StructureAlert to send
        """
        try:
            from crawler.monitoring.sentry_integration import capture_alert

            # Map severity to Sentry level
            sentry_level = {
                AlertSeverity.INFO: "info",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.CRITICAL: "error",
            }.get(alert.severity, "warning")

            # Prepare extra data
            extra_data = {
                "severity": alert.severity.value,
                "timestamp": alert.timestamp,
                **alert.extra_data,
            }

            if alert.old_fingerprint:
                extra_data["old_fingerprint"] = alert.old_fingerprint
            if alert.new_fingerprint:
                extra_data["new_fingerprint"] = alert.new_fingerprint
            if alert.failed_selectors:
                extra_data["failed_selectors"] = alert.failed_selectors

            capture_alert(
                message=alert.message,
                level=sentry_level,
                source_name=alert.source,
                extra_data=extra_data,
            )

        except ImportError:
            logger.warning("Sentry integration not available, alert logged locally only")
        except Exception as e:
            logger.error(f"Failed to send alert to Sentry: {e}")

    def get_sent_alerts(self) -> List[StructureAlert]:
        """
        Get list of alerts sent by this handler.

        Returns:
            List of StructureAlert objects
        """
        return list(self._sent_alerts)

    def clear_sent_alerts(self) -> None:
        """Clear the list of sent alerts."""
        self._sent_alerts = []
