"""
Selector Health Checker for Award Site Crawlers.

Pre-crawl validation that CSS selectors still match expected elements
on award site listing pages. Detects structural changes before they
cause crawl failures.

Usage:
    checker = SelectorHealthChecker()
    report = checker.check_source("iwsc", 2024)
    if not report.is_healthy:
        # Alert and potentially skip crawl
        print(f"Failed selectors: {report.failed_selectors}")
"""

from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SelectorHealth:
    """Health status for a single CSS selector."""

    selector: str
    found_count: int
    expected_min: int
    healthy: bool
    description: str = ""


@dataclass
class CollectorHealthReport:
    """
    Health report for a collector's selectors.

    Attributes:
        source: Source name (e.g., 'iwsc', 'dwwa')
        sample_url: URL that was tested
        selectors_tested: Number of selectors checked
        selectors_healthy: Number of selectors that passed
        is_healthy: Overall health status (True if >50% pass)
        failed_selectors: List of selector strings that failed
        timestamp: ISO timestamp of the check
    """

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

    Validates that expected CSS selectors still match elements on
    award site listing pages. This helps detect structural changes
    before they cause crawl failures or missed data.

    Health is determined by checking if >50% of expected selectors
    find at least their minimum expected number of matches.
    """

    # Source selector configurations
    # Each source has a sample URL template and selector definitions
    SOURCE_SELECTORS: Dict[str, Dict] = {
        "iwsc": {
            "sample_url": "https://www.iwsc.net/results/{year}?category=wine&style=fortified",
            "selectors": {
                ".c-card--listing": {
                    "min": 10,
                    "desc": "Product listing cards",
                },
                "a[href*='/results/detail/']": {
                    "min": 10,
                    "desc": "Detail page links",
                },
            },
        },
        "dwwa": {
            "sample_url": "https://awards.decanter.com/DWWA/{year}/search/wines",
            "selectors": {
                "[data-wine-id]": {
                    "min": 10,
                    "desc": "Wine cards with data attribute",
                },
                "a[href*='/wines/']": {
                    "min": 10,
                    "desc": "Wine detail links",
                },
                ".wine-card": {
                    "min": 5,
                    "desc": "Wine card containers",
                },
            },
        },
        "sfwsc": {
            "sample_url": "https://www.sfwsc.com/results/{year}",
            "selectors": {
                ".result-item": {
                    "min": 10,
                    "desc": "Result item containers",
                },
                "a[href*='/spirit/']": {
                    "min": 5,
                    "desc": "Spirit detail links",
                },
            },
        },
        "wwa": {
            "sample_url": "https://www.worldwhiskiesawards.com/{year}/winners",
            "selectors": {
                ".winner-card": {
                    "min": 5,
                    "desc": "Winner card containers",
                },
                "a[href*='/whisky/']": {
                    "min": 5,
                    "desc": "Whisky detail links",
                },
            },
        },
    }

    # HTTP request settings
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; SpiritwiseBot/1.0; +https://spiritswise.com/bot)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = None, headers: Dict[str, str] = None):
        """
        Initialize the selector health checker.

        Args:
            timeout: HTTP request timeout in seconds
            headers: Optional custom HTTP headers
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.headers = headers or self.DEFAULT_HEADERS

    def check_source(self, source: str, year: int) -> CollectorHealthReport:
        """
        Check if a source's selectors still work.

        Fetches a sample listing page and validates that expected CSS
        selectors find at least their minimum number of matches.

        Args:
            source: Source name (case-insensitive), e.g., 'iwsc', 'dwwa'
            year: Competition year to test

        Returns:
            CollectorHealthReport with health status and details

        Raises:
            ValueError: If source is not recognized
        """
        source_lower = source.lower()

        if source_lower not in self.SOURCE_SELECTORS:
            available = list(self.SOURCE_SELECTORS.keys())
            raise ValueError(
                f"Unknown source: {source}. Available sources: {available}"
            )

        config = self.SOURCE_SELECTORS[source_lower]
        sample_url = config["sample_url"].format(year=year)
        selectors = config["selectors"]

        # Fetch the sample page
        try:
            html = self._fetch_page(sample_url)
        except Exception as e:
            logger.error(f"Failed to fetch {sample_url}: {e}")
            # Return unhealthy report on fetch failure
            return CollectorHealthReport(
                source=source_lower,
                sample_url=sample_url,
                selectors_tested=len(selectors),
                selectors_healthy=0,
                is_healthy=False,
                failed_selectors=list(selectors.keys()),
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

        # Check each selector
        selector_results = []
        for selector, meta in selectors.items():
            result = self._check_selector(html, selector, meta["min"], meta["desc"])
            selector_results.append(result)

        # Determine overall health
        healthy_count = sum(1 for r in selector_results if r.healthy)
        total_count = len(selector_results)
        failed = [r.selector for r in selector_results if not r.healthy]

        # Healthy if >50% of selectors pass
        is_healthy = healthy_count > (total_count / 2)

        return CollectorHealthReport(
            source=source_lower,
            sample_url=sample_url,
            selectors_tested=total_count,
            selectors_healthy=healthy_count,
            is_healthy=is_healthy,
            failed_selectors=failed,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def _fetch_page(self, url: str) -> str:
        """
        Fetch HTML content from a URL.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string

        Raises:
            httpx.HTTPError: On HTTP errors
        """
        response = httpx.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text

    def _check_selector(
        self, html: str, selector: str, expected_min: int, description: str
    ) -> SelectorHealth:
        """
        Check if a CSS selector finds expected matches.

        Args:
            html: HTML content to check
            selector: CSS selector string
            expected_min: Minimum expected number of matches
            description: Human-readable description

        Returns:
            SelectorHealth with match count and health status
        """
        soup = BeautifulSoup(html, "html.parser")

        try:
            matches = soup.select(selector)
            found_count = len(matches)
        except Exception as e:
            logger.warning(f"Selector error for '{selector}': {e}")
            found_count = 0

        healthy = found_count >= expected_min

        if not healthy:
            logger.warning(
                f"Selector '{selector}' ({description}) found {found_count} "
                f"matches, expected at least {expected_min}"
            )

        return SelectorHealth(
            selector=selector,
            found_count=found_count,
            expected_min=expected_min,
            healthy=healthy,
            description=description,
        )

    def check_all_sources(self, year: int) -> Dict[str, CollectorHealthReport]:
        """
        Check health of all configured sources.

        Args:
            year: Competition year to test

        Returns:
            Dict mapping source names to their health reports
        """
        reports = {}
        for source in self.SOURCE_SELECTORS:
            try:
                reports[source] = self.check_source(source, year)
            except Exception as e:
                logger.error(f"Failed to check source {source}: {e}")
                reports[source] = CollectorHealthReport(
                    source=source,
                    sample_url="error",
                    selectors_tested=0,
                    selectors_healthy=0,
                    is_healthy=False,
                    failed_selectors=[],
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
        return reports
