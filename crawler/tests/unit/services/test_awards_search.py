"""
Unit tests for Dedicated Awards Search.

Task 4.4: Implement Dedicated Awards Search

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 5.1 - Step 4

Tests verify:
- Awards search always runs (not skipped even if COMPLETE)
- Awards search uses dedicated budget (not main search budget)
- awards_search_completed flag is set
"""

import time
from unittest.mock import MagicMock, patch, AsyncMock

from django.test import TestCase

from crawler.services.enrichment_orchestrator_v3 import (
    EnrichmentOrchestratorV3,
    EnrichmentSession,
)


class AwardsSearchAlwaysRunsTests(TestCase):
    """Tests for awards search always running."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_search_awards_method_exists(self):
        """Test _search_awards method exists."""
        self.assertTrue(hasattr(self.orchestrator, '_search_awards'))

    def test_awards_search_runs_when_not_complete(self):
        """Test awards search runs when product is not COMPLETE."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ) as mock_search:
            self.orchestrator._search_awards(session, "whiskey")
            mock_search.assert_called_once()

    def test_awards_search_runs_when_complete(self):
        """Test awards search runs even when product is COMPLETE."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        session.start_time = time.time()
        # Simulate a COMPLETE product (but awards should still run)
        session.awards_search_completed = False

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ) as mock_search:
            self.orchestrator._search_awards(session, "whiskey")
            mock_search.assert_called_once()


class AwardsDedicatedBudgetTests(TestCase):
    """Tests for awards search using dedicated budget."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_awards_search_does_not_decrement_main_budget(self):
        """Test awards search doesn't use main search budget."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        session.searches_performed = 3
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([{"competition": "IWSC", "medal": "Gold"}], ["https://iwsc.net"])
        ):
            self.orchestrator._search_awards(session, "whiskey")

        # Main budget should not be affected
        self.assertEqual(session.searches_performed, 3)

    def test_awards_search_has_separate_limit(self):
        """Test awards search has its own search limit."""
        # Awards search should have its own limit (e.g., 1 search)
        # This is separate from the main max_searches limit
        session = EnrichmentSession(
            initial_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey"
        )
        session.searches_performed = 6  # At main limit
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ) as mock_search:
            # Should still run even though main budget exhausted
            self.orchestrator._search_awards(session, "whiskey")
            mock_search.assert_called_once()

    def test_awards_search_skips_if_already_completed(self):
        """Test awards search skips if already completed this session."""
        session = EnrichmentSession(
            initial_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey"
        )
        session.awards_search_completed = True  # Already done
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ) as mock_search:
            self.orchestrator._search_awards(session, "whiskey")
            # Should skip since already completed
            mock_search.assert_not_called()


class AwardsSearchCompletedFlagTests(TestCase):
    """Tests for awards_search_completed flag."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_session_has_awards_search_completed_field(self):
        """Test EnrichmentSession has awards_search_completed field."""
        session = EnrichmentSession(
            initial_data={"name": "Test"},
            product_type="whiskey"
        )

        self.assertTrue(hasattr(session, 'awards_search_completed'))
        self.assertFalse(session.awards_search_completed)

    def test_flag_set_after_search(self):
        """Test awards_search_completed set to True after search."""
        session = EnrichmentSession(
            initial_data={"name": "Highland Park 18", "brand": "Highland Park"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ):
            self.orchestrator._search_awards(session, "whiskey")

        self.assertTrue(session.awards_search_completed)

    def test_flag_set_even_if_no_awards_found(self):
        """Test flag set even when no awards returned."""
        session = EnrichmentSession(
            initial_data={"name": "Unknown Whiskey", "brand": "Unknown"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])  # No awards found
        ):
            self.orchestrator._search_awards(session, "whiskey")

        self.assertTrue(session.awards_search_completed)


class AwardsSearchQueryTests(TestCase):
    """Tests for awards search query construction."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_build_awards_search_query(self):
        """Test building awards search query."""
        product_data = {
            "name": "Highland Park 18 Year Old",
            "brand": "Highland Park"
        }

        query = self.orchestrator._build_awards_search_query(product_data)

        self.assertIn("Highland Park", query)
        self.assertIn("award", query.lower())

    def test_query_includes_brand(self):
        """Test query includes brand name."""
        product_data = {
            "name": "18 Year Old Single Malt",
            "brand": "Lagavulin"
        }

        query = self.orchestrator._build_awards_search_query(product_data)

        self.assertIn("Lagavulin", query)

    def test_query_includes_competition_keywords(self):
        """Test query includes competition/award keywords."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test"
        }

        query = self.orchestrator._build_awards_search_query(product_data)

        # Should include award-related keywords
        query_lower = query.lower()
        self.assertTrue(
            "award" in query_lower or
            "medal" in query_lower or
            "competition" in query_lower
        )


class AwardsExtractionTests(TestCase):
    """Tests for awards extraction from results."""

    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = EnrichmentOrchestratorV3()

    def test_extracts_awards_from_results(self):
        """Test awards extracted from search results."""
        session = EnrichmentSession(
            initial_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey"
        )
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
        self.assertEqual(awards[1]["medal"], "Double Gold")

    def test_returns_empty_list_when_no_awards(self):
        """Test returns empty list when no awards found."""
        session = EnrichmentSession(
            initial_data={"name": "Unknown Whiskey", "brand": "Unknown"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=([], [])
        ):
            awards, sources = self.orchestrator._search_awards(session, "whiskey")

        self.assertEqual(awards, [])
        self.assertEqual(sources, [])

    def test_awards_sources_tracked(self):
        """Test awards sources are tracked."""
        session = EnrichmentSession(
            initial_data={"name": "Test Whiskey", "brand": "Test"},
            product_type="whiskey"
        )
        session.start_time = time.time()

        with patch.object(
            self.orchestrator,
            '_execute_awards_search',
            return_value=(
                [{"competition": "IWSC", "medal": "Gold"}],
                ["https://iwsc.net/results"]
            )
        ):
            awards, sources = self.orchestrator._search_awards(session, "whiskey")

        self.assertIn("https://iwsc.net/results", sources)
