"""
Awards Handler Service.

Task 4.5: Implement Awards Deduplication

Handles:
- Award deduplication based on competition+year+medal
- Competition name normalization
- Medal name normalization
- Awards list merging

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 10.1
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AwardsHandler:
    """
    Handles awards deduplication and normalization.

    Deduplication key: (normalized_competition, year, normalized_medal)
    """

    # Competition name mappings for normalization
    COMPETITION_MAPPINGS = {
        # IWSC variations
        "iwsc": "iwsc",
        "international wine & spirit competition": "iwsc",
        "international wine and spirit competition": "iwsc",
        "int'l wine & spirit competition": "iwsc",
        "international wine spirit competition": "iwsc",

        # San Francisco World Spirits Competition
        "sfwsc": "sfwsc",
        "san francisco world spirits competition": "sfwsc",
        "san francisco wsc": "sfwsc",
        "sf world spirits competition": "sfwsc",

        # World Whiskies Awards
        "wwa": "wwa",
        "world whiskies awards": "wwa",
        "world whisky awards": "wwa",
        "world whiskey awards": "wwa",

        # International Spirits Challenge
        "isc": "isc",
        "international spirits challenge": "isc",

        # World Wine Awards
        "world wine awards": "world_wine_awards",
        "decanter world wine awards": "decanter_world_wine_awards",
        "dwwa": "decanter_world_wine_awards",
    }

    # Medal name mappings for normalization
    MEDAL_MAPPINGS = {
        "gold": "gold",
        "gold medal": "gold",
        "gold award": "gold",
        "double gold": "double_gold",
        "double gold medal": "double_gold",
        "silver": "silver",
        "silver medal": "silver",
        "bronze": "bronze",
        "bronze medal": "bronze",
        "platinum": "platinum",
        "best in class": "best_in_class",
        "best in show": "best_in_show",
        "trophy": "trophy",
    }

    def normalize_competition_name(self, name: str) -> str:
        """
        Normalize competition name for deduplication.

        Args:
            name: Raw competition name

        Returns:
            Normalized competition identifier
        """
        if not name:
            return ""

        # Clean up name
        cleaned = name.strip().lower()

        # Check for known mappings
        if cleaned in self.COMPETITION_MAPPINGS:
            return self.COMPETITION_MAPPINGS[cleaned]

        # Check if any mapping key is contained in the name
        for key, value in self.COMPETITION_MAPPINGS.items():
            if key in cleaned:
                return value

        # Unknown competition - convert to slug format
        slug = re.sub(r'[^\w\s]', '', cleaned)  # Remove special chars
        slug = re.sub(r'\s+', '_', slug)  # Replace spaces with underscores
        return slug

    def normalize_medal(self, medal: str) -> str:
        """
        Normalize medal name for deduplication.

        Args:
            medal: Raw medal name

        Returns:
            Normalized medal identifier
        """
        if not medal:
            return ""

        cleaned = medal.strip().lower()

        # Check for known mappings
        if cleaned in self.MEDAL_MAPPINGS:
            return self.MEDAL_MAPPINGS[cleaned]

        # Check if any mapping key is contained in the medal name
        for key, value in self.MEDAL_MAPPINGS.items():
            if key in cleaned:
                return value

        # Unknown medal - return cleaned lowercase
        return re.sub(r'\s+', '_', cleaned)

    def _get_award_key(self, award: Dict[str, Any]) -> tuple:
        """
        Get deduplication key for an award.

        Args:
            award: Award dict with competition, year, medal

        Returns:
            Tuple (normalized_competition, year, normalized_medal)
        """
        competition = self.normalize_competition_name(
            award.get("competition", "")
        )
        year = award.get("year")
        medal = self.normalize_medal(award.get("medal", ""))

        return (competition, year, medal)

    def is_duplicate(
        self,
        new_award: Dict[str, Any],
        existing_awards: List[Dict[str, Any]],
    ) -> bool:
        """
        Check if award is a duplicate of an existing award.

        Deduplication is based on normalized competition+year+medal.

        Args:
            new_award: The award to check
            existing_awards: List of existing awards

        Returns:
            True if award is a duplicate
        """
        if not existing_awards:
            return False

        new_key = self._get_award_key(new_award)

        for existing in existing_awards:
            existing_key = self._get_award_key(existing)
            if new_key == existing_key:
                logger.debug(
                    "Duplicate award detected: %s matches existing %s",
                    new_award,
                    existing
                )
                return True

        return False

    def merge_awards(
        self,
        existing_awards: List[Dict[str, Any]],
        new_awards: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge new awards into existing awards, skipping duplicates.

        Args:
            existing_awards: Current awards list
            new_awards: New awards to add

        Returns:
            Merged awards list with no duplicates
        """
        if not new_awards:
            return list(existing_awards)

        merged = list(existing_awards)
        added = 0
        skipped = 0

        for award in new_awards:
            if self.is_duplicate(award, merged):
                skipped += 1
                continue

            merged.append(award)
            added += 1

        if added or skipped:
            logger.info(
                "Awards merge: added %d, skipped %d duplicates",
                added,
                skipped
            )

        return merged


# Singleton instance
_awards_handler: Optional[AwardsHandler] = None


def get_awards_handler() -> AwardsHandler:
    """Get singleton AwardsHandler instance."""
    global _awards_handler
    if _awards_handler is None:
        _awards_handler = AwardsHandler()
    return _awards_handler


def reset_awards_handler() -> None:
    """Reset singleton for testing."""
    global _awards_handler
    _awards_handler = None
