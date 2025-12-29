"""
Tests for Celery Tasks.

Phase 3: Generic Search Discovery - TDD Tests for tasks.py
"""

import pytest
from unittest.mock import patch, MagicMock


class TestRunGenericDiscovery:
    """Tests for run_generic_discovery task."""

    def test_returns_dict_result(self):
        """Should return dictionary result."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter") as MockRL, \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            # Configure mocks
            MockSS.return_value.get_next_queries.return_value = []
            MockSS.return_value.can_execute_search.return_value = True
            MockRL.return_value.can_make_request.return_value = True

            result = run_generic_discovery("whiskey")

            assert isinstance(result, dict)
            assert "status" in result
            assert "product_type" in result

    def test_returns_no_queries_status(self):
        """Should return no_queries status when no queries available."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter"), \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor"), \
             patch("crawler.discovery.serpapi.client.SerpAPIClient"):

            MockSS.return_value.get_next_queries.return_value = []

            result = run_generic_discovery("whiskey")

            assert result["status"] == "no_queries"

    def test_executes_searches_when_queries_available(self):
        """Should execute searches when queries are available."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter") as MockRL, \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            # Setup mocks
            MockSS.return_value.get_next_queries.return_value = ["test query"]
            MockSS.return_value.can_execute_search.return_value = True
            MockClient.return_value.google_search.return_value = {"organic_results": []}
            MockTE.return_value.extract_targets.return_value = []
            MockTE.return_value.deduplicate_across_searches.return_value = []

            result = run_generic_discovery("whiskey")

            # Should call google_search
            MockClient.return_value.google_search.assert_called()
            assert result["status"] == "completed"

    def test_respects_quota_limit(self):
        """Should stop when quota is exhausted."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter") as MockRL, \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            # Setup: have queries but can't execute
            MockSS.return_value.get_next_queries.return_value = ["query1", "query2"]
            MockSS.return_value.can_execute_search.return_value = False  # Quota exhausted
            MockTE.return_value.deduplicate_across_searches.return_value = []

            result = run_generic_discovery("whiskey")

            # Should not call google_search because quota exhausted
            MockClient.return_value.google_search.assert_not_called()

    def test_records_request_after_search(self):
        """Should record request to rate limiter after search."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter") as MockRL, \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            MockSS.return_value.get_next_queries.return_value = ["test query"]
            MockSS.return_value.can_execute_search.return_value = True
            MockClient.return_value.google_search.return_value = {"organic_results": []}
            MockTE.return_value.extract_targets.return_value = []
            MockTE.return_value.deduplicate_across_searches.return_value = []

            run_generic_discovery("whiskey")

            # Should record the request
            MockRL.return_value.record_request.assert_called()

    def test_marks_query_executed(self):
        """Should mark query as executed after search."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter"), \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            MockSS.return_value.get_next_queries.return_value = ["test query"]
            MockSS.return_value.can_execute_search.return_value = True
            MockClient.return_value.google_search.return_value = {"organic_results": []}
            MockTE.return_value.extract_targets.return_value = []
            MockTE.return_value.deduplicate_across_searches.return_value = []

            run_generic_discovery("whiskey")

            # Should mark query as executed
            MockSS.return_value.mark_executed.assert_called_with("test query")

    def test_handles_search_errors(self):
        """Should handle search errors gracefully."""
        from crawler.discovery.search.tasks import run_generic_discovery

        with patch("crawler.discovery.serpapi.rate_limiter.RateLimiter"), \
             patch("crawler.discovery.search.scheduler.SearchScheduler") as MockSS, \
             patch("crawler.discovery.search.config.SearchConfig"), \
             patch("crawler.discovery.search.target_extractor.TargetURLExtractor") as MockTE, \
             patch("crawler.discovery.serpapi.client.SerpAPIClient") as MockClient, \
             patch("crawler.discovery.search.tasks.queue_target_for_scraping"):

            MockSS.return_value.get_next_queries.return_value = ["query1", "query2"]
            MockSS.return_value.can_execute_search.return_value = True
            MockClient.return_value.google_search.side_effect = Exception("API Error")
            MockTE.return_value.deduplicate_across_searches.return_value = []

            # Should not raise
            result = run_generic_discovery("whiskey")

            assert result["status"] == "completed"


class TestQueueTargetForScraping:
    """Tests for queue_target_for_scraping task."""

    def test_creates_crawled_url_entry(self, db):
        """Should create CrawledURL entry for new target."""
        from crawler.discovery.search.tasks import queue_target_for_scraping
        from crawler.models import CrawledURL

        target = {
            "url": "https://example.com/test-page-unique-12345",
            "title": "Test Page",
            "source": "example.com",
        }

        with patch.object(CrawledURL, "compute_url_hash", return_value="test-hash-unique"):
            # Clear any existing
            CrawledURL.objects.filter(url_hash="test-hash-unique").delete()

            queue_target_for_scraping(target)

            # Should create entry
            assert CrawledURL.objects.filter(url_hash="test-hash-unique").exists()

    def test_skips_existing_url(self, db):
        """Should skip URL that was already crawled."""
        from crawler.discovery.search.tasks import queue_target_for_scraping
        from crawler.models import CrawledURL

        # Create existing entry
        existing_hash = "existing-hash-12345"
        CrawledURL.objects.filter(url_hash=existing_hash).delete()
        CrawledURL.objects.create(
            url="https://example.com/existing",
            url_hash=existing_hash,
            is_product_page=False,
        )

        target = {
            "url": "https://example.com/existing",
            "title": "Existing Page",
        }

        with patch.object(CrawledURL, "compute_url_hash", return_value=existing_hash):
            queue_target_for_scraping(target)

            # Should not create duplicate
            count = CrawledURL.objects.filter(url_hash=existing_hash).count()
            assert count == 1

    def test_handles_empty_url(self):
        """Should handle empty URL gracefully."""
        from crawler.discovery.search.tasks import queue_target_for_scraping

        target = {"url": "", "title": "No URL"}

        # Should not raise
        queue_target_for_scraping(target)

    def test_handles_missing_url(self):
        """Should handle missing URL key."""
        from crawler.discovery.search.tasks import queue_target_for_scraping

        target = {"title": "Missing URL"}

        # Should not raise
        queue_target_for_scraping(target)


class TestRunAllGenericDiscovery:
    """Tests for run_all_generic_discovery task."""

    def test_runs_for_all_product_types(self):
        """Should run discovery for all product types."""
        from crawler.discovery.search.tasks import run_all_generic_discovery

        with patch("crawler.discovery.search.tasks.run_generic_discovery") as mock_run:
            mock_run.return_value = {"status": "completed"}

            result = run_all_generic_discovery()

            # Should call for whiskey and port_wine
            assert mock_run.call_count == 2
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert "whiskey" in calls
            assert "port_wine" in calls

    def test_returns_results_dict(self):
        """Should return results dictionary."""
        from crawler.discovery.search.tasks import run_all_generic_discovery

        with patch("crawler.discovery.search.tasks.run_generic_discovery") as mock_run:
            mock_run.return_value = {"status": "completed"}

            result = run_all_generic_discovery()

            assert isinstance(result, dict)
            assert "whiskey" in result
            assert "port_wine" in result
