"""
Utility functions for the crawler application.

Task Group 8: Per-Field Provenance Tracking
- provenance.py: Field provenance lookup utilities

Task Group 14: Freshness Tracking
- freshness.py: Freshness score calculation and update utilities

Task Group 15: CrawlSchedule Utilities
- scheduling.py: Next run calculation with exponential backoff
"""

from .provenance import get_field_provenance, FieldProvenanceResult
from .freshness import (
    calculate_freshness_score,
    get_data_freshness_level,
    update_product_freshness,
    get_products_needing_refresh,
    batch_update_freshness_scores,
    FRESHNESS_THRESHOLDS,
    FRESHNESS_WEIGHTS,
    NEEDS_REFRESH_THRESHOLD,
)
from .scheduling import (
    calculate_next_run,
    calculate_next_run_with_backoff,
    reset_error_backoff,
    apply_error_backoff,
    get_due_schedules,
    SCHEDULE_INTERVALS,
    MAX_BACKOFF_DELAY,
)

__all__ = [
    # Provenance utilities
    "get_field_provenance",
    "FieldProvenanceResult",
    # Freshness utilities
    "calculate_freshness_score",
    "get_data_freshness_level",
    "update_product_freshness",
    "get_products_needing_refresh",
    "batch_update_freshness_scores",
    "FRESHNESS_THRESHOLDS",
    "FRESHNESS_WEIGHTS",
    "NEEDS_REFRESH_THRESHOLD",
    # Scheduling utilities
    "calculate_next_run",
    "calculate_next_run_with_backoff",
    "reset_error_backoff",
    "apply_error_backoff",
    "get_due_schedules",
    "SCHEDULE_INTERVALS",
    "MAX_BACKOFF_DELAY",
]
