"""
Verification Pipeline TDD Tests - Phase 5

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md

These tests verify the multi-source verification logic matches the spec.
Written FIRST according to TDD methodology.

Key Spec Requirements:
- TARGET_SOURCES = 3
- MIN_SOURCES_FOR_VERIFIED = 2
- source_count tracks sources used
- verified_fields tracks which fields were verified by 2+ sources
- Field is verified when 2 sources agree on same value
"""

from decimal import Decimal
from django.test import TestCase

from crawler.models import DiscoveredProduct, DiscoveredBrand


class TestSourceCountTracking(TestCase):
    """Tests for source_count field tracking."""

    def test_source_count_default_is_1(self):
        """Spec: Initial product has source_count = 1"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        # Default should be 1 (the source that created it)
        self.assertEqual(product.source_count, 1)

    def test_source_count_can_be_set(self):
        """source_count can be updated as more sources verify."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            source_count=2,
        )
        self.assertEqual(product.source_count, 2)

    def test_source_count_affects_status_verification_points(self):
        """Spec: source_count >= 2 gives 5 points, >= 3 gives 10 points"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            source_count=3,
        )
        # 10 (name) + 5 (product_type) + 10 (source_count>=3) = 25
        self.assertEqual(product.completeness_score, 25)


class TestVerifiedFieldsTracking(TestCase):
    """Tests for verified_fields JSONField tracking."""

    def test_verified_fields_default_is_empty(self):
        """verified_fields should default to empty list."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        self.assertEqual(product.verified_fields, [])

    def test_verified_fields_can_be_set(self):
        """verified_fields can track which fields are verified."""
        verified = ["name", "abv", "country"]
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            verified_fields=verified,
        )
        product.refresh_from_db()
        self.assertEqual(product.verified_fields, verified)

    def test_verified_fields_can_be_updated(self):
        """verified_fields can be updated as more fields are verified."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            verified_fields=["name"],
        )
        # Simulate verification pipeline adding more verified fields
        product.verified_fields = ["name", "abv", "country"]
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.verified_fields, ["name", "abv", "country"])


class TestMissingCriticalFields(TestCase):
    """Tests for identifying missing critical tasting fields."""

    def test_missing_palate_identified(self):
        """Spec: palate missing when no palate_flavors AND no palate_description"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            # No palate fields
        )
        missing = product.get_missing_critical_fields()
        self.assertIn("palate", missing)

    def test_palate_not_missing_with_palate_flavors(self):
        """palate_flavors satisfies palate requirement."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            palate_flavors=["vanilla", "oak"],
        )
        missing = product.get_missing_critical_fields()
        self.assertNotIn("palate", missing)

    def test_palate_not_missing_with_palate_description(self):
        """palate_description satisfies palate requirement."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            palate_description="Rich and smooth.",
        )
        missing = product.get_missing_critical_fields()
        self.assertNotIn("palate", missing)

    def test_missing_nose_identified(self):
        """Spec: nose missing when no nose_description AND no primary_aromas"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            # No nose fields
        )
        missing = product.get_missing_critical_fields()
        self.assertIn("nose", missing)

    def test_nose_not_missing_with_primary_aromas(self):
        """primary_aromas satisfies nose requirement."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            primary_aromas=["fruit", "peat"],
        )
        missing = product.get_missing_critical_fields()
        self.assertNotIn("nose", missing)

    def test_missing_finish_identified(self):
        """Spec: finish missing when no finish_description AND no finish_flavors"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            # No finish fields
        )
        missing = product.get_missing_critical_fields()
        self.assertIn("finish", missing)

    def test_finish_not_missing_with_finish_flavors(self):
        """finish_flavors satisfies finish requirement."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            finish_flavors=["spice", "oak"],
        )
        missing = product.get_missing_critical_fields()
        self.assertNotIn("finish", missing)


class TestVerificationTargets(TestCase):
    """Tests for verification target constants."""

    def test_target_sources_is_3(self):
        """Spec: TARGET_SOURCES = 3"""
        from crawler.verification.pipeline import VerificationPipeline

        self.assertEqual(VerificationPipeline.TARGET_SOURCES, 3)

    def test_min_sources_for_verified_is_2(self):
        """Spec: MIN_SOURCES_FOR_VERIFIED = 2"""
        from crawler.verification.pipeline import VerificationPipeline

        self.assertEqual(VerificationPipeline.MIN_SOURCES_FOR_VERIFIED, 2)


