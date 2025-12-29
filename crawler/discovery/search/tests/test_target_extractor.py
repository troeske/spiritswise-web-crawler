"""
Tests for Target URL Extractor.

Phase 3: Generic Search Discovery - TDD Tests for target_extractor.py
"""

import pytest

from crawler.discovery.search.config import SearchConfig
from crawler.discovery.search.target_extractor import TargetURLExtractor


@pytest.fixture
def config():
    """Create a SearchConfig instance."""
    return SearchConfig(year=2025)


@pytest.fixture
def extractor(config):
    """Create a TargetURLExtractor instance."""
    return TargetURLExtractor(config)


@pytest.fixture
def sample_search_results():
    """Sample SerpAPI search results."""
    return {
        "organic_results": [
            {
                "position": 1,
                "title": "Best Whisky 2025 - Top 10 Picks",
                "link": "https://whiskyadvocate.com/best-whisky-2025",
                "snippet": "Our review of the top rated whiskies this year.",
            },
            {
                "position": 2,
                "title": "Award Winning Scotch",
                "link": "https://masterofmalt.com/scotch-awards",
                "snippet": "Gold medal winners with tasting notes.",
            },
            {
                "position": 3,
                "title": "Wikipedia Whisky Article",
                "link": "https://en.wikipedia.org/wiki/Whisky",
                "snippet": "General information about whisky.",
            },
            {
                "position": 4,
                "title": "Unknown Site Review",
                "link": "https://randomsite.com/whisky-review",
                "snippet": "A simple review page.",
            },
        ]
    }


class TestTargetURLExtractorInit:
    """Tests for TargetURLExtractor initialization."""

    def test_init_with_config(self, config):
        """Should initialize with SearchConfig."""
        extractor = TargetURLExtractor(config)
        assert extractor.config == config

    def test_init_creates_empty_seen_set(self, config):
        """Should initialize with empty seen URLs set."""
        extractor = TargetURLExtractor(config)
        assert len(extractor._seen_urls) == 0


class TestExtractTargets:
    """Tests for extract_targets method."""

    def test_extract_targets_from_results(self, extractor, sample_search_results):
        """Should extract target URLs from search results."""
        targets = extractor.extract_targets(sample_search_results)

        assert len(targets) > 0
        # Should have URL, title, source, priority
        first = targets[0]
        assert "url" in first
        assert "title" in first
        assert "source" in first
        assert "priority" in first

    def test_filters_excluded_domains(self, extractor, sample_search_results):
        """Should filter out excluded domains."""
        targets = extractor.extract_targets(sample_search_results)

        # Wikipedia should be filtered out
        urls = [t["url"] for t in targets]
        wikipedia_urls = [u for u in urls if "wikipedia" in u]
        assert len(wikipedia_urls) == 0

    def test_prioritizes_priority_domains(self, extractor, sample_search_results):
        """Should boost priority for known domains."""
        targets = extractor.extract_targets(sample_search_results)

        # Find whiskyadvocate and randomsite results
        wa_target = next((t for t in targets if "whiskyadvocate" in t["url"]), None)
        random_target = next((t for t in targets if "randomsite" in t["url"]), None)

        assert wa_target is not None
        assert random_target is not None
        assert wa_target["priority"] > random_target["priority"]

    def test_deduplicates_urls(self, extractor, config):
        """Should not return duplicate URLs."""
        # Results with duplicate URL
        results = {
            "organic_results": [
                {"position": 1, "title": "Page 1", "link": "https://example.com/page", "snippet": ""},
                {"position": 2, "title": "Page 2", "link": "https://example.com/page", "snippet": ""},
            ]
        }

        targets = extractor.extract_targets(results)

        urls = [t["url"] for t in targets]
        assert len(urls) == len(set(urls))  # All unique

    def test_limits_results(self, extractor, config):
        """Should respect max_targets limit."""
        results = {
            "organic_results": [
                {"position": i, "title": f"Page {i}", "link": f"https://site{i}.com/page", "snippet": ""}
                for i in range(20)
            ]
        }

        targets = extractor.extract_targets(results, max_targets=5)

        assert len(targets) == 5

    def test_handles_empty_results(self, extractor):
        """Should handle empty search results."""
        targets = extractor.extract_targets({"organic_results": []})
        assert targets == []

    def test_handles_missing_organic_results(self, extractor):
        """Should handle missing organic_results key."""
        targets = extractor.extract_targets({})
        assert targets == []

    def test_extracts_position(self, extractor, sample_search_results):
        """Should include search position in target."""
        targets = extractor.extract_targets(sample_search_results)

        for target in targets:
            assert "position" in target
            assert isinstance(target["position"], int)

    def test_extracts_snippet(self, extractor, sample_search_results):
        """Should include snippet in target."""
        targets = extractor.extract_targets(sample_search_results)

        assert targets[0]["snippet"] != ""


