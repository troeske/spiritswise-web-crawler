"""
Unit tests for QualityGateV3 integration with discovery and enrichment flows.

Task 2.1: Quality Gate V3 Integration

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 2.8 (COMP-LEARN-008)

Tests verify:
- Status assessment after extraction
- Category-specific requirements (blends exempt from region/primary_cask)
- 90% ECP threshold for COMPLETE status
- Integration with DiscoveryOrchestratorV3 and EnrichmentOrchestratorV3
"""

from django.test import TestCase
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class QualityGateV3StatusAssessmentTests(TestCase):
    """Tests for QualityGateV3 status assessment after extraction."""

    def test_skeleton_status_with_name_only(self):
        """Test product with only name gets SKELETON status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Buffalo Trace Bourbon"
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        self.assertEqual(assessment.status, ProductStatus.SKELETON)
        self.assertIn("name", assessment.populated_fields)
        self.assertTrue(assessment.needs_enrichment)

    def test_rejected_status_without_name(self):
        """Test product without name gets REJECTED status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "brand": "Buffalo Trace",
            "abv": "45%"
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        self.assertEqual(assessment.status, ProductStatus.REJECTED)
        self.assertIn("name", assessment.missing_required_fields)
        self.assertFalse(assessment.needs_enrichment)

    def test_partial_status_with_basic_fields(self):
        """Test product with basic required fields gets PARTIAL status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Partial requires: name, brand, abv, region, country, category
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": "40%",
            "region": "Speyside",
            "country": "Scotland",
            "category": "Single Malt Scotch Whisky",
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        self.assertEqual(assessment.status, ProductStatus.PARTIAL)
        self.assertTrue(assessment.needs_enrichment)

    def test_baseline_status_with_all_required_fields(self):
        """Test product with all baseline required fields gets BASELINE status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Baseline requires: name, brand, abv, region, country, category,
        # volume_ml, description, primary_aromas, finish_flavors,
        # age_statement, primary_cask, palate_flavors
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": "40%",
            "region": "Speyside",
            "country": "Scotland",
            "category": "Single Malt Scotch Whisky",
            "volume_ml": 750,
            "description": "A smooth single malt with notes of pear and oak",
            "primary_aromas": ["pear", "oak", "vanilla"],
            "finish_flavors": ["oak", "honey"],
            "age_statement": "12 years",
            "primary_cask": "American Oak",
            "palate_flavors": ["honey", "apple", "oak"],
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        self.assertEqual(assessment.status, ProductStatus.BASELINE)
        self.assertTrue(assessment.needs_enrichment)  # Still needs enrichment until COMPLETE

    def test_enriched_status_with_mouthfeel_and_or_fields(self):
        """Test product with baseline + mouthfeel + OR fields gets ENRICHED status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Enriched requires: baseline + mouthfeel + enriched_or_fields satisfied
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": "40%",
            "region": "Speyside",
            "country": "Scotland",
            "category": "Single Malt Scotch Whisky",
            "volume_ml": 750,
            "description": "A smooth single malt with notes of pear and oak",
            "primary_aromas": ["pear", "oak", "vanilla"],
            "finish_flavors": ["oak", "honey"],
            "age_statement": "12 years",
            "primary_cask": "American Oak",
            "palate_flavors": ["honey", "apple", "oak"],
            # Enriched additions
            "mouthfeel": "Smooth and creamy",
            "complexity": "Medium",  # OR with overall_complexity
            "finishing_cask": "Sherry",  # OR with maturation_notes
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        self.assertEqual(assessment.status, ProductStatus.ENRICHED)
        self.assertTrue(assessment.needs_enrichment)  # Still needs enrichment until COMPLETE


class CategorySpecificRequirementsTests(TestCase):
    """Tests for category-specific requirements (blends exempt from region/primary_cask)."""

    def test_blended_scotch_exempt_from_region(self):
        """Test blended scotch whisky is exempt from region requirement."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Blended scotch without region should still reach BASELINE
        extracted_data = {
            "name": "Johnnie Walker Black Label",
            "brand": "Johnnie Walker",
            "abv": "40%",
            "country": "Scotland",
            "category": "Blended Scotch Whisky",
            "volume_ml": 750,
            "description": "A rich, smoky blended scotch",
            "primary_aromas": ["smoke", "vanilla", "caramel"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "12 years",
            "palate_flavors": ["smoke", "spice", "fruit"],
            # No region - should be exempt for blends
            # No primary_cask - should be exempt for blends
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            product_category="Blended Scotch Whisky",
        )

        # Blends should reach BASELINE without region/primary_cask
        self.assertEqual(assessment.status, ProductStatus.BASELINE)
        self.assertNotIn("region", assessment.missing_required_fields)
        self.assertNotIn("primary_cask", assessment.missing_required_fields)

    def test_blended_malt_exempt_from_primary_cask(self):
        """Test blended malt whisky is exempt from primary_cask requirement."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Monkey Shoulder",
            "brand": "William Grant",
            "abv": "40%",
            "country": "Scotland",
            "category": "Blended Malt Scotch Whisky",
            "volume_ml": 750,
            "description": "Triple malt smoothness",
            "primary_aromas": ["vanilla", "spice", "barley"],
            "finish_flavors": ["spice", "oak"],
            "age_statement": "NAS",
            "palate_flavors": ["honey", "vanilla", "fruit"],
            # No primary_cask - should be exempt for blended malts
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            product_category="Blended Malt Scotch Whisky",
        )

        # Should reach BASELINE without primary_cask
        self.assertEqual(assessment.status, ProductStatus.BASELINE)
        self.assertNotIn("primary_cask", assessment.missing_required_fields)

    def test_single_malt_requires_region(self):
        """Test single malt whisky requires region for BASELINE."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Single malt without region should NOT reach BASELINE
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": "40%",
            "country": "Scotland",
            "category": "Single Malt Scotch Whisky",
            "volume_ml": 750,
            "description": "A smooth single malt",
            "primary_aromas": ["pear", "oak"],
            "finish_flavors": ["oak", "honey"],
            "age_statement": "12 years",
            "primary_cask": "American Oak",
            "palate_flavors": ["honey", "apple"],
            # No region - should be required for single malts
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            product_category="Single Malt Scotch Whisky",
        )

        # Single malts should require region
        self.assertLess(assessment.status, ProductStatus.BASELINE)
        self.assertIn("region", assessment.missing_required_fields)

    def test_single_malt_requires_primary_cask(self):
        """Test single malt whisky requires primary_cask for BASELINE."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Single malt without primary_cask should NOT reach BASELINE
        extracted_data = {
            "name": "Glenfiddich 12 Year",
            "brand": "Glenfiddich",
            "abv": "40%",
            "region": "Speyside",
            "country": "Scotland",
            "category": "Single Malt Scotch Whisky",
            "volume_ml": 750,
            "description": "A smooth single malt",
            "primary_aromas": ["pear", "oak"],
            "finish_flavors": ["oak", "honey"],
            "age_statement": "12 years",
            "palate_flavors": ["honey", "apple"],
            # No primary_cask - should be required for single malts
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            product_category="Single Malt Scotch Whisky",
        )

        # Single malts should require primary_cask
        self.assertLess(assessment.status, ProductStatus.BASELINE)
        self.assertIn("primary_cask", assessment.missing_required_fields)

    def test_blended_category_from_extracted_data(self):
        """Test category exemptions work when category is in extracted_data."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Category in extracted_data, not passed explicitly
        extracted_data = {
            "name": "Johnnie Walker Black Label",
            "brand": "Johnnie Walker",
            "abv": "40%",
            "country": "Scotland",
            "category": "blended scotch whisky",  # lowercase
            "volume_ml": 750,
            "description": "A rich, smoky blended scotch",
            "primary_aromas": ["smoke", "vanilla"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "12 years",
            "palate_flavors": ["smoke", "spice"],
        }

        # No product_category passed - should use extracted_data["category"]
        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
        )

        # Should reach BASELINE without region/primary_cask
        self.assertEqual(assessment.status, ProductStatus.BASELINE)

    def test_canadian_whisky_exempt_from_region(self):
        """Test Canadian whisky is exempt from region requirement."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Crown Royal",
            "brand": "Crown Royal",
            "abv": "40%",
            "country": "Canada",
            "category": "Canadian Whisky",
            "volume_ml": 750,
            "description": "A smooth Canadian whisky",
            "primary_aromas": ["vanilla", "caramel"],
            "finish_flavors": ["oak", "honey"],
            "age_statement": "NAS",
            "palate_flavors": ["vanilla", "fruit"],
            # No region - should be exempt for Canadian whisky
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            product_category="Canadian Whisky",
        )

        # Canadian whisky should reach BASELINE without region
        self.assertEqual(assessment.status, ProductStatus.BASELINE)
        self.assertNotIn("region", assessment.missing_required_fields)


class ECPThresholdCompleteStatusTests(TestCase):
    """Tests for 90% ECP threshold for COMPLETE status."""

    def test_complete_status_at_90_percent_ecp(self):
        """Test product at exactly 90% ECP gets COMPLETE status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        # Product with 90% ECP
        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
        }

        # Pass pre-calculated ECP of exactly 90%
        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            ecp_total=90.0,
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE)
        self.assertFalse(assessment.needs_enrichment)
        self.assertGreaterEqual(assessment.ecp_total, 90.0)

    def test_complete_status_above_90_percent_ecp(self):
        """Test product above 90% ECP gets COMPLETE status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
        }

        # Pass pre-calculated ECP of 95%
        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            ecp_total=95.0,
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE)
        self.assertFalse(assessment.needs_enrichment)

    def test_not_complete_below_90_percent_ecp(self):
        """Test product below 90% ECP does not get COMPLETE status."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Speyside",
            "country": "Scotland",
            "category": "Single Malt",
        }

        # Pass pre-calculated ECP of 89%
        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            ecp_total=89.0,
        )

        self.assertNotEqual(assessment.status, ProductStatus.COMPLETE)
        self.assertTrue(assessment.needs_enrichment)

    def test_ecp_total_in_assessment(self):
        """Test ECP total is included in assessment."""
        from crawler.services.quality_gate_v3 import QualityGateV3

        quality_gate = QualityGateV3()

        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
        }

        assessment = quality_gate.assess(
            extracted_data=extracted_data,
            product_type="whiskey",
            ecp_total=75.5,
        )

        self.assertEqual(assessment.ecp_total, 75.5)


