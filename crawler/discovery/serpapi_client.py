"""
SerpAPI Client - Google Search API integration for brand discovery.

Queries SerpAPI to find official producer websites when direct links
are not available from hub pages.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cost per search in cents (SerpAPI pricing: $75/month for 5000 searches = 1.5 cents each)
SERPAPI_COST_PER_SEARCH_CENTS = 2  # Rounded up for safety


@dataclass
class SearchResult:
    """A search result from SerpAPI."""

    url: str
    domain: str
    title: str
    snippet: str
    position: int
    is_likely_official: bool = False


class SerpAPIClient:
    """
    Client for SerpAPI Google Search API.

    Used to find official producer websites when hub pages don't provide
    direct external links.
    """

    BASE_URL = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize SerpAPI client.

        Args:
            api_key: SerpAPI API key (defaults to settings.SERPAPI_API_KEY)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or getattr(settings, "SERPAPI_API_KEY", "")
        self.timeout = timeout

        if not self.api_key:
            logger.warning("SerpAPI API key not configured")

    def build_brand_query(self, brand_name: str) -> str:
        """
        Build a search query to find the official site for a brand.

        Args:
            brand_name: Name of the brand/producer

        Returns:
            Search query string optimized for finding official sites
        """
        # Query format optimized for finding official producer sites
        return f"{brand_name} official site whisky whiskey distillery"

    async def search_brand_official_site(
        self,
        brand_name: str,
        crawl_job=None,
    ) -> Optional[SearchResult]:
        """
        Search for a brand's official website.

        Args:
            brand_name: Name of the brand to search for
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            SearchResult for the likely official site, or None if not found
        """
        query = self.build_brand_query(brand_name)
        results = await self.search(query, crawl_job=crawl_job)

        if not results:
            return None

        # Analyze results to find the official site
        return self._identify_official_site(results, brand_name)

    async def search(
        self,
        query: str,
        num_results: int = 10,
        crawl_job=None,
    ) -> List[SearchResult]:
        """
        Execute a Google search via SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to request
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            logger.error("Cannot search: SerpAPI API key not configured")
            return []

        params = {
            "api_key": self.api_key,
            "engine": "google",
            "q": query,
            "num": num_results,
            "hl": "en",
            "gl": "us",
        }

        try:
            response_data = await self._make_request(params)

            # Track cost
            await self._track_cost(crawl_job)

            # Parse results
            return self._parse_results(response_data)

        except Exception as e:
            logger.error(f"SerpAPI search failed for query '{query}': {e}")
            return []

    async def _make_request(self, params: dict) -> dict:
        """Make HTTP request to SerpAPI."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()

    def _parse_results(self, response_data: dict) -> List[SearchResult]:
        """Parse SerpAPI response into SearchResult objects."""
        results = []
        organic_results = response_data.get("organic_results", [])

        for item in organic_results:
            url = item.get("link", "")
            if not url:
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")

            results.append(SearchResult(
                url=url,
                domain=domain,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                position=item.get("position", 0),
            ))

        return results

    def _identify_official_site(
        self,
        results: List[SearchResult],
        brand_name: str,
    ) -> Optional[SearchResult]:
        """
        Identify the most likely official site from search results.

        Uses heuristics:
        1. Domain contains brand name (or close match)
        2. Title contains "official"
        3. Position in search results (higher = more likely)
        4. Exclude known retailers and aggregators
        """
        brand_lower = brand_name.lower().replace(" ", "").replace("'", "")

        # Known domains to exclude (retailers, aggregators, etc.)
        exclude_domains = [
            "thewhiskyexchange.com",
            "masterofmalt.com",
            "whiskybase.com",
            "drinksupermarket.com",
            "amazon.com",
            "amazon.co.uk",
            "ebay.com",
            "ebay.co.uk",
            "wine-searcher.com",
            "vivino.com",
            "totalwine.com",
            "klwines.com",
            "caskers.com",
            "reservebar.com",
            "drizly.com",
            "facebook.com",
            "twitter.com",
            "instagram.com",
            "linkedin.com",
            "youtube.com",
            "wikipedia.org",
            "reddit.com",
        ]

        for result in results:
            # Skip excluded domains
            if any(excluded in result.domain for excluded in exclude_domains):
                continue

            # Check if domain contains brand name
            domain_clean = result.domain.replace("-", "").replace(".", "")
            brand_in_domain = brand_lower in domain_clean

            # Check if title indicates official site
            title_lower = result.title.lower()
            is_official_title = any(
                indicator in title_lower
                for indicator in ["official", "home", "welcome to"]
            )

            # Check snippet for official indicators
            snippet_lower = result.snippet.lower()
            is_official_snippet = any(
                indicator in snippet_lower
                for indicator in ["official", "our distillery", "our whisky", "visit us"]
            )

            # Score the result
            if brand_in_domain:
                result.is_likely_official = True
                return result

            if is_official_title or is_official_snippet:
                result.is_likely_official = True
                return result

        # If no clear match, return first non-excluded result with position <= 3
        for result in results[:3]:
            if not any(excluded in result.domain for excluded in exclude_domains):
                return result

        return None

    async def _track_cost(self, crawl_job) -> None:
        """Track API cost in CrawlCost model."""
        try:
            from crawler.models import CrawlCost, CostService
            from asgiref.sync import sync_to_async

            @sync_to_async
            def create_cost():
                CrawlCost.objects.create(
                    service=CostService.SERPAPI,
                    cost_cents=SERPAPI_COST_PER_SEARCH_CENTS,
                    crawl_job=crawl_job,
                    request_count=1,
                    timestamp=timezone.now(),
                )

            await create_cost()
            logger.debug("Tracked SerpAPI cost")

        except Exception as e:
            # Don't fail the search if cost tracking fails
            logger.warning(f"Failed to track SerpAPI cost: {e}")
