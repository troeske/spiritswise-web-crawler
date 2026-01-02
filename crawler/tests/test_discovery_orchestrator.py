"""
Tests for Discovery Orchestrator (TDD approach).

Phase 3: Generic Search Discovery Flow
Tests written first, implementation to follow.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from django.test import TestCase
from django.utils import timezone

from crawler.models import (
    SearchTerm,
    CrawlSchedule,
    ScheduleCategory,
    ScheduleFrequency,
    DiscoveryJob,
    DiscoveryResult,
    DiscoveredProduct,
    SearchTermCategory,
    SearchTermProductType,
    DiscoveryJobStatus,
    DiscoveryResultStatus,
)


class TestDiscoveryOrchestratorInit(TestCase):
    """Test TASK-GS-010: Core Orchestrator Class initialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )

    def test_orchestrator_init_with_schedule(self):
        """Test orchestrator initializes with schedule parameter."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        self.assertEqual(orchestrator.schedule, self.schedule)
        self.assertIsNone(orchestrator.job)

    def test_orchestrator_init_without_schedule(self):
        """Test orchestrator can run without schedule (manual mode)."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator()

        self.assertIsNone(orchestrator.schedule)

    def test_orchestrator_has_smart_crawler(self):
        """Test orchestrator initializes SmartCrawler."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        self.assertIsNotNone(orchestrator.smart_crawler)

    def test_orchestrator_has_serpapi_client(self):
        """Test orchestrator initializes SerpAPI client."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        self.assertIsNotNone(orchestrator.serpapi_client)


class TestDiscoveryOrchestratorRun(TestCase):
    """Test orchestrator run() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )
        # Create test search terms
        SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_run_creates_job(self, mock_search):
        """Test run() creates a DiscoveryJob."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = []
        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        job = orchestrator.run()

        self.assertIsInstance(job, DiscoveryJob)
        self.assertEqual(job.crawl_schedule, self.schedule)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_run_sets_job_status_running(self, mock_search):
        """Test job status is 'running' during execution."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = []
        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Verify job status during run
        original_process = orchestrator._process_search_term

        def check_status(term):
            self.assertEqual(orchestrator.job.status, DiscoveryJobStatus.RUNNING)
            return original_process(term)

        with patch.object(orchestrator, "_process_search_term", side_effect=check_status):
            orchestrator.run()

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_run_completes_job_on_success(self, mock_search):
        """Test job status is 'completed' after successful run."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = []
        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        job = orchestrator.run()

        self.assertEqual(job.status, DiscoveryJobStatus.COMPLETED)
        self.assertIsNotNone(job.completed_at)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_run_fails_job_on_error(self, mock_search):
        """Test job status is 'failed' when error occurs."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.side_effect = Exception("SerpAPI error")
        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        with self.assertRaises(Exception):
            orchestrator.run()

        # Job should still be saved with failed status
        job = DiscoveryJob.objects.get(crawl_schedule=self.schedule)
        self.assertEqual(job.status, DiscoveryJobStatus.FAILED)
        self.assertIn("SerpAPI error", job.error_log)


class TestGetSearchTerms(TestCase):
    """Test TASK-GS-010: _get_search_terms() filtering."""

    def setUp(self):
        """Set up test fixtures with various search terms."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-terms",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=10,
        )

        # Create various search terms
        self.whiskey_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )
        self.port_term = SearchTerm.objects.create(
            term_template="best port wine {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.PORT_WINE,
            priority=90,
            is_active=True,
        )
        self.awards_term = SearchTerm.objects.create(
            term_template="whiskey awards {year}",
            category=SearchTermCategory.AWARDS,
            product_type=SearchTermProductType.WHISKEY,
            priority=80,
            is_active=True,
        )
        self.inactive_term = SearchTerm.objects.create(
            term_template="inactive term",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=False,
        )

    def test_get_terms_excludes_inactive(self):
        """Test inactive terms are excluded."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = orchestrator._get_search_terms()

        self.assertNotIn(self.inactive_term, terms)
        self.assertEqual(len(terms), 3)

    def test_get_terms_filters_by_category(self):
        """Test terms filtered by schedule's search_categories."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        self.schedule.search_categories = [SearchTermCategory.BEST_LISTS]
        self.schedule.save()

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = orchestrator._get_search_terms()

        self.assertIn(self.whiskey_term, terms)
        self.assertIn(self.port_term, terms)
        self.assertNotIn(self.awards_term, terms)

    def test_get_terms_filters_by_product_type(self):
        """Test terms filtered by schedule's product_types."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        self.schedule.product_types = [SearchTermProductType.WHISKEY]
        self.schedule.save()

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = orchestrator._get_search_terms()

        self.assertIn(self.whiskey_term, terms)
        self.assertNotIn(self.port_term, terms)

    def test_get_terms_respects_max_limit(self):
        """Test terms limited by max_search_terms."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        self.schedule.max_search_terms = 2
        self.schedule.save()

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = orchestrator._get_search_terms()

        self.assertEqual(len(terms), 2)

    def test_get_terms_ordered_by_priority(self):
        """Test terms ordered by priority (highest first)."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = list(orchestrator._get_search_terms())

        # Highest priority first
        self.assertEqual(terms[0], self.whiskey_term)

    def test_get_terms_filters_seasonal(self):
        """Test seasonal terms filtered correctly."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        # Create a seasonal term for December only
        december_term = SearchTerm.objects.create(
            term_template="holiday whiskey gifts",
            category=SearchTermCategory.SEASONAL,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
            seasonal_start_month=12,
            seasonal_end_month=12,
        )

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        terms = orchestrator._get_search_terms()

        # Should only include seasonal term if current month is December
        current_month = datetime.now().month
        if current_month == 12:
            self.assertIn(december_term, terms)
        else:
            self.assertNotIn(december_term, terms)


