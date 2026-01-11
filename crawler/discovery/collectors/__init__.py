"""
URL Collectors for Award Sites.

This module contains collectors that extract detail page URLs from award site
listing pages. Unlike parsers that extract data directly, collectors only
gather URLs for later AI extraction.

Collectors:
- IWSCCollector: Collects detail URLs from IWSC (iwsc.net)
- DWWACollector: Collects detail URLs from DWWA (awards.decanter.com) - Uses Playwright
- SFWSCCollector: Collects product entries from SFWSC (thetastingalliance.com)
- WWACollector: Collects detail URLs from WWA (worldwhiskiesawards.com)
"""

from .base_collector import AwardDetailURL, BaseCollector, get_collector
from .iwsc_collector import IWSCCollector
from .dwwa_collector import DWWACollector
from .sfwsc_collector import SFWSCCollector
from .wwa_collector import WWACollector

__all__ = [
    "AwardDetailURL",
    "BaseCollector",
    "IWSCCollector",
    "DWWACollector",
    "SFWSCCollector",
    "WWACollector",
    "get_collector",
]
