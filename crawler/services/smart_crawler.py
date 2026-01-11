"""
Smart Crawler Service with SerpAPI Fallback.

This module implements an intelligent crawling strategy:
1. Primary source (competition site or retailer) for initial extraction
2. Name validation to detect wrong-product extraction
3. SerpAPI fallback to find better sources when needed
4. Preference for official brand websites
5. CrawledSource cache to avoid redundant API calls
6. Multi-source extraction with conflict detection

Phase 10 Updates (Unified Pipeline):
- extract_from_url(url) method for API
- extract_from_urls_parallel(urls) method for batch processing
- Auto-detect page type (list vs single)
"""

import hashlib
import logging
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Content extraction library for cleaner text
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

logger = logging.getLogger(__name__)

# SerpAPI configuration - Task 3 fix: Use environment variable instead of hardcoded key
SERPAPI_KEY = os.environ.get('SERPAPI_API_KEY', '')

# Trusted domains ranked by preference (lower index = higher preference)
# Official brand sites are discovered dynamically and get highest priority
TRUSTED_RETAILER_DOMAINS = [
    "masterofmalt.com",
    "whisky.com",
    "totalwine.com",
    "wine.com",
    "drizly.com",
    "reservebar.com",
    "caskers.com",
    "flaviar.com",
    "klwines.com",
    "binnys.com",
    "astorwines.com",
    "thewhiskyexchange.com",  # Lower priority due to related products issue
]

# Domains to skip (often have bot protection or poor content)
SKIP_DOMAINS = [
    "amazon.com",
    "ebay.com",
    "walmart.com",
    "target.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "youtube.com",
    "reddit.com",
    "pinterest.com",
]

# Known official brand domains (extracted products from these are authoritative)
OFFICIAL_BRAND_DOMAINS = [
    "ardbeg.com",
    "lagavulin.com",
    "obanwhisky.com",
    "talisker.com",
    "bulleit.com",
    "elijahcraig.com",
    "makersmark.com",
    "wildturkeybourbon.com",
    "buffalotracedistillery.com",
    "fourrosebourbon.com",
    "jimbeam.com",
    "woodfordreserve.com",
    "jackdaniels.com",
    "heavenhilldistillery.com",
    "grahams-port.com",
    "taylor.pt",
    "dows-port.com",
    "fonseca.pt",
    "sandeman.com",
    "warre.pt",
]

# Patterns for detecting list pages vs single product pages
LIST_PAGE_INDICATORS = [
    r'search[-_]?results',
    r'product[-_]?list',
    r'product[-_]?grid',
    r'results[-_]?page',
    r'category[-_]?page',
    r'<div[^>]*class="[^"]*product[-_]?card[^"]*"[^>]*>.*<div[^>]*class="[^"]*product[-_]?card',
    r'pagination',
    r'page[-_]?nav',
    r'showing\s+\d+\s+(of|to)\s+\d+',
]

SINGLE_PAGE_INDICATORS = [
    r'product[-_]?detail',
    r'product[-_]?page',
    r'add[-_]?to[-_]?cart',
    r'buy[-_]?now',
    r'<h1[^>]*>.*?(whisky|whiskey|bourbon|port|wine)',
    r'abv|alcohol\s+by\s+volume',
    r'tasting[-_]?notes',
]


@dataclass
class CrawlResult:
    """Result from smart crawling."""
    success: bool
    source_url: str
    source_type: str  # 'primary', 'serpapi_official', 'serpapi_retailer'
    content: Optional[str] = None
    error: Optional[str] = None
    search_attempts: int = 0
    urls_tried: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result from extraction with validation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    source_url: str = ""
    source_type: str = ""  # 'single', 'list', 'primary', etc.
    name_match_score: float = 0.0
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sources_used: int = 1  # Number of sources merged
    conflicts: List[Dict] = field(default_factory=list)  # Conflict details
    is_list_page: bool = False  # True if this is a product listing page
    product_urls: List[str] = field(default_factory=list)  # URLs from list pages


