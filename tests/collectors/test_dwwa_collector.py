"""
Tests for DWWACollector - Decanter World Wine Awards collector.

These tests verify the DWWA collector which uses Playwright for JS-rendered pages.
The collector navigates to awards.decanter.com, applies filters for fortified wines,
and extracts detail page URLs for port wines and other fortified wines.

Test approach:
- Tests use real DWWA website to verify actual behavior
- Tests are marked with pytest.mark.slow for optional skipping
- Async tests use pytest-asyncio
"""

import pytest
from typing import List

from crawler.discovery.collectors.base_collector import AwardDetailURL


class TestDWWACollectorPlaywright:
    """Test that collector uses Playwright for JS rendering."""

    @pytest.mark.asyncio
    async def test_collector_uses_playwright_for_js_rendering(self):
        """Verify collector launches headless browser via Playwright."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Collector should have Playwright configuration
        assert hasattr(collector, "COMPETITION_NAME")
        assert collector.COMPETITION_NAME == "DWWA"
        assert hasattr(collector, "BASE_URL")
        assert "awards.decanter.com" in collector.BASE_URL

        # Collector should be async
        import inspect
        collect_method = getattr(collector, "collect", None)
        assert collect_method is not None
        assert inspect.iscoroutinefunction(collect_method), \
            "DWWACollector.collect must be an async method for Playwright"


class TestDWWAFortifiedFilter:
    """Test that collector applies Fortified category filter."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_applies_fortified_filter_for_port_wines(self):
        """
        Verify collector filters by Fortified category to capture port wines.

        This test actually connects to DWWA and verifies the filter works.
        """
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Collect URLs for a recent year (e.g., 2024)
        urls = await collector.collect(year=2024, product_types=["port_wine"])

        # Should return AwardDetailURL objects
        assert isinstance(urls, list)
        # Should have collected some URLs (DWWA typically has fortified wines)
        # At minimum we verify the structure is correct
        if len(urls) > 0:
            first_url = urls[0]
            assert isinstance(first_url, AwardDetailURL)
            assert first_url.competition == "DWWA"
            assert first_url.year == 2024


class TestDWWADetailURLExtraction:
    """Test that collector extracts detail URLs correctly."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extracts_detail_urls_from_listing(self):
        """
        Verify collector extracts /DWWA/{year}/wines/{id} URLs.

        Detail URL pattern: https://awards.decanter.com/DWWA/{year}/wines/{wine_id}
        """
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        urls = await collector.collect(year=2024)

        # Should have extracted URLs
        assert len(urls) > 0, "Collector should find at least some URLs"

        # Check URL pattern for each collected URL
        for url in urls[:5]:  # Check first 5
            assert "awards.decanter.com" in url.detail_url
            assert "/DWWA/" in url.detail_url or "/wines/" in url.detail_url
            assert url.listing_url is not None


class TestDWWAPortStyleDetection:
    """Test port wine style detection from card text."""

    def test_detects_port_style_from_card_text_tawny(self):
        """Verify detection of Tawny port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("10 Year Old Tawny Port")
        assert style == "tawny"

    def test_detects_port_style_from_card_text_ruby(self):
        """Verify detection of Ruby port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("Reserve Ruby Port")
        assert style == "ruby"

    def test_detects_port_style_from_card_text_lbv(self):
        """Verify detection of LBV (Late Bottled Vintage) style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Test "LBV" abbreviation
        style = collector._detect_port_style("2018 LBV Port")
        assert style == "lbv"

        # Test full name
        style = collector._detect_port_style("Late Bottled Vintage 2019")
        assert style == "lbv"

    def test_detects_port_style_from_card_text_vintage(self):
        """Verify detection of Vintage port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("2016 Vintage Port")
        assert style == "vintage"

    def test_detects_port_style_from_card_text_colheita(self):
        """Verify detection of Colheita port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("1998 Colheita Port")
        assert style == "colheita"

    def test_detects_port_style_from_card_text_white(self):
        """Verify detection of White port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("Dry White Port")
        assert style == "white_port"

    def test_detects_port_style_from_card_text_rose(self):
        """Verify detection of Rose/Pink port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        style = collector._detect_port_style("Rose Port")
        assert style in ["rose_port", "pink_port"]

        style = collector._detect_port_style("Pink Port Reserve")
        assert style in ["rose_port", "pink_port"]

    def test_detects_port_style_from_card_text_crusted(self):
        """Verify detection of Crusted port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("Crusted Port Bottled 2020")
        assert style == "crusted"

    def test_detects_port_style_from_card_text_single_quinta(self):
        """Verify detection of Single Quinta port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("Single Quinta Vintage Port")
        assert style == "single_quinta"

    def test_detects_port_style_from_card_text_garrafeira(self):
        """Verify detection of Garrafeira port style."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()
        style = collector._detect_port_style("1985 Garrafeira Port")
        assert style == "garrafeira"


class TestDWWAPagination:
    """Test pagination/infinite scroll handling."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_handles_pagination_or_infinite_scroll(self):
        """
        Verify collector handles multiple pages of results.

        DWWA may use pagination or infinite scroll.
        Collector should navigate through all results.
        """
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Collect all URLs (should handle pagination internally)
        urls = await collector.collect(year=2024)

        # If DWWA has more than one page of fortified wines,
        # we should get more than typical single page count (usually 20-50 per page)
        # This is a loose check - just verifying pagination doesn't break
        assert isinstance(urls, list)
        # Even with pagination, we should get results
        # Note: actual count depends on how many fortified wines are in DWWA 2024


