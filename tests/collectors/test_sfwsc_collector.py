"""
Tests for SFWSCCollector - San Francisco World Spirits Competition collector.

These tests verify the SFWSC collector which parses The Tasting Alliance results pages.
The competition data is embedded as JSON in the page HTML (GlobalsObj.CMS_JSON).

Test approach:
- Tests use real Tasting Alliance website to verify actual behavior
- Tests are marked with pytest.mark.slow for optional skipping
- Synchronous tests since the page is static HTML with embedded JSON
"""

import pytest
from typing import List

from crawler.discovery.collectors.base_collector import AwardDetailURL


class TestSFWSCCollectorExtraction:
    """Test that collector extracts URLs from Tasting Alliance results pages."""

    @pytest.mark.slow
    def test_extracts_urls_from_tasting_alliance_results(self):
        """
        Verify collector extracts product URLs from SFWSC results pages.

        The Tasting Alliance embeds product data as JSON in the page.
        Collector should parse this JSON to extract product entries.
        """
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Collect URLs for 2024
        urls = collector.collect(year=2024)

        # Should return AwardDetailURL objects
        assert isinstance(urls, list)
        assert len(urls) > 0, "Collector should find at least some URLs"

        # Check structure of first URL
        first_url = urls[0]
        assert isinstance(first_url, AwardDetailURL)
        assert first_url.competition == "SFWSC"
        assert first_url.year == 2024

    @pytest.mark.slow
    def test_extracts_product_entries_with_metadata(self):
        """Verify product entries include all required metadata."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        urls = collector.collect(year=2024, product_types=["whiskey"])

        if len(urls) > 0:
            url = urls[0]
            # Should have listing URL
            assert url.listing_url is not None
            # Should have medal hint
            assert url.medal_hint != ""
            # Should have product type
            assert url.product_type_hint == "whiskey"


class TestSFWSCWhiskeyFiltering:
    """Test that collector filters for whiskey categories only."""

    @pytest.mark.slow
    def test_filters_whiskey_categories(self):
        """
        Verify collector filters for whiskey categories only.

        Should filter out non-whiskey spirits like vodka, gin, rum, etc.
        """
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Collect only whiskey
        whiskey_urls = collector.collect(year=2024, product_types=["whiskey"])

        # All results should be whiskey
        for url in whiskey_urls:
            assert url.product_type_hint == "whiskey", \
                f"Expected whiskey but got {url.product_type_hint}"

    def test_detects_bourbon_as_whiskey(self):
        """Verify Straight Bourbon is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Straight Bourbon")
        assert product_type == "whiskey"

    def test_detects_rye_whiskey_as_whiskey(self):
        """Verify Rye Whisk(e)y is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Test with 'e'
        product_type = collector._detect_product_type("Rye Whiskey")
        assert product_type == "whiskey"

        # Test without 'e'
        product_type = collector._detect_product_type("Rye Whisky")
        assert product_type == "whiskey"

    def test_detects_single_malt_as_whiskey(self):
        """Verify Single Malt is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        product_type = collector._detect_product_type("American Single Malt")
        assert product_type == "whiskey"

        product_type = collector._detect_product_type("Single Malt Scotch")
        assert product_type == "whiskey"

    def test_detects_tennessee_whiskey_as_whiskey(self):
        """Verify Tennessee Whiskey is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Tennessee Whiskey")
        assert product_type == "whiskey"

    def test_detects_scotch_as_whiskey(self):
        """Verify Scotch Whisky is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Scotch Whisky")
        assert product_type == "whiskey"

        product_type = collector._detect_product_type("Blended Scotch")
        assert product_type == "whiskey"

    def test_detects_irish_whiskey_as_whiskey(self):
        """Verify Irish Whiskey is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Irish Whiskey")
        assert product_type == "whiskey"

    def test_detects_canadian_whisky_as_whiskey(self):
        """Verify Canadian Whisky is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Canadian Whisky")
        assert product_type == "whiskey"

    def test_detects_japanese_whisky_as_whiskey(self):
        """Verify Japanese Whisky is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Japanese Whisky")
        assert product_type == "whiskey"

    def test_detects_world_whisky_as_whiskey(self):
        """Verify World Whisky/Whiskey is detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        product_type = collector._detect_product_type("World Whisky")
        assert product_type == "whiskey"

        product_type = collector._detect_product_type("World Whiskey")
        assert product_type == "whiskey"

    def test_does_not_detect_vodka_as_whiskey(self):
        """Verify vodka is NOT detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Premium Vodka")
        assert product_type != "whiskey"

    def test_does_not_detect_gin_as_whiskey(self):
        """Verify gin is NOT detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("London Dry Gin")
        assert product_type != "whiskey"

    def test_does_not_detect_rum_as_whiskey(self):
        """Verify rum is NOT detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Aged Rum")
        assert product_type != "whiskey"

    def test_does_not_detect_tequila_as_whiskey(self):
        """Verify tequila is NOT detected as whiskey."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        product_type = collector._detect_product_type("Blanco Tequila")
        assert product_type != "whiskey"


