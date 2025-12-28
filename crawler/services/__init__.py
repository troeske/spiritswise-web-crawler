"""
Services module for the Web Crawler.

Contains:
- ai_client: AI Enhancement Service API client
- content_processor: Content processing pipeline
- sitemap_parser: Sitemap parsing and URL discovery
- link_extractor: Link extraction, filtering, and categorization
- auto_queue_service: Auto-queue integration for link discovery
"""

from crawler.services.ai_client import AIEnhancementClient, EnhancementResult
from crawler.services.content_processor import ContentProcessor
from crawler.services.sitemap_parser import (
    SitemapParser,
    SitemapURL,
    SitemapResult,
    SitemapParseError,
    get_sitemap_parser,
)
from crawler.services.link_extractor import (
    LinkExtractor,
    ExtractedLink,
    get_link_extractor,
)
from crawler.services.auto_queue_service import (
    AutoQueueService,
    AutoQueueResult,
    get_auto_queue_service,
)

__all__ = [
    "AIEnhancementClient",
    "EnhancementResult",
    "ContentProcessor",
    "SitemapParser",
    "SitemapURL",
    "SitemapResult",
    "SitemapParseError",
    "get_sitemap_parser",
    "LinkExtractor",
    "ExtractedLink",
    "get_link_extractor",
    "AutoQueueService",
    "AutoQueueResult",
    "get_auto_queue_service",
]
