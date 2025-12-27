"""
Hub Crawler - Orchestrates crawling of retailer hub pages.

Coordinates the discovery workflow:
1. Fetch hub pages using Smart Router
2. Parse brand listings
3. Search SerpAPI for official sites when needed
4. Register discovered sources
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from django.utils import timezone

from .hub_parser import HubPageParser, BrandInfo
from .serpapi_client import SerpAPIClient
from .spoke_registry import SpokeRegistry

logger = logging.getLogger(__name__)


@dataclass
class HubDefinition:
    """Definition of a hub site to crawl."""

    name: str
    url: str
    domain: str


# Pre-defined hub sites for whiskey discovery
WHISKEY_HUBS = [
    HubDefinition(
        name="The Whisky Exchange - Brands",
        url="https://www.thewhiskyexchange.com/brands",
        domain="thewhiskyexchange.com",
    ),
    HubDefinition(
        name="Master of Malt - Distilleries",
        url="https://www.masterofmalt.com/distilleries/",
        domain="masterofmalt.com",
    ),
    HubDefinition(
        name="Whiskybase - Distilleries",
        url="https://www.whiskybase.com/whiskies/distilleries",
        domain="whiskybase.com",
    ),
]


@dataclass
class DiscoveryResult:
    """Result of hub discovery for a single brand."""

    brand_name: str
    hub_source: str
    official_url: Optional[str] = None
    source_created: bool = False
    error: Optional[str] = None


class HubCrawler:
    """
    Orchestrates the Hub & Spoke discovery process.

    Crawls retailer hub pages to discover brands, then uses SerpAPI
    to find official producer websites when not directly linked.
    """

    def __init__(
        self,
        smart_router=None,
        serpapi_client: Optional[SerpAPIClient] = None,
        spoke_registry: Optional[SpokeRegistry] = None,
        parser: Optional[HubPageParser] = None,
    ):
        """
        Initialize hub crawler.

        Args:
            smart_router: SmartRouter instance for fetching pages
            serpapi_client: SerpAPIClient for searching official sites
            spoke_registry: SpokeRegistry for registering discovered sources
            parser: HubPageParser for parsing brand listings
        """
        self.smart_router = smart_router
        self.serpapi_client = serpapi_client or SerpAPIClient()
        self.spoke_registry = spoke_registry or SpokeRegistry()
        self.parser = parser or HubPageParser()

    async def crawl_hub(
        self,
        hub: HubDefinition,
        crawl_job=None,
        max_pages: int = 10,
        use_serpapi: bool = True,
    ) -> List[DiscoveryResult]:
        """
        Crawl a single hub site to discover brands.

        Args:
            hub: Hub definition to crawl
            crawl_job: Optional CrawlJob for tracking
            max_pages: Maximum pagination pages to crawl
            use_serpapi: Whether to use SerpAPI for brands without direct links

        Returns:
            List of DiscoveryResult for each discovered brand
        """
        logger.info(f"Starting hub crawl: {hub.name}")
        results = []

        try:
            # Fetch the hub page
            brands = await self._fetch_and_parse_hub(
                hub=hub,
                crawl_job=crawl_job,
                max_pages=max_pages,
            )

            logger.info(f"Discovered {len(brands)} brands from {hub.name}")

            # Process each brand
            for brand in brands:
                result = await self._process_brand(
                    brand=brand,
                    crawl_job=crawl_job,
                    use_serpapi=use_serpapi,
                )
                results.append(result)

        except Exception as e:
            logger.error(f"Hub crawl failed for {hub.name}: {e}")

        return results

    async def crawl_all_hubs(
        self,
        crawl_job=None,
        max_pages_per_hub: int = 10,
        use_serpapi: bool = True,
    ) -> List[DiscoveryResult]:
        """
        Crawl all configured whiskey hub sites.

        Args:
            crawl_job: Optional CrawlJob for tracking
            max_pages_per_hub: Maximum pagination pages per hub
            use_serpapi: Whether to use SerpAPI for brands without direct links

        Returns:
            Combined list of DiscoveryResult from all hubs
        """
        all_results = []

        for hub in WHISKEY_HUBS:
            hub_results = await self.crawl_hub(
                hub=hub,
                crawl_job=crawl_job,
                max_pages=max_pages_per_hub,
                use_serpapi=use_serpapi,
            )
            all_results.extend(hub_results)

        logger.info(f"Total brands discovered from all hubs: {len(all_results)}")
        return all_results

    async def _fetch_and_parse_hub(
        self,
        hub: HubDefinition,
        crawl_job,
        max_pages: int,
    ) -> List[BrandInfo]:
        """Fetch hub pages and parse brand listings."""
        all_brands = []
        urls_to_crawl = [hub.url]
        crawled_urls = set()
        page_count = 0

        while urls_to_crawl and page_count < max_pages:
            url = urls_to_crawl.pop(0)
            if url in crawled_urls:
                continue

            crawled_urls.add(url)
            page_count += 1

            # Fetch the page
            content = await self._fetch_page(url, crawl_job)
            if not content:
                continue

            # Parse brands
            brands = self.parser.parse_brands(
                html=content,
                hub_url=url,
            )
            all_brands.extend(brands)

            # Extract pagination links
            if page_count < max_pages:
                pagination_links = self.parser.extract_pagination_links(
                    html=content,
                    hub_url=url,
                )
                for link in pagination_links:
                    if link not in crawled_urls and link not in urls_to_crawl:
                        urls_to_crawl.append(link)

        return all_brands

    async def _fetch_page(
        self,
        url: str,
        crawl_job,
    ) -> Optional[str]:
        """Fetch a page using Smart Router if available."""
        if self.smart_router:
            result = await self.smart_router.fetch(
                url=url,
                crawl_job=crawl_job,
            )
            if result.success:
                return result.content
            else:
                logger.warning(f"Failed to fetch {url}: {result.error}")
                return None
        else:
            # Fallback to simple httpx fetch
            import httpx
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    return response.text
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                return None

    async def _process_brand(
        self,
        brand: BrandInfo,
        crawl_job,
        use_serpapi: bool,
    ) -> DiscoveryResult:
        """Process a discovered brand."""
        result = DiscoveryResult(
            brand_name=brand.name,
            hub_source=brand.hub_source,
        )

        try:
            # Check if we have an external URL from the hub
            official_url = brand.external_url

            # If no direct link and SerpAPI enabled, search for it
            if not official_url and use_serpapi:
                search_result = await self.serpapi_client.search_brand_official_site(
                    brand_name=brand.name,
                    crawl_job=crawl_job,
                )
                if search_result:
                    official_url = search_result.url

            result.official_url = official_url

            # Register the source if we found an official URL
            if official_url:
                source = await self.spoke_registry.register_spoke_async(
                    name=brand.name,
                    base_url=official_url,
                    discovered_from_hub=brand.hub_source,
                )
                result.source_created = source is not None

        except Exception as e:
            result.error = str(e)
            logger.error(f"Error processing brand {brand.name}: {e}")

        return result
