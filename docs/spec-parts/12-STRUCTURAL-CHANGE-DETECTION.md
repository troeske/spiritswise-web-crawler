# Section 12: Structural Change Detection for Award Sites

> **Source:** Extracted from `FLOW_COMPARISON_ANALYSIS.md`, lines 2385-3046

---

## 12. Structural Change Detection for Award Sites

Award sites periodically redesign their HTML structure. Without detection, collectors silently fail, returning zero results or malformed data. This section defines mechanisms to detect structural changes early.

### 12.1 Multi-Layer Detection Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURAL CHANGE DETECTION LAYERS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: SELECTOR HEALTH CHECK (Pre-crawl)                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Before each crawl run:                                               │   │
│  │  • Fetch a known sample page                                          │   │
│  │  • Test all CSS selectors used by collector                           │   │
│  │  • If >50% selectors fail → ABORT + ALERT                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 2: YIELD MONITORING (During crawl)                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Track results per listing page:                                      │   │
│  │  • Expected: 20-50 products per page                                  │   │
│  │  • If page yields <5 products when >20 expected → FLAG                │   │
│  │  • If 3 consecutive pages yield <10% expected → ABORT + ALERT         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 3: SCHEMA VALIDATION (Post-extraction)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Validate each extracted AwardDetailURL:                              │   │
│  │  • detail_url matches expected pattern (regex)                        │   │
│  │  • medal_hint is valid enum value                                     │   │
│  │  • If >30% of items fail validation → ALERT                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           ▼                                                  │
│  Layer 4: KNOWN PRODUCT VERIFICATION (Periodic)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Weekly: Re-extract 3-5 known products per source                     │   │
│  │  • Compare extracted data with stored "ground truth"                  │   │
│  │  • If extraction differs significantly → INVESTIGATE                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Selector Health Check Implementation

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import httpx
import logging

logger = logging.getLogger(__name__)


@dataclass
class SelectorHealth:
    """Result of testing a CSS selector."""
    selector: str
    found_count: int
    expected_min: int
    healthy: bool


@dataclass
class CollectorHealthReport:
    """Health report for a collector's selectors."""
    source: str
    sample_url: str
    selectors_tested: int
    selectors_healthy: int
    is_healthy: bool
    failed_selectors: List[str]
    timestamp: str


class SelectorHealthChecker:
    """
    Pre-crawl health check for collector CSS selectors.
    Run before each scheduled crawl to detect site changes.
    """

    # Define expected selectors for each source
    # These are the CSS selectors each collector relies on
    SOURCE_SELECTORS = {
        "iwsc": {
            "sample_url": "https://www.iwsc.net/results/{year}?category=wine&style=fortified",
            "selectors": {
                ".c-card--listing": {"min": 10, "desc": "Product cards"},
                "a[href*='/results/detail/']": {"min": 10, "desc": "Detail page links"},
                ".c-card--listing img[src*='medal']": {"min": 5, "desc": "Medal images"},
            }
        },
        "dwwa": {
            "sample_url": "https://awards.decanter.com/DWWA/{year}",
            "selectors": {
                "[data-wine-id]": {"min": 10, "desc": "Wine cards"},
                "a[href*='/wines/']": {"min": 10, "desc": "Detail page links"},
                ".medal-badge, .award-level": {"min": 5, "desc": "Medal indicators"},
            }
        },
        "sfwsc": {
            "sample_url": "https://sfwsc.com/winners/{year}/",
            "selectors": {
                ".winner-entry, .product-card": {"min": 10, "desc": "Winner entries"},
                ".medal-type, .award-medal": {"min": 5, "desc": "Medal types"},
            }
        }
    }

    async def check_source(self, source: str, year: int) -> CollectorHealthReport:
        """
        Check if a source's selectors still work.
        Run BEFORE each crawl job.
        """
        if source not in self.SOURCE_SELECTORS:
            raise ValueError(f"Unknown source: {source}")

        config = self.SOURCE_SELECTORS[source]
        sample_url = config["sample_url"].format(year=year)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(sample_url, timeout=30)
                response.raise_for_status()
                html = response.text
        except Exception as e:
            logger.error(f"Failed to fetch sample page for {source}: {e}")
            return CollectorHealthReport(
                source=source,
                sample_url=sample_url,
                selectors_tested=0,
                selectors_healthy=0,
                is_healthy=False,
                failed_selectors=["FETCH_FAILED"],
                timestamp=datetime.now().isoformat()
            )

        soup = BeautifulSoup(html, "lxml")
        results = []
        failed = []

        for selector, spec in config["selectors"].items():
            found = soup.select(selector)
            healthy = len(found) >= spec["min"]

            if not healthy:
                failed.append(f"{selector} (found {len(found)}, expected {spec['min']}+)")
                logger.warning(
                    f"Selector health check FAILED for {source}: "
                    f"{selector} found {len(found)}, expected {spec['min']}+ "
                    f"({spec['desc']})"
                )

            results.append(SelectorHealth(
                selector=selector,
                found_count=len(found),
                expected_min=spec["min"],
                healthy=healthy
            ))

        healthy_count = sum(1 for r in results if r.healthy)
        # Consider healthy if >50% selectors work
        is_healthy = (healthy_count / len(results)) > 0.5 if results else False

        return CollectorHealthReport(
            source=source,
            sample_url=sample_url,
            selectors_tested=len(results),
            selectors_healthy=healthy_count,
            is_healthy=is_healthy,
            failed_selectors=failed,
            timestamp=datetime.now().isoformat()
        )
