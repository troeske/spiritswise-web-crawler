"""
Tests for Query Builder.

Phase 2: SerpAPI Integration - TDD Tests for queries.py
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from crawler.discovery.serpapi.queries import QueryBuilder


class TestQueryBuilderGenericQueries:
    """Tests for building generic search queries."""

    def test_build_generic_whiskey_queries(self):
        """Should build whiskey search queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey")

        assert len(queries) > 0
        # Should include common whiskey terms
        query_str = " ".join(queries).lower()
        assert "whisky" in query_str or "whiskey" in query_str

    def test_build_generic_port_queries(self):
        """Should build port wine search queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("port_wine")

        assert len(queries) > 0
        # Should include port wine terms
        query_str = " ".join(queries).lower()
        assert "port" in query_str

    def test_queries_include_year(self):
        """Should substitute current year in queries."""
        builder = QueryBuilder()
        current_year = datetime.now().year
        queries = builder.build_generic_queries("whiskey", year=current_year)

        # At least one query should include the year
        year_queries = [q for q in queries if str(current_year) in q]
        assert len(year_queries) > 0

    def test_queries_use_provided_year(self):
        """Should use provided year instead of current year."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey", year=2024)

        year_queries = [q for q in queries if "2024" in q]
        assert len(year_queries) > 0

    def test_queries_default_to_current_year(self):
        """Should default to current year if not provided."""
        builder = QueryBuilder()
        current_year = datetime.now().year
        queries = builder.build_generic_queries("whiskey")

        # Should have current year in some queries
        year_queries = [q for q in queries if str(current_year) in q]
        assert len(year_queries) > 0

    def test_unknown_product_type_returns_empty(self):
        """Should return empty list for unknown product types."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("unknown_type")

        assert queries == []

    def test_whiskey_queries_include_categories(self):
        """Should include various whiskey categories."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey")

        query_str = " ".join(queries).lower()
        # Should include major whiskey categories
        assert any(cat in query_str for cat in ["bourbon", "scotch", "single malt"])

    def test_port_queries_include_styles(self):
        """Should include various port styles."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("port_wine")

        query_str = " ".join(queries).lower()
        # Should include port styles
        assert any(style in query_str for style in ["tawny", "vintage", "ruby"])

    def test_category_filter_adds_specific_query(self):
        """Should add category-specific query when provided."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey", category="bourbon")

        # Should include a query with the category
        category_queries = [q for q in queries if "bourbon" in q.lower()]
        assert len(category_queries) > 0


class TestQueryBuilderProductQueries:
    """Tests for building product-specific queries."""

    def test_build_product_price_query(self):
        """Should build price search for product."""
        product = MagicMock()
        product.extracted_data = {
            "name": "Glenfiddich 12",
            "brand": "Glenfiddich",
        }

        builder = QueryBuilder()
        query = builder.build_product_price_query(product)

        assert "Glenfiddich 12" in query
        assert "buy" in query.lower() or "price" in query.lower()

    def test_build_product_price_query_quoted_name(self):
        """Should quote product name for exact match."""
        product = MagicMock()
        product.extracted_data = {
            "name": "Glenfiddich 12 Year Old",
            "brand": "Glenfiddich",
        }

        builder = QueryBuilder()
        query = builder.build_product_price_query(product)

        # Name should be quoted for exact match
        assert '"Glenfiddich 12 Year Old"' in query

    def test_build_product_review_query(self):
        """Should build review search for product."""
        product = MagicMock()
        product.extracted_data = {
            "name": "Lagavulin 16",
        }

        builder = QueryBuilder()
        query = builder.build_product_review_query(product)

        assert "Lagavulin 16" in query
        assert "review" in query.lower()

    def test_build_product_review_query_includes_tasting_notes(self):
        """Should include tasting notes in review query."""
        product = MagicMock()
        product.extracted_data = {"name": "Test Whisky"}

        builder = QueryBuilder()
        query = builder.build_product_review_query(product)

        assert "tasting" in query.lower() or "notes" in query.lower()

    def test_build_product_image_query(self):
        """Should build image search for product."""
        product = MagicMock()
        product.extracted_data = {
            "name": "Macallan 18",
            "brand": "Macallan",
        }

        builder = QueryBuilder()
        query = builder.build_product_image_query(product)

        assert "Macallan" in query
        assert "bottle" in query.lower() or "whisky" in query.lower()

    def test_build_product_news_query(self):
        """Should build news search for product."""
        product = MagicMock()
        product.extracted_data = {"name": "Buffalo Trace"}

        builder = QueryBuilder()
        query = builder.build_product_news_query(product)

        assert "Buffalo Trace" in query
        assert "news" in query.lower()

    def test_handles_missing_product_name(self):
        """Should handle missing product name gracefully."""
        product = MagicMock()
        product.extracted_data = {}

        builder = QueryBuilder()
        query = builder.build_product_price_query(product)

        # Should not raise, but return a query (possibly empty name)
        assert isinstance(query, str)

    def test_handles_missing_brand(self):
        """Should handle missing brand gracefully."""
        product = MagicMock()
        product.extracted_data = {"name": "Test Whisky"}

        builder = QueryBuilder()
        query = builder.build_product_price_query(product)

        assert "Test Whisky" in query

    def test_strips_whitespace_from_query(self):
        """Should strip extra whitespace from queries."""
        product = MagicMock()
        product.extracted_data = {
            "name": "  Test Whisky  ",
            "brand": "",
        }

        builder = QueryBuilder()
        query = builder.build_product_price_query(product)

        # Should not have leading/trailing spaces
        assert query == query.strip()
        # Should not have double spaces
        assert "  " not in query


class TestQueryBuilderWhiskeyQueries:
    """Tests for whiskey-specific query building."""

    def test_whiskey_best_lists_queries(self):
        """Should include best lists queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey")

        query_str = " ".join(queries).lower()
        assert "best" in query_str

    def test_whiskey_award_queries(self):
        """Should include award-related queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey")

        query_str = " ".join(queries).lower()
        assert "award" in query_str or "winner" in query_str or "year" in query_str

    def test_whiskey_new_release_queries(self):
        """Should include new release queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("whiskey")

        query_str = " ".join(queries).lower()
        assert "new" in query_str or "release" in query_str


class TestQueryBuilderPortQueries:
    """Tests for port wine-specific query building."""

    def test_port_best_lists_queries(self):
        """Should include best lists queries for port."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("port_wine")

        query_str = " ".join(queries).lower()
        assert "best" in query_str

    def test_port_style_queries(self):
        """Should include port style queries."""
        builder = QueryBuilder()
        queries = builder.build_generic_queries("port_wine")

        query_str = " ".join(queries).lower()
        # Should include at least one style
        assert any(style in query_str for style in ["tawny", "vintage", "ruby", "lbv"])
