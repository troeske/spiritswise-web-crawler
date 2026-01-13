"""
Unit tests for V3 source tracking persistence.

Task 2.2.6: Update product save logic to persist source tracking.
Spec Reference: GENERIC_SEARCH_V3_SPEC.md Section 5.6.2

Tests:
- SourceTrackingData dataclass
- create_source_tracking_from_enrichment_result helper
- _populate_source_tracking method
- _merge_source_tracking method
- update_product_source_tracking standalone function
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from crawler.services.product_pipeline import (
    SourceTrackingData,
    UnifiedProductPipeline,
    create_source_tracking_from_enrichment_result,
)


class TestSourceTrackingData:
    """Tests for SourceTrackingData dataclass."""

    def test_create_with_defaults(self):
        """Test creating SourceTrackingData with default values."""
        tracking = SourceTrackingData()

        assert tracking.sources_searched == []
        assert tracking.sources_used == []
        assert tracking.sources_rejected == []
        assert tracking.field_provenance == {}
        assert tracking.enrichment_steps_completed == 0

    def test_create_with_all_fields(self):
        """Test creating SourceTrackingData with all fields populated."""
        tracking = SourceTrackingData(
            sources_searched=["https://site1.com", "https://site2.com"],
            sources_used=["https://site1.com"],
            sources_rejected=[{"url": "https://site2.com", "reason": "brand_mismatch"}],
            field_provenance={"name": "https://site1.com", "brand": "https://site1.com"},
            enrichment_steps_completed=2,
        )

        assert len(tracking.sources_searched) == 2
        assert len(tracking.sources_used) == 1
        assert len(tracking.sources_rejected) == 1
        assert "name" in tracking.field_provenance
        assert tracking.enrichment_steps_completed == 2


class TestCreateSourceTrackingFromEnrichmentResult:
    """Tests for create_source_tracking_from_enrichment_result helper."""

    def test_convert_from_v3_result_both_steps_complete(self):
        """Test conversion from EnrichmentResultV3 with both steps complete."""
        class MockV3Result:
            step_1_completed = True
            step_2_completed = True
            sources_searched = ["https://producer.com", "https://review.com"]
            sources_used = ["https://producer.com"]
            sources_rejected = [{"url": "https://review.com", "reason": "product_mismatch"}]
            field_provenance = {"abv": "https://producer.com"}

        result = MockV3Result()
        tracking = create_source_tracking_from_enrichment_result(result)

        assert tracking.enrichment_steps_completed == 2
        assert tracking.sources_searched == ["https://producer.com", "https://review.com"]
        assert tracking.sources_used == ["https://producer.com"]
        assert len(tracking.sources_rejected) == 1
        assert tracking.field_provenance == {"abv": "https://producer.com"}

    def test_convert_from_v3_result_step_1_only(self):
        """Test conversion from EnrichmentResultV3 with only step 1 complete."""
        class MockV3Result:
            step_1_completed = True
            step_2_completed = False
            sources_searched = ["https://producer.com"]
            sources_used = ["https://producer.com"]
            sources_rejected = []
            field_provenance = {}

        result = MockV3Result()
        tracking = create_source_tracking_from_enrichment_result(result)

        assert tracking.enrichment_steps_completed == 1

    def test_convert_from_v2_result_estimates_steps(self):
        """Test conversion from V2 EnrichmentResult estimates steps from sources."""
        class MockV2Result:
            sources_searched = ["https://site1.com", "https://site2.com"]
            sources_used = ["https://site1.com", "https://site2.com"]
            sources_rejected = []
            # No step_1_completed or step_2_completed attributes

        result = MockV2Result()
        tracking = create_source_tracking_from_enrichment_result(result)

        # V2 estimates steps as min(2, len(sources_used))
        assert tracking.enrichment_steps_completed == 2

    def test_convert_handles_empty_result(self):
        """Test conversion handles result with empty/None fields."""
        class MockEmptyResult:
            step_1_completed = False
            step_2_completed = False
            sources_searched = None
            sources_used = None
            sources_rejected = None
            field_provenance = None

        result = MockEmptyResult()
        tracking = create_source_tracking_from_enrichment_result(result)

        assert tracking.sources_searched == []
        assert tracking.sources_used == []
        assert tracking.sources_rejected == []
        assert tracking.field_provenance == {}
        assert tracking.enrichment_steps_completed == 0


class TestPopulateSourceTracking:
    """Tests for _populate_source_tracking method."""

    def test_populates_all_fields_on_new_product(self):
        """Test that all source tracking fields are populated on a new product."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        # Create a mock product
        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = None
        mock_product.enrichment_sources_used = None
        mock_product.enrichment_sources_rejected = None
        mock_product.field_provenance = None
        mock_product.enrichment_steps_completed = None
        mock_product.last_enrichment_at = None

        tracking = SourceTrackingData(
            sources_searched=["https://site1.com", "https://site2.com"],
            sources_used=["https://site1.com"],
            sources_rejected=[{"url": "https://site2.com", "reason": "mismatch"}],
            field_provenance={"name": "https://site1.com"},
            enrichment_steps_completed=2,
        )

        pipeline._populate_source_tracking(mock_product, tracking)

        assert mock_product.enrichment_sources_searched == ["https://site1.com", "https://site2.com"]
        assert mock_product.enrichment_sources_used == ["https://site1.com"]
        assert mock_product.enrichment_sources_rejected == [{"url": "https://site2.com", "reason": "mismatch"}]
        assert mock_product.field_provenance == {"name": "https://site1.com"}
        assert mock_product.enrichment_steps_completed == 2
        assert mock_product.last_enrichment_at is not None

    def test_handles_empty_tracking_data(self):
        """Test that empty tracking data results in empty lists/dicts."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        tracking = SourceTrackingData()  # All defaults (empty)

        pipeline._populate_source_tracking(mock_product, tracking)

        assert mock_product.enrichment_sources_searched == []
        assert mock_product.enrichment_sources_used == []
        assert mock_product.enrichment_sources_rejected == []
        assert mock_product.field_provenance == {}
        assert mock_product.enrichment_steps_completed == 0


class TestMergeSourceTracking:
    """Tests for _merge_source_tracking method."""

    def test_merges_sources_searched_unique(self):
        """Test that sources_searched is merged with unique URLs."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = ["https://existing.com"]
        mock_product.enrichment_sources_used = []
        mock_product.enrichment_sources_rejected = []
        mock_product.field_provenance = {}
        mock_product.enrichment_steps_completed = 1

        tracking = SourceTrackingData(
            sources_searched=["https://existing.com", "https://new.com"],  # One duplicate
            sources_used=[],
            sources_rejected=[],
            field_provenance={},
            enrichment_steps_completed=1,
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        # Should have 2 unique URLs
        assert len(mock_product.enrichment_sources_searched) == 2
        assert "https://existing.com" in mock_product.enrichment_sources_searched
        assert "https://new.com" in mock_product.enrichment_sources_searched

    def test_merges_sources_used_unique(self):
        """Test that sources_used is merged with unique URLs."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = []
        mock_product.enrichment_sources_used = ["https://used1.com"]
        mock_product.enrichment_sources_rejected = []
        mock_product.field_provenance = {}
        mock_product.enrichment_steps_completed = 1

        tracking = SourceTrackingData(
            sources_searched=[],
            sources_used=["https://used1.com", "https://used2.com"],  # One duplicate
            sources_rejected=[],
            field_provenance={},
            enrichment_steps_completed=1,
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        assert len(mock_product.enrichment_sources_used) == 2

    def test_appends_all_rejected_sources(self):
        """Test that sources_rejected appends all (preserves history)."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = []
        mock_product.enrichment_sources_used = []
        mock_product.enrichment_sources_rejected = [{"url": "https://old.com", "reason": "old_mismatch"}]
        mock_product.field_provenance = {}
        mock_product.enrichment_steps_completed = 1

        tracking = SourceTrackingData(
            sources_searched=[],
            sources_used=[],
            sources_rejected=[{"url": "https://new.com", "reason": "new_mismatch"}],
            field_provenance={},
            enrichment_steps_completed=1,
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        # Should have 2 rejected entries (not deduplicated)
        assert len(mock_product.enrichment_sources_rejected) == 2

    def test_newer_field_provenance_wins(self):
        """Test that newer field_provenance mappings override older ones."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = []
        mock_product.enrichment_sources_used = []
        mock_product.enrichment_sources_rejected = []
        mock_product.field_provenance = {"name": "https://old.com", "brand": "https://old.com"}
        mock_product.enrichment_steps_completed = 1

        tracking = SourceTrackingData(
            sources_searched=[],
            sources_used=[],
            sources_rejected=[],
            field_provenance={"name": "https://new.com", "abv": "https://new.com"},  # name override
            enrichment_steps_completed=2,
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        # name should be updated, brand preserved, abv added
        assert mock_product.field_provenance["name"] == "https://new.com"
        assert mock_product.field_provenance["brand"] == "https://old.com"
        assert mock_product.field_provenance["abv"] == "https://new.com"

    def test_takes_max_enrichment_steps(self):
        """Test that enrichment_steps_completed takes the max value."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = []
        mock_product.enrichment_sources_used = []
        mock_product.enrichment_sources_rejected = []
        mock_product.field_provenance = {}
        mock_product.enrichment_steps_completed = 1

        tracking = SourceTrackingData(
            sources_searched=[],
            sources_used=[],
            sources_rejected=[],
            field_provenance={},
            enrichment_steps_completed=2,  # Higher value
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        assert mock_product.enrichment_steps_completed == 2

    def test_updates_last_enrichment_at(self):
        """Test that last_enrichment_at is always updated."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = []
        mock_product.enrichment_sources_used = []
        mock_product.enrichment_sources_rejected = []
        mock_product.field_provenance = {}
        mock_product.enrichment_steps_completed = 0
        mock_product.last_enrichment_at = None

        tracking = SourceTrackingData()

        pipeline._merge_source_tracking(mock_product, tracking)

        assert mock_product.last_enrichment_at is not None

    def test_handles_none_existing_fields(self):
        """Test that None existing fields are handled correctly."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = None
        mock_product.enrichment_sources_used = None
        mock_product.enrichment_sources_rejected = None
        mock_product.field_provenance = None
        mock_product.enrichment_steps_completed = None

        tracking = SourceTrackingData(
            sources_searched=["https://new.com"],
            sources_used=["https://new.com"],
            sources_rejected=[],
            field_provenance={"name": "https://new.com"},
            enrichment_steps_completed=1,
        )

        pipeline._merge_source_tracking(mock_product, tracking)

        assert "https://new.com" in mock_product.enrichment_sources_searched
        assert "https://new.com" in mock_product.enrichment_sources_used
        assert mock_product.enrichment_steps_completed == 1


class TestIntegration:
    """Integration tests for source tracking with real EnrichmentResultV3."""

    def test_end_to_end_source_tracking_flow(self):
        """Test creating tracking from result and populating product."""
        # Simulate EnrichmentResultV3
        from crawler.services.enrichment_pipeline_v3 import EnrichmentResultV3

        result = EnrichmentResultV3(
            success=True,
            product_data={"name": "Test Whiskey", "brand": "Test Brand"},
            quality_status="baseline",
            step_1_completed=True,
            step_2_completed=True,
            sources_searched=["https://producer.com", "https://review1.com", "https://review2.com"],
            sources_used=["https://producer.com", "https://review1.com"],
            sources_rejected=[{"url": "https://review2.com", "reason": "product_type_mismatch"}],
            field_provenance={
                "name": "https://producer.com",
                "brand": "https://producer.com",
                "abv": "https://review1.com",
            },
        )

        # Convert to SourceTrackingData
        tracking = create_source_tracking_from_enrichment_result(result)

        assert tracking.enrichment_steps_completed == 2
        assert len(tracking.sources_searched) == 3
        assert len(tracking.sources_used) == 2
        assert len(tracking.sources_rejected) == 1
        assert tracking.field_provenance["name"] == "https://producer.com"

        # Populate mock product
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)
        mock_product = MagicMock()
        mock_product.enrichment_sources_searched = None
        mock_product.enrichment_sources_used = None
        mock_product.enrichment_sources_rejected = None
        mock_product.field_provenance = None
        mock_product.enrichment_steps_completed = None
        mock_product.last_enrichment_at = None

        pipeline._populate_source_tracking(mock_product, tracking)

        assert mock_product.enrichment_sources_searched == tracking.sources_searched
        assert mock_product.enrichment_sources_used == tracking.sources_used
        assert mock_product.enrichment_sources_rejected == tracking.sources_rejected
        assert mock_product.field_provenance == tracking.field_provenance
        assert mock_product.enrichment_steps_completed == 2


class TestSaveProductWithSourceTracking:
    """Tests for _save_product with source_tracking parameter."""

    def test_save_product_accepts_source_tracking(self):
        """Test that _save_product accepts source_tracking parameter."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        # Verify the method signature accepts source_tracking
        import inspect
        sig = inspect.signature(pipeline._save_product)
        params = list(sig.parameters.keys())

        assert "source_tracking" in params, "_save_product should accept source_tracking parameter"

    def test_update_existing_product_accepts_source_tracking(self):
        """Test that _update_existing_product accepts source_tracking parameter."""
        pipeline = UnifiedProductPipeline.__new__(UnifiedProductPipeline)

        import inspect
        sig = inspect.signature(pipeline._update_existing_product)
        params = list(sig.parameters.keys())

        assert "source_tracking" in params, "_update_existing_product should accept source_tracking parameter"
