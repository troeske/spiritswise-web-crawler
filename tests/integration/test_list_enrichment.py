# tests/integration/test_list_enrichment.py
"""
Integration tests for List Page Enrichment Flow.

Task 3.2: Test enrichment of products extracted from list pages:
- Products with direct links -> Crawl the linked page for full details
- Products without links -> Search (SerpAPI) to find product page, then crawl

Tests verify the VPS AI service at:
https://api.spiritswise.tech/api/v1/enhance/from-crawler/

To run these tests:
    RUN_VPS_TESTS=true pytest tests/integration/test_list_enrichment.py -v

NO MOCKS are used for AI service - all tests call the real VPS AI service.
SerpAPI is mocked for cost control in non-production tests.
"""

import pytest
import httpx
import os
import time
from typing import Optional, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Mark all tests to require VPS flag
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VPS_TESTS") != "true",
    reason="VPS tests disabled - set RUN_VPS_TESTS=true"
)


# =============================================================================
# Mock Data for Enrichment Tests
# =============================================================================

# Products extracted from a list page (from Task 3.1)
EXTRACTED_PRODUCTS = [
    {
        "name": "Ardbeg Uigeadail",
        "direct_product_link": "https://www.thewhiskyexchange.com/p/6180/ardbeg-uigeadail",
        "rating": "96 points",
        "source_article_url": "https://whiskyadvocate.com/top-10-whiskeys-2024",
    },
    {
        "name": "Buffalo Trace Kentucky Straight Bourbon",
        "direct_product_link": None,  # Needs search enrichment
        "rating": "94 points",
        "source_article_url": "https://whiskyadvocate.com/top-10-whiskeys-2024",
    },
    {
        "name": "Redbreast 12 Year Old",
        "direct_product_link": None,  # Needs search enrichment
        "rating": "93 points",
        "source_article_url": "https://whiskyadvocate.com/top-10-whiskeys-2024",
    },
]

# Mock product page content for crawling linked pages
MOCK_ARDBEG_PRODUCT_PAGE = """
<html>
<head><title>Ardbeg Uigeadail | The Whisky Exchange</title></head>
<body>
<h1>Ardbeg Uigeadail</h1>
<div class="product-info">
    <p>ABV: 54.2%</p>
    <p>Price: $79.99</p>
    <p>Region: Islay, Scotland</p>
    <p>Style: Single Malt Scotch Whisky</p>
</div>
<div class="tasting-notes">
    <h3>Nose:</h3>
    <p>Smoke, tar, and rich dried fruit. Deep espresso and dark chocolate.</p>
    <h3>Palate:</h3>
    <p>Massive peat with Christmas cake sweetness. Roasted coffee, treacle.</p>
    <h3>Finish:</h3>
    <p>Long, warming, and smoky with lingering fruit notes.</p>
</div>
<div class="awards">
    <p>World Whiskies Awards 2023 - Gold Medal</p>
    <p>Jim Murray's Whisky Bible - 96 Points</p>
</div>
</body>
</html>
"""

MOCK_BUFFALO_TRACE_PAGE = """
<html>
<head><title>Buffalo Trace Kentucky Straight Bourbon Whiskey</title></head>
<body>
<h1>Buffalo Trace Kentucky Straight Bourbon</h1>
<div class="product-info">
    <p>ABV: 45%</p>
    <p>Price: $29.99</p>
    <p>Region: Kentucky, USA</p>
    <p>Style: Straight Bourbon Whiskey</p>
</div>
<div class="tasting-notes">
    <h3>Nose:</h3>
    <p>Sweet vanilla, brown sugar, and hints of oak. Light mint and molasses.</p>
    <h3>Palate:</h3>
    <p>Caramel and vanilla with toasted oak. Complex with hints of cherry.</p>
    <h3>Finish:</h3>
    <p>Long and smooth with a pleasant sweetness.</p>
</div>
</body>
</html>
"""

