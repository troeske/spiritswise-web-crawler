"""
Tests for Review Finder.

Phase 4: Product Enrichment - TDD Tests for review_finder.py
"""

import pytest
from unittest.mock import MagicMock

from crawler.discovery.enrichment.review_finder import (
    ReviewFinder,
    ReviewAggregator,
    REVIEW_SITES,
)


@pytest.fixture
def mock_client():
    """Create a mock SerpAPIClient."""
    return MagicMock()


@pytest.fixture
def review_finder(mock_client):
    """Create a ReviewFinder with mock client."""
    return ReviewFinder(client=mock_client)


@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct."""
    product = MagicMock()
    product.extracted_data = {
        "name": "Lagavulin 16 Year Old",
    }
    return product


class TestReviewSitesConfig:
    """Tests for REVIEW_SITES configuration."""

    def test_review_sites_not_empty(self):
        """Should have review sites defined."""
        assert len(REVIEW_SITES) > 0

    def test_whisky_advocate_config(self):
        """Should have whiskyadvocate.com config."""
        assert "whiskyadvocate.com" in REVIEW_SITES
        config = REVIEW_SITES["whiskyadvocate.com"]
        assert config["max_score"] == 100
        assert "pattern" in config

    def test_masterofmalt_config(self):
        """Should have masterofmalt.com config."""
        assert "masterofmalt.com" in REVIEW_SITES
        config = REVIEW_SITES["masterofmalt.com"]
        assert config["max_score"] == 5


class TestReviewFinderInit:
    """Tests for ReviewFinder initialization."""

    def test_init_with_client(self, mock_client):
        """Should initialize with provided client."""
        finder = ReviewFinder(client=mock_client)
        assert finder.client == mock_client

    def test_init_creates_parser(self, mock_client):
        """Should create OrganicResultParser."""
        finder = ReviewFinder(client=mock_client)
        assert finder.parser is not None


class TestFindReviews:
    """Tests for find_reviews method."""

    def test_find_reviews_returns_list(self, review_finder, mock_client, mock_product):
        """Should return list of review entries."""
        mock_client.google_search.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Lagavulin 16 Review",
                    "link": "https://whiskyadvocate.com/lagavulin-16-review",
                    "snippet": "Rated 94 points. A classic Islay whisky.",
                }
            ]
        }

        reviews = review_finder.find_reviews(mock_product)

        assert isinstance(reviews, list)

    def test_find_reviews_includes_url_title_source(self, review_finder, mock_client, mock_product):
        """Should include url, title, source in results."""
        mock_client.google_search.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Lagavulin 16 Review",
                    "link": "https://whiskyadvocate.com/review",
                    "snippet": "A great whisky.",
                }
            ]
        }

        reviews = review_finder.find_reviews(mock_product)

        assert len(reviews) > 0
        first = reviews[0]
        assert "url" in first
        assert "title" in first
        assert "source" in first

    def test_find_reviews_extracts_rating_when_found(self, review_finder, mock_client, mock_product):
        """Should extract rating from snippet when found."""
        mock_client.google_search.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Lagavulin 16 Review",
                    "link": "https://whiskyadvocate.com/review",
                    "snippet": "Rated 94 points. Excellent whisky.",
                }
            ]
        }

        reviews = review_finder.find_reviews(mock_product)

        assert len(reviews) > 0
        first = reviews[0]
        assert "score" in first
        assert first["score"] == 94
        assert first["max_score"] == 100

    def test_find_reviews_handles_api_error(self, review_finder, mock_client, mock_product):
        """Should return empty list on API error."""
        mock_client.google_search.side_effect = Exception("API Error")

        reviews = review_finder.find_reviews(mock_product)

        assert reviews == []

    def test_find_reviews_respects_max_results(self, review_finder, mock_client, mock_product):
        """Should respect max_results limit."""
        mock_client.google_search.return_value = {
            "organic_results": [
                {"position": i, "title": f"Review {i}", "link": f"https://site{i}.com", "snippet": ""}
                for i in range(20)
            ]
        }

        reviews = review_finder.find_reviews(mock_product, max_results=5)

        assert len(reviews) <= 5


class TestExtractRating:
    """Tests for _extract_rating method."""

    def test_extract_rating_from_whiskyadvocate(self, review_finder):
        """Should extract rating from whiskyadvocate format."""
        rating = review_finder._extract_rating(
            "whiskyadvocate.com",
            "This whisky earned 94 points in our review."
        )

        assert rating is not None
        assert rating["score"] == 94
        assert rating["max_score"] == 100

    def test_extract_rating_from_masterofmalt(self, review_finder):
        """Should extract rating from masterofmalt format."""
        rating = review_finder._extract_rating(
            "masterofmalt.com",
            "Customer rating: 4.5 / 5 stars."
        )

        assert rating is not None
        assert rating["score"] == 4.5
        assert rating["max_score"] == 5

    def test_extract_rating_generic_100_scale(self, review_finder):
        """Should extract generic X/100 format."""
        rating = review_finder._extract_rating(
            "unknownsite.com",
            "We give this whisky a score of 88/100."
        )

        assert rating is not None
        assert rating["score"] == 88
        assert rating["max_score"] == 100

    def test_extract_rating_generic_5_scale(self, review_finder):
        """Should extract generic X/5 format."""
        rating = review_finder._extract_rating(
            "unknownsite.com",
            "Rating: 4.2/5 stars"
        )

        assert rating is not None
        assert rating["score"] == 4.2
        assert rating["max_score"] == 5

    def test_extract_rating_stars_format(self, review_finder):
        """Should extract X stars format."""
        rating = review_finder._extract_rating(
            "unknownsite.com",
            "A solid 4.5 stars whisky."
        )

        assert rating is not None
        assert rating["score"] == 4.5

    def test_extract_rating_returns_none_when_not_found(self, review_finder):
        """Should return None when no rating found."""
        rating = review_finder._extract_rating(
            "unknownsite.com",
            "This is a great whisky without any scores mentioned."
        )

        assert rating is None


class TestReviewAggregator:
    """Tests for ReviewAggregator."""

    def test_aggregates_reviews_to_ratings(self, mock_product):
        """Should add reviews with scores as ratings."""
        aggregator = ReviewAggregator()
        reviews = [
            {
                "url": "https://whiskyadvocate.com/review",
                "title": "Review Title",
                "source": "whiskyadvocate.com",
                "snippet": "Great whisky",
                "score": 94,
                "max_score": 100,
            }
        ]

        aggregator.aggregate_reviews(mock_product, reviews)

        mock_product.add_rating.assert_called_once()
        call_args = mock_product.add_rating.call_args[0][0]
        assert call_args["score"] == 94
        assert call_args["source"] == "whiskyadvocate.com"

    def test_aggregates_reviews_to_mentions(self, mock_product):
        """Should add all reviews as article mentions."""
        aggregator = ReviewAggregator()
        reviews = [
            {
                "url": "https://site.com/review",
                "title": "Review Title",
                "source": "site.com",
                "snippet": "Great whisky",
            }
        ]

        aggregator.aggregate_reviews(mock_product, reviews)

        mock_product.add_press_mention.assert_called_once()

    def test_skips_rating_when_no_score(self, mock_product):
        """Should not add rating when no score in review."""
        aggregator = ReviewAggregator()
        reviews = [
            {
                "url": "https://site.com/review",
                "title": "Review Title",
                "source": "site.com",
                "snippet": "Great whisky",
                # No score/max_score
            }
        ]

        aggregator.aggregate_reviews(mock_product, reviews)

        mock_product.add_rating.assert_not_called()
        # Should still add as mention
        mock_product.add_press_mention.assert_called_once()

    def test_saves_product(self, mock_product):
        """Should save the product after aggregation."""
        aggregator = ReviewAggregator()

        aggregator.aggregate_reviews(mock_product, [])

        mock_product.save.assert_called_once()