class SmartCrawler:
    """
    Intelligent crawler with automatic source switching.

    Features:
    - Primary source crawling
    - Name validation against expected product
    - SerpAPI fallback for better sources
    - Official brand website preference
    - Partial extraction with review flags
    - CrawledSource caching to avoid redundant API calls
    - Multi-source extraction with conflict detection
    - Page type auto-detection (list vs single product)
    - Parallel URL extraction
    """

    def __init__(self, scrapingbee_client, ai_client):
        """
        Initialize smart crawler.

        Args:
            scrapingbee_client: ScrapingBee client for web crawling
            ai_client: AI Enhancement Service client for extraction
        """
        self.crawler = scrapingbee_client
        self.ai_client = ai_client
        self.serpapi_key = SERPAPI_KEY

    def _check_crawled_source(self, url: str) -> Optional[str]:
        """
        Check if URL has cached content in CrawledSource.

        Only returns content if:
        - URL exists in CrawledSource
        - extraction_status is 'processed' or 'needs_review' (successful extractions)
        - raw_content is not empty

        Args:
            url: The URL to check for cached content

        Returns:
            Cached content string if available, None otherwise
        """
        from crawler.models import CrawledSource, ExtractionStatusChoices

        # Only use cache for successful extractions (processed or needs_review)
        # Do not use cache for failed or pending - we should re-crawl those
        existing = CrawledSource.objects.filter(
            url=url,
            extraction_status__in=[
                ExtractionStatusChoices.PROCESSED,
                ExtractionStatusChoices.NEEDS_REVIEW,
            ]
        ).first()

        if existing and existing.raw_content:
            return existing.raw_content

        return None

    def _save_to_crawled_source(self, url: str, content: str) -> None:
        """
        Save crawled content to CrawledSource for future reuse.

        Creates a new record or updates existing one with fresh content.
        Content is truncated to 500KB to prevent database bloat.

        Args:
            url: The URL that was crawled
            content: The raw HTML content from the crawl
        """
        from crawler.models import (
            CrawledSource,
            CrawledSourceTypeChoices,
            ExtractionStatusChoices,
        )

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Truncate content to 500KB max
        truncated_content = content[:500000]

        # Extract a simple title from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        title = parsed.path.split('/')[-1] or parsed.netloc
        title = title[:100]  # Limit title length

        # Determine source type based on URL
        domain = self._extract_domain(url)
        if any(official in domain for official in OFFICIAL_BRAND_DOMAINS):
            source_type = CrawledSourceTypeChoices.DISTILLERY_PAGE
        else:
            source_type = CrawledSourceTypeChoices.RETAILER_PAGE

        # Update or create the CrawledSource record
        CrawledSource.objects.update_or_create(
            url=url,
            defaults={
                'title': title,
                'raw_content': truncated_content,
                'content_hash': content_hash,
                'extraction_status': ExtractionStatusChoices.PENDING,
                'source_type': source_type,
            }
        )

        logger.debug(f"Saved crawled content to CrawledSource: {url[:60]}...")

    # ================================================================
    # Phase 10: New API Methods
    # ================================================================

    def extract_from_url(self, url: str, product_type: str = "whiskey") -> ExtractionResult:
        """
        Extract product data from a single URL for API use.

        Auto-detects whether the page is a single product page or a listing page.
        For single pages, extracts product data.
        For list pages, returns product URLs for batch processing.

        Args:
            url: URL to extract from
            product_type: Product type hint ('whiskey', 'port_wine', etc.)

        Returns:
            ExtractionResult with extracted data or list page info
        """
        result = ExtractionResult(
            success=False,
            source_url=url,
            source_type="",
            errors=[],
        )

        try:
            # Step 1: Fetch the page content
            crawl_result = self.crawler.fetch_page(url, render_js=True)

            if not crawl_result.get("success"):
                result.errors.append(crawl_result.get("error", "Crawl failed"))
                return result

            content = crawl_result.get("content", "")

            # Step 2: Detect page type
            page_type = self.detect_page_type(content)
            result.source_type = page_type

            if page_type == "list":
                # List page - extract product URLs
                result.is_list_page = True
                result.product_urls = self._extract_product_urls(content, url)
                result.success = True
                result.data = {
                    "is_list_page": True,
                    "product_urls": result.product_urls,
                    "url_count": len(result.product_urls),
                }
            else:
                # Single product page - extract data
                content = self._trim_content(content)

                # Save for cache
                self._save_to_crawled_source(url, content)

                # Extract via AI
                enhance_result = self.ai_client.enhance_from_crawler(
                    content=content,
                    source_url=url,
                    product_type_hint=product_type
                )

                if enhance_result.get("success"):
                    result.success = True
                    result.data = enhance_result.get("data", {})
                    result.source_type = "single"
                else:
                    result.errors.append(enhance_result.get("error", "Extraction failed"))

        except Exception as e:
            logger.error(f"extract_from_url failed for {url}: {e}")
            result.errors.append(str(e))

        return result

    def extract_from_urls_parallel(
        self,
        urls: List[str],
        product_type: str = "whiskey",
        max_workers: int = 5,
    ) -> List[ExtractionResult]:
        """
        Extract product data from multiple URLs in parallel.

        Uses ThreadPoolExecutor for concurrent extraction with configurable
        worker count.

        Args:
            urls: List of URLs to extract from
            product_type: Product type hint
            max_workers: Maximum number of parallel workers (default 5)

        Returns:
            List of ExtractionResult, one per URL
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all extraction tasks
            future_to_url = {
                executor.submit(self.extract_from_url, url, product_type): url
                for url in urls
            }

            # Collect results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Parallel extraction failed for {url}: {e}")
                    results.append(ExtractionResult(
                        success=False,
                        source_url=url,
                        source_type="error",
                        errors=[str(e)],
                    ))

        return results

    def detect_page_type(self, html_content: str) -> str:
        """
        Auto-detect whether a page is a product listing or single product page.

        Uses pattern matching on HTML content to determine page type.

        Args:
            html_content: Raw HTML content of the page

        Returns:
            'list' for listing/search results pages
            'single' for single product detail pages
        """
        html_lower = html_content.lower()

        # Count matches for each type
        list_score = 0
        single_score = 0

        for pattern in LIST_PAGE_INDICATORS:
            if re.search(pattern, html_lower, re.IGNORECASE | re.DOTALL):
                list_score += 1

        for pattern in SINGLE_PAGE_INDICATORS:
            if re.search(pattern, html_lower, re.IGNORECASE | re.DOTALL):
                single_score += 1

        # Count product cards (strong list indicator)
        product_cards = len(re.findall(
            r'<div[^>]*class="[^"]*product[-_]?card[^"]*"',
            html_content,
            re.IGNORECASE
        ))
        if product_cards >= 3:
            list_score += 3

        # Check for pagination (strong list indicator)
        if re.search(r'page\s*\d+\s*of\s*\d+', html_lower):
            list_score += 2

        # Add to cart button (strong single indicator)
        if re.search(r'add[-_\s]?to[-_\s]?cart|buy[-_\s]?now', html_lower):
            single_score += 2

        logger.debug(
            f"Page type detection: list_score={list_score}, single_score={single_score}"
        )

        if list_score > single_score:
            return "list"
        return "single"

    def _extract_product_urls(self, html_content: str, base_url: str) -> List[str]:
        """
        Extract product URLs from a listing page.

        Looks for product links in common listing patterns.

        Args:
            html_content: HTML content of the listing page
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute product URLs
        """
        from urllib.parse import urljoin

        urls = []
        seen = set()

        # Pattern 1: Links inside product cards
        card_links = re.findall(
            r'<div[^>]*class="[^"]*product[-_]?card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"',
            html_content,
            re.IGNORECASE | re.DOTALL
        )
        for href in card_links:
            abs_url = urljoin(base_url, href)
            if abs_url not in seen:
                seen.add(abs_url)
                urls.append(abs_url)

        # Pattern 2: Links with product in class or id
        product_links = re.findall(
            r'<a[^>]*(?:class|id)="[^"]*product[^"]*"[^>]*href="([^"]+)"',
            html_content,
            re.IGNORECASE
        )
        for href in product_links:
            abs_url = urljoin(base_url, href)
            if abs_url not in seen:
                seen.add(abs_url)
                urls.append(abs_url)

        # Pattern 3: Links with /product/ in URL
        all_links = re.findall(r'href="([^"]+/product[s]?/[^"]+)"', html_content, re.IGNORECASE)
        for href in all_links:
            abs_url = urljoin(base_url, href)
            if abs_url not in seen:
                seen.add(abs_url)
                urls.append(abs_url)

        return urls[:50]  # Limit to 50 products

    # ================================================================
    # Original Methods (maintained for backward compatibility)
    # ================================================================

    def extract_product(
        self,
        expected_name: str,
        product_type: str,
        primary_url: Optional[str] = None,
        award_info: Optional[Dict] = None,
        name_match_threshold: float = 0.6
    ) -> ExtractionResult:
        """
        Extract product with smart source selection.

        Args:
            expected_name: Expected product name (from competition site or user)
            product_type: 'whiskey' or 'port_wine'
            primary_url: Optional primary URL to try first
            award_info: Optional award information to merge
            name_match_threshold: Minimum name similarity (0-1) to accept

        Returns:
            ExtractionResult with extracted data or errors
        """
        result = ExtractionResult(success=False, source_url="", source_type="")
        urls_tried = []

        # Step 1: Try primary URL if provided
        if primary_url:
            logger.info(f"Trying primary URL: {primary_url}")
            extraction = self._try_extraction(primary_url, product_type)
            urls_tried.append(primary_url)

            if extraction["success"]:
                # Get name from flat structure (individual columns, not extracted_data blob)
                extracted_name = extraction.get("data", {}).get("name", "")
                match_score = self._name_similarity(expected_name, extracted_name)

                logger.info(f"Primary extraction: '{extracted_name}' vs expected '{expected_name}' = {match_score:.2f}")

                if match_score >= name_match_threshold:
                    # Good match - use this extraction
                    result.success = True
                    result.data = extraction["data"]
                    result.source_url = primary_url
                    result.source_type = "primary"
                    result.name_match_score = match_score

                    # Merge award info if provided
                    if award_info:
                        result.data = self._merge_award_info(result.data, award_info)

                    return result
                else:
                    # Name mismatch - need to find better source
                    logger.warning(f"Name mismatch ({match_score:.2f} < {name_match_threshold}), searching for better source")

        # Step 2: Search for better sources via SerpAPI
        logger.info(f"Searching for: {expected_name}")
        search_urls = self._search_product(expected_name, product_type)

        # Step 3: Try each URL until we get a good match
        for url in search_urls:
            if url in urls_tried:
                continue

            urls_tried.append(url)
            source_type = self._classify_source(url)

            logger.info(f"Trying {source_type}: {url[:60]}...")
            extraction = self._try_extraction(url, product_type)

            if extraction["success"]:
                # Get name from flat structure (individual columns, not extracted_data blob)
                extracted_name = extraction.get("data", {}).get("name", "")
                match_score = self._name_similarity(expected_name, extracted_name)

                logger.info(f"Extraction: '{extracted_name}' = {match_score:.2f} match")

                if match_score >= name_match_threshold:
                    result.success = True
                    result.data = extraction["data"]
                    result.source_url = url
                    result.source_type = source_type
                    result.name_match_score = match_score

                    # Merge award info if provided
                    if award_info:
                        result.data = self._merge_award_info(result.data, award_info)

                    return result
                elif match_score >= 0.4:
                    # Partial match - save as fallback but keep looking
                    if not result.data:
                        result.data = extraction["data"]
                        result.source_url = url
                        result.source_type = source_type
                        result.name_match_score = match_score
                        result.needs_review = True
                        result.review_reasons.append(
                            f"Name match score {match_score:.2f} below threshold {name_match_threshold}"
                        )

        # Step 4: Return best result (even if needs review)
        if result.data:
            result.success = True
            if award_info:
                result.data = self._merge_award_info(result.data, award_info)
        else:
            result.errors.append(f"Could not extract from any source. Tried {len(urls_tried)} URLs.")

        return result

    def extract_product_multi_source(
        self,
        expected_name: str,
        product_type: str,
        primary_url: Optional[str] = None,
        award_info: Optional[Dict] = None,
        max_sources: int = 3,
        name_match_threshold: float = 0.6
    ) -> ExtractionResult:
        """
        Extract from multiple sources and merge results.

        This is an enhanced version of extract_product() that:
        1. Collects data from up to max_sources
        2. Merges non-conflicting fields
        3. Flags conflicts for human review

        Args:
            expected_name: Expected product name
            product_type: 'whiskey' or 'port_wine'
            primary_url: Optional primary URL to try first
            award_info: Optional award information to merge
            max_sources: Maximum number of sources to use (default 3)
            name_match_threshold: Minimum name similarity (0-1)

        Returns:
            ExtractionResult with merged data from multiple sources
        """
        result = ExtractionResult(success=False, source_url="", source_type="")
        successful_extractions = []
        urls_tried = []

        # Step 1: Build list of candidate URLs
        search_urls = []
        if primary_url:
            search_urls.append(primary_url)

        # Add SerpAPI results
        serpapi_urls = self._search_product(expected_name, product_type)
        for url in serpapi_urls:
            if url not in search_urls:
                search_urls.append(url)

        # Step 2: Try each URL until we have enough successful extractions
        for url in search_urls:
            if len(successful_extractions) >= max_sources:
                break

            if url in urls_tried:
                continue

            urls_tried.append(url)
            extraction = self._try_extraction(url, product_type)

            if extraction.get("success"):
                # Get name from flat structure (individual columns, not extracted_data blob)
                extracted_name = extraction.get("data", {}).get("name", "")
                match_score = self._name_similarity(expected_name, extracted_name)

                if match_score >= name_match_threshold:
                    successful_extractions.append({
                        "url": url,
                        "data": extraction["data"],
                        "match_score": match_score,
                        "source_type": self._classify_source(url),
                    })
                    logger.info(f"Good extraction from {url}: {extracted_name} ({match_score:.2f})")

        # Step 3: Handle results
        if not successful_extractions:
            result.errors.append(f"No sources matched. Tried {len(urls_tried)} URLs.")
            return result

        if len(successful_extractions) == 1:
            # Single source - no merge needed
            ext = successful_extractions[0]
            result.success = True
            result.data = ext["data"]
            result.source_url = ext["url"]
            result.source_type = ext["source_type"]
            result.name_match_score = ext["match_score"]
            result.sources_used = 1
        else:
            # Multiple sources - merge
            merged = self._merge_extractions(successful_extractions)
            result.success = True
            result.data = merged["data"]
            result.source_url = successful_extractions[0]["url"]  # Primary source
            result.source_type = "multi_source"
            result.name_match_score = max(e["match_score"] for e in successful_extractions)
            result.needs_review = merged.get("has_conflicts", False)
            result.sources_used = merged.get("sources_used", len(successful_extractions))
            result.conflicts = merged.get("conflicts", [])
            if merged.get("conflicts"):
                result.review_reasons.extend([
                    f"Conflict: {c['field']}" for c in merged["conflicts"]
                ])

        # Merge award info if provided
        if award_info and result.data:
            result.data = self._merge_award_info(result.data, award_info)

        return result

    def _merge_extractions(self, extractions: List[Dict]) -> Dict:
        """
        Merge multiple extractions, detecting conflicts.

        Strategy:
        - For non-list fields: use first non-empty value, flag if different
        - For list fields (awards, ratings, images): combine without duplicates

        Args:
            extractions: List of extraction dicts with url, data, match_score

        Returns:
            Dict with merged data, conflict info, and source count
        """
        if not extractions:
            return {"data": {}, "has_conflicts": False, "conflicts": [], "sources_used": 0}

        # Use flat structure (individual columns, not extracted_data blob)
        merged_data = {}
        conflicts = []

        # Fields to check for conflicts (scalar fields)
        scalar_fields = [
            "name", "brand", "abv", "age_statement", "volume_ml", "price",
            "region", "country", "distillery", "bottler", "description",
        ]

        # Tasting profile fields
        tasting_fields = [
            "nose_description", "palate_description", "finish_description",
            "color_description",
        ]

        # List fields to merge (combine without duplicates)
        list_fields = ["awards", "ratings", "images", "primary_aromas", "palate_flavors"]

        # Merge scalar fields (using flat structure, not extracted_data blob)
        for field_name in scalar_fields + tasting_fields:
            values = []
            for ext in extractions:
                # Get from flat structure (individual columns)
                val = ext.get("data", {}).get(field_name)
                if val is not None and val != "":
                    values.append({"source": ext["url"], "value": val})

            if values:
                # Use first value - store directly in merged_data (flat structure)
                merged_data[field_name] = values[0]["value"]

                # Check for conflicts
                unique_values = set(str(v["value"]).lower().strip() for v in values)
                if len(unique_values) > 1:
                    conflicts.append({
                        "field": field_name,
                        "values": values,
                        "chosen": values[0]["value"],
                        "reason": "Used value from primary source",
                    })

        # Merge list fields (combine without duplicates, using flat structure)
        for field_name in list_fields:
            combined = []
            seen = set()

            for ext in extractions:
                # Get from flat structure (individual columns)
                items = ext.get("data", {}).get(field_name, [])
                if isinstance(items, list):
                    for item in items:
                        # For dicts, use JSON key for dedup
                        if isinstance(item, dict):
                            key = str(sorted(item.items()))
                        else:
                            key = str(item)

                        if key not in seen:
                            seen.add(key)
                            combined.append(item)

            if combined:
                # Store directly in merged_data (flat structure)
                merged_data[field_name] = combined

        # Copy other fields from first extraction that weren't already merged
        for key, value in extractions[0].get("data", {}).items():
            if key not in merged_data:
                merged_data[key] = value

        return {
            "data": merged_data,
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "sources_used": len(extractions),
        }

    def _search_product(self, product_name: str, product_type: str) -> List[str]:
        """Search for product URLs using SerpAPI."""
        # Build search query - prefer official sites
        if product_type == "port_wine":
            query = f"{product_name} port wine official"
        else:
            query = f"{product_name} whiskey official"

        try:
            params = {
                "q": query,
                "api_key": self.serpapi_key,
                "engine": "google",
                "num": 15,
            }

            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Collect and rank URLs
            urls_with_priority = []

            for result in data.get("organic_results", []):
                url = result.get("link", "")
                domain = self._extract_domain(url)

                # Skip unwanted domains
                if any(skip in domain for skip in SKIP_DOMAINS):
                    continue

                # Determine priority (lower = better)
                priority = 100

                # Official brand domains get highest priority
                if any(official in domain for official in OFFICIAL_BRAND_DOMAINS):
                    priority = 0
                # Domains with brand name in them (likely official)
                elif any(word.lower() in domain for word in product_name.split()[:2]):
                    priority = 5
                # Trusted retailers
                elif domain in TRUSTED_RETAILER_DOMAINS:
                    priority = 10 + TRUSTED_RETAILER_DOMAINS.index(domain)
                # Other domains
                else:
                    priority = 50

                urls_with_priority.append((url, priority))

            # Sort by priority and return URLs
            urls_with_priority.sort(key=lambda x: x[1])
            urls = [url for url, _ in urls_with_priority]

            logger.info(f"SerpAPI found {len(urls)} URLs for '{product_name}'")
            return urls[:10]  # Limit to top 10

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []

    def _try_extraction(self, url: str, product_type: str) -> Dict:
        """
        Try to crawl and extract from a URL.

        Uses CrawledSource cache to avoid redundant ScrapingBee API calls.
        Only re-crawls if:
        - URL not in cache
        - Previous extraction failed or is pending
        - Cached content is empty

        Args:
            url: URL to crawl and extract from
            product_type: 'whiskey' or 'port_wine'

        Returns:
            Dict with success status, data, and error info
        """
        try:
            # Check cache first
            cached_content = self._check_crawled_source(url)

            if cached_content:
                logger.info(f"Using cached content for {url[:60]}...")
                content = self._trim_content(cached_content)
            else:
                # Crawl (no cache hit)
                crawl_result = self.crawler.fetch_page(url, render_js=True)

                if not crawl_result["success"]:
                    return {
                        "success": False,
                        "error": crawl_result.get("error", "Crawl failed")
                    }

                content = self._trim_content(crawl_result["content"])

                # Save for future reuse
                self._save_to_crawled_source(url, crawl_result["content"])

            # Extract (same for both cached and fresh)
            enhance_result = self.ai_client.enhance_from_crawler(
                content=content,
                source_url=url,
                product_type_hint=product_type
            )

            return enhance_result

        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            return {"success": False, "error": str(e)}

    def _trim_content(self, content: str) -> str:
        """
        Extract clean text content from HTML for AI processing.

        Strategy:
        1. First try to extract product-specific elements (most reliable)
        2. Fall back to trafilatura for general content extraction
        3. Use regex cleaning as last resort

        Target: <30k chars of clean, relevant text for fast AI processing.
        """
        original_len = len(content)

        # Step 0: Try to extract product-specific content first (most reliable)
        # This targets common e-commerce product page structures
        # Structured data (JSON-LD, OG tags) is high quality even when short
        product_content = self._extract_product_section(content)
        if product_content and len(product_content) > 100:
            # Clean up the product section
            product_content = re.sub(r'<script[^>]*>.*?</script>', '', product_content, flags=re.DOTALL | re.IGNORECASE)
            product_content = re.sub(r'<style[^>]*>.*?</style>', '', product_content, flags=re.DOTALL | re.IGNORECASE)
            product_content = re.sub(r'\s+', ' ', product_content)

            if len(product_content) > 30000:
                product_content = product_content[:30000]

            logger.debug(f"Product section extraction: {original_len} -> {len(product_content)} chars")
            return product_content

        # Step 1: Try trafilatura for intelligent extraction
        if TRAFILATURA_AVAILABLE and len(content) > 10000:
            try:
                # Extract main content with trafilatura
                extracted = trafilatura.extract(
                    content,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False,
                    favor_precision=False,  # Favor recall for product data
                    include_formatting=False,
                )

                # Check if extracted content looks like product content (not T&C, privacy policy, etc.)
                if extracted and len(extracted) > 500:
                    # Skip if it looks like legal/policy content
                    legal_patterns = ['terms and conditions', 'privacy policy', 'cookie policy', 'legal notice']
                    is_legal = any(p in extracted.lower()[:500] for p in legal_patterns)

                    if not is_legal:
                        logger.debug(
                            f"Trafilatura extraction: {original_len} -> {len(extracted)} chars"
                        )
                        # Add some HTML structure hints for AI
                        content = f"<extracted_content>\n{extracted}\n</extracted_content>"

                        # If still too large, truncate
                        if len(content) > 30000:
                            content = content[:30000]

                        return content
                    else:
                        logger.debug("Trafilatura extracted legal content, using fallback")
                else:
                    logger.debug("Trafilatura extraction too short, using fallback")
            except Exception as e:
                logger.warning(f"Trafilatura extraction failed: {e}")

        # Step 2: Fallback - regex-based cleaning
        # Remove scripts and styles
        content = re.sub(
            r'<script[^>]*>.*?</script>',
            '',
            content,
            flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r'<style[^>]*>.*?</style>',
            '',
            content,
            flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # Remove SVG and other noise
        content = re.sub(r'<svg[^>]*>.*?</svg>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', content, flags=re.DOTALL | re.IGNORECASE)

        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)

        # Try to extract product-relevant sections
        product_patterns = [
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*product[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*product[^"]*"[^>]*>(.*?)</div>',
        ]

        for pattern in product_patterns:
            match = re.search(pattern, content, flags=re.DOTALL | re.IGNORECASE)
            if match and len(match.group(1)) > 500:
                content = match.group(1)
                logger.debug(f"Extracted product section: {len(content)} chars")
                break

        # Final size limit
        if len(content) > 30000:
            content = content[:30000]

        logger.debug(f"Content trimmed: {original_len} -> {len(content)} chars")
        return content

    def _extract_product_section(self, html: str) -> Optional[str]:
        """
        Extract product-specific content from HTML.

        Strategy (prioritized by reliability):
        1. JSON-LD structured data (most reliable)
        2. Open Graph meta tags (very common, reliable)
        3. Title + meta description
        4. Product-specific HTML sections

        Returns combined content from multiple sources for best coverage.
        """
        parts = []

        # Source 1: Try JSON-LD structured data (most reliable)
        json_ld_match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            flags=re.DOTALL | re.IGNORECASE
        )
        if json_ld_match:
            try:
                import json
                data = json.loads(json_ld_match.group(1))
                # Handle array of schemas
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'Product':
                            data = item
                            break
                if data.get('@type') == 'Product':
                    if data.get('name'):
                        parts.append(f"Product Name: {data['name']}")
                    if data.get('brand', {}).get('name'):
                        parts.append(f"Brand: {data['brand']['name']}")
                    if data.get('description'):
                        parts.append(f"Description: {data['description']}")
                    if data.get('offers'):
                        offers = data['offers']
                        if isinstance(offers, list):
                            offers = offers[0]
                        if offers.get('price'):
                            parts.append(f"Price: {offers.get('priceCurrency', '')} {offers['price']}")
                    logger.debug(f"Extracted {len(parts)} fields from JSON-LD")
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Source 2: Open Graph meta tags (very common)
        og_patterns = [
            (r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', 'Product Name'),
            (r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', 'Description'),
            (r'<meta[^>]*property="og:price:amount"[^>]*content="([^"]+)"', 'Price'),
            (r'<meta[^>]*property="product:price:amount"[^>]*content="([^"]+)"', 'Price'),
            (r'<meta[^>]*property="product:brand"[^>]*content="([^"]+)"', 'Brand'),
        ]
        for pattern, label in og_patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                value = match.group(1)
                # Avoid duplicates
                if not any(label in p for p in parts):
                    parts.append(f"{label}: {value}")

        # Source 3: Title tag and meta description (fallback)
        if not any('Product Name' in p for p in parts):
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, flags=re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
                # Clean common suffixes
                title = re.sub(r'\s*[\|–-]\s*[^|–-]+$', '', title)
                parts.append(f"Product Name: {title}")

        if not any('Description' in p for p in parts):
            meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html, flags=re.IGNORECASE)
            if meta_desc:
                parts.append(f"Description: {meta_desc.group(1)}")

        # If we have structured data, return it (high quality)
        if len(parts) >= 2:
            content = '\n'.join(parts)
            logger.debug(f"Extracted structured product data: {len(content)} chars from {len(parts)} fields")
            return content

        # Source 4: Product HTML sections (less reliable, may contain noise)
        product_patterns = [
            (r'<div[^>]*class="[^"]*product-description[^"]*"[^>]*>(.*?)</div>', 'product-description'),
            (r'<div[^>]*class="[^"]*product-info[^"]*"[^>]*>(.*?)</div>', 'product-info'),
            (r'<div[^>]*class="[^"]*product-detail[^"]*"[^>]*>(.*?)</div>', 'product-detail'),
            (r'<article[^>]*>(.*?)</article>', 'article'),
        ]

        for pattern, name in product_patterns:
            match = re.search(pattern, html, flags=re.DOTALL | re.IGNORECASE)
            if match and len(match.group(1)) > 500:
                extracted = match.group(1)
                # Clean it up
                extracted = re.sub(r'<script[^>]*>.*?</script>', '', extracted, flags=re.DOTALL | re.IGNORECASE)
                extracted = re.sub(r'<style[^>]*>.*?</style>', '', extracted, flags=re.DOTALL | re.IGNORECASE)
                # Check it has text content
                text_only = re.sub(r'<[^>]+>', '', extracted)
                if len(text_only.strip()) > 200:
                    logger.debug(f"Found product section via '{name}': {len(extracted)} chars")
                    return '\n'.join(parts) + '\n\n' + extracted if parts else extracted

        return '\n'.join(parts) if parts else None

    def _name_similarity(self, expected: str, extracted: str) -> float:
        """Calculate similarity between expected and extracted names."""
        if not expected or not extracted:
            return 0.0

        # Normalize names
        def normalize(s):
            s = s.lower()
            # Remove common suffixes/prefixes
            s = re.sub(r'\b(whiskey|whisky|bourbon|scotch|single malt|port|tawny)\b', '', s)
            s = re.sub(r'\b(year|years|yr|yrs|old)\b', '', s)
            s = re.sub(r'[^\w\s]', '', s)
            s = ' '.join(s.split())
            return s

        norm_expected = normalize(expected)
        norm_extracted = normalize(extracted)

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, norm_expected, norm_extracted).ratio()

    def _classify_source(self, url: str) -> str:
        """Classify the source type of a URL."""
        domain = self._extract_domain(url)

        if any(official in domain for official in OFFICIAL_BRAND_DOMAINS):
            return "official_brand"
        elif domain in TRUSTED_RETAILER_DOMAINS:
            return "trusted_retailer"
        else:
            return "other"

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower().replace("www.", "")
        except:
            return ""

    def _merge_award_info(self, data: Dict, award_info: Dict) -> Dict:
        """Merge award information into extracted data (flat structure)."""
        if not data or not award_info:
            return data

        # Ensure awards list exists (flat structure, not nested in extracted_data)
        if "awards" not in data:
            data["awards"] = []

        # Add award if not already present
        new_award = {
            "competition": award_info.get("competition", ""),
            "year": award_info.get("year", 2025),
            "medal": award_info.get("medal", ""),
            "category": award_info.get("category"),
            "score": award_info.get("score"),
        }

        # Check if award already exists
        existing = False
        for award in data["awards"]:
            if (award.get("competition") == new_award["competition"] and
                award.get("year") == new_award["year"]):
                existing = True
                break

        if not existing and new_award["competition"] and new_award["medal"]:
            data["awards"].append(new_award)

        return data


def create_smart_crawler(scrapingbee_client, ai_client) -> SmartCrawler:
    """Factory function to create a SmartCrawler instance."""
    return SmartCrawler(scrapingbee_client, ai_client)
