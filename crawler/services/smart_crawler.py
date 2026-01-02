"""
Smart Crawler Service with SerpAPI Fallback.

This module implements an intelligent crawling strategy:
1. Primary source (competition site or retailer) for initial extraction
2. Name validation to detect wrong-product extraction
3. SerpAPI fallback to find better sources when needed
4. Preference for official brand websites
5. CrawledSource cache to avoid redundant API calls
6. Multi-source extraction with conflict detection
"""

import hashlib
import logging
import re
import requests
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# SerpAPI configuration
SERPAPI_KEY = "86dc430939860e8775ca38fe37b279b93b191f560f83b5a9b0b0f37dab3e697d"

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
    source_type: str = ""
    name_match_score: float = 0.0
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sources_used: int = 1  # Number of sources merged
    conflicts: List[Dict] = field(default_factory=list)  # Conflict details


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
                extracted_name = extraction["data"].get("extracted_data", {}).get("name", "")
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
                extracted_name = extraction["data"].get("extracted_data", {}).get("name", "")
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
                extracted_name = extraction.get("data", {}).get("extracted_data", {}).get("name", "")
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

        merged_data = {"extracted_data": {}}
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

        # Merge scalar fields
        for field_name in scalar_fields + tasting_fields:
            values = []
            for ext in extractions:
                val = ext.get("data", {}).get("extracted_data", {}).get(field_name)
                if val is not None and val != "":
                    values.append({"source": ext["url"], "value": val})

            if values:
                # Use first value
                merged_data["extracted_data"][field_name] = values[0]["value"]

                # Check for conflicts
                unique_values = set(str(v["value"]).lower().strip() for v in values)
                if len(unique_values) > 1:
                    conflicts.append({
                        "field": field_name,
                        "values": values,
                        "chosen": values[0]["value"],
                        "reason": "Used value from primary source",
                    })

        # Merge list fields (combine without duplicates)
        for field_name in list_fields:
            combined = []
            seen = set()

            for ext in extractions:
                items = ext.get("data", {}).get("extracted_data", {}).get(field_name, [])
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
                merged_data["extracted_data"][field_name] = combined

        # Copy other fields from first extraction
        for key, value in extractions[0].get("data", {}).items():
            if key != "extracted_data":
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
        """Trim content to fit API limits."""
        if len(content) > 90000:
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

            if len(content) > 90000:
                content = content[:90000]

        return content

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
        """Merge award information into extracted data."""
        if not data or not award_info:
            return data

        # Ensure awards list exists
        extracted = data.get("extracted_data", {})
        if "awards" not in extracted:
            extracted["awards"] = []

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
        for award in extracted["awards"]:
            if (award.get("competition") == new_award["competition"] and
                award.get("year") == new_award["year"]):
                existing = True
                break

        if not existing and new_award["competition"] and new_award["medal"]:
            extracted["awards"].append(new_award)

        data["extracted_data"] = extracted
        return data


def create_smart_crawler(scrapingbee_client, ai_client) -> SmartCrawler:
    """Factory function to create a SmartCrawler instance."""
    return SmartCrawler(scrapingbee_client, ai_client)