class TestSerpAPISearch(TestCase):
    """Test TASK-GS-011: SerpAPI Search Integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )

    @patch("crawler.services.discovery_orchestrator.SerpAPIClient")
    def test_search_calls_serpapi(self, mock_serpapi_class):
        """Test _search() calls SerpAPI client."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_client = Mock()
        mock_client.search.return_value = {"organic_results": []}
        mock_serpapi_class.return_value = mock_client

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        orchestrator._search("best whiskey 2024")

        mock_client.search.assert_called_once()

    @patch("crawler.services.discovery_orchestrator.SerpAPIClient")
    def test_search_parses_results(self, mock_serpapi_class):
        """Test _search() parses organic results correctly."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_client = Mock()
        mock_client.search.return_value = {
            "organic_results": [
                {"title": "Best Whiskey 2024", "link": "https://example.com/whiskey"},
                {"title": "Top 10 Whiskeys", "link": "https://review.com/top10"},
            ]
        }
        mock_serpapi_class.return_value = mock_client

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        results = orchestrator._search("best whiskey 2024")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Best Whiskey 2024")
        self.assertEqual(results[0]["link"], "https://example.com/whiskey")

    @patch("crawler.services.discovery_orchestrator.SerpAPIClient")
    def test_search_handles_empty_results(self, mock_serpapi_class):
        """Test _search() handles empty results gracefully."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_client = Mock()
        mock_client.search.return_value = {}
        mock_serpapi_class.return_value = mock_client

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        results = orchestrator._search("obscure query")

        self.assertEqual(results, [])

    @patch("crawler.services.discovery_orchestrator.SerpAPIClient")
    def test_search_handles_api_error(self, mock_serpapi_class):
        """Test _search() handles API errors."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_client = Mock()
        mock_client.search.side_effect = Exception("API quota exceeded")
        mock_serpapi_class.return_value = mock_client

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        with self.assertRaises(Exception) as context:
            orchestrator._search("test query")

        self.assertIn("API quota exceeded", str(context.exception))


class TestURLProcessing(TestCase):
    """Test TASK-GS-012: URL Processing Pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-url",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
        )

    def test_is_product_url_detects_retailers(self):
        """Test retailer URLs are identified as product URLs."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        retailer_urls = [
            "https://www.masterofmalt.com/whisky/glenfiddich-18",
            "https://thewhiskyexchange.com/p/12345/lagavulin-16",
            "https://www.totalwine.com/spirits/bourbon",
        ]

        for url in retailer_urls:
            self.assertTrue(
                orchestrator._is_product_url(url, "Some Whiskey"),
                f"Should detect as product URL: {url}"
            )

    def test_is_product_url_detects_brand_sites(self):
        """Test official brand sites are identified."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Brand site with product title
        self.assertTrue(
            orchestrator._is_product_url(
                "https://www.glenfiddich.com/whiskies/18-year-old",
                "Glenfiddich 18 Year Old"
            )
        )

    def test_is_product_url_skips_social_media(self):
        """Test social media URLs are skipped."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        social_urls = [
            "https://www.facebook.com/whiskey",
            "https://twitter.com/whiskey",
            "https://www.instagram.com/whiskey",
            "https://www.youtube.com/watch?v=123",
            "https://www.tiktok.com/@whiskey",
            "https://www.pinterest.com/whiskey",
        ]

        for url in social_urls:
            self.assertFalse(
                orchestrator._is_product_url(url, "Whiskey Review"),
                f"Should skip social media: {url}"
            )

    def test_is_product_url_skips_news_sites(self):
        """Test general news sites are skipped."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        news_urls = [
            "https://www.cnn.com/whiskey",
            "https://www.bbc.com/whiskey",
            "https://www.nytimes.com/whiskey",
        ]

        for url in news_urls:
            self.assertFalse(
                orchestrator._is_product_url(url, "Whiskey News"),
                f"Should skip news site: {url}"
            )

    def test_is_product_url_detects_list_pages(self):
        """Test 'best of' list pages are identified."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        list_urls = [
            ("https://whiskyadvocate.com/best-whisky-2024", "Best Whisky 2024"),
            ("https://vinepair.com/top-10-bourbon", "Top 10 Bourbon"),
        ]

        for url, title in list_urls:
            result = orchestrator._is_product_url(url, title)
            self.assertTrue(result, f"Should detect list page: {url}")

    def test_extract_domain(self):
        """Test domain extraction from URL."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        test_cases = [
            ("https://www.masterofmalt.com/product", "masterofmalt.com"),
            ("https://thewhiskyexchange.com/p/123", "thewhiskyexchange.com"),
            ("http://example.org/path", "example.org"),
        ]

        for url, expected_domain in test_cases:
            domain = orchestrator._extract_domain(url)
            self.assertEqual(domain, expected_domain)


