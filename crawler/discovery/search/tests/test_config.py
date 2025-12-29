"""
Tests for Search Configuration.

Phase 3: Generic Search Discovery - TDD Tests for config.py
"""

import pytest
from datetime import datetime

from crawler.discovery.search.config import (
    SearchConfig,
    GENERIC_SEARCH_TERMS,
    PRIORITY_DOMAINS,
    EXCLUDED_DOMAINS,
    SEARCH_PRIORITY,
)


class TestGenericSearchTerms:
    """Tests for GENERIC_SEARCH_TERMS configuration."""

    def test_whiskey_terms_exist(self):
        """Should have whiskey search terms defined."""
        assert "whiskey" in GENERIC_SEARCH_TERMS
        assert len(GENERIC_SEARCH_TERMS["whiskey"]) > 0

    def test_port_wine_terms_exist(self):
        """Should have port wine search terms defined."""
        assert "port_wine" in GENERIC_SEARCH_TERMS
        assert len(GENERIC_SEARCH_TERMS["port_wine"]) > 0

    def test_whiskey_has_best_lists(self):
        """Whiskey should have best_lists category."""
        assert "best_lists" in GENERIC_SEARCH_TERMS["whiskey"]
        assert len(GENERIC_SEARCH_TERMS["whiskey"]["best_lists"]) > 0

    def test_whiskey_has_awards(self):
        """Whiskey should have awards category."""
        assert "awards" in GENERIC_SEARCH_TERMS["whiskey"]

    def test_port_has_best_lists(self):
        """Port wine should have best_lists category."""
        assert "best_lists" in GENERIC_SEARCH_TERMS["port_wine"]

    def test_terms_contain_year_placeholder(self):
        """Some terms should contain {year} placeholder."""
        whiskey_best = GENERIC_SEARCH_TERMS["whiskey"]["best_lists"]
        year_terms = [t for t in whiskey_best if "{year}" in t]
        assert len(year_terms) > 0


class TestPriorityDomains:
    """Tests for PRIORITY_DOMAINS list."""

    def test_priority_domains_not_empty(self):
        """Should have priority domains defined."""
        assert len(PRIORITY_DOMAINS) > 0

    def test_contains_whisky_advocate(self):
        """Should include whiskyadvocate.com."""
        assert "whiskyadvocate.com" in PRIORITY_DOMAINS

    def test_contains_major_retailers(self):
        """Should include major retailer domains."""
        retailers = ["masterofmalt.com", "thewhiskyexchange.com"]
        for retailer in retailers:
            assert retailer in PRIORITY_DOMAINS


class TestExcludedDomains:
    """Tests for EXCLUDED_DOMAINS list."""

    def test_excluded_domains_not_empty(self):
        """Should have excluded domains defined."""
        assert len(EXCLUDED_DOMAINS) > 0

    def test_excludes_social_media(self):
        """Should exclude social media platforms."""
        social = ["facebook.com", "twitter.com", "instagram.com"]
        for domain in social:
            assert domain in EXCLUDED_DOMAINS

    def test_excludes_wikipedia(self):
        """Should exclude Wikipedia."""
        assert "wikipedia.org" in EXCLUDED_DOMAINS


class TestSearchPriority:
    """Tests for SEARCH_PRIORITY ordering."""

    def test_priority_not_empty(self):
        """Should have priority order defined."""
        assert len(SEARCH_PRIORITY) > 0

    def test_best_lists_first(self):
        """best_lists should be highest priority."""
        assert SEARCH_PRIORITY[0] == "best_lists"

    def test_contains_main_categories(self):
        """Should contain main search categories."""
        expected = ["best_lists", "awards"]
        for cat in expected:
            assert cat in SEARCH_PRIORITY


class TestSearchConfigInit:
    """Tests for SearchConfig initialization."""

    def test_init_with_default_year(self):
        """Should default to current year."""
        config = SearchConfig()
        assert config.year == datetime.now().year

    def test_init_with_custom_year(self):
        """Should accept custom year."""
        config = SearchConfig(year=2024)
        assert config.year == 2024


class TestSearchConfigGetQueriesForType:
    """Tests for SearchConfig.get_queries_for_type()."""

    def test_get_queries_for_whiskey(self):
        """Should return whiskey queries with year substituted."""
        config = SearchConfig(year=2025)
        queries = config.get_queries_for_type("whiskey")

        assert len(queries) > 0
        # Should have year substituted
        year_queries = [q for q in queries if "2025" in q]
        assert len(year_queries) > 0

    def test_get_queries_for_port(self):
        """Should return port wine queries."""
        config = SearchConfig(year=2025)
        queries = config.get_queries_for_type("port_wine")

        assert len(queries) > 0
        query_str = " ".join(queries).lower()
        assert "port" in query_str

    def test_year_substitution(self):
        """Should substitute current year in queries."""
        config = SearchConfig(year=2025)
        queries = config.get_queries_for_type("whiskey")

        # No {year} placeholders should remain
        for query in queries:
            assert "{year}" not in query

    def test_unknown_type_returns_empty(self):
        """Should return empty list for unknown product type."""
        config = SearchConfig()
        queries = config.get_queries_for_type("unknown_type")
        assert queries == []

    def test_category_filter(self):
        """Should filter by category when specified."""
        config = SearchConfig()
        queries = config.get_queries_for_type("whiskey", category="best_lists")

        # Should only have best_lists queries
        assert len(queries) > 0
        # Other categories should not be included
        all_queries = config.get_queries_for_type("whiskey")
        assert len(queries) < len(all_queries)

    def test_limit_queries(self):
        """Should respect limit parameter."""
        config = SearchConfig()
        queries = config.get_queries_for_type("whiskey", limit=3)

        assert len(queries) == 3


class TestSearchConfigGetAllQueries:
    """Tests for SearchConfig.get_all_queries()."""

    def test_get_all_queries(self):
        """Should return queries from all product types."""
        config = SearchConfig()
        queries = config.get_all_queries()

        assert len(queries) > 0
        # Should have both whiskey and port queries
        query_str = " ".join(queries).lower()
        assert "whisky" in query_str or "whiskey" in query_str
        assert "port" in query_str

    def test_get_all_queries_with_limit(self):
        """Should respect limit parameter."""
        config = SearchConfig()
        queries = config.get_all_queries(limit=5)

        assert len(queries) == 5


class TestSearchConfigDomainChecks:
    """Tests for domain checking methods."""

    def test_is_priority_domain_true(self):
        """Should return True for priority domains."""
        config = SearchConfig()
        assert config.is_priority_domain("whiskyadvocate.com") is True
        assert config.is_priority_domain("www.whiskyadvocate.com") is True

    def test_is_priority_domain_false(self):
        """Should return False for non-priority domains."""
        config = SearchConfig()
        assert config.is_priority_domain("unknownsite.com") is False

    def test_is_priority_domain_partial_match(self):
        """Should match partial domain names."""
        config = SearchConfig()
        # Should match subdomains
        assert config.is_priority_domain("shop.masterofmalt.com") is True

    def test_is_excluded_domain_true(self):
        """Should return True for excluded domains."""
        config = SearchConfig()
        assert config.is_excluded_domain("wikipedia.org") is True
        assert config.is_excluded_domain("facebook.com") is True

    def test_is_excluded_domain_false(self):
        """Should return False for non-excluded domains."""
        config = SearchConfig()
        assert config.is_excluded_domain("whiskyadvocate.com") is False

    def test_is_excluded_domain_partial_match(self):
        """Should match partial domain names."""
        config = SearchConfig()
        assert config.is_excluded_domain("en.wikipedia.org") is True
