"""
Services module for the Web Crawler.

Contains:
- ai_client_v2: AI Service V2 extraction client with content preprocessing
- config_service: Configuration and schema builder service (V2 Architecture)
- quality_gate_v2: V2 Quality Gate using database-backed configuration
- enrichment_orchestrator_v2: Progressive multi-source enrichment (V2 Architecture Phase 4)
- enrichment_pipeline_v3: 2-step enrichment pipeline for generic search (V3 Architecture)
- content_preprocessor: Content preprocessing for AI token cost reduction (V2 Architecture)
- source_tracker: Source tracking and field provenance (V2 Architecture Phase 4.5)
- wayback_service: Wayback Machine integration with retry (V2 Architecture Phase 4.6)
- content_processor: Content processing pipeline
- sitemap_parser: Sitemap parsing and URL discovery
- link_extractor: Link extraction, filtering, and categorization
- auto_queue_service: Auto-queue integration for link discovery
- strategy_detection: Crawl strategy auto-detection and escalation
- scrapingbee_client: ScrapingBee API client wrapper
- wayback: Wayback Machine integration service
- confidence_merger: Confidence-based data merging (V3 Architecture)
- product_match_validator: Product match validation to prevent cross-contamination (V3 Architecture)
- duplicate_detector: URL/content/product deduplication (V3 Architecture Task 2.3)
- product_pipeline: Unified product pipeline with V3 source tracking (Task 2.2.6)

V1->V2 Migration: V1 ai_client removed. Use ai_client_v2 (AIClientV2) instead.
AIEnhancementClient and EnhancementResult are now aliases to V2 classes for backward compatibility.
"""

# V1->V2 Migration: Import V2 components with backward-compatible aliases
from crawler.services.ai_client_v2 import (
    AIClientV2,
    AIClientError,
    SchemaConfigurationError,  # Raised when schema cannot be loaded from DB
    EnhancementResult,  # V1-compatible result class for backward compatibility
    ExtractedProductV2,
    ExtractionResultV2,
    get_ai_client_v2,
    reset_ai_client_v2,
)
# Backward-compatible aliases for V1 names
AIEnhancementClient = AIClientV2
get_ai_client = get_ai_client_v2
from crawler.services.config_service import ConfigService, get_config_service
from crawler.services.quality_gate_v2 import (
    QualityGateV2,
    QualityAssessment,
    ProductStatus,
    get_quality_gate_v2,
    reset_quality_gate_v2,
)
from crawler.services.enrichment_orchestrator_v2 import (
    EnrichmentOrchestratorV2,
    EnrichmentResult as EnrichmentResultV2,
    EnrichmentSession,
    get_enrichment_orchestrator_v2,
    reset_enrichment_orchestrator_v2,
)
from crawler.services.enrichment_pipeline_v3 import (
    EnrichmentPipelineV3,
    EnrichmentResultV3,
    EnrichmentSessionV3,
    get_enrichment_pipeline_v3,
    reset_enrichment_pipeline_v3,
)
from crawler.services.content_preprocessor import (
    ContentPreprocessor,
    ContentType,
    PreprocessedContent,
    get_content_preprocessor,
    reset_content_preprocessor,
)
from crawler.services.content_processor import ContentProcessor
from crawler.services.source_tracker import SourceTracker
from crawler.services.wayback_service import WaybackService
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
from crawler.services.confidence_merger import (
    ConfidenceBasedMerger,
    get_confidence_merger,
    reset_confidence_merger,
)
from crawler.services.product_match_validator import (
    ProductMatchValidator,
    get_product_match_validator,
    reset_product_match_validator,
)
from crawler.services.duplicate_detector import (
    DuplicateDetector,
    get_duplicate_detector,
    reset_duplicate_detector,
)

from crawler.services.product_pipeline import (
    UnifiedProductPipeline,
    PipelineResult,
    SourceTrackingData,
    create_source_tracking_from_enrichment_result,
    update_product_source_tracking,
)

__all__ = [
    # AI Client (V2 with V1-compatible aliases)
    "AIEnhancementClient",  # Alias for AIClientV2 (backward compatibility)
    "EnhancementResult",    # V1-compatible result class
    "get_ai_client",        # Alias for get_ai_client_v2 (backward compatibility)
    # AI Client V2 (V2 Architecture)
    "AIClientV2",
    "AIClientError",
    "SchemaConfigurationError",
    "ExtractedProductV2",
    "ExtractionResultV2",
    "get_ai_client_v2",
    "reset_ai_client_v2",
    # Config service (V2 Architecture)
    "ConfigService",
    "get_config_service",
    # Quality Gate V2 (V2 Architecture)
    "QualityGateV2",
    "QualityAssessment",
    "ProductStatus",
    "get_quality_gate_v2",
    "reset_quality_gate_v2",
    # Enrichment Orchestrator V2 (V2 Architecture Phase 4)
    "EnrichmentOrchestratorV2",
    "EnrichmentResultV2",
    "EnrichmentSession",
    "get_enrichment_orchestrator_v2",
    "reset_enrichment_orchestrator_v2",
    # Enrichment Pipeline V3 - 2-Step Pipeline for Generic Search (V3 Architecture)
    "EnrichmentPipelineV3",
    "EnrichmentResultV3",
    "EnrichmentSessionV3",
    "get_enrichment_pipeline_v3",
    "reset_enrichment_pipeline_v3",
    # Content Preprocessor (V2 Architecture)
    "ContentPreprocessor",
    "ContentType",
    "PreprocessedContent",
    "get_content_preprocessor",
    "reset_content_preprocessor",
    # Source Tracker (V2 Architecture Phase 4.5)
    "SourceTracker",
    # Wayback Service (V2 Architecture Phase 4.6)
    "WaybackService",
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
    # Confidence-Based Merger (V3 Architecture)
    "ConfidenceBasedMerger",
    "get_confidence_merger",
    "reset_confidence_merger",
    # Product Match Validator (V3 Architecture)
    "ProductMatchValidator",
    "get_product_match_validator",
    "reset_product_match_validator",
    # Duplicate Detector (V3 Architecture Task 2.3)
    "DuplicateDetector",
    "get_duplicate_detector",
    "reset_duplicate_detector",

    # Product Pipeline with V3 Source Tracking (Task 2.2.6)
    "UnifiedProductPipeline",
    "PipelineResult",
    "SourceTrackingData",
    "create_source_tracking_from_enrichment_result",
    "update_product_source_tracking",
]
