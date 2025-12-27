"""
Tests for Hub & Spoke discovery system.

Task Group 4: Hub & Spoke Discovery
These tests verify hub page parsing, SerpAPI integration, and CrawlerSource creation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal


class TestHubPageParsing:
    """Tests for hub page parsing and brand extraction."""

    def test_parses_brand_listings_from_hub_page(self):
        """Hub page parser extracts brand names and links from retailer hub pages."""
        from crawler.discovery.hub_parser import HubPageParser

        # Sample hub page HTML structure (similar to thewhiskyexchange.com/brands)
        hub_html = """
        <html>
        <body>
            <div class="brand-list">
                <a href="/brands/glenfiddich" class="brand-item">
                    <span class="brand-name">Glenfiddich</span>
                </a>
                <a href="/brands/macallan" class="brand-item">
                    <span class="brand-name">The Macallan</span>
                </a>
                <a href="https://www.ardbeg.com" class="brand-item external">
                    <span class="brand-name">Ardbeg</span>
                </a>
            </div>
        </body>
        </html>
        """

        parser = HubPageParser()
        brands = parser.parse_brands(
            html=hub_html,
            hub_url="https://www.thewhiskyexchange.com/brands",
        )

        # Verify brands were extracted
        assert len(brands) >= 3
        brand_names = [b.name for b in brands]
        assert "Glenfiddich" in brand_names
        assert "The Macallan" in brand_names
        assert "Ardbeg" in brand_names

        # Verify external link was captured for Ardbeg
        ardbeg = next((b for b in brands if b.name == "Ardbeg"), None)
        assert ardbeg is not None
        assert ardbeg.external_url == "https://www.ardbeg.com"

    def test_handles_pagination_links(self):
        """Hub parser detects pagination links for multi-page brand listings."""
        from crawler.discovery.hub_parser import HubPageParser

        # Sample hub page with pagination
        hub_html = """
        <html>
        <body>
            <div class="brand-list">
                <a href="/brands/glenfiddich" class="brand-item">
                    <span class="brand-name">Glenfiddich</span>
                </a>
            </div>
            <div class="pagination">
                <a href="/brands?page=2" class="next">Next</a>
                <a href="/brands?page=3">3</a>
            </div>
        </body>
        </html>
        """

        parser = HubPageParser()
        pagination = parser.extract_pagination_links(
            html=hub_html,
            hub_url="https://www.thewhiskyexchange.com/brands",
        )

        # Verify pagination links were found
        assert len(pagination) >= 1
        assert any("/brands?page=2" in link for link in pagination)


class TestSerpAPIQueryGeneration:
    """Tests for SerpAPI fallback query generation."""

    def test_generates_serpapi_query_for_brand(self):
        """SerpAPI client generates proper query format for brand discovery."""
        from crawler.discovery.serpapi_client import SerpAPIClient

        client = SerpAPIClient(api_key="test_key")
        query = client.build_brand_query("Glenfiddich")

        assert "Glenfiddich" in query
        assert "official site" in query.lower() or "official" in query.lower()
        # Query should target whiskey context
        assert "whiskey" in query.lower() or "whisky" in query.lower()

    @pytest.mark.asyncio
    async def test_serpapi_parses_official_domain_from_results(self):
        """SerpAPI client extracts official domain from search results."""
        from crawler.discovery.serpapi_client import SerpAPIClient

        client = SerpAPIClient(api_key="test_key")

        # Mock SerpAPI response
        mock_response = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Glenfiddich - The World's Most Awarded Single Malt",
                    "link": "https://www.glenfiddich.com/",
                    "domain": "glenfiddich.com",
                    "snippet": "Official website of Glenfiddich single malt whisky.",
                },
                {
                    "position": 2,
                    "title": "Buy Glenfiddich - The Whisky Exchange",
                    "link": "https://www.thewhiskyexchange.com/brands/glenfiddich",
                    "domain": "thewhiskyexchange.com",
                    "snippet": "Shop for Glenfiddich whisky.",
                },
            ]
        }

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await client.search_brand_official_site("Glenfiddich")

            # Should identify glenfiddich.com as the official site
            assert result is not None
            assert result.domain == "glenfiddich.com"
            assert result.url == "https://www.glenfiddich.com/"
            assert result.is_likely_official is True


class TestCrawlerSourceCreation:
    """Tests for CrawlerSource creation with discovery_method='hub'."""

    @pytest.mark.django_db
    def test_creates_crawler_source_with_hub_discovery_method(self):
        """Creates CrawlerSource with correct discovery_method when discovered via hub."""
        from crawler.discovery.spoke_registry import SpokeRegistry
        from crawler.models import CrawlerSource, DiscoveryMethod

        registry = SpokeRegistry()

        # Create source from hub discovery
        source = registry.register_spoke(
            name="Glenfiddich",
            base_url="https://www.glenfiddich.com/",
            discovered_from_hub="thewhiskyexchange.com",
        )

        assert source is not None
        assert source.discovery_method == DiscoveryMethod.HUB
        assert source.is_active is True
        # Verify it's in the database
        assert CrawlerSource.objects.filter(base_url="https://www.glenfiddich.com/").exists()

    @pytest.mark.django_db
    def test_prevents_duplicate_source_creation(self):
        """SpokeRegistry prevents creating duplicate CrawlerSources for same domain."""
        from crawler.discovery.spoke_registry import SpokeRegistry
        from crawler.models import CrawlerSource

        registry = SpokeRegistry()

        # Create first source
        source1 = registry.register_spoke(
            name="Glenfiddich",
            base_url="https://www.glenfiddich.com/",
            discovered_from_hub="thewhiskyexchange.com",
        )

        # Attempt to create duplicate
        source2 = registry.register_spoke(
            name="Glenfiddich Whisky",
            base_url="https://www.glenfiddich.com/",
            discovered_from_hub="masterofmalt.com",
        )

        # Should return existing source, not create duplicate
        assert source2.id == source1.id
        # Only one source should exist
        assert CrawlerSource.objects.filter(
            base_url__icontains="glenfiddich.com"
        ).count() == 1
