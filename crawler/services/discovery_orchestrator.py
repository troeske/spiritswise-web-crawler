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
from crawler.services.product_saver import save_discovered_product, ProductSaveResult

logger = logging.getLogger(__name__)


class SerpAPIClient:
    """Client for Google Search API via SerpAPI."""

    def __init__(self, api_key: Optional[str] = None):
        from django.conf import settings
        self.api_key = api_key or getattr(settings, "SERPAPI_KEY", None) or os.getenv("SERPAPI_KEY")
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
       a. Check if URL is a competition site -> route to competition flow
       b. Check if product already exists (dedup)
       c. If new, use SmartCrawler to extract
       d. If existing, check if update needed
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

    # Known competition/award sites (handled by competition flow)
    COMPETITION_DOMAINS = {
        # Major spirits competitions
        "iwsc.net": "iwsc",
        "sfspiritscomp.com": "sfwsc",
        "thetastingalliance.com": "sfwsc",  # SFWSC results hosted here
        "worldwhiskiesawards.com": "wwa",
        "awards.decanter.com": "decanter",
        "decanter.com": "decanter",
        # Additional competitions
        "spiritsawards.com": "spirits_awards",
        "internationalspiritschallenge.com": "isc",
        "ultimatespirits.com": "ultimate_spirits",
        "beveragetestinginstitute.com": "bti",
        "tastings.com": "bti",
        # Wine competitions (for Port)
        "winecompetitions.com": "wine_comp",
        "internationalwinecompetition.com": "iwc",
    }

    # URL patterns that indicate competition/award sites
    COMPETITION_URL_PATTERNS = [
        r"/results/?\d{4}",  # /results/2024 or /results2024
        r"/winners/?\d{4}",  # /winners/2024
        r"/awarded/",
        r"/medal-?winners",
        r"/award-?winners",
        r"/competition.*results",
        r"/spirits-?awards",
        r"/wine-?awards",
        r"/whisky-?awards",
        r"/whiskey-?awards",
    ]

    # Title patterns that indicate competition pages
    COMPETITION_TITLE_PATTERNS = [
        r"\b(iwsc|sfwsc|wwa)\b",  # Known acronyms
        r"international.*(wine|spirit|whisky).*competition",
        r"world.*spirits.*competition",
        r"world.*whisk(y|ey).*award",
        r"\d{4}.*medal.*winners",
        r"medal.*winners.*\d{4}",
        r"spirits.*award.*\d{4}",
        r"competition.*results",
    ]

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

    # =========================================================================
    # Competition Detection Methods
    # =========================================================================

    def _is_competition_url(self, url: str, title: str) -> tuple[bool, Optional[str]]:
        """
        Check if a URL is a competition/award site.

        Args:
            url: The URL to check
            title: The page title

        Returns:
            Tuple of (is_competition, parser_key)
            parser_key is the key to use for competition parsing if known
        """
        domain = self._extract_domain(url)
        url_lower = url.lower()
        title_lower = title.lower()

        # Check known competition domains
        for comp_domain, parser_key in self.COMPETITION_DOMAINS.items():
            if comp_domain in domain:
                return True, parser_key

        # Check URL patterns
        for pattern in self.COMPETITION_URL_PATTERNS:
            if re.search(pattern, url_lower, re.IGNORECASE):
                return True, None  # Unknown competition

        # Check title patterns
        for pattern in self.COMPETITION_TITLE_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True, None  # Unknown competition

        return False, None

    def _is_competition_in_schedule(self, url: str) -> Optional[CrawlSchedule]:
        """
        Check if a competition URL is already covered by a CrawlSchedule.

        Args:
            url: The competition URL to check

        Returns:
            CrawlSchedule if found, None otherwise
        """
        from crawler.models import ScheduleCategory

        domain = self._extract_domain(url)

        # Check for existing competition schedules that cover this domain
        schedules = CrawlSchedule.objects.filter(
            category=ScheduleCategory.COMPETITION
        )

        for schedule in schedules:
            # Check if base_url matches
            if schedule.base_url:
                schedule_domain = self._extract_domain(schedule.base_url)
                if schedule_domain and domain in schedule_domain or schedule_domain in domain:
                    return schedule

        return None

    def _create_pending_competition_schedule(
        self,
        url: str,
        title: str,
        parser_key: Optional[str] = None,
    ) -> CrawlSchedule:
        """
        Create an inactive CrawlSchedule for a discovered competition site.

        This allows humans to review and activate the schedule.

        Args:
            url: The competition URL
            title: The page title
            parser_key: Optional parser key if known

        Returns:
            The created CrawlSchedule (inactive, for review)
        """
        from crawler.models import ScheduleCategory, ScheduleFrequency

        domain = self._extract_domain(url)

        # Generate a slug from the domain
        slug = f"discovered-{domain.replace('.', '-')}"

        # Check if we already created this one
        existing = CrawlSchedule.objects.filter(slug=slug).first()
        if existing:
            return existing

        # Create new inactive schedule for review
        schedule = CrawlSchedule.objects.create(
            name=f"[REVIEW] {title[:50]}",
            slug=slug,
            category=ScheduleCategory.COMPETITION,
            frequency=ScheduleFrequency.WEEKLY,
            base_url=url,
            search_terms=[parser_key] if parser_key else [],
            is_active=False,  # Inactive until human reviews
            notes=f"Auto-discovered competition site. Parser: {parser_key or 'unknown'}. Original title: {title}",
        )

        logger.info(f"Created pending competition schedule for review: {domain}")
        return schedule

    def _handle_competition_url(
        self,
        url: str,
        title: str,
        term: SearchTerm,
        rank: int,
    ) -> bool:
        """
        Handle a URL that appears to be a competition site.

        If the competition is already in our schedule, skip it (it will be
        handled by the competition flow). If not, create a pending schedule
        for human review.

        Args:
            url: The competition URL
            title: The page title
            term: The search term that found this
            rank: Search result rank

        Returns:
            True if handled (should skip normal processing), False otherwise
        """
        is_competition, parser_key = self._is_competition_url(url, title)

        if not is_competition:
            return False

        # Check if already in schedule
        existing_schedule = self._is_competition_in_schedule(url)
        if existing_schedule:
            logger.info(
                f"Competition URL already scheduled: {url} -> {existing_schedule.name}"
            )
            self.job.urls_skipped += 1
            return True

        # Create pending schedule for review
        self._create_pending_competition_schedule(url, title, parser_key)
        self.job.urls_skipped += 1
        return True

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
        Get search terms to process based on schedule configuration.

        If schedule has direct search_terms list (CrawlSchedule), creates
        temporary SearchTerm-like objects from those.

        Otherwise, queries the SearchTerm model with filters.

        Returns:
            List of SearchTerm objects (or compatible wrappers) to process
        """
        # Check if schedule has direct search_terms (unified CrawlSchedule approach)
        if self.schedule and hasattr(self.schedule, 'search_terms') and self.schedule.search_terms:
            # Create lightweight SearchTerm-like objects from direct search terms
            class DirectSearchTerm:
                """Lightweight wrapper for direct search term strings."""
                def __init__(self, query: str, priority: int = 100, product_type: str = None):
                    self.term_template = query
                    self.priority = priority
                    self.search_count = 0
                    self.products_discovered = 0
                    # Infer product type from query if not specified
                    self.product_type = product_type or self._infer_product_type(query)

                def _infer_product_type(self, query: str) -> str:
                    """Infer product type from search query."""
                    query_lower = query.lower()
                    if any(w in query_lower for w in ["whisky", "whiskey", "scotch", "bourbon", "rye"]):
                        return "whiskey"
                    elif any(w in query_lower for w in ["port", "wine"]):
                        return "port_wine"
                    elif any(w in query_lower for w in ["rum"]):
                        return "rum"
                    elif any(w in query_lower for w in ["gin"]):
                        return "gin"
                    elif any(w in query_lower for w in ["vodka"]):
                        return "vodka"
                    elif any(w in query_lower for w in ["tequila", "mezcal"]):
                        return "tequila"
                    elif any(w in query_lower for w in ["cognac", "brandy"]):
                        return "brandy"
                    return "spirits"  # Default

                def get_search_query(self) -> str:
                    # Replace {year} with current year if present
                    from django.utils import timezone
                    return self.term_template.replace("{year}", str(timezone.now().year))

                def save(self, *args, **kwargs):
                    pass  # No-op for direct terms

            return [DirectSearchTerm(term, 100 - i) for i, term in enumerate(self.schedule.search_terms)]

        # Fall back to SearchTerm model lookup
        terms = SearchTerm.objects.filter(is_active=True)

        # Apply schedule filters if we have a schedule
        if self.schedule:
            # Product type filter
            if hasattr(self.schedule, 'product_types') and self.schedule.product_types:
                terms = terms.filter(product_type__in=self.schedule.product_types)

        # Filter seasonal terms
        terms = [t for t in terms if self._is_term_in_season(t)]

        # Order by priority (higher value = higher priority)
        terms = sorted(terms, key=lambda t: -t.priority)

        # Apply limit (default 20)
        max_terms = 20
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

        # STEP 1: Check if this is a competition site
        # If so, route to competition flow or create pending schedule
        if self._handle_competition_url(url, title, term, rank):
            return  # Handled by competition logic

        # STEP 2: Check if this is a list page with multiple products
        if self._is_list_page(url, title):
            self._process_list_page(url, title, term, rank)
            return

        # Create discovery result record for single product page
        domain = self._extract_domain(url)
        # Only assign search_term if it's a real SearchTerm model instance
        search_term_fk = term if isinstance(term, SearchTerm) else None
        discovery_result = DiscoveryResult.objects.create(
            job=self.job,
            search_term=search_term_fk,
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

        Extracts all products mentioned on the page, including any available
        tasting notes, ratings, and other data. Then enriches each product
        by searching for additional details.

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

        # Get product type from search term
        product_type = getattr(term, "product_type", "unknown") or "unknown"

        # Extract products from list - includes all available data (names, tasting notes, ratings, etc.)
        products = self._extract_list_products(url, html_content, product_type=product_type)
        if not products:
            logger.warning(f"No products found in list page: {url}")
            return

        logger.info(f"Found {len(products)} products in list page")

        # Process each product - enrich with additional data and save
        for product_info in products:
            # Log what data we have from the list page
            if product_info.get("tasting_notes"):
                logger.info(f"  Product {product_info.get('name', 'Unknown')} has tasting notes from list page")
            if product_info.get("rating"):
                logger.info(f"  Product {product_info.get('name', 'Unknown')} has rating from list page")

            # Enrich and save the product
            result = self._enrich_product_from_list(product_info, url, term)

            # Track results
            if result.get("is_duplicate"):
                self.job.products_duplicates += 1
            elif result.get("created"):
                self.job.products_new += 1
                logger.info(f"  Created product: {product_info.get('name', 'Unknown')}")
            # Note: _enrich_product_from_list now handles partial product creation

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

                # Create or update product using unified save function
                product = self._save_product(extraction.data, url, product_type=product_type)
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
        discovery_source: str = "search",
        product_type: str = "whiskey",
    ) -> Optional[DiscoveredProduct]:
        """
        Save extracted product data to database using the unified save function.

        This method delegates to save_discovered_product() from product_saver.py,
        which handles all the field mapping, deduplication, and related record creation.

        Args:
            data: Extracted product data from AI/crawler
            source_url: URL where product was found
            discovery_source: How product was discovered (search, competition, etc.)
            product_type: Type of product (whiskey, port_wine, etc.)

        Returns:
            Created DiscoveredProduct or None if already exists (updated instead)
        """
        if not data:
            return None

        name = data.get("name", "Unknown")
        if not name or name == "Unknown":
            return None

        # Normalize product_type to match ProductType enum values
        normalized_type = product_type
        if product_type in ("spirits", "unknown", "both"):
            normalized_type = "whiskey"  # Default fallback

        # Convert the extracted data format to match save_discovered_product expectations
        # The orchestrator may receive data with JSON fields (taste_profile, ratings, images, awards)
        # that need to be converted to individual column format
        normalized_data = self._normalize_data_for_save(data)

        # Call the unified save function with check_existing=True to handle deduplication
        try:
            result: ProductSaveResult = save_discovered_product(
                extracted_data=normalized_data,
                source_url=source_url,
                product_type=normalized_type,
                discovery_source=discovery_source,
                crawled_source=None,  # Discovery flow doesn't have CrawledSource
                check_existing=True,  # Enable deduplication check
                field_confidences=None,
                extraction_confidence=0.8,
                raw_content="",
            )

            if result.created:
                logger.info(f"Created new product via discovery: {result.product.name} ({result.product.id})")
                return result.product
            else:
                logger.info(f"Updated existing product via discovery: {result.product.name} ({result.product.id})")
                return None  # Return None to indicate update, not new (matches original behavior)

        except Exception as e:
            logger.error(f"Failed to save product via unified save function: {e}")
            return None

    def _normalize_data_for_save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize extracted data from orchestrator format to save_discovered_product format.

        The orchestrator may receive data with JSON-style fields that need to be
        expanded into the individual column format expected by save_discovered_product.

        Args:
            data: Raw extracted data dict

        Returns:
            Normalized data dict with fields expanded for save_discovered_product
        """
        normalized = data.copy()

        # Handle taste_profile JSON field -> individual tasting fields
        taste_profile = data.get("taste_profile", {})
        if isinstance(taste_profile, dict):
            if taste_profile.get("nose") and not normalized.get("nose_description"):
                normalized["nose_description"] = taste_profile["nose"]
            if taste_profile.get("palate") and not normalized.get("initial_taste"):
                normalized["initial_taste"] = taste_profile["palate"]
            if taste_profile.get("finish") and not normalized.get("final_notes"):
                normalized["final_notes"] = taste_profile["finish"]
            if taste_profile.get("flavor_tags") and not normalized.get("palate_flavors"):
                normalized["palate_flavors"] = taste_profile["flavor_tags"]
            if taste_profile.get("overall_notes") and not normalized.get("nose_description"):
                normalized["nose_description"] = taste_profile["overall_notes"]

        # Handle tasting_notes if present (alternate format)
        tasting_notes = data.get("tasting_notes", {})
        if isinstance(tasting_notes, dict):
            if tasting_notes.get("nose") and not normalized.get("nose_description"):
                normalized["nose_description"] = tasting_notes["nose"]
            if tasting_notes.get("palate") and not normalized.get("initial_taste"):
                normalized["initial_taste"] = tasting_notes["palate"]
            if tasting_notes.get("finish") and not normalized.get("final_notes"):
                normalized["final_notes"] = tasting_notes["finish"]
            if tasting_notes.get("flavor_tags") and not normalized.get("palate_flavors"):
                normalized["palate_flavors"] = tasting_notes["flavor_tags"]
            if tasting_notes.get("overall") and not normalized.get("nose_description"):
                normalized["nose_description"] = tasting_notes["overall"]
            if tasting_notes.get("notes") and not normalized.get("nose_description"):
                normalized["nose_description"] = tasting_notes["notes"]
        elif isinstance(tasting_notes, str) and tasting_notes:
            if not normalized.get("nose_description"):
                normalized["nose_description"] = tasting_notes

        # Handle ratings list -> ensure it's in the expected format
        ratings = data.get("ratings", [])
        if not isinstance(ratings, list):
            ratings = []

        # If there's a single rating/score in the data, add it to ratings
        if data.get("rating") or data.get("score"):
            single_rating = {
                "source": data.get("rating_source", source_url if 'source_url' in dir() else ""),
                "score": data.get("rating") or data.get("score"),
                "max_score": data.get("max_score", 100),
                "reviewer": data.get("reviewer"),
            }
            # Only add if not already in ratings
            if single_rating not in ratings:
                ratings.append(single_rating)

        if ratings:
            normalized["ratings"] = ratings

        # Handle images list -> ensure it's in the expected format
        images = data.get("images", [])
        if not isinstance(images, list):
            images = []

        # If there's a single image_url in the data, add it to images
        if data.get("image_url"):
            single_image = {
                "url": data["image_url"],
                "image_type": "bottle",
                "source": data.get("source_url", ""),
            }
            if single_image not in images:
                images.append(single_image)

        if images:
            normalized["images"] = images

        # Handle awards list -> ensure it's in the expected format
        awards = data.get("awards", [])
        if not isinstance(awards, list):
            awards = []
        if awards:
            normalized["awards"] = awards

        # Handle price_history -> extract current price for ratings
        price_history = data.get("price_history", [])
        if isinstance(price_history, list) and price_history:
            # Keep price_history for reference but also set price field
            if not normalized.get("price") and price_history[0].get("price"):
                normalized["price"] = price_history[0]["price"]

        # Parse ABV, age, volume if they're in string format
        if data.get("abv") and isinstance(data["abv"], str):
            normalized["abv"] = self._parse_abv(data["abv"])
        if data.get("age_statement") and isinstance(data["age_statement"], str):
            normalized["age_statement"] = self._parse_age(data["age_statement"])
        if data.get("age") and isinstance(data["age"], str):
            normalized["age_statement"] = self._parse_age(data["age"])
        if data.get("volume_ml") and isinstance(data["volume_ml"], str):
            normalized["volume_ml"] = self._parse_volume(data["volume_ml"])
        if data.get("volume") and isinstance(data["volume"], str):
            normalized["volume_ml"] = self._parse_volume(data["volume"])
        if data.get("size") and isinstance(data["size"], str):
            normalized["volume_ml"] = self._parse_volume(data["size"])

        return normalized

    def _parse_abv(self, value) -> Optional[float]:
        """Parse ABV value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Extract number from strings like "40%", "40.5% ABV", etc.
            match = re.search(r"(\d+\.?\d*)", value)
            if match:
                return float(match.group(1))
        return None

    def _parse_age(self, value) -> Optional[int]:
        """Parse age statement from various formats."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # Extract number from strings like "12 Year Old", "12 years", "12yo"
            match = re.search(r"(\d+)", value)
            if match:
                return int(match.group(1))
        return None

    def _parse_volume(self, value) -> Optional[int]:
        """Parse volume in ml from various formats."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value_lower = value.lower()
            # Handle common formats
            match = re.search(r"(\d+)", value)
            if match:
                num = int(match.group(1))
                # Convert liters to ml
                if "l" in value_lower and "ml" not in value_lower:
                    if num <= 10:  # Likely liters
                        return num * 1000
                return num
        return None

    def _parse_price(self, value) -> Optional[float]:
        """Parse price value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and common formatting
            cleaned = re.sub(r"[$£€¥,\s]", "", value)
            match = re.search(r"(\d+\.?\d*)", cleaned)
            if match:
                return float(match.group(1))
        return None

    def _generate_fingerprint(self, name: str, data: Dict[str, Any]) -> str:
        """Generate a fingerprint for deduplication."""
        import hashlib
        # Combine key identifying fields
        key_parts = [
            name.lower().strip(),
            str(data.get("abv", "")),
            str(data.get("age_statement", "")),
            str(data.get("volume_ml", "")),
        ]
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:64]

    def _merge_product_data(
        self,
        existing: DiscoveredProduct,
        new_data: Dict[str, Any],
        new_url: str,
    ):
        """
        Merge new data into an existing product.

        Updates fields that are empty or adds to lists.

        Args:
            existing: The existing product
            new_data: New extracted data
            new_url: New source URL
        """
        updated_fields = []

        # Update empty individual fields
        if not existing.abv and new_data.get("abv"):
            existing.abv = self._parse_abv(new_data["abv"])
            updated_fields.append("abv")

        if not existing.age_statement and new_data.get("age_statement"):
            existing.age_statement = self._parse_age(new_data["age_statement"])
            updated_fields.append("age_statement")

        if not existing.region and new_data.get("region"):
            existing.region = new_data["region"]
            updated_fields.append("region")

        if not existing.country and new_data.get("country"):
            existing.country = new_data["country"]
            updated_fields.append("country")

        # Merge taste profile -> individual fields
        if new_data.get("tasting_notes"):
            notes = new_data["tasting_notes"]
            if isinstance(notes, dict):
                if notes.get("nose") and not existing.nose_description:
                    existing.nose_description = notes["nose"]
                    updated_fields.append("nose_description")
                if notes.get("palate") and not existing.initial_taste:
                    existing.initial_taste = notes["palate"]
                    updated_fields.append("initial_taste")
                if notes.get("finish") and not existing.final_notes:
                    existing.final_notes = notes["finish"]
                    updated_fields.append("final_notes")

        if updated_fields:
            existing.save(update_fields=updated_fields)

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
        r"/ranking", r"/awards", r"/winners", r"/results",
        r"/competition", r"/medal", r"/recommendations",
        r"/review.*\d{4}", r"/guide/",
    ]

    # Title patterns that indicate list pages
    LIST_TITLE_PATTERNS = [
        r"\bbest\b.*\bwhisk", r"\bbest\b.*\bport", r"\bbest\b.*\bspirit",
        r"\btop\s+\d+\b", r"\d+\s+best\b",
        r"\bour\s+picks\b", r"\bfavorite\b",
        r"\bgift\s+guide\b", r"\bultimate\s+guide\b",
        # Competition and award patterns
        r"\bresult\b.*\d{4}", r"\bresults\b",
        r"\bwinner", r"\bmedal", r"\baward",
        r"\bcompetition\b", r"\bcontest\b",
        # Review/recommendation patterns
        r"\brecommend", r"\breview.*\d{4}",
        r"\btasted\b.*\brand", r"\brating",
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
        list_keywords = [
            "best", "top 10", "top 15", "top 20", "picks", "favorites", "ranking",
            "result", "results", "winners", "winner", "medal", "awards", "award",
            "competition", "recommendations", "recommended", "rated", "ratings",
            "reviewed", "tasted", "guide to", "roundup", "collection",
        ]
        if any(kw in title_lower for kw in list_keywords):
            # Make sure it's not a single product review that mentions "best"
            product_patterns = [r"/product/", r"/p/\d+", r"/shop/", r"/buy/"]
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
        Fetch HTML content from a URL using ScrapingBee via SmartCrawler.

        Args:
            url: The URL to fetch

        Returns:
            HTML content string
        """
        if not self.smart_crawler:
            return ""

        try:
            # SmartCrawler has self.crawler which is a ScrapingBee client
            # with fetch_page(url, render_js=True) method
            if hasattr(self.smart_crawler, "crawler"):
                result = self.smart_crawler.crawler.fetch_page(url, render_js=True)
                if result.get("success") and result.get("content"):
                    # Track the API call
                    if self.job:
                        self.job.scrapingbee_calls_used += 1
                    return result["content"]
                else:
                    logger.warning(f"Fetch failed for {url}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.warning(f"Failed to fetch page content: {e}")

        return ""

    def _call_ai_list_extraction(
        self,
        html_content: str,
        url: str,
        product_type: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Call AI service to extract product list from HTML.

        Uses the AI enhancement service to identify all products mentioned
        on a list/article page, extracting names and any available links.

        Args:
            html_content: The HTML content
            url: The source URL
            product_type: The product type (whiskey, port_wine, etc.)

        Returns:
            Dict with 'products' list and metadata
        """
        if not self.smart_crawler:
            return {"products": [], "error": "SmartCrawler not available"}

        try:
            # Access AI client through SmartCrawler
            if hasattr(self.smart_crawler, "ai_client"):
                ai_client = self.smart_crawler.ai_client

                # Trim content to reasonable size for AI processing
                content = html_content
                if len(content) > 80000:
                    content = content[:80000]

                # Map product type to valid hint values
                valid_types = ["whiskey", "gin", "tequila", "rum", "vodka", "sake", "brandy", "port_wine", "unknown"]
                type_hint = product_type if product_type in valid_types else "unknown"

                # Use enhance_from_crawler with product type hint
                result = ai_client.enhance_from_crawler(
                    content=content,
                    source_url=url,
                    product_type_hint=type_hint,
                )

                # Track the API call
                if self.job:
                    self.job.ai_calls_used += 1

                if result.get("success"):
                    data = result.get("data", {})
                    # The AI response may contain 'products' list or 'extracted_data'
                    if "products" in data:
                        return {"products": data["products"]}
                    elif "extracted_data" in data:
                        # Single product extracted - wrap in list
                        extracted = data["extracted_data"]
                        if extracted.get("name"):
                            return {"products": [extracted]}
                    # Try to parse from response
                    return {"products": [], "raw_response": data}
                else:
                    logger.warning(f"AI list extraction failed: {result.get('error')}")
                    return {"products": [], "error": result.get("error")}

        except Exception as e:
            logger.warning(f"AI list extraction failed: {e}")
            return {"products": [], "error": str(e)}

        return {"products": [], "error": "AI client not available"}

    def _extract_list_products(
        self,
        url: str,
        html_content: str,
        max_products: int = 20,
        product_type: str = "unknown",
    ) -> List[Dict[str, Any]]:
        """
        Extract products from a list page using AI.

        Args:
            url: The list page URL
            html_content: The HTML content
            max_products: Maximum products to extract
            product_type: The product type (whiskey, port_wine, etc.)

        Returns:
            List of product dictionaries
        """
        response = self._call_ai_list_extraction(html_content, url, product_type)
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

    def _search_and_extract_product(
        self,
        product_name: str,
        brand: Optional[str] = None,
        product_type: str = "whiskey",
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a product by name via SerpAPI and extract full data.

        This is the main enrichment method - uses the product NAME to:
        1. Search SerpAPI for product pages
        2. Find the best matching result (retailer or review site)
        3. Crawl that page to extract complete product data

        Args:
            product_name: The product name to search for
            brand: Optional brand name for better search
            product_type: Type of product (whiskey, port_wine, etc.)

        Returns:
            Dict with 'success' and 'data' keys, or None if failed
        """
        if not product_name:
            return None

        # Construct search query - focus on getting product details
        query = product_name
        if brand and brand.lower() not in product_name.lower():
            query = f"{brand} {product_name}"

        # Add product type to narrow results
        if product_type and product_type not in query.lower():
            query = f"{query} {product_type}"

        logger.info(f"Enrichment search: {query}")

        try:
            # Search via SerpAPI
            results = self._search(query)
            if self.job:
                self.job.serpapi_calls_used += 1

            if not results:
                return None

            # Find best matching result - prefer retailers, then review sites
            best_url = None
            for result in results[:5]:
                url = result.get("link", "")
                title = result.get("title", "")
                domain = self._extract_domain(url)

                # Skip competition sites - they're handled separately
                if domain in self.COMPETITION_DOMAINS:
                    continue

                # Skip blocked domains
                if domain in self.SKIP_DOMAINS:
                    continue

                # Prefer retailers for accurate product data
                if domain in self.RETAILER_DOMAINS:
                    best_url = url
                    break

                # Use review sites as fallback
                if domain in self.REVIEW_DOMAINS and not best_url:
                    best_url = url

                # General product pages
                if self._is_product_url(url, title) and not best_url:
                    best_url = url

            if not best_url:
                logger.info(f"No suitable product URL found for: {product_name}")
                return None

            logger.info(f"Crawling for enrichment: {best_url}")

            # Crawl the page and extract data
            if self.smart_crawler:
                extraction = self.smart_crawler.extract_product(
                    expected_name=product_name,
                    product_type=product_type,
                    primary_url=best_url,
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

                if extraction.success and extraction.data:
                    return {
                        "success": True,
                        "data": extraction.data,
                        "source_url": best_url,
                        "source_type": extraction.source_type,
                    }

        except Exception as e:
            logger.warning(f"Product search and extract failed for {product_name}: {e}")

        return None

    def _enrich_product_from_list(
        self,
        product_info: Dict[str, Any],
        source_url: str,
        search_term: SearchTerm,
    ) -> Dict[str, Any]:
        """
        Enrich a product discovered from a list page.

        Uses the product NAME to search for additional details via SerpAPI,
        then crawls the best matching result to extract full product data.

        Args:
            product_info: Basic product info from list (name, brand, tasting_notes, etc.)
            source_url: The list page URL where product was mentioned
            search_term: The search term that found this

        Returns:
            Result dictionary with enrichment details
        """
        name = product_info.get("name", "")
        brand = product_info.get("brand")
        link = product_info.get("link")

        if not name:
            return {"partial": True, "error": "No product name"}

        result = {
            "name": name,
            "brand": brand,
            "discovered_via_list": source_url,
            "is_duplicate": False,
            "needs_review": False,
            "partial": False,
            "created": False,
        }

        # Check for existing product by name
        existing = self._find_existing_product("", name)
        if existing:
            # Merge any new data from this mention into existing product
            self._merge_product_data(existing, product_info, source_url)
            result["is_duplicate"] = True
            result["existing_product_id"] = existing.id
            return result

        # Get product type
        product_type = getattr(search_term, "product_type", "whiskey")
        if product_type == "both":
            product_type = "whiskey"

        # STRATEGY 1: If we have initial data from the list page, start with that
        extracted_data = {
            "name": name,
            "brand": brand,
            "product_type": product_type,
            "tasting_notes": product_info.get("tasting_notes"),
            "rating": product_info.get("rating"),
            "price": product_info.get("price"),
            "abv": product_info.get("abv"),
            "age_statement": product_info.get("age"),
            "region": product_info.get("region"),
            "country": product_info.get("country"),
        }

        # STRATEGY 2: If we have a direct link, use SmartCrawler for full extraction
        if link and self.smart_crawler:
            try:
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

                if extraction.success and extraction.data:
                    # Merge with any data we already have
                    merged_data = {**extracted_data, **extraction.data}
                    merged_data["name"] = name  # Keep original name

                    # Save the product using unified save function
                    product = self._save_product(merged_data, link, discovery_source="search", product_type=product_type)
                    if product:
                        result["created"] = True
                        result["data"] = merged_data
                        result["product_id"] = str(product.id)
                    else:
                        result["is_duplicate"] = True
                    return result

            except Exception as e:
                logger.warning(f"Product enrichment failed for {name}: {e}")

        # STRATEGY 3: No link available - use product NAME to search for details
        logger.info(f"Searching for product details: {name}")
        search_result = self._search_and_extract_product(name, brand, product_type)

        if search_result and search_result.get("success"):
            # Merge search results with initial data
            merged_data = {**extracted_data}
            if search_result.get("data"):
                for key, value in search_result["data"].items():
                    if value and not merged_data.get(key):
                        merged_data[key] = value

            # Save the product using unified save function
            product = self._save_product(merged_data, source_url, discovery_source="search", product_type=product_type)
            if product:
                result["created"] = True
                result["data"] = merged_data
                result["product_id"] = str(product.id)
                result["enriched_from_search"] = True
            else:
                result["is_duplicate"] = True
            return result

        # STRATEGY 4: Couldn't find additional info - create with available data
        if extracted_data.get("name"):
            product = self._save_product(extracted_data, source_url, discovery_source="search", product_type=product_type)
            if product:
                result["created"] = True
                result["partial"] = True
                result["data"] = extracted_data
                result["product_id"] = str(product.id)
            else:
                result["is_duplicate"] = True
        else:
            result["partial"] = True
            result["needs_review"] = True

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
                        # Save the product using unified save function
                        product = self._save_product(extraction.data, link, product_type=product_type)
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

        # Create product with partial info using unified save function
        product_type = search_term.product_type
        if product_type == "both":
            product_type = "whiskey"

        # Prepare data for unified save
        extracted_data = {
            "name": name,
            "partial": True,
            "from_list_page": source_url,
            "brand": product_info.get("brand"),
            "price": product_info.get("price"),
            "rating": product_info.get("rating"),
        }

        product = self._save_product(extracted_data, source_url, discovery_source="search", product_type=product_type)
        if product:
            self.job.products_new += 1
        return product
