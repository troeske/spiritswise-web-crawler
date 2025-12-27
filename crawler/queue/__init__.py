"""
URL Queue Management - Redis-based URL frontier and queue management.

Provides priority-based URL queuing with deduplication for the web crawler.
"""

from .url_frontier import URLFrontier

__all__ = [
    "URLFrontier",
]
