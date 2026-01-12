"""
Unit tests for DiscoveredProduct ECP fields (V3 Architecture).

Task 1.4: Update DiscoveredProduct Model

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3.2, 6.1

V3 New Fields:
- enrichment_completion: JSONField storing ECP by group
- ecp_total: DecimalField with total ECP percentage
- members_only_sites_detected: JSONField storing detected paywall URLs
- awards_search_completed: BooleanField for awards search status
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from crawler.models import (
    DiscoveredProduct,
    ProductType,
    DiscoveredBrand,
)


class DiscoveredProductECPFieldsTests(TestCase):
    """Tests for DiscoveredProduct V3 ECP fields."""

    def setUp(self):
        """Create a brand for FK relationship."""
        self.brand = DiscoveredBrand.objects.create(
            name="Test Brand",
        )

    def test_enrichment_completion_default_empty(self):
        """Test enrichment_completion defaults to empty dict."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
        )
        product.save()

        self.assertEqual(product.enrichment_completion, {})

    def test_enrichment_completion_json_structure(self):
        """Test enrichment_completion stores ECP JSON per spec."""
        ecp_data = {
            "basic_product_info": {
                "populated": 7,
                "total": 9,
                "percentage": 77.78,
                "missing": ["bottler", "age_statement"]
            },
            "tasting_nose": {
                "populated": 3,
                "total": 5,
                "percentage": 60.0,
                "missing": ["primary_intensity", "aroma_evolution"]
            },
            "total": {
                "populated": 32,
                "total": 59,
                "percentage": 54.24
            },
            "last_updated": "2026-01-12T10:30:00Z"
        }

        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
            enrichment_completion=ecp_data,
        )
        product.save()

        # Reload to verify persistence
        product.refresh_from_db()

        self.assertEqual(product.enrichment_completion["basic_product_info"]["percentage"], 77.78)
        self.assertEqual(product.enrichment_completion["tasting_nose"]["missing"], ["primary_intensity", "aroma_evolution"])
        self.assertEqual(product.enrichment_completion["total"]["percentage"], 54.24)

    def test_ecp_total_default_zero(self):
        """Test ecp_total defaults to 0."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
        )
        product.save()

        self.assertEqual(product.ecp_total, Decimal("0"))

    def test_ecp_total_decimal_precision(self):
        """Test ecp_total stores decimal with 2 places."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
            ecp_total=Decimal("87.56"),
        )
        product.save()
        product.refresh_from_db()

        self.assertEqual(product.ecp_total, Decimal("87.56"))

    def test_ecp_total_90_threshold(self):
        """Test ecp_total can store values at and above 90% threshold."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
            ecp_total=Decimal("91.50"),
        )
        product.save()
        product.refresh_from_db()

        self.assertEqual(product.ecp_total, Decimal("91.50"))
        self.assertGreaterEqual(product.ecp_total, Decimal("90.0"))

    def test_members_only_sites_detected_default_empty(self):
        """Test members_only_sites_detected defaults to empty list."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
        )
        product.save()

        self.assertEqual(product.members_only_sites_detected, [])

    def test_members_only_sites_detected_stores_urls(self):
        """Test members_only_sites_detected stores detected paywall URLs."""
        detected_sites = [
            "https://smws.com/product/1.292",
            "https://members.whiskyadvocate.com/review",
        ]

        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
            members_only_sites_detected=detected_sites,
        )
        product.save()
        product.refresh_from_db()

        self.assertEqual(len(product.members_only_sites_detected), 2)
        self.assertIn("https://smws.com/product/1.292", product.members_only_sites_detected)

    def test_awards_search_completed_default_false(self):
        """Test awards_search_completed defaults to False."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
        )
        product.save()

        self.assertFalse(product.awards_search_completed)

    def test_awards_search_completed_can_be_true(self):
        """Test awards_search_completed can be set to True."""
        product = DiscoveredProduct(
            name="Test Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test",
            raw_content="test content",
            awards_search_completed=True,
        )
        product.save()
        product.refresh_from_db()

        self.assertTrue(product.awards_search_completed)


class DiscoveredProductECPIndexTests(TestCase):
    """Tests for ECP field indexing."""

    def test_ecp_total_indexed_for_queries(self):
        """Test that ecp_total is indexed (can be queried efficiently)."""
        # Create products with different ECP values
        for ecp in [45.0, 67.5, 89.0, 92.5]:
            DiscoveredProduct.objects.create(
                name=f"Product {ecp}%",
                product_type=ProductType.WHISKEY,
                source_url=f"https://example.com/{ecp}",
                raw_content="test",
                ecp_total=Decimal(str(ecp)),
            )

        # Query by ECP threshold
        complete_products = DiscoveredProduct.objects.filter(
            ecp_total__gte=Decimal("90.0")
        )
        partial_products = DiscoveredProduct.objects.filter(
            ecp_total__lt=Decimal("90.0")
        )

        self.assertEqual(complete_products.count(), 1)
        self.assertEqual(partial_products.count(), 3)


class DiscoveredProductECPQueryTests(TestCase):
    """Tests for ECP-based queries."""

    def test_filter_by_ecp_complete(self):
        """Test filtering products that are ECP COMPLETE (90%+)."""
        # Create products
        DiscoveredProduct.objects.create(
            name="Incomplete Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/1",
            raw_content="test",
            ecp_total=Decimal("45.0"),
        )
        DiscoveredProduct.objects.create(
            name="Near Complete Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/2",
            raw_content="test",
            ecp_total=Decimal("89.5"),
        )
        DiscoveredProduct.objects.create(
            name="Complete Product",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/3",
            raw_content="test",
            ecp_total=Decimal("92.3"),
        )

        complete = DiscoveredProduct.objects.filter(ecp_total__gte=90)
        self.assertEqual(complete.count(), 1)
        self.assertEqual(complete.first().name, "Complete Product")

    def test_order_by_ecp_total(self):
        """Test ordering products by ECP total."""
        DiscoveredProduct.objects.create(
            name="Low ECP",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/1",
            raw_content="test",
            ecp_total=Decimal("30.0"),
        )
        DiscoveredProduct.objects.create(
            name="High ECP",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/2",
            raw_content="test",
            ecp_total=Decimal("95.0"),
        )
        DiscoveredProduct.objects.create(
            name="Medium ECP",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/3",
            raw_content="test",
            ecp_total=Decimal("65.0"),
        )

        ordered = DiscoveredProduct.objects.order_by("-ecp_total")
        self.assertEqual(ordered[0].name, "High ECP")
        self.assertEqual(ordered[1].name, "Medium ECP")
        self.assertEqual(ordered[2].name, "Low ECP")