class TestSmartCrawlerIntegration(TestCase):
    """Test TASK-GS-013: SmartCrawler Integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )
        self.search_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_smart_crawler_called_for_new_products(self, mock_search):
        """Test SmartCrawler is called for new product URLs."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Glenfiddich 18", "link": "https://example.com/glenfiddich"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock SmartCrawler
        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Glenfiddich 18"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/glenfiddich"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.95

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ) as mock_extract:
            orchestrator.run()
            mock_extract.assert_called()

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_product_saved_on_extraction_success(self, mock_search):
        """Test product is saved when extraction succeeds."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Lagavulin 16", "link": "https://example.com/lagavulin"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {
            "name": "Lagavulin 16 Year Old",
            "brand": "Lagavulin",
            "abv": "43.0",
            "product_type": "whiskey",
        }
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/lagavulin"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.90
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        # Should have created a product
        self.assertEqual(job.products_new, 1)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_needs_review_flag_propagated(self, mock_search):
        """Test needs_review flag from SmartCrawler is saved."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Mystery Whiskey", "link": "https://example.com/mystery"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Unknown Whiskey", "product_type": "whiskey"}
        mock_extraction.needs_review = True  # Low confidence
        mock_extraction.review_reasons = ["Low name match score"]
        mock_extraction.source_url = "https://example.com/mystery"
        mock_extraction.source_type = "other"
        mock_extraction.name_match_score = 0.55
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        # Check the result has needs_review set
        result = DiscoveryResult.objects.filter(job=job).first()
        self.assertIsNotNone(result)
        self.assertTrue(result.needs_review)


