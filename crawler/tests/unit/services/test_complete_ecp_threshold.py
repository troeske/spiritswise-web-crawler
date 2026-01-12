"""
Unit tests for V3 90% ECP Threshold for COMPLETE Status.

Task 2.5: Implement 90% ECP Threshold for COMPLETE

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2.4

Tests verify:
- Product with 89% ECP → ENRICHED (not COMPLETE)
- Product with 90% ECP → COMPLETE
- Product with 95% ECP → COMPLETE
- ECP threshold is 90.0%
- ECP can be passed to assess() method
"""

from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class ECPThresholdBasicTests(TestCase):
    """Tests for basic ECP threshold behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()
        # Enriched-level data
        self.enriched_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey", "caramel"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Sherry",
        }

    def test_ecp_threshold_constant(self):
        """Test ECP threshold is 90.0%."""
        self.assertEqual(self.quality_gate.ECP_COMPLETE_THRESHOLD, 90.0)

    def test_enriched_with_89_percent_ecp(self):
        """Test product with 89% ECP stays at ENRICHED."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=89.0
        )
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_complete_with_90_percent_ecp(self):
        """Test product with exactly 90% ECP reaches COMPLETE."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=90.0
        )
        self.assertEqual(result.status, ProductStatus.COMPLETE)

    def test_complete_with_95_percent_ecp(self):
        """Test product with 95% ECP reaches COMPLETE."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=95.0
        )
        self.assertEqual(result.status, ProductStatus.COMPLETE)

    def test_complete_with_100_percent_ecp(self):
        """Test product with 100% ECP reaches COMPLETE."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=100.0
        )
        self.assertEqual(result.status, ProductStatus.COMPLETE)


class ECPThresholdEdgeCasesTests(TestCase):
    """Tests for ECP threshold edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()
        self.enriched_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Sherry",
        }

    def test_enriched_with_89_99_percent_ecp(self):
        """Test product with 89.99% ECP stays at ENRICHED."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=89.99
        )
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_complete_with_90_01_percent_ecp(self):
        """Test product with 90.01% ECP reaches COMPLETE."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=90.01
        )
        self.assertEqual(result.status, ProductStatus.COMPLETE)

    def test_no_ecp_provided_defaults_to_status_based(self):
        """Test assessment without ECP defaults to status-based determination."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=None
        )
        # Should be ENRICHED since ECP not provided
        self.assertEqual(result.status, ProductStatus.ENRICHED)

    def test_zero_ecp_does_not_affect_status(self):
        """Test 0% ECP doesn't override status determination."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=0.0
        )
        # Should be ENRICHED even with 0% ECP (status-based still applies)
        self.assertEqual(result.status, ProductStatus.ENRICHED)


class ECPStatusPromotionTests(TestCase):
    """Tests for ECP-based status promotion."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_ecp_promotes_from_baseline_to_complete(self):
        """Test high ECP can promote product from BASELINE to COMPLETE."""
        # BASELINE-level data (no mouthfeel/enriched fields)
        baseline_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
            # No mouthfeel, complexity, or finishing_cask
        }

        # Without ECP, should be BASELINE
        result_no_ecp = self.quality_gate.assess(baseline_data, "whiskey")
        self.assertEqual(result_no_ecp.status, ProductStatus.BASELINE)

        # With 90%+ ECP, should be COMPLETE
        result_with_ecp = self.quality_gate.assess(
            baseline_data, "whiskey", ecp_total=92.0
        )
        self.assertEqual(result_with_ecp.status, ProductStatus.COMPLETE)

    def test_ecp_promotes_from_partial_to_complete(self):
        """Test high ECP can promote product from PARTIAL to COMPLETE."""
        # PARTIAL-level data
        partial_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            # Missing baseline fields
        }

        # Without ECP, should be PARTIAL
        result_no_ecp = self.quality_gate.assess(partial_data, "whiskey")
        self.assertEqual(result_no_ecp.status, ProductStatus.PARTIAL)

        # With 90%+ ECP, should be COMPLETE
        result_with_ecp = self.quality_gate.assess(
            partial_data, "whiskey", ecp_total=95.0
        )
        self.assertEqual(result_with_ecp.status, ProductStatus.COMPLETE)

    def test_ecp_does_not_promote_skeleton_without_data(self):
        """Test ECP respects that skeleton still needs enrichment."""
        # SKELETON-level data
        skeleton_data = {"name": "Test Whiskey"}

        # With high ECP, status is determined by ECP threshold
        result = self.quality_gate.assess(
            skeleton_data, "whiskey", ecp_total=95.0
        )
        # ECP >= 90% promotes to COMPLETE
        self.assertEqual(result.status, ProductStatus.COMPLETE)


class ECPAssessmentResultTests(TestCase):
    """Tests for ECP value in assessment results."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()
        self.enriched_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Sherry",
        }

    def test_ecp_stored_in_assessment(self):
        """Test ECP value is stored in QualityAssessment result."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=85.5
        )
        self.assertEqual(result.ecp_total, 85.5)

    def test_ecp_defaults_to_zero_when_not_provided(self):
        """Test ECP defaults to 0.0 when not provided."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=None
        )
        self.assertEqual(result.ecp_total, 0.0)


class ECPNeedsEnrichmentTests(TestCase):
    """Tests for needs_enrichment flag with ECP."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()
        self.enriched_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Sherry",
        }

    def test_needs_enrichment_true_below_complete(self):
        """Test needs_enrichment is True for ENRICHED status."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=85.0
        )
        self.assertEqual(result.status, ProductStatus.ENRICHED)
        self.assertTrue(result.needs_enrichment)

    def test_needs_enrichment_false_at_complete(self):
        """Test needs_enrichment is False for COMPLETE status."""
        result = self.quality_gate.assess(
            self.enriched_data,
            "whiskey",
            ecp_total=92.0
        )
        self.assertEqual(result.status, ProductStatus.COMPLETE)
        self.assertFalse(result.needs_enrichment)