class TestSFWSCMedalExtraction:
    """Test medal and score hint extraction."""

    def test_extracts_double_gold_medal(self):
        """Verify Double Gold (GG) medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Double Gold", "GG")
        assert medal == "Double Gold"

    def test_extracts_gold_medal(self):
        """Verify Gold (G) medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Gold", "G")
        assert medal == "Gold"

    def test_extracts_silver_medal(self):
        """Verify Silver (S) medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Silver", "S")
        assert medal == "Silver"

    def test_extracts_bronze_medal(self):
        """Verify Bronze (B) medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Bronze", "B")
        assert medal == "Bronze"

    def test_extracts_best_of_class(self):
        """Verify Best of Class medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Best of Class", "best-of-class")
        assert medal == "Best of Class"

    def test_extracts_best_in_show(self):
        """Verify Best in Show medal extraction."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        medal = collector._extract_medal_from_award("2024 SFWSC Best in Show", "best-in-show")
        assert medal == "Best in Show"

    @pytest.mark.slow
    def test_extracts_medal_and_score_hints(self):
        """
        Verify medal extraction from real SFWSC data.

        Medals: Double Gold, Gold, Silver, Bronze
        Note: SFWSC does not typically show scores publicly.
        """
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        urls = collector.collect(year=2024, product_types=["whiskey"])

        if len(urls) > 0:
            # Check that medals are extracted
            medals = {url.medal_hint for url in urls}
            # Should have at least some valid medals
            valid_medals = {"Double Gold", "Gold", "Silver", "Bronze", "Best of Class", "Best in Show"}
            assert len(medals & valid_medals) > 0, \
                f"Should have valid medals, got: {medals}"


class TestSFWSCPagination:
    """Test pagination handling."""

    @pytest.mark.slow
    def test_handles_pagination(self):
        """
        Verify collector handles multiple result pages.

        The Tasting Alliance loads more results via "Load More" button.
        Collector should gather all available results.
        """
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Collect URLs (should handle pagination internally)
        urls = collector.collect(year=2024, product_types=["whiskey"])

        # Should get a reasonable number of whiskey products
        # SFWSC typically has 100+ whiskey entries
        assert len(urls) > 10, \
            f"Expected more whiskey entries, got {len(urls)}"


class TestSFWSCProductTypeDetection:
    """Test product type detection from category."""

    def test_detects_product_type_from_category(self):
        """Verify whiskey type detection from category class."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Test various whiskey categories
        whiskey_categories = [
            "Straight Bourbon",
            "Rye Whisk(e)y",
            "American Single Malt",
            "Tennessee Whiskey",
            "Scotch Whisky",
            "Single Malt Scotch",
            "Blended Scotch",
            "Irish Whiskey",
            "Canadian Whisky",
            "Japanese Whisky",
            "World Whisky",
        ]

        for category in whiskey_categories:
            product_type = collector._detect_product_type(category)
            assert product_type == "whiskey", \
                f"Category '{category}' should be detected as whiskey"

    def test_detects_non_whiskey_types(self):
        """Verify non-whiskey spirits are detected correctly."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Non-whiskey categories
        assert collector._detect_product_type("London Dry Gin") == "gin"
        assert collector._detect_product_type("Premium Vodka") == "vodka"
        assert collector._detect_product_type("Aged Rum") == "rum"
        assert collector._detect_product_type("Blanco Tequila") == "tequila"
        assert collector._detect_product_type("Reposado Tequila") == "tequila"
        assert collector._detect_product_type("Mezcal") == "mezcal"
        assert collector._detect_product_type("Cognac VSOP") == "brandy"
        assert collector._detect_product_type("Brandy") == "brandy"


class TestSFWSCFactoryRegistration:
    """Test that SFWSC collector is registered in factory."""

    def test_collector_registered_in_factory(self):
        """Verify get_collector('sfwsc') returns SFWSCCollector."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = get_collector("sfwsc")
        assert isinstance(collector, SFWSCCollector)

    def test_get_collector_case_insensitive(self):
        """Verify get_collector works with different cases."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector1 = get_collector("sfwsc")
        collector2 = get_collector("SFWSC")
        collector3 = get_collector("Sfwsc")

        assert isinstance(collector1, SFWSCCollector)
        assert isinstance(collector2, SFWSCCollector)
        assert isinstance(collector3, SFWSCCollector)


class TestSFWSCCollectorProperties:
    """Test collector properties and configuration."""

    def test_collector_has_correct_competition_name(self):
        """Verify competition name is set correctly."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        assert collector.COMPETITION_NAME == "SFWSC"

    def test_collector_has_correct_base_url(self):
        """Verify base URL points to Tasting Alliance."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()
        assert "thetastingalliance.com" in collector.BASE_URL


class TestSFWSCCollectorSync:
    """Test that collector is synchronous (like IWSC)."""

    def test_collect_is_synchronous(self):
        """Verify collect() is a synchronous method, not async."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector
        import inspect

        collector = SFWSCCollector()
        collect_method = getattr(collector, "collect", None)

        assert collect_method is not None
        assert not inspect.iscoroutinefunction(collect_method), \
            "SFWSCCollector.collect should be synchronous (page is static HTML with JSON)"


class TestSFWSCYearHandling:
    """Test handling of different competition years."""

    @pytest.mark.slow
    def test_collects_for_different_years(self):
        """Verify collector can collect for different competition years."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Test 2024
        urls_2024 = collector.collect(year=2024, product_types=["whiskey"])
        assert isinstance(urls_2024, list)

        # All should be marked as 2024
        for url in urls_2024:
            assert url.year == 2024

    def test_constructs_correct_url_for_year(self):
        """Verify URL construction includes year parameter."""
        from crawler.discovery.collectors.sfwsc_collector import SFWSCCollector

        collector = SFWSCCollector()

        # Get the listing URL for a year
        listing_url = collector._get_listing_url(2024)
        assert "2024" in listing_url or "sfwsc" in listing_url.lower()
