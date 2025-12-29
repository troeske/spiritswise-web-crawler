"""
Tests for Article Finder.

Phase 4: Product Enrichment - TDD Tests for article_finder.py
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from crawler.discovery.enrichment.article_finder import ArticleFinder, ArticleAggregator


@pytest.fixture
def mock_client():
    """Create a mock SerpAPIClient."""
    return MagicMock()


@pytest.fixture
def article_finder(mock_client):
    """Create an ArticleFinder with mock client."""
    return ArticleFinder(client=mock_client)


@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct."""
    product = MagicMock()
    product.extracted_data = {
        "name": "Ardbeg Uigeadail",
        "brand": "Ardbeg",
    }
    product.product_type = "whisky"
    return product


class TestArticleFinderInit:
    """Tests for ArticleFinder initialization."""

    def test_init_with_client(self, mock_client):
        """Should initialize with provided client."""
        finder = ArticleFinder(client=mock_client)
        assert finder.client == mock_client

    def test_init_creates_parser(self, mock_client):
        """Should create NewsResultParser."""
        finder = ArticleFinder(client=mock_client)
        assert finder.parser is not None


class TestFindArticles:
    """Tests for find_articles method."""

    def test_find_articles_returns_list(self, article_finder, mock_client, mock_product):
        """Should return list of article entries."""
        mock_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Ardbeg Uigeadail Wins Award",
                    "link": "https://whiskymagazine.com/ardbeg",
                    "source": {"name": "Whisky Magazine"},
                    "date": "2 days ago",
                    "snippet": "The acclaimed Ardbeg Uigeadail...",
                }
            ]
        }

        articles = article_finder.find_articles(mock_product)

        assert isinstance(articles, list)

    def test_find_articles_includes_url_title_source_date(self, article_finder, mock_client, mock_product):
        """Should include url, title, source, date in results."""
        mock_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Ardbeg Uigeadail Review",
                    "link": "https://whiskymagazine.com/review",
                    "source": {"name": "Whisky Magazine"},
                    "date": "1 week ago",
                    "snippet": "Our review of the famous Ardbeg.",
                }
            ]
        }

        articles = article_finder.find_articles(mock_product)

        assert len(articles) > 0
        first = articles[0]
        assert "url" in first
        assert "title" in first
        assert "source" in first
        assert "date" in first
        assert "snippet" in first

    def test_find_articles_filters_old_articles(self, article_finder, mock_client, mock_product):
        """Should filter out articles older than threshold."""
        mock_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Recent Article",
                    "link": "https://site1.com/recent",
                    "source": {"name": "Site 1"},
                    "date": "2 days ago",
                    "snippet": "Recent news about Ardbeg.",
                },
                {
                    "title": "Old Article",
                    "link": "https://site2.com/old",
                    "source": {"name": "Site 2"},
                    "date": "2 years ago",
                    "snippet": "Old news about Ardbeg.",
                },
            ]
        }

        articles = article_finder.find_articles(mock_product, max_age_days=365)

        # Should only include recent article
        assert len(articles) == 1
        assert "Recent" in articles[0]["title"]

    def test_find_articles_handles_api_error(self, article_finder, mock_client, mock_product):
        """Should return empty list on API error."""
        mock_client.google_news.side_effect = Exception("API Error")

        articles = article_finder.find_articles(mock_product)

        assert articles == []

    def test_find_articles_respects_max_results(self, article_finder, mock_client, mock_product):
        """Should respect max_results limit."""
        mock_client.google_news.return_value = {
            "news_results": [
                {
                    "title": f"Article {i}",
                    "link": f"https://site{i}.com",
                    "source": {"name": f"Site {i}"},
                    "date": "1 day ago",
                    "snippet": "",
                }
                for i in range(20)
            ]
        }

        articles = article_finder.find_articles(mock_product, max_results=5)

        assert len(articles) <= 5

    def test_find_articles_includes_thumbnail(self, article_finder, mock_client, mock_product):
        """Should include thumbnail URL when available."""
        mock_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Article with Image",
                    "link": "https://site.com/article",
                    "source": {"name": "Site"},
                    "date": "1 day ago",
                    "snippet": "News about Ardbeg.",
                    "thumbnail": "https://site.com/thumb.jpg",
                }
            ]
        }

        articles = article_finder.find_articles(mock_product)

        assert articles[0].get("thumbnail") == "https://site.com/thumb.jpg"


class TestParseDateAge:
    """Tests for _parse_date_age method."""

    def test_parses_days_ago(self, article_finder):
        """Should parse 'X days ago' format."""
        days = article_finder._parse_date_age("3 days ago")
        assert days == 3

    def test_parses_weeks_ago(self, article_finder):
        """Should parse 'X weeks ago' format."""
        days = article_finder._parse_date_age("2 weeks ago")
        assert days == 14

    def test_parses_months_ago(self, article_finder):
        """Should parse 'X months ago' format."""
        days = article_finder._parse_date_age("1 month ago")
        assert days == 30

    def test_parses_years_ago(self, article_finder):
        """Should parse 'X years ago' format."""
        days = article_finder._parse_date_age("2 years ago")
        assert days == 730

    def test_parses_hours_ago(self, article_finder):
        """Should parse 'X hours ago' format as 0 days."""
        days = article_finder._parse_date_age("5 hours ago")
        assert days == 0

    def test_parses_yesterday(self, article_finder):
        """Should parse 'yesterday' format."""
        days = article_finder._parse_date_age("yesterday")
        assert days == 1

    def test_returns_max_for_unknown_format(self, article_finder):
        """Should return large number for unknown formats."""
        days = article_finder._parse_date_age("unknown format")
        assert days >= 9999


class TestArticleAggregator:
    """Tests for ArticleAggregator."""

    def test_aggregates_articles_to_mentions(self, mock_product):
        """Should add articles as press mentions."""
        aggregator = ArticleAggregator()
        articles = [
            {
                "url": "https://site1.com/article1",
                "title": "Article 1",
                "source": "Site 1",
                "date": "2 days ago",
                "snippet": "Great whisky.",
            },
            {
                "url": "https://site2.com/article2",
                "title": "Article 2",
                "source": "Site 2",
                "date": "1 week ago",
                "snippet": "Another article.",
            },
        ]

        aggregator.aggregate_articles(mock_product, articles)

        assert mock_product.add_press_mention.call_count == 2

    def test_saves_product(self, mock_product):
        """Should save the product after aggregation."""
        aggregator = ArticleAggregator()

        aggregator.aggregate_articles(mock_product, [])

        mock_product.save.assert_called_once()

    def test_handles_empty_articles(self, mock_product):
        """Should handle empty articles list."""
        aggregator = ArticleAggregator()

        aggregator.aggregate_articles(mock_product, [])

        mock_product.add_press_mention.assert_not_called()
        mock_product.save.assert_called_once()

    def test_includes_article_metadata(self, mock_product):
        """Should include all article metadata in mention."""
        aggregator = ArticleAggregator()
        articles = [
            {
                "url": "https://site.com/article",
                "title": "Test Article",
                "source": "Test Site",
                "date": "1 day ago",
                "snippet": "Test snippet.",
                "thumbnail": "https://site.com/thumb.jpg",
            }
        ]

        aggregator.aggregate_articles(mock_product, articles)

        call_args = mock_product.add_press_mention.call_args[0][0]
        assert call_args["url"] == "https://site.com/article"
        assert call_args["title"] == "Test Article"
        assert call_args["source"] == "Test Site"
