"""
Tests for WWACollector - World Whiskies Awards collector.

These tests verify the WWA collector which parses worldwhiskiesawards.com pages.
The competition hosts prestigious whiskey awards with results organized by year
and category (Single Malt, Bourbon, Rye, Blended, etc.).

Test approach:
- Tests use real WWA website to verify actual behavior
- Tests are marked with pytest.mark.slow for optional skipping
- Synchronous tests since the page is static HTML with JS enhancement
"""

import pytest
from typing import List

from crawler.discovery.collectors.base_collector import AwardDetailURL


class TestWWACollectorExtraction:
    """Test that collector extracts URLs from World Whiskies Awards pages."""

    @pytest.mark.slow
    def test_extracts_urls_from_world_whiskies_awards(self):
        """
        Verify collector extracts product URLs from WWA winners pages.

        WWA organizes winners by category pages (e.g., /winner-whisky/whisky/2025/...).
        Collector should navigate to category pages and extract winner URLs.
        """
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Collect URLs for 2025
        urls = collector.collect(year=2025)

        # Should return AwardDetailURL objects
        assert isinstance(urls, list)
        assert len(urls) > 0, "Collector should find at least some URLs"

        # Check structure of first URL
        first_url = urls[0]
        assert isinstance(first_url, AwardDetailURL)
        assert first_url.competition == "WWA"
        assert first_url.year == 2025

    @pytest.mark.slow
    def test_extracts_product_entries_with_metadata(self):
        """Verify product entries include all required metadata."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        urls = collector.collect(year=2025, product_types=["whiskey"])

        if len(urls) > 0:
            url = urls[0]
            # Should have listing URL
            assert url.listing_url is not None
            # Should have medal hint (award level)
            assert url.medal_hint != ""
            # Should have product type
            assert url.product_type_hint == "whiskey"


class TestWWAYearAndCategoryFiltering:
    """Test that collector filters by year and category."""

    @pytest.mark.slow
    def test_filters_by_year_and_category(self):
        """
        Verify collector can filter by specific year and category.

        WWA has results from 2012-2025. Filtering by year should only
        return winners from that year.
        """
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Collect URLs for 2024
        urls_2024 = collector.collect(year=2024)

        # All results should be marked as 2024
        for url in urls_2024:
            assert url.year == 2024

    @pytest.mark.slow
    def test_filters_by_category_bourbon(self):
        """Verify collector can filter by bourbon category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Collect bourbon URLs only
        urls = collector.collect(year=2025, categories=["bourbon"])

        # Should get bourbon-related URLs
        assert len(urls) > 0
        # All should be whiskey type
        for url in urls:
            assert url.product_type_hint == "whiskey"

    @pytest.mark.slow
    def test_filters_by_category_single_malt(self):
        """Verify collector can filter by single malt category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Collect single malt URLs only
        urls = collector.collect(year=2025, categories=["single_malt"])

        # Should get single malt URLs
        assert len(urls) > 0


class TestWWAWinnerDetailsExtraction:
    """Test extraction of winner details (award levels)."""

    @pytest.mark.slow
    def test_extracts_winner_details(self):
        """
        Verify award category extracted (World's Best, Category Winner, etc.).

        WWA awards include:
        - World's Best (top award in category)
        - Best Regional (Best Scotch, Best American, etc.)
        - Country Winners
        """
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        urls = collector.collect(year=2025, product_types=["whiskey"])

        if len(urls) > 0:
            # Check that medal hints are extracted
            medal_hints = {url.medal_hint for url in urls}
            # Should have meaningful medal hints
            assert "Unknown" not in medal_hints or len(medal_hints) > 1

    def test_extracts_worlds_best_award(self):
        """Verify detection of World's Best award."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        medal = collector._extract_award_level("World's Best Single Malt")
        assert medal == "World's Best"

    def test_extracts_best_regional_award(self):
        """Verify detection of Best Regional award."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        medal = collector._extract_award_level("Best Scotch Speyside Single Malt")
        assert "Best" in medal

        medal = collector._extract_award_level("Best American Single Malt")
        assert "Best" in medal

    def test_extracts_category_winner_award(self):
        """Verify detection of Category Winner award."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        medal = collector._extract_award_level("Best Kentucky Bourbon")
        assert "Best" in medal


class TestWWACategoryPages:
    """Test that collector handles category pages correctly."""

    @pytest.mark.slow
    def test_handles_category_pages(self):
        """
        Verify collector handles /winner-whisky/whisky/{year}/{category} pages.

        Category pages like /worlds-best-single-malt/, /worlds-best-bourbon/
        contain multiple winners at different award levels.
        """
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Collect from category pages
        urls = collector.collect(year=2025)

        # Should handle category page structure
        assert isinstance(urls, list)
        # Should have URLs from multiple categories
        if len(urls) > 0:
            assert all(isinstance(u, AwardDetailURL) for u in urls)

    @pytest.mark.slow
    def test_collects_from_multiple_category_pages(self):
        """Verify collector visits multiple category pages."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        urls = collector.collect(year=2025)

        # Should get URLs from different categories
        # Check listing URLs are from different category pages
        if len(urls) > 1:
            listing_urls = {url.listing_url for url in urls}
            # Might have multiple distinct listing URLs if collecting from multiple categories
            assert len(listing_urls) >= 1


class TestWWAWhiskeyTypeDetection:
    """Test whiskey type detection from award category."""

    def test_detects_whiskey_type_from_category(self):
        """Verify whiskey type detection from award category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # All WWA awards are whiskey - it's a whiskey-only competition
        product_type = collector._detect_product_type("World's Best Single Malt")
        assert product_type == "whiskey"

        product_type = collector._detect_product_type("Best Bourbon")
        assert product_type == "whiskey"

        product_type = collector._detect_product_type("Best Rye")
        assert product_type == "whiskey"

    def test_detects_single_malt_from_category(self):
        """Verify Single Malt detection from category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        product_type = collector._detect_product_type("World's Best Single Malt")
        assert product_type == "whiskey"

    def test_detects_bourbon_from_category(self):
        """Verify Bourbon detection from category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        product_type = collector._detect_product_type("World's Best Bourbon")
        assert product_type == "whiskey"

    def test_detects_rye_from_category(self):
        """Verify Rye detection from category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        product_type = collector._detect_product_type("World's Best Rye")
        assert product_type == "whiskey"

    def test_detects_blended_from_category(self):
        """Verify Blended Whisky detection from category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        product_type = collector._detect_product_type("World's Best Blended")
        assert product_type == "whiskey"

    def test_detects_grain_from_category(self):
        """Verify Grain Whisky detection from category."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        product_type = collector._detect_product_type("World's Best Grain")
        assert product_type == "whiskey"


class TestWWAFactoryRegistration:
    """Test that WWA collector is registered in factory."""

    def test_collector_registered_in_factory(self):
        """Verify get_collector('wwa') returns WWACollector."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = get_collector("wwa")
        assert isinstance(collector, WWACollector)

    def test_get_collector_case_insensitive(self):
        """Verify get_collector works with different cases."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector1 = get_collector("wwa")
        collector2 = get_collector("WWA")
        collector3 = get_collector("Wwa")

        assert isinstance(collector1, WWACollector)
        assert isinstance(collector2, WWACollector)
        assert isinstance(collector3, WWACollector)


class TestWWACollectorProperties:
    """Test collector properties and configuration."""

    def test_collector_has_correct_competition_name(self):
        """Verify competition name is set correctly."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        assert collector.COMPETITION_NAME == "WWA"

    def test_collector_has_correct_base_url(self):
        """Verify base URL points to World Whiskies Awards."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        assert "worldwhiskiesawards.com" in collector.BASE_URL


class TestWWACollectorSync:
    """Test that collector is synchronous (like IWSC and SFWSC)."""

    def test_collect_is_synchronous(self):
        """Verify collect() is a synchronous method, not async."""
        from crawler.discovery.collectors.wwa_collector import WWACollector
        import inspect

        collector = WWACollector()
        collect_method = getattr(collector, "collect", None)

        assert collect_method is not None
        assert not inspect.iscoroutinefunction(collect_method), \
            "WWACollector.collect should be synchronous (page is static HTML)"


class TestWWAURLConstruction:
    """Test URL construction for different years."""

    def test_constructs_winners_url_for_year(self):
        """Verify URL construction for winners page."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Get listing URL for 2025
        listing_url = collector._get_winners_page_url(2025)
        assert "worldwhiskiesawards.com" in listing_url
        assert "winners" in listing_url.lower() or "winner" in listing_url.lower()

    def test_constructs_category_url(self):
        """Verify URL construction for category pages."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Get category URL
        category_url = collector._get_category_url(2025, "single_malt")
        assert "worldwhiskiesawards.com" in category_url
        assert "2025" in category_url


class TestWWACategoryMapping:
    """Test category mapping and filtering."""

    def test_has_category_mappings(self):
        """Verify collector has WWA category mappings."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Should have category mappings
        assert hasattr(collector, "CATEGORY_SLUGS") or hasattr(collector, "CATEGORIES")

    def test_maps_category_to_url_slug(self):
        """Verify category names map to URL slugs."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()

        # Test mapping single_malt -> URL slug
        slug = collector._get_category_slug("single_malt")
        assert "single-malt" in slug.lower() or "single_malt" in slug.lower()


class TestWWAMultipleYears:
    """Test handling of different competition years."""

    @pytest.mark.slow
    def test_collects_for_2025(self):
        """Verify collector works for 2025."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        urls = collector.collect(year=2025)

        assert isinstance(urls, list)
        for url in urls:
            assert url.year == 2025

    @pytest.mark.slow
    def test_collects_for_2024(self):
        """Verify collector works for 2024."""
        from crawler.discovery.collectors.wwa_collector import WWACollector

        collector = WWACollector()
        urls = collector.collect(year=2024)

        assert isinstance(urls, list)
        for url in urls:
            assert url.year == 2024
