"""
Data types for Single Product Enrichment Flow.

Task 1.3-1.4: Define dataclasses for tracking single product processing results.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 7
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class SingleProductResult:
    """
    Result from processing a single product.

    Tracks the outcome of fetching, matching, and enriching a single product
    from the CrawlSchedule.search_terms entries.

    Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 7.1
    """

    success: bool = False
    product_id: Optional[UUID] = None
    product_name: str = ""

    # Match status - how the product was identified
    is_new_product: bool = True
    match_method: str = "none"  # gtin | fingerprint | fuzzy_name | none
    match_confidence: float = 0.0

    # Quality progression - status before and after enrichment
    status_before: str = ""
    status_after: str = ""
    ecp_before: float = 0.0
    ecp_after: float = 0.0

    # Enrichment tracking
    enrichment_completed: bool = False
    fields_enriched: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)

    # Timing metrics
    extraction_time_seconds: float = 0.0
    enrichment_time_seconds: float = 0.0
    total_time_seconds: float = 0.0

    # Error handling
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "product_id": str(self.product_id) if self.product_id else None,
            "product_name": self.product_name,
            "is_new_product": self.is_new_product,
            "match_method": self.match_method,
            "match_confidence": self.match_confidence,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "ecp_before": self.ecp_before,
            "ecp_after": self.ecp_after,
            "enrichment_completed": self.enrichment_completed,
            "fields_enriched": self.fields_enriched,
            "sources_used": self.sources_used,
            "field_provenance": self.field_provenance,
            "extraction_time_seconds": self.extraction_time_seconds,
            "enrichment_time_seconds": self.enrichment_time_seconds,
            "total_time_seconds": self.total_time_seconds,
            "error": self.error,
            "warnings": self.warnings,
        }


@dataclass
class SingleProductJobResult:
    """
    Result from processing all products in a single job.

    Aggregates results from processing all product entries in a CrawlSchedule.

    Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 7.2
    """

    job_id: Optional[UUID] = None
    schedule_id: Optional[UUID] = None

    # Counts
    products_processed: int = 0
    products_new: int = 0
    products_existing: int = 0
    products_enriched: int = 0
    products_failed: int = 0

    # Individual results
    results: List[SingleProductResult] = field(default_factory=list)

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Status
    success: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "job_id": str(self.job_id) if self.job_id else None,
            "schedule_id": str(self.schedule_id) if self.schedule_id else None,
            "products_processed": self.products_processed,
            "products_new": self.products_new,
            "products_existing": self.products_existing,
            "products_enriched": self.products_enriched,
            "products_failed": self.products_failed,
            "results": [r.to_dict() for r in self.results],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "errors": self.errors,
        }

    def add_result(self, result: SingleProductResult) -> None:
        """Add a single product result and update counts."""
        self.results.append(result)
        self.products_processed += 1

        if result.success:
            if result.is_new_product:
                self.products_new += 1
            else:
                self.products_existing += 1

            if result.enrichment_completed:
                self.products_enriched += 1
        else:
            self.products_failed += 1
            if result.error:
                self.errors.append(result.error)

    def finalize(self) -> None:
        """Finalize the result with end time and duration."""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

        # Set overall success based on failures
        self.success = self.products_failed == 0 or self.products_processed > self.products_failed
