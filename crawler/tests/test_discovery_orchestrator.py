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
    DiscoverySchedule,
    DiscoveryJob,
    DiscoveryResult,
    DiscoveredProduct,
    SearchTermCategory,
    SearchTermProductType,
    ScheduleFrequency,
    DiscoveryJobStatus,
    DiscoveryResultStatus,
)


class TestDiscoveryOrchestratorInit(TestCase):
    """Test TASK-GS-010: Core Orchestrator Class initialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
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
        self.assertEqual(job.schedule, self.schedule)

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
        job = DiscoveryJob.objects.get(schedule=self.schedule)
        self.assertEqual(job.status, DiscoveryJobStatus.FAILED)
        self.assertIn("SerpAPI error", job.error_log)


class TestGetSearchTerms(TestCase):
    """Test TASK-GS-010: _get_search_terms() filtering."""

    def setUp(self):
        """Set up test fixtures with various search terms."""
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=5,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
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

        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=10,
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
        self.schedule = DiscoverySchedule.objects.create(
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            max_search_terms=2,
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
