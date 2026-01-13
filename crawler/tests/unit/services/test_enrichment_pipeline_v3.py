"""
Unit tests for 2-Step Enrichment Pipeline V3.

Task 1.3: 2-Step Enrichment Pipeline

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.1 (FEAT-001)

The Generic Search 2-step pipeline differs from Competition Flow's 3-step:
- Step 1: Producer page search ("{brand} {name} official")
- Step 2: Review site enrichment (if not COMPLETE after Step 1)

No detail page step because generic search returns listicles with inline
product text, not detail page links.

Tests verify:
- Step 1: Producer page search and filter
- Step 2: Review site enrichment
- Early exit when COMPLETE reached
- Limit enforcement (max_searches, max_sources, max_time)
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase

from crawler.services.quality_gate_v3 import ProductStatus


class ProducerPageSearchTests(TestCase):
    """Tests for Step 1: Producer page search."""

    def test_build_producer_search_query(self):
        """Test producer search query is built correctly with brand, name, and 'official'."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
        }

        query = pipeline._build_producer_search_query(product_data)

        self.assertIn("Highland Park", query)
        self.assertIn("Highland Park 18", query)
        self.assertIn("official", query.lower())

    def test_build_producer_search_query_without_brand(self):
        """Test producer search query with name only."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        product_data = {
            "name": "Single Malt 12 Year",
            "brand": "",
        }

        query = pipeline._build_producer_search_query(product_data)

        self.assertIn("Single Malt 12 Year", query)
        self.assertIn("official", query.lower())

    def test_filter_producer_urls_prioritizes_official(self):
        """Test URL filtering prioritizes official sites over retailers."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        urls = [
            "https://www.totalwine.com/highland-park-18",
            "https://www.highlandparkwhisky.com/products/18-year",
            "https://www.masterofmalt.com/whiskies/highland-park-18",
            "https://www.whiskyreviews.com/highland-park-18",
        ]

        filtered = pipeline._filter_producer_urls(
            urls,
            brand="Highland Park",
            producer="Highland Park Distillery"
        )

        # Official site should be first
        self.assertEqual(filtered[0], "https://www.highlandparkwhisky.com/products/18-year")
        # Non-retailer review site should be second
        self.assertEqual(filtered[1], "https://www.whiskyreviews.com/highland-park-18")
        # Retailers should be at the end
        retailer_urls = filtered[2:]
        self.assertTrue(all(
            any(r in url for r in ["totalwine", "masterofmalt"])
            for url in retailer_urls
        ))

    def test_filter_producer_urls_deprioritizes_retailers(self):
        """Test known retailers are deprioritized."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        urls = [
            "https://www.amazon.com/highland-park",
            "https://www.drizly.com/highland-park",
            "https://www.wine.com/product/highland-park",
            "https://www.random-blog.com/highland-park-review",
        ]

        filtered = pipeline._filter_producer_urls(urls, brand="Highland Park", producer="")

        # Non-retailer should be first
        self.assertEqual(filtered[0], "https://www.random-blog.com/highland-park-review")
        # All retailers should be after non-retailer
        retailer_urls = [u for u in filtered[1:] if any(r in u for r in ["amazon", "drizly", "wine.com"])]
        self.assertEqual(len(retailer_urls), 3)

    def test_confidence_boost_for_producer_page(self):
        """Test producer page data gets confidence boost (+0.1, max 0.95)."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        confidences = {"name": 0.80, "abv": 0.85, "description": 0.90}

        boosted = pipeline._apply_producer_confidence_boost(confidences)

        # Should boost by 0.1 but cap at 0.95
        self.assertEqual(boosted["name"], 0.90)
        self.assertEqual(boosted["abv"], 0.95)
        self.assertEqual(boosted["description"], 0.95)  # Capped at 0.95

    def test_confidence_boost_does_not_exceed_max(self):
        """Test confidence boost never exceeds 0.95."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        confidences = {"name": 0.93, "abv": 0.95, "description": 1.0}

        boosted = pipeline._apply_producer_confidence_boost(confidences)

        self.assertEqual(boosted["name"], 0.95)  # 0.93 + 0.1 = 1.03 -> capped at 0.95
        self.assertEqual(boosted["abv"], 0.95)   # Already at 0.95
        self.assertEqual(boosted["description"], 0.95)  # 1.0 -> capped at 0.95


class ReviewSiteEnrichmentTests(TestCase):
    """Tests for Step 2: Review site enrichment."""

    def test_review_site_confidence_range(self):
        """Test review site data gets confidence 0.70-0.80."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        confidence = pipeline._get_review_site_confidence()

        self.assertGreaterEqual(confidence, 0.70)
        self.assertLessEqual(confidence, 0.80)

    def test_review_site_confidence_default(self):
        """Test default review site confidence is 0.75."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        confidence = pipeline._get_review_site_confidence()

        # Default should be 0.75 (middle of range)
        self.assertEqual(confidence, 0.75)


class EarlyExitOnCompleteTests(TestCase):
    """Tests for early exit when COMPLETE status reached."""

    def test_early_exit_when_complete_after_step1(self):
        """Test pipeline exits early if COMPLETE reached after Step 1."""
        from crawler.services.enrichment_pipeline_v3 import (
            EnrichmentPipelineV3,
            EnrichmentSessionV3,
        )

        pipeline = EnrichmentPipelineV3()
        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test Whiskey", "brand": "Test"},
        )

        # Check that COMPLETE status triggers early exit
        should_continue = pipeline._should_continue_to_step2(ProductStatus.COMPLETE)

        self.assertFalse(should_continue)

    def test_continue_when_baseline_after_step1(self):
        """Test pipeline continues to Step 2 if only BASELINE after Step 1."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        should_continue = pipeline._should_continue_to_step2(ProductStatus.BASELINE)

        self.assertTrue(should_continue)

    def test_continue_when_partial_after_step1(self):
        """Test pipeline continues to Step 2 if PARTIAL after Step 1."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        should_continue = pipeline._should_continue_to_step2(ProductStatus.PARTIAL)

        self.assertTrue(should_continue)


class LimitEnforcementTests(TestCase):
    """Tests for limit enforcement (max_searches, max_sources, max_time)."""

    def test_check_limits_returns_true_when_under_limits(self):
        """Test limits check passes when under all limits."""
        from crawler.services.enrichment_pipeline_v3 import (
            EnrichmentPipelineV3,
            EnrichmentSessionV3,
        )

        pipeline = EnrichmentPipelineV3()
        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
            max_searches=3,
            max_sources=5,
            max_time_seconds=120.0,
        )
        session.searches_performed = 1
        session.sources_used = ["url1"]
        session.start_time = time.time()

        can_continue = pipeline._check_limits(session)

        self.assertTrue(can_continue)

    def test_check_limits_returns_false_when_max_searches_reached(self):
        """Test limits check fails when max_searches reached."""
        from crawler.services.enrichment_pipeline_v3 import (
            EnrichmentPipelineV3,
            EnrichmentSessionV3,
        )

        pipeline = EnrichmentPipelineV3()
        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
            max_searches=3,
            max_sources=5,
            max_time_seconds=120.0,
        )
        session.searches_performed = 3
        session.sources_used = ["url1"]
        session.start_time = time.time()

        can_continue = pipeline._check_limits(session)

        self.assertFalse(can_continue)

    def test_check_limits_returns_false_when_max_sources_reached(self):
        """Test limits check fails when max_sources reached."""
        from crawler.services.enrichment_pipeline_v3 import (
            EnrichmentPipelineV3,
            EnrichmentSessionV3,
        )

        pipeline = EnrichmentPipelineV3()
        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
            max_searches=3,
            max_sources=5,
            max_time_seconds=120.0,
        )
        session.searches_performed = 1
        session.sources_used = ["url1", "url2", "url3", "url4", "url5"]
        session.start_time = time.time()

        can_continue = pipeline._check_limits(session)

        self.assertFalse(can_continue)

    def test_check_limits_returns_false_when_max_time_exceeded(self):
        """Test limits check fails when max_time exceeded."""
        from crawler.services.enrichment_pipeline_v3 import (
            EnrichmentPipelineV3,
            EnrichmentSessionV3,
        )

        pipeline = EnrichmentPipelineV3()
        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
            max_searches=3,
            max_sources=5,
            max_time_seconds=120.0,
        )
        session.searches_performed = 1
        session.sources_used = ["url1"]
        # Set start time to 2 minutes ago
        session.start_time = time.time() - 121.0

        can_continue = pipeline._check_limits(session)

        self.assertFalse(can_continue)


class SourceTrackingTests(TestCase):
    """Tests for source tracking (searched, used, rejected)."""

    def test_track_searched_source(self):
        """Test sources are tracked when searched."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentSessionV3

        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        session.sources_searched.append("https://example.com/whiskey")

        self.assertIn("https://example.com/whiskey", session.sources_searched)

    def test_track_used_source(self):
        """Test sources are tracked when used."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentSessionV3

        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        session.sources_used.append("https://example.com/whiskey")

        self.assertIn("https://example.com/whiskey", session.sources_used)

    def test_track_rejected_source_with_reason(self):
        """Test rejected sources are tracked with reasons."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentSessionV3

        session = EnrichmentSessionV3(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        session.sources_rejected.append({
            "url": "https://example.com/wrong-product",
            "reason": "product_type_mismatch: target has bourbon, extracted has rye",
        })

        self.assertEqual(len(session.sources_rejected), 1)
        self.assertEqual(session.sources_rejected[0]["url"], "https://example.com/wrong-product")
        self.assertIn("product_type_mismatch", session.sources_rejected[0]["reason"])


class ProductMatchValidationIntegrationTests(TestCase):
    """Tests for product match validation integration in pipeline."""

    def test_validates_product_match_before_merging(self):
        """Test pipeline validates product match before merging data."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        target_data = {"name": "Frank August Bourbon", "brand": "Frank August"}
        extracted_data = {"name": "Frank August Rye", "brand": "Frank August"}

        is_match, reason = pipeline._validate_and_track(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_accepts_matching_product_data(self):
        """Test pipeline accepts data for matching product."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        target_data = {"name": "Buffalo Trace Bourbon", "brand": "Buffalo Trace"}
        extracted_data = {"name": "Buffalo Trace Kentucky Straight Bourbon", "brand": "Buffalo Trace"}

        is_match, reason = pipeline._validate_and_track(target_data, extracted_data)

        self.assertTrue(is_match)


class ConfidenceMergerIntegrationTests(TestCase):
    """Tests for confidence merger integration in pipeline."""

    def test_merges_data_with_confidence(self):
        """Test pipeline uses confidence-based merger."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()
        existing_data = {"name": "Whiskey", "abv": "40%"}
        existing_confidences = {"name": 0.90, "abv": 0.70}
        new_data = {"abv": "43%", "description": "A fine whiskey"}
        new_confidence = 0.85

        merged, enriched = pipeline._merge_with_confidence(
            existing_data, existing_confidences, new_data, new_confidence
        )

        # ABV should be updated (0.85 > 0.70)
        self.assertEqual(merged["abv"], "43%")
        # Name should not change (0.85 < 0.90)
        self.assertEqual(merged["name"], "Whiskey")
        # Description should be added
        self.assertEqual(merged["description"], "A fine whiskey")
        self.assertIn("abv", enriched)
        self.assertIn("description", enriched)


class EnrichmentResultV3Tests(TestCase):
    """Tests for EnrichmentResultV3 dataclass."""

    def test_result_tracks_steps_completed(self):
        """Test result tracks enrichment steps completed."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentResultV3

        result = EnrichmentResultV3(
            success=True,
            product_data={"name": "Whiskey"},
            step_1_completed=True,
            step_2_completed=False,
        )

        self.assertTrue(result.step_1_completed)
        self.assertFalse(result.step_2_completed)

    def test_result_tracks_status_progression(self):
        """Test result tracks status progression."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentResultV3

        result = EnrichmentResultV3(
            success=True,
            product_data={"name": "Whiskey"},
            status_progression=["skeleton", "partial", "baseline"],
        )

        self.assertEqual(len(result.status_progression), 3)
        self.assertEqual(result.status_progression[-1], "baseline")


class PipelineOrchestrationTests(TestCase):
    """Tests for main enrich_product() orchestration."""

    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._search_and_extract_producer_page')
    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._assess_status')
    async def test_skips_step2_when_complete_after_step1(
        self, mock_assess, mock_producer_search
    ):
        """Test Step 2 is skipped when COMPLETE after Step 1."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        # Setup mocks
        mock_producer_search.return_value = (
            {"description": "Rich whiskey"},
            {"description": 0.85}
        )
        mock_assess.return_value = ProductStatus.COMPLETE

        result = await pipeline.enrich_product(
            product_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey",
        )

        # Step 1 should complete, Step 2 should be skipped
        self.assertTrue(result.step_1_completed)
        self.assertFalse(result.step_2_completed)

    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._search_and_extract_producer_page')
    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._enrich_from_review_sites')
    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._assess_status')
    async def test_executes_step2_when_not_complete_after_step1(
        self, mock_assess, mock_review, mock_producer
    ):
        """Test Step 2 executes when not COMPLETE after Step 1."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        # Setup mocks
        mock_producer.return_value = ({"abv": "46%"}, {"abv": 0.85})
        mock_review.return_value = ({"description": "Smooth"}, {"description": 0.75})
        # Return statuses for: initial, after step1, after step2 (final)
        mock_assess.side_effect = [
            ProductStatus.SKELETON,   # Initial status
            ProductStatus.PARTIAL,    # After Step 1
            ProductStatus.COMPLETE,   # After Step 2
        ]

        result = await pipeline.enrich_product(
            product_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey",
        )

        # Both steps should complete
        self.assertTrue(result.step_1_completed)
        self.assertTrue(result.step_2_completed)

    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._search_and_extract_producer_page')
    @patch('crawler.services.enrichment_pipeline_v3.EnrichmentPipelineV3._assess_status')
    async def test_tracks_all_sources(self, mock_assess, mock_producer):
        """Test all sources are tracked in result."""
        from crawler.services.enrichment_pipeline_v3 import EnrichmentPipelineV3

        pipeline = EnrichmentPipelineV3()

        mock_producer.return_value = ({}, {})
        mock_assess.return_value = ProductStatus.COMPLETE

        result = await pipeline.enrich_product(
            product_data={"name": "Test", "brand": "Test"},
            product_type="whiskey",
        )

        # Result should have source tracking fields
        self.assertIsNotNone(result.sources_searched)
        self.assertIsNotNone(result.sources_used)
        self.assertIsNotNone(result.sources_rejected)
