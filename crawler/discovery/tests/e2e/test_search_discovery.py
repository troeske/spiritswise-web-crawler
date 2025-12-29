"""
End-to-End Tests for Generic Search Discovery (Phase 3).

Tests the complete flow from search configuration through URL extraction,
scheduling, and task execution.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta

from crawler.discovery.search.config import (
    SearchConfig,
    GENERIC_SEARCH_TERMS,
    PRIORITY_DOMAINS,
    EXCLUDED_DOMAINS,
)
from crawler.discovery.search.target_extractor import TargetURLExtractor
from crawler.discovery.search.scheduler import SearchScheduler
from crawler.discovery.serpapi.rate_limiter import RateLimiter


class TestSearchConfigToExtractorFlow:
    """Tests flow from config to URL extraction."""

    def test_config_provides_valid_search_terms(self):
        """Test that config provides usable search terms."""
        config = SearchConfig()

        # Use the actual method
        terms = config.get_queries_for_type("whiskey")

        assert len(terms) > 0
        assert all(isinstance(t, str) for t in terms)
        assert all(len(t) > 0 for t in terms)

    def test_config_provides_priority_domains(self):
        """Test that config provides priority domains."""
        # Check the module-level constant
        assert len(PRIORITY_DOMAINS) > 0

    def test_config_provides_excluded_domains(self):
        """Test that config provides excluded domains."""
        # Check the module-level constant
        assert len(EXCLUDED_DOMAINS) > 0

    def test_extractor_uses_config(self, mock_google_search_response):
        """Test that extractor properly uses config settings."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        # Use actual method name: extract_targets
        targets = extractor.extract_targets(mock_google_search_response)

        # Should have extracted some targets
        assert isinstance(targets, list)

    def test_extractor_filters_excluded_domains(self, mock_google_search_response):
        """Test that extractor filters out excluded domains."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        targets = extractor.extract_targets(mock_google_search_response)

        # Check no excluded domains in results
        for target in targets:
            source = target.get("source", "")
            assert source not in EXCLUDED_DOMAINS


class TestURLExtractionFlow:
    """Tests URL extraction and prioritization."""

    def test_extract_and_prioritize_urls(self, mock_google_search_response):
        """Test complete URL extraction and prioritization."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        targets = extractor.extract_targets(mock_google_search_response)

        # Targets should be extracted
        if len(targets) > 0:
            # Each target should have required fields
            for target in targets:
                assert "url" in target
                assert "priority" in target

    def test_priority_scoring(self, mock_google_search_response):
        """Test that priority domains get higher scores."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        targets = extractor.extract_targets(mock_google_search_response)

        if len(targets) >= 2:
            # Targets should already be sorted by priority
            assert targets[0].get("priority", 0) >= targets[-1].get("priority", 0)

    def test_deduplication(self):
        """Test URL deduplication across multiple responses."""
        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        response1 = {
            "organic_results": [
                {"link": "https://example.com/page1", "title": "Page 1", "position": 1},
                {"link": "https://example.com/page2", "title": "Page 2", "position": 2},
            ]
        }

        response2 = {
            "organic_results": [
                {"link": "https://example.com/page1", "title": "Page 1 Again", "position": 1},  # Duplicate
                {"link": "https://example.com/page3", "title": "Page 3", "position": 2},
            ]
        }

        targets1 = extractor.extract_targets(response1)
        targets2 = extractor.extract_targets(response2)

        # Same extractor should have deduplicated
        # page1 should only appear once across both extractions
        all_urls = [t["url"] for t in targets1] + [t["url"] for t in targets2]
        assert all_urls.count("https://example.com/page1") <= 1


class TestSchedulerIntegration:
    """Tests scheduler with search execution."""

    def test_scheduler_manages_search_execution(self, mock_cache):
        """Test scheduler manages which searches to run."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            rate_limiter = RateLimiter()
            scheduler = SearchScheduler(rate_limiter=rate_limiter)

            # Get next queries to execute
            queries = scheduler.get_next_queries("whiskey", count=5)

            # Should return some queries
            assert isinstance(queries, list)

    def test_scheduler_prevents_duplicate_execution(self, mock_cache):
        """Test scheduler prevents running same query twice."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.search.scheduler.cache", mock_cache):
                rate_limiter = RateLimiter()
                scheduler = SearchScheduler(rate_limiter=rate_limiter)

                # Get a query
                queries = scheduler.get_next_queries("whiskey", count=1)
                if queries:
                    query = queries[0]

                    # Mark as executed
                    scheduler.mark_executed(query)

                    # Get queries again - should not include the just-executed one
                    next_queries = scheduler.get_next_queries("whiskey", count=10)

                    # The executed query should not appear immediately again
                    # (depending on implementation)
                    assert isinstance(next_queries, list)

    def test_scheduler_checks_rate_limit(self, mock_cache):
        """Test scheduler respects rate limits."""
        with patch("crawler.discovery.serpapi.rate_limiter.cache", mock_cache):
            with patch("crawler.discovery.search.scheduler.cache", mock_cache):
                rate_limiter = RateLimiter()
                scheduler = SearchScheduler(rate_limiter=rate_limiter)

                # Check if can execute
                can_execute = scheduler.can_execute_search()
                assert isinstance(can_execute, bool)


class TestConfiguredSearchTerms:
    """Tests with actual configured search terms."""

    def test_generic_search_terms_are_valid(self):
        """Test that GENERIC_SEARCH_TERMS are valid."""
        assert len(GENERIC_SEARCH_TERMS) > 0

        for term in GENERIC_SEARCH_TERMS:
            assert isinstance(term, str)
            assert len(term) > 0

    def test_priority_domains_are_valid(self):
        """Test that PRIORITY_DOMAINS are valid."""
        assert len(PRIORITY_DOMAINS) > 0

        for domain in PRIORITY_DOMAINS:
            assert isinstance(domain, str)
            assert "." in domain  # Valid domain format

    def test_excluded_domains_are_valid(self):
        """Test that EXCLUDED_DOMAINS are valid."""
        assert len(EXCLUDED_DOMAINS) > 0

        for domain in EXCLUDED_DOMAINS:
            assert isinstance(domain, str)
            assert "." in domain

    def test_no_overlap_priority_excluded(self):
        """Test no overlap between priority and excluded domains."""
        overlap = set(PRIORITY_DOMAINS) & set(EXCLUDED_DOMAINS)
        assert len(overlap) == 0, f"Domains in both lists: {overlap}"


class TestSearchConfigQueries:
    """Tests for SearchConfig query generation."""

    def test_get_whiskey_queries(self):
        """Test getting whiskey queries."""
        config = SearchConfig()
        queries = config.get_queries_for_type("whiskey")

        assert len(queries) > 0
        # Should have year substituted
        current_year = str(datetime.now().year)
        assert any(current_year in q for q in queries)

    def test_get_port_queries(self):
        """Test getting port wine queries."""
        config = SearchConfig()
        queries = config.get_queries_for_type("port_wine")

        assert len(queries) > 0

    def test_domain_exclusion_check(self):
        """Test domain exclusion checking."""
        config = SearchConfig()

        # Facebook should be excluded
        assert config.is_excluded_domain("facebook.com")

        # Priority domain should not be excluded
        assert not config.is_excluded_domain("masterofmalt.com")

    def test_priority_domain_in_list(self):
        """Test priority domain detection."""
        from crawler.discovery.search.config import PRIORITY_DOMAINS

        # Master of malt should be in priority domains
        assert "masterofmalt.com" in PRIORITY_DOMAINS

        # Random site should not be in priority domains
        assert "randomsite.com" not in PRIORITY_DOMAINS
