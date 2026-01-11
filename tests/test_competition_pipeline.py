"""
Tests for the Competition Pipeline integration.

Tests the end-to-end flow from competition URL to skeleton to enrichment:
1. Competition parsing and skeleton creation
2. Skeleton deduplication
3. Enrichment search triggering
4. URL queuing from enrichment results

Phase 4 Update: Skeleton products now store awards as ProductAward records
instead of in a JSON field.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestCompetitionPipelineEndToEnd:
    """Tests for the complete competition pipeline flow."""

    @pytest.mark.django_db(transaction=True)
    def test_competition_discovery_creates_skeletons(self):
        """Competition discovery parses HTML and creates skeleton products."""
        from crawler.services.competition_orchestrator import CompetitionOrchestrator
        from crawler.models import (
            CrawlerSource,
            CrawlJob,
            DiscoveredProduct,
            DiscoveredProductStatus,
            DiscoverySource,
            SourceCategory,
            ProductAward,
        )

        # Create competition source
        source = CrawlerSource.objects.create(
            name="Test Competition",
            slug="test-competition",
            base_url="https://test-competition.com/results",
            category=SourceCategory.COMPETITION,
            product_types=["whiskey"],
            is_active=True,
        )
        job = CrawlJob.objects.create(source=source)

        # Sample competition HTML
        html_content = """
        <html>
        <body>
            <div class="results-list">
                <div class="result-item">
                    <h3 class="product-name">Glenfiddich 18 Year Old</h3>
                    <span class="medal gold">Gold</span>
                    <span class="producer">William Grant</span>
                </div>
                <div class="result-item">
                    <h3 class="product-name">Macallan 12 Sherry Oak</h3>
                    <span class="medal silver">Silver</span>
                    <span class="producer">The Macallan</span>
                </div>
            </div>
        </body>
        </html>
        """

        # Run discovery
        import asyncio

        orchestrator = CompetitionOrchestrator()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                orchestrator.run_competition_discovery(
                    competition_url="https://test-competition.com/results/2024",
                    crawl_job=job,
                    html_content=html_content,
                    competition_key="iwsc",
                    year=2024,
                )
            )
        finally:
            loop.close()

        # Verify results
        assert result.success is True
        assert result.awards_found >= 2
        assert result.skeletons_created >= 2

        # Verify skeleton products were created
        skeletons = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            discovery_source=DiscoverySource.COMPETITION,
        )
        assert skeletons.count() >= 2

        # Verify awards data is stored as ProductAward records (Phase 4)
        glenfiddich = skeletons.filter(
            name__icontains="Glenfiddich"
        ).first()

        if glenfiddich:
            awards = ProductAward.objects.filter(product=glenfiddich)
            assert awards.count() > 0
            award = awards.first()
            assert award.competition == "IWSC"
            assert award.year == 2024


class TestSkeletonDeduplication:
    """Tests for skeleton product deduplication."""

    @pytest.mark.django_db
    def test_skeleton_deduplication_by_fingerprint(self):
        """Duplicate skeleton products are detected and updated instead of created."""
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.models import DiscoveredProduct, DiscoveredProductStatus, ProductAward

        manager = SkeletonProductManager()

        # Create first skeleton
        award_data_1 = {
            "product_name": "Glenfiddich 18 Year Old",
            "producer": "Glenfiddich",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        }
        product1 = manager.create_skeleton_product(award_data_1)
        original_id = product1.id

        # Try to create duplicate with different award
        award_data_2 = {
            "product_name": "Glenfiddich 18 Year Old",
            "producer": "Glenfiddich",
            "competition": "SFWSC",
            "year": 2024,
            "medal": "Double Gold",
        }
        product2 = manager.create_skeleton_product(award_data_2)

        # Should return the same product with additional award
        assert product2.id == original_id

        # Verify awards stored as ProductAward records (Phase 4)
        awards = ProductAward.objects.filter(product=product2)
        assert awards.count() == 2

        # Verify only one skeleton exists
        skeletons = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            name__icontains="Glenfiddich 18",
        )
        assert skeletons.count() == 1

    @pytest.mark.django_db
    def test_skeleton_batch_creation(self):
        """Batch skeleton creation handles duplicates correctly."""
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.models import DiscoveredProduct, ProductAward

        manager = SkeletonProductManager()

        # Create batch with some duplicates
        award_data_list = [
            {
                "product_name": "Ardbeg Uigeadail",
                "producer": "Ardbeg",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Gold",
            },
            {
                "product_name": "Ardbeg Uigeadail",
                "producer": "Ardbeg",
                "competition": "WWA",
                "year": 2024,
                "medal": "gold",  # Lower case gold should normalize
            },
            {
                "product_name": "Lagavulin 16",
                "producer": "Lagavulin",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Gold",
            },
        ]

        products = manager.create_skeleton_products_batch(award_data_list)

        # Should return 3 products but only 2 unique skeletons
        assert len(products) == 3

        # Verify Ardbeg has 2 awards using ProductAward (Phase 4)
        ardbeg = DiscoveredProduct.objects.filter(
            name__icontains="Ardbeg Uigeadail"
        ).first()
        assert ardbeg is not None

        awards = ProductAward.objects.filter(product=ardbeg)
        assert awards.count() == 2


class TestEnrichmentSearchTriggering:
    """Tests for enrichment search triggering."""

    @pytest.mark.asyncio
    async def test_enrichment_triggers_triple_search(self):
        """Enrichment search triggers 3 SerpAPI searches per skeleton."""
        from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher

        searcher = EnrichmentSearcher(api_key="test_key")

        with patch.object(
            searcher.serpapi_client, "search", new_callable=AsyncMock
        ) as mock_search:
            # Return mock results
            mock_result = MagicMock()
            mock_result.url = "https://example.com/product"
            mock_result.domain = "example.com"
            mock_result.title = "Product Page"
            mock_result.snippet = "Description"
            mock_search.return_value = [mock_result]

            # Run enrichment search
            results = await searcher.search_for_enrichment("Glenfiddich 18")

            # Verify 3 searches were made
            assert mock_search.call_count == 3

            # Verify search types
            calls = mock_search.call_args_list
            queries = [
                call.args[0] if call.args else call.kwargs.get("query", "")
                for call in calls
            ]

            assert any("price" in q.lower() or "buy" in q.lower() for q in queries)
            assert any("review" in q.lower() for q in queries)
            assert any("official" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_enrichment_excludes_unwanted_domains(self):
        """Enrichment results exclude social media and aggregator domains."""
        from crawler.discovery.competitions.enrichment_searcher import EnrichmentSearcher

        searcher = EnrichmentSearcher(api_key="test_key")

        with patch.object(
            searcher.serpapi_client, "search", new_callable=AsyncMock
        ) as mock_search:
            # Return mix of good and excluded domains
            mock_results = []
            for domain in [
                "masterofmalt.com",
                "facebook.com",
                "twitter.com",
                "whiskyexchange.com",
            ]:
                mock_result = MagicMock()
                mock_result.url = f"https://{domain}/product"
                mock_result.domain = domain
                mock_result.title = "Product"
                mock_result.snippet = "Desc"
                mock_results.append(mock_result)

            mock_search.return_value = mock_results

            results = await searcher.search_for_enrichment("Test Product")

            # Verify excluded domains are filtered out
            result_domains = [r["domain"] for r in results]
            assert "facebook.com" not in result_domains
            assert "twitter.com" not in result_domains


class TestURLQueuingFromEnrichment:
    """Tests for URL queuing from enrichment results."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_enrichment_urls_queued_with_high_priority(self):
        """URLs from enrichment are queued with priority 10."""
        from crawler.services.competition_orchestrator import CompetitionOrchestrator
        from crawler.discovery.competitions.enrichment_searcher import ENRICHMENT_PRIORITY

        orchestrator = CompetitionOrchestrator()

        # Mock the URL frontier
        with patch.object(orchestrator, "url_frontier") as mock_frontier:
            mock_frontier.add_url.return_value = True

            enrichment_results = [
                {
                    "url": "https://example.com/buy",
                    "domain": "example.com",
                    "search_type": "price",
                    "product_name": "Test Product",
                    "priority": ENRICHMENT_PRIORITY,
                },
                {
                    "url": "https://review.com/test",
                    "domain": "review.com",
                    "search_type": "review",
                    "product_name": "Test Product",
                    "priority": ENRICHMENT_PRIORITY,
                },
            ]

            queued = await orchestrator.queue_enrichment_urls(enrichment_results)

            assert queued == 2
            assert mock_frontier.add_url.call_count == 2

            # Verify priority is 10
            for call in mock_frontier.add_url.call_args_list:
                assert call.kwargs.get("priority") == ENRICHMENT_PRIORITY


