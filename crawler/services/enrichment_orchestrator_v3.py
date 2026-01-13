"""
Enrichment Orchestrator V3 - Enhanced multi-source product enrichment.

V3 Changes from V2:
- Updated budget defaults: 6 searches, 8 sources, 180s timeout
- Uses PipelineConfig for per-product-type budget configuration
- Integration with QualityGateV3 for V3 status levels
- ECP calculation and persistence
- Members-only site detection and budget refund (Tasks 4.2, 4.3)
- Dedicated awards search (Task 4.4)

Task 2.1.3 Integration:
- Assess before each enrichment step
- Check for COMPLETE (90% ECP) for early exit
- Record status_before and status_after in session

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4 & 5
Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 2.8 (COMP-LEARN-008)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from crawler.models import PipelineConfig, ProductTypeConfig
from crawler.services.ai_client_v2 import AIClientV2, get_ai_client_v2
from crawler.services.enrichment_orchestrator_v2 import (
    EnrichmentOrchestratorV2,
    EnrichmentResult,
)
from crawler.services.members_only_detector import get_members_only_detector
from crawler.services.quality_gate_v3 import (
    ProductStatus,
    QualityAssessment,
    QualityGateV3,
    get_quality_gate_v3,
)

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentSession:
    """
    Tracks state during V3 enrichment.

    V3 Changes:
    - Updated default limits (8 sources, 6 searches, 180s)
    - Added members_only_sites_detected tracking
    - Added awards_search_completed flag
    - Task 2.1.3: Added status_before, status_after tracking
    """

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any] = field(default_factory=dict)
    field_confidences: Dict[str, float] = field(default_factory=dict)
    sources_searched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    sources_rejected: List[Dict[str, str]] = field(default_factory=list)
    fields_enriched: List[str] = field(default_factory=list)
    searches_performed: int = 0
    max_sources: int = 8  # V3 default
    max_searches: int = 6  # V3 default
    max_time_seconds: float = 180.0  # V3 default
    start_time: float = 0.0
    # V3 additions
    members_only_sites_detected: List[str] = field(default_factory=list)
    awards_search_completed: bool = False
    # Task 2.1.3: Status tracking
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    status_history: List[str] = field(default_factory=list)
    ecp_before: float = 0.0
    ecp_after: float = 0.0
    product_category: Optional[str] = None  # For category-specific requirements

    def __post_init__(self):
        """Initialize current_data from initial_data if empty."""
        if not self.current_data:
            self.current_data = dict(self.initial_data)


class EnrichmentOrchestratorV3(EnrichmentOrchestratorV2):
    """
    V3 Enrichment Orchestrator with enhanced budgets and features.

    V3 Changes:
    - Default budget: 6 searches, 8 sources, 180s timeout
    - Uses PipelineConfig for product-type specific limits
    - QualityGateV3 for V3 status hierarchy
    - ECP tracking in enrichment results

    Task 2.1.3 Integration:
    - Assess before each enrichment step
    - Check for COMPLETE (90% ECP) for early exit
    - Record status_before and status_after

    Future V3 Features (separate tasks):
    - Members-only site detection and budget refund
    - Dedicated awards search step
    """

    # V3 Budget Defaults (increased from V2)
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_SOURCES = 8  # V2 was 5
    DEFAULT_MAX_SEARCHES = 6  # V2 was 3
    DEFAULT_MAX_TIME_SECONDS = 180.0  # V2 was 120

    # V3 Quality Gate Thresholds
    ECP_COMPLETE_THRESHOLD = 90.0  # 90% ECP for COMPLETE status

    def __init__(
        self,
        ai_client: Optional[AIClientV2] = None,
        serp_client: Optional[Any] = None,
        quality_gate: Optional[QualityGateV3] = None,
    ):
        """
        Initialize V3 orchestrator.

        Args:
            ai_client: AIClientV2 instance (optional, creates default)
            serp_client: SerpAPI client (optional, creates default)
            quality_gate: QualityGateV3 instance (optional, creates default)
        """
        # Don't call super().__init__ to avoid V2 quality gate initialization
        self.ai_client = ai_client
        self._serp_client = serp_client
        self._quality_gate_v3 = quality_gate

        logger.debug("EnrichmentOrchestratorV3 initialized with V3 budget defaults")

    @property
    def quality_gate(self) -> QualityGateV3:
        """Get or create V3 quality gate."""
        if self._quality_gate_v3 is None:
            self._quality_gate_v3 = get_quality_gate_v3()
        return self._quality_gate_v3

    def _assess_quality(
        self,
        session: EnrichmentSession,
    ) -> QualityAssessment:
        """
        Assess current data quality using QualityGateV3.

        Task 2.1.3: Called before each enrichment step to check
        if early exit is possible (90% ECP = COMPLETE).

        Args:
            session: Current enrichment session

        Returns:
            QualityAssessment with status and ECP
        """
        assessment = self.quality_gate.assess(
            extracted_data=session.current_data,
            product_type=session.product_type,
            field_confidences=session.field_confidences,
            product_category=session.product_category,
        )

        logger.debug(
            "Quality assessment: status=%s, ecp=%.2f%%, needs_enrichment=%s",
            assessment.status.value,
            assessment.ecp_total,
            assessment.needs_enrichment,
        )

        return assessment

    def _should_continue_enrichment(
        self,
        session: EnrichmentSession,
        assessment: QualityAssessment,
        limits: Dict[str, Any],
    ) -> bool:
        """
        Determine if enrichment should continue.

        Task 2.1.3: Checks for:
        1. COMPLETE status (90% ECP) - early exit
        2. Budget exhausted - forced exit
        3. No more fields to enrich - exit

        Args:
            session: Current enrichment session
            assessment: Latest quality assessment
            limits: Budget limits

        Returns:
            True if enrichment should continue
        """
        # Check for COMPLETE status (90% ECP threshold reached)
        if assessment.status == ProductStatus.COMPLETE:
            logger.info(
                "COMPLETE status reached (ECP=%.2f%%), early exit",
                assessment.ecp_total,
            )
            return False

        # Check for budget exhaustion
        if self._check_budget_exceeded(session, limits):
            return False

        # Check if enrichment is still needed
        if not assessment.needs_enrichment:
            logger.info(
                "No more enrichment needed (status=%s)",
                assessment.status.value,
            )
            return False

        return True

    def _record_status_transition(
        self,
        session: EnrichmentSession,
        before: QualityAssessment,
        after: QualityAssessment,
    ) -> None:
        """
        Record status transition for audit trail.

        Task 2.1.3: Records status_before and status_after,
        plus tracks progression history.

        Args:
            session: Current enrichment session
            before: Assessment before enrichment step
            after: Assessment after enrichment step
        """
        session.status_history.append(after.status.value)

        # Update status_after (status_before is set at session start)
        session.status_after = after.status.value
        session.ecp_after = after.ecp_total

        # Log transition if status changed
        if before.status != after.status:
            logger.info(
                "Status transition: %s -> %s (ECP: %.2f%% -> %.2f%%)",
                before.status.value,
                after.status.value,
                before.ecp_total,
                after.ecp_total,
            )

    def _get_budget_limits(self, product_type: str) -> Dict[str, Any]:
        """
        Get budget limits for a product type.

        Tries to load from PipelineConfig, falls back to V3 defaults.

        Args:
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            Dict with max_searches, max_sources, max_time
        """
        max_searches = self.DEFAULT_MAX_SEARCHES
        max_sources = self.DEFAULT_MAX_SOURCES
        max_time = self.DEFAULT_MAX_TIME_SECONDS

        try:
            # Try to load from PipelineConfig (V3 model)
            config = PipelineConfig.objects.get(
                product_type_config__product_type=product_type
            )
            max_searches = config.max_serpapi_searches or max_searches
            max_sources = config.max_sources_per_product or max_sources
            max_time = float(config.max_enrichment_time_seconds or max_time)

            logger.debug(
                "Using PipelineConfig limits for %s: searches=%d, sources=%d, time=%.0fs",
                product_type,
                max_searches,
                max_sources,
                max_time,
            )

        except PipelineConfig.DoesNotExist:
            logger.debug(
                "PipelineConfig not found for %s, using V3 defaults",
                product_type,
            )

        return {
            "max_searches": max_searches,
            "max_sources": max_sources,
            "max_time": max_time,
        }

    def _check_budget_exceeded(
        self,
        session: EnrichmentSession,
        limits: Dict[str, Any],
    ) -> bool:
        """
        Check if enrichment budget has been exceeded.

        Args:
            session: Current enrichment session
            limits: Budget limits dict

        Returns:
            True if any limit exceeded
        """
        # Check search limit
        if session.searches_performed >= limits["max_searches"]:
            logger.info(
                "Search budget exhausted: %d/%d",
                session.searches_performed,
                limits["max_searches"],
            )
            return True

        # Check source limit
        if len(session.sources_used) >= limits["max_sources"]:
            logger.info(
                "Source budget exhausted: %d/%d",
                len(session.sources_used),
                limits["max_sources"],
            )
            return True

        # Check time limit
        elapsed = time.time() - session.start_time
        if elapsed >= limits["max_time"]:
            logger.info(
                "Time budget exhausted: %.0fs/%.0fs",
                elapsed,
                limits["max_time"],
            )
            return True

        return False

    def _refund_search_budget(
        self,
        session: EnrichmentSession,
        url: str,
    ) -> None:
        """
        Refund search budget when members-only site detected.

        Args:
            session: Current enrichment session
            url: URL of the members-only site
        """
        # Decrement searches_performed (don't go below 0)
        if session.searches_performed > 0:
            session.searches_performed -= 1
            logger.info(
                "Refunded search budget for members-only site: %s (now %d)",
                url,
                session.searches_performed,
            )

        # Track the members-only site
        if url not in session.members_only_sites_detected:
            session.members_only_sites_detected.append(url)

    def _get_remaining_budget(
        self,
        session: EnrichmentSession,
        limits: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Get remaining budget for searches and sources.

        Args:
            session: Current enrichment session
            limits: Budget limits dict

        Returns:
            Dict with remaining searches and sources
        """
        remaining_searches = limits["max_searches"] - session.searches_performed
        remaining_sources = limits["max_sources"] - len(session.sources_used)

        return {
            "searches": max(0, remaining_searches),
            "sources": max(0, remaining_sources),
        }

    def _check_and_refund_if_members_only(
        self,
        session: EnrichmentSession,
        url: str,
        content: Optional[str],
        status_code: int = 200,
    ) -> bool:
        """
        Check if response is members-only and refund budget if so.

        Args:
            session: Current enrichment session
            url: URL that was fetched
            content: Response content
            status_code: HTTP status code

        Returns:
            True if members-only detected and budget refunded
        """
        detector = get_members_only_detector()

        if detector.check_response(content, status_code):
            logger.info("Members-only detected for %s, refunding budget", url)
            self._refund_search_budget(session, url)
            return True

        return False

    def _build_awards_search_query(
        self,
        product_data: Dict[str, Any],
    ) -> str:
        """
        Build search query for awards search.

        Args:
            product_data: Current product data

        Returns:
            Search query string
        """
        name = product_data.get("name", "")
        brand = product_data.get("brand", "")

        # Build query with name, brand, and award keywords
        parts = []
        if brand:
            parts.append(brand)
        if name:
            parts.append(name)
        parts.append("awards medals competition")

        query = " ".join(parts)
        logger.debug("Awards search query: %s", query)

        return query

    def _execute_awards_search(
        self,
        query: str,
        product_type: str,
    ) -> tuple:
        """
        Execute the awards search (stub for integration).

        This method will be implemented in full pipeline integration.
        For now, returns empty results.

        Args:
            query: Search query
            product_type: Product type

        Returns:
            Tuple of (awards_list, sources_list)
        """
        # Stub - will be implemented with SerpAPI integration
        logger.debug("Executing awards search: %s", query)
        return ([], [])

    def _search_awards(
        self,
        session: EnrichmentSession,
        product_type: str,
    ) -> tuple:
        """
        Perform dedicated awards search (Step 4).

        Awards search:
        - Always runs (even if product is COMPLETE)
        - Uses dedicated budget (doesn't affect main search budget)
        - Sets awards_search_completed flag

        Args:
            session: Current enrichment session
            product_type: Product type

        Returns:
            Tuple of (awards_list, sources_list)
        """
        # Skip if already completed in this session
        if session.awards_search_completed:
            logger.debug("Awards search already completed, skipping")
            return ([], [])

        logger.info("Starting dedicated awards search")

        # Build query from current product data
        query = self._build_awards_search_query(session.current_data)

        # Execute awards search (separate from main budget)
        awards, sources = self._execute_awards_search(query, product_type)

        # Mark as completed
        session.awards_search_completed = True

        if awards:
            logger.info("Found %d awards from %d sources", len(awards), len(sources))
        else:
            logger.debug("No awards found in search")

        return (awards, sources)

    def _create_session(
        self,
        product_type: str,
        initial_data: Dict[str, Any],
        initial_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None,
    ) -> EnrichmentSession:
        """
        Create a V3 enrichment session.

        Task 2.1.3: Initializes session with status_before and ecp_before.

        Args:
            product_type: Product type
            initial_data: Initial product data
            initial_confidences: Initial field confidences
            product_category: Optional category for category-specific requirements

        Returns:
            EnrichmentSession with V3 defaults
        """
        limits = self._get_budget_limits(product_type)

        # Get category from initial_data if not explicitly provided
        effective_category = product_category or initial_data.get("category")

        # Create session
        session = EnrichmentSession(
            product_type=product_type,
            initial_data=initial_data,
            current_data=dict(initial_data),
            field_confidences=dict(initial_confidences or {}),
            max_searches=limits["max_searches"],
            max_sources=limits["max_sources"],
            max_time_seconds=limits["max_time"],
            start_time=time.time(),
            product_category=effective_category,
        )

        # Task 2.1.3: Assess initial status
        initial_assessment = self._assess_quality(session)
        session.status_before = initial_assessment.status.value
        session.ecp_before = initial_assessment.ecp_total
        session.status_history.append(initial_assessment.status.value)

        logger.info(
            "Created enrichment session: status_before=%s, ecp_before=%.2f%%",
            session.status_before,
            session.ecp_before,
        )

        return session

    def enrich(
        self,
        product_type: str,
        initial_data: Dict[str, Any],
        initial_confidences: Optional[Dict[str, float]] = None,
        product_category: Optional[str] = None,
    ) -> EnrichmentResult:
        """
        Perform V3 enrichment with quality gate integration.

        Task 2.1.3: Implements the quality-aware enrichment loop:
        1. Create session (assesses initial status)
        2. Check for COMPLETE status for early exit
        3. Loop: search -> extract -> assess -> continue?
        4. Return result with status_before/status_after

        Args:
            product_type: Product type
            initial_data: Initial product data
            initial_confidences: Initial field confidences
            product_category: Optional category for category-specific requirements

        Returns:
            EnrichmentResult with enriched data and status tracking
        """
        # Step 1: Create session (assesses initial status)
        session = self._create_session(
            product_type=product_type,
            initial_data=initial_data,
            initial_confidences=initial_confidences,
            product_category=product_category,
        )

        limits = self._get_budget_limits(product_type)

        # Step 2: Check for COMPLETE status for early exit
        initial_assessment = self._assess_quality(session)
        if initial_assessment.status == ProductStatus.COMPLETE:
            logger.info(
                "Product already COMPLETE (ECP=%.2f%%), skipping enrichment",
                initial_assessment.ecp_total,
            )
            return EnrichmentResult(
                success=True,
                product_data=session.current_data,
                field_confidences=session.field_confidences,
                sources_used=session.sources_used,
                status_before=session.status_before,
                status_after=initial_assessment.status.value,
                ecp_total=initial_assessment.ecp_total,
            )

        # Step 3: Enrichment loop (stub - actual implementation in pipeline tasks)
        # In full implementation, this would:
        # - Execute searches
        # - Fetch and extract from sources
        # - Merge data with confidence
        # - Check quality after each step
        # - Exit when COMPLETE or budget exhausted

        # For now, return current state
        final_assessment = self._assess_quality(session)
        session.status_after = final_assessment.status.value
        session.ecp_after = final_assessment.ecp_total

        logger.info(
            "Enrichment complete: %s -> %s (ECP: %.2f%% -> %.2f%%)",
            session.status_before,
            session.status_after,
            session.ecp_before,
            session.ecp_after,
        )

        return EnrichmentResult(
            success=True,
            product_data=session.current_data,
            field_confidences=session.field_confidences,
            sources_used=session.sources_used,
            status_before=session.status_before,
            status_after=session.status_after,
            ecp_total=session.ecp_after,
        )


# Singleton instance
_enrichment_orchestrator_v3: Optional[EnrichmentOrchestratorV3] = None


def get_enrichment_orchestrator_v3() -> EnrichmentOrchestratorV3:
    """Get singleton EnrichmentOrchestratorV3 instance."""
    global _enrichment_orchestrator_v3
    if _enrichment_orchestrator_v3 is None:
        _enrichment_orchestrator_v3 = EnrichmentOrchestratorV3()
    return _enrichment_orchestrator_v3


def reset_enrichment_orchestrator_v3() -> None:
    """Reset singleton for testing."""
    global _enrichment_orchestrator_v3
    _enrichment_orchestrator_v3 = None
