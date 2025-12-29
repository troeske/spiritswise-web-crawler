"""
Search Scheduler - Schedule generic searches within rate limits.

Phase 3: Generic Search Discovery

Manages search scheduling to:
- Respect SerpAPI rate limits
- Avoid repeating searches too frequently
- Distribute searches across categories
"""

import hashlib
from datetime import datetime
from typing import List

from django.core.cache import cache

from crawler.discovery.serpapi.rate_limiter import RateLimiter


class SearchScheduler:
    """
    Schedule generic searches within rate limits.

    Uses cache to track recently executed queries and avoid repeats.
    Integrates with RateLimiter to stay within API quota.

    Usage:
        rate_limiter = RateLimiter()
        scheduler = SearchScheduler(rate_limiter)

        if scheduler.can_execute_search():
            queries = scheduler.get_next_queries("whiskey", count=5)
            for query in queries:
                # Execute search
                scheduler.mark_executed(query)
    """

    def __init__(self, rate_limiter: RateLimiter):
        """
        Initialize search scheduler.

        Args:
            rate_limiter: RateLimiter instance for quota checking
        """
        self.rate_limiter = rate_limiter
        self.cache_prefix = "search_scheduler"

    def get_next_queries(
        self,
        product_type: str,
        count: int = 5,
    ) -> List[str]:
        """
        Get next queries to execute for a product type.

        Returns queries that haven't been executed recently.

        Args:
            product_type: "whiskey" or "port_wine"
            count: Maximum number of queries to return

        Returns:
            List of query strings ready for execution
        """
        from .config import SearchConfig

        config = SearchConfig()
        all_queries = config.get_queries_for_type(product_type)

        # Filter out recently executed queries
        available = []
        for query in all_queries:
            if not self._was_recently_executed(query):
                available.append(query)

            if len(available) >= count:
                break

        return available

    def mark_executed(self, query: str) -> None:
        """
        Mark a query as executed.

        Sets cache entry to prevent repeat execution for 24 hours.

        Args:
            query: Query string that was executed
        """
        key = self._query_key(query)
        # Don't repeat for 24 hours
        cache.set(key, datetime.now().isoformat(), 86400)

    def can_execute_search(self) -> bool:
        """
        Check if we can execute another search.

        Delegates to rate limiter.

        Returns:
            True if under daily limit
        """
        return self.rate_limiter.can_make_request()

    def get_daily_budget_remaining(self) -> int:
        """
        Get remaining daily search budget.

        Returns:
            Number of searches remaining today
        """
        return self.rate_limiter.get_remaining_daily()

    def _was_recently_executed(self, query: str) -> bool:
        """
        Check if query was recently executed.

        Args:
            query: Query string to check

        Returns:
            True if query is in cache (executed within 24 hours)
        """
        key = self._query_key(query)
        return cache.get(key) is not None

    def _query_key(self, query: str) -> str:
        """
        Generate cache key for query.

        Uses MD5 hash of query to create consistent key.

        Args:
            query: Query string

        Returns:
            Cache key string
        """
        query_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        return f"{self.cache_prefix}:query:{query_hash}"
