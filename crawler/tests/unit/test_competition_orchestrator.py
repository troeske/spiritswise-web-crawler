"""
Unit tests for CompetitionOrchestrator filtering.

TDD tests for ensuring product type filtering correctly removes
non-MVP products (e.g., wine products from whiskey searches).
"""
import pytest
import logging
from unittest.mock import MagicMock, patch

from crawler.services.competition_orchestrator import (
    CompetitionOrchestrator,
    NEGATIVE_KEYWORDS,
)


class TestFilterAwardsByProductType:
    """Tests for _filter_awards_by_product_type method."""

    def test_filter_removes_wine_products(self):
        """Should filter out wine products when searching for whiskey."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Glenfiddich 12", "category": "Whisky"},
            {"product_name": "Winery Gurjaani", "category": "Wine"},
            {"product_name": "Taylor's Port", "category": "Port"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey", "port_wine"]
        )
        assert len(filtered) == 2
        names = [a["product_name"] for a in filtered]
        assert "Winery Gurjaani" not in names
        assert "Glenfiddich 12" in names
        assert "Taylor's Port" in names

    def test_filter_uses_negative_keywords(self):
        """Should filter products with negative keywords like 'winery'."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Calligraphy Winery 2024", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_removes_vineyard_products(self):
        """Should filter products containing 'vineyard' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Sunset Vineyard Reserve 2023", "category": "General"},
            {"product_name": "Highland Whisky 18 Year", "category": "Scotch"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 1
        assert filtered[0]["product_name"] == "Highland Whisky 18 Year"

    def test_filter_removes_chateau_products(self):
        """Should filter products containing 'chateau' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Chateau Margaux 2018", "category": "General"},
            {"product_name": "Glen Ord Single Malt Scotch Whisky", "category": "Whisky"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 1
        assert filtered[0]["product_name"] == "Glen Ord Single Malt Scotch Whisky"

    def test_filter_removes_domaine_products(self):
        """Should filter products containing 'domaine' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Domaine de la Romanee 2020", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_removes_bodega_products(self):
        """Should filter products containing 'bodega' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Bodega Vega 2019", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_removes_vino_products(self):
        """Should filter products containing 'vino' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Vino Rosso Premium", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_removes_wine_cellar_products(self):
        """Should filter products containing 'wine cellar' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Oak Wine Cellar Reserve", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_removes_estate_wine_products(self):
        """Should filter products containing 'estate wine' or 'wine estate' keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Heritage Estate Wine 2022", "category": "General"},
            {"product_name": "Wine Estate Collection", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_keeps_valid_whiskey_products(self):
        """Should keep valid whiskey products that don't match negative keywords."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Glenfiddich 12 Year Old Single Malt Scotch Whisky", "category": "Whisky"},
            {"product_name": "Jack Daniel's Tennessee Whiskey", "category": "Whiskey"},
            {"product_name": "Macallan 18 Year Old", "category": "Single Malt"},
            {"product_name": "Buffalo Trace Bourbon", "category": "Bourbon"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 4

    def test_filter_keeps_valid_port_wine_products(self):
        """Should keep valid port wine products."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Taylor's 20 Year Old Tawny Port", "category": "Port"},
            {"product_name": "Graham's Vintage Port 2017", "category": "Port"},
            {"product_name": "Fonseca Ruby Port", "category": "Ruby Port"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["port_wine"]
        )
        assert len(filtered) == 3

    def test_filter_is_case_insensitive(self):
        """Filtering should be case insensitive for negative keywords."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "WINERY GURJAANI 2024", "category": "General"},
            {"product_name": "Vineyard Premium Selection", "category": "General"},
            {"product_name": "CHATEAU Bordeaux 2020", "category": "General"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        assert len(filtered) == 0

    def test_filter_logs_filtered_products(self, caplog):
        """Should log details of filtered products."""
        # Set level on the specific logger used by competition_orchestrator
        with caplog.at_level(logging.DEBUG, logger="crawler.services.competition_orchestrator"):
            orchestrator = CompetitionOrchestrator()
            awards = [
                {"product_name": "Winery Gurjaani 2024", "category": "Wine"},
            ]
            filtered = orchestrator._filter_awards_by_product_type(
                awards, ["whiskey"]
            )

            # Check that filtering was logged
            assert len(filtered) == 0

            # The log should mention filtering - check INFO level summary log
            log_messages = [record.message for record in caplog.records]
            filter_logs = [msg for msg in log_messages if "filter" in msg.lower()]
            assert len(filter_logs) > 0, f"Expected filtering to be logged. Got: {log_messages}"

    def test_returns_all_when_no_product_types_specified(self):
        """Should return all awards when no product types are specified."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Winery Gurjaani", "category": "Wine"},
            {"product_name": "Glenfiddich 12", "category": "Whisky"},
        ]
        # Empty list should return all
        filtered = orchestrator._filter_awards_by_product_type(awards, [])
        assert len(filtered) == 2

    def test_handles_missing_product_name(self):
        """Should handle awards with missing product_name gracefully."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": None, "category": "Whisky"},
            {"product_name": "", "category": "Scotch"},
            {"category": "Port"},  # No product_name key at all
        ]
        # Should not raise an exception
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["whiskey"]
        )
        # These will be filtered out because they don't match whiskey keywords
        assert isinstance(filtered, list)


class TestNegativeKeywords:
    """Tests for the NEGATIVE_KEYWORDS constant."""

    def test_negative_keywords_list_exists(self):
        """Should have a list of negative keywords defined."""
        assert NEGATIVE_KEYWORDS is not None
        assert isinstance(NEGATIVE_KEYWORDS, list)
        assert len(NEGATIVE_KEYWORDS) > 0

    def test_required_negative_keywords_present(self):
        """Should contain all required negative keywords from Task 4."""
        required_keywords = [
            'winery',
            'vineyard',
            'wine cellar',
            'chateau',
            'domaine',
            'bodega',
            'vino',
        ]
        for keyword in required_keywords:
            assert keyword in NEGATIVE_KEYWORDS, f"Missing required negative keyword: {keyword}"

    def test_port_wine_not_filtered_by_wine_keyword(self):
        """Port wine products should NOT be filtered out by the 'wine' negative keyword."""
        orchestrator = CompetitionOrchestrator()
        awards = [
            {"product_name": "Taylor's 20 Year Old Tawny Port Wine", "category": "Port"},
            {"product_name": "Graham's Port Wine 2017", "category": "Port Wine"},
        ]
        filtered = orchestrator._filter_awards_by_product_type(
            awards, ["port_wine"]
        )
        # Port wine products should be kept even though they contain 'wine'
        assert len(filtered) == 2