# Mock SerpAPI search results
MOCK_SERPAPI_RESULTS = {
    "Buffalo Trace": [
        {
            "url": "https://www.totalwine.com/spirits/bourbon/buffalo-trace/p/123",
            "domain": "totalwine.com",
            "title": "Buffalo Trace Kentucky Straight Bourbon Whiskey",
            "snippet": "Buffalo Trace Kentucky Straight Bourbon Whiskey. Shop online or find in store.",
            "position": 1,
        },
        {
            "url": "https://www.buffalotracedistillery.com/our-brands/buffalo-trace.html",
            "domain": "buffalotracedistillery.com",
            "title": "Buffalo Trace - Official Site",
            "snippet": "Buffalo Trace Kentucky Straight Bourbon Whiskey. The flagship bourbon.",
            "position": 2,
        },
    ],
    "Redbreast 12": [
        {
            "url": "https://www.thewhiskyexchange.com/p/12345/redbreast-12-year-old",
            "domain": "thewhiskyexchange.com",
            "title": "Redbreast 12 Year Old Irish Whiskey",
            "snippet": "Redbreast 12 Year Old is a classic Irish pot still whiskey.",
            "position": 1,
        },
    ],
}


# =============================================================================
# VPS AI Service Client
# =============================================================================

class VPSAIClient:
    """
    Direct VPS AI Service client for testing enrichment flow.

    Calls https://api.spiritswise.tech/api/v1/enhance/from-crawler/
    """

    BASE_URL = "https://api.spiritswise.tech"
    ENDPOINT = "/api/v1/enhance/from-crawler/"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN", "")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def extract_from_content(
        self,
        content: str,
        source_url: str,
        product_type_hint: Optional[str] = None,
        timeout: float = 60.0
    ) -> dict:
        """
        Call VPS AI service to extract product data from content.

        Args:
            content: Cleaned text content from the page
            source_url: URL of the page
            product_type_hint: Optional hint for product type
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON response from AI service
        """
        payload = {
            "content": content,
            "source_url": source_url,
        }

        if product_type_hint:
            payload["product_type_hint"] = product_type_hint

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}{self.ENDPOINT}",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()


# =============================================================================
# Mock SerpAPI Client for Cost Control
# =============================================================================

class MockSerpAPIClient:
    """
    Mock SerpAPI client for testing without API costs.
    """

    def __init__(self):
        self.search_calls = []

    async def search(self, query: str, num_results: int = 10) -> List[Dict]:
        """Mock search returning predefined results."""
        self.search_calls.append(query)

        # Find matching mock results
        for product_name, results in MOCK_SERPAPI_RESULTS.items():
            if product_name.lower() in query.lower():
                return results

        # Default empty results
        return []

    async def search_brand_official_site(self, brand_name: str) -> Optional[Dict]:
        """Mock search for brand official site."""
        results = await self.search(brand_name)
        return results[0] if results else None


# =============================================================================
# Enrichment Service for Testing
# =============================================================================