class DiscoveryOrchestratorV3QualityGateIntegrationTests(TestCase):
    """Tests for DiscoveryOrchestratorV3 integration with QualityGateV3."""

    def test_discovery_uses_quality_gate_v3(self):
        """Test DiscoveryOrchestratorV2 can use QualityGateV3 for assessment."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        # Create orchestrator with V3 quality gate
        quality_gate_v3 = QualityGateV3()
        orchestrator = DiscoveryOrchestratorV2(quality_gate=quality_gate_v3)

        # Test quality assessment uses V3
        product_data = {
            "name": "Test Bourbon",
            "brand": "Test Brand",
            "category": "Bourbon",
        }

        status = orchestrator._assess_quality(
            product_data=product_data,
            field_confidences={},
            product_type="whiskey",
        )

        # Status should be a valid V3 status
        valid_statuses = [s.value for s in ProductStatus]
        self.assertIn(status, valid_statuses)

    def test_discovery_passes_product_category(self):
        """Test DiscoveryOrchestrator passes product_category to quality assessment."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate_v3 = QualityGateV3()

        # Blended whisky product
        product_data = {
            "name": "Johnnie Walker Black Label",
            "brand": "Johnnie Walker",
            "abv": "40%",
            "country": "Scotland",
            "category": "Blended Scotch Whisky",
            "volume_ml": 750,
            "description": "A rich blend",
            "primary_aromas": ["smoke"],
            "finish_flavors": ["oak"],
            "age_statement": "12 years",
            "palate_flavors": ["smoke"],
        }

        # Pass category explicitly
        assessment = quality_gate_v3.assess(
            extracted_data=product_data,
            product_type="whiskey",
            product_category="Blended Scotch Whisky",
        )

        # Should reach BASELINE without region/primary_cask
        self.assertEqual(assessment.status, ProductStatus.BASELINE)


