"""
Tests for Skeleton Deduplication Fix.

Fix 2 of Duplicate Crawling Fixes: SkeletonProductManager should check for
existing products regardless of status, not just status=SKELETON.

This prevents duplicate skeletons from being created when the same award
is crawled again after a skeleton was enriched (status changed to PENDING/APPROVED).
"""

import pytest
from django.db.models import Q

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductAward,
    ProductType,
)
from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager


@pytest.mark.django_db
class TestSkeletonDeduplication:
    """Tests for skeleton deduplication across all product statuses."""

    def test_finds_existing_by_fingerprint_any_status(self):
        """Should find existing product regardless of status."""
        manager = SkeletonProductManager()

        # Create initial skeleton product
        award_data = {
            "product_name": "Macallan 18",
            "producer": "Macallan",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
            "category": "Single Malt Scotch",
        }
        product = manager.create_skeleton_product(award_data)
        original_id = product.id

        # Change status to PENDING (simulating enrichment)
        product.status = DiscoveredProductStatus.PENDING
        product.save(update_fields=["status"])

        # Try to create skeleton with same fingerprint
        # Should NOT create duplicate, should return existing
        result = manager.create_skeleton_product(award_data)

        assert result.id == original_id, "Should return existing product, not create new"
        assert result.status == DiscoveredProductStatus.PENDING, "Status should remain PENDING"

        # Verify no duplicate was created
        products = DiscoveredProduct.objects.filter(name="Macallan 18")
        assert products.count() == 1, "Should have exactly 1 product, not duplicates"

    def test_finds_existing_by_name(self):
        """Should find existing product by name match."""
        manager = SkeletonProductManager()

        # Create initial skeleton product
        award_data_1 = {
            "product_name": "Glenmorangie Signet",
            "producer": "Glenmorangie",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product = manager.create_skeleton_product(award_data_1)
        original_id = product.id

        # Change status to APPROVED
        product.status = DiscoveredProductStatus.APPROVED
        product.save(update_fields=["status"])

        # Try to create skeleton with same name
        # (producer slightly different to test name matching)
        award_data_2 = {
            "product_name": "Glenmorangie Signet",
            "producer": "Glenmorangie Distillery",  # Slightly different producer
            "competition": "World Whiskies Awards",
            "year": 2024,
            "medal": "Gold",
        }
        result = manager.create_skeleton_product(award_data_2)

        assert result.id == original_id, "Should return existing product by name match"

        # Verify no duplicate was created
        products = DiscoveredProduct.objects.filter(name__icontains="Glenmorangie Signet")
        assert products.count() == 1, "Should have exactly 1 product"

    def test_adds_award_to_pending_product(self):
        """Should add award to enriched (pending) product."""
        manager = SkeletonProductManager()

        # Create initial skeleton and change to PENDING
        award_data_1 = {
            "product_name": "Talisker 18",
            "producer": "Talisker",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product = manager.create_skeleton_product(award_data_1)
        original_id = product.id

        # Simulate enrichment by changing status
        product.status = DiscoveredProductStatus.PENDING
        product.save(update_fields=["status"])

        # Initial award count
        initial_award_count = ProductAward.objects.filter(product=product).count()
        assert initial_award_count == 1

        # Add second award via create_skeleton_product
        award_data_2 = {
            "product_name": "Talisker 18",
            "producer": "Talisker",
            "competition": "World Whiskies Awards",
            "year": 2024,
            "medal": "Gold",
        }
        result = manager.create_skeleton_product(award_data_2)

        # Should be same product
        assert result.id == original_id

        # Award should be added
        final_award_count = ProductAward.objects.filter(product=product).count()
        assert final_award_count == 2, "Should have 2 awards now"

        # Verify the second award was created
        awards = ProductAward.objects.filter(product=product)
        competitions = [a.competition for a in awards]
        assert "IWSC" in competitions
        assert "World Whiskies Awards" in competitions

    def test_adds_award_to_approved_product(self):
        """Should add award to approved product."""
        manager = SkeletonProductManager()

        # Create initial skeleton and change to APPROVED
        award_data_1 = {
            "product_name": "Lagavulin 12 Cask Strength",
            "producer": "Lagavulin",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product = manager.create_skeleton_product(award_data_1)
        original_id = product.id

        # Simulate approval
        product.status = DiscoveredProductStatus.APPROVED
        product.save(update_fields=["status"])

        # Add second award via create_skeleton_product
        award_data_2 = {
            "product_name": "Lagavulin 12 Cask Strength",
            "producer": "Lagavulin",
            "competition": "San Francisco World Spirits",
            "year": 2024,
            "medal": "Double Gold",
        }
        result = manager.create_skeleton_product(award_data_2)

        # Should be same product
        assert result.id == original_id

        # Status should remain APPROVED
        result.refresh_from_db()
        assert result.status == DiscoveredProductStatus.APPROVED

        # Award should be added
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() == 2

    def test_does_not_create_duplicate_for_rejected_product(self):
        """Should not create duplicate for rejected products either."""
        manager = SkeletonProductManager()

        # Create initial skeleton
        award_data = {
            "product_name": "Ardbeg Corryvreckan",
            "producer": "Ardbeg",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product = manager.create_skeleton_product(award_data)
        original_id = product.id

        # Mark as rejected
        product.status = DiscoveredProductStatus.REJECTED
        product.save(update_fields=["status"])

        # Try to create again
        result = manager.create_skeleton_product(award_data)

        # Should return existing, not create duplicate
        assert result.id == original_id

        # Verify no duplicate
        products = DiscoveredProduct.objects.filter(name="Ardbeg Corryvreckan")
        assert products.count() == 1

    def test_still_creates_new_for_truly_new_product(self):
        """Should still create new skeleton for truly new products."""
        manager = SkeletonProductManager()

        # Create first product
        award_data_1 = {
            "product_name": "Highland Park 18",
            "producer": "Highland Park",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product_1 = manager.create_skeleton_product(award_data_1)

        # Create different product
        award_data_2 = {
            "product_name": "Springbank 15",
            "producer": "Springbank",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Silver",
        }
        product_2 = manager.create_skeleton_product(award_data_2)

        # Should be different products
        assert product_1.id != product_2.id

        # Verify both exist
        assert DiscoveredProduct.objects.filter(name="Highland Park 18").exists()
        assert DiscoveredProduct.objects.filter(name="Springbank 15").exists()

    def test_discovery_sources_updated_when_adding_award_to_existing(self):
        """Should ensure 'competition' is in discovery_sources when adding award."""
        manager = SkeletonProductManager()

        # Create initial skeleton
        award_data_1 = {
            "product_name": "Bowmore 15",
            "producer": "Bowmore",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product = manager.create_skeleton_product(award_data_1)

        # Change status and clear discovery_sources to simulate edge case
        product.status = DiscoveredProductStatus.PENDING
        product.discovery_sources = ["search"]  # Only search, no competition
        product.save(update_fields=["status", "discovery_sources"])

        # Add award via create_skeleton_product
        award_data_2 = {
            "product_name": "Bowmore 15",
            "producer": "Bowmore",
            "competition": "World Whiskies Awards",
            "year": 2024,
            "medal": "Gold",
        }
        result = manager.create_skeleton_product(award_data_2)

        # Refresh and check discovery_sources
        result.refresh_from_db()
        assert "competition" in result.discovery_sources, (
            "Should have 'competition' in discovery_sources"
        )
