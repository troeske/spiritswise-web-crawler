"""
Enrichment Searcher - SerpAPI triple search for skeleton product enrichment.

For each skeleton product, triggers 3 SerpAPI searches:
1. "{Product Name} price buy online" - Find retail sources
2. "{Product Name} review tasting notes" - Find review content
3. "{Product Name} official site" - Find producer website

Discovered URLs are queued with priority=10 (highest) for immediate processing.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from crawler.discovery.serpapi_client import SerpAPIClient, SearchResult

logger = logging.getLogger(__name__)

# Priority level for URLs discovered through skeleton enrichment
ENRICHMENT_PRIORITY = 10  # Highest priority


@dataclass
class EnrichmentSearchResult:
    """Result from an enrichment search."""

    url: str
    domain: str
    title: str
    snippet: str
    search_type: str  # "price", "review", "official"
    priority: int = ENRICHMENT_PRIORITY
    product_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "snippet": self.snippet,
            "search_type": self.search_type,
            "priority": self.priority,
            "product_name": self.product_name,
        }


class EnrichmentSearcher:
    """
    Searcher for enriching skeleton products via SerpAPI.

    Triggers 3 targeted searches per skeleton product to find:
    - Retail/pricing information
    - Reviews and tasting notes
    - Official producer website
    """

    # Search query templates
    SEARCH_TEMPLATES = {
        "price": "{product_name} price buy online",
        "review": "{product_name} review tasting notes",
        "official": "{product_name} official site",
    }

    # Domains to exclude from results (aggregators, social media, etc.)
    EXCLUDE_DOMAINS = [
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "linkedin.com",
        "youtube.com",
        "pinterest.com",
        "reddit.com",
        "wikipedia.org",
        "amazon.com",
        "amazon.co.uk",
        "ebay.com",
        "ebay.co.uk",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        results_per_search: int = 5,
    ):
        """
        Initialize enrichment searcher.

        Args:
            api_key: SerpAPI API key (defaults to settings.SERPAPI_API_KEY)
            results_per_search: Number of results per search query
        """
        self.serpapi_client = SerpAPIClient(api_key=api_key)
        self.results_per_search = results_per_search

    async def search_for_enrichment(
        self,
        product_name: str,
        crawl_job=None,
    ) -> List[Dict[str, Any]]:
        """
        Execute triple search for skeleton product enrichment.

        Args:
            product_name: Name of the product to search for
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            List of enrichment search results with priority=10
        """
        all_results = []
        seen_urls = set()

        for search_type, template in self.SEARCH_TEMPLATES.items():
            query = template.format(product_name=product_name)

            try:
                results = await self.serpapi_client.search(
                    query=query,
                    num_results=self.results_per_search,
                    crawl_job=crawl_job,
                )

                for result in results:
                    # Skip excluded domains
                    if self._is_excluded_domain(result.domain):
                        continue

                    # Skip duplicate URLs
                    if result.url in seen_urls:
                        continue

                    seen_urls.add(result.url)

                    enrichment_result = EnrichmentSearchResult(
                        url=result.url,
                        domain=result.domain,
                        title=result.title,
                        snippet=result.snippet,
                        search_type=search_type,
                        priority=ENRICHMENT_PRIORITY,
                        product_name=product_name,
                    )

                    all_results.append(enrichment_result.to_dict())

            except Exception as e:
                logger.error(
                    f"Enrichment search failed for '{product_name}' ({search_type}): {e}"
                )
                continue

        logger.info(
            f"Enrichment search for '{product_name}' found {len(all_results)} URLs"
        )

        return all_results

    async def search_multiple_skeletons(
        self,
        product_names: List[str],
        crawl_job=None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute enrichment searches for multiple skeleton products.

        Args:
            product_names: List of product names to search for
            crawl_job: Optional CrawlJob for cost tracking

        Returns:
            Dictionary mapping product names to their search results
        """
        results = {}

        for product_name in product_names:
            try:
                search_results = await self.search_for_enrichment(
                    product_name=product_name,
                    crawl_job=crawl_job,
                )
                results[product_name] = search_results
            except Exception as e:
                logger.error(f"Failed to search for '{product_name}': {e}")
                results[product_name] = []

        return results

    def _is_excluded_domain(self, domain: str) -> bool:
        """Check if domain should be excluded from results."""
        domain_lower = domain.lower()
        return any(excluded in domain_lower for excluded in self.EXCLUDE_DOMAINS)

    def build_query(self, product_name: str, search_type: str) -> str:
        """
        Build a search query for a specific search type.

        Args:
            product_name: Product name to search for
            search_type: Type of search ("price", "review", "official")

        Returns:
            Formatted search query string
        """
        template = self.SEARCH_TEMPLATES.get(search_type, "{product_name}")
        return template.format(product_name=product_name)

    def categorize_result(
        self,
        result: SearchResult,
        search_type: str,
    ) -> Dict[str, Any]:
        """
        Categorize a search result based on domain and content.

        Args:
            result: SearchResult from SerpAPI
            search_type: Type of search that produced this result

        Returns:
            Dictionary with categorization metadata
        """
        category = "unknown"
        domain = result.domain.lower()
        title = result.title.lower()
        snippet = result.snippet.lower()

        # Categorize by domain patterns
        retailer_domains = [
            "thewhiskyexchange.com",
            "masterofmalt.com",
            "whiskybase.com",
            "totalwine.com",
            "klwines.com",
            "drizly.com",
            "reservebar.com",
            "caskers.com",
            "wine-searcher.com",
        ]

        review_domains = [
            "whiskyadvocate.com",
            "whisky.com",
            "thewhiskeywash.com",
            "maltwhiskyreviews.com",
            "breakingbourbon.com",
        ]

        if any(rd in domain for rd in retailer_domains):
            category = "retailer"
        elif any(rd in domain for rd in review_domains):
            category = "review"
        elif "official" in title or "official" in snippet:
            category = "official"
        elif search_type == "price":
            # Check for price indicators
            if any(word in title + snippet for word in ["buy", "shop", "price", "$", "cart"]):
                category = "retailer"
        elif search_type == "review":
            if any(word in title + snippet for word in ["review", "tasting", "notes", "rating"]):
                category = "review"
        elif search_type == "official":
            # First result for official search is often the official site
            category = "potential_official"

        return {
            "url": result.url,
            "domain": result.domain,
            "category": category,
            "search_type": search_type,
        }


async def enrich_skeleton_from_competition(
    skeleton,
    searcher: Optional[EnrichmentSearcher] = None,
    crawl_job=None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to enrich a skeleton product.

    Args:
        skeleton: DiscoveredProduct with status='skeleton'
        searcher: Optional EnrichmentSearcher instance
        crawl_job: Optional CrawlJob for cost tracking

    Returns:
        List of discovered URLs for queuing
    """
    if searcher is None:
        searcher = EnrichmentSearcher()

    product_name = skeleton.extracted_data.get("name", "")
    if not product_name:
        logger.warning(f"Skeleton {skeleton.id} has no product name")
        return []

    return await searcher.search_for_enrichment(
        product_name=product_name,
        crawl_job=crawl_job,
    )
