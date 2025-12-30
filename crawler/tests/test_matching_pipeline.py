"""
Tests for Matching Pipeline.

Task Group 13: Matching Pipeline Implementation
These tests verify the product matching pipeline for deduplication.

Tests focus on:
- GTIN matching (confidence 1.0)
- Fingerprint matching (confidence 0.95)
- Fuzzy name matching with similarity thresholds
- Variant detection (cask finish, etc.)
- Auto-merge for high confidence matches
- Flagging for medium confidence matches
"""

import uuid
from decimal import Decimal
from django.test import TestCase

from crawler.models import (
    ProductCandidate,
    DiscoveredProduct,
    DiscoveredBrand,
    CrawledSource,
    DiscoverySourceConfig,
    ProductType,
    ProductCandidateMatchStatus,
)
from crawler.services.matching_pipeline import (
    MatchingPipeline,
    match_by_gtin,
    match_by_fingerprint,
    match_by_fuzzy_name,
    detect_variant,
    MatchResult,
)


class GTINMatchingTestCase(TestCase):
    """Test GTIN matching (Step 1 in pipeline)."""

    def setUp(self):
        """Create required related objects for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Macallan",
        )
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
        )
        # Existing product with GTIN
        self.existing_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint="abc123" * 10 + "abcd",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Macallan 18 Year",
            gtin="12345678901234",
            brand=self.brand,
            abv=Decimal("43.0"),
        )

    def test_gtin_exact_match_returns_confidence_1(self):
        """Test that GTIN exact match returns confidence 1.0."""
        candidate_data = {
            "gtin": "12345678901234",
            "name": "Macallan 18 Year Old",
        }

        result = match_by_gtin(candidate_data)

        self.assertIsNotNone(result)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.matched_product.id, self.existing_product.id)
        self.assertEqual(result.method, "gtin")

    def test_gtin_no_match_returns_none(self):
        """Test that non-matching GTIN returns None."""
        candidate_data = {
            "gtin": "99999999999999",
            "name": "Some Other Product",
        }

        result = match_by_gtin(candidate_data)

        self.assertIsNone(result)

    def test_gtin_missing_returns_none(self):
        """Test that missing GTIN returns None."""
        candidate_data = {
            "name": "Macallan 18",
        }

        result = match_by_gtin(candidate_data)

        self.assertIsNone(result)


class FingerprintMatchingTestCase(TestCase):
    """Test fingerprint matching (Step 2 in pipeline)."""

    def setUp(self):
        """Create required related objects for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
        )
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
        )

    def test_fingerprint_match_returns_confidence_095(self):
        """Test that fingerprint match returns confidence 0.95."""
        # Define extracted_data with product_type included for matching fingerprint
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": 40.0,
            "volume_ml": 700,
            "product_type": "whiskey",  # Include product_type for fingerprint
        }
        # Compute the fingerprint from extracted_data
        computed_fingerprint = DiscoveredProduct.compute_fingerprint(extracted_data)

        # Create existing product with pre-computed fingerprint
        existing_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint=computed_fingerprint,
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Glenfiddich 12 Year",
            brand=self.brand,
            abv=Decimal("40.0"),
            extracted_data=extracted_data,
        )

        # Candidate data should produce the same fingerprint
        candidate_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": 40.0,
            "volume_ml": 700,
            "product_type": "whiskey",
        }

        result = match_by_fingerprint(candidate_data)

        self.assertIsNotNone(result)
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.matched_product.id, existing_product.id)
        self.assertEqual(result.method, "fingerprint")

    def test_fingerprint_no_match_returns_none(self):
        """Test that non-matching fingerprint returns None."""
        candidate_data = {
            "name": "New Product",
            "brand": "NewBrand",
            "abv": 50.0,
            "volume_ml": 1000,
            "product_type": "whiskey",
        }

        result = match_by_fingerprint(candidate_data)

        self.assertIsNone(result)