class TestCompetitionOrchestrator:
    """Tests for the CompetitionOrchestrator service."""

    @pytest.mark.django_db
    def test_get_competition_sources(self):
        """Orchestrator returns active competition sources."""
        from crawler.services.competition_orchestrator import CompetitionOrchestrator
        from crawler.models import CrawlerSource, SourceCategory

        # Create test sources
        CrawlerSource.objects.create(
            name="Active Competition",
            slug="active-comp",
            base_url="https://active.com",
            category=SourceCategory.COMPETITION,
            is_active=True,
        )
        CrawlerSource.objects.create(
            name="Inactive Competition",
            slug="inactive-comp",
            base_url="https://inactive.com",
            category=SourceCategory.COMPETITION,
            is_active=False,
        )
        CrawlerSource.objects.create(
            name="Regular Source",
            slug="regular",
            base_url="https://regular.com",
            category=SourceCategory.RETAILER,
            is_active=True,
        )

        orchestrator = CompetitionOrchestrator()
        sources = orchestrator.get_competition_sources()

        # Should only return active competition sources
        assert len(sources) == 1
        assert sources[0].slug == "active-comp"

    @pytest.mark.django_db
    def test_get_skeleton_statistics(self):
        """Orchestrator provides accurate skeleton statistics."""
        from crawler.services.competition_orchestrator import CompetitionOrchestrator
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager

        manager = SkeletonProductManager()

        # Create some skeletons
        for i in range(3):
            manager.create_skeleton_product({
                "product_name": f"Test Product {i}",
                "producer": "Test Producer",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Gold",
            })

        orchestrator = CompetitionOrchestrator()
        stats = orchestrator.get_skeleton_statistics()

        assert stats["total_skeletons"] == 3
        assert stats["awaiting_enrichment"] == 3
        assert stats["enriched"] == 0