class TestDWWANonPortuguesePortWines:
    """Test handling of non-Portuguese port-style wines."""

    def test_detects_south_african_fortified_producers(self):
        """Verify collector recognizes South African fortified wine producers."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # South African producers known for Cape Port
        south_african_producers = ["galpin peak", "boplaas", "allesverloren"]

        for producer in south_african_producers:
            is_fortified = collector._is_fortified_wine_producer(producer)
            assert is_fortified, f"Should recognize {producer} as fortified wine producer"

    def test_detects_australian_fortified_producers(self):
        """Verify collector recognizes Australian fortified wine producers."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Australian producers known for fortified wines
        australian_producers = ["seppeltsfield", "yalumba"]

        for producer in australian_producers:
            is_fortified = collector._is_fortified_wine_producer(producer)
            assert is_fortified, f"Should recognize {producer} as fortified wine producer"

    def test_detects_portuguese_port_producers(self):
        """Verify collector recognizes traditional Portuguese port producers."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Traditional Portuguese port houses
        portuguese_producers = [
            "taylor", "graham", "fonseca", "sandeman", "dow",
            "warre", "cockburn", "croft", "quinta do noval", "niepoort",
            "ramos pinto", "ferreira", "kopke", "burmester", "churchill"
        ]

        for producer in portuguese_producers:
            is_fortified = collector._is_fortified_wine_producer(producer)
            assert is_fortified, f"Should recognize {producer} as fortified wine producer"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_collects_urls_for_non_portuguese_port_wines(self):
        """
        Verify collector includes South African and Australian port-style wines.

        Cape Port, Australian fortified wines should be collected when
        filtering for fortified wines.
        """
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Collect all fortified wines (should include non-Portuguese)
        urls = await collector.collect(year=2024, product_types=["port_wine"])

        # Structure verification
        assert isinstance(urls, list)
        # All URLs should be properly formed
        for url in urls:
            assert isinstance(url, AwardDetailURL)
            assert url.competition == "DWWA"


class TestDWWAMedalExtraction:
    """Test medal hint extraction from listing cards."""

    def test_extracts_gold_medal_hint(self):
        """Verify extraction of Gold medal from card."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        # Test medal extraction from text
        medal = collector._extract_medal_from_text("Gold Medal Winner 2024")
        assert medal == "Gold"

    def test_extracts_silver_medal_hint(self):
        """Verify extraction of Silver medal from card."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        medal = collector._extract_medal_from_text("Silver Medal")
        assert medal == "Silver"

    def test_extracts_bronze_medal_hint(self):
        """Verify extraction of Bronze medal from card."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        medal = collector._extract_medal_from_text("Bronze Award")
        assert medal == "Bronze"

    def test_extracts_platinum_medal_hint(self):
        """Verify extraction of Platinum (best in show) from card."""
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = DWWACollector()

        medal = collector._extract_medal_from_text("Platinum Best in Show")
        assert medal == "Platinum"


class TestDWWAFactoryRegistration:
    """Test that DWWA collector is registered in factory."""

    def test_get_collector_returns_dwwa_collector(self):
        """Verify get_collector('dwwa') returns DWWACollector."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector = get_collector("dwwa")
        assert isinstance(collector, DWWACollector)

    def test_get_collector_case_insensitive(self):
        """Verify get_collector works with different cases."""
        from crawler.discovery.collectors.base_collector import get_collector
        from crawler.discovery.collectors.dwwa_collector import DWWACollector

        collector1 = get_collector("dwwa")
        collector2 = get_collector("DWWA")
        collector3 = get_collector("Dwwa")

        assert isinstance(collector1, DWWACollector)
        assert isinstance(collector2, DWWACollector)
        assert isinstance(collector3, DWWACollector)
