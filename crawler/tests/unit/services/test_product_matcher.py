"""
Unit tests for ProductMatcher Service.

Task 2.1-2.2: Tests for product matching with GTIN, fingerprint, and fuzzy name.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 4.1
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from django.test import TestCase
from django.utils.text import slugify
from asgiref.sync import async_to_sync

from crawler.models import DiscoveredProduct, DiscoveredBrand
from crawler.services.product_matcher import (
    ProductMatcher,
    get_product_matcher,
    reset_product_matcher,
)


def create_brand(name: str) -> DiscoveredBrand:
    """Helper to create DiscoveredBrand with unique slug."""
    slug = slugify(name)
    # Ensure unique slug by appending uuid if exists
    existing = DiscoveredBrand.objects.filter(slug=slug).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:8]}"
    return DiscoveredBrand.objects.create(name=name, slug=slug)


class ProductMatcherInitializationTests(TestCase):
    """Tests for ProductMatcher initialization."""

    def test_matcher_initialization(self):
        """Test ProductMatcher initializes correctly."""
        matcher = ProductMatcher()
        self.assertIsNotNone(matcher)

    def test_singleton_getter(self):
        """Test singleton getter returns same instance."""
        reset_product_matcher()
        instance1 = get_product_matcher()
        instance2 = get_product_matcher()
        self.assertIs(instance1, instance2)

    def test_singleton_reset(self):
        """Test singleton reset creates new instance."""
        instance1 = get_product_matcher()
        reset_product_matcher()
        instance2 = get_product_matcher()
        self.assertIsNot(instance1, instance2)


class GTINMatchingTests(TestCase):
    """Tests for GTIN matching (Task 2.1)."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()
        self.brand = create_brand("Test Brand")

    def test_gtin_match_found(self):
        """Test GTIN matching finds existing product."""
        # Create product with GTIN
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=self.brand,
            product_type="whiskey",
            gtin="1234567890123",
        )

        # Find match
        result = async_to_sync(self.matcher.find_match)(
            {"gtin": "1234567890123", "name": "Test Whiskey"},
            product_type="whiskey"
        )

        matched_product, method, confidence = result
        self.assertEqual(matched_product.id, product.id)
        self.assertEqual(method, "gtin")
        self.assertEqual(confidence, 1.0)

    def test_gtin_no_match(self):
        """Test GTIN matching returns None when no match."""
        result = async_to_sync(self.matcher.find_match)(
            {"gtin": "9999999999999", "name": "Test"},
            product_type="whiskey"
        )

        matched_product, method, confidence = result
        self.assertIsNone(matched_product)
        self.assertEqual(method, "none")
        self.assertEqual(confidence, 0.0)


class FingerprintMatchingTests(TestCase):
    """Tests for fingerprint matching (Task 2.1)."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()
        self.brand = create_brand("The Macallan")

    def test_fingerprint_match_found(self):
        """Test fingerprint matching finds existing product."""
        # Create product and compute its fingerprint
        fingerprint = self.matcher._compute_fingerprint({
            "name": "Macallan 18",
            "brand": "The Macallan"
        })

        product = DiscoveredProduct.objects.create(
            name="Macallan 18",
            brand=self.brand,
            product_type="whiskey",
            fingerprint=fingerprint,
        )

        # Find match
        result = async_to_sync(self.matcher.find_match)(
            {"name": "Macallan 18", "brand": "The Macallan"},
            product_type="whiskey"
        )

        matched_product, method, confidence = result
        self.assertEqual(matched_product.id, product.id)
        self.assertEqual(method, "fingerprint")
        self.assertEqual(confidence, 0.95)


class FuzzyNameMatchingTests(TestCase):
    """Tests for fuzzy name matching with brand filter (Task 2.2)."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()
        self.macallan_brand = create_brand("The Macallan")
        self.glenfiddich_brand = create_brand("Glenfiddich")
        self.test_brand = create_brand("Test Brand")

    def test_fuzzy_match_same_brand(self):
        """Test fuzzy match works when brand matches."""
        # Create existing product
        product = DiscoveredProduct.objects.create(
            name="Macallan 18 Year Old Sherry Oak",
            brand=self.macallan_brand,
            product_type="whiskey",
        )

        # Find with slightly different name, same brand
        result = async_to_sync(self.matcher.find_match)(
            {"name": "The Macallan 18", "brand": "The Macallan"},
            product_type="whiskey"
        )

        matched_product, method, confidence = result
        self.assertEqual(matched_product.id, product.id)
        self.assertEqual(method, "fuzzy_name")
        self.assertGreaterEqual(confidence, 0.85)

    def test_fuzzy_match_different_brand_no_match(self):
        """Test fuzzy match fails when brand differs."""
        # Create product with specific brand
        DiscoveredProduct.objects.create(
            name="Macallan 18",
            brand=self.macallan_brand,
            product_type="whiskey",
        )

        # Search with different brand
        result = async_to_sync(self.matcher.find_match)(
            {"name": "Macallan 18", "brand": "Glenfiddich"},
            product_type="whiskey"
        )

        matched_product, method, confidence = result
        # Should not match due to brand mismatch
        self.assertIsNone(matched_product)

    def test_fuzzy_match_product_type_filter(self):
        """Test fuzzy match respects product type filter."""
        # Create whiskey product
        DiscoveredProduct.objects.create(
            name="Test Product",
            brand=self.test_brand,
            product_type="whiskey",
        )

        # Search in different product type
        result = async_to_sync(self.matcher.find_match)(
            {"name": "Test Product", "brand": "Test Brand"},
            product_type="port_wine"
        )

        matched_product, method, confidence = result
        self.assertIsNone(matched_product)


