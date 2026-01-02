"""
URL Frontier - Redis-based URL queue management.

Implements a priority queue for URLs to be crawled with:
- Priority-based ordering (lower score = higher priority)
- URL deduplication via seen URL tracking
- Domain-specific cookie caching
- Persistence across restarts via database fallback

Reference: ai_enhancement_engine/crawlers/url_frontier.py
"""

import json
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class URLFrontier:
    """
    Redis-based URL frontier with priority queue and database fallback.

    Uses sorted sets for priority ordering - lower score = higher priority
    (priority inversion: priority 10 becomes score 0, priority 1 becomes score 9).
    Maintains a separate set for URL deduplication.

    Database Fallback (Fix 4):
    After Redis restart, the seen URL sets are lost. To prevent re-crawling
    URLs that were already processed, we fall back to checking:
    1. CrawledSource table (URLs that were crawled)
    2. DiscoveredProduct.source_url (URLs that yielded products)

    When a URL is found in the database, we add it to Redis for future checks.
    """

    # Redis key patterns
    QUEUE_KEY_PATTERN = "crawler:frontier:{queue_id}"
    SEEN_KEY_PATTERN = "crawler:seen:{queue_id}"
    GLOBAL_SEEN_KEY = "crawler:seen:global"
    COOKIE_KEY_PATTERN = "crawler:cookies:{domain}"

    def __init__(self, redis_client=None):
        """
        Initialize URL frontier.

        Args:
            redis_client: Optional pre-configured Redis client
        """
        self._redis = redis_client

        if self._redis is None:
            self._init_redis()

        logger.info("URL Frontier initialized")

    def _init_redis(self):
        """Initialize Redis connection from settings."""
        import redis

        redis_url = getattr(settings, "REDIS_URL", None)
        if redis_url:
            self._redis = redis.from_url(redis_url, decode_responses=True)
        else:
            # Fall back to Celery broker URL
            broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/1")
            self._redis = redis.from_url(broker_url, decode_responses=True)

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for consistent comparison.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL (lowercase, stripped, no trailing slash)
        """
        return url.lower().strip().rstrip("/")

    def _check_crawled_source(self, url: str, url_hash: str, seen_key: str) -> bool:
        """
        Check if URL exists in CrawledSource table.

        If found, populates Redis seen sets for future checks.

        Args:
            url: URL to check
            url_hash: Pre-computed hash of the URL
            seen_key: Queue-specific seen key

        Returns:
            True if URL was found in CrawledSource
        """
        try:
            from crawler.models import CrawledSource

            # Check both exact URL and normalized version
            normalized = self._normalize_url(url)
            if CrawledSource.objects.filter(url=url).exists() or \
               CrawledSource.objects.filter(url=normalized).exists():
                # URL was crawled before - add to Redis for future checks
                self._redis.sadd(seen_key, url_hash)
                self._redis.sadd(self.GLOBAL_SEEN_KEY, url_hash)
                logger.debug(f"URL already in CrawledSource, skipping: {url[:50]}...")
                return True
        except Exception as e:
            logger.warning(f"CrawledSource check failed: {e}")

        return False

    def _check_discovered_product(self, url: str, url_hash: str, seen_key: str) -> bool:
        """
        Check if URL exists in DiscoveredProduct.source_url.

        If found, populates Redis seen sets for future checks.

        Args:
            url: URL to check
            url_hash: Pre-computed hash of the URL
            seen_key: Queue-specific seen key

        Returns:
            True if URL was found in DiscoveredProduct
        """
        try:
            from crawler.models import DiscoveredProduct

            # Check both exact URL and normalized version
            normalized = self._normalize_url(url)
            if DiscoveredProduct.objects.filter(source_url=url).exists() or \
               DiscoveredProduct.objects.filter(source_url=normalized).exists():
                # URL already used for a product - add to Redis for future checks
                self._redis.sadd(seen_key, url_hash)
                self._redis.sadd(self.GLOBAL_SEEN_KEY, url_hash)
                logger.debug(f"URL already in DiscoveredProduct, skipping: {url[:50]}...")
                return True
        except Exception as e:
            logger.warning(f"DiscoveredProduct check failed: {e}")

        return False

    def add_url(
        self,
        queue_id: str,
        url: str,
        priority: int = 5,
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add URL to frontier if not already seen.

        Checks in order (fast to slow):
        1. Redis seen set (fastest, may be stale after restart)
        2. CrawledSource table (persistent)
        3. DiscoveredProduct.source_url (persistent)

        Args:
            queue_id: Queue identifier (typically source slug)
            url: URL to add
            priority: Priority 1-10 (higher = more important)
            source_id: Optional source UUID
            metadata: Optional metadata dict

        Returns:
            True if URL was added, False if already seen
        """
        url_hash = self._hash_url(url)
        queue_key = self.QUEUE_KEY_PATTERN.format(queue_id=queue_id)
        seen_key = self.SEEN_KEY_PATTERN.format(queue_id=queue_id)

        # Check 1: Redis queue-specific seen set (fast, may be stale)
        if self._redis.sismember(seen_key, url_hash):
            return False

        # Check 2: Redis global seen set (fast, may be stale)
        if self._redis.sismember(self.GLOBAL_SEEN_KEY, url_hash):
            return False

        # Check 3: CrawledSource table (persistent)
        if self._check_crawled_source(url, url_hash, seen_key):
            return False

        # Check 4: DiscoveredProduct.source_url (persistent)
        if self._check_discovered_product(url, url_hash, seen_key):
            return False

        # Truly new URL - add to seen sets
        self._redis.sadd(seen_key, url_hash)
        self._redis.sadd(self.GLOBAL_SEEN_KEY, url_hash)

        # Create URL entry
        entry = {
            "url": url,
            "url_hash": url_hash,
            "source_id": source_id,
            "added_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        # Add to priority queue
        # Priority inversion: lower score = fetched first
        # Priority 10 (highest) -> score 0, Priority 1 -> score 9
        score = 10 - priority
        self._redis.zadd(queue_key, {json.dumps(entry): score})

        logger.debug(f"Added URL to frontier: {url[:80]}... (priority={priority})")
        return True

    def add_urls(
        self,
        queue_id: str,
        urls: List[str],
        priority: int = 5,
        source_id: Optional[str] = None,
    ) -> int:
        """
        Add multiple URLs to frontier.

        Args:
            queue_id: Queue identifier
            urls: List of URLs to add
            priority: Priority for all URLs
            source_id: Optional source UUID

        Returns:
            Number of URLs actually added (excluding duplicates)
        """
        added = 0
        for url in urls:
            if self.add_url(queue_id, url, priority, source_id):
                added += 1
        return added

    def get_next_url(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """
        Get highest priority URL from frontier.

        Args:
            queue_id: Queue identifier

        Returns:
            URL entry dict or None if queue is empty
        """
        queue_key = self.QUEUE_KEY_PATTERN.format(queue_id=queue_id)

        # Pop from sorted set (lowest score = highest priority)
        result = self._redis.zpopmin(queue_key, count=1)

        if result:
            entry_json, score = result[0]
            entry = json.loads(entry_json)
            logger.debug(f"Got URL from frontier: {entry['url'][:80]}...")
            return entry

        return None

    def peek_next_url(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """
        Peek at next URL without removing it.

        Args:
            queue_id: Queue identifier

        Returns:
            URL entry dict or None if queue is empty
        """
        queue_key = self.QUEUE_KEY_PATTERN.format(queue_id=queue_id)

        # Get first item without removing
        result = self._redis.zrange(queue_key, 0, 0)

        if result:
            return json.loads(result[0])

        return None

    def get_queue_size(self, queue_id: str) -> int:
        """
        Get current frontier size for a queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of URLs in queue
        """
        queue_key = self.QUEUE_KEY_PATTERN.format(queue_id=queue_id)
        return self._redis.zcard(queue_key)

    def is_empty(self, queue_id: str) -> bool:
        """
        Check if frontier queue is empty.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue is empty
        """
        return self.get_queue_size(queue_id) == 0

    def is_url_seen(self, queue_id: str, url: str) -> bool:
        """
        Check if URL has been seen.

        Checks both Redis and database for complete coverage.

        Args:
            queue_id: Queue identifier
            url: URL to check

        Returns:
            True if URL has been seen
        """
        url_hash = self._hash_url(url)
        seen_key = self.SEEN_KEY_PATTERN.format(queue_id=queue_id)

        # Check Redis first (fast)
        if self._redis.sismember(seen_key, url_hash):
            return True
        if self._redis.sismember(self.GLOBAL_SEEN_KEY, url_hash):
            return True

        # Check database (persistent)
        if self._check_crawled_source(url, url_hash, seen_key):
            return True
        if self._check_discovered_product(url, url_hash, seen_key):
            return True

        return False

    def mark_url_seen(self, queue_id: str, url: str):
        """
        Mark URL as seen without adding to queue.

        Args:
            queue_id: Queue identifier
            url: URL to mark
        """
        url_hash = self._hash_url(url)
        seen_key = self.SEEN_KEY_PATTERN.format(queue_id=queue_id)

        self._redis.sadd(seen_key, url_hash)
        self._redis.sadd(self.GLOBAL_SEEN_KEY, url_hash)

    def clear_queue(self, queue_id: str):
        """
        Clear all URLs from a queue.

        Args:
            queue_id: Queue identifier
        """
        queue_key = self.QUEUE_KEY_PATTERN.format(queue_id=queue_id)
        self._redis.delete(queue_key)
        logger.info(f"Cleared queue: {queue_id}")

    def clear_seen(self, queue_id: str):
        """
        Clear seen URL set for a queue.

        Args:
            queue_id: Queue identifier
        """
        seen_key = self.SEEN_KEY_PATTERN.format(queue_id=queue_id)
        self._redis.delete(seen_key)
        logger.info(f"Cleared seen set: {queue_id}")

    def reset_queue(self, queue_id: str):
        """
        Reset both queue and seen set for a source.

        Args:
            queue_id: Queue identifier
        """
        self.clear_queue(queue_id)
        self.clear_seen(queue_id)
        logger.info(f"Reset queue: {queue_id}")

    def get_seen_count(self, queue_id: str) -> int:
        """
        Get count of seen URLs for a queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of seen URLs
        """
        seen_key = self.SEEN_KEY_PATTERN.format(queue_id=queue_id)
        return self._redis.scard(seen_key)

    def get_global_seen_count(self) -> int:
        """
        Get count of all globally seen URLs.

        Returns:
            Number of globally seen URLs
        """
        return self._redis.scard(self.GLOBAL_SEEN_KEY)

    # Domain-specific cookie caching

    def set_domain_cookies(
        self,
        domain: str,
        cookies: Dict[str, str],
        ttl_seconds: int = 86400,
    ):
        """
        Cache cookies for a domain.

        Args:
            domain: Domain name
            cookies: Cookie dictionary
            ttl_seconds: Time-to-live in seconds (default 24 hours)
        """
        cookie_key = self.COOKIE_KEY_PATTERN.format(domain=domain)
        self._redis.setex(cookie_key, ttl_seconds, json.dumps(cookies))
        logger.debug(f"Cached cookies for domain: {domain}")

    def get_domain_cookies(self, domain: str) -> Optional[Dict[str, str]]:
        """
        Get cached cookies for a domain.

        Args:
            domain: Domain name

        Returns:
            Cookie dictionary or None if not cached
        """
        cookie_key = self.COOKIE_KEY_PATTERN.format(domain=domain)
        cached = self._redis.get(cookie_key)

        if cached:
            return json.loads(cached)

        return None

    def delete_domain_cookies(self, domain: str):
        """
        Delete cached cookies for a domain.

        Args:
            domain: Domain name
        """
        cookie_key = self.COOKIE_KEY_PATTERN.format(domain=domain)
        self._redis.delete(cookie_key)
        logger.debug(f"Deleted cookies for domain: {domain}")

    def _hash_url(self, url: str) -> str:
        """
        Compute SHA-256 hash of URL.

        Args:
            url: URL to hash

        Returns:
            Hex digest of URL hash
        """
        # Normalize URL before hashing
        normalized = self._normalize_url(url)
        return hashlib.sha256(normalized.encode()).hexdigest()


# Singleton instance for convenience
_frontier_instance: Optional[URLFrontier] = None


def get_url_frontier() -> URLFrontier:
    """
    Get the global URL Frontier instance.

    Returns:
        URLFrontier singleton instance
    """
    global _frontier_instance
    if _frontier_instance is None:
        _frontier_instance = URLFrontier()
    return _frontier_instance
