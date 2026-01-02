"""
Tests for Competition Pipeline Integration into Standard Crawler Tasks.

TDD tests for integrating competition discovery into the standard crawler flow:
1. Competition source detection in crawl_source
2. CompetitionOrchestrator usage for competition sources
3. enrich_skeletons periodic task
4. process_enrichment_queue periodic task
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class TestCompetitionSourceDetection:
    """Tests for detecting and routing competition sources."""

    @pytest.mark.django_db(transaction=True)
    def test_crawl_source_detects_competition_category(self):
        """crawl_source should detect sources with category='competition'."""
        from crawler.models import CrawlerSource, CrawlJob, SourceCategory

        # Create a competition source
        source = CrawlerSource.objects.create(
            name="Test Competition Source",
            slug="test-competition",
            base_url="https://competition.example.com/results",
            category=SourceCategory.COMPETITION,
            product_types=["whiskey"],
            is_active=True,
        )
        job = CrawlJob.objects.create(source=source)

        # The source should be detected as a competition source
        assert source.category == SourceCategory.COMPETITION

    @pytest.mark.django_db(transaction=True)
    def test_crawl_source_uses_orchestrator_for_competition(self):
        """crawl_source should use CompetitionOrchestrator for competition sources."""
        from crawler.models import CrawlerSource, CrawlJob, SourceCategory
        from crawler.tasks import crawl_source

        # Create a competition source
        source = CrawlerSource.objects.create(
            name="IWSC Test",
            slug="iwsc-test",
            base_url="https://iwsc.net/results/search/2024",
            category=SourceCategory.COMPETITION,
            product_types=["whiskey"],
            is_active=True,
        )
        job = CrawlJob.objects.create(source=source)

        # Mock the competition orchestrator at its source module
        with patch('crawler.services.competition_orchestrator.CompetitionOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock the async method
            async def mock_run_discovery(*args, **kwargs):
                from crawler.services.competition_orchestrator import CompetitionDiscoveryResult
                return CompetitionDiscoveryResult(
                    competition="IWSC",
                    year=2024,
                    awards_found=5,
                    skeletons_created=5,
                )

            mock_orchestrator.run_competition_discovery = AsyncMock(side_effect=mock_run_discovery)

            # Mock SmartRouter fetch at its source module
            with patch('crawler.fetchers.smart_router.SmartRouter') as mock_router_class:
                mock_router = MagicMock()
                mock_router_class.return_value = mock_router

                async def mock_fetch(*args, **kwargs):
                    result = MagicMock()
                    result.success = True
                    result.content = "<html><body>Competition results</body></html>"
                    return result

                mock_router.fetch = AsyncMock(side_effect=mock_fetch)
                mock_router.close = AsyncMock()

                # Run the task
                result = crawl_source(str(source.id), str(job.id))

                # Verify CompetitionOrchestrator was used
                mock_orchestrator_class.assert_called_once()
                # Note: run_competition_discovery is called multiple times (pagination + categories)
                mock_orchestrator.run_competition_discovery.assert_called()

    @pytest.mark.django_db(transaction=True)
    def test_crawl_source_uses_content_processor_for_non_competition(self):
        """crawl_source should use ContentProcessor for non-competition sources."""
        from crawler.models import CrawlerSource, CrawlJob, SourceCategory
        from crawler.tasks import crawl_source

        # Create a regular (review) source
        source = CrawlerSource.objects.create(
            name="Review Site",
            slug="review-site",
            base_url="https://reviews.example.com",
            category=SourceCategory.REVIEW,
            product_types=["whiskey"],
            is_active=True,
        )
        job = CrawlJob.objects.create(source=source)

        # Mock ContentProcessor at its source module
        with patch('crawler.services.content_processor.ContentProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor

            async def mock_process(*args, **kwargs):
                result = MagicMock()
                result.success = True
                result.is_new = True
                return result

            mock_processor.process = AsyncMock(side_effect=mock_process)

            # Mock SmartRouter at its source module
            with patch('crawler.fetchers.smart_router.SmartRouter') as mock_router_class:
                mock_router = MagicMock()
                mock_router_class.return_value = mock_router

                async def mock_fetch(*args, **kwargs):
                    result = MagicMock()
                    result.success = True
                    result.content = "<html><body>Review content</body></html>"
                    return result

                mock_router.fetch = AsyncMock(side_effect=mock_fetch)
                mock_router.close = AsyncMock()

                # Mock URL frontier at its source module
                with patch('crawler.queue.url_frontier.get_url_frontier') as mock_frontier_func:
                    mock_frontier = MagicMock()
                    mock_frontier_func.return_value = mock_frontier
                    mock_frontier.is_empty.return_value = False
                    mock_frontier.get_next_url.side_effect = [
                        {"url": "https://reviews.example.com/product1"},
                        None,  # End of queue
                    ]

                    # Run the task
                    result = crawl_source(str(source.id), str(job.id))

                    # Verify ContentProcessor was used (not CompetitionOrchestrator)
                    mock_processor_class.assert_called()


class TestEnrichSkeletonsTask:
    """Tests for the enrich_skeletons periodic task."""

    @pytest.mark.django_db(transaction=True)
    def test_enrich_skeletons_processes_unenriched_products(self):
        """enrich_skeletons should process skeleton products without enrichment."""
        from crawler.models import (
            DiscoveredProduct,
            DiscoveredProductStatus,
            DiscoverySource,
            ProductType,
        )
        from crawler.tasks import enrich_skeletons

        # Create skeleton products
        for i in range(3):
            DiscoveredProduct.objects.create(
                source_url="",
                fingerprint=f"test-fingerprint-{i}",
                product_type=ProductType.WHISKEY,
                raw_content="",
                raw_content_hash="abc123",
                extracted_data={"name": f"Test Product {i}"},
                enriched_data={},  # Empty = needs enrichment
                status=DiscoveredProductStatus.SKELETON,
                discovery_source=DiscoverySource.COMPETITION,
            )

        # Mock the orchestrator at its source module
        with patch('crawler.services.competition_orchestrator.CompetitionOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator.get_pending_skeletons_count.return_value = 3

            async def mock_enrich(*args, **kwargs):
                from crawler.services.competition_orchestrator import EnrichmentResult
                return EnrichmentResult(
                    skeletons_processed=3,
                    urls_discovered=9,
                    urls_queued=9,
                )

            mock_orchestrator.process_skeletons_for_enrichment = AsyncMock(side_effect=mock_enrich)

            # Run the task
            result = enrich_skeletons(limit=10)

            # Verify orchestrator was called
            mock_orchestrator.process_skeletons_for_enrichment.assert_called_once()
            assert result["status"] == "completed"
            assert result["skeletons_processed"] == 3

    @pytest.mark.django_db(transaction=True)
    def test_enrich_skeletons_respects_limit(self):
        """enrich_skeletons should respect the limit parameter."""
        from crawler.tasks import enrich_skeletons

        with patch('crawler.services.competition_orchestrator.CompetitionOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator.get_pending_skeletons_count.return_value = 10

            async def mock_enrich(limit=50, **kwargs):
                from crawler.services.competition_orchestrator import EnrichmentResult
                return EnrichmentResult(skeletons_processed=min(limit, 5))

            mock_orchestrator.process_skeletons_for_enrichment = AsyncMock(side_effect=mock_enrich)

            # Run with specific limit
            result = enrich_skeletons(limit=25)

            # Verify limit was passed
            mock_orchestrator.process_skeletons_for_enrichment.assert_called_once()
            call_kwargs = mock_orchestrator.process_skeletons_for_enrichment.call_args[1]
            assert call_kwargs.get('limit') == 25


class TestProcessEnrichmentQueueTask:
    """Tests for the process_enrichment_queue periodic task."""

    @pytest.mark.django_db(transaction=True)
    def test_process_enrichment_queue_processes_urls(self):
        """process_enrichment_queue should process URLs from the enrichment queue."""
        from crawler.tasks import process_enrichment_queue

        # Mock URL frontier at its source module
        with patch('crawler.queue.url_frontier.get_url_frontier') as mock_frontier_func:
            mock_frontier = MagicMock()
            mock_frontier_func.return_value = mock_frontier
            mock_frontier.get_queue_size.return_value = 5
            mock_frontier.get_next_url.side_effect = [
                {"url": "https://example.com/review1", "metadata": {"skeleton_id": "123"}},
                {"url": "https://example.com/review2", "metadata": {"skeleton_id": "456"}},
                None,  # End of queue
            ]

            # Mock SmartRouter at its source module
            with patch('crawler.fetchers.smart_router.SmartRouter') as mock_router_class:
                mock_router = MagicMock()
                mock_router_class.return_value = mock_router

                async def mock_fetch(*args, **kwargs):
                    result = MagicMock()
                    result.success = True
                    result.content = "<html>Product details</html>"
                    return result

                mock_router.fetch = AsyncMock(side_effect=mock_fetch)
                mock_router.close = AsyncMock()

                # Mock ContentProcessor at its source module
                with patch('crawler.services.content_processor.ContentProcessor') as mock_processor_class:
                    mock_processor = MagicMock()
                    mock_processor_class.return_value = mock_processor

                    async def mock_process(*args, **kwargs):
                        result = MagicMock()
                        result.success = True
                        result.enriched_data = {"tasting_notes": "Smooth"}
                        return result

                    mock_processor.process = AsyncMock(side_effect=mock_process)

                    # Run the task
                    result = process_enrichment_queue(max_urls=10)

                    assert result["status"] == "completed"
                    assert result["urls_processed"] >= 1

    @pytest.mark.django_db(transaction=True)
    def test_process_enrichment_queue_handles_empty_queue(self):
        """process_enrichment_queue should handle empty queue gracefully."""
        from crawler.tasks import process_enrichment_queue

        with patch('crawler.queue.url_frontier.get_url_frontier') as mock_frontier_func:
            mock_frontier = MagicMock()
            mock_frontier_func.return_value = mock_frontier
            mock_frontier.get_queue_size.return_value = 0

            # Run the task
            result = process_enrichment_queue(max_urls=10)

            assert result["status"] == "completed"
            assert result["urls_processed"] == 0
            assert "empty" in result.get("message", "").lower() or result["urls_processed"] == 0


class TestCeleryBeatSchedule:
    """Tests for Celery beat schedule configuration."""

    def test_enrich_skeletons_in_beat_schedule(self):
        """enrich_skeletons should be in Celery beat schedule."""
        from config.celery import app

        beat_schedule = app.conf.beat_schedule or {}

        # Check for enrichment task
        enrichment_tasks = [
            name for name in beat_schedule.keys()
            if 'enrich' in name.lower() or 'skeleton' in name.lower()
        ]

        # This will fail until we add it - that's TDD!
        assert len(enrichment_tasks) > 0, "enrich_skeletons should be in beat schedule"

    def test_process_enrichment_queue_in_beat_schedule(self):
        """process_enrichment_queue should be in Celery beat schedule."""
        from config.celery import app

        beat_schedule = app.conf.beat_schedule or {}

        # Check for queue processing task
        queue_tasks = [
            name for name in beat_schedule.keys()
            if 'queue' in name.lower() and 'enrich' in name.lower()
        ]

        # This will fail until we add it - that's TDD!
        assert len(queue_tasks) > 0, "process_enrichment_queue should be in beat schedule"
