"""
Auto-Queue Service.

Integrates link extraction with URL frontier for automatic link discovery
and queueing during crawl operations.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class AutoQueueResult:
    """Result of auto-queue processing."""

    total_links_found: int = 0
    product_links: int = 0
    queued_links: int = 0
    filtered_links: int = 0
    duplicate_links: int = 0
    links_by_type: Dict[str, int] = field(default_factory=dict)


class LinkExtractorProtocol(Protocol):
    """Protocol for link extractor dependency."""

    def extract_links(
        self,
        html: str,
        base_url: str,
        product_patterns: Optional[List[str]] = None,
    ) -> List[Any]: ...


class URLFrontierProtocol(Protocol):
    """Protocol for URL frontier dependency."""

    def add_url(
        self,
        queue_id: str,
        url: str,
        priority: int = 5,
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool: ...

    def is_url_seen(self, queue_id: str, url: str) -> bool: ...

    def get_queue_size(self, queue_id: str) -> int: ...

    def get_seen_count(self, queue_id: str) -> int: ...


class AutoQueueService:
    """
    Service for automatic link discovery and queueing.

    Integrates LinkExtractor and URLFrontier to automatically
    discover and queue links from crawled pages.
    """

    PRIORITY_PRODUCT = 8
    PRIORITY_CATEGORY = 6
    PRIORITY_PAGINATION = 5
    PRIORITY_RELATED = 9
    PRIORITY_EXTERNAL = 3
    PRIORITY_DEFAULT = 5

    def __init__(
        self,
        link_extractor: LinkExtractorProtocol,
        frontier: URLFrontierProtocol,
    ):
        self.link_extractor = link_extractor
        self.frontier = frontier

    async def process_crawled_page(
        self,
        url: str,
        html: str,
        source: Any,
        current_depth: int = 0,
    ) -> AutoQueueResult:
        result = AutoQueueResult()

        auto_discover = getattr(source, 'auto_discover_links', True)
        if not auto_discover:
            logger.debug(f'Auto-discovery disabled for source {source.slug}')
            return result

        max_depth = getattr(source, 'max_crawl_depth', 3)
        if current_depth >= max_depth:
            logger.debug(f'Depth limit reached ({current_depth}/{max_depth}) for {source.slug}')
            result.filtered_links = 1
            return result

        product_patterns = getattr(source, 'product_url_patterns', []) or []
        links = self.link_extractor.extract_links(
            html=html,
            base_url=url,
            product_patterns=product_patterns,
        )

        result.total_links_found = len(links)

        for link in links:
            link_type = getattr(link, 'link_type', 'unknown')
            result.links_by_type[link_type] = result.links_by_type.get(link_type, 0) + 1
            if getattr(link, 'is_product', False):
                result.product_links += 1

        max_pages = getattr(source, 'max_pages', 100)
        current_queue_size = self.frontier.get_seen_count(source.slug)
        remaining_capacity = max(0, max_pages - current_queue_size)

        queued_count = 0
        for link in links:
            if queued_count >= remaining_capacity:
                result.filtered_links += len(links) - queued_count
                break

            if not self.should_queue_link(link, source):
                result.filtered_links += 1
                continue

            if self.frontier.is_url_seen(source.slug, link.url):
                result.duplicate_links += 1
                continue

            priority = self.calculate_priority(link, source)

            added = self.frontier.add_url(
                queue_id=source.slug,
                url=link.url,
                priority=priority,
                source_id=str(source.id),
                metadata={
                    'link_type': getattr(link, 'link_type', 'unknown'),
                    'depth': current_depth + 1,
                    'parent_url': url,
                },
            )

            if added:
                queued_count += 1

        result.queued_links = queued_count
        logger.info(
            f'Auto-queue for {url}: found={result.total_links_found}, '
            f'queued={result.queued_links}, duplicates={result.duplicate_links}'
        )

        return result

    async def queue_discovered_links(
        self,
        links: List[Any],
        source: Any,
        crawl_job: Any,
    ) -> int:
        queued_count = 0

        for link in links:
            if not getattr(link, 'is_internal', True):
                continue

            priority = self.calculate_priority(link, source)

            added = self.frontier.add_url(
                queue_id=source.slug,
                url=link.url,
                priority=priority,
                source_id=str(source.id),
                metadata={
                    'crawl_job_id': str(crawl_job.id),
                    'link_type': getattr(link, 'link_type', 'unknown'),
                },
            )

            if added:
                queued_count += 1

        return queued_count

    def calculate_priority(self, link: Any, source: Any) -> int:
        link_type = getattr(link, 'link_type', 'unknown')
        is_internal = getattr(link, 'is_internal', True)

        if not is_internal:
            return self.PRIORITY_EXTERNAL

        if link_type == 'related':
            return self.PRIORITY_RELATED

        if link_type == 'product' or getattr(link, 'is_product', False):
            return self.PRIORITY_PRODUCT

        if link_type == 'category' or getattr(link, 'is_category', False):
            return self.PRIORITY_CATEGORY

        if link_type == 'pagination' or getattr(link, 'is_pagination', False):
            return self.PRIORITY_PAGINATION

        return self.PRIORITY_DEFAULT

    def should_queue_link(self, link: Any, source: Any) -> bool:
        url = getattr(link, 'url', '')
        is_internal = getattr(link, 'is_internal', True)

        if is_internal:
            return True

        product_patterns = getattr(source, 'product_url_patterns', []) or []
        for pattern in product_patterns:
            try:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            except re.error:
                logger.warning(f'Invalid regex pattern: {pattern}')

        return False


def get_auto_queue_service() -> AutoQueueService:
    from crawler.queue.url_frontier import get_url_frontier
    from crawler.services.link_extractor import get_link_extractor

    return AutoQueueService(
        link_extractor=get_link_extractor(),
        frontier=get_url_frontier(),
    )
