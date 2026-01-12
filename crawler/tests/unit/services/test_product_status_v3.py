"""
Unit tests for ProductStatus V3 enum.

Task 2.1: Add BASELINE Status to ProductStatus Enum

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2

Tests verify:
- New status ordering: REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE
- BASELINE is the new name for the former COMPLETE status
- COMPLETE now means 90% ECP threshold reached
- Comparison operators work correctly with new ordering
"""

from django.test import TestCase


class ProductStatusV3OrderingTests(TestCase):
    """Tests for ProductStatus V3 ordering."""

    def test_status_values(self):
        """Test all status values are present."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertEqual(ProductStatus.REJECTED.value, "rejected")
        self.assertEqual(ProductStatus.SKELETON.value, "skeleton")
        self.assertEqual(ProductStatus.PARTIAL.value, "partial")
        self.assertEqual(ProductStatus.BASELINE.value, "baseline")
        self.assertEqual(ProductStatus.ENRICHED.value, "enriched")
        self.assertEqual(ProductStatus.COMPLETE.value, "complete")

    def test_rejected_is_lowest(self):
        """Test REJECTED is the lowest status."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.REJECTED < ProductStatus.SKELETON)
        self.assertTrue(ProductStatus.REJECTED < ProductStatus.PARTIAL)
        self.assertTrue(ProductStatus.REJECTED < ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.REJECTED < ProductStatus.ENRICHED)
        self.assertTrue(ProductStatus.REJECTED < ProductStatus.COMPLETE)

    def test_skeleton_second_lowest(self):
        """Test SKELETON is second lowest status."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.SKELETON > ProductStatus.REJECTED)
        self.assertTrue(ProductStatus.SKELETON < ProductStatus.PARTIAL)
        self.assertTrue(ProductStatus.SKELETON < ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.SKELETON < ProductStatus.ENRICHED)
        self.assertTrue(ProductStatus.SKELETON < ProductStatus.COMPLETE)

    def test_partial_third(self):
        """Test PARTIAL is third status."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.PARTIAL > ProductStatus.REJECTED)
        self.assertTrue(ProductStatus.PARTIAL > ProductStatus.SKELETON)
        self.assertTrue(ProductStatus.PARTIAL < ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.PARTIAL < ProductStatus.ENRICHED)
        self.assertTrue(ProductStatus.PARTIAL < ProductStatus.COMPLETE)

    def test_baseline_fourth(self):
        """Test BASELINE is fourth status (formerly COMPLETE in V2)."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.BASELINE > ProductStatus.REJECTED)
        self.assertTrue(ProductStatus.BASELINE > ProductStatus.SKELETON)
        self.assertTrue(ProductStatus.BASELINE > ProductStatus.PARTIAL)
        self.assertTrue(ProductStatus.BASELINE < ProductStatus.ENRICHED)
        self.assertTrue(ProductStatus.BASELINE < ProductStatus.COMPLETE)

    def test_enriched_fifth(self):
        """Test ENRICHED is fifth status."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.ENRICHED > ProductStatus.REJECTED)
        self.assertTrue(ProductStatus.ENRICHED > ProductStatus.SKELETON)
        self.assertTrue(ProductStatus.ENRICHED > ProductStatus.PARTIAL)
        self.assertTrue(ProductStatus.ENRICHED > ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.ENRICHED < ProductStatus.COMPLETE)

    def test_complete_is_highest(self):
        """Test COMPLETE is the highest status (90% ECP)."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.COMPLETE > ProductStatus.REJECTED)
        self.assertTrue(ProductStatus.COMPLETE > ProductStatus.SKELETON)
        self.assertTrue(ProductStatus.COMPLETE > ProductStatus.PARTIAL)
        self.assertTrue(ProductStatus.COMPLETE > ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.COMPLETE > ProductStatus.ENRICHED)


class ProductStatusV3ComparisonTests(TestCase):
    """Tests for ProductStatus V3 comparison operators."""

    def test_less_than(self):
        """Test < operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.PARTIAL < ProductStatus.BASELINE)
        self.assertFalse(ProductStatus.BASELINE < ProductStatus.PARTIAL)

    def test_less_than_or_equal(self):
        """Test <= operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.PARTIAL <= ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.BASELINE <= ProductStatus.BASELINE)
        self.assertFalse(ProductStatus.ENRICHED <= ProductStatus.PARTIAL)

    def test_greater_than(self):
        """Test > operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.ENRICHED > ProductStatus.BASELINE)
        self.assertFalse(ProductStatus.PARTIAL > ProductStatus.ENRICHED)

    def test_greater_than_or_equal(self):
        """Test >= operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.ENRICHED >= ProductStatus.BASELINE)
        self.assertTrue(ProductStatus.ENRICHED >= ProductStatus.ENRICHED)
        self.assertFalse(ProductStatus.SKELETON >= ProductStatus.PARTIAL)

    def test_equality(self):
        """Test == operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.BASELINE == ProductStatus.BASELINE)
        self.assertFalse(ProductStatus.BASELINE == ProductStatus.ENRICHED)

    def test_inequality(self):
        """Test != operator."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertTrue(ProductStatus.BASELINE != ProductStatus.ENRICHED)
        self.assertFalse(ProductStatus.BASELINE != ProductStatus.BASELINE)


class ProductStatusV3StringTests(TestCase):
    """Tests for ProductStatus V3 string behavior."""

    def test_status_is_str_enum(self):
        """Test ProductStatus inherits from str."""
        from crawler.services.quality_gate_v3 import ProductStatus

        # Value is accessible
        self.assertEqual(ProductStatus.BASELINE.value, "baseline")
        # Enum inherits from str so value comparison works
        self.assertTrue(ProductStatus.BASELINE == "baseline")

    def test_status_equality_with_string(self):
        """Test ProductStatus can be compared with string value."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertEqual(ProductStatus.BASELINE, "baseline")
        self.assertEqual(ProductStatus.COMPLETE, "complete")
        self.assertNotEqual(ProductStatus.BASELINE, "complete")

    def test_status_from_string(self):
        """Test creating ProductStatus from string value."""
        from crawler.services.quality_gate_v3 import ProductStatus

        self.assertEqual(ProductStatus("baseline"), ProductStatus.BASELINE)
        self.assertEqual(ProductStatus("complete"), ProductStatus.COMPLETE)
        self.assertEqual(ProductStatus("enriched"), ProductStatus.ENRICHED)


