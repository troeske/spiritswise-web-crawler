"""
Target URL Extractor - Extract and prioritize target URLs from search results.

Phase 3: Generic Search Discovery

Extracts URLs from SerpAPI search results, filters out excluded domains,
prioritizes high-value sources, and deduplicates across multiple searches.
"""

from typing import List, Dict, Any, Set
from urllib.parse import urlparse

from crawler.discovery.serpapi.parsers import OrganicResultParser
from .config import SearchConfig


class TargetURLExtractor:
    """
    Extract and prioritize target URLs from search results.

    Uses SearchConfig to filter domains and prioritize results.
    Tracks seen URLs to avoid duplicate extraction across searches.

    Usage:
        config = SearchConfig()
        extractor = TargetURLExtractor(config)
        targets = extractor.extract_targets(search_results)
    """

    def __init__(self, config: SearchConfig):
        """
        Initialize target URL extractor.

        Args:
            config: SearchConfig instance for domain filtering
        """
        self.config = config
        self.organic_parser = OrganicResultParser()
        self._seen_urls: Set[str] = set()

    def extract_targets(
        self,
        search_results: Dict[str, Any],
        max_targets: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Extract target URLs from search results.

        Args:
            search_results: SerpAPI response dictionary
            max_targets: Maximum targets to return

        Returns:
            List of targets with url, title, snippet, source, priority, position
        """
        targets = []

        # Parse organic results
        organic = self.organic_parser.parse(search_results)

        for result in organic:
            url = result.get("url", "")

            # Skip empty or already seen URLs
            if not url or url in self._seen_urls:
                continue

            domain = self._extract_domain(url)

            # Skip excluded domains
            if self.config.is_excluded_domain(domain):
                continue

            # Calculate priority score
            priority = self._calculate_priority(result, domain)

            target = {
                "url": url,
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "source": domain,
                "priority": priority,
                "position": result.get("position", 0),
            }

            targets.append(target)
            self._seen_urls.add(url)

        # Sort by priority (descending) and limit
        targets.sort(key=lambda x: x["priority"], reverse=True)
        return targets[:max_targets]

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL string

        Returns:
            Domain name without www prefix
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            domain = parsed.netloc or ""
            return domain.replace("www.", "")
        except Exception:
            return ""

    def _calculate_priority(
        self,
        result: Dict[str, Any],
        domain: str,
    ) -> int:
        """
        Calculate priority score for a target.

        Factors:
        - Base priority: 50
        - Priority domain: +30
        - Search position: +20 to 0 (higher positions get more)
        - Product words in snippet: +5 each

        Args:
            result: Parsed search result
            domain: Extracted domain name

        Returns:
            Priority score (higher is better)
        """
        priority = 50  # Base priority

        # Boost priority domains
        if self.config.is_priority_domain(domain):
            priority += 30

        # Boost higher search positions
        position = result.get("position", 10)
        position_boost = max(0, 20 - position * 2)
        priority += position_boost

        # Boost if snippet contains product indicators
        snippet = (result.get("snippet", "") or "").lower()
        product_words = ["review", "rating", "score", "tasting", "best", "top"]
        for word in product_words:
            if word in snippet:
                priority += 5

        return priority

    def deduplicate_across_searches(
        self,
        all_targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate targets from multiple searches.

        Keeps first occurrence of each URL.

        Args:
            all_targets: List of all targets from multiple searches

        Returns:
            List of unique targets
        """
        seen = set()
        unique = []

        for target in all_targets:
            url = target.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(target)

        return unique

    def clear_seen_cache(self):
        """Clear the seen URLs cache."""
        self._seen_urls.clear()
