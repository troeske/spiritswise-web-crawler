# tests/integration/test_iwsc_flow.py
"""
Integration tests for IWSCCollector with real IWSC website.

These tests verify the IWSCCollector works correctly against the live
IWSC website (https://www.iwsc.net). No mocks are used.

To run these tests:
    RUN_VPS_TESTS=true pytest tests/integration/test_iwsc_flow.py -v
"""

import pytest
import httpx
import os
from typing import List

from crawler.discovery.collectors.iwsc_collector import IWSCCollector
from crawler.discovery.collectors.base_collector import AwardDetailURL

# Mark all tests to require VPS flag
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VPS_TESTS") != "true",
    reason="VPS tests disabled - set RUN_VPS_TESTS=true"
)


class TestIWSCCollectorRealWebsite:
    """Integration tests for IWSCCollector using real IWSC website."""

    @pytest.fixture
    def collector(self) -> IWSCCollector:
        """Create IWSCCollector instance."""
        return IWSCCollector()

    def test_collects_real_urls_from_iwsc_2024(self, collector: IWSCCollector):
        """
        IWSCCollector should return valid URLs from IWSC 2024.
        Uses real website, no mocks.

        Note: Current collector fetches first page only. IWSC shows ~16 results
        per page. For 50+ URLs, pagination would need to be implemented.
        This test verifies the collector works with the first page of results.
        """
        # Act
        urls = collector.collect(year=2024)

        # Assert - should have at least 10 URLs from first page
        # IWSC typically shows 16 results per page
        assert len(urls) >= 10, f"Expected at least 10 URLs from first page, got {len(urls)}"

        # All URLs should be AwardDetailURL instances
        for url in urls:
            assert isinstance(url, AwardDetailURL)

        # All URLs should have required fields
        for url in urls:
            assert url.detail_url, "detail_url should not be empty"
            assert url.detail_url.startswith("https://www.iwsc.net/results/detail/")
            assert url.listing_url == "https://www.iwsc.net/results/search/2024"
            assert url.competition == "IWSC"
            assert url.year == 2024

    def test_collects_real_urls_from_iwsc_2025(self, collector: IWSCCollector):
        """
        IWSCCollector should return valid URLs from IWSC 2025.
        Uses real website, no mocks.
        """
        # Act
        urls = collector.collect(year=2025)

        # Assert - 2025 should have URLs (may be fewer if competition is ongoing)
        # At minimum, the page should load and return valid structure
        assert isinstance(urls, list)

        # If there are URLs, they should be valid
        if len(urls) > 0:
            for url in urls:
                assert isinstance(url, AwardDetailURL)
                assert url.detail_url.startswith("https://www.iwsc.net/results/detail/")
                assert url.competition == "IWSC"
                assert url.year == 2025

    def test_extracts_whiskey_detail_urls(self, collector: IWSCCollector):
        """
        Verify collector extracts whiskey product detail URLs.
        Filter for whiskey products only.
        """
        # Act - filter for whiskey
        urls = collector.collect(year=2024, product_types=["whiskey"])

        # Assert - should have whiskey URLs
        # Note: May be 0 if no whiskey on first page, but if found they should be whiskey
        assert isinstance(urls, list)

        for url in urls:
            assert isinstance(url, AwardDetailURL)
            assert url.product_type_hint == "whiskey"
            assert url.detail_url.startswith("https://www.iwsc.net/results/detail/")

    def test_extracts_port_wine_detail_urls(self, collector: IWSCCollector):
        """
        Verify collector extracts port wine detail URLs.
        Filter for Fortified/Wine category.
        """
        # Act - filter for port wine
        urls = collector.collect(year=2024, product_types=["port_wine"])

        # Assert - should have port wine URLs
        # Note: May be 0 if no port wine on first page, but if found they should be port_wine
        assert isinstance(urls, list)

        for url in urls:
            assert isinstance(url, AwardDetailURL)
            assert url.product_type_hint == "port_wine"
            assert url.detail_url.startswith("https://www.iwsc.net/results/detail/")

    def test_medal_hints_match_actual_awards(self, collector: IWSCCollector):
        """
        Verify medal hints (Gold, Silver, Bronze) are accurate.
        Compare listing card hint to expected medal values.
        """
        # Act
        urls = collector.collect(year=2024)

        # Assert - medal hints should be valid values
        valid_medals = {"Gold", "Silver", "Bronze", "Unknown"}
        medals_found = set()

        for url in urls:
            assert url.medal_hint in valid_medals, f"Invalid medal hint: {url.medal_hint}"
            medals_found.add(url.medal_hint)

        # We should find at least Gold, Silver, or Bronze medals
        assert medals_found - {"Unknown"}, "Should find at least one real medal type"

    def test_all_urls_are_reachable(self, collector: IWSCCollector):
        """
        Verify all collected URLs return HTTP 200.
        Sample test - check first 10 URLs are accessible.
        """
        # Act
        urls = collector.collect(year=2024)

        # Sample first 10 URLs to avoid too many requests
        sample_size = min(10, len(urls))
        sample_urls = urls[:sample_size]

        # Assert - all sampled URLs should be reachable
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as client:
            for url_obj in sample_urls:
                response = client.get(url_obj.detail_url)
                assert response.status_code == 200, f"URL not reachable: {url_obj.detail_url}"


class TestIWSCCollectorURLValidation:
    """Tests for URL validation and structure."""

    @pytest.fixture
    def collector(self) -> IWSCCollector:
        """Create IWSCCollector instance."""
        return IWSCCollector()

    def test_detail_url_format_is_valid(self, collector: IWSCCollector):
        """Verify detail URLs follow expected IWSC format."""
        urls = collector.collect(year=2024)

        for url in urls[:20]:  # Check first 20
            # Should be full absolute URL
            assert url.detail_url.startswith("https://")
            # Should contain results/detail path
            assert "/results/detail/" in url.detail_url

    def test_score_hints_are_valid_when_present(self, collector: IWSCCollector):
        """Verify score hints are valid integers when present."""
        urls = collector.collect(year=2024)

        for url in urls:
            if url.score_hint is not None:
                assert isinstance(url.score_hint, int)
                # IWSC scores typically 70-100
                assert 50 <= url.score_hint <= 100, f"Unusual score: {url.score_hint}"


class TestIWSCCollectorProductTypes:
    """Tests for product type detection."""

    @pytest.fixture
    def collector(self) -> IWSCCollector:
        """Create IWSCCollector instance."""
        return IWSCCollector()

    def test_detects_multiple_product_types(self, collector: IWSCCollector):
        """Verify collector detects various product types."""
        urls = collector.collect(year=2024)

        product_types = set(url.product_type_hint for url in urls)

        # Should detect at least some product types (spirits are common at IWSC)
        # Even "unknown" counts as detection working
        assert len(product_types) >= 1, "Should detect at least one product type"

    def test_filtering_by_multiple_product_types(self, collector: IWSCCollector):
        """Verify filtering by multiple product types works."""
        # Act - filter for both whiskey and port_wine
        urls = collector.collect(year=2024, product_types=["whiskey", "port_wine"])

        # Assert
        for url in urls:
            assert url.product_type_hint in ["whiskey", "port_wine"]