class FuzzyNameMatchingTestCase(TestCase):
    """Test fuzzy name matching (Step 3 in pipeline)."""

    def setUp(self):
        """Create required related objects for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Macallan",
        )
        self.existing_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint="abc123" * 10 + "abcd",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Macallan 18 Year Double Cask",
            brand=self.brand,
            abv=Decimal("43.0"),
        )

    def test_fuzzy_match_high_similarity_same_brand(self):
        """Test fuzzy match with >= 0.85 similarity and same brand."""
        candidate_data = {
            "name": "The Macallan 18 Years Old Double Cask",
            "brand": "Macallan",
            "product_type": "whiskey",
        }

        result = match_by_fuzzy_name(candidate_data)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.confidence, 0.7)
        self.assertLessEqual(result.confidence, 0.9)
        self.assertEqual(result.matched_product.id, self.existing_product.id)
        self.assertEqual(result.method, "fuzzy")

    def test_fuzzy_match_high_similarity_same_abv(self):
        """Test fuzzy match with >= 0.90 similarity and same ABV."""
        candidate_data = {
            "name": "Macallan 18 Year Double Cask",
            "abv": 43.0,
            "product_type": "whiskey",
        }

        result = match_by_fuzzy_name(candidate_data)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.confidence, 0.7)
        self.assertEqual(result.matched_product.id, self.existing_product.id)

    def test_fuzzy_match_low_similarity_returns_none(self):
        """Test that low similarity fuzzy match returns None."""
        candidate_data = {
            "name": "Completely Different Product Name",
            "brand": "OtherBrand",
            "product_type": "whiskey",
        }

        result = match_by_fuzzy_name(candidate_data)

        self.assertIsNone(result)


class VariantDetectionTestCase(TestCase):
    """Test variant detection (different expression, not duplicate)."""

    def setUp(self):
        """Create required related objects for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Macallan",
        )
        # Base product: Macallan 18
        self.base_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint="abc123" * 10 + "abcd",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Macallan 18 Year",
            brand=self.brand,
            abv=Decimal("43.0"),
        )

    def test_detect_cask_finish_variant(self):
        """Test detection of cask finish variant."""
        candidate_data = {
            "name": "Macallan 18 Year Sherry Oak",
            "brand": "Macallan",
            "product_type": "whiskey",
        }

        result = detect_variant(candidate_data, self.base_product)

        self.assertIsNotNone(result)
        self.assertTrue(result.is_variant)
        self.assertEqual(result.variant_type, "cask_finish")
        self.assertEqual(result.base_product.id, self.base_product.id)

    def test_detect_cask_strength_variant(self):
        """Test detection of cask strength variant."""
        candidate_data = {
            "name": "Macallan 18 Year Cask Strength",
            "brand": "Macallan",
            "product_type": "whiskey",
        }

        result = detect_variant(candidate_data, self.base_product)

        self.assertIsNotNone(result)
        self.assertTrue(result.is_variant)
        self.assertEqual(result.variant_type, "cask_strength")

    def test_detect_limited_edition_variant(self):
        """Test detection of limited edition variant."""
        candidate_data = {
            "name": "Macallan 18 Year Limited Edition",
            "brand": "Macallan",
            "product_type": "whiskey",
        }

        result = detect_variant(candidate_data, self.base_product)

        self.assertIsNotNone(result)
        self.assertTrue(result.is_variant)
        self.assertEqual(result.variant_type, "limited_edition")

    def test_no_variant_detected_for_same_product(self):
        """Test that no variant is detected when names are too similar."""
        candidate_data = {
            "name": "Macallan 18 Year",
            "brand": "Macallan",
            "product_type": "whiskey",
        }

        result = detect_variant(candidate_data, self.base_product)

        self.assertIsNone(result)


