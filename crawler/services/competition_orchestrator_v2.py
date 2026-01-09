"""
Competition Orchestrator V2 - Orchestrates competition discovery with V2 components.

Phase 7 of V2 Architecture: Integrates AIExtractorV2, QualityGateV2 for
award/competition discovery pipeline.

Features:
- Uses AIExtractorV2 for content extraction
- Uses QualityGateV2 for quality assessment
- Preserves award data (medal, competition, year)
- Determines enrichment needs for incomplete products
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2, get_ai_extractor_v2
from crawler.services.quality_gate_v2 import (
    ProductStatus,
    QualityGateV2,
    QualityAssessment,
    get_quality_gate_v2,
)

logger = logging.getLogger(__name__)


@dataclass
class CompetitionExtractionResult:
    """Result of single competition URL extraction."""

    success: bool
    product_data: Optional[Dict[str, Any]] = None
    quality_status: Optional[str] = None
    needs_enrichment: bool = False
    error: Optional[str] = None
    field_confidences: Dict[str, float] = field(default_factory=dict)
    award_data: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None


@dataclass
class CompetitionBatchResult:
    """Result of batch competition processing."""

    success: bool
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    needs_enrichment: int = 0
    complete: int = 0
    errors: List[str] = field(default_factory=list)
    results: List[CompetitionExtractionResult] = field(default_factory=list)


class CompetitionOrchestratorV2:
    """
    V2 Competition Orchestrator using V2 architecture components.

    Orchestrates:
    - Award page extraction via AIExtractorV2
    - Quality assessment via QualityGateV2
    - Enrichment queue decisions
    - Award data preservation
    """

    def __init__(
        self,
        ai_extractor: Optional[AIExtractorV2] = None,
        quality_gate: Optional[QualityGateV2] = None,
    ):
        """
        Initialize the Competition Orchestrator V2.

        Args:
            ai_extractor: AIExtractorV2 instance (optional, creates default)
            quality_gate: QualityGateV2 instance (optional, creates default)
        """
        self.ai_extractor = ai_extractor or get_ai_extractor_v2()
        self.quality_gate = quality_gate or get_quality_gate_v2()

        logger.debug("CompetitionOrchestratorV2 initialized")

    async def process_competition_url(
        self,
        url: str,
        source: str,
        year: int,
        medal_hint: Optional[str] = None,
        score_hint: Optional[str] = None,
        product_type: str = "whiskey",
        product_category: Optional[str] = None,
    ) -> CompetitionExtractionResult:
        """
        Process a single competition URL with V2 components.

        Args:
            url: Detail page URL to extract from
            source: Competition source (iwsc, sfwsc, dwwa, etc.)
            year: Competition year
            medal_hint: Optional medal hint (Gold, Silver, etc.)
            score_hint: Optional score hint
            product_type: Product type (whiskey, port_wine)
            product_category: Optional category (bourbon, single_malt, etc.)

        Returns:
            CompetitionExtractionResult with extraction and quality data
        """
        logger.info("Processing competition URL: %s (source=%s, year=%s)", url, source, year)

        try:
            # Build context for extraction
            context = {
                "source": source,
                "year": year,
                "medal_hint": medal_hint,
                "score_hint": score_hint,
                "product_type_hint": product_type,
                "product_category_hint": product_category,
            }

            # Extract using AIExtractorV2
            extracted = await self.ai_extractor.extract(url=url, context=context)

            if "error" in extracted and not extracted.get("name"):
                return CompetitionExtractionResult(
                    success=False,
                    error=extracted.get("error", "Extraction failed"),
                    source_url=url,
                )

            # Get field confidences
            field_confidences = extracted.pop("field_confidences", {})
            overall_confidence = extracted.pop("overall_confidence", 0.0)

            # Assess quality
            assessment = self._assess_quality(
                product_data=extracted,
                field_confidences=field_confidences,
                product_type=product_type,
            )

            # Determine enrichment need
            needs_enrichment = self._should_enrich(assessment.status)

            # Build award data
            award_data = {
                "medal": medal_hint,
                "competition": source.upper(),
                "year": year,
                "score": extracted.get("award_score"),
            }

            return CompetitionExtractionResult(
                success=True,
                product_data=extracted,
                quality_status=assessment.status.value,
                needs_enrichment=needs_enrichment,
                field_confidences=field_confidences,
                award_data=award_data,
                source_url=url,
            )

        except Exception as e:
            logger.exception("Error processing competition URL %s: %s", url, e)
            return CompetitionExtractionResult(
                success=False,
                error=str(e),
                source_url=url,
            )

    async def process_competition_batch(
        self,
        urls: List[Dict[str, Any]],
        source: str,
        year: int,
        product_type: str = "whiskey",
    ) -> CompetitionBatchResult:
        """
        Process a batch of competition URLs.

        Args:
            urls: List of dicts with url, medal_hint, score_hint
            source: Competition source
            year: Competition year
            product_type: Product type

        Returns:
            CompetitionBatchResult with batch statistics
        """
        result = CompetitionBatchResult(success=True)

        for url_info in urls:
            try:
                extraction_result = await self.process_competition_url(
                    url=url_info.get("url") or url_info.get("detail_url"),
                    source=source,
                    year=year,
                    medal_hint=url_info.get("medal_hint"),
                    score_hint=url_info.get("score_hint"),
                    product_type=product_type,
                )

                result.total_processed += 1
                result.results.append(extraction_result)

                if extraction_result.success:
                    result.successful += 1
                    if extraction_result.needs_enrichment:
                        result.needs_enrichment += 1
                    else:
                        result.complete += 1
                else:
                    result.failed += 1
                    if extraction_result.error:
                        result.errors.append(extraction_result.error)

            except Exception as e:
                result.failed += 1
                result.errors.append(str(e))
                result.total_processed += 1

        return result

    def _assess_quality(
        self,
        product_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        product_type: str,
    ) -> QualityAssessment:
        """
        Assess product quality using QualityGateV2.

        Args:
            product_data: Extracted product data
            field_confidences: Field confidence scores
            product_type: Product type

        Returns:
            QualityAssessment with status and recommendations
        """
        return self.quality_gate.assess(
            extracted_data=product_data,
            product_type=product_type,
            field_confidences=field_confidences,
        )

    def _should_enrich(self, status: ProductStatus) -> bool:
        """
        Determine if product should be enriched.

        Args:
            status: Product quality status

        Returns:
            True if enrichment is needed
        """
        return status in [ProductStatus.SKELETON, ProductStatus.PARTIAL]


# Singleton instance
_competition_orchestrator_v2: Optional[CompetitionOrchestratorV2] = None


def get_competition_orchestrator_v2() -> CompetitionOrchestratorV2:
    """Get or create singleton CompetitionOrchestratorV2 instance."""
    global _competition_orchestrator_v2
    if _competition_orchestrator_v2 is None:
        _competition_orchestrator_v2 = CompetitionOrchestratorV2()
    return _competition_orchestrator_v2


def reset_competition_orchestrator_v2():
    """Reset singleton instance (for testing)."""
    global _competition_orchestrator_v2
    _competition_orchestrator_v2 = None