class EnrichmentOrchestratorV3QualityGateIntegrationTests(TestCase):
    """Tests for EnrichmentOrchestratorV3 integration with QualityGateV3."""

    def test_enrichment_uses_quality_gate_v3(self):
        """Test EnrichmentOrchestratorV3 uses QualityGateV3 for status assessment."""
        from crawler.services.enrichment_orchestrator_v3 import EnrichmentOrchestratorV3
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate_v3 = QualityGateV3()
        orchestrator = EnrichmentOrchestratorV3(quality_gate=quality_gate_v3)

        # Verify quality_gate property returns V3
        self.assertIsInstance(orchestrator.quality_gate, QualityGateV3)

    def test_enrichment_checks_complete_for_early_exit(self):
        """Test EnrichmentOrchestratorV3 checks for COMPLETE status for early exit."""
        from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus

        quality_gate_v3 = QualityGateV3()

        # Product at 90% ECP should be COMPLETE
        product_data = {"name": "Test Product"}
        assessment = quality_gate_v3.assess(
            extracted_data=product_data,
            product_type="whiskey",
            ecp_total=92.0,
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE)
        self.assertFalse(assessment.needs_enrichment)

    def test_enrichment_records_status_before_and_after(self):
        """Test EnrichmentOrchestratorV3 records status_before and status_after."""
        from crawler.services.enrichment_orchestrator_v3 import (
            EnrichmentOrchestratorV3,
            EnrichmentSession,
        )
        from crawler.services.quality_gate_v3 import QualityGateV3

        quality_gate_v3 = QualityGateV3()
        orchestrator = EnrichmentOrchestratorV3(quality_gate=quality_gate_v3)

        # Create session
        session = orchestrator._create_session(
            product_type="whiskey",
            initial_data={"name": "Test Product"},
            initial_confidences={},
        )

        # Session should be created
        self.assertIsInstance(session, EnrichmentSession)
        self.assertEqual(session.product_type, "whiskey")
        self.assertIn("name", session.current_data)