```

### 12.3 Yield Monitoring Implementation

```python
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class YieldMonitor:
    """
    Monitors yield (results per page) during a crawl.
    Detects abnormal drops that indicate structural changes.
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

    def record_page(self, items_collected: int, page_url: str) -> bool:
        """
        Record results from a page. Returns False if crawl should abort.
        """
        self.pages_processed += 1
        self.total_items_collected += items_collected

        # Check for abnormally low yield
        if items_collected < self.expected_min_per_page:
            self.consecutive_low_pages += 1

            if items_collected == 0:
                alert = f"ZERO YIELD on page {page_url}"
                self.alerts.append(alert)
                logger.error(alert)
            else:
                alert = f"LOW YIELD: {items_collected} items on {page_url} (expected {self.expected_min_per_page}+)"
                self.alerts.append(alert)
                logger.warning(alert)

            # Abort if too many consecutive low-yield pages
            if self.consecutive_low_pages >= self.consecutive_low_threshold:
                abort_msg = (
                    f"ABORTING {self.source} crawl: "
                    f"{self.consecutive_low_pages} consecutive pages with low yield. "
                    f"Site structure may have changed."
                )
                self.alerts.append(abort_msg)
                logger.critical(abort_msg)
                return False  # Signal to abort
        else:
            # Reset counter on healthy page
            self.consecutive_low_pages = 0

        return True  # Continue crawling

    def get_summary(self) -> dict:
        """Get yield monitoring summary."""
        avg_yield = (
            self.total_items_collected / self.pages_processed
            if self.pages_processed > 0 else 0
        )
        return {
            "source": self.source,
            "pages_processed": self.pages_processed,
            "total_items": self.total_items_collected,
            "avg_per_page": round(avg_yield, 1),
            "expected_avg": self.expected_avg_per_page,
            "yield_health": "HEALTHY" if avg_yield >= self.expected_min_per_page else "DEGRADED",
            "alerts": self.alerts,
        }
```

### 12.4 Known Product Verification (Ground Truth)

```python
from dataclasses import dataclass
from typing import Dict, Any, List
import json

@dataclass
class KnownProduct:
    """A product with known correct extraction for verification."""
    source: str
    detail_url: str
    expected_data: Dict[str, Any]  # Ground truth


# Store 3-5 known products per source for periodic verification
KNOWN_PRODUCTS = {
    "iwsc": [
        KnownProduct(
            source="iwsc",
            detail_url="https://www.iwsc.net/results/detail/157656/10-yo-tawny-nv",
            expected_data={
                "name_contains": "10 Year",
                "medal": "Gold",
                "has_tasting_notes": True,
                "product_type": "port_wine",
            }
        ),
        # Add more known products...
    ],
    "dwwa": [
        KnownProduct(
            source="dwwa",
            detail_url="https://awards.decanter.com/DWWA/2025/wines/768949",
            expected_data={
                "name_contains": "Galpin Peak",
                "medal_in": ["Gold", "Silver", "Bronze", "Platinum"],
                "has_tasting_notes": True,
                "origin_country": "South Africa",
            }
        ),
        # Add more known products...
    ],
}


class KnownProductVerifier:
    """
    Periodically verify extraction on known products.
    Run weekly via scheduled task.
    """

    def __init__(self, ai_extractor):
        self.ai_extractor = ai_extractor

    async def verify_source(self, source: str) -> Dict[str, Any]:
        """Verify all known products for a source."""
        if source not in KNOWN_PRODUCTS:
            return {"error": f"No known products for {source}"}

        results = []
        for known in KNOWN_PRODUCTS[source]:
            result = await self._verify_single(known)
            results.append(result)

        passed = sum(1 for r in results if r["passed"])
        return {
            "source": source,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "health": "HEALTHY" if passed == len(results) else "DEGRADED",
            "details": results,
        }

    async def _verify_single(self, known: KnownProduct) -> Dict[str, Any]:
        """Verify extraction for a single known product."""
        try:
            # Extract using current implementation
            extracted = await self.ai_extractor.extract_from_url(known.detail_url)

            # Compare with expected
            checks = []
            for key, expected in known.expected_data.items():
                if key == "name_contains":
                    actual = extracted.get("name", "")
                    passed = expected.lower() in actual.lower()
                    checks.append({"check": key, "passed": passed})
                elif key == "medal_in":
                    actual = extracted.get("medal", "")
                    passed = actual in expected
                    checks.append({"check": key, "passed": passed})
                elif key == "has_tasting_notes":
                    has_notes = bool(
                        extracted.get("palate_description") or
                        extracted.get("nose_description") or
                        extracted.get("finish_description")
                    )
                    passed = has_notes == expected
                    checks.append({"check": key, "passed": passed})
                elif key.startswith("origin_"):
                    field = key.replace("origin_", "")
                    actual = extracted.get(field, "")
                    passed = expected.lower() in actual.lower()
                    checks.append({"check": key, "passed": passed})

            all_passed = all(c["passed"] for c in checks)
            return {
                "url": known.detail_url,
                "passed": all_passed,
                "checks": checks,
            }
        except Exception as e:
            return {
                "url": known.detail_url,
                "passed": False,
                "error": str(e),
            }
```

### 12.5 Structural Fingerprinting

```python
import hashlib
from bs4 import BeautifulSoup


class StructuralFingerprint:
    """
    Create a fingerprint of key structural elements.
    Changes in fingerprint indicate structural changes.
    """

    # Elements that define site structure (not content)
    STRUCTURE_ELEMENTS = {
        "iwsc": [
            "div.c-card--listing",
            "div.results-grid",
            "nav.pagination",
            "form.filter-form",
        ],
        "dwwa": [
            "div[data-wine-id]",
            "div.results-container",
            "div.filter-panel",
            "nav.pagination",
        ],
    }

    @classmethod
    def compute(cls, source: str, html: str) -> str:
        """
        Compute structural fingerprint for a page.
        Returns hash of structural element presence/hierarchy.
        """
        soup = BeautifulSoup(html, "lxml")
        elements = cls.STRUCTURE_ELEMENTS.get(source, [])

        structure = []
        for selector in elements:
            found = soup.select(selector)
            # Record: selector, count, first element's classes/attrs
            if found:
                first = found[0]
                attrs = sorted(first.attrs.keys())
                structure.append(f"{selector}:{len(found)}:{attrs}")
            else:
                structure.append(f"{selector}:0:[]")

        fingerprint_str = "|".join(structure)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()

    @classmethod
    def compare(cls, old_fingerprint: str, new_fingerprint: str) -> bool:
        """
        Compare fingerprints. Returns True if they match (no structural change).
        """
        return old_fingerprint == new_fingerprint


# Store and compare fingerprints
class FingerPrintStore:
    """Store fingerprints in database for comparison."""

    def store(self, source: str, fingerprint: str, url: str):
        """Store a new fingerprint."""
        from crawler.models import SourceFingerprint
        SourceFingerprint.objects.update_or_create(
            source=source,
            defaults={
                "fingerprint": fingerprint,
                "sample_url": url,
                "updated_at": timezone.now(),
            }
        )

    def check_changed(self, source: str, new_fingerprint: str) -> bool:
        """Check if fingerprint has changed. Returns True if changed."""
        from crawler.models import SourceFingerprint
        try:
            stored = SourceFingerprint.objects.get(source=source)
            return stored.fingerprint != new_fingerprint
        except SourceFingerprint.DoesNotExist:
            return False  # First time, no comparison possible
```

### 12.6 Alerting Integration

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class StructureAlert:
    """Alert for structural change detection."""
    source: str
    severity: AlertSeverity
    message: str
    details: Optional[dict] = None


class StructureChangeAlertHandler:
    """
    Handle structural change alerts.
    Integrates with Sentry, email, and Slack.
    """

    def __init__(self, config):
        self.config = config

    def send_alert(self, alert: StructureAlert):
        """Send alert through configured channels."""
        if alert.severity == AlertSeverity.CRITICAL:
            self._send_sentry(alert)
            self._send_slack(alert)
            self._send_email(alert)
        elif alert.severity == AlertSeverity.WARNING:
            self._send_sentry(alert)
            self._send_slack(alert)
        else:
            self._send_sentry(alert)

    def _send_sentry(self, alert: StructureAlert):
        """Send to Sentry."""
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("source", alert.source)
            scope.set_tag("severity", alert.severity.value)
            scope.set_extra("details", alert.details)
            if alert.severity == AlertSeverity.CRITICAL:
                sentry_sdk.capture_message(alert.message, level="error")
            else:
                sentry_sdk.capture_message(alert.message, level="warning")

    def _send_slack(self, alert: StructureAlert):
        """Send to Slack webhook."""
        import httpx
        webhook_url = self.config.get("slack_webhook")
        if not webhook_url:
            return

        color = {
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.INFO: "#17a2b8",
        }[alert.severity]

        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert.severity.value.upper()}] {alert.source} Structure Change",
                "text": alert.message,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in (alert.details or {}).items()
                ],
            }]
        }
        httpx.post(webhook_url, json=payload)

    def _send_email(self, alert: StructureAlert):
        """Send email for critical alerts."""
        from django.core.mail import send_mail
        send_mail(
            subject=f"[CRITICAL] {alert.source} Structure Change Detected",
            message=f"{alert.message}\n\nDetails: {alert.details}",
            from_email=self.config.get("from_email"),
            recipient_list=self.config.get("alert_emails", []),
        )
```

### 12.7 Scheduled Health Checks

```python
# Add to Celery beat schedule
CELERY_BEAT_SCHEDULE = {
    # Run selector health check before each scheduled crawl
    "pre-crawl-health-check-iwsc": {
        "task": "crawler.tasks.check_source_health",
        "schedule": crontab(hour=5, minute=45),  # 15 min before IWSC crawl
        "args": ["iwsc"],
    },
    "pre-crawl-health-check-dwwa": {
        "task": "crawler.tasks.check_source_health",
        "schedule": crontab(hour=5, minute=45, day_of_week="monday"),
        "args": ["dwwa"],
    },

    # Weekly known product verification
    "weekly-known-product-verification": {
        "task": "crawler.tasks.verify_known_products",
        "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),
    },
}


# Celery task implementation
@shared_task
def check_source_health(source: str) -> dict:
    """
    Run pre-crawl health check for a source.
    Aborts scheduled crawl if health check fails.
    """
    from crawler.discovery.health import SelectorHealthChecker, StructureChangeAlertHandler

    checker = SelectorHealthChecker()
    year = datetime.now().year

    report = asyncio.run(checker.check_source(source, year))

    if not report.is_healthy:
        # Send alert
        alert_handler = StructureChangeAlertHandler(settings.ALERT_CONFIG)
        alert_handler.send_alert(StructureAlert(
            source=source,
            severity=AlertSeverity.CRITICAL,
            message=f"Pre-crawl health check FAILED for {source}. Crawl aborted.",
            details={
                "failed_selectors": report.failed_selectors,
                "healthy_ratio": f"{report.selectors_healthy}/{report.selectors_tested}",
            }
        ))

        # Cancel the scheduled crawl task
        revoke_scheduled_crawl(source)

        return {"status": "UNHEALTHY", "crawl_cancelled": True, "report": report}

    return {"status": "HEALTHY", "report": report}
```

### 12.8 Database Model for Tracking

```python
# Add to crawler/models.py

class SourceHealthCheck(models.Model):
    """Track health check results for each source."""
    source = models.CharField(max_length=50)
    check_type = models.CharField(
        max_length=20,
        choices=[
            ("selector", "Selector Health"),
            ("yield", "Yield Monitoring"),
            ("fingerprint", "Structural Fingerprint"),
            ("known_product", "Known Product Verification"),
        ]
    )
    is_healthy = models.BooleanField()
    details = models.JSONField(default=dict)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "source_health_check"
        indexes = [
            models.Index(fields=["source", "check_type"]),
            models.Index(fields=["checked_at"]),
        ]


class SourceFingerprint(models.Model):
    """Store structural fingerprints for change detection."""
    source = models.CharField(max_length=50, unique=True)
    fingerprint = models.CharField(max_length=64)  # MD5 hash
    sample_url = models.URLField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "source_fingerprint"
```

---
