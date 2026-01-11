"""
Status Model TDD Tests - Phase 3

Spec Reference: docs/spec-parts/05-UNIFIED-ARCHITECTURE.md, Section 5.3

These tests verify that status determination matches the spec exactly.
Written FIRST according to TDD methodology.

Status Determination Rules:
| Status     | Score | Requirements                              |
|------------|-------|-------------------------------------------|
| INCOMPLETE | 0-29  | Missing critical data, no palate profile  |
| PARTIAL    | 30-59 | Has basic data but no tasting profile     |
| COMPLETE   | 60-79 | **HAS palate tasting profile**            |
| VERIFIED   | 80-100| Full tasting + multi-source verified      |
| REJECTED   | N/A   | Marked as not a valid product             |
| MERGED     | N/A   | Merged into another product               |

CRITICAL: A product CANNOT reach COMPLETE or VERIFIED without palate tasting data.
has_palate = palate_flavors OR palate_description OR initial_taste
"""

from decimal import Decimal
from django.test import TestCase

from crawler.models import DiscoveredProduct, DiscoveredBrand


class TestStatusIncomplete(TestCase):
    """Tests for INCOMPLETE status (score 0-29)."""

    def test_score_0_is_incomplete(self):
        """Spec: Score 0 = INCOMPLETE"""
        product = DiscoveredProduct.objects.create()
        status = product.determine_status()
        self.assertEqual(status, "incomplete")

    def test_score_29_is_incomplete(self):
        """Spec: Score 29 (max boundary) = INCOMPLETE"""
        # Create product with score ~29
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",  # 10 points
            product_type="whiskey",  # 5 points
            abv=Decimal("43.0"),  # 5 points
            description="A fine whiskey.",  # 5 points
            # Total: 25 points = INCOMPLETE
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        status = product.determine_status()
        self.assertEqual(status, "incomplete")

    def test_no_palate_under_30_is_incomplete(self):
        """Spec: Without palate, score < 30 = INCOMPLETE"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",  # 10 points
            product_type="whiskey",  # 5 points
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        status = product.determine_status()
        self.assertEqual(status, "incomplete")


class TestStatusPartial(TestCase):
    """Tests for PARTIAL status (score 30-59 OR score >= 30 without palate)."""

    def test_score_30_without_palate_is_partial(self):
        """Spec: Score 30 (min boundary) without palate = PARTIAL"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",  # 10 points
            brand=brand,  # 5 points
            product_type="whiskey",  # 5 points
            abv=Decimal("43.0"),  # 5 points
            description="A fine whiskey.",  # 5 points
            # No palate data
            # Total: 30 points
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        status = product.determine_status()
        self.assertEqual(status, "partial")

    def test_score_59_without_palate_is_partial(self):
        """Spec: Score 59 (max boundary) without palate = PARTIAL"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
            # Nose section (no palate)
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish section
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            # Enrichment
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            # NO PALATE DATA
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        status = product.determine_status()
        self.assertEqual(status, "partial")

    def test_high_score_without_palate_is_partial_not_complete(self):
        """
        Spec CRITICAL: Score 70+ but no palate = PARTIAL not COMPLETE.
        This is the key rule - palate is MANDATORY for COMPLETE/VERIFIED.
        """
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",  # 10
            brand=brand,  # 5
            product_type="whiskey",  # 5
            abv=Decimal("43.0"),  # 5
            description="A fine whiskey.",  # 5
            # Nose (10)
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish (10)
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            # Enrichment (20)
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            ratings=[{"source": "test", "score": 90}],
            awards=[{"name": "Gold Medal"}],
            # Verification (10)
            source_count=3,
            # NO PALATE DATA - CRITICAL TEST
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        # Score should be ~80 but status MUST be partial due to no palate
        self.assertGreaterEqual(product.completeness_score, 70)
        status = product.determine_status()
        self.assertEqual(status, "partial", "High score without palate must be PARTIAL, not COMPLETE")


class TestStatusComplete(TestCase):
    """Tests for COMPLETE status (score 60-79 WITH palate)."""

    def test_score_60_with_palate_flavors_is_complete(self):
        """Spec: Score 60+ with palate_flavors = COMPLETE"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",  # 10
            brand=brand,  # 5
            product_type="whiskey",  # 5
            abv=Decimal("43.0"),  # 5
            description="A fine whiskey.",  # 5
            # Palate (20) - REQUIRED FOR COMPLETE
            palate_flavors=["vanilla", "oak", "honey"],  # 10
            palate_description="Rich and smooth.",  # 5
            mid_palate_evolution="Develops spice.",  # 3
            mouthfeel="full_rich",  # 2
            # Nose (10)
            nose_description="Fruity and peaty.",  # 5
            primary_aromas=["fruit", "peat"],  # 5
            # Total: ~60 points
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        self.assertGreaterEqual(product.completeness_score, 60)
        self.assertLess(product.completeness_score, 80)
        status = product.determine_status()
        self.assertEqual(status, "complete")

    def test_score_60_with_palate_description_is_complete(self):
        """Spec: palate_description alone counts as having palate"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
            # Only palate_description (no palate_flavors)
            palate_description="Rich and smooth with vanilla notes.",
            # Nose
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,  # +2 points to reach 60
            # Enrichment
            best_price=Decimal("49.99"),
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        self.assertGreaterEqual(product.completeness_score, 60)
        status = product.determine_status()
        self.assertEqual(status, "complete")

    def test_score_60_with_initial_taste_is_complete(self):
        """Spec: initial_taste alone counts as having palate"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
            # Only initial_taste (no palate_flavors or palate_description)
            initial_taste="Sweet entry with honey and vanilla.",
            # Nose
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,  # +2 points to reach 60
            # Enrichment
            best_price=Decimal("49.99"),
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        self.assertGreaterEqual(product.completeness_score, 60)
        status = product.determine_status()
        self.assertEqual(status, "complete")

    def test_score_79_with_palate_is_complete(self):
        """Spec: Score 79 (max boundary) with palate = COMPLETE (not VERIFIED)"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
            # Palate
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Rich and smooth.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            # Nose
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            # Low enrichment (not enough for 80)
            best_price=Decimal("49.99"),
            # source_count=1 (default) - not enough for verification points
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        # Should be between 60-79
        self.assertGreaterEqual(product.completeness_score, 60)
        self.assertLess(product.completeness_score, 80)
        status = product.determine_status()
        self.assertEqual(status, "complete")


class TestStatusVerified(TestCase):
    """Tests for VERIFIED status (score 80-100 WITH palate)."""

    def test_score_80_with_palate_is_verified(self):
        """Spec: Score 80+ with palate = VERIFIED"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            # Identification (15)
            name="Test Whiskey 12 Year",
            brand=brand,
            # Basic Info (15)
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine single malt.",
            # Palate (20) - REQUIRED
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Rich and smooth.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            # Nose (10)
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish (10)
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            # Enrichment (20)
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            ratings=[{"source": "test", "score": 90}],
            awards=[{"name": "Gold Medal"}],
            # Verification (10)
            source_count=3,
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        self.assertGreaterEqual(product.completeness_score, 80)
        status = product.determine_status()
        self.assertEqual(status, "verified")

    def test_score_100_is_verified(self):
        """Spec: Perfect score = VERIFIED"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            # All fields for max score
            name="Test Whiskey 12 Year",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine single malt.",
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Rich and smooth.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            ratings=[{"source": "test", "score": 90}],
            awards=[{"name": "Gold Medal"}],
            source_count=3,
        )
        product.completeness_score = product.calculate_completeness_score()
        product.save()
        self.assertEqual(product.completeness_score, 100)
        status = product.determine_status()
        self.assertEqual(status, "verified")


class TestStatusSpecialCases(TestCase):
    """Tests for special status values (REJECTED, MERGED)."""

    def test_rejected_status_can_be_set(self):
        """Spec: REJECTED can be manually set regardless of score"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            status="rejected",
        )
        self.assertEqual(product.status, "rejected")

    def test_merged_status_can_be_set(self):
        """Spec: MERGED can be manually set regardless of score"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            status="merged",
        )
        self.assertEqual(product.status, "merged")


class TestStatusAutoUpdate(TestCase):
    """Tests that status auto-updates when score changes."""

    def test_status_updates_on_save(self):
        """Status should update automatically when product is saved."""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        # Initially incomplete
        self.assertEqual(product.status, "incomplete")

        # Add data to make it complete
        product.brand = brand
        product.abv = Decimal("43.0")
        product.description = "A fine whiskey."
        product.palate_flavors = ["vanilla", "oak", "honey"]
        product.palate_description = "Rich and smooth."
        product.mid_palate_evolution = "Develops spice."
        product.mouthfeel = "full_rich"
        product.nose_description = "Fruity and peaty."
        product.primary_aromas = ["fruit", "peat", "smoke"]
        product.finish_description = "Long and warming."
        product.finish_flavors = ["spice", "oak"]
        product.save()

        # Should now be complete or verified
        self.assertIn(product.status, ["complete", "verified"])


class TestHasPalateData(TestCase):
    """Tests for the has_palate_data property/method."""

    def test_has_palate_with_palate_flavors(self):
        """palate_flavors counts as having palate data."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_flavors=["vanilla", "oak"],
        )
        self.assertTrue(product.has_palate_data())

    def test_has_palate_with_palate_description(self):
        """palate_description counts as having palate data."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_description="Rich and smooth.",
        )
        self.assertTrue(product.has_palate_data())

    def test_has_palate_with_initial_taste(self):
        """initial_taste counts as having palate data."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            initial_taste="Sweet entry with honey.",
        )
        self.assertTrue(product.has_palate_data())

    def test_no_palate_when_all_empty(self):
        """No palate data when all palate fields empty."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
        )
        self.assertFalse(product.has_palate_data())

    def test_no_palate_with_empty_list(self):
        """Empty palate_flavors list doesn't count as having palate."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_flavors=[],
        )
        self.assertFalse(product.has_palate_data())

    def test_no_palate_with_empty_string(self):
        """Empty palate_description string doesn't count as having palate."""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_description="",
        )
        self.assertFalse(product.has_palate_data())