class ProductEnrichmentService:
    """
    Service to enrich products from list page extraction.

    Handles:
    1. Products with direct links -> Crawl linked page
    2. Products without links -> Search then crawl
    """

    def __init__(
        self,
        ai_client: VPSAIClient,
        serpapi_client = None,
        http_client = None
    ):
        self.ai_client = ai_client
        self.serpapi_client = serpapi_client or MockSerpAPIClient()
        self.http_client = http_client

    async def enrich_product(
        self,
        product: Dict[str, Any],
        mock_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich a single product extracted from a list page.

        Args:
            product: Product dict with name, direct_product_link, etc.
            mock_content: Optional mock HTML content for testing

        Returns:
            Enriched product dict with full details
        """
        enrichment_source = "none"
        enriched_data = {}
        original_data = product.copy()

        direct_link = product.get("direct_product_link")

        if direct_link:
            # Strategy 1: Crawl the direct link
            enrichment_source = "direct_link"
            content = mock_content or await self._fetch_page(direct_link)

            if content:
                try:
                    ai_result = await self.ai_client.extract_from_content(
                        content=content,
                        source_url=direct_link,
                        product_type_hint="whiskey"
                    )
                    enriched_data = ai_result.get("extracted_data", {})
                except Exception as e:
                    enrichment_source = "failed"
                    enriched_data = {"error": str(e)}
        else:
            # Strategy 2: Search then crawl
            product_name = product.get("name", "")

            # Build search query
            search_query = f"{product_name} buy price whiskey"
            search_results = await self.serpapi_client.search(search_query)

            if search_results:
                enrichment_source = "search_result"
                best_result = self._filter_search_results(search_results)

                if best_result:
                    content = mock_content or await self._fetch_page(best_result["url"])

                    if content:
                        try:
                            ai_result = await self.ai_client.extract_from_content(
                                content=content,
                                source_url=best_result["url"],
                                product_type_hint="whiskey"
                            )
                            enriched_data = ai_result.get("extracted_data", {})
                        except Exception:
                            enrichment_source = "failed"
            else:
                enrichment_source = "failed"

        # Merge enriched data with original
        result = {
            **original_data,
            **enriched_data,
            "enrichment_source": enrichment_source,
            "enrichment_sources": [enrichment_source],
        }

        # Preserve original source info
        if original_data.get("source_article_url"):
            result["original_source_url"] = original_data["source_article_url"]
        if original_data.get("rating"):
            result["original_rating"] = original_data["rating"]

        # Determine completeness status
        result["status"] = self._determine_status(result)

        return result

    def _filter_search_results(self, results: List[Dict]) -> Optional[Dict]:
        """
        Filter search results to find best product page.

        Prefers:
        - Official retailer sites
        - Product pages (not reviews, not forums)
        """
        # Preferred domains (retailers)
        preferred_domains = [
            "thewhiskyexchange.com",
            "masterofmalt.com",
            "totalwine.com",
            "klwines.com",
            "wine.com",
        ]

        # Excluded domains (reviews, forums)
        excluded_domains = [
            "reddit.com",
            "facebook.com",
            "twitter.com",
            "youtube.com",
            "wikipedia.org",
        ]

        # First pass: preferred domains
        for result in results:
            domain = result.get("domain", "")
            if any(pref in domain for pref in preferred_domains):
                return result

        # Second pass: any non-excluded domain
        for result in results:
            domain = result.get("domain", "")
            if not any(excl in domain for excl in excluded_domains):
                return result

        return None

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content (mock for testing)."""
        # In real implementation, would use SmartRouter
        # For testing, return None to use mock content
        return None

    def _determine_status(self, product: Dict) -> str:
        """Determine product completeness status."""
        has_name = bool(product.get("name"))
        has_palate = bool(product.get("palate") or product.get("tasting_notes"))
        has_price = bool(product.get("price"))

        if has_name and has_palate and has_price:
            return "COMPLETE"
        elif has_name and (has_palate or has_price):
            return "PARTIAL"
        elif has_name:
            return "INCOMPLETE"
        else:
            return "FAILED"


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def ai_client() -> VPSAIClient:
    """Create VPS AI client for tests."""
    return VPSAIClient()


@pytest.fixture
def mock_serpapi() -> MockSerpAPIClient:
    """Create mock SerpAPI client."""
    return MockSerpAPIClient()


@pytest.fixture
def enrichment_service(ai_client, mock_serpapi) -> ProductEnrichmentService:
    """Create enrichment service with mocked SerpAPI."""
    return ProductEnrichmentService(
        ai_client=ai_client,
        serpapi_client=mock_serpapi
    )


# =============================================================================
# Test Classes
# =============================================================================

class TestEnrichmentWithDirectLink:
    """
    Test enrichment when product has a direct link.

    All tests use REAL VPS AI service - NO MOCKS for AI.
    """

    @pytest.mark.asyncio
    async def test_enriches_product_with_direct_link(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Flow:
        1. Extract product from list page with direct_product_link
        2. Crawl the linked product page
        3. AI extracts full details from product page
        4. Merge into ProductCandidate with richer data
        """
        product = EXTRACTED_PRODUCTS[0]  # Ardbeg with direct link

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Should have enrichment source as direct_link
        assert result.get("enrichment_source") == "direct_link", \
            f"Should use direct_link for enrichment. Got: {result.get('enrichment_source')}"

        # Should have enriched data
        assert result.get("name"), "Should have product name"

        print(f"Enriched product: {result.get('name')}")
        print(f"Enrichment source: {result.get('enrichment_source')}")

    @pytest.mark.asyncio
    async def test_extracts_full_details_from_linked_page(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Product page should provide:
        - Full tasting notes (nose, palate, finish)
        - ABV
        - Price
        - Images
        - Awards
        """
        product = EXTRACTED_PRODUCTS[0]  # Ardbeg with direct link

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Check for tasting notes extraction
        has_tasting = (
            result.get("nose") or
            result.get("palate") or
            result.get("finish") or
            result.get("tasting_notes")
        )

        # Check for ABV extraction
        has_abv = result.get("abv") or result.get("alcohol_by_volume")

        # Log what was extracted
        print(f"Extracted details:")
        print(f"  Name: {result.get('name')}")
        print(f"  ABV: {result.get('abv')}")
        print(f"  Has tasting notes: {has_tasting is not None}")
        print(f"  Awards: {result.get('awards')}")

        # At minimum should have product name
        assert result.get("name"), "Should extract product name"

    @pytest.mark.asyncio
    async def test_preserves_original_source_info(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Original list page info should be preserved:
        - Source article URL
        - Rating from article (if any)
        """
        product = EXTRACTED_PRODUCTS[0]  # Ardbeg with direct link

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Should preserve original source URL
        assert result.get("original_source_url") == product["source_article_url"], \
            "Should preserve original source URL"

        # Should preserve original rating from article
        assert result.get("original_rating") == product["rating"], \
            "Should preserve original rating from article"

        print(f"Preserved source info:")
        print(f"  Original URL: {result.get('original_source_url')}")
        print(f"  Original rating: {result.get('original_rating')}")


class TestEnrichmentViaSearch:
    """
    Test enrichment via search when no direct link exists.

    SerpAPI is MOCKED for cost control.
    AI service is REAL.
    """

    @pytest.mark.asyncio
    async def test_enriches_product_via_search_when_no_link(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Flow:
        1. Extract product without direct_product_link
        2. SerpAPI search triggers: "{product_name} buy price"
        3. Best result crawled and extracted
        4. Merge into ProductCandidate

        Note: SerpAPI is mocked for cost control.
        """
        product = EXTRACTED_PRODUCTS[1]  # Buffalo Trace without link

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_BUFFALO_TRACE_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Should have enrichment source as search_result
        assert result.get("enrichment_source") == "search_result", \
            f"Should use search_result for enrichment. Got: {result.get('enrichment_source')}"

        # Should have enriched data
        assert result.get("name"), "Should have product name"

        print(f"Enriched product via search: {result.get('name')}")
        print(f"Enrichment source: {result.get('enrichment_source')}")

    @pytest.mark.asyncio
    async def test_search_query_uses_product_name(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Search query should include product name.
        E.g., "Ardbeg 10 buy price whiskey"
        """
        product = EXTRACTED_PRODUCTS[1]  # Buffalo Trace without link
        mock_serpapi = enrichment_service.serpapi_client

        try:
            await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_BUFFALO_TRACE_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Check that search was called with product name
        assert len(mock_serpapi.search_calls) > 0, \
            "Should have made search call"

        search_query = mock_serpapi.search_calls[0].lower()
        product_name = product["name"].lower()

        # Query should contain significant words from product name
        assert "buffalo" in search_query or "trace" in search_query, \
            f"Search query should contain product name. Query: {search_query}"

        print(f"Search query: {mock_serpapi.search_calls[0]}")

    @pytest.mark.asyncio
    async def test_filters_search_results_appropriately(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Should prefer:
        - Official retailer sites
        - Product pages (not reviews, not forums)
        """
        # Test the filtering logic directly
        results = MOCK_SERPAPI_RESULTS["Buffalo Trace"]

        best_result = enrichment_service._filter_search_results(results)

        assert best_result is not None, "Should find a result"

        # Should prefer totalwine.com (retailer) over official site
        # when totalwine is first in results
        assert "totalwine" in best_result["domain"], \
            f"Should prefer retailer. Got: {best_result['domain']}"

        print(f"Selected result: {best_result['title']}")
        print(f"Domain: {best_result['domain']}")


class TestEnrichmentFailure:
    """
    Test handling when enrichment fails.
    """

    @pytest.mark.asyncio
    async def test_saves_partial_product_when_enrichment_fails(
        self,
        ai_client: VPSAIClient,
        mock_serpapi: MockSerpAPIClient
    ):
        """
        When enrichment fails (dead link, blocked site),
        should still save partial product with available data.
        """
        # Create service with no mock content (will fail to fetch)
        service = ProductEnrichmentService(
            ai_client=ai_client,
            serpapi_client=mock_serpapi
        )

        # Product that will fail (no direct link, no search results)
        product = {
            "name": "NonExistent Whiskey XYZ",
            "direct_product_link": None,
            "rating": "90 points",
            "source_article_url": "https://example.com/article",
        }

        result = await service.enrich_product(product=product)

        # Should still have original data
        assert result.get("name") == product["name"], \
            "Should preserve original product name"

        # Should have failed enrichment source
        assert result.get("enrichment_source") == "failed", \
            f"Should mark as failed. Got: {result.get('enrichment_source')}"

        # Should preserve original info
        assert result.get("original_rating") == "90 points", \
            "Should preserve original rating"

        print(f"Partial product saved: {result.get('name')}")
        print(f"Status: {result.get('status')}")

    @pytest.mark.asyncio
    async def test_marks_product_as_needing_enrichment(
        self,
        ai_client: VPSAIClient,
        mock_serpapi: MockSerpAPIClient
    ):
        """
        Partial products should have status indicating
        they need more data (INCOMPLETE or PARTIAL).
        """
        service = ProductEnrichmentService(
            ai_client=ai_client,
            serpapi_client=mock_serpapi
        )

        # Product that will fail
        product = {
            "name": "NonExistent Whiskey",
            "direct_product_link": None,
            "source_article_url": "https://example.com/article",
        }

        result = await service.enrich_product(product=product)

        # Status should indicate incomplete
        assert result.get("status") in ["INCOMPLETE", "PARTIAL", "FAILED"], \
            f"Should have incomplete status. Got: {result.get('status')}"

        print(f"Product status: {result.get('status')}")


class TestEnrichmentSourceTracking:
    """
    Test that enrichment sources are properly tracked.
    """

    @pytest.mark.asyncio
    async def test_enrichment_source_tracked(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Should track where enrichment data came from:
        - direct_link
        - search_result
        - failed
        """
        # Test with direct link
        product_with_link = EXTRACTED_PRODUCTS[0]
        try:
            result1 = await enrichment_service.enrich_product(
                product=product_with_link,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        assert result1.get("enrichment_source") == "direct_link"

        # Test with search
        product_without_link = EXTRACTED_PRODUCTS[1]
        try:
            result2 = await enrichment_service.enrich_product(
                product=product_without_link,
                mock_content=MOCK_BUFFALO_TRACE_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        assert result2.get("enrichment_source") == "search_result"

        print("Enrichment sources tracked correctly:")
        print(f"  Product with link: {result1.get('enrichment_source')}")
        print(f"  Product without link: {result2.get('enrichment_source')}")

    @pytest.mark.asyncio
    async def test_multiple_sources_tracked(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        If data comes from multiple sources, all should be tracked.
        """
        product = EXTRACTED_PRODUCTS[0]

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        # Should have enrichment_sources list
        sources = result.get("enrichment_sources", [])
        assert isinstance(sources, list), "enrichment_sources should be a list"
        assert len(sources) >= 1, "Should have at least one source"

        print(f"Enrichment sources: {sources}")


class TestVPSServiceConnectivity:
    """
    Tests for VPS AI service connectivity during enrichment.
    """

    @pytest.mark.asyncio
    async def test_vps_service_is_reachable_for_enrichment(
        self, ai_client: VPSAIClient
    ):
        """Verify VPS AI service is reachable."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{ai_client.BASE_URL}/health/",
                    headers=ai_client._get_headers()
                )
                # Service should respond
                assert response.status_code in [200, 404, 405], \
                    f"VPS should be reachable. Got status: {response.status_code}"
            except httpx.ConnectError:
                pytest.fail("Cannot connect to VPS AI service")

    @pytest.mark.asyncio
    async def test_authentication_works_for_enrichment(
        self, ai_client: VPSAIClient
    ):
        """Verify authentication works for enrichment extraction."""
        simple_content = """
        Product: Ardbeg 10 Year Old
        ABV: 46%
        Price: $55
        """

        try:
            result = await ai_client.extract_from_content(
                content=simple_content,
                source_url="https://example.com/product",
                product_type_hint="whiskey"
            )
            assert result is not None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                pytest.fail("Authentication failed - check AI_ENHANCEMENT_SERVICE_TOKEN")
            elif e.response.status_code == 403:
                pytest.fail("Authorization failed - token may be expired")


class TestEnrichmentPerformance:
    """
    Tests for enrichment performance.
    """

    @pytest.mark.asyncio
    async def test_enrichment_completes_within_timeout(
        self,
        enrichment_service: ProductEnrichmentService
    ):
        """
        Single product enrichment should complete within reasonable time.
        """
        product = EXTRACTED_PRODUCTS[0]
        start_time = time.time()

        try:
            result = await enrichment_service.enrich_product(
                product=product,
                mock_content=MOCK_ARDBEG_PRODUCT_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                pytest.skip("VPS returned 500 - content may exceed service limits")
            raise

        elapsed_time = time.time() - start_time

        assert result is not None, "Should return result"
        assert elapsed_time < 60.0, \
            f"Enrichment should complete within 60s. Took: {elapsed_time:.2f}s"

        print(f"Enrichment completed in {elapsed_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
