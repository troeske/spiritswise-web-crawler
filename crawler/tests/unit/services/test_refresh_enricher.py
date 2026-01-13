"""
Unit tests for RefreshEnricher Service.

Task 4.1-4.3: Tests for refresh enrichment with confidence-aware merging.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 5.2, 5.3
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from django.test import TestCase
from django.utils.text import slugify
from asgiref.sync import async_to_sync

from crawler.models import DiscoveredProduct, DiscoveredBrand


def create_brand(name: str) -> DiscoveredBrand:
    """Helper to create DiscoveredBrand with unique slug."""
    slug = slugify(name)
    existing = DiscoveredBrand.objects.filter(slug=slug).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:8]}"
    return DiscoveredBrand.objects.create(name=name, slug=slug)


class RefreshEnricherInitializationTests(TestCase):
    """Tests for RefreshEnricher initialization."""

    def test_refresher_initialization(self):
        """Test RefreshEnricher initializes correctly."""
        from crawler.services.refresh_enricher import RefreshEnricher

        refresher = RefreshEnricher()
        self.assertIsNotNone(refresher)


class RecentSearchTemplatesTests(TestCase):
    """Tests for recent review search templates (Task 4.2)."""

    def test_recent_review_search_templates(self):
        """Test search templates include year filters."""
        from crawler.services.refresh_enricher import get_recent_search_templates

        templates = get_recent_search_templates(2025)

        # Should contain year references
        self.assertTrue(
            any("2024" in t or "2025" in t for t in templates),
            "Templates should include recent years"
        )

        # Should contain recency keywords
        all_templates = " ".join(templates).lower()
        self.assertTrue(
            any(kw in all_templates for kw in ["latest", "recent", "new"]),
            "Templates should include recency keywords"
        )


class ConfidenceAwareMergeTests(TestCase):
    """Tests for confidence-aware merge logic (Task 4.3)."""

    def test_preserve_high_confidence_fields(self):
        """Test high-confidence fields are preserved during merge."""
        from crawler.services.refresh_enricher import RefreshEnricher

        existing_data = {"name": "Macallan 18", "abv": 43.0}
        existing_confidences = {"name": 0.95, "abv": 0.90}

        new_data = {"name": "The Macallan 18 Years", "abv": 43.0, "awards": ["Gold"]}
        new_confidences = {"name": 0.80, "abv": 0.80, "awards": 0.85}

        refresher = RefreshEnricher()
        merged, merged_confidences = async_to_sync(refresher._merge_with_existing)(
            existing_data, existing_confidences,
            new_data, new_confidences
        )

        # Name should be preserved (existing confidence higher)
        self.assertEqual(merged["name"], "Macallan 18")
        # Awards should be added (new field)
        self.assertEqual(merged["awards"], ["Gold"])

    def test_merge_array_fields(self):
        """Test array fields are union-merged."""
        from crawler.services.refresh_enricher import RefreshEnricher

        existing_data = {"primary_aromas": ["vanilla", "oak"]}
        new_data = {"primary_aromas": ["oak", "honey", "spice"]}

        refresher = RefreshEnricher()
        merged, _ = async_to_sync(refresher._merge_with_existing)(
            existing_data, {"primary_aromas": 0.7},
            new_data, {"primary_aromas": 0.8}
        )

        # Should union-merge arrays
        self.assertEqual(
            set(merged["primary_aromas"]),
            {"vanilla", "oak", "honey", "spice"}
        )

    def test_new_fields_always_added(self):
        """Test new fields are always added."""
        from crawler.services.refresh_enricher import RefreshEnricher

        existing_data = {"name": "Test", "abv": 40.0}
        existing_confidences = {"name": 0.9, "abv": 0.9}

        new_data = {"description": "A fine whiskey", "region": "Scotland"}
        new_confidences = {"description": 0.75, "region": 0.80}

        refresher = RefreshEnricher()
        merged, _ = async_to_sync(refresher._merge_with_existing)(
            existing_data, existing_confidences,
            new_data, new_confidences
        )

        # New fields should be added
        self.assertEqual(merged["description"], "A fine whiskey")
        self.assertEqual(merged["region"], "Scotland")
        # Existing fields preserved
        self.assertEqual(merged["name"], "Test")
        self.assertEqual(merged["abv"], 40.0)


class RefreshProductTests(TestCase):
    """Tests for refresh_product method (Task 4.1)."""

    def setUp(self):
        """Set up test fixtures."""
        self.brand = create_brand("TestBrand")

    def test_refresh_product_recent_reviews(self):
        """Test refresh_product adds new data from recent reviews."""
        from crawler.services.refresh_enricher import RefreshEnricher

        existing = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=self.brand,
            product_type="whiskey",
            status="partial",
        )
        # Set aromas manually on instance
        existing.primary_aromas = ["vanilla", "oak"]

        new_extraction = {
            "primary_aromas": ["vanilla", "oak", "honey"],
            "description": "A wonderful whiskey"
        }

        refresher = RefreshEnricher()
        result = async_to_sync(refresher.refresh_product)(
            existing_product=existing,
            new_extraction=new_extraction,
            new_confidences={"primary_aromas": 0.85, "description": 0.80},
            focus_recent=True
        )

        # Should have merged aromas
        self.assertIn("honey", result.product_data.get("primary_aromas", []))
        # Description should be added
        self.assertEqual(result.product_data.get("description"), "A wonderful whiskey")


class IdentityFieldPreservationTests(TestCase):
    """Tests for identity field preservation."""

    def test_identity_fields_never_overwritten(self):
        """Test identity fields (name, brand) are never overwritten."""
        from crawler.services.refresh_enricher import RefreshEnricher

        existing_data = {"name": "Original Name", "brand": "Original Brand", "abv": 40.0}
        existing_confidences = {"name": 0.6, "brand": 0.6, "abv": 0.6}

        # New data has higher confidence on name/brand
        new_data = {"name": "Different Name", "brand": "Different Brand", "abv": 43.0}
        new_confidences = {"name": 0.95, "brand": 0.95, "abv": 0.95}

        refresher = RefreshEnricher()
        merged, _ = async_to_sync(refresher._merge_with_existing)(
            existing_data, existing_confidences,
            new_data, new_confidences
        )

        # Identity fields should be preserved
        self.assertEqual(merged["name"], "Original Name")
        self.assertEqual(merged["brand"], "Original Brand")
        # Non-identity fields can be overwritten
        self.assertEqual(merged["abv"], 43.0)