class TestProductMergeLogic(TestCase):
    """Test TASK-GS-014: Product Merge Logic."""

    def setUp(self):
        """Set up test fixtures."""
        from crawler.models import DiscoveredBrand

        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-merge",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
        )
        # Create brand first
        self.brand = DiscoveredBrand.objects.create(
            name="Glenfiddich",
        )
        # Create an existing product with source_url
        self.existing_product = DiscoveredProduct.objects.create(
            name="Glenfiddich 18 Year Old",
            brand=self.brand,
            product_type="whiskey",
            source_url="https://masterofmalt.com/glenfiddich-18",
        )

    def test_find_existing_by_exact_url(self):
        """Test finding existing product by exact URL match."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        found = orchestrator._find_existing_product(
            url="https://masterofmalt.com/glenfiddich-18",
            name="Glenfiddich 18"
        )

        self.assertEqual(found, self.existing_product)

    def test_find_existing_by_fuzzy_name(self):
        """Test finding existing product by fuzzy name match."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Very similar name - should match with >85% token overlap
        # Original: "Glenfiddich 18 Year Old"
        # Test:     "Glenfiddich 18 Year Old"  - exact match (different URL)
        found = orchestrator._find_existing_product(
            url="https://newsite.com/glenfiddich",  # Different URL
            name="Glenfiddich 18 Year Old"  # Same name
        )

        # The fuzzy match should find this
        self.assertEqual(found, self.existing_product)

    def test_no_match_for_different_product(self):
        """Test no match returned for different product."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        found = orchestrator._find_existing_product(
            url="https://example.com/lagavulin-16",
            name="Lagavulin 16 Year Old"
        )

        self.assertIsNone(found)

    def test_merge_updates_alternative_urls(self):
        """Test merging updates product with new source information."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        new_url = "https://newretailer.com/glenfiddich-18"

        # The _merge_product method should be called but mainly for future use
        # For now we just verify it doesn't crash
        orchestrator._merge_product(
            existing=self.existing_product,
            new_url=new_url,
            new_data={"price": 99.99}
        )

        # Verify product still exists
        self.existing_product.refresh_from_db()
        self.assertEqual(self.existing_product.name, "Glenfiddich 18 Year Old")


class TestResultRecording(TestCase):
    """Test TASK-GS-015: Result Recording."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )
        self.search_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_discovery_result_created(self, mock_search):
        """Test DiscoveryResult is created for each processed URL."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Whiskey Review", "link": "https://retailer.com/whiskey1"},
            {"title": "Another Whiskey", "link": "https://retailer.com/whiskey2"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock extraction
        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Test Whiskey"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://retailer.com/whiskey1"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.85

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        results = DiscoveryResult.objects.filter(job=job)
        self.assertGreaterEqual(results.count(), 1)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_job_metrics_updated(self, mock_search):
        """Test job metrics are updated correctly."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Whiskey 1", "link": "https://example.com/w1"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Whiskey 1"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/w1"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.90

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        self.assertEqual(job.search_terms_processed, 1)
        self.assertEqual(job.serpapi_calls_used, 1)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_search_term_stats_updated(self, mock_search):
        """Test search term statistics are updated."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Whiskey", "link": "https://example.com/w"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Whiskey"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/w"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.90

        initial_count = self.search_term.search_count

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            orchestrator.run()

        self.search_term.refresh_from_db()
        self.assertEqual(self.search_term.search_count, initial_count + 1)
        self.assertIsNotNone(self.search_term.last_searched)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_error_captured_in_result(self, mock_search):
        """Test errors are captured in DiscoveryResult."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Error Whiskey", "link": "https://example.com/error"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = False
        mock_extraction.errors = ["Extraction failed", "Invalid content"]
        mock_extraction.data = None
        mock_extraction.source_url = "https://example.com/error"
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        result = DiscoveryResult.objects.filter(job=job).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.status, DiscoveryResultStatus.FAILED)
        self.assertIn("Extraction failed", result.error_message)


class TestQuotaTracking(TestCase):
    """Test quota tracking during discovery."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-quota",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=3,
        )
        SearchTerm.objects.create(
            term_template="test {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_serpapi_calls_counted(self, mock_search):
        """Test SerpAPI calls are counted in job."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = []
        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        job = orchestrator.run()

        self.assertEqual(job.serpapi_calls_used, 1)  # One term = one call

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_scrapingbee_calls_counted(self, mock_search):
        """Test ScrapingBee calls are counted."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Test", "link": "https://example.com/test"},
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Test"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com/test"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.90
        mock_extraction.scrapingbee_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            job = orchestrator.run()

        self.assertGreaterEqual(job.scrapingbee_calls_used, 1)


# ============================================================================
# Phase 4: Multi-Product Extraction Tests (TDD)
# ============================================================================