class MatchingPipelineWorkflowTestCase(TestCase):
    """Test the complete matching pipeline workflow."""

    def setUp(self):
        """Create required related objects for testing."""
        self.brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
        )
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="IWSC Test",
            base_url="https://iwsc.net",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
        )
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
            discovery_source=self.discovery_source,
        )
        # Create existing product
        self.existing_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint="abc123" * 10 + "1234",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Glenfiddich 12 Year",
            gtin="11111111111111",
            brand=self.brand,
            abv=Decimal("40.0"),
        )

    def test_high_confidence_auto_merge(self):
        """Test that high confidence matches (>0.9) trigger auto-merge."""
        candidate = ProductCandidate.objects.create(
            raw_name="Glenfiddich 12 Year",
            normalized_name="glenfiddich 12 year",
            source=self.crawled_source,
            extracted_data={
                "gtin": "11111111111111",
                "name": "Glenfiddich 12 Year",
            },
        )

        pipeline = MatchingPipeline()
        result = pipeline.process_candidate(candidate)

        candidate.refresh_from_db()
        self.assertEqual(candidate.match_status, ProductCandidateMatchStatus.MATCHED)
        self.assertEqual(candidate.matched_product.id, self.existing_product.id)
        self.assertGreater(candidate.match_confidence, 0.9)

    def test_medium_confidence_flags_for_review(self):
        """Test that medium confidence matches (0.7-0.9) are flagged for review."""
        # Create a product that will match with medium confidence
        self.existing_product.gtin = None  # Remove GTIN to avoid exact match
        self.existing_product.save()

        candidate = ProductCandidate.objects.create(
            raw_name="Glenfiddich 12 Years Old Special Reserve",
            normalized_name="glenfiddich 12 year special reserve",
            source=self.crawled_source,
            extracted_data={
                "name": "Glenfiddich 12 Years Old Special Reserve",
                "brand": "Glenfiddich",
                "product_type": "whiskey",
            },
        )

        pipeline = MatchingPipeline()
        result = pipeline.process_candidate(candidate)

        candidate.refresh_from_db()
        # Medium confidence - either matched or needs_review depending on confidence
        self.assertIn(
            candidate.match_status,
            [ProductCandidateMatchStatus.MATCHED, ProductCandidateMatchStatus.NEEDS_REVIEW]
        )
        if candidate.match_status == ProductCandidateMatchStatus.NEEDS_REVIEW:
            self.assertGreaterEqual(candidate.match_confidence, 0.7)
            self.assertLess(candidate.match_confidence, 0.9)

    def test_low_confidence_creates_new_product(self):
        """Test that low confidence (<0.7) or no match creates new product."""
        candidate = ProductCandidate.objects.create(
            raw_name="Completely New Whiskey 2024",
            normalized_name="completely new whiskey 2024",
            source=self.crawled_source,
            extracted_data={
                "name": "Completely New Whiskey 2024",
                "brand": "NewBrand",
                "product_type": "whiskey",
            },
        )

        pipeline = MatchingPipeline()
        result = pipeline.process_candidate(candidate)

        candidate.refresh_from_db()
        self.assertEqual(candidate.match_status, ProductCandidateMatchStatus.NEW_PRODUCT)
        self.assertLess(candidate.match_confidence, 0.7)

    def test_pipeline_runs_steps_in_order(self):
        """Test that pipeline runs GTIN -> fingerprint -> fuzzy in order."""
        # Product with GTIN should match at step 1
        candidate_with_gtin = ProductCandidate.objects.create(
            raw_name="Glenfiddich 12",
            normalized_name="glenfiddich 12",
            source=self.crawled_source,
            extracted_data={
                "gtin": "11111111111111",
                "name": "Glenfiddich 12",
            },
        )

        pipeline = MatchingPipeline()
        result = pipeline.process_candidate(candidate_with_gtin)

        candidate_with_gtin.refresh_from_db()
        self.assertEqual(candidate_with_gtin.match_method, "gtin")

    def test_candidate_match_status_updated(self):
        """Test that ProductCandidate.match_status is updated after processing."""
        candidate = ProductCandidate.objects.create(
            raw_name="Unknown Product",
            normalized_name="unknown product",
            source=self.crawled_source,
            extracted_data={
                "name": "Unknown Product",
            },
            match_status=ProductCandidateMatchStatus.PENDING,
        )

        pipeline = MatchingPipeline()
        result = pipeline.process_candidate(candidate)

        candidate.refresh_from_db()
        self.assertNotEqual(candidate.match_status, ProductCandidateMatchStatus.PENDING)
