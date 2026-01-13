"""
Unit tests for Awards Deduplication.

Task 4.5: Implement Awards Deduplication

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 10.1

Tests verify:
- Same competition+year+medal = duplicate
- Same competition+different year = NOT duplicate
- Competition name normalization
"""

from django.test import TestCase

from crawler.services.awards_handler import AwardsHandler


class DuplicateDetectionTests(TestCase):
    """Tests for duplicate award detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = AwardsHandler()

    def test_handler_exists(self):
        """Test AwardsHandler exists."""
        self.assertIsNotNone(self.handler)

    def test_same_competition_year_medal_is_duplicate(self):
        """Test same competition, year, and medal is a duplicate."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_award = {"competition": "IWSC", "year": 2024, "medal": "Gold"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertTrue(is_duplicate)

    def test_same_competition_different_year_not_duplicate(self):
        """Test same competition but different year is NOT a duplicate."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_award = {"competition": "IWSC", "year": 2023, "medal": "Gold"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertFalse(is_duplicate)

    def test_same_competition_year_different_medal_not_duplicate(self):
        """Test same competition and year but different medal is NOT duplicate."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_award = {"competition": "IWSC", "year": 2024, "medal": "Silver"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertFalse(is_duplicate)

    def test_different_competition_not_duplicate(self):
        """Test different competition is NOT a duplicate."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_award = {"competition": "San Francisco", "year": 2024, "medal": "Gold"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertFalse(is_duplicate)

    def test_empty_existing_awards_not_duplicate(self):
        """Test new award against empty list is not a duplicate."""
        existing = []
        new_award = {"competition": "IWSC", "year": 2024, "medal": "Gold"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertFalse(is_duplicate)


class CompetitionNameNormalizationTests(TestCase):
    """Tests for competition name normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = AwardsHandler()

    def test_normalize_iwsc_variations(self):
        """Test IWSC name variations normalized."""
        variations = [
            "IWSC",
            "iwsc",
            "International Wine & Spirit Competition",
            "International Wine and Spirit Competition",
            "Int'l Wine & Spirit Competition",
        ]

        for variation in variations:
            normalized = self.handler.normalize_competition_name(variation)
            self.assertEqual(normalized, "iwsc", f"Failed for: {variation}")

    def test_normalize_san_francisco_variations(self):
        """Test San Francisco competition name variations."""
        variations = [
            "San Francisco World Spirits Competition",
            "SFWSC",
            "San Francisco WSC",
            "SF World Spirits Competition",
        ]

        for variation in variations:
            normalized = self.handler.normalize_competition_name(variation)
            self.assertEqual(normalized, "sfwsc", f"Failed for: {variation}")

    def test_normalize_world_whisky_awards(self):
        """Test World Whisky Awards name variations."""
        variations = [
            "World Whiskies Awards",
            "World Whisky Awards",
            "WWA",
        ]

        for variation in variations:
            normalized = self.handler.normalize_competition_name(variation)
            self.assertEqual(normalized, "wwa", f"Failed for: {variation}")

    def test_normalize_handles_case_insensitivity(self):
        """Test normalization is case-insensitive."""
        result1 = self.handler.normalize_competition_name("IWSC")
        result2 = self.handler.normalize_competition_name("iwsc")
        result3 = self.handler.normalize_competition_name("Iwsc")

        self.assertEqual(result1, result2)
        self.assertEqual(result2, result3)

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        result = self.handler.normalize_competition_name("  IWSC  ")

        self.assertEqual(result, "iwsc")

    def test_normalize_unknown_competition(self):
        """Test unknown competition name returned as lowercase slug."""
        result = self.handler.normalize_competition_name("Some Random Competition")

        # Should return a normalized slug
        self.assertEqual(result, "some_random_competition")


class MedalNormalizationTests(TestCase):
    """Tests for medal name normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = AwardsHandler()

    def test_normalize_gold_medal(self):
        """Test gold medal normalization."""
        variations = ["Gold", "GOLD", "gold", "Gold Medal", "Gold Award"]

        for variation in variations:
            normalized = self.handler.normalize_medal(variation)
            self.assertEqual(normalized, "gold", f"Failed for: {variation}")

    def test_normalize_double_gold(self):
        """Test double gold normalization."""
        variations = ["Double Gold", "DOUBLE GOLD", "double gold"]

        for variation in variations:
            normalized = self.handler.normalize_medal(variation)
            self.assertEqual(normalized, "double_gold", f"Failed for: {variation}")

    def test_normalize_silver_medal(self):
        """Test silver medal normalization."""
        result = self.handler.normalize_medal("Silver")

        self.assertEqual(result, "silver")

    def test_normalize_bronze_medal(self):
        """Test bronze medal normalization."""
        result = self.handler.normalize_medal("Bronze")

        self.assertEqual(result, "bronze")


class DeduplicationWithNormalizationTests(TestCase):
    """Tests for deduplication using normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = AwardsHandler()

    def test_detects_duplicate_with_different_name_format(self):
        """Test detects duplicate when competition names differ in format."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_award = {
            "competition": "International Wine & Spirit Competition",
            "year": 2024,
            "medal": "Gold"
        }

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertTrue(is_duplicate)

    def test_detects_duplicate_with_different_medal_format(self):
        """Test detects duplicate when medal names differ in format."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold Medal"}
        ]
        new_award = {"competition": "IWSC", "year": 2024, "medal": "gold"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertTrue(is_duplicate)

    def test_detects_duplicate_with_both_differences(self):
        """Test detects duplicate with both name and medal format differences."""
        existing = [
            {"competition": "Int'l Wine & Spirit Competition", "year": 2024, "medal": "GOLD"}
        ]
        new_award = {"competition": "IWSC", "year": 2024, "medal": "Gold Medal"}

        is_duplicate = self.handler.is_duplicate(new_award, existing)

        self.assertTrue(is_duplicate)


class MergeAwardsTests(TestCase):
    """Tests for merging awards lists."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = AwardsHandler()

    def test_merge_adds_new_awards(self):
        """Test merge adds non-duplicate awards."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_awards = [
            {"competition": "San Francisco", "year": 2024, "medal": "Double Gold"}
        ]

        merged = self.handler.merge_awards(existing, new_awards)

        self.assertEqual(len(merged), 2)

    def test_merge_skips_duplicates(self):
        """Test merge skips duplicate awards."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]
        new_awards = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"},  # Duplicate
            {"competition": "San Francisco", "year": 2024, "medal": "Gold"}  # New
        ]

        merged = self.handler.merge_awards(existing, new_awards)

        self.assertEqual(len(merged), 2)  # 1 existing + 1 new (skipped duplicate)

    def test_merge_preserves_original_awards(self):
        """Test merge preserves all original awards."""
        existing = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"},
            {"competition": "IWSC", "year": 2023, "medal": "Silver"}
        ]
        new_awards = []

        merged = self.handler.merge_awards(existing, new_awards)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged, existing)

    def test_merge_handles_empty_existing(self):
        """Test merge handles empty existing list."""
        existing = []
        new_awards = [
            {"competition": "IWSC", "year": 2024, "medal": "Gold"}
        ]

        merged = self.handler.merge_awards(existing, new_awards)

        self.assertEqual(len(merged), 1)
