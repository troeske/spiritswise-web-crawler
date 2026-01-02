"""
Discovery Orchestrator - Automated product discovery from search results.

Phase 3: Generic Search Discovery Flow
Implements the core orchestration logic for discovering products using
configurable search terms and the SmartCrawler extraction pipeline.
"""

import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from django.db.models import Q
from django.utils import timezone

from crawler.models import (
    SearchTerm,
    CrawlSchedule,
    DiscoveryJob,
    DiscoveryResult,
    DiscoveredProduct,
    ProductSource,
    DiscoveryJobStatus,
    DiscoveryResultStatus,
)

logger = logging.getLogger(__name__)


class SerpAPIClient:
    """Client for Google Search API via SerpAPI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        if not self.api_key:
            logger.warning("SERPAPI_KEY not set - searches will fail")

    def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Execute a Google search via SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to request

        Returns:
            Dict with organic_results list
        """
        try:
            import requests

            params = {
                "api_key": self.api_key,
                "engine": "google",
                "q": query,
                "num": num_results,
            }

            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            raise


class DiscoveryOrchestrator:
    """
    Orchestrates the product discovery process.

    Flow:
    1. Load active search terms based on schedule
    2. For each term, execute SerpAPI search
    3. Parse results to identify product pages
    4. For each product page:
       a. Check if product already exists (dedup)
       b. If new, use SmartCrawler to extract
       c. If existing, check if update needed
    5. Save results and update metrics
    """

    # Domains to skip (social media, general news, etc.)
    SKIP_DOMAINS = {
        # Social media
        "facebook.com", "twitter.com", "instagram.com", "youtube.com",
        "tiktok.com", "pinterest.com", "linkedin.com", "reddit.com",
        # General news
        "cnn.com", "bbc.com", "nytimes.com", "theguardian.com",
        "washingtonpost.com", "usatoday.com", "foxnews.com",
        # Shopping aggregators (not product pages)
        "amazon.com", "ebay.com", "walmart.com",
        # Other
        "wikipedia.org", "yelp.com",
    }

    # Known retailer domains
    RETAILER_DOMAINS = {
        "masterofmalt.com", "thewhiskyexchange.com", "totalwine.com",
        "wine.com", "drizly.com", "reservebar.com", "caskers.com",
        "flaviar.com", "klwines.com", "wine-searcher.com",
        "dekanta.com", "whiskyshop.com", "finedrams.com",
    }

    # Known review/list sites
    REVIEW_DOMAINS = {
        "whiskyadvocate.com", "vinepair.com", "whiskymagazine.com",
        "diffordsguide.com", "liquor.com", "tastingtable.com",
        "thespruceeats.com", "winemag.com", "decanter.com",
    }

    def __init__(
        self,
        schedule: Optional[CrawlSchedule] = None,
        serpapi_client: Optional[SerpAPIClient] = None,
        smart_crawler=None,
    ):
        """
        Initialize the orchestrator.

        Args:
            schedule: Optional schedule that triggered this run
            serpapi_client: Optional SerpAPI client (creates default if not provided)
            smart_crawler: Optional SmartCrawler instance
        """
        self.schedule = schedule
        self.serpapi_client = serpapi_client or SerpAPIClient()
        self.job: Optional[DiscoveryJob] = None

        # Initialize SmartCrawler
        if smart_crawler:
            self.smart_crawler = smart_crawler
        else:
            self._init_smart_crawler()

    def _init_smart_crawler(self):
        """Initialize SmartCrawler with default clients."""
        try:
            from crawler.services.smart_crawler import create_smart_crawler
            from crawler.tests.integration.scrapingbee_client import ScrapingBeeClient
            from crawler.tests.integration.ai_service_client import AIEnhancementClient

            scrapingbee = ScrapingBeeClient()
            ai_service = AIEnhancementClient()
            self.smart_crawler = create_smart_crawler(scrapingbee, ai_service)
        except ImportError as e:
            logger.warning(f"Could not initialize SmartCrawler: {e}")
            self.smart_crawler = None

    def run(self) -> DiscoveryJob:
        """
        Execute a discovery run.

        Returns:
            The completed DiscoveryJob
        """
        # Create job
        self.job = DiscoveryJob.objects.create(
            crawl_schedule=self.schedule,
            status=DiscoveryJobStatus.RUNNING,
        )

        try:
            # Get search terms
            terms = self._get_search_terms()
            self.job.search_terms_total = len(terms)
            self.job.save()

            # Process each term
            for term in terms:
                self._process_search_term(term)
                self.job.search_terms_processed += 1
                self.job.save()

            # Complete job
            self.job.status = DiscoveryJobStatus.COMPLETED
            self.job.completed_at = timezone.now()
            self.job.save()

        except Exception as e:
            logger.error(f"Discovery job failed: {e}")
            self.job.status = DiscoveryJobStatus.FAILED
            self.job.log_error(str(e))
            self.job.save()
            raise

        return self.job

    def _get_search_terms(self) -> List[SearchTerm]:
        """
        Get active search terms for this run.

        Filters by:
        - is_active = True
        - Schedule's category filters (if any)
        - Schedule's product type filters (if any)
        - Seasonal availability

        Returns:
            List of SearchTerm objects to process
        """
        terms = SearchTerm.objects.filter(is_active=True)

        # Apply schedule filters if we have a schedule
        if self.schedule:
            # Category filter
            if self.schedule.search_categories:
                terms = terms.filter(category__in=self.schedule.search_categories)

            # Product type filter
            if self.schedule.product_types:
                terms = terms.filter(product_type__in=self.schedule.product_types)

        # Filter seasonal terms
        terms = [t for t in terms if self._is_term_in_season(t)]

        # Order by priority (higher value = higher priority)
        terms = sorted(terms, key=lambda t: -t.priority)

        # Apply limit
        max_terms = self.schedule.max_search_terms if self.schedule else 20
        return terms[:max_terms]

    def _is_term_in_season(self, term: SearchTerm) -> bool:
        """Check if a seasonal term is currently in season."""
        if not term.seasonal_start_month or not term.seasonal_end_month:
            return True  # Non-seasonal terms are always in season

        return term.is_in_season()

    def _process_search_term(self, term: SearchTerm):
        """
        Process a single search term.

        Args:
            term: The SearchTerm to process
        """
        query = term.get_search_query()
        logger.info(f"Searching: {query}")

        # Execute search
        results = self._search(query)
        self.job.serpapi_calls_used += 1

        # Get max results limit
        max_results = 10
        if self.schedule:
            max_results = self.schedule.max_results_per_term

        # Process each result
        for rank, result in enumerate(results[:max_results], 1):
            self._process_search_result(term, result, rank)

        # Update term stats
        term.last_searched = timezone.now()
        term.search_count += 1
        term.save()

    def _search(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a search query via SerpAPI.

        Args:
            query: The search query

        Returns:
            List of organic results
        """
        response = self.serpapi_client.search(query)
        return response.get("organic_results", [])

    def _process_search_result(
        self,
        term: SearchTerm,
        result: Dict[str, Any],
        rank: int,
    ):
        """
        Process a single search result.

        Args:
            term: The search term that found this result
            result: The search result dict with 'title' and 'link'
            rank: Position in search results (1 = first)
        """
        url = result.get("link")
        title = result.get("title", "")

        if not url:
            return

        # Check if this is a product URL we should process
        if not self._is_product_url(url, title):
            self.job.urls_skipped += 1
            return

        self.job.urls_found += 1

        # Check if this is a list page (Phase 4)
        if self._is_list_page(url, title):
            self._process_list_page(url, title, term, rank)
            return

        # Create discovery result record for single product page
        domain = self._extract_domain(url)
        discovery_result = DiscoveryResult.objects.create(
            job=self.job,
            search_term=term,
            source_url=url,
            source_domain=domain,
            source_title=title,
            search_rank=rank,
            product_name=title,
            status=DiscoveryResultStatus.PROCESSING,
        )

        # Check for existing product
        existing = self._find_existing_product(url, title)
        if existing:
            discovery_result.product = existing
            discovery_result.is_duplicate = True
            discovery_result.status = DiscoveryResultStatus.DUPLICATE
            discovery_result.save()
            self.job.products_duplicates += 1
            return

        # Extract product using SmartCrawler
        self._extract_and_save_product(term, discovery_result, url, title)

    def _process_list_page(
        self,
        url: str,
        title: str,
        term: SearchTerm,
        rank: int,
    ):
        """
        Process a list page containing multiple products.

        Args:
            url: The list page URL
            title: The page title
            term: The search term
            rank: Search result rank
        """
        logger.info(f"Processing list page: {title}")

        # Fetch page content
        html_content = self._fetch_page_content(url)
        if not html_content:
            logger.warning(f"Failed to fetch list page content: {url}")
            return

        # Extract products from list
        products = self._extract_list_products(url, html_content)
        if not products:
            logger.warning(f"No products found in list page: {url}")
            return

        logger.info(f"Found {len(products)} products in list page")

        # Process each product
        for product_info in products:
            result = self._enrich_product_from_list(product_info, url, term)

            # Track results
            if result.get("is_duplicate"):
                self.job.products_duplicates += 1
            elif result.get("created"):
                self.job.products_new += 1
            elif result.get("partial"):
                # Create a partial product record
                self._create_partial_product(product_info, url, term)

    def _is_product_url(self, url: str, title: str) -> bool:
        """
        Determine if a URL likely leads to product information.

        Args:
            url: The URL to check
            title: The page title from search results

        Returns:
            True if this looks like a product-related URL
        """
        domain = self._extract_domain(url)

        # Skip blocked domains
        if domain in self.SKIP_DOMAINS:
            return False

        # Skip social media subdomains
        for skip in self.SKIP_DOMAINS:
            if skip in domain:
                return False

        # Always process known retailer domains
        if domain in self.RETAILER_DOMAINS:
            return True

        # Always process known review sites
        if domain in self.REVIEW_DOMAINS:
            return True

        # Check for product-like URL patterns
        url_lower = url.lower()
        product_patterns = [
            "/product/", "/products/", "/p/", "/shop/",
            "/whiskey/", "/whisky/", "/bourbon/", "/scotch/",
            "/port/", "/wine/", "/spirits/",
            "/best-", "/top-", "/review/",
        ]
        if any(pattern in url_lower for pattern in product_patterns):
            return True

        # Check title for product indicators
        title_lower = title.lower()
        product_keywords = [
            "whiskey", "whisky", "bourbon", "scotch", "port wine",
            "best", "top 10", "review", "tasting", "year old",
        ]
        if any(keyword in title_lower for keyword in product_keywords):
            return True

        return True  # Default to allowing URLs that aren't explicitly blocked

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL, removing www prefix.

        Args:
            url: The URL to parse

        Returns:
            The domain name without www
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _find_existing_product(
        self,
        url: str,
        name: str,
    ) -> Optional[DiscoveredProduct]:
        """
        Find an existing product by URL or fuzzy name match.

        Args:
            url: The source URL
            name: The product name/title

        Returns:
            Existing DiscoveredProduct if found, None otherwise
        """
        # 1. Check for exact URL match in DiscoveredProduct.source_url
        product = DiscoveredProduct.objects.filter(source_url=url).first()
        if product:
            return product

        # 2. Check CrawledSource -> ProductSource path
        try:
            from crawler.models import CrawledSource
            crawled = CrawledSource.objects.filter(url=url).first()
            if crawled:
                source = ProductSource.objects.filter(source=crawled).first()
                if source and source.product:
                    return source.product
        except Exception:
            pass  # Ignore if CrawledSource lookup fails

        # 3. Fuzzy name match
        # Normalize the name for comparison
        normalized_name = self._normalize_name(name)

        # Search for similar products
        products = DiscoveredProduct.objects.filter(
            name__icontains=normalized_name[:30]  # First 30 chars as rough filter
        )

        for product in products[:10]:  # Limit to avoid too many comparisons
            similarity = self._name_similarity(name, product.name)
            if similarity >= 0.85:
                return product

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize a product name for comparison."""
        # Remove common prefixes/suffixes
        name = name.lower().strip()
        # Remove year patterns
        name = re.sub(r'\b(19|20)\d{2}\b', '', name)
        # Remove extra whitespace
        name = ' '.join(name.split())
        return name

    def _name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two product names.

        Uses simple token overlap for now.

        Args:
            name1: First name
            name2: Second name

        Returns:
            Similarity score 0.0 to 1.0
        """
        tokens1 = set(self._normalize_name(name1).split())
        tokens2 = set(self._normalize_name(name2).split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union) if union else 0.0

    def _extract_and_save_product(
        self,
        term: SearchTerm,
        discovery_result: DiscoveryResult,
        url: str,
        title: str,
    ):
        """
        Extract product data using SmartCrawler and save.

        Args:
            term: The search term
            discovery_result: The DiscoveryResult to update
            url: The URL to crawl
            title: The page title
        """
        if not self.smart_crawler:
            discovery_result.status = DiscoveryResultStatus.FAILED
            discovery_result.error_message = "SmartCrawler not available"
            discovery_result.save()
            self.job.products_failed += 1
            return

        try:
            # Determine product type from search term
            product_type = term.product_type
            if product_type == "both":
                product_type = "whiskey"  # Default

            # Call SmartCrawler
            extraction = self.smart_crawler.extract_product(
                expected_name=title,
                product_type=product_type,
                primary_url=url,
            )

            # Track API calls
            if hasattr(extraction, "scrapingbee_calls"):
                self.job.scrapingbee_calls_used += extraction.scrapingbee_calls
            else:
                self.job.scrapingbee_calls_used += 1

            if hasattr(extraction, "ai_calls"):
                self.job.ai_calls_used += extraction.ai_calls
            else:
                self.job.ai_calls_used += 1

            if extraction.success:
                # Save extracted data
                discovery_result.crawl_success = True
                discovery_result.extraction_success = True
                discovery_result.extracted_data = extraction.data or {}
                discovery_result.final_source_url = extraction.source_url
                discovery_result.source_type = extraction.source_type or ""
                discovery_result.name_match_score = extraction.name_match_score
                discovery_result.needs_review = extraction.needs_review
                discovery_result.status = DiscoveryResultStatus.SUCCESS

                # Create or update product
                product = self._save_product(extraction.data, url)
                if product:
                    discovery_result.product = product
                    discovery_result.is_new_product = True
                    term.products_discovered += 1
                    self.job.products_new += 1
                else:
                    self.job.products_updated += 1

                self.job.urls_crawled += 1

            else:
                discovery_result.status = DiscoveryResultStatus.FAILED
                discovery_result.error_message = "; ".join(extraction.errors or [])
                self.job.products_failed += 1

            discovery_result.save()

        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            discovery_result.status = DiscoveryResultStatus.FAILED
            discovery_result.error_message = str(e)
            discovery_result.save()
            self.job.products_failed += 1
            self.job.error_count += 1

    def _save_product(
        self,
        data: Dict[str, Any],
        source_url: str,
    ) -> Optional[DiscoveredProduct]:
        """
        Save extracted product data to database.

        Args:
            data: Extracted product data
            source_url: URL where product was found

        Returns:
            Created DiscoveredProduct or None if update
        """
        if not data:
            return None

        name = data.get("name", "Unknown")
        brand_name = data.get("brand", "")

        # Check for existing product with same name
        existing = DiscoveredProduct.objects.filter(
            name__iexact=name,
        ).first()

        if existing:
            return None  # Indicates update, not new

        # Create new product (without brand FK for simplicity in discovery)
        product = DiscoveredProduct.objects.create(
            name=name,
            product_type=data.get("product_type", "whiskey"),
            source_url=source_url,
            status="pending",
            extracted_data=data,
        )

        return product

    def _merge_product(
        self,
        existing: DiscoveredProduct,
        new_url: str,
        new_data: Dict[str, Any],
    ):
        """
        Merge new data into an existing product.

        Args:
            existing: The existing product
            new_url: New source URL to add
            new_data: New data to potentially merge
        """
        # TODO: Implement data merging logic
        # For now, we could potentially update extracted_data
        # or add to a list of alternative source URLs
        pass

    # =========================================================================
    # Phase 4: Multi-Product Extraction Methods
    # =========================================================================

    # URL patterns that indicate list pages
    LIST_URL_PATTERNS = [
        r"/best-", r"/top-\d+", r"/\d+-best", r"best.*\d{4}",
        r"/picks/", r"/favorites/", r"/gift-guide",
        r"/ranking", r"/awards", r"/winners",
    ]

    # Title patterns that indicate list pages
    LIST_TITLE_PATTERNS = [
        r"\bbest\b.*\bwhisk", r"\bbest\b.*\bport",
        r"\btop\s+\d+\b", r"\d+\s+best\b",
        r"\bour\s+picks\b", r"\bfavorite\b",
        r"\bgift\s+guide\b", r"\bultimate\s+guide\b",
    ]

    def _is_list_page(self, url: str, title: str) -> bool:
        """
        Determine if a URL/title indicates a list page with multiple products.

        Args:
            url: The page URL
            title: The page title

        Returns:
            True if this appears to be a list page
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # Check URL patterns
        for pattern in self.LIST_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return True

        # Check title patterns
        for pattern in self.LIST_TITLE_PATTERNS:
            if re.search(pattern, title_lower):
                return True

        # Check for common list indicators in title
        list_keywords = ["best", "top 10", "top 15", "top 20", "picks", "favorites", "ranking"]
        if any(kw in title_lower for kw in list_keywords):
            # Make sure it's not a single product review that mentions "best"
            product_patterns = [r"/product/", r"/p/\d+", r"/shop/"]
            if not any(re.search(p, url_lower) for p in product_patterns):
                return True

        return False

    def _classify_list_type(self, url: str, title: str) -> str:
        """
        Classify the type of list page.

        Args:
            url: The page URL
            title: The page title

        Returns:
            List type: "best_of", "top_n", "gift_guide", "ranking", or "other"
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # Check for "top N" pattern
        if re.search(r"\btop\s+\d+\b", title_lower) or re.search(r"/top-\d+", url_lower):
            return "top_n"

        # Check for gift guide
        if "gift" in title_lower or "gift-guide" in url_lower:
            return "gift_guide"

        # Check for ranking/awards
        if "ranking" in title_lower or "award" in title_lower:
            return "ranking"

        # Default to "best of"
        if "best" in title_lower:
            return "best_of"

        return "other"

    def _estimate_list_size(self, title: str) -> Optional[int]:
        """
        Estimate the number of products in a list from the title.

        Args:
            title: The page title

        Returns:
            Estimated number of products, or None if not determinable
        """
        # Look for patterns like "Top 10", "15 Best", "20 Must-Try"
        patterns = [
            r"\btop\s+(\d+)\b",
            r"(\d+)\s+best\b",
            r"\bthe\s+(\d+)\s+best\b",
            r"\bour\s+(\d+)\b",
        ]

        title_lower = title.lower()
        for pattern in patterns:
            match = re.search(pattern, title_lower)
            if match:
                return int(match.group(1))

        return None

    def _fetch_page_content(self, url: str) -> str:
        """
        Fetch HTML content from a URL using ScrapingBee.

        Args:
            url: The URL to fetch

        Returns:
            HTML content string
        """
        if not self.smart_crawler:
            return ""

        try:
            # Use the existing crawl capability
            from crawler.services.smart_crawler import SmartCrawler

            if hasattr(self.smart_crawler, "scrapingbee_client"):
                response = self.smart_crawler.scrapingbee_client.get(url)
                if hasattr(response, "content"):
                    return response.content.decode("utf-8", errors="ignore")
                return str(response)
        except Exception as e:
            logger.warning(f"Failed to fetch page content: {e}")

        return ""

    def _call_ai_list_extraction(
        self,
        html_content: str,
        url: str,
    ) -> Dict[str, Any]:
        """
        Call AI service to extract product list from HTML.

        Args:
            html_content: The HTML content
            url: The source URL

        Returns:
            Dict with 'products' list and metadata
        """
        if not self.smart_crawler:
            return {"products": [], "error": "SmartCrawler not available"}

        try:
            # Check if AI client exists
            if hasattr(self.smart_crawler, "ai_client"):
                # Use AI to extract products from the list page
                prompt = """
                Extract all whiskey/spirit products mentioned in this HTML content.
                For each product, extract:
                - name: The product name
                - brand: The brand name
                - link: Any product link (relative or absolute URL)
                - price: Price if mentioned
                - rating: Rating/score if mentioned
                - description: Brief description if provided

                Return as JSON: {"products": [...], "total_products": N}
                """

                # This would call the actual AI service
                response = self.smart_crawler.ai_client.extract(
                    content=html_content,
                    prompt=prompt,
                    extraction_type="list_products",
                )

                if hasattr(response, "data"):
                    return response.data or {"products": []}
                return response if isinstance(response, dict) else {"products": []}

        except Exception as e:
            logger.warning(f"AI list extraction failed: {e}")

        return {"products": [], "error": str(e) if 'e' in dir() else "Unknown error"}

    def _extract_list_products(
        self,
        url: str,
        html_content: str,
        max_products: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Extract products from a list page using AI.

        Args:
            url: The list page URL
            html_content: The HTML content
            max_products: Maximum products to extract

        Returns:
            List of product dictionaries
        """
        response = self._call_ai_list_extraction(html_content, url)
        products = response.get("products", [])

        # Limit to max_products
        products = products[:max_products]

        # Resolve relative links
        products = self._resolve_product_links(products, url)

        return products

    def _resolve_product_links(
        self,
        products: List[Dict[str, Any]],
        base_url: str,
    ) -> List[Dict[str, Any]]:
        """
        Resolve relative links in product list to absolute URLs.

        Args:
            products: List of product dictionaries
            base_url: The base URL for resolving relative links

        Returns:
            Products with resolved links
        """
        from urllib.parse import urljoin

        resolved = []
        for product in products:
            product_copy = product.copy()
            link = product_copy.get("link")

            if link:
                if link.startswith("/"):
                    # Relative URL
                    parsed = urlparse(base_url)
                    product_copy["link"] = f"{parsed.scheme}://{parsed.netloc}{link}"
                elif not link.startswith("http"):
                    # Relative path
                    product_copy["link"] = urljoin(base_url, link)
                # else: already absolute

            resolved.append(product_copy)

        return resolved

    def _search_for_product_details(
        self,
        product_name: str,
        brand: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search for additional product details using SerpAPI.

        Args:
            product_name: The product name
            brand: Optional brand name

        Returns:
            Product details if found, None otherwise
        """
        # Construct search query
        query = product_name
        if brand:
            query = f"{brand} {product_name}"

        try:
            results = self._search(query)
            if results:
                # Return first result that looks like a product page
                for result in results[:5]:
                    url = result.get("link", "")
                    if self._is_product_url(url, result.get("title", "")):
                        return {
                            "url": url,
                            "title": result.get("title"),
                            "snippet": result.get("snippet"),
                        }
        except Exception as e:
            logger.warning(f"Product detail search failed: {e}")

        return None

    def _enrich_product_from_list(
        self,
        product_info: Dict[str, Any],
        source_url: str,
        search_term: SearchTerm,
    ) -> Dict[str, Any]:
        """
        Enrich a product discovered from a list page.

        Args:
            product_info: Basic product info from list
            source_url: The list page URL
            search_term: The search term that found this

        Returns:
            Result dictionary with enrichment details
        """
        name = product_info.get("name", "")
        brand = product_info.get("brand")
        link = product_info.get("link")

        result = {
            "name": name,
            "brand": brand,
            "discovered_via_list": source_url,
            "is_duplicate": False,
            "needs_review": False,
            "partial": False,
            "created": False,
        }

        # Check for existing product
        existing = self._find_existing_product(link or "", name)
        if existing:
            result["is_duplicate"] = True
            result["existing_product_id"] = existing.id
            return result

        # If we have a direct link, use SmartCrawler
        if link and self.smart_crawler:
            try:
                product_type = search_term.product_type
                if product_type == "both":
                    product_type = "whiskey"

                extraction = self.smart_crawler.extract_product(
                    expected_name=name,
                    product_type=product_type,
                    primary_url=link,
                )

                # Track API calls
                if self.job:
                    if hasattr(extraction, "scrapingbee_calls"):
                        self.job.scrapingbee_calls_used += extraction.scrapingbee_calls
                    else:
                        self.job.scrapingbee_calls_used += 1

                    if hasattr(extraction, "ai_calls"):
                        self.job.ai_calls_used += extraction.ai_calls
                    else:
                        self.job.ai_calls_used += 1

                if extraction.success:
                    result["created"] = True
                    result["data"] = extraction.data
                    result["needs_review"] = extraction.needs_review
                    return result

            except Exception as e:
                logger.warning(f"Product enrichment failed for {name}: {e}")

        # No link or extraction failed - create partial product
        result["partial"] = True
        result["needs_review"] = True

        # Try to find additional details via search
        if not link:
            search_result = self._search_for_product_details(name, brand)
            if search_result:
                result["search_result"] = search_result

        return result

    def _process_list_page_products(
        self,
        products: List[Dict[str, Any]],
        list_url: str,
        search_term: SearchTerm,
    ):
        """
        Process all products extracted from a list page.

        Args:
            products: List of product info dictionaries
            list_url: The source list page URL
            search_term: The search term that found this list
        """
        for product_info in products:
            link = product_info.get("link")

            # If product has a direct link, use SmartCrawler
            if link and self.smart_crawler:
                try:
                    product_type = search_term.product_type
                    if product_type == "both":
                        product_type = "whiskey"

                    extraction = self.smart_crawler.extract_product(
                        expected_name=product_info.get("name", ""),
                        product_type=product_type,
                        primary_url=link,
                    )

                    # Track API calls
                    if hasattr(extraction, "scrapingbee_calls"):
                        self.job.scrapingbee_calls_used += extraction.scrapingbee_calls
                    else:
                        self.job.scrapingbee_calls_used += 1

                    if hasattr(extraction, "ai_calls"):
                        self.job.ai_calls_used += extraction.ai_calls
                    else:
                        self.job.ai_calls_used += 1

                    if extraction.success and extraction.data:
                        # Save the product
                        product = self._save_product(extraction.data, link)
                        if product:
                            self.job.products_new += 1
                        else:
                            self.job.products_updated += 1

                        self.job.urls_crawled += 1

                except Exception as e:
                    logger.warning(f"Failed to process list product {product_info.get('name')}: {e}")
                    self.job.products_failed += 1

    def _create_partial_product(
        self,
        product_info: Dict[str, Any],
        source_url: str,
        search_term: SearchTerm,
    ):
        """
        Create a partial product record for a product without full details.

        Args:
            product_info: Basic product info from list
            source_url: The list page URL
            search_term: The search term that found this
        """
        name = product_info.get("name", "Unknown")

        # Check if product already exists
        existing = self._find_existing_product("", name)
        if existing:
            return

        # Create product with partial info
        product_type = search_term.product_type
        if product_type == "both":
            product_type = "whiskey"

        product = DiscoveredProduct.objects.create(
            name=name,
            product_type=product_type,
            source_url=source_url,
            status="needs_review",
            extracted_data={
                "partial": True,
                "from_list_page": source_url,
                "brand": product_info.get("brand"),
                "price": product_info.get("price"),
                "rating": product_info.get("rating"),
            },
        )

        self.job.products_new += 1
        return product
