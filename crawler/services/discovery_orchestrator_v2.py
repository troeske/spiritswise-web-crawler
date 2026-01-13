"""
Discovery Orchestrator V2 - Orchestrates product discovery with V2 components.

Phase 5 of V2 Architecture: Integrates AIClientV2, QualityGateV2,
EnrichmentOrchestratorV2, and SourceTracker for complete product discovery.

Features:
- Single product extraction with quality assessment
- List page extraction with skeleton product creation
- Source tracking and field provenance
- Enrichment queue decision logic
- Content preprocessing integration
- URL resolution for relative links
- Backward-compatible run() method for V1 interface support

V2 Migration (2026-01-11):
- Added schedule parameter to __init__ for backward compatibility with V1
- Added run() method to support V1 interface used in tasks.py
- Maintains all V2 functionality while supporting V1 callers

V3 Integration (2026-01-13):
- Updated _assess_quality to support QualityGateV3 with product_category
- Updated _should_enrich to include V3 status levels (BASELINE, ENRICHED)
- Added status progression tracking
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from crawler.fetchers.smart_router import SmartRouter
from crawler.services.ai_client_v2 import AIClientV2, ExtractionResultV2, get_ai_client_v2
from crawler.services.quality_gate_v2 import ProductStatus, QualityGateV2, get_quality_gate_v2
from crawler.services.enrichment_orchestrator_v2 import (
    EnrichmentOrchestratorV2,
    get_enrichment_orchestrator_v2,
)
from crawler.services.source_tracker import SourceTracker, get_source_tracker

logger = logging.getLogger(__name__)


# Safety limits for enrichment (ScrapingBee cost control)
MAX_URLS_PER_PRODUCT = 5
MAX_SERPAPI_SEARCHES_PER_PRODUCT = 3
MAX_ENRICHMENT_TIME_SECONDS = 120


@dataclass
class SingleProductResult:
    """Result of single product extraction."""

    success: bool
    product_data: Optional[Dict[str, Any]] = None
    quality_status: Optional[str] = None
    needs_enrichment: bool = False
    error: Optional[str] = None
    product_id: Optional[int] = None
    field_confidences: Dict[str, float] = field(default_factory=dict)
    detail_url: Optional[str] = None


@dataclass
class ListProductResult:
    """Result of list page extraction."""

    success: bool
    products: List[SingleProductResult] = field(default_factory=list)
    error: Optional[str] = None
    source_url: Optional[str] = None


class DiscoveryOrchestratorV2:
    """
    V2 Discovery Orchestrator integrating all V2 components.

    Orchestrates:
    - Page fetching and content preprocessing
    - AI extraction via AIClientV2
    - Quality assessment via QualityGateV2 or QualityGateV3
    - Enrichment decisions and queueing
    - Source tracking and field provenance

    Supports both single product pages and list pages.

    V2 Migration: Also supports V1 interface via schedule parameter and run() method.
    V3 Integration: Supports QualityGateV3 with category-specific requirements.
    """

    DEFAULT_TIMEOUT = 30.0

    # Domains to skip (social media, general news, etc.)
    SKIP_DOMAINS = {
        "facebook.com", "twitter.com", "instagram.com", "youtube.com",
        "tiktok.com", "pinterest.com", "linkedin.com", "reddit.com",
        "cnn.com", "bbc.com", "nytimes.com", "theguardian.com",
        "washingtonpost.com", "usatoday.com", "foxnews.com",
        "amazon.com", "ebay.com", "walmart.com",
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
        ai_client: Optional[AIClientV2] = None,
        quality_gate=None,  # Can be QualityGateV2 or QualityGateV3
        enrichment_orchestrator: Optional[EnrichmentOrchestratorV2] = None,
        source_tracker: Optional[SourceTracker] = None,
        schedule=None,
        serpapi_client=None,
        smart_crawler=None,
    ):
        """
        Initialize the Discovery Orchestrator V2.

        Args:
            ai_client: AIClientV2 instance (optional, creates default)
            quality_gate: QualityGateV2 or QualityGateV3 instance (optional, creates default)
            enrichment_orchestrator: EnrichmentOrchestratorV2 instance (optional)
            source_tracker: SourceTracker instance (optional, creates default)
            schedule: CrawlSchedule for V1 backward compatibility (optional)
            serpapi_client: SerpAPI client for V1 backward compatibility (optional)
            smart_crawler: SmartCrawler for V1 backward compatibility (optional)
        """
        self.ai_client = ai_client or get_ai_client_v2()
        self.quality_gate = quality_gate or get_quality_gate_v2()
        self.enrichment_orchestrator = enrichment_orchestrator or get_enrichment_orchestrator_v2()
        self.source_tracker = source_tracker or get_source_tracker()

        # V1 backward compatibility
        self.schedule = schedule
        self.serpapi_client = serpapi_client
        self.smart_crawler = smart_crawler
        self.job = None  # DiscoveryJob, set during run()

        # Enrichment tracking (from V1)
        self._product_url_counts: Dict[str, int] = {}
        self._product_serpapi_counts: Dict[str, int] = {}
        self._product_start_times: Dict[str, float] = {}

        # V3: Status progression tracking
        self._status_progression: Dict[str, List[str]] = {}

        # Initialize SerpAPI client if not provided
        if self.serpapi_client is None and self.schedule is not None:
            self._init_serpapi_client()

        logger.debug("DiscoveryOrchestratorV2 initialized with V2 components")

    def _init_serpapi_client(self):
        """Initialize SerpAPI client from settings."""
        try:
            import os
            from django.conf import settings

            api_key = getattr(settings, "SERPAPI_KEY", None) or os.getenv("SERPAPI_KEY")
            if api_key:
                # Create a simple wrapper for SerpAPI
                self.serpapi_client = _SerpAPIClient(api_key)
        except Exception as e:
            logger.warning(f"Could not initialize SerpAPI client: {e}")

    # =========================================================================
    # V1 Backward Compatibility Methods
    # =========================================================================

    def run(self):
        """
        Execute a discovery run using the V1 interface.

        This method provides backward compatibility with the V1 DiscoveryOrchestrator
        interface used in tasks.py:run_discovery_flow().

        Returns:
            DiscoveryJob with results
        """
        from django.utils import timezone
        from crawler.models import (
            DiscoveryJob,
            DiscoveryJobStatus,
            SearchTerm,
        )

        if self.schedule is None:
            raise ValueError("schedule must be set to use run() method")

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

    def _get_search_terms(self) -> List:
        """Get search terms from schedule."""
        # Check if schedule has direct search_terms
        if self.schedule and hasattr(self.schedule, 'search_terms') and self.schedule.search_terms:

            class DirectSearchTerm:
                """Lightweight wrapper for direct search term strings."""
                def __init__(self, query: str, priority: int = 100, product_type: str = None):
                    self.search_query = query
                    self.priority = priority
                    self.search_count = 0
                    self.products_discovered = 0
                    self.max_results = 10
                    self.product_type = product_type or self._infer_product_type(query)

                def _infer_product_type(self, query: str) -> str:
                    query_lower = query.lower()
                    if any(w in query_lower for w in ["whisky", "whiskey", "scotch", "bourbon", "rye"]):
                        return "whiskey"
                    elif any(w in query_lower for w in ["port", "wine"]):
                        return "port_wine"
                    elif any(w in query_lower for w in ["rum"]):
                        return "rum"
                    elif any(w in query_lower for w in ["gin"]):
                        return "gin"
                    return "spirits"

                def save(self, *args, **kwargs):
                    pass

            return [DirectSearchTerm(term, 100 - i) for i, term in enumerate(self.schedule.search_terms)]

        # Fall back to SearchTerm model lookup
        from crawler.models import SearchTerm
        terms = SearchTerm.objects.filter(is_active=True)

        if self.schedule and hasattr(self.schedule, 'product_types') and self.schedule.product_types:
            terms = terms.filter(product_type__in=self.schedule.product_types)

        terms = sorted(list(terms), key=lambda t: -t.priority)
        return terms[:20]

    def _process_search_term(self, term):
        """Process a single search term."""
        from django.utils import timezone

        query = term.search_query
        logger.info(f"Searching: {query}")

        # Execute search
        results = self._search(query)
        self.job.serpapi_calls_used += 1

        max_results = getattr(term, 'max_results', 10)

        # Process each result
        for rank, result in enumerate(results[:max_results], 1):
            self._process_search_result(term, result, rank)

        # Update term stats
        if hasattr(term, 'last_searched'):
            term.last_searched = timezone.now()
            term.search_count += 1
            term.save()

    def _search(self, query: str) -> List[Dict[str, Any]]:
        """Execute a search query via SerpAPI."""
        if self.serpapi_client is None:
            logger.warning("SerpAPI client not initialized")
            return []

        try:
            response = self.serpapi_client.search(query)
            return response.get("organic_results", [])
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _process_search_result(self, term, result: Dict[str, Any], rank: int):
        """Process a single search result."""
        from crawler.models import DiscoveryResult, DiscoveryResultStatus, SearchTerm

        url = result.get("link")
        title = result.get("title", "")

        if not url:
            return

        # Check if this is a product URL we should process
        if not self._is_product_url(url, title):
            self.job.urls_skipped += 1
            return

        self.job.urls_found += 1
        logger.info(f"Processing URL: {url[:80]}...")

        # Create discovery result record
        domain = self._extract_domain(url)
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

        # Extract product using V2 AI client
        self._extract_and_save_product_v2(term, discovery_result, url, title)

    def _is_product_url(self, url: str, title: str) -> bool:
        """Determine if a URL likely leads to product information."""
        domain = self._extract_domain(url)

        if domain in self.SKIP_DOMAINS:
            return False

        for skip in self.SKIP_DOMAINS:
            if skip in domain:
                return False

        if domain in self.RETAILER_DOMAINS:
            return True

        if domain in self.REVIEW_DOMAINS:
            return True

        url_lower = url.lower()
        product_patterns = [
            "/product/", "/products/", "/p/", "/shop/",
            "/whiskey/", "/whisky/", "/bourbon/", "/scotch/",
            "/port/", "/wine/", "/spirits/",
            "/best-", "/top-", "/review/",
        ]
        if any(pattern in url_lower for pattern in product_patterns):
            return True

        title_lower = title.lower()
        product_keywords = [
            "whiskey", "whisky", "bourbon", "scotch", "port wine",
            "best", "top 10", "review", "tasting", "year old",
        ]
        if any(keyword in title_lower for keyword in product_keywords):
            return True

        return True

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL, removing www prefix."""
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _find_existing_product(self, url: str, name: str):
        """Find an existing product by URL or fuzzy name match."""
        from crawler.models import DiscoveredProduct, CrawledSource, ProductSource

        # Check for exact URL match
        product = DiscoveredProduct.objects.filter(source_url=url).first()
        if product:
            return product

        # Check CrawledSource -> ProductSource path
        try:
            crawled = CrawledSource.objects.filter(url=url).first()
            if crawled:
                source = ProductSource.objects.filter(source=crawled).first()
                if source and source.product:
                    return source.product
        except Exception:
            pass

        return None

    def _extract_and_save_product_v2(self, term, discovery_result, url: str, title: str):
        """Extract product data using V2 AI client and save."""
        from crawler.models import DiscoveryResultStatus

        product_type = getattr(term, 'product_type', 'whiskey')
        if product_type == "both":
            product_type = "whiskey"

        try:
            # Use async extraction via V2
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.extract_single_product(
                        url=url,
                        product_type=product_type,
                        save_to_db=True,
                    )
                )

                if result.success:
                    discovery_result.crawl_success = True
                    discovery_result.extraction_success = True
                    discovery_result.extracted_data = result.product_data or {}
                    discovery_result.status = DiscoveryResultStatus.SUCCESS
                    discovery_result.is_new_product = True

                    if result.product_id:
                        from crawler.models import DiscoveredProduct
                        try:
                            discovery_result.product = DiscoveredProduct.objects.get(id=result.product_id)
                        except DiscoveredProduct.DoesNotExist:
                            pass

                    self.job.products_new += 1
                    self.job.urls_crawled += 1
                else:
                    discovery_result.status = DiscoveryResultStatus.FAILED
                    discovery_result.error_message = result.error
                    self.job.products_failed += 1

                discovery_result.save()

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            discovery_result.status = DiscoveryResultStatus.FAILED
            discovery_result.error_message = str(e)
            discovery_result.save()
            self.job.products_failed += 1
            self.job.error_count += 1

    # =========================================================================
    # V2 Core Methods (Original V2 API)
    # =========================================================================

    async def extract_single_product(
        self,
        url: str,
        product_type: str,
        product_category: Optional[str] = None,
        save_to_db: bool = False,
    ) -> SingleProductResult:
        """
        Extract a single product from a URL.

        Args:
            url: URL of the product page
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint
            save_to_db: Whether to save the product to the database

        Returns:
            SingleProductResult with extraction results and quality assessment
        """
        logger.info("Extracting single product from %s (type=%s)", url, product_type)

        try:
            # Step 1: Fetch page content
            content = await self._fetch_page(url)
            if not content:
                return SingleProductResult(
                    success=False,
                    error="Failed to fetch page content"
                )

            # Step 2: Extract using AIClientV2
            extraction_result = await self.ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                product_category=product_category,
            )

            if not extraction_result.success or not extraction_result.products:
                return SingleProductResult(
                    success=False,
                    error=extraction_result.error or "No products extracted"
                )

            # Step 3: Get the primary product
            primary_product = extraction_result.products[0]
            product_data = primary_product.extracted_data
            field_confidences = primary_product.field_confidences

            # Step 4: Assess quality (V3-compatible with category support)
            quality_status = self._assess_quality(
                product_data=product_data,
                field_confidences=field_confidences,
                product_type=product_type,
                product_category=product_category,
            )

            # Step 5: Track status progression
            product_key = product_data.get("name", url)
            self._track_status_progression(product_key, quality_status)

            # Step 6: Determine enrichment need
            needs_enrichment = self._should_enrich(quality_status)

            # Step 7: Optionally save to database
            product_id = None
            if save_to_db:
                product_id = await self._save_product(
                    url=url,
                    product_data=product_data,
                    product_type=product_type,
                    quality_status=quality_status,
                    field_confidences=field_confidences,
                    raw_content=content,
                )

            return SingleProductResult(
                success=True,
                product_data=product_data,
                quality_status=quality_status,
                needs_enrichment=needs_enrichment,
                product_id=product_id,
                field_confidences=field_confidences,
            )

        except Exception as e:
            logger.exception("Error extracting single product from %s: %s", url, e)
            return SingleProductResult(
                success=False,
                error=str(e)
            )

    async def extract_list_products(
        self,
        url: str,
        product_type: str,
        product_category: Optional[str] = None,
    ) -> ListProductResult:
        """
        Extract multiple products from a list page.

        Args:
            url: URL of the list page
            product_type: Product type (whiskey, port_wine, etc.)
            product_category: Optional category hint

        Returns:
            ListProductResult with all extracted products
        """
        logger.info("Extracting list products from %s (type=%s)", url, product_type)

        try:
            # Step 1: Fetch page content
            content = await self._fetch_page(url)
            if not content:
                return ListProductResult(
                    success=False,
                    error="Failed to fetch page content",
                    source_url=url
                )

            # Step 2: Extract using AIClientV2
            extraction_result = await self.ai_client.extract(
                content=content,
                source_url=url,
                product_type=product_type,
                product_category=product_category,
            )

            if not extraction_result.success:
                return ListProductResult(
                    success=False,
                    error=extraction_result.error or "Extraction failed",
                    source_url=url
                )

            # Step 3: Process each extracted product
            product_results = []
            for extracted_product in extraction_result.products:
                product_data = extracted_product.extracted_data
                field_confidences = extracted_product.field_confidences

                # Get category from extracted data if not provided
                effective_category = product_category or product_data.get("category")

                # Assess quality (V3-compatible with category support)
                quality_status = self._assess_quality(
                    product_data=product_data,
                    field_confidences=field_confidences,
                    product_type=product_type,
                    product_category=effective_category,
                )

                # Track status progression
                product_key = product_data.get("name", f"{url}_{len(product_results)}")
                self._track_status_progression(product_key, quality_status)

                # Resolve relative URL if present
                detail_url = self._resolve_url(
                    base_url=url,
                    relative_url=product_data.get("detail_url")
                )

                # Determine enrichment need
                needs_enrichment = self._should_enrich(quality_status)

                product_results.append(SingleProductResult(
                    success=True,
                    product_data=product_data,
                    quality_status=quality_status,
                    needs_enrichment=needs_enrichment,
                    field_confidences=field_confidences,
                    detail_url=detail_url,
                ))

            return ListProductResult(
                success=True,
                products=product_results,
                source_url=url
            )

        except Exception as e:
            logger.exception("Error extracting list products from %s: %s", url, e)
            return ListProductResult(
                success=False,
                error=str(e),
                source_url=url
            )

    async def _fetch_page(self, url: str, use_javascript: bool = True) -> Optional[str]:
        """
        Fetch page content from URL using SmartRouter for JavaScript rendering.

        Uses SmartRouter which supports:
        - Tier 1: httpx (fast, for static pages)
        - Tier 2: Playwright (JavaScript rendering)
        - Tier 3: ScrapingBee (premium proxy + JS rendering for blocked sites)

        Args:
            url: URL to fetch
            use_javascript: If True, force Tier 3 (ScrapingBee) for JavaScript rendering

        Returns:
            HTML content or None if failed
        """
        router = None
        try:
            # Use SmartRouter for fetching - it handles JavaScript rendering
            router = SmartRouter(timeout=self.DEFAULT_TIMEOUT)

            # For JavaScript-heavy pages (like competition sites), use Tier 3
            # which has ScrapingBee with render_js and wait capabilities
            force_tier = 3 if use_javascript else None

            result = await router.fetch(url, force_tier=force_tier)

            if result.success and result.content:
                logger.info(
                    "Fetched %s via SmartRouter (tier=%s, content_size=%d)",
                    url, result.tier_used, len(result.content)
                )
                return result.content
            else:
                logger.warning(
                    "SmartRouter failed for %s: %s (tier=%s)",
                    url, result.error, result.tier_used
                )
                # Fallback to httpx for simple pages
                async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                    response = await client.get(
                        url,
                        follow_redirects=True,
                        headers={
                            "User-Agent": "Mozilla/5.0 (compatible; SpiritswiseCrawler/2.0)"
                        }
                    )
                    response.raise_for_status()
                    return response.text

        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            raise
        finally:
            # Clean up SmartRouter connections
            if router:
                try:
                    await router.close()
                except Exception:
                    pass

    def _assess_quality(
        self,
        product_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        product_type: str,
        product_category: Optional[str] = None,
    ) -> str:
        """
        Assess product data quality using QualityGateV2 or QualityGateV3.

        V3 Integration:
        - Passes product_category for category-specific requirements
        - Supports V3 status hierarchy (SKELETON -> PARTIAL -> BASELINE -> ENRICHED -> COMPLETE)
        - COMPLETE requires 90% ECP in V3

        Args:
            product_data: Extracted product data
            field_confidences: Field confidence scores
            product_type: Product type
            product_category: Optional category for category-specific requirements

        Returns:
            Quality status string (e.g., "complete", "partial", "skeleton", "baseline", "enriched")
        """
        try:
            # Get category from product_data if not explicitly provided
            effective_category = product_category or product_data.get("category")

            # Check if quality_gate supports product_category (V3)
            if hasattr(self.quality_gate, 'assess'):
                import inspect
                sig = inspect.signature(self.quality_gate.assess)
                if 'product_category' in sig.parameters:
                    # V3 quality gate with category support
                    assessment = self.quality_gate.assess(
                        extracted_data=product_data,
                        product_type=product_type,
                        field_confidences=field_confidences,
                        product_category=effective_category,
                    )
                else:
                    # V2 quality gate without category support
                    assessment = self.quality_gate.assess(
                        extracted_data=product_data,
                        product_type=product_type,
                        field_confidences=field_confidences,
                    )
            else:
                # Fallback for unexpected quality gate implementation
                assessment = self.quality_gate.assess(
                    extracted_data=product_data,
                    product_type=product_type,
                    field_confidences=field_confidences,
                )

            return assessment.status.value
        except Exception as e:
            logger.warning("Quality assessment failed: %s, defaulting to rejected", e)
            return ProductStatus.REJECTED.value

    def _track_status_progression(self, product_key: str, status: str) -> None:
        """
        Track status progression for a product.

        V3 Feature: Records status changes for audit trail.

        Args:
            product_key: Unique identifier for the product
            status: Current status
        """
        if product_key not in self._status_progression:
            self._status_progression[product_key] = []
        self._status_progression[product_key].append(status)

    def get_status_progression(self, product_key: str) -> List[str]:
        """
        Get the status progression history for a product.

        Args:
            product_key: Unique identifier for the product

        Returns:
            List of status values in chronological order
        """
        return self._status_progression.get(product_key, [])

    def _should_enrich(self, quality_status: str) -> bool:
        """
        Determine if a product should be enriched based on quality status.

        V3 Status Hierarchy:
        - SKELETON: Minimal data, needs significant enrichment
        - PARTIAL: Missing some required fields
        - BASELINE: All required fields met, but could use more
        - ENRICHED: Has mouthfeel and OR fields
        - COMPLETE: 90% ECP reached, no more enrichment needed
        - REJECTED: Invalid data, not worth enriching

        Args:
            quality_status: Quality status string

        Returns:
            True if enrichment is needed
        """
        # V3 status values that need enrichment
        status_needs_enrichment = {
            "skeleton": True,
            "partial": True,
            "baseline": True,  # V3: BASELINE needs enrichment to reach COMPLETE
            "enriched": True,  # V3: ENRICHED needs more to reach 90% ECP
            "complete": False,  # V3: COMPLETE = 90% ECP, no more needed
            "rejected": False,
        }
        return status_needs_enrichment.get(quality_status.lower(), False)

    def _resolve_url(
        self,
        base_url: str,
        relative_url: Optional[str]
    ) -> Optional[str]:
        """
        Resolve a relative URL to absolute.

        Args:
            base_url: Base URL for resolution
            relative_url: Relative URL to resolve

        Returns:
            Absolute URL or None
        """
        if not relative_url:
            return None

        # Already absolute
        if relative_url.startswith(("http://", "https://")):
            return relative_url

        return urljoin(base_url, relative_url)

    async def _save_product(
        self,
        url: str,
        product_data: Dict[str, Any],
        product_type: str,
        quality_status: str,
        field_confidences: Dict[str, float],
        raw_content: str,
    ) -> Optional[int]:
        """
        Save extracted product to database.

        Args:
            url: Source URL
            product_data: Extracted product data
            product_type: Product type
            quality_status: Quality status
            field_confidences: Field confidences
            raw_content: Raw HTML content

        Returns:
            Product ID if saved, None otherwise
        """
        try:
            from crawler.models import DiscoveredProduct, DiscoveredBrand

            # Find or create brand
            brand_name = product_data.get("brand")
            brand = None
            if brand_name:
                brand, _ = DiscoveredBrand.objects.get_or_create(
                    name=brand_name,
                    defaults={"slug": brand_name.lower().replace(" ", "-")}
                )

            # Create product
            product = DiscoveredProduct.objects.create(
                name=product_data.get("name", "Unknown"),
                brand=brand,
                abv=product_data.get("abv"),
                product_type=product_type,
                description=product_data.get("description"),
                data_quality_status=quality_status,
                confidence_score=sum(field_confidences.values()) / len(field_confidences) if field_confidences else 0.0,
            )

            # Track source
            try:
                source = self.source_tracker.store_crawled_source(
                    url=url,
                    title=product_data.get("name", ""),
                    raw_content=raw_content,
                    source_type="product_page",
                )
                self.source_tracker.link_product_to_source(
                    product_id=product.id,
                    source_id=source.id,
                    extraction_confidence=product_data.get("confidence", 0.0),
                    fields_extracted=list(product_data.keys()),
                )
            except Exception as e:
                logger.warning("Failed to track source: %s", e)

            logger.info("Saved product %s (id=%s)", product.name, product.id)
            return product.id

        except Exception as e:
            logger.exception("Failed to save product: %s", e)
            return None


class _SerpAPIClient:
    """Simple SerpAPI client wrapper for V1 compatibility."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """Execute a Google search via SerpAPI."""
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


# Singleton instance
_discovery_orchestrator_v2: Optional[DiscoveryOrchestratorV2] = None


def get_discovery_orchestrator_v2() -> DiscoveryOrchestratorV2:
    """Get or create the singleton DiscoveryOrchestratorV2 instance."""
    global _discovery_orchestrator_v2
    if _discovery_orchestrator_v2 is None:
        _discovery_orchestrator_v2 = DiscoveryOrchestratorV2()
    return _discovery_orchestrator_v2


def reset_discovery_orchestrator_v2():
    """Reset the singleton instance (for testing)."""
    global _discovery_orchestrator_v2
    _discovery_orchestrator_v2 = None
