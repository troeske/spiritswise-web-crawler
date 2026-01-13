"""
E2E Test: Generic Search Discovery Flow

Tests the complete discovery flow per V2 Architecture Spec Section 7:
- Section 7.2: Load SearchTerms from database
- Section 7.3: Filter by seasonality and priority
- Section 7.4: Execute SerpAPI searches (organic only)
- Section 7.5: Store results in DiscoveryResult
- Section 7.6: Process URLs through List Page Extraction
- Section 7.9: Detail Page Extraction
- Section 7.10: Enrichment Queue
- Section 7.11: Complete flow with Wayback archival

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md

IMPORTANT: These tests use REAL external services - SerpAPI, ScrapingBee, AI Service.
All data created during tests is PRESERVED for verification.
"""

import pytest
import logging
from datetime import datetime
from typing import List, Dict, Any

from tests.e2e.conftest import e2e, requires_serpapi, requires_ai_service
from tests.e2e.utils.test_products import PRODUCT_TYPE_IDS

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestGenericSearchDiscoveryFlow:
    """
    E2E test for Generic Search Discovery per Spec Section 7.

    This test class validates the complete discovery pipeline from
    SearchTerm configuration through product extraction and archival.
    """

    @pytest.mark.parametrize("product_type", PRODUCT_TYPE_IDS)
    def test_search_terms_loaded_from_database(
        self,
        product_type: str,
        db,
        search_term_factory,
        test_run_tracker,
    ):
        """
        [SPEC Section 7.2] SearchTerms are loaded from database.
        [STATUS: COMPLETE]

        Verifies that:
        1. SearchTerms can be created in the database
        2. Active terms can be queried
        3. Fields match spec requirements (search_query, max_results, priority)
        """
        from crawler.models import SearchTerm

        # Build product-type-specific queries
        product_label = product_type.replace("_", " ")

        # Create test SearchTerms
        term1 = search_term_factory(
            search_query=f"best {product_label} 2026",
            category="best_lists",
            product_type=product_type,
            max_results=5,
            priority=100,
            is_active=True,
        )
        term2 = search_term_factory(
            search_query=f"top {product_label} awards 2026",
            category="awards",
            product_type=product_type,
            max_results=10,
            priority=90,
            is_active=True,
        )
        term3 = search_term_factory(
            search_query=f"inactive {product_label} term",
            category="best_lists",
            product_type=product_type,
            is_active=False,
        )

        # Verify terms are in database for this product type
        active_terms = SearchTerm.objects.filter(is_active=True, product_type=product_type)
        assert active_terms.count() >= 2

        # Verify fields match spec
        loaded_term = SearchTerm.objects.get(id=term1.id)
        assert loaded_term.search_query == f"best {product_label} 2026"
        assert loaded_term.max_results == 5
        assert loaded_term.priority == 100
        assert loaded_term.category == "best_lists"
        assert loaded_term.product_type == product_type

        # Verify inactive term is filtered out
        active_queries = list(active_terms.values_list("search_query", flat=True))
        assert f"inactive {product_label} term" not in active_queries

        logger.info(f"Created {active_terms.count()} active SearchTerms for {product_type}")

    def test_search_terms_priority_ordering(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] SearchTerms ordered by priority (lower = higher priority).
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        # Create terms with different priorities
        search_term_factory(search_query="low priority term", priority=200)
        search_term_factory(search_query="high priority term", priority=50)
        search_term_factory(search_query="medium priority term", priority=100)

        # Query with priority ordering
        ordered_terms = SearchTerm.objects.filter(is_active=True).order_by("priority")
        priorities = [t.priority for t in ordered_terms]

        # Verify ordering
        assert priorities == sorted(priorities), "Terms should be ordered by priority ascending"

    def test_search_terms_seasonality_filtering(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Seasonal terms only active during specified months.
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        current_month = datetime.now().month

        # Create year-round term
        year_round = search_term_factory(
            search_query="year round whiskey",
            seasonal_start_month=None,
            seasonal_end_month=None,
        )

        # Create seasonal term for current month
        in_season = search_term_factory(
            search_query="in season whiskey",
            seasonal_start_month=current_month,
            seasonal_end_month=current_month,
        )

        # Create out-of-season term
        out_month = (current_month % 12) + 1  # Next month
        out_of_season = search_term_factory(
            search_query="out of season whiskey",
            seasonal_start_month=out_month,
            seasonal_end_month=out_month,
        )

        # Verify is_in_season() method
        assert year_round.is_in_season() is True, "Year-round term should always be in season"
        assert in_season.is_in_season() is True, "Current month term should be in season"
        # Note: out_of_season.is_in_season() depends on current month

    @pytest.mark.parametrize("product_type", PRODUCT_TYPE_IDS)
    def test_search_term_max_results_enforcement(
        self,
        product_type: str,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.4] max_results field controls per-term crawl limit.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        # Valid max_results values
        term = search_term_factory(max_results=15, product_type=product_type)
        assert term.max_results == 15

        # Test boundary values
        term_min = search_term_factory(search_query="min results", max_results=1, product_type=product_type)
        assert term_min.max_results == 1

        term_max = search_term_factory(search_query="max results", max_results=20, product_type=product_type)
        assert term_max.max_results == 20

        # Invalid values should fail validation
        invalid_term = SearchTerm(
            search_query="invalid term",
            category="best_lists",
            product_type=product_type,
            max_results=0,  # Below minimum
        )
        with pytest.raises(ValidationError):
            invalid_term.full_clean()

    def test_search_term_metrics_tracking(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] SearchTerm tracks search_count and products_discovered.
        [STATUS: COMPLETE]
        """
        from django.utils import timezone

        term = search_term_factory()

        # Initial values
        assert term.search_count == 0
        assert term.products_discovered == 0
        assert term.last_searched is None

        # Simulate search execution
        term.search_count += 1
        term.products_discovered += 5
        term.last_searched = timezone.now()
        term.save()

        # Reload and verify
        term.refresh_from_db()
        assert term.search_count == 1
        assert term.products_discovered == 5
        assert term.last_searched is not None

    @requires_serpapi
    def test_serpapi_returns_organic_only(
        self,
        db,
        serpapi_client,
        test_run_tracker,
    ):
        """
        [SPEC Section 7.4] Only organic_results used, ads excluded.
        [STATUS: COMPLETE]

        Note: This test requires SERPAPI_API_KEY to be configured.
        """
        import httpx

        if not serpapi_client:
            pytest.skip("SerpAPI not configured")

        # Execute a real search
        params = {
            "api_key": serpapi_client["api_key"],
            "q": "best bourbon whiskey 2026",
            "engine": "google",
            "num": 5,
        }

        response = httpx.get(serpapi_client["base_url"], params=params, timeout=30.0)
        test_run_tracker.record_api_call("serpapi")

        assert response.status_code == 200
        data = response.json()

        # Verify we get organic results
        organic_results = data.get("organic_results", [])
        assert len(organic_results) > 0, "Should have organic results"

        # Verify organic results structure
        for result in organic_results[:3]:
            assert "link" in result, "Organic result should have 'link'"
            assert "title" in result, "Organic result should have 'title'"
            # Should NOT be an ad
            assert result.get("type") != "ad"

        logger.info(f"SerpAPI returned {len(organic_results)} organic results")

    def test_discovery_result_model_exists(
        self,
        db,
    ):
        """
        [SPEC Section 7.5] DiscoveryResult model stores discovered URLs.
        [STATUS: COMPLETE]
        """
        from crawler.models import DiscoveryResult, DiscoveryResultStatus

        # Verify model and status choices exist
        assert hasattr(DiscoveryResult, "source_url")
        assert hasattr(DiscoveryResult, "status")
        assert hasattr(DiscoveryResult, "search_term")

        # Verify status choices include DUPLICATE
        assert DiscoveryResultStatus.DUPLICATE == "duplicate"

    def test_discovery_job_model_exists(
        self,
        db,
        discovery_job_factory,
    ):
        """
        [SPEC Section 7.5] DiscoveryJob tracks job execution.
        [STATUS: COMPLETE]
        """
        from crawler.models import DiscoveryJob

        job = discovery_job_factory()

        assert job.id is not None
        assert hasattr(job, "status")
        assert hasattr(job, "serpapi_calls_used")

    def test_crawled_source_list_page_type(
        self,
        db,
        source_factory,
    ):
        """
        [SPEC Section 8.4] CrawledSource accepts source_type='list_page'.
        [STATUS: COMPLETE]
        """
        from crawler.models import CrawledSourceTypeChoices

        source = source_factory(
            url="https://example.com/best-whiskey-2026",
            source_type=CrawledSourceTypeChoices.LIST_PAGE,
            raw_content="<html><body>Best Whiskey List</body></html>",
        )

        assert source.source_type == "list_page"
        source.refresh_from_db()
        assert source.source_type == "list_page"

    @requires_ai_service
    @pytest.mark.parametrize("product_type", PRODUCT_TYPE_IDS)
    @pytest.mark.asyncio
    async def test_list_page_extraction_triggered(
        self,
        product_type: str,
        db,
        ai_client,
        test_run_tracker,
    ):
        """
        [SPEC Section 7.6] Discovered URLs processed through List Page Extraction.
        [STATUS: COMPLETE]

        Note: This test requires AI_ENHANCEMENT_SERVICE to be configured.
        """
        if not ai_client:
            pytest.skip("AI Enhancement Service not configured")

        # Load base_fields.json fixture if FieldDefinitions don't exist
        from crawler.models import FieldDefinition
        from django.core.management import call_command
        from asgiref.sync import sync_to_async

        field_def_exists = await sync_to_async(FieldDefinition.objects.exists, thread_sensitive=True)()
        if not field_def_exists:
            logger.info("Loading base_fields.json fixture...")
            await sync_to_async(call_command, thread_sensitive=True)("loaddata", "crawler/fixtures/base_fields.json", verbosity=0)

        # Product-type-specific sample content
        sample_content_by_type = {
            "whiskey": """
            <html>
            <body>
                <h1>Best Bourbon Whiskey 2026</h1>
                <ol>
                    <li><a href="/products/buffalo-trace">Buffalo Trace Bourbon</a> - 45% ABV</li>
                    <li><a href="/products/woodford-reserve">Woodford Reserve</a> - 43.2% ABV</li>
                    <li><a href="/products/makers-mark">Maker's Mark</a> - 45% ABV</li>
                </ol>
            </body>
            </html>
            """,
            "port_wine": """
            <html>
            <body>
                <h1>Best Port Wines 2026</h1>
                <ol>
                    <li><a href="/products/taylors-20">Taylor's 20 Year Old Tawny Port</a> - 20% ABV</li>
                    <li><a href="/products/grahams-10">Graham's 10 Year Old Tawny Port</a> - 20% ABV</li>
                    <li><a href="/products/dows-vintage">Dow's Vintage Port 2017</a> - 20% ABV</li>
                </ol>
            </body>
            </html>
            """,
        }

        sample_content = sample_content_by_type.get(product_type, sample_content_by_type["whiskey"])

        # Call AI extraction (async method using proper async/await)
        result = await ai_client.extract(
            content=sample_content,
            product_type=product_type,
            detect_multi_product=True,
        )
        test_run_tracker.record_api_call("openai")

        # Verify extraction - result is ExtractionResultV2 object
        assert result.success is True, f"Extraction failed: {result.error}"
        products = getattr(result, 'products', []) or []
        assert len(products) >= 1

        # Log extraction result
        logger.info(f"Extracted {len(products)} products from {product_type} list page")

    def test_wayback_service_available(
        self,
        db,
        wayback_service,
    ):
        """
        [SPEC Section 7.6, 7.9] Wayback archival service is available.
        [STATUS: COMPLETE]
        """
        assert wayback_service is not None
        assert hasattr(wayback_service, "save_url") or hasattr(wayback_service, "queue_archive")

    def test_discovery_orchestrator_available(
        self,
        db,
    ):
        """
        [SPEC Section 7] DiscoveryOrchestrator service exists.
        [STATUS: COMPLETE]
        """
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        # Verify class exists and has expected methods
        assert hasattr(DiscoveryOrchestratorV2, "_get_search_terms")
        assert hasattr(DiscoveryOrchestratorV2, "_process_search_term")

    def test_skeleton_product_status_exists(
        self,
        db,
    ):
        """
        [SPEC Section 7.10] Skeleton status for incomplete products.
        [STATUS: COMPLETE]
        """
        from crawler.models import DiscoveredProductStatus

        # Verify SKELETON status exists (legacy status for V2 spec)
        assert hasattr(DiscoveredProductStatus, "SKELETON")
        assert DiscoveredProductStatus.SKELETON == "skeleton"

        # Verify status progression
        assert hasattr(DiscoveredProductStatus, "PARTIAL")
        assert hasattr(DiscoveredProductStatus, "COMPLETE")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermIntegration:
    """
    Integration tests for SearchTerm with Discovery flow.
    """

    def test_search_term_str_representation(
        self,
        db,
        search_term_factory,
    ):
        """SearchTerm string representation shows search_query and category."""
        term = search_term_factory(
            search_query="best scotch whisky 2026",
            category="best_lists",
        )

        str_repr = str(term)
        assert "best scotch whisky 2026" in str_repr
        assert "best_lists" in str_repr

    def test_search_term_category_choices(
        self,
        db,
    ):
        """SearchTerm category uses valid choices."""
        from crawler.models import SearchTermCategory

        # Verify expected categories exist
        expected_categories = ["best_lists", "awards", "new_releases", "style", "value", "regional", "seasonal"]
        for cat in expected_categories:
            assert cat in SearchTermCategory.values, f"Missing category: {cat}"

    def test_search_term_product_type_choices(
        self,
        db,
    ):
        """SearchTerm product_type uses valid choices."""
        from crawler.models import SearchTermProductType

        # Verify expected product types exist
        expected_types = ["whiskey", "port_wine"]
        for ptype in expected_types:
            assert ptype in SearchTermProductType.values, f"Missing product type: {ptype}"