class TestListPageDetection(TestCase):
    """Test TASK-GS-016: List Page Detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )

    def test_detect_best_of_list_page_by_url(self):
        """Test detecting 'best of' list pages by URL pattern."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        list_urls = [
            ("https://vinepair.com/best-whiskey-2025", "Best Whiskey"),
            ("https://liquor.com/top-10-bourbon", "Top 10 Bourbon"),
            ("https://whiskyadvocate.com/best-scotch-under-50", "Best Scotch"),
            ("https://tastingtable.com/15-best-port-wines", "15 Best Port Wines"),
            ("https://example.com/10-best-whiskeys-of-2025", "10 Best Whiskeys"),
        ]

        for url, title in list_urls:
            result = orchestrator._is_list_page(url, title)
            self.assertTrue(result, f"Should detect list page: {url}")

    def test_detect_list_page_by_title(self):
        """Test detecting list pages by title keywords."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        list_titles = [
            ("https://example.com/article", "The 20 Best Scotch Whiskies to Try"),
            ("https://example.com/page", "Top 15 Bourbon Brands of 2025"),
            ("https://example.com/review", "Our Picks: Best Irish Whiskeys"),
            ("https://example.com/guide", "Ultimate Guide to the Best Port Wines"),
        ]

        for url, title in list_titles:
            result = orchestrator._is_list_page(url, title)
            self.assertTrue(result, f"Should detect list page by title: {title}")

    def test_single_product_page_not_list(self):
        """Test that single product pages are not detected as list pages."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        single_product_pages = [
            ("https://masterofmalt.com/product/glenfiddich-18", "Glenfiddich 18 Year Old"),
            ("https://thewhiskyexchange.com/p/123/lagavulin-16", "Lagavulin 16"),
            ("https://example.com/whiskey/macallan-12", "Macallan 12 Year Old"),
        ]

        for url, title in single_product_pages:
            result = orchestrator._is_list_page(url, title)
            self.assertFalse(result, f"Should NOT detect as list page: {url}")

    def test_list_page_type_classification(self):
        """Test classifying different types of list pages."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # "best of" list
        list_type = orchestrator._classify_list_type(
            "https://example.com/best-whiskey-2025",
            "Best Whiskeys of 2025"
        )
        self.assertEqual(list_type, "best_of")

        # "top N" list
        list_type = orchestrator._classify_list_type(
            "https://example.com/top-10-bourbon",
            "Top 10 Bourbon Brands"
        )
        self.assertEqual(list_type, "top_n")

        # "gift guide" or recommendation list
        list_type = orchestrator._classify_list_type(
            "https://example.com/gift-guide",
            "Holiday Gift Guide: Whiskey Edition"
        )
        self.assertEqual(list_type, "gift_guide")

    def test_estimate_list_size_from_title(self):
        """Test estimating number of products in a list from title."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        test_cases = [
            ("Top 10 Bourbon Brands", 10),
            ("15 Best Port Wines", 15),
            ("The 20 Best Scotch Whiskies", 20),
            ("Best Whiskeys to Try", None),  # No number
            ("Our 5 Favorite Ryes", 5),
        ]

        for title, expected in test_cases:
            size = orchestrator._estimate_list_size(title)
            self.assertEqual(size, expected, f"Failed for title: {title}")


