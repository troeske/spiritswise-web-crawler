"""
Multi-Source Verification Pipeline

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md

This pipeline enriches products from multiple sources and verifies data consistency.

Note: This is a synchronous implementation because:
1. Django ORM is synchronous
2. SmartCrawler.extract_product() is synchronous
3. SerpAPIClient can be called synchronously via httpx
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result from verification pipeline."""

    product: Any
    sources_used: int
    verified_fields: List[str]
    conflicts: List[Dict]


class VerificationPipeline:
    """
    Pipeline that enriches products from multiple sources.
    Goal: Every product should be verified from 2+ sources before VERIFIED status.
    """

    TARGET_SOURCES = 3
    MIN_SOURCES_FOR_VERIFIED = 2

    ENRICHMENT_STRATEGIES = {
        "tasting_notes": [
            "{name} tasting notes review",
            "{name} nose palate finish",
            "{brand} {name} whisky review",
        ],
        "pricing": [
            "{name} buy price",
            "{name} whisky exchange price",
        ],
    }

    # Domains to exclude from search results
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

    def __init__(self):
        """Initialize the verification pipeline."""
        self._serpapi_client = None
        self._smart_crawler = None

    @property
    def serpapi_client(self):
        """Lazy-load SerpAPI client."""
        if self._serpapi_client is None:
            from crawler.discovery.serpapi_client import SerpAPIClient

            self._serpapi_client = SerpAPIClient()
        return self._serpapi_client

    @property
    def smart_crawler(self):
        """Lazy-load SmartCrawler."""
        if self._smart_crawler is None:
            from crawler.services.smart_crawler import SmartCrawler

            self._smart_crawler = SmartCrawler()
        return self._smart_crawler

    def verify_product(self, product) -> VerificationResult:
        """
        Main verification entry point.

        Steps:
        1. Save initial product (from first source)
        2. Identify missing/unverified fields
        3. Search for additional sources
        4. Extract data from each source
        5. Merge and verify data (if values match = verified)
        6. Update completeness and status
        """
        sources_used = product.source_count or 1
        conflicts = []

        missing = self._get_missing_critical_fields(product)
        needs_verification = self._get_unverified_fields(product)

        if missing or needs_verification or sources_used < self.TARGET_SOURCES:
            search_results = self._search_additional_sources(product, missing)

            for source_url in search_results[: self.TARGET_SOURCES - 1]:
                extraction = self._extract_from_source(source_url, product)
                if extraction and extraction.get("success"):
                    merge_conflicts = self._merge_and_verify(
                        product, extraction.get("data", {})
                    )
                    conflicts.extend(merge_conflicts)
                    sources_used += 1

        product.source_count = sources_used
        product.completeness_score = product.calculate_completeness_score()
        product.status = product.determine_status()
        product.save()

        return VerificationResult(
            product=product,
            sources_used=sources_used,
            verified_fields=list(product.verified_fields or []),
            conflicts=conflicts,
        )

    def _get_missing_critical_fields(self, product) -> List[str]:
        """
        Identify missing critical fields.
        Especially: palate, nose, finish, abv, description.
        """
        return product.get_missing_critical_fields()

    def _get_unverified_fields(self, product) -> List[str]:
        """Get fields that exist but aren't verified by 2+ sources."""
        verified = set(product.verified_fields or [])
        critical_fields = ["name", "abv", "country", "region", "palate_description"]

        unverified = []
        for field in critical_fields:
            if getattr(product, field, None) and field not in verified:
                unverified.append(field)

        return unverified

    def _select_strategy(self, missing_fields: List[str]) -> str:
        """Select the best enrichment strategy based on missing fields."""
        # If any tasting profile fields are missing, prioritize tasting_notes
        tasting_fields = {"palate", "nose", "finish"}
        if tasting_fields.intersection(set(missing_fields)):
            return "tasting_notes"

        # Default to tasting_notes as it's most comprehensive
        return "tasting_notes"

    def _format_query(self, template: str, product) -> str:
        """Format a query template with product information."""
        name = product.name or ""
        brand = ""
        if hasattr(product, "brand") and product.brand:
            brand = product.brand.name or ""

        return template.format(name=name, brand=brand)

    def _is_excluded_domain(self, domain: str) -> bool:
        """Check if a domain should be excluded from results."""
        domain_lower = domain.lower()
        return any(excluded in domain_lower for excluded in self.EXCLUDE_DOMAINS)

    def _execute_search(self, query: str) -> List[str]:
        """
        Execute a search query using SerpAPI synchronously.

        Args:
            query: Search query string

        Returns:
            List of URLs from search results
        """
        import asyncio

        try:
            # Run the async search in a new event loop
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(
                    self.serpapi_client.search(query=query, num_results=5)
                )
            finally:
                loop.close()

            urls = []
            seen_urls = set()

            for result in results:
                # Skip excluded domains
                if self._is_excluded_domain(result.domain):
                    continue

                # Skip duplicates
                if result.url in seen_urls:
                    continue

                seen_urls.add(result.url)
                urls.append(result.url)

            return urls

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def _search_additional_sources(
        self, product, missing_fields: List[str]
    ) -> List[str]:
        """
        Search for additional sources to fill missing fields.

        Uses ENRICHMENT_STRATEGIES patterns.

        Args:
            product: DiscoveredProduct to enrich
            missing_fields: List of missing field names

        Returns:
            List of URLs to extract from (max TARGET_SOURCES - 1)
        """
        all_urls = []
        seen_urls = set()

        # Select strategy based on missing fields
        strategy = self._select_strategy(missing_fields)
        templates = self.ENRICHMENT_STRATEGIES.get(strategy, [])

        # Try each template until we have enough URLs
        for template in templates:
            if len(all_urls) >= self.TARGET_SOURCES - 1:
                break

            query = self._format_query(template, product)

            try:
                urls = self._execute_search(query)

                for url in urls:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_urls.append(url)

                        if len(all_urls) >= self.TARGET_SOURCES - 1:
                            break

            except Exception as e:
                logger.error(f"Search failed for query '{query}': {e}")
                continue

        # Limit to TARGET_SOURCES - 1
        return all_urls[: self.TARGET_SOURCES - 1]

    def _execute_extraction(
        self, url: str, product
    ) -> Optional[Dict[str, Any]]:
        """
        Execute extraction from a URL using SmartCrawler.

        Args:
            url: URL to extract from
            product: Product for context (name, type)

        Returns:
            Dict with 'success' and 'data' keys, or None on failure
        """
        try:
            result = self.smart_crawler.extract_product(
                expected_name=product.name or "",
                product_type=product.product_type or "whiskey",
                primary_url=url,
            )

            if result.success:
                return {
                    "success": True,
                    "data": result.data or {},
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Extraction failed for '{url}': {e}")
            return None

    def _extract_from_source(
        self, source_url: str, product
    ) -> Optional[Dict[str, Any]]:
        """
        Extract data from a source URL.

        Returns dict with 'success' and 'data' keys, or None on failure.

        Args:
            source_url: URL to extract from
            product: DiscoveredProduct for context

        Returns:
            Dict with 'success' bool and 'data' dict, or None
        """
        try:
            result = self._execute_extraction(source_url, product)
            return result
        except Exception as e:
            logger.error(f"Extraction from {source_url} failed: {e}")
            return None

    def _merge_and_verify(
        self, product, extraction_data: Dict[str, Any]
    ) -> List[Dict]:
        """
        Merge new data, marking verified fields.
        If values match = field is verified!

        Returns list of conflicts found.
        """
        conflicts = []
        verified = list(product.verified_fields or [])

        for field, new_value in extraction_data.items():
            if not new_value:
                continue

            current_value = getattr(product, field, None)

            # Treat None and empty lists/strings as "missing"
            is_missing = (
                current_value is None
                or (isinstance(current_value, (list, str)) and len(current_value) == 0)
            )

            if is_missing:
                # Field was missing - add it
                setattr(product, field, new_value)
            elif product.values_match(current_value, new_value):
                # Values match - field is verified!
                if field not in verified:
                    verified.append(field)
            else:
                # Values differ - log conflict
                conflicts.append(
                    {
                        "field": field,
                        "current": current_value,
                        "new": new_value,
                    }
                )

        product.verified_fields = verified
        return conflicts