class TestCompetitionSources:
    """Tests for competition source management."""

    @pytest.mark.django_db
    def test_ensure_competition_sources_exist(self):
        """Competition sources are created if they don't exist."""
        from crawler.services.competition_orchestrator import (
            ensure_competition_sources_exist,
            COMPETITION_SOURCES,
        )
        from crawler.models import CrawlerSource, SourceCategory

        # Run setup
        created = ensure_competition_sources_exist()

        assert created == len(COMPETITION_SOURCES)

        # Verify sources exist
        for source_data in COMPETITION_SOURCES:
            source = CrawlerSource.objects.get(slug=source_data["slug"])
            assert source.category == SourceCategory.COMPETITION
            assert source.is_active is True

        # Run again - should not create duplicates
        created_again = ensure_competition_sources_exist()
        assert created_again == 0


class TestFuzzyMatchingIntegration:
    """Tests for fuzzy matching integration with pipeline."""

    @pytest.mark.django_db
    def test_skeleton_enrichment_via_fuzzy_match(self):
        """Skeleton products are enriched when matching crawled data is found."""
        from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
        from crawler.discovery.competitions.fuzzy_matcher import SkeletonMatcher
        from crawler.models import DiscoveredProductStatus

        manager = SkeletonProductManager()
        matcher = SkeletonMatcher(threshold=85)

        # Create skeleton
        skeleton = manager.create_skeleton_product({
            "product_name": "Glenfiddich 18 Year Old",
            "producer": "Glenfiddich",
            "competition": "IWSC",
            "year": 2024,
            "medal": "Gold",
        })

        assert skeleton.status == DiscoveredProductStatus.SKELETON

        # Simulate crawled data
        crawled_name = "Glenfiddich 18 Year Old Single Malt Scotch Whisky"
        enriched_data = {
            "name": crawled_name,
            "brand": "Glenfiddich",
            "price": "89.99",
            "volume_ml": 750,
            "abv": 40.0,
            "description": "A rich and fruity single malt whisky.",
        }

        # Match and enrich
        success = matcher.match_and_enrich(
            skeleton=skeleton,
            crawled_name=crawled_name,
            enriched_data=enriched_data,
            source_url="https://example.com/product",
        )

        assert success is True

        # Verify enrichment
        skeleton.refresh_from_db()
        # After enrichment, status transitions based on completeness (not hardcoded PENDING)
        assert skeleton.status in (
            DiscoveredProductStatus.PARTIAL,
            DiscoveredProductStatus.INCOMPLETE,
            DiscoveredProductStatus.PENDING,  # Legacy compatibility
        )
        assert skeleton.source_url == "https://example.com/product"
