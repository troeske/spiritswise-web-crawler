"""
Fuzzy Matcher - Name matching for skeleton-to-crawled product matching.

Uses fuzzywuzzy for fuzzy string matching to connect skeleton products
(created from competition data) with crawled product data.

Default threshold: 85% similarity
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from fuzzywuzzy import fuzz
from django.db import transaction

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
)

logger = logging.getLogger(__name__)

# Default similarity threshold (85%)
DEFAULT_THRESHOLD = 85


class SkeletonMatcher:
    """
    Matcher for connecting skeleton products with crawled data.

    Uses fuzzy string matching to find skeleton products that match
    crawled product names, then enriches them with the crawled data.
    """

    def __init__(self, threshold: int = DEFAULT_THRESHOLD):
        """
        Initialize skeleton matcher.

        Args:
            threshold: Minimum similarity score for a match (0-100)
        """
        self.threshold = threshold

    def calculate_similarity(
        self,
        skeleton_name: str,
        crawled_name: str,
    ) -> int:
        """
        Calculate similarity score between skeleton and crawled product names.

        Uses multiple fuzzy matching strategies and returns the best score.

        Args:
            skeleton_name: Name from skeleton product (competition data)
            crawled_name: Name from crawled product page

        Returns:
            Similarity score (0-100)
        """
        # Normalize names for comparison
        norm_skeleton = self._normalize_name(skeleton_name)
        norm_crawled = self._normalize_name(crawled_name)

        # Calculate various similarity scores
        scores = [
            fuzz.ratio(norm_skeleton, norm_crawled),
            fuzz.partial_ratio(norm_skeleton, norm_crawled),
            fuzz.token_sort_ratio(norm_skeleton, norm_crawled),
            fuzz.token_set_ratio(norm_skeleton, norm_crawled),
        ]

        # Return the best score
        return max(scores)

    def _normalize_name(self, name: str) -> str:
        """
        Normalize product name for comparison.

        Handles common variations in whiskey naming:
        - "Year Old" variations
        - "Single Malt" prefix/suffix
        - Case normalization
        - Extra whitespace
        """
        if not name:
            return ""

        normalized = name.lower().strip()

        # Remove common suffixes/prefixes
        removals = [
            "single malt",
            "single malt scotch",
            "single malt whisky",
            "single malt whiskey",
            "scotch whisky",
            "scotch whiskey",
            "blended scotch",
            "blended whisky",
            "blended whiskey",
            "irish whiskey",
            "irish whisky",
            "bourbon whiskey",
            "bourbon",
            "rye whiskey",
            "rye whisky",
            "japanese whisky",
            "japanese whiskey",
        ]

        for removal in removals:
            normalized = normalized.replace(removal, "")

        # Normalize "year old" variations
        normalized = re.sub(r"(\d+)\s*y\.?o\.?", r"\1 year old", normalized)
        normalized = re.sub(r"(\d+)\s*years?\s*old", r"\1 year old", normalized)

        # Remove special characters except spaces
        normalized = re.sub(r"[^\w\s]", "", normalized)

        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def find_matching_skeleton(
        self,
        crawled_name: str,
        candidates: Optional[List[DiscoveredProduct]] = None,
    ) -> Optional[Tuple[DiscoveredProduct, int]]:
        """
        Find a skeleton product that matches the crawled name.

        Args:
            crawled_name: Name from crawled product page
            candidates: Optional list of candidate skeletons (defaults to all)

        Returns:
            Tuple of (matching skeleton, similarity score) or None
        """
        if candidates is None:
            candidates = DiscoveredProduct.objects.filter(
                status=DiscoveredProductStatus.SKELETON,
                discovery_source=DiscoverySource.COMPETITION,
            )

        best_match = None
        best_score = 0

        for skeleton in candidates:
            # Use individual column instead of extracted_data
            skeleton_name = skeleton.name or ""
            if not skeleton_name:
                continue

            score = self.calculate_similarity(skeleton_name, crawled_name)

            if score >= self.threshold and score > best_score:
                best_match = skeleton
                best_score = score

        if best_match:
            logger.info(
                f"Found skeleton match: '{best_match.name}' "
                f"matches '{crawled_name}' with score {best_score}"
            )
            return (best_match, best_score)

        return None

    def match_and_enrich(
        self,
        skeleton: DiscoveredProduct,
        crawled_name: str,
        enriched_data: Dict[str, Any],
        source_url: str = "",
    ) -> bool:
        """
        Check if crawled data matches skeleton, and enrich if it does.

        Args:
            skeleton: Skeleton product to potentially enrich
            crawled_name: Name from crawled product page
            enriched_data: Data extracted from crawled page
            source_url: URL of the crawled page

        Returns:
            True if match was found and skeleton was enriched, False otherwise
        """
        skeleton_name = skeleton.name or ""
        score = self.calculate_similarity(skeleton_name, crawled_name)

        if score < self.threshold:
            logger.debug(
                f"No match: '{skeleton_name}' vs '{crawled_name}' (score: {score})"
            )
            return False

        # Match found - enrich the skeleton with individual columns
        with transaction.atomic():
            # Update individual fields from enriched data
            if enriched_data.get("name") and not skeleton.name:
                skeleton.name = enriched_data["name"]
            if enriched_data.get("description") and not skeleton.description:
                skeleton.description = enriched_data["description"]
            if enriched_data.get("volume_ml") and not skeleton.volume_ml:
                skeleton.volume_ml = enriched_data["volume_ml"]
            if enriched_data.get("abv") and not skeleton.abv:
                skeleton.abv = enriched_data["abv"]
            if enriched_data.get("nose_description") and not skeleton.nose_description:
                skeleton.nose_description = enriched_data["nose_description"]
            if enriched_data.get("palate_description") and not skeleton.palate_description:
                skeleton.palate_description = enriched_data["palate_description"]
            if enriched_data.get("finish_description") and not skeleton.finish_description:
                skeleton.finish_description = enriched_data["finish_description"]

            # Set source URL if provided
            if source_url:
                skeleton.source_url = source_url

            # Update match confidence
            skeleton.match_confidence = score / 100.0

            # Change status from skeleton to pending
            skeleton.status = DiscoveredProductStatus.PENDING

            # Recompute fingerprint from model fields
            skeleton.fingerprint = skeleton.compute_fingerprint_from_fields()

            skeleton.save()

        logger.info(
            f"Enriched skeleton '{skeleton_name}' from '{crawled_name}' "
            f"(score: {score}, status: pending)"
        )

        return True

    def batch_match_skeletons(
        self,
        crawled_products: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Match multiple crawled products against all skeletons.

        Args:
            crawled_products: List of dicts with 'name', 'data', 'url' keys

        Returns:
            Dictionary with match statistics and results
        """
        skeletons = list(
            DiscoveredProduct.objects.filter(
                status=DiscoveredProductStatus.SKELETON,
                discovery_source=DiscoverySource.COMPETITION,
            )
        )

        results = {
            "total_crawled": len(crawled_products),
            "total_skeletons": len(skeletons),
            "matches_found": 0,
            "matches": [],
        }

        for crawled in crawled_products:
            crawled_name = crawled.get("name", "")
            if not crawled_name:
                continue

            match_result = self.find_matching_skeleton(
                crawled_name=crawled_name,
                candidates=skeletons,
            )

            if match_result:
                skeleton, score = match_result
                success = self.match_and_enrich(
                    skeleton=skeleton,
                    crawled_name=crawled_name,
                    enriched_data=crawled.get("data", {}),
                    source_url=crawled.get("url", ""),
                )

                if success:
                    results["matches_found"] += 1
                    results["matches"].append({
                        "skeleton_name": skeleton.name,
                        "crawled_name": crawled_name,
                        "score": score,
                        "url": crawled.get("url"),
                    })

                    # Remove matched skeleton from candidates
                    skeletons = [s for s in skeletons if s.id != skeleton.id]

        logger.info(
            f"Batch matching complete: {results['matches_found']} matches "
            f"from {results['total_crawled']} crawled products"
        )

        return results


def find_and_enrich_skeleton(
    crawled_name: str,
    enriched_data: Dict[str, Any],
    source_url: str = "",
    threshold: int = DEFAULT_THRESHOLD,
) -> Optional[DiscoveredProduct]:
    """
    Convenience function to find and enrich a matching skeleton.

    Args:
        crawled_name: Name from crawled product page
        enriched_data: Data extracted from crawled page
        source_url: URL of the crawled page
        threshold: Minimum similarity score for a match

    Returns:
        Enriched DiscoveredProduct or None if no match found
    """
    matcher = SkeletonMatcher(threshold=threshold)
    match_result = matcher.find_matching_skeleton(crawled_name)

    if match_result:
        skeleton, score = match_result
        success = matcher.match_and_enrich(
            skeleton=skeleton,
            crawled_name=crawled_name,
            enriched_data=enriched_data,
            source_url=source_url,
        )
        if success:
            return skeleton

    return None
