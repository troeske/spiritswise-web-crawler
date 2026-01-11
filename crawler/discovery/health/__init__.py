"""
Health Monitoring for Award Site Crawlers.

This module provides structural change detection and health monitoring
for award site crawlers. It helps detect when site structures change
and need collector/parser updates.

Components:
- SelectorHealthChecker: Pre-crawl CSS selector validation
- YieldMonitor: Runtime yield tracking and abort detection
- StructuralFingerprint: DOM structure hashing for change detection
- StructureChangeAlertHandler: Alert routing to Sentry

Usage:
    from crawler.discovery.health import (
        SelectorHealthChecker,
        YieldMonitor,
        StructuralFingerprint,
        StructureChangeAlertHandler,
    )

    # Pre-crawl health check
    checker = SelectorHealthChecker()
    report = checker.check_source("iwsc", 2024)
    if not report.is_healthy:
        handler.handle_health_report(report)

    # Runtime yield monitoring
    monitor = YieldMonitor(source="iwsc")
    for page in pages:
        if not monitor.record_page(items_found, page.url):
            break  # Abort crawl

    # Structure change detection
    fingerprint = StructuralFingerprint.compute("iwsc", html)
    stored = StructuralFingerprint.get_stored("iwsc")
    if stored and not StructuralFingerprint.compare(fingerprint, stored):
        handler.handle_fingerprint_change("iwsc", stored, fingerprint)
"""

from .selector_health import SelectorHealthChecker, CollectorHealthReport, SelectorHealth
from .yield_monitor import YieldMonitor
from .fingerprint import StructuralFingerprint
from .alerts import StructureChangeAlertHandler, StructureAlert, AlertSeverity

__all__ = [
    # Selector health checking
    "SelectorHealthChecker",
    "CollectorHealthReport",
    "SelectorHealth",
    # Yield monitoring
    "YieldMonitor",
    # Structural fingerprinting
    "StructuralFingerprint",
    # Alert handling
    "StructureChangeAlertHandler",
    "StructureAlert",
    "AlertSeverity",
]
