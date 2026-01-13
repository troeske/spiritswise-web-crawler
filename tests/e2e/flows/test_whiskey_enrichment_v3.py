"""
E2E tests for Whiskey Enrichment V3 Pipeline.

Task 5.1: E2E Test - Whiskey Full Enrichment

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 5

Tests verify:
- Product progresses SKELETON → PARTIAL → BASELINE → ENRICHED
- ECP calculated correctly
- Awards search runs
"""

import pytest
from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.services.enrichment_orchestrator_v3 import (
    EnrichmentOrchestratorV3,
    EnrichmentSession,
)
from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class WhiskeyStatusProgressionTests(TestCase):
    """Tests for whiskey status progression through V3 pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_skeleton_status_with_only_name(self):
        """Test SKELETON status with only name field."""
        product_data = {"name": "Highland Park 18"}

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.SKELETON.value)

    def test_partial_status_with_basic_fields(self):
        """Test PARTIAL status with basic identity fields."""
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.PARTIAL.value)

    def test_baseline_status_with_tasting_fields(self):
        """Test BASELINE status with required tasting fields."""
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke", "heather"],
            "finish_flavors": ["smoke", "oak", "sweetness"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla", "peat"]
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.BASELINE.value)

    def test_enriched_status_with_or_fields(self):
        """Test ENRICHED status with OR field requirements."""
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke", "heather"],
            "finish_flavors": ["smoke", "oak", "sweetness"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla", "peat"],
            # ENRICHED requirements
            "mouthfeel": "Full-bodied, oily",
            "complexity": "Complex, layered",  # OR overall_complexity
            "finishing_cask": "Oloroso Sherry"  # OR maturation_notes
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.ENRICHED.value)


class ECPCalculationTests(TestCase):
    """Tests for ECP calculation in V3 pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_ecp_calculated_on_assess(self, mock_get_calculator):
        """Test ECP is calculated during assessment."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "basic", "fields": ["name", "brand", "abv"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "basic": {"populated": 3, "total": 3, "percentage": 100.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 100.0
        mock_get_calculator.return_value = mock_calculator

        product_data = {
            "name": "Test Whiskey",
            "brand": "Test",
            "abv": 40.0
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey",
            ecp_total=None  # Force calculation
        )

        # ECP should be calculated
        mock_calculator.calculate_ecp_by_group.assert_called()

    @patch('crawler.services.quality_gate_v3.get_ecp_calculator')
    def test_ecp_90_percent_promotes_to_complete(self, mock_get_calculator):
        """Test 90% ECP promotes to COMPLETE status."""
        mock_calculator = MagicMock()
        mock_calculator.load_field_groups_for_product_type.return_value = [
            {"group_key": "all", "fields": ["name"]}
        ]
        mock_calculator.calculate_ecp_by_group.return_value = {
            "all": {"populated": 9, "total": 10, "percentage": 90.0}
        }
        mock_calculator.calculate_total_ecp.return_value = 90.0
        mock_get_calculator.return_value = mock_calculator

        # Provide all ENRICHED requirements
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": 43.0,
            "region": "Islands",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A rich and complex single malt",
            "primary_aromas": ["honey", "smoke"],
            "finish_flavors": ["smoke", "oak"],
            "age_statement": "18 Years",
            "primary_cask": "Sherry",
            "palate_flavors": ["honey", "vanilla"],
            "mouthfeel": "Full-bodied",
            "complexity": "Complex",
            "finishing_cask": "Oloroso Sherry"
        }

        assessment = self.quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey"
        )

        self.assertEqual(assessment.status, ProductStatus.COMPLETE.value)


class AwardsSearchIntegrationTests(TestCase):
    """Tests for awards search integration in V3 pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_awards_search_sets_completed_flag(self):
        """Test awards search sets the completed flag."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        import time
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ):
            self.orchestrator._search_awards(session, "whiskey")

        self.assertTrue(session.awards_search_completed)

    def test_awards_search_returns_found_awards(self):
        """Test awards search returns found awards."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        import time
        session.start_time = time.time()

        mock_awards = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"},
            {"competition": "San Francisco", "year": 2023, "medal": "Double Gold"}
        ]

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=(mock_awards, ["https://iwsc.net"])
        ):
            awards, sources = self.orchestrator._search_awards(session, "whiskey")

        self.assertEqual(len(awards), 2)
        self.assertEqual(awards[0]["competition"], "IWSC")


class V3BudgetEnforcementTests(TestCase):
    """Tests for V3 budget enforcement."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_v3_search_budget_is_6(self):
        """Test V3 search budget is 6."""
        self.assertEqual(self.orchestrator.DEFAULT_MAX_SEARCHES, 6)

    def test_v3_source_budget_is_8(self):
        """Test V3 source budget is 8."""
        self.assertEqual(self.orchestrator.DEFAULT_MAX_SOURCES, 8)

    def test_v3_time_budget_is_180(self):
        """Test V3 time budget is 180 seconds."""
        self.assertEqual(self.orchestrator.DEFAULT_MAX_TIME_SECONDS, 180.0)

    def test_budget_exceeded_at_search_limit(self):
        """Test budget exceeded when at search limit."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 6
        import time
        session.start_time = time.time()

        limits = {"max_searches": 6, "max_sources": 8, "max_time": 180.0}
        exceeded = self.orchestrator._check_budget_exceeded(session, limits)

        self.assertTrue(exceeded)


class FullPipelineFlowTests(TestCase):
    """Tests for full V3 pipeline flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()
        self.quality_gate = QualityGateV3()

    def test_session_creation_with_v3_defaults(self):
        """Test session created with V3 defaults."""
        with patch('crawler.services.enrichment_orchestrator_v3.ProductTypeConfig') as mock_config:
            from crawler.models import ProductTypeConfig as RealConfig
            mock_config.DoesNotExist = RealConfig.DoesNotExist
            mock_config.objects.get.side_effect = RealConfig.DoesNotExist

            session = self.orchestrator._create_session(
                "whiskey",
                {"name": "Test Whiskey", "brand": "Test"}
            )

        self.assertEqual(session.max_searches, 6)
        self.assertEqual(session.max_sources, 8)
        self.assertEqual(session.max_time_seconds, 180.0)
        self.assertFalse(session.awards_search_completed)
        self.assertEqual(session.members_only_sites_detected, [])

    def test_quality_gate_v3_used(self):
        """Test QualityGateV3 is used for assessment."""
        gate = self.orchestrator.quality_gate

        self.assertIsInstance(gate, QualityGateV3)

    def test_members_only_detection_integration(self):
        """Test members-only detection integrates with budget."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 3

        with patch('crawler.services.enrichment_orchestrator_v3.get_members_only_detector') as mock_get:
            mock_detector = MagicMock()
            mock_detector.check_response.return_value = True
            mock_get.return_value = mock_detector

            self.orchestrator._check_and_refund_if_members_only(
                session,
                url="https://smws.com",
                content="<html>Members Only</html>",
                status_code=200
            )

        self.assertEqual(session.searches_performed, 2)  # Refunded
        self.assertIn("https://smws.com", session.members_only_sites_detected)
