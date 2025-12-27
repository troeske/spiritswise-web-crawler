"""
Tests for Prestige-Led Discovery (Competition-Driven) system.

Task Group 5: Prestige-Led Discovery (Competitions)
These tests verify competition parsing, skeleton product creation,
SerpAPI enrichment triggers, and fuzzy matching for skeleton enrichment.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal


class TestSkeletonProductCreation:
    """Tests for skeleton product creation from competition data."""

    @pytest.mark.django_db
    def test_creates_skeleton_product_from_competition_data(self):
        """Skeleton products created from competition data have correct attributes."""
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus, DiscoverySource

        manager = SkeletonProductManager()

        # Competition award data
        award_data = {
            "product_name": "Glenfiddich 18 Year Old",
            "producer": "Glenfiddich",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
            "category": "Single Malt Scotch",
        }

        # Create skeleton product
        product = manager.create_skeleton_product(award_data)

        # Verify skeleton product attributes
        assert product is not None
        assert product.status == DiscoveredProductStatus.SKELETON
        assert product.discovery_source == DiscoverySource.COMPETITION

        # Verify awards data stored correctly
        assert len(product.awards) == 1
        assert product.awards[0]["competition"] == "IWSC"
        assert product.awards[0]["year"] == 2024
        assert product.awards[0]["medal"] == "Gold"

        # Verify minimal extracted_data
        assert product.extracted_data.get("name") == "Glenfiddich 18 Year Old"
        assert "award" in product.extracted_data or len(product.awards) > 0


class TestSerpAPITripleSearchTrigger:
    """Tests for SerpAPI triple search trigger for skeleton enrichment."""

    @pytest.mark.asyncio
    async def test_triggers_three_searches_per_skeleton(self):
        """Skeleton enrichment triggers 3 SerpAPI searches: price, review, official."""
        from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher
        from crawler.discovery.serpapi_client import SerpAPIClient

        searcher = EnrichmentSearcher(api_key="test_key")

        # Mock the underlying SerpAPI client
        with patch.object(
            searcher.serpapi_client, "search", new_callable=AsyncMock
        ) as mock_search:
            # Return mock search results
            mock_search.return_value = [
                MagicMock(url="https://example.com/buy", domain="example.com"),
            ]

            product_name = "Glenfiddich 18 Year Old"
            results = await searcher.search_for_enrichment(product_name)

            # Should have made 3 searches
            assert mock_search.call_count == 3

            # Verify search query types
            calls = mock_search.call_args_list
            queries = [call.args[0] if call.args else call.kwargs.get("query", "") for call in calls]

            # Check for price/buy search
            assert any("price" in q.lower() or "buy" in q.lower() for q in queries)
            # Check for review search
            assert any("review" in q.lower() or "tasting" in q.lower() for q in queries)
            # Check for official site search
            assert any("official" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_queues_discovered_urls_with_high_priority(self):
        """URLs discovered from skeleton enrichment are queued with priority=10."""
        from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher

        searcher = EnrichmentSearcher(api_key="test_key")

        with patch.object(
            searcher.serpapi_client, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [
                MagicMock(url="https://example.com/product", domain="example.com"),
            ]

            product_name = "Glenfiddich 18 Year Old"
            results = await searcher.search_for_enrichment(product_name)

            # Verify results contain priority information
            assert len(results) > 0
            for result in results:
                assert result.get("priority") == 10


class TestFuzzyMatchingForEnrichment:
    """Tests for fuzzy name matching for skeleton enrichment."""

    def test_matches_skeleton_with_similar_name(self):
        """Fuzzy matching finds skeleton products with 85%+ name similarity."""
        from crawler.discovery.competitions.fuzzy_matcher import SkeletonMatcher

        matcher = SkeletonMatcher(threshold=85)

        # Test various name variations
        test_cases = [
            # (skeleton_name, crawled_name, should_match)
            ("Glenfiddich 18 Year Old", "Glenfiddich 18 Year Old Single Malt", True),
            ("Glenfiddich 18", "Glenfiddich 18 Year Old", True),
            ("The Macallan 12", "Macallan 12 Year Old", True),
            ("Ardbeg Uigeadail", "Ardbeg Uigeadail Single Malt", True),
            ("Glenfiddich 18", "Johnnie Walker Blue", False),
            ("Lagavulin 16", "Talisker 10", False),
        ]

        for skeleton_name, crawled_name, should_match in test_cases:
            match_score = matcher.calculate_similarity(skeleton_name, crawled_name)
            is_match = match_score >= 85

            assert is_match == should_match, (
                f"Expected match={should_match} for "
                f"'{skeleton_name}' vs '{crawled_name}' (score: {match_score})"
            )

    @pytest.mark.django_db
    def test_updates_skeleton_to_pending_after_enrichment(self):
        """Skeleton status changes to 'pending' after enrichment with matched data."""
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.discovery.competitions.fuzzy_matcher import SkeletonMatcher
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus

        manager = SkeletonProductManager()
        matcher = SkeletonMatcher(threshold=85)

        # Create skeleton product
        award_data = {
            "product_name": "Glenfiddich 18 Year Old",
            "producer": "Glenfiddich",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
            "category": "Single Malt Scotch",
        }
        skeleton = manager.create_skeleton_product(award_data)
        assert skeleton.status == DiscoveredProductStatus.SKELETON

        # Enriched data from crawled page
        enriched_data = {
            "name": "Glenfiddich 18 Year Old Single Malt Scotch",
            "brand": "Glenfiddich",
            "price": "89.99",
            "volume_ml": 750,
            "abv": 40.0,
            "description": "A rich and complex single malt whisky.",
        }

        # Match and enrich
        match_result = matcher.match_and_enrich(
            skeleton=skeleton,
            crawled_name=enriched_data["name"],
            enriched_data=enriched_data,
        )

        assert match_result is True
        skeleton.refresh_from_db()
        assert skeleton.status == DiscoveredProductStatus.PENDING
        assert skeleton.enriched_data.get("price") == "89.99"


class TestCompetitionParsing:
    """Tests for competition result page parsing."""

    def test_parses_iwsc_results_format(self):
        """IWSC parser extracts product name, medal, year, and producer."""
        from crawler.discovery.competitions.parsers import IWSCParser

        # Sample IWSC results HTML structure
        iwsc_html = """
        <html>
        <body>
            <div class="results-list">
                <div class="result-item">
                    <h3 class="product-name">Glenfiddich 18 Year Old</h3>
                    <span class="medal gold">Gold</span>
                    <span class="producer">William Grant & Sons</span>
                    <span class="category">Single Malt Scotch</span>
                </div>
                <div class="result-item">
                    <h3 class="product-name">Macallan 12 Double Cask</h3>
                    <span class="medal silver">Silver</span>
                    <span class="producer">The Macallan</span>
                    <span class="category">Single Malt Scotch</span>
                </div>
            </div>
        </body>
        </html>
        """

        parser = IWSCParser()
        results = parser.parse(iwsc_html, year=2024)

        assert len(results) >= 2

        # Verify first result
        glenfiddich = next((r for r in results if "Glenfiddich" in r["product_name"]), None)
        assert glenfiddich is not None
        assert glenfiddich["medal"] == "Gold"
        assert glenfiddich["year"] == 2024
        assert "Grant" in glenfiddich.get("producer", "") or glenfiddich.get("producer")

    def test_parses_world_whiskies_awards_format(self):
        """World Whiskies Awards parser extracts winners with award category."""
        from crawler.discovery.competitions.parsers import WorldWhiskiesAwardsParser

        # Sample WWA results HTML structure
        wwa_html = """
        <html>
        <body>
            <div class="winners-section">
                <div class="winner-card">
                    <h4 class="award-title">World's Best Single Malt</h4>
                    <div class="winner-name">Kavalan Solist Vinho Barrique</div>
                    <div class="distillery">Kavalan Distillery</div>
                    <div class="country">Taiwan</div>
                </div>
                <div class="winner-card">
                    <h4 class="award-title">Best Scotch Single Malt</h4>
                    <div class="winner-name">Glenfarclas 25 Year Old</div>
                    <div class="distillery">Glenfarclas Distillery</div>
                    <div class="country">Scotland</div>
                </div>
            </div>
        </body>
        </html>
        """

        parser = WorldWhiskiesAwardsParser()
        results = parser.parse(wwa_html, year=2024)

        assert len(results) >= 2

        # Verify Kavalan result
        kavalan = next((r for r in results if "Kavalan" in r["product_name"]), None)
        assert kavalan is not None
        assert kavalan["competition"] == "World Whiskies Awards"
        assert "World's Best" in kavalan.get("medal", "") or kavalan.get("award_category")