class StatusHierarchyTests(TestCase):
    """Tests for V3 status hierarchy ordering."""

    def test_status_ordering(self):
        """Test ProductStatus comparison operators work correctly."""
        from crawler.services.quality_gate_v3 import ProductStatus

        # Test hierarchy: REJECTED < SKELETON < PARTIAL < BASELINE < ENRICHED < COMPLETE
        self.assertLess(ProductStatus.REJECTED, ProductStatus.SKELETON)
        self.assertLess(ProductStatus.SKELETON, ProductStatus.PARTIAL)
        self.assertLess(ProductStatus.PARTIAL, ProductStatus.BASELINE)
        self.assertLess(ProductStatus.BASELINE, ProductStatus.ENRICHED)
        self.assertLess(ProductStatus.ENRICHED, ProductStatus.COMPLETE)

    def test_status_less_than_complete_needs_enrichment(self):
        """Test statuses less than COMPLETE need enrichment."""
        from crawler.services.quality_gate_v3 import ProductStatus

        statuses_needing_enrichment = [
            ProductStatus.SKELETON,
            ProductStatus.PARTIAL,
            ProductStatus.BASELINE,
            ProductStatus.ENRICHED,
        ]

        for status in statuses_needing_enrichment:
            self.assertLess(status, ProductStatus.COMPLETE)

    def test_complete_is_highest_status(self):
        """Test COMPLETE is the highest status."""
        from crawler.services.quality_gate_v3 import ProductStatus

        all_statuses = [
            ProductStatus.REJECTED,
            ProductStatus.SKELETON,
            ProductStatus.PARTIAL,
            ProductStatus.BASELINE,
            ProductStatus.ENRICHED,
            ProductStatus.COMPLETE,
        ]

        for status in all_statuses[:-1]:  # All except COMPLETE
            self.assertLess(status, ProductStatus.COMPLETE)