class TestFieldVerification(TestCase):
    """Tests for field-level verification logic."""

    def test_mark_field_as_verified(self):
        """When 2 sources agree, field should be marked verified."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            abv=Decimal("43.0"),
            verified_fields=[],
        )
        # Simulate second source confirming ABV
        product.mark_field_verified("abv")
        self.assertIn("abv", product.verified_fields)

    def test_multiple_fields_can_be_verified(self):
        """Multiple fields can be tracked as verified."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            verified_fields=[],
        )
        product.mark_field_verified("name")
        product.mark_field_verified("abv")
        product.mark_field_verified("country")
        self.assertEqual(sorted(product.verified_fields), ["abv", "country", "name"])

    def test_duplicate_verification_ignored(self):
        """Marking same field verified twice doesn't duplicate."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            verified_fields=["name"],
        )
        product.mark_field_verified("name")
        self.assertEqual(product.verified_fields, ["name"])


class TestStatusVerificationRequirements(TestCase):
    """Tests that VERIFIED status requires proper verification."""

    def test_verification_points_with_source_count_1(self):
        """Spec: source_count=1 gives 0 verification points"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        # Create a product that's mostly complete but missing some enrichment
        # to demonstrate the verification point difference
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Rich and smooth.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            # Some enrichment
            best_price=Decimal("49.99"),
            source_count=1,  # Only 1 source = 0 verification points
        )
        # Score with source_count=1 should be 75 (no verification points)
        # Identification(15) + Basic(15) + Palate(20) + Nose(10) + Finish(10) + Enrichment(5) = 75
        self.assertEqual(product.completeness_score, 75)

    def test_verified_status_achievable_with_source_count_3(self):
        """Spec: source_count >= 3 gives 10 verification points, enabling VERIFIED"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            # Complete product with 3 sources
            name="Test Whiskey",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
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
            source_count=3,  # 3 sources = 10 verification points
        )
        self.assertEqual(product.completeness_score, 100)
        self.assertEqual(product.status, "verified")


class TestEnrichmentStrategies(TestCase):
    """Tests for enrichment search strategies."""

    def test_tasting_notes_strategies_available(self):
        """Spec: ENRICHMENT_STRATEGIES includes tasting_notes patterns"""
        from crawler.verification.pipeline import VerificationPipeline

        self.assertIn("tasting_notes", VerificationPipeline.ENRICHMENT_STRATEGIES)

    def test_pricing_strategies_available(self):
        """Spec: ENRICHMENT_STRATEGIES includes pricing patterns"""
        from crawler.verification.pipeline import VerificationPipeline

        self.assertIn("pricing", VerificationPipeline.ENRICHMENT_STRATEGIES)


class TestMergeAndVerifyLogic(TestCase):
    """Tests for merge and verify data logic."""

    def test_merge_fills_missing_field(self):
        """When field is missing, new value fills it."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            # No ABV set
        )
        self.assertIsNone(product.abv)

        # Simulate extraction filling missing field
        product.abv = Decimal("43.0")
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.abv, Decimal("43.0"))

    def test_merge_verifies_matching_values(self):
        """When new value matches existing, field becomes verified."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            abv=Decimal("43.0"),
            verified_fields=[],
        )
        # Simulate second extraction with matching ABV
        new_abv = Decimal("43.0")
        if product.abv == new_abv:
            product.mark_field_verified("abv")

        self.assertIn("abv", product.verified_fields)

    def test_values_match_for_decimals(self):
        """Decimal values should be compared properly."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        # Same value, different precision
        val1 = Decimal("43.0")
        val2 = Decimal("43.00")
        self.assertTrue(product.values_match(val1, val2))

    def test_values_match_for_strings(self):
        """String values should be compared case-insensitively."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        val1 = "Scotland"
        val2 = "scotland"
        self.assertTrue(product.values_match(val1, val2))

    def test_values_match_for_lists(self):
        """List values should be compared (order-independent)."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        val1 = ["vanilla", "oak", "honey"]
        val2 = ["oak", "vanilla", "honey"]
        self.assertTrue(product.values_match(val1, val2))