class ConfidenceCalculationTests(TestCase):
    """Tests for confidence score calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()

    def test_brand_match_boosts_confidence(self):
        """Test brand match adds confidence boost."""
        confidence = self.matcher._calculate_match_confidence(
            search_name="Macallan 18",
            search_brand="The Macallan",
            candidate_name="Macallan 18 Year",
            candidate_brand="The Macallan",
        )

        # Should include brand boost
        self.assertGreater(confidence, ProductMatcher.FUZZY_NAME_BASE_CONFIDENCE)

    def test_no_brand_match_lower_confidence(self):
        """Test missing brand match results in lower confidence."""
        confidence_with_brand = self.matcher._calculate_match_confidence(
            search_name="Macallan 18",
            search_brand="The Macallan",
            candidate_name="Macallan 18",
            candidate_brand="The Macallan",
        )

        confidence_without_brand = self.matcher._calculate_match_confidence(
            search_name="Macallan 18",
            search_brand=None,
            candidate_name="Macallan 18",
            candidate_brand="The Macallan",
        )

        self.assertGreater(confidence_with_brand, confidence_without_brand)


class FingerprintComputationTests(TestCase):
    """Tests for fingerprint computation."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()

    def test_compute_fingerprint(self):
        """Test fingerprint computation returns consistent hash."""
        data = {"name": "Test Whiskey", "brand": "Test Brand"}

        fp1 = self.matcher._compute_fingerprint(data)
        fp2 = self.matcher._compute_fingerprint(data)

        self.assertEqual(fp1, fp2)
        self.assertIsNotNone(fp1)
        self.assertEqual(len(fp1), 32)  # Truncated SHA256

    def test_fingerprint_case_insensitive(self):
        """Test fingerprint is case-insensitive."""
        fp1 = self.matcher._compute_fingerprint({"name": "Test", "brand": "Brand"})
        fp2 = self.matcher._compute_fingerprint({"name": "TEST", "brand": "BRAND"})

        self.assertEqual(fp1, fp2)

    def test_fingerprint_empty_name_returns_none(self):
        """Test empty name returns None fingerprint."""
        fp = self.matcher._compute_fingerprint({"name": "", "brand": "Brand"})
        self.assertIsNone(fp)


class FirstSignificantWordTests(TestCase):
    """Tests for extracting first significant word."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()

    def test_skips_articles(self):
        """Test first significant word skips articles."""
        word = self.matcher._get_first_significant_word("The Macallan 18")
        self.assertEqual(word, "macallan")

    def test_handles_no_articles(self):
        """Test handles names without articles."""
        word = self.matcher._get_first_significant_word("Lagavulin 16")
        self.assertEqual(word, "lagavulin")

    def test_handles_empty_string(self):
        """Test handles empty string."""
        word = self.matcher._get_first_significant_word("")
        self.assertIsNone(word)


class FindOrCreateTests(TestCase):
    """Tests for find_or_create method."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ProductMatcher()
        self.brand = create_brand("Brand")

    def test_find_or_create_finds_existing(self):
        """Test find_or_create returns existing product."""
        # Create existing product with fingerprint
        fingerprint = self.matcher._compute_fingerprint({
            "name": "Test",
            "brand": "Brand"
        })
        existing = DiscoveredProduct.objects.create(
            name="Test",
            brand=self.brand,
            product_type="whiskey",
            fingerprint=fingerprint,
        )

        product, is_new = async_to_sync(self.matcher.find_or_create)(
            {"name": "Test", "brand": "Brand"},
            product_type="whiskey",
            source_url="https://example.com",
        )

        self.assertEqual(product.id, existing.id)
        self.assertFalse(is_new)

    def test_find_or_create_creates_new(self):
        """Test find_or_create creates new product when no match."""
        product, is_new = async_to_sync(self.matcher.find_or_create)(
            {"name": "New Product", "brand": "New Brand"},
            product_type="whiskey",
            source_url="https://example.com/new",
        )

        self.assertIsNotNone(product.id)
        self.assertTrue(is_new)
        self.assertEqual(product.name, "New Product")
