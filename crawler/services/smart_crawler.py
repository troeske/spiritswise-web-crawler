"""
Smart Crawler Service with SerpAPI Fallback.

This module implements an intelligent crawling strategy:
1. Primary source (competition site or retailer) for initial extraction
2. Name validation to detect wrong-product extraction
3. SerpAPI fallback to find better sources when needed
4. Preference for official brand websites
"""

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


class SmartCrawler:
    """
    Intelligent crawler with automatic source switching.

    Features:
    - Primary source crawling
    - Name validation against expected product
    - SerpAPI fallback for better sources
    - Official brand website preference
    - Partial extraction with review flags
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
        """Try to crawl and extract from a URL."""
        try:
            # Crawl
            crawl_result = self.crawler.fetch_page(url, render_js=True)

            if not crawl_result["success"]:
                return {
                    "success": False,
                    "error": crawl_result.get("error", "Crawl failed")
                }

            # Trim content
            content = self._trim_content(crawl_result["content"])

            # Extract
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
