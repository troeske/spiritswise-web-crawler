"""
Multi-tiered content fetching system.

Provides tiered fetching capabilities:
- Tier 1: httpx + cookies (fastest, lowest cost)
- Tier 2: Playwright headless browser (for JavaScript and age gates)
- Tier 3: ScrapingBee proxy service (for blocked sites)

The Smart Router orchestrates tier selection and escalation.
"""

from .age_gate import (
    AgeGateDetectionResult,
    detect_age_gate,
    AGE_GATE_KEYWORDS,
)
from .tier1_httpx import Tier1HttpxFetcher
from .tier2_playwright import Tier2PlaywrightFetcher
from .tier3_scrapingbee import Tier3ScrapingBeeFetcher
from .smart_router import SmartRouter, FetchResult

__all__ = [
    "AgeGateDetectionResult",
    "detect_age_gate",
    "AGE_GATE_KEYWORDS",
    "Tier1HttpxFetcher",
    "Tier2PlaywrightFetcher",
    "Tier3ScrapingBeeFetcher",
    "SmartRouter",
    "FetchResult",
]
