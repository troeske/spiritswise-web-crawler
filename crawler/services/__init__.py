"""
Services module for the Web Crawler.

Contains:
- ai_client: AI Enhancement Service API client
- config_service: Configuration and schema builder service (V2 Architecture)
- quality_gate_v2: V2 Quality Gate using database-backed configuration
- content_preprocessor: Content preprocessing for AI token cost reduction (V2 Architecture)
- content_processor: Content processing pipeline
- sitemap_parser: Sitemap parsing and URL discovery
- link_extractor: Link extraction, filtering, and categorization
- auto_queue_service: Auto-queue integration for link discovery
- strategy_detection: Crawl strategy auto-detection and escalation
- scrapingbee_client: ScrapingBee API client wrapper
- wayback: Wayback Machine integration service
"""

from crawler.services.ai_client import AIEnhancementClient, EnhancementResult
from crawler.services.config_service import ConfigService, get_config_service
from crawler.services.quality_gate_v2 import (
    QualityGateV2,
    QualityAssessment,
    ProductStatus,
    get_quality_gate_v2,
    reset_quality_gate_v2,
)
from crawler.services.content_preprocessor import (
    ContentPreprocessor,
    ContentType,
    PreprocessedContent,
    get_content_preprocessor,
    reset_content_preprocessor,
)
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
from crawler.services.strategy_detection import (
    ObstacleType,
    DetectedObstacle,
    detect_obstacles,
    StrategyEscalationService,
    EscalationResult,
)
from crawler.services.scrapingbee_client import (
    ScrapingBeeClient,
    ScrapingBeeMode,
    ScrapingBeeResponse,
)
from crawler.services.wayback import (
    save_to_wayback,
    mark_wayback_failed,
    cleanup_raw_content,
    get_pending_wayback_sources,
)

__all__ = [
    "AIEnhancementClient",
    "EnhancementResult",
    # Config service (V2 Architecture)
    "ConfigService",
    "get_config_service",
    # Quality Gate V2 (V2 Architecture)
    "QualityGateV2",
    "QualityAssessment",
    "ProductStatus",
    "get_quality_gate_v2",
    "reset_quality_gate_v2",
    # Content Preprocessor (V2 Architecture)
    "ContentPreprocessor",
    "ContentType",
    "PreprocessedContent",
    "get_content_preprocessor",
    "reset_content_preprocessor",
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
    # Strategy detection
    "ObstacleType",
    "DetectedObstacle",
    "detect_obstacles",
    "StrategyEscalationService",
    "EscalationResult",
    # ScrapingBee client
    "ScrapingBeeClient",
    "ScrapingBeeMode",
    "ScrapingBeeResponse",
    # Wayback Machine integration
    "save_to_wayback",
    "mark_wayback_failed",
    "cleanup_raw_content",
    "get_pending_wayback_sources",
]