class ProductStatusV3FullOrderingTests(TestCase):
    """Tests for complete ordering verification."""

    def test_full_ordering_list(self):
        """Test complete status ordering matches V3 spec."""
        from crawler.services.quality_gate_v3 import ProductStatus

        # V3 spec ordering: REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE
        expected_order = [
            ProductStatus.REJECTED,
            ProductStatus.SKELETON,
            ProductStatus.PARTIAL,
            ProductStatus.BASELINE,
            ProductStatus.ENRICHED,
            ProductStatus.COMPLETE,
        ]

        # Test by sorting
        unsorted = [
            ProductStatus.COMPLETE,
            ProductStatus.SKELETON,
            ProductStatus.BASELINE,
            ProductStatus.REJECTED,
            ProductStatus.ENRICHED,
            ProductStatus.PARTIAL,
        ]
        sorted_statuses = sorted(unsorted)

        self.assertEqual(sorted_statuses, expected_order)

    def test_adjacent_comparisons(self):
        """Test each adjacent pair in the ordering."""
        from crawler.services.quality_gate_v3 import ProductStatus

        pairs = [
            (ProductStatus.REJECTED, ProductStatus.SKELETON),
            (ProductStatus.SKELETON, ProductStatus.PARTIAL),
            (ProductStatus.PARTIAL, ProductStatus.BASELINE),
            (ProductStatus.BASELINE, ProductStatus.ENRICHED),
            (ProductStatus.ENRICHED, ProductStatus.COMPLETE),
        ]

        for lower, higher in pairs:
            with self.subTest(lower=lower, higher=higher):
                self.assertTrue(lower < higher)
                self.assertTrue(higher > lower)
                self.assertFalse(lower > higher)
                self.assertFalse(higher < lower)
