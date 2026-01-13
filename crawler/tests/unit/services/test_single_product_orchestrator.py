"""
Unit tests for SingleProductOrchestrator Service.

Task 3.1: Tests for orchestrator initialization and basic functionality.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 8.2
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from django.utils.text import slugify
from asgiref.sync import async_to_sync

from crawler.models import (
    CrawlSchedule,
    CrawlJob,
    DiscoveredProduct,
    DiscoveredBrand,
    ScheduleCategory,
)


def create_brand(name: str) -> DiscoveredBrand:
    """Helper to create DiscoveredBrand with unique slug."""
    slug = slugify(name)
    existing = DiscoveredBrand.objects.filter(slug=slug).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:8]}"
    return DiscoveredBrand.objects.create(name=name, slug=slug)


class OrchestratorInitializationTests(TestCase):
    """Tests for SingleProductOrchestrator initialization (Task 3.1)."""

    def test_orchestrator_initialization(self):
        """Test SingleProductOrchestrator initializes correctly."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator

        orchestrator = SingleProductOrchestrator()
        self.assertIsNotNone(orchestrator)
        self.assertIsNotNone(orchestrator.product_matcher)
        self.assertIsNotNone(orchestrator.quality_gate)

    def test_orchestrator_with_custom_dependencies(self):
        """Test orchestrator accepts custom dependencies."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator
        from crawler.services.product_matcher import ProductMatcher

        custom_matcher = ProductMatcher()
        orchestrator = SingleProductOrchestrator(product_matcher=custom_matcher)

        self.assertIs(orchestrator.product_matcher, custom_matcher)


class ProcessProductEntryTests(TestCase):
    """Tests for process_product_entry method (Task 3.3)."""

    def setUp(self):
        """Set up test fixtures."""
        self.brand = create_brand("The Macallan")

    @patch('crawler.services.single_product_orchestrator.SingleProductOrchestrator._search_for_product')
    @patch('crawler.services.single_product_orchestrator.SingleProductOrchestrator._fetch_and_extract')
    def test_process_product_entry_new_product(self, mock_fetch, mock_search):
        """Test process_product_entry creates new product."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator

        # Mock search returns URLs
        mock_search.return_value = ["https://example.com/macallan-18"]

        # Mock extraction returns product data
        mock_fetch.return_value = ({
            "name": "Macallan 18",
            "brand": "The Macallan",
            "abv": 43.0,
        }, {"name": 0.9, "brand": 0.9, "abv": 0.85})

        orchestrator = SingleProductOrchestrator()

        result = async_to_sync(orchestrator.process_product_entry)(
            product_entry={
                "name": "Macallan 18",
                "brand": "The Macallan",
                "product_type": "whiskey"
            },
            config={}
        )

        self.assertTrue(result.success)
        self.assertTrue(result.is_new_product)
        self.assertIsNotNone(result.product_id)
        self.assertEqual(result.product_name, "Macallan 18")

    def test_process_product_entry_existing_product(self):
        """Test process_product_entry finds existing product."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator
        from crawler.services.product_matcher import ProductMatcher

        # Create existing product with fingerprint
        matcher = ProductMatcher()
        fingerprint = matcher._compute_fingerprint({
            "name": "Macallan 18",
            "brand": "The Macallan"
        })
        existing = DiscoveredProduct.objects.create(
            name="Macallan 18",
            brand=self.brand,
            product_type="whiskey",
            fingerprint=fingerprint,
        )

        orchestrator = SingleProductOrchestrator()

        result = async_to_sync(orchestrator.process_product_entry)(
            product_entry={
                "name": "Macallan 18",
                "brand": "The Macallan",
                "product_type": "whiskey"
            },
            config={}
        )

        self.assertTrue(result.success)
        self.assertFalse(result.is_new_product)
        self.assertEqual(result.product_id, existing.id)


class ProcessScheduleTests(TestCase):
    """Tests for process_schedule method (Task 3.4)."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Single Product Schedule",
            slug=f"test-sp-{uuid4().hex[:8]}",
            category=ScheduleCategory.SINGLE_PRODUCT,
            search_terms=[
                {"name": "Macallan 18", "brand": "The Macallan", "product_type": "whiskey"},
                {"name": "Glenfiddich 21", "brand": "Glenfiddich", "product_type": "whiskey"},
                {"name": "Lagavulin 16", "brand": "Lagavulin", "product_type": "whiskey"},
            ],
        )
        self.job = CrawlJob.objects.create(schedule=self.schedule)

    @patch('crawler.services.single_product_orchestrator.SingleProductOrchestrator.process_product_entry')
    def test_process_schedule_multiple_products(self, mock_process):
        """Test process_schedule processes all entries."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator
        from crawler.services.single_product_types import SingleProductResult

        # Mock process_product_entry returns success
        mock_process.return_value = SingleProductResult(
            success=True,
            is_new_product=True,
            product_id=uuid4(),
            product_name="Test",
        )

        orchestrator = SingleProductOrchestrator()

        result = async_to_sync(orchestrator.process_schedule)(
            self.schedule, self.job
        )

        self.assertEqual(result.products_processed, 3)
        self.assertEqual(len(result.results), 3)
        self.assertTrue(result.success)


class SkipRecentlyEnrichedTests(TestCase):
    """Tests for skip_if_enriched_within_days logic (Task 3.5)."""

    def setUp(self):
        """Set up test fixtures."""
        self.brand = create_brand("Test Brand")

    def test_skip_recently_enriched(self):
        """Test products enriched recently are skipped."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator
        from crawler.services.product_matcher import ProductMatcher

        # Create product enriched 10 days ago
        matcher = ProductMatcher()
        fingerprint = matcher._compute_fingerprint({
            "name": "Recent Product",
            "brand": "Test Brand"
        })
        existing = DiscoveredProduct.objects.create(
            name="Recent Product",
            brand=self.brand,
            product_type="whiskey",
            fingerprint=fingerprint,
            last_enrichment_at=timezone.now() - timedelta(days=10),
        )

        orchestrator = SingleProductOrchestrator()

        result = async_to_sync(orchestrator.process_product_entry)(
            product_entry={
                "name": "Recent Product",
                "brand": "Test Brand",
                "product_type": "whiskey"
            },
            config={"skip_if_enriched_within_days": 30}
        )

        self.assertTrue(result.success)
        self.assertFalse(result.is_new_product)
        # Should be skipped due to recent enrichment
        self.assertIn("skipped_recent_enrichment", result.warnings or [])

    def test_enrich_if_not_recent(self):
        """Test old products are re-enriched."""
        from crawler.services.single_product_orchestrator import SingleProductOrchestrator
        from crawler.services.product_matcher import ProductMatcher

        # Create product enriched 60 days ago
        matcher = ProductMatcher()
        fingerprint = matcher._compute_fingerprint({
            "name": "Old Product",
            "brand": "Test Brand"
        })
        existing = DiscoveredProduct.objects.create(
            name="Old Product",
            brand=self.brand,
            product_type="whiskey",
            fingerprint=fingerprint,
            last_enrichment_at=timezone.now() - timedelta(days=60),
        )

        orchestrator = SingleProductOrchestrator()

        with patch.object(orchestrator, '_search_for_product', return_value=[]):
            result = async_to_sync(orchestrator.process_product_entry)(
                product_entry={
                    "name": "Old Product",
                    "brand": "Test Brand",
                    "product_type": "whiskey"
                },
                config={"skip_if_enriched_within_days": 30}
            )

        self.assertTrue(result.success)
        self.assertFalse(result.is_new_product)
        # Should NOT be skipped (old enough to re-enrich)
        self.assertNotIn("skipped_recent_enrichment", result.warnings or [])
