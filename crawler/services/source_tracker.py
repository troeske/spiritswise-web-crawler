"""
Source Tracker Service for V2 Architecture.

Handles source tracking, content archival, and field provenance tracking.

Phase 4.5: Source Tracking and Content Archival
"""

import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

logger = logging.getLogger(__name__)


class SourceTracker:
    """
    Service for tracking crawled sources and field provenance.

    Provides methods for:
    - Storing crawled sources with preprocessed content
    - Linking products to sources
    - Tracking per-field provenance
    - Managing cleanup eligibility

    Uses singleton pattern for consistent state.
    """

    _instance: Optional['SourceTracker'] = None

    def __new__(cls) -> 'SourceTracker':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the source tracker."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("SourceTracker initialized")

    def is_cleanup_eligible(
        self,
        extraction_status: str,
        wayback_status: str
    ) -> bool:
        """
        Check if a source is eligible for raw content cleanup.

        Cleanup is eligible when:
        - extraction_status is 'processed'
        - wayback_status is 'saved'

        Args:
            extraction_status: Current extraction status
            wayback_status: Current wayback status

        Returns:
            True if eligible for cleanup
        """
        return extraction_status == "processed" and wayback_status == "saved"

    @transaction.atomic
    def store_crawled_source(
        self,
        url: str,
        title: str,
        raw_content: str,
        source_type: str,
        preprocessed_content: Optional[str] = None,
        discovery_source_id: Optional[UUID] = None
    ) -> 'CrawledSource':
        """
        Store or update a crawled source.

        Creates a new CrawledSource record or updates existing if URL matches.

        Args:
            url: URL of the crawled page
            title: Title of the page
            raw_content: Raw HTML content
            source_type: Type of source (award_page, review_article, etc.)
            preprocessed_content: Optional preprocessed/cleaned content
            discovery_source_id: Optional FK to DiscoverySourceConfig

        Returns:
            The created or updated CrawledSource instance
        """
        from crawler.models import CrawledSource

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        # Look for existing source by URL
        existing = CrawledSource.objects.filter(url=url).first()

        if existing:
            # Update existing
            existing.title = title
            existing.raw_content = raw_content
            existing.content_hash = content_hash
            existing.source_type = source_type

            if preprocessed_content:
                existing.preprocessed_content = preprocessed_content
                existing.preprocessed_at = timezone.now()

            if discovery_source_id:
                existing.discovery_source_id = discovery_source_id

            existing.save()
            logger.debug(f"Updated CrawledSource: {url}")
            return existing

        # Create new source
        source = CrawledSource(
            url=url,
            title=title,
            raw_content=raw_content,
            content_hash=content_hash,
            source_type=source_type
        )

        if preprocessed_content:
            source.preprocessed_content = preprocessed_content
            source.preprocessed_at = timezone.now()

        if discovery_source_id:
            source.discovery_source_id = discovery_source_id

        source.save()
        logger.info(f"Created CrawledSource: {url}")
        return source

    @transaction.atomic
    def link_product_to_source(
        self,
        product_id: UUID,
        source_id: UUID,
        extraction_confidence: float,
        fields_extracted: List[str],
        mention_type: Optional[str] = None,
        mention_count: int = 1
    ) -> 'ProductSource':
        """
        Create or update link between product and source.

        Args:
            product_id: UUID of the DiscoveredProduct
            source_id: UUID of the CrawledSource
            extraction_confidence: Overall confidence score (0.0-1.0)
            fields_extracted: List of field names extracted
            mention_type: Optional type of mention (award_winner, etc.)
            mention_count: Number of mentions in source

        Returns:
            The created or updated ProductSource instance
        """
        from crawler.models import ProductSource

        # Look for existing link
        existing = ProductSource.objects.filter(
            product_id=product_id,
            source_id=source_id
        ).first()

        if existing:
            # Update existing
            existing.extraction_confidence = Decimal(str(extraction_confidence))
            existing.fields_extracted = fields_extracted
            if mention_type:
                existing.mention_type = mention_type
            existing.mention_count = mention_count
            existing.save()
            logger.debug(f"Updated ProductSource: {product_id} <- {source_id}")
            return existing

        # Create new link
        link = ProductSource.objects.create(
            product_id=product_id,
            source_id=source_id,
            extraction_confidence=Decimal(str(extraction_confidence)),
            fields_extracted=fields_extracted,
            mention_type=mention_type,
            mention_count=mention_count
        )
        logger.info(f"Created ProductSource: {product_id} <- {source_id}")
        return link

    @transaction.atomic
    def track_field_provenance(
        self,
        product_id: UUID,
        source_id: UUID,
        field_name: str,
        extracted_value: str,
        confidence: float
    ) -> 'ProductFieldSource':
        """
        Track provenance for a specific field value.

        Args:
            product_id: UUID of the DiscoveredProduct
            source_id: UUID of the CrawledSource
            field_name: Name of the field
            extracted_value: The extracted value (as string)
            confidence: Confidence score (0.0-1.0)

        Returns:
            The created or updated ProductFieldSource instance
        """
        from crawler.models import ProductFieldSource

        # Look for existing record
        existing = ProductFieldSource.objects.filter(
            product_id=product_id,
            source_id=source_id,
            field_name=field_name
        ).first()

        if existing:
            # Update existing
            existing.extracted_value = extracted_value
            existing.confidence = Decimal(str(confidence))
            existing.save()
            logger.debug(f"Updated ProductFieldSource: {product_id}.{field_name}")
            return existing

        # Create new record
        record = ProductFieldSource.objects.create(
            product_id=product_id,
            source_id=source_id,
            field_name=field_name,
            extracted_value=extracted_value,
            confidence=Decimal(str(confidence))
        )
        logger.debug(f"Created ProductFieldSource: {product_id}.{field_name}")
        return record

    @transaction.atomic
    def track_extraction_result(
        self,
        product_id: UUID,
        source_id: UUID,
        extracted_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        overall_confidence: float
    ) -> None:
        """
        Track an entire extraction result.

        Batch operation that:
        1. Creates/updates ProductSource link
        2. Creates/updates ProductFieldSource for each field

        Args:
            product_id: UUID of the DiscoveredProduct
            source_id: UUID of the CrawledSource
            extracted_data: Dict of field_name -> extracted_value
            field_confidences: Dict of field_name -> confidence
            overall_confidence: Overall extraction confidence
        """
        # Create product-source link
        fields_extracted = list(extracted_data.keys())
        self.link_product_to_source(
            product_id=product_id,
            source_id=source_id,
            extraction_confidence=overall_confidence,
            fields_extracted=fields_extracted
        )

        # Track each field
        for field_name, value in extracted_data.items():
            confidence = field_confidences.get(field_name, 0.5)

            # Convert value to string for storage
            if isinstance(value, (list, dict)):
                import json
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            self.track_field_provenance(
                product_id=product_id,
                source_id=source_id,
                field_name=field_name,
                extracted_value=value_str,
                confidence=confidence
            )

        logger.info(
            f"Tracked extraction result: {product_id} <- {source_id} "
            f"({len(extracted_data)} fields)"
        )

    def update_cleanup_eligibility(self, source_id: UUID) -> bool:
        """
        Update cleanup eligibility for a source.

        Checks current extraction_status and wayback_status,
        sets cleanup_eligible accordingly.

        Args:
            source_id: UUID of the CrawledSource

        Returns:
            The new cleanup_eligible value
        """
        from crawler.models import CrawledSource

        source = CrawledSource.objects.get(pk=source_id)
        eligible = self.is_cleanup_eligible(
            source.extraction_status,
            source.wayback_status
        )

        if source.cleanup_eligible != eligible:
            source.cleanup_eligible = eligible
            source.save(update_fields=['cleanup_eligible'])
            logger.info(f"Updated cleanup_eligible for {source_id}: {eligible}")

        return eligible

    def get_pending_cleanup_sources(
        self,
        limit: int = 100
    ) -> QuerySet:
        """
        Get sources eligible for cleanup that haven't been cleared.

        Args:
            limit: Maximum number of sources to return

        Returns:
            QuerySet of CrawledSource instances
        """
        from crawler.models import CrawledSource

        return CrawledSource.objects.filter(
            cleanup_eligible=True,
            raw_content_cleared=False,
            raw_content__isnull=False
        ).order_by('crawled_at')[:limit]

    def get_source_by_url(self, url: str) -> Optional['CrawledSource']:
        """
        Get a crawled source by URL.

        Args:
            url: The URL to look up

        Returns:
            CrawledSource instance or None
        """
        from crawler.models import CrawledSource

        return CrawledSource.objects.filter(url=url).first()

    def get_product_sources(
        self,
        product_id: UUID
    ) -> List['ProductSource']:
        """
        Get all sources for a product.

        Args:
            product_id: UUID of the DiscoveredProduct

        Returns:
            List of ProductSource instances
        """
        from crawler.models import ProductSource

        return list(
            ProductSource.objects.filter(product_id=product_id)
            .select_related('source')
            .order_by('-extraction_confidence')
        )

    def get_field_provenance_history(
        self,
        product_id: UUID,
        field_name: str
    ) -> List['ProductFieldSource']:
        """
        Get provenance history for a specific field.

        Args:
            product_id: UUID of the DiscoveredProduct
            field_name: Name of the field

        Returns:
            List of ProductFieldSource instances, ordered by confidence
        """
        from crawler.models import ProductFieldSource

        return list(
            ProductFieldSource.objects.filter(
                product_id=product_id,
                field_name=field_name
            )
            .select_related('source')
            .order_by('-confidence', '-extracted_at')
        )


# Singleton getter function
def get_source_tracker() -> SourceTracker:
    """Get the singleton SourceTracker instance."""
    return SourceTracker()