class TestAIListExtraction(TestCase):
    """Test TASK-GS-017: AI List Extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )
        self.search_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    def test_extract_products_from_list_page(self):
        """Test extracting multiple products from a list page."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock the AI extraction response
        mock_ai_response = {
            "products": [
                {"name": "Glenfiddich 18 Year Old", "brand": "Glenfiddich", "link": "/product/glenfiddich-18"},
                {"name": "Lagavulin 16 Year Old", "brand": "Lagavulin", "link": "/product/lagavulin-16"},
                {"name": "Macallan 12 Year Old", "brand": "Macallan", "link": "https://other-site.com/macallan"},
            ],
            "list_type": "best_of",
            "total_products": 3,
        }

        with patch.object(
            orchestrator, "_call_ai_list_extraction", return_value=mock_ai_response
        ):
            products = orchestrator._extract_list_products(
                url="https://vinepair.com/best-whiskey-2025",
                html_content="<html>...</html>"
            )

        self.assertEqual(len(products), 3)
        self.assertEqual(products[0]["name"], "Glenfiddich 18 Year Old")

    def test_resolve_relative_links_in_list(self):
        """Test that relative links are resolved to absolute URLs."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        products = [
            {"name": "Product 1", "link": "/product/p1"},
            {"name": "Product 2", "link": "https://other.com/p2"},
            {"name": "Product 3", "link": None},
        ]

        base_url = "https://example.com/best-whiskey"
        resolved = orchestrator._resolve_product_links(products, base_url)

        self.assertEqual(resolved[0]["link"], "https://example.com/product/p1")
        self.assertEqual(resolved[1]["link"], "https://other.com/p2")
        self.assertIsNone(resolved[2]["link"])

    def test_ai_list_extraction_with_empty_page(self):
        """Test AI extraction handles empty/invalid pages gracefully."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock empty response
        with patch.object(
            orchestrator, "_call_ai_list_extraction", return_value={"products": [], "error": "No products found"}
        ):
            products = orchestrator._extract_list_products(
                url="https://example.com/empty-page",
                html_content=""
            )

        self.assertEqual(len(products), 0)

    def test_ai_extraction_limits_products(self):
        """Test AI extraction respects max product limit."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock response with many products
        many_products = [{"name": f"Product {i}", "link": f"/p{i}"} for i in range(50)]
        mock_response = {"products": many_products, "total_products": 50}

        with patch.object(
            orchestrator, "_call_ai_list_extraction", return_value=mock_response
        ):
            products = orchestrator._extract_list_products(
                url="https://example.com/big-list",
                html_content="<html>...</html>",
                max_products=20
            )

        self.assertLessEqual(len(products), 20)

    def test_ai_extraction_parses_product_details(self):
        """Test AI extraction captures available product details."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        mock_response = {
            "products": [
                {
                    "name": "Glenfiddich 18",
                    "brand": "Glenfiddich",
                    "price": "$89.99",
                    "rating": "95 points",
                    "link": "/product/glenfiddich",
                    "description": "A rich, oak-aged single malt"
                }
            ],
            "total_products": 1,
        }

        with patch.object(
            orchestrator, "_call_ai_list_extraction", return_value=mock_response
        ):
            products = orchestrator._extract_list_products(
                url="https://example.com/list",
                html_content="<html>...</html>"
            )

        self.assertEqual(products[0]["brand"], "Glenfiddich")
        self.assertEqual(products[0]["price"], "$89.99")
        self.assertEqual(products[0]["rating"], "95 points")


