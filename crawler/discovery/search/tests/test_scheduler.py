"""
Tests for Search Scheduler.

Phase 3: Generic Search Discovery - TDD Tests for scheduler.py
"""

import pytest
from unittest.mock import patch, MagicMock

from crawler.discovery.search.scheduler import SearchScheduler
from crawler.discovery.serpapi.rate_limiter import RateLimiter


@pytest.fixture
def mock_rate_limiter():
    """Create a mock RateLimiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.can_make_request.return_value = True
    limiter.get_remaining_daily.return_value = 100
    return limiter


@pytest.fixture
def scheduler(mock_rate_limiter):
    """Create a SearchScheduler instance."""
    return SearchScheduler(mock_rate_limiter)


class TestSearchSchedulerInit:
    """Tests for SearchScheduler initialization."""

    def test_init_with_rate_limiter(self, mock_rate_limiter):
        """Should initialize with rate limiter."""
        scheduler = SearchScheduler(mock_rate_limiter)
        assert scheduler.rate_limiter == mock_rate_limiter

    def test_init_sets_cache_prefix(self, mock_rate_limiter):
        """Should set cache prefix."""
        scheduler = SearchScheduler(mock_rate_limiter)
        assert scheduler.cache_prefix == "search_scheduler"


class TestGetNextQueries:
    """Tests for get_next_queries method."""

    def test_get_next_queries_returns_list(self, scheduler):
        """Should return list of queries."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None  # No queries executed

            queries = scheduler.get_next_queries("whiskey", count=5)

            assert isinstance(queries, list)
            assert len(queries) <= 5

    def test_get_next_queries_for_whiskey(self, scheduler):
        """Should return whiskey queries."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None

            queries = scheduler.get_next_queries("whiskey", count=3)

            assert len(queries) > 0
            # Queries should be related to whiskey
            query_str = " ".join(queries).lower()
            assert "whisky" in query_str or "whiskey" in query_str or "bourbon" in query_str

    def test_get_next_queries_for_port(self, scheduler):
        """Should return port wine queries."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None

            queries = scheduler.get_next_queries("port_wine", count=3)

            assert len(queries) > 0
            query_str = " ".join(queries).lower()
            assert "port" in query_str

    def test_filters_recently_executed(self, scheduler):
        """Should filter out recently executed queries."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            # First call: no queries executed yet
            mock_cache.get.return_value = None
            queries_first = scheduler.get_next_queries("whiskey", count=3)

            # Mark first query as executed by making cache return a value for it
            first_query_key = scheduler._query_key(queries_first[0])

            def cache_get_side_effect(key):
                if key == first_query_key:
                    return "2025-01-01T00:00:00"  # Recently executed
                return None

            mock_cache.get.side_effect = cache_get_side_effect

            queries_second = scheduler.get_next_queries("whiskey", count=3)

            # First query should not be in second result
            assert queries_first[0] not in queries_second

    def test_respects_count_limit(self, scheduler):
        """Should respect count parameter."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None

            queries = scheduler.get_next_queries("whiskey", count=2)

            assert len(queries) == 2


class TestMarkExecuted:
    """Tests for mark_executed method."""

    def test_mark_executed_sets_cache(self, scheduler):
        """Should set cache entry for executed query."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            scheduler.mark_executed("best whisky 2025")

            mock_cache.set.assert_called_once()

    def test_mark_executed_prevents_repeat(self, scheduler):
        """Should prevent query from being returned again."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None

            # Get initial queries
            queries1 = scheduler.get_next_queries("whiskey", count=5)
            assert len(queries1) > 0

            # Get the cache key for the first query
            first_query_key = scheduler._query_key(queries1[0])

            # Now make cache return timestamp for that specific query key
            def cache_get_with_executed(key):
                if key == first_query_key:
                    return "2025-01-01T00:00:00"
                return None

            mock_cache.get.side_effect = cache_get_with_executed

            queries2 = scheduler.get_next_queries("whiskey", count=5)

            # First query should not be in second result
            assert queries1[0] not in queries2

    def test_mark_executed_cache_expires(self, scheduler):
        """Should set cache with 24 hour expiry."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            scheduler.mark_executed("test query")

            # Check expiry time (86400 seconds = 24 hours)
            call_args = mock_cache.set.call_args
            assert call_args[0][2] == 86400


class TestCanExecuteSearch:
    """Tests for can_execute_search method."""

    def test_can_execute_respects_rate_limit(self, mock_rate_limiter):
        """Should respect rate limiter."""
        scheduler = SearchScheduler(mock_rate_limiter)

        mock_rate_limiter.can_make_request.return_value = True
        assert scheduler.can_execute_search() is True

        mock_rate_limiter.can_make_request.return_value = False
        assert scheduler.can_execute_search() is False

    def test_can_execute_calls_rate_limiter(self, mock_rate_limiter):
        """Should call rate limiter's can_make_request."""
        scheduler = SearchScheduler(mock_rate_limiter)
        scheduler.can_execute_search()

        mock_rate_limiter.can_make_request.assert_called_once()


class TestGetDailyBudgetRemaining:
    """Tests for get_daily_budget_remaining method."""

    def test_daily_budget_remaining(self, mock_rate_limiter):
        """Should return remaining daily budget."""
        mock_rate_limiter.get_remaining_daily.return_value = 150

        scheduler = SearchScheduler(mock_rate_limiter)
        remaining = scheduler.get_daily_budget_remaining()

        assert remaining == 150

    def test_daily_budget_calls_rate_limiter(self, mock_rate_limiter):
        """Should call rate limiter's get_remaining_daily."""
        scheduler = SearchScheduler(mock_rate_limiter)
        scheduler.get_daily_budget_remaining()

        mock_rate_limiter.get_remaining_daily.assert_called_once()


class TestQueryKey:
    """Tests for _query_key method."""

    def test_query_key_includes_prefix(self, scheduler):
        """Should include cache prefix in key."""
        key = scheduler._query_key("test query")
        assert key.startswith("search_scheduler:")

    def test_query_key_includes_hash(self, scheduler):
        """Should include query hash in key."""
        key = scheduler._query_key("test query")
        assert ":query:" in key
        # Key should have hash after :query:
        parts = key.split(":query:")
        assert len(parts[1]) == 12  # MD5 hash truncated to 12 chars

    def test_different_queries_different_keys(self, scheduler):
        """Different queries should have different keys."""
        key1 = scheduler._query_key("query one")
        key2 = scheduler._query_key("query two")
        assert key1 != key2

    def test_same_query_same_key(self, scheduler):
        """Same query should always produce same key."""
        key1 = scheduler._query_key("test query")
        key2 = scheduler._query_key("test query")
        assert key1 == key2


class TestWasRecentlyExecuted:
    """Tests for _was_recently_executed method."""

    def test_returns_true_if_in_cache(self, scheduler):
        """Should return True if query is in cache."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = "2025-01-01T00:00:00"

            result = scheduler._was_recently_executed("test query")

            assert result is True

    def test_returns_false_if_not_in_cache(self, scheduler):
        """Should return False if query is not in cache."""
        with patch("crawler.discovery.search.scheduler.cache") as mock_cache:
            mock_cache.get.return_value = None

            result = scheduler._was_recently_executed("test query")

            assert result is False
