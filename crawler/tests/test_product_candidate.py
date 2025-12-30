"""
Tests for ProductCandidate model.

Task Group 12: ProductCandidate Staging Model
These tests verify the product candidate staging model functionality for deduplication.

Tests focus on:
- Candidate creation with raw/normalized names
- match_status state transitions
- matched_product FK relationship
- Name normalization utility
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from crawler.models import (
    ProductCandidate,
    DiscoveredProduct,
    CrawledSource,
    DiscoverySourceConfig,
    ProductType,
)
from crawler.utils.normalization import normalize_product_name


class ProductCandidateCreationTestCase(TestCase):
    """Test ProductCandidate creation with raw and normalized names."""

    def setUp(self):
        """Create required related objects for testing."""
        self.discovery_source = DiscoverySourceConfig.objects.create(
            name="IWSC Test",
            base_url="https://iwsc.net",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
        )
        self.crawled_source = CrawledSource.objects.create(
            url="https://iwsc.net/awards/2024/whiskey-winners",
            title="IWSC 2024 Whiskey Winners",
            source_type="award_page",
            extraction_status="pending",
            discovery_source=self.discovery_source,
        )

    def test_create_product_candidate_with_required_fields(self):
        """Test creating a product candidate with all required fields succeeds."""
        candidate = ProductCandidate.objects.create(
            raw_name="The Macallan 18 Years Old Double Cask",
            normalized_name="macallan 18 year double cask",
            source=self.crawled_source,
            extracted_data={"name": "Macallan 18", "abv": 43.0},
            match_status="pending",
        )

        self.assertIsNotNone(candidate.id)
        self.assertIsInstance(candidate.id, uuid.UUID)
        self.assertEqual(candidate.raw_name, "The Macallan 18 Years Old Double Cask")
        self.assertEqual(candidate.normalized_name, "macallan 18 year double cask")
        self.assertEqual(candidate.source, self.crawled_source)
        self.assertEqual(candidate.match_status, "pending")
        self.assertEqual(candidate.extracted_data["abv"], 43.0)
        self.assertIsNotNone(candidate.created_at)

    def test_create_candidate_with_default_match_status(self):
        """Test that default match_status is 'pending'."""
        candidate = ProductCandidate.objects.create(
            raw_name="Glenfiddich 12 Year Old",
            normalized_name="glenfiddich 12 year",
            source=self.crawled_source,
            extracted_data={},
        )

        self.assertEqual(candidate.match_status, "pending")

    def test_create_candidate_with_long_name(self):
        """Test creating candidate with long product names (up to 500 chars)."""
        long_name = "A" * 500
        candidate = ProductCandidate.objects.create(
            raw_name=long_name,
            normalized_name=long_name.lower(),
            source=self.crawled_source,
            extracted_data={},
        )

        self.assertEqual(len(candidate.raw_name), 500)
        self.assertEqual(len(candidate.normalized_name), 500)


class ProductCandidateMatchStatusTestCase(TestCase):
    """Test match_status state transitions."""

    def setUp(self):
        """Create required related objects for testing."""
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
        )

    def test_valid_match_statuses(self):
        """Test all valid match_status choices are accepted."""
        valid_statuses = ["pending", "matched", "new_product", "needs_review"]

        for i, status in enumerate(valid_statuses):
            candidate = ProductCandidate.objects.create(
                raw_name=f"Product {i}",
                normalized_name=f"product {i}",
                source=self.crawled_source,
                extracted_data={},
                match_status=status,
            )
            self.assertEqual(candidate.match_status, status)

    def test_status_transition_to_matched(self):
        """Test transitioning match_status from pending to matched."""
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18",
            normalized_name="macallan 18",
            source=self.crawled_source,
            extracted_data={},
            match_status="pending",
        )

        self.assertEqual(candidate.match_status, "pending")

        # Transition to matched
        candidate.match_status = "matched"
        candidate.match_confidence = Decimal("0.95")
        candidate.match_method = "fingerprint"
        candidate.save()

        candidate.refresh_from_db()
        self.assertEqual(candidate.match_status, "matched")
        self.assertEqual(candidate.match_confidence, Decimal("0.95"))
        self.assertEqual(candidate.match_method, "fingerprint")

    def test_status_transition_to_new_product(self):
        """Test transitioning match_status from pending to new_product."""
        candidate = ProductCandidate.objects.create(
            raw_name="New Release Whiskey 2024",
            normalized_name="new release whiskey 2024",
            source=self.crawled_source,
            extracted_data={},
            match_status="pending",
        )

        # No match found, create new product
        candidate.match_status = "new_product"
        candidate.match_confidence = Decimal("0.0")
        candidate.save()

        candidate.refresh_from_db()
        self.assertEqual(candidate.match_status, "new_product")

    def test_status_transition_to_needs_review(self):
        """Test transitioning match_status to needs_review for ambiguous matches."""
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18 Sherry Oak",
            normalized_name="macallan 18 sherry oak",
            source=self.crawled_source,
            extracted_data={},
            match_status="pending",
        )

        # Ambiguous match, flag for review
        candidate.match_status = "needs_review"
        candidate.match_confidence = Decimal("0.65")
        candidate.match_method = "fuzzy"
        candidate.save()

        candidate.refresh_from_db()
        self.assertEqual(candidate.match_status, "needs_review")
        self.assertEqual(candidate.match_confidence, Decimal("0.65"))


class ProductCandidateMatchedProductTestCase(TestCase):
    """Test matched_product FK relationship."""

    def setUp(self):
        """Create required related objects for testing."""
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
        )
        self.discovered_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/product",
            fingerprint="abc123" * 10 + "abcd",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            raw_content_hash="hash123",
            name="Macallan 18 Year",
            extracted_data={"name": "Macallan 18 Year"},
        )

    def test_create_candidate_with_matched_product(self):
        """Test creating a candidate with FK to matched DiscoveredProduct."""
        candidate = ProductCandidate.objects.create(
            raw_name="The Macallan 18 Y.O.",
            normalized_name="macallan 18 year",
            source=self.crawled_source,
            extracted_data={"name": "Macallan 18"},
            match_status="matched",
            matched_product=self.discovered_product,
            match_confidence=Decimal("0.95"),
            match_method="fingerprint",
        )

        self.assertEqual(candidate.matched_product, self.discovered_product)
        self.assertEqual(candidate.matched_product.name, "Macallan 18 Year")

    def test_matched_product_can_be_null(self):
        """Test that matched_product FK can be null for unmatched candidates."""
        candidate = ProductCandidate.objects.create(
            raw_name="Unknown Product",
            normalized_name="unknown product",
            source=self.crawled_source,
            extracted_data={},
            match_status="pending",
            matched_product=None,
        )

        self.assertIsNone(candidate.matched_product)

    def test_matched_product_set_null_on_delete(self):
        """Test that matched_product is set to null when product is deleted."""
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18",
            normalized_name="macallan 18",
            source=self.crawled_source,
            extracted_data={},
            match_status="matched",
            matched_product=self.discovered_product,
            match_confidence=Decimal("0.95"),
            match_method="fingerprint",
        )

        product_id = self.discovered_product.id

        # Delete the product
        self.discovered_product.delete()

        # Candidate should still exist with null matched_product
        candidate.refresh_from_db()
        self.assertIsNone(candidate.matched_product)


class ProductCandidateMatchMethodTestCase(TestCase):
    """Test match_method field for different matching strategies."""

    def setUp(self):
        """Create required related objects for testing."""
        self.crawled_source = CrawledSource.objects.create(
            url="https://example.com/review",
            title="Test Review",
            source_type="review_article",
            extraction_status="pending",
        )

    def test_valid_match_methods(self):
        """Test all valid match_method values are accepted."""
        valid_methods = ["gtin", "fingerprint", "fuzzy", "ai", None]

        for i, method in enumerate(valid_methods):
            candidate = ProductCandidate.objects.create(
                raw_name=f"Product {i}",
                normalized_name=f"product {i}",
                source=self.crawled_source,
                extracted_data={},
                match_status="pending" if method is None else "matched",
                match_method=method,
                match_confidence=Decimal("0.0") if method is None else Decimal("0.9"),
            )
            self.assertEqual(candidate.match_method, method)

    def test_gtin_match_has_high_confidence(self):
        """Test GTIN matches are stored with high confidence."""
        candidate = ProductCandidate.objects.create(
            raw_name="Product with GTIN",
            normalized_name="product with gtin",
            source=self.crawled_source,
            extracted_data={"gtin": "12345678901234"},
            match_status="matched",
            match_method="gtin",
            match_confidence=Decimal("1.0"),
        )

        self.assertEqual(candidate.match_method, "gtin")
        self.assertEqual(candidate.match_confidence, Decimal("1.0"))


class NameNormalizationUtilityTestCase(TestCase):
    """Test name normalization utility function."""

    def test_lowercase_transformation(self):
        """Test that names are lowercased."""
        result = normalize_product_name("The MACALLAN 18 Year Old")
        self.assertTrue(result.islower())

    def test_remove_leading_the(self):
        """Test removal of leading 'the'."""
        result = normalize_product_name("The Macallan 18")
        self.assertFalse(result.startswith("the "))
        self.assertTrue(result.startswith("macallan"))

    def test_standardize_years_variations(self):
        """Test standardization of year variations."""
        test_cases = [
            ("Macallan 18 Years Old", "macallan 18 year old"),
            ("Macallan 18 Yrs Old", "macallan 18 year old"),
            ("Macallan 18yo", "macallan 18 year"),
            ("Macallan 18 Y.O.", "macallan 18 year"),
            ("Macallan 18 y/o", "macallan 18 year"),
        ]

        for input_name, expected in test_cases:
            result = normalize_product_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")

    def test_remove_trademark_symbols(self):
        """Test removal of trademark symbols."""
        test_cases = [
            ("Macallan(R) 18", "macallan 18"),
            ("Macallan(TM) 18", "macallan 18"),
        ]

        for input_name, expected in test_cases:
            result = normalize_product_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")

    def test_standardize_quotes(self):
        """Test standardization of quotes and apostrophes."""
        test_cases = [
            ("Taylor's Port", "taylors port"),
            ("Taylor's Port", "taylors port"),  # Curly apostrophe
            ('Graham"s Port', "grahams port"),
        ]

        for input_name, expected in test_cases:
            result = normalize_product_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")

    def test_remove_extra_whitespace(self):
        """Test removal of extra whitespace."""
        result = normalize_product_name("Macallan   18    Year   Old")
        self.assertNotIn("  ", result)
        self.assertEqual(result, "macallan 18 year old")

    def test_complex_normalization(self):
        """Test complex name normalization combining multiple rules."""
        input_name = "The Macallan(R) 18 Years Old Double Cask"
        expected = "macallan 18 year old double cask"
        result = normalize_product_name(input_name)
        self.assertEqual(result, expected)

    def test_empty_string(self):
        """Test handling of empty string."""
        result = normalize_product_name("")
        self.assertEqual(result, "")

    def test_whitespace_only(self):
        """Test handling of whitespace-only string."""
        result = normalize_product_name("   ")
        self.assertEqual(result, "")