class TestExtractDomain:
    """Tests for _extract_domain method."""

    def test_extracts_domain_from_url(self, extractor):
        """Should extract domain from full URL."""
        domain = extractor._extract_domain("https://www.example.com/page/path")
        assert domain == "example.com"

    def test_strips_www_prefix(self, extractor):
        """Should strip www. prefix."""
        domain = extractor._extract_domain("https://www.whiskyadvocate.com/review")
        assert domain == "whiskyadvocate.com"

    def test_handles_no_www(self, extractor):
        """Should handle URLs without www."""
        domain = extractor._extract_domain("https://example.com/page")
        assert domain == "example.com"

    def test_handles_invalid_url(self, extractor):
        """Should return empty string for invalid URL."""
        domain = extractor._extract_domain("not-a-valid-url")
        assert domain == "" or domain == "not-a-valid-url"

    def test_handles_empty_url(self, extractor):
        """Should handle empty URL."""
        domain = extractor._extract_domain("")
        assert domain == ""


class TestCalculatePriority:
    """Tests for _calculate_priority method."""

    def test_base_priority(self, extractor):
        """Should have base priority of 50."""
        result = {"position": 10, "snippet": ""}
        priority = extractor._calculate_priority(result, "unknownsite.com")
        assert priority >= 50

    def test_priority_domain_boost(self, extractor):
        """Should boost priority for known domains."""
        result = {"position": 1, "snippet": ""}
        priority_domain = extractor._calculate_priority(result, "whiskyadvocate.com")
        regular_domain = extractor._calculate_priority(result, "unknownsite.com")

        assert priority_domain > regular_domain

    def test_position_boost(self, extractor):
        """Should boost priority for higher positions."""
        result_high = {"position": 1, "snippet": ""}
        result_low = {"position": 10, "snippet": ""}

        priority_high = extractor._calculate_priority(result_high, "example.com")
        priority_low = extractor._calculate_priority(result_low, "example.com")

        assert priority_high > priority_low

    def test_product_words_boost(self, extractor):
        """Should boost priority for product-related words in snippet."""
        result_with_words = {"position": 5, "snippet": "A detailed review with tasting notes and rating."}
        result_without = {"position": 5, "snippet": "General information about the topic."}

        priority_with = extractor._calculate_priority(result_with_words, "example.com")
        priority_without = extractor._calculate_priority(result_without, "example.com")

        assert priority_with > priority_without


class TestDeduplicateAcrossSearches:
    """Tests for deduplicate_across_searches method."""

    def test_removes_duplicate_urls(self, extractor):
        """Should remove duplicate URLs from list."""
        targets = [
            {"url": "https://example.com/page1", "title": "Page 1"},
            {"url": "https://example.com/page2", "title": "Page 2"},
            {"url": "https://example.com/page1", "title": "Page 1 Copy"},  # Duplicate
        ]

        unique = extractor.deduplicate_across_searches(targets)

        urls = [t["url"] for t in unique]
        assert len(urls) == 2
        assert len(set(urls)) == 2

    def test_keeps_first_occurrence(self, extractor):
        """Should keep first occurrence of duplicate."""
        targets = [
            {"url": "https://example.com/page", "title": "First"},
            {"url": "https://example.com/page", "title": "Second"},
        ]

        unique = extractor.deduplicate_across_searches(targets)

        assert len(unique) == 1
        assert unique[0]["title"] == "First"

    def test_handles_empty_list(self, extractor):
        """Should handle empty list."""
        unique = extractor.deduplicate_across_searches([])
        assert unique == []


class TestClearSeenCache:
    """Tests for clear_seen_cache method."""

    def test_clears_seen_urls(self, extractor, sample_search_results):
        """Should clear the seen URLs cache."""
        # Extract some targets to populate cache
        extractor.extract_targets(sample_search_results)
        assert len(extractor._seen_urls) > 0

        extractor.clear_seen_cache()

        assert len(extractor._seen_urls) == 0

    def test_allows_re_extraction_after_clear(self, extractor, sample_search_results):
        """Should allow re-extraction after clearing cache."""
        targets1 = extractor.extract_targets(sample_search_results)
        extractor.clear_seen_cache()
        targets2 = extractor.extract_targets(sample_search_results)

        # Should get same results after clearing
        assert len(targets1) == len(targets2)


class TestSeenUrlsTracking:
    """Tests for seen URLs tracking across extractions."""

    def test_tracks_seen_urls_across_calls(self, extractor, config):
        """Should track seen URLs across multiple extract calls."""
        results1 = {
            "organic_results": [
                {"position": 1, "title": "Page 1", "link": "https://site1.com/page", "snippet": ""},
            ]
        }
        results2 = {
            "organic_results": [
                {"position": 1, "title": "Page 1 Again", "link": "https://site1.com/page", "snippet": ""},
                {"position": 2, "title": "Page 2", "link": "https://site2.com/page", "snippet": ""},
            ]
        }

        targets1 = extractor.extract_targets(results1)
        targets2 = extractor.extract_targets(results2)

        # First call should get 1 target
        assert len(targets1) == 1
        # Second call should only get the new URL
        assert len(targets2) == 1
        assert "site2.com" in targets2[0]["url"]