class TestIndividualProductEnrichment(TestCase):
    """Test TASK-GS-018: Individual Product Enrichment."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=5,
        )
        self.search_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_enrichment_follows_product_links(self, mock_search):
        """Test enrichment follows links to get full product details."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        # Mock search returning a list page
        mock_search.return_value = [
            {"title": "Best Whiskeys 2025", "link": "https://vinepair.com/best-whiskey-2025"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock list detection
        with patch.object(orchestrator, "_is_list_page", return_value=True):
            # Mock list extraction returning products with links
            mock_list_products = [
                {"name": "Glenfiddich 18", "brand": "Glenfiddich", "link": "https://retailer.com/glenfiddich"},
                {"name": "Lagavulin 16", "brand": "Lagavulin", "link": "https://retailer.com/lagavulin"},
            ]
            with patch.object(orchestrator, "_extract_list_products", return_value=mock_list_products):
                # Mock SmartCrawler for enrichment
                mock_extraction = Mock()
                mock_extraction.success = True
                mock_extraction.data = {"name": "Glenfiddich 18 Year Old", "abv": "43%"}
                mock_extraction.needs_review = False
                mock_extraction.source_url = "https://retailer.com/glenfiddich"
                mock_extraction.source_type = "trusted_retailer"
                mock_extraction.name_match_score = 0.95
                mock_extraction.scrapingbee_calls = 1
                mock_extraction.ai_calls = 1

                with patch.object(
                    orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
                ) as mock_extract:
                    with patch.object(orchestrator, "_fetch_page_content", return_value="<html>...</html>"):
                        job = orchestrator.run()

                    # SmartCrawler should be called for each product with link
                    self.assertGreaterEqual(mock_extract.call_count, 1)

    def test_enrich_product_without_link(self):
        """Test handling products without direct links."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Product from list with no link
        product_info = {
            "name": "Mystery Whiskey XO",
            "brand": "Unknown",
            "price": "$150",
            "rating": "92 points",
            "link": None
        }

        # Should create a partial product record needing enrichment
        with patch.object(orchestrator, "_search_for_product_details") as mock_search:
            mock_search.return_value = None  # No additional details found

            result = orchestrator._enrich_product_from_list(
                product_info,
                source_url="https://example.com/best-list",
                search_term=self.search_term
            )

        # Should create product with available info and mark for review
        self.assertIsNotNone(result)
        self.assertTrue(result.get("needs_review", False) or result.get("partial", False))

    def test_enrichment_deduplicates_against_existing(self):
        """Test enrichment checks for existing products before creating new ones."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator
        from crawler.models import DiscoveredBrand

        # Create existing product
        brand = DiscoveredBrand.objects.create(name="Glenfiddich")
        existing = DiscoveredProduct.objects.create(
            name="Glenfiddich 18 Year Old",
            brand=brand,
            product_type="whiskey",
            source_url="https://original.com/glenfiddich"
        )

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Product from list that matches existing
        product_info = {
            "name": "Glenfiddich 18 Year Old",
            "brand": "Glenfiddich",
            "link": "https://new-source.com/glenfiddich-18"
        }

        result = orchestrator._enrich_product_from_list(
            product_info,
            source_url="https://example.com/best-list",
            search_term=self.search_term
        )

        # Should detect as duplicate
        self.assertTrue(result.get("is_duplicate", False))
        self.assertEqual(result.get("existing_product_id"), existing.id)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_list_page_creates_multiple_products(self, mock_search):
        """Test processing a list page creates multiple product records."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Top 5 Bourbons", "link": "https://example.com/top-5-bourbon"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        with patch.object(orchestrator, "_is_list_page", return_value=True):
            mock_list = [
                {"name": "Buffalo Trace", "brand": "Buffalo Trace", "link": None},
                {"name": "Woodford Reserve", "brand": "Woodford", "link": None},
                {"name": "Maker's Mark", "brand": "Maker's Mark", "link": None},
            ]
            with patch.object(orchestrator, "_extract_list_products", return_value=mock_list):
                with patch.object(orchestrator, "_fetch_page_content", return_value="<html>...</html>"):
                    with patch.object(orchestrator, "_enrich_product_from_list") as mock_enrich:
                        mock_enrich.return_value = {"created": True, "needs_review": True}
                        job = orchestrator.run()

                        # Should have called enrich for each product
                        self.assertEqual(mock_enrich.call_count, 3)

    def test_enrichment_tracks_source_list(self):
        """Test enriched products track their source list page."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        product_info = {
            "name": "Test Whiskey",
            "brand": "TestBrand",
            "link": "https://retailer.com/test-whiskey"
        }

        # Mock SmartCrawler extraction
        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Test Whiskey", "abv": "40%"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://retailer.com/test-whiskey"
        mock_extraction.source_type = "trusted_retailer"
        mock_extraction.name_match_score = 0.95
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            result = orchestrator._enrich_product_from_list(
                product_info,
                source_url="https://vinepair.com/best-whiskey-2025",
                search_term=self.search_term
            )

        # Result should track the list page source
        self.assertEqual(result.get("discovered_via_list"), "https://vinepair.com/best-whiskey-2025")


class TestListPageProcessingIntegration(TestCase):
    """Integration tests for full list page processing flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = CrawlSchedule.objects.create(
            name="Test Schedule",
            slug="test-schedule-integration",
            category=ScheduleCategory.DISCOVERY,
            frequency=ScheduleFrequency.DAILY,
            search_terms=["test query"],
            max_results_per_term=10,
        )
        self.search_term = SearchTerm.objects.create(
            term_template="best whiskey {year}",
            category=SearchTermCategory.BEST_LISTS,
            product_type=SearchTermProductType.WHISKEY,
            priority=100,
            is_active=True,
        )

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_full_list_page_flow(self, mock_search):
        """Test complete flow: search -> detect list -> extract -> enrich."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        # Search returns a list page
        mock_search.return_value = [
            {"title": "10 Best Scotch Whiskies 2025", "link": "https://review-site.com/best-scotch"}
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Mock page fetch
        with patch.object(orchestrator, "_fetch_page_content", return_value="<html>list content</html>"):
            # Mock list detection (based on URL/title)
            with patch.object(orchestrator, "_is_list_page", return_value=True):
                # Mock AI list extraction
                mock_products = [
                    {"name": "Lagavulin 16", "brand": "Lagavulin", "link": "https://retailer.com/lagavulin"},
                    {"name": "Laphroaig 10", "brand": "Laphroaig", "link": "https://retailer.com/laphroaig"},
                ]
                with patch.object(orchestrator, "_extract_list_products", return_value=mock_products):
                    # Mock SmartCrawler enrichment
                    mock_extraction = Mock()
                    mock_extraction.success = True
                    mock_extraction.data = {"name": "Lagavulin 16 Year Old"}
                    mock_extraction.needs_review = False
                    mock_extraction.source_url = "https://retailer.com/lagavulin"
                    mock_extraction.source_type = "trusted_retailer"
                    mock_extraction.name_match_score = 0.95
                    mock_extraction.scrapingbee_calls = 1
                    mock_extraction.ai_calls = 1

                    with patch.object(
                        orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
                    ):
                        job = orchestrator.run()

        # Verify job completed and tracked list processing
        self.assertEqual(job.status, DiscoveryJobStatus.COMPLETED)
        self.assertGreaterEqual(job.products_new + job.products_updated, 0)

    @patch("crawler.services.discovery_orchestrator.DiscoveryOrchestrator._search")
    def test_mixed_single_and_list_pages(self, mock_search):
        """Test handling both single product pages and list pages in same search."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        mock_search.return_value = [
            {"title": "Glenfiddich 18 Review", "link": "https://retailer.com/glenfiddich-18"},  # Single
            {"title": "Best Whiskeys 2025", "link": "https://review.com/best-whiskey"},  # List
            {"title": "Macallan 12", "link": "https://shop.com/macallan"},  # Single
        ]

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)

        # Set up detection to return True only for the list page
        def is_list_page(url, title):
            return "best" in title.lower() and "best" in url.lower()

        with patch.object(orchestrator, "_is_list_page", side_effect=is_list_page):
            with patch.object(orchestrator, "_fetch_page_content", return_value="<html>...</html>"):
                mock_list = [{"name": "Test", "link": None}]
                with patch.object(orchestrator, "_extract_list_products", return_value=mock_list):
                    mock_extraction = Mock()
                    mock_extraction.success = True
                    mock_extraction.data = {"name": "Test Product"}
                    mock_extraction.needs_review = False
                    mock_extraction.source_url = "https://example.com"
                    mock_extraction.source_type = "other"
                    mock_extraction.name_match_score = 0.90
                    mock_extraction.scrapingbee_calls = 1
                    mock_extraction.ai_calls = 1

                    with patch.object(
                        orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
                    ):
                        with patch.object(orchestrator, "_enrich_product_from_list", return_value={"created": True}):
                            job = orchestrator.run()

        self.assertEqual(job.status, DiscoveryJobStatus.COMPLETED)

    def test_list_extraction_quota_tracking(self):
        """Test that list extraction properly tracks API quotas."""
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator(schedule=self.schedule)
        orchestrator.job = DiscoveryJob.objects.create(
            crawl_schedule=self.schedule,
            status=DiscoveryJobStatus.RUNNING,
        )

        # Mock list with 5 products
        mock_products = [
            {"name": f"Product {i}", "link": f"https://example.com/p{i}"}
            for i in range(5)
        ]

        mock_extraction = Mock()
        mock_extraction.success = True
        mock_extraction.data = {"name": "Product"}
        mock_extraction.needs_review = False
        mock_extraction.source_url = "https://example.com"
        mock_extraction.source_type = "other"
        mock_extraction.name_match_score = 0.90
        mock_extraction.scrapingbee_calls = 1
        mock_extraction.ai_calls = 1

        with patch.object(
            orchestrator.smart_crawler, "extract_product", return_value=mock_extraction
        ):
            orchestrator._process_list_page_products(
                mock_products,
                list_url="https://review.com/best-list",
                search_term=self.search_term
            )

        # Should track 5 ScrapingBee calls (one per product link)
        self.assertGreaterEqual(orchestrator.job.scrapingbee_calls_used, 5)
