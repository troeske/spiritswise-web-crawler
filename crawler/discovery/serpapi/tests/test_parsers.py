"""
Tests for Result Parsers.

Phase 2: SerpAPI Integration - TDD Tests for parsers.py
"""

import pytest

from crawler.discovery.serpapi.parsers import (
    OrganicResultParser,
    ShoppingResultParser,
    ImageResultParser,
    NewsResultParser,
)


class TestOrganicResultParser:
    """Tests for OrganicResultParser."""

    def test_extracts_url_title_snippet(self):
        """Should extract url, title, snippet from results."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Best Whisky 2025",
                    "link": "https://example.com/best-whisky",
                    "snippet": "Our top picks for whisky this year.",
                }
            ]
        }

        results = parser.parse(response)

        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/best-whisky"
        assert results[0]["title"] == "Best Whisky 2025"
        assert results[0]["snippet"] == "Our top picks for whisky this year."

    def test_extracts_source_from_url(self):
        """Should extract domain as source."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Test",
                    "link": "https://www.whiskyadvocate.com/review/macallan",
                    "snippet": "Review...",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["source"] == "whiskyadvocate.com"

    def test_extracts_source_without_www(self):
        """Should strip www. from domain."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Test",
                    "link": "https://robbreport.com/article",
                    "snippet": "",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["source"] == "robbreport.com"

    def test_extracts_position(self):
        """Should extract search position."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {"position": 3, "title": "Test", "link": "https://example.com", "snippet": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["position"] == 3

    def test_handles_empty_results(self):
        """Should handle empty results gracefully."""
        parser = OrganicResultParser()
        response = {"organic_results": []}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_organic_results(self):
        """Should handle missing organic_results key."""
        parser = OrganicResultParser()
        response = {}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_fields(self):
        """Should handle missing fields in result items."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {"position": 1}  # Missing title, link, snippet
            ]
        }

        results = parser.parse(response)

        assert len(results) == 1
        assert results[0]["url"] == ""
        assert results[0]["title"] == ""
        assert results[0]["snippet"] == ""

    def test_parses_multiple_results(self):
        """Should parse multiple results."""
        parser = OrganicResultParser()
        response = {
            "organic_results": [
                {"position": 1, "title": "First", "link": "https://a.com", "snippet": "A"},
                {"position": 2, "title": "Second", "link": "https://b.com", "snippet": "B"},
                {"position": 3, "title": "Third", "link": "https://c.com", "snippet": "C"},
            ]
        }

        results = parser.parse(response)

        assert len(results) == 3
        assert results[0]["title"] == "First"
        assert results[2]["title"] == "Third"


class TestShoppingResultParser:
    """Tests for ShoppingResultParser."""

    def test_parses_usd_price(self):
        """Should parse $89.99 format."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {
                    "title": "Whisky",
                    "price": "$89.99",
                    "source": "Total Wine",
                    "link": "https://totalwine.com/whisky",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["price"] == 89.99
        assert results[0]["currency"] == "USD"

    def test_parses_gbp_price(self):
        """Should parse 75.00 format."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Whisky", "price": "£75.00", "source": "Master of Malt", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["price"] == 75.00
        assert results[0]["currency"] == "GBP"

    def test_parses_eur_price(self):
        """Should parse 85,00 format."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Whisky", "price": "€85,00", "source": "Retailer", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["price"] == 85.00
        assert results[0]["currency"] == "EUR"

    def test_extracts_retailer(self):
        """Should extract retailer name."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Product", "price": "$50", "source": "Amazon", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["retailer"] == "Amazon"

    def test_extracts_url(self):
        """Should extract product URL."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {
                    "title": "Product",
                    "price": "$50",
                    "source": "Shop",
                    "link": "https://shop.com/product",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["url"] == "https://shop.com/product"

    def test_extracts_thumbnail(self):
        """Should extract thumbnail URL."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {
                    "title": "Product",
                    "price": "$50",
                    "source": "Shop",
                    "link": "",
                    "thumbnail": "https://shop.com/thumb.jpg",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["thumbnail"] == "https://shop.com/thumb.jpg"

    def test_handles_malformed_price(self):
        """Should handle malformed price strings."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Product", "price": "Price unavailable", "source": "Shop", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["price"] == 0.0

    def test_handles_empty_price(self):
        """Should handle empty price."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Product", "price": "", "source": "Shop", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["price"] == 0.0
        assert results[0]["currency"] == "USD"  # Default currency

    def test_handles_price_with_comma_thousands(self):
        """Should handle prices with comma as thousands separator."""
        parser = ShoppingResultParser()
        response = {
            "shopping_results": [
                {"title": "Product", "price": "$1,299.99", "source": "Shop", "link": ""}
            ]
        }

        results = parser.parse(response)

        # Should parse correctly (implementation may vary)
        assert results[0]["price"] > 0

    def test_handles_empty_shopping_results(self):
        """Should handle empty shopping results."""
        parser = ShoppingResultParser()
        response = {"shopping_results": []}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_shopping_results(self):
        """Should handle missing shopping_results key."""
        parser = ShoppingResultParser()
        response = {}

        results = parser.parse(response)

        assert results == []


class TestImageResultParser:
    """Tests for ImageResultParser."""

    def test_extracts_image_urls(self):
        """Should extract original and thumbnail URLs."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {
                    "title": "Whisky Bottle",
                    "original": "https://example.com/bottle.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "example.com",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["url"] == "https://example.com/bottle.jpg"
        assert results[0]["thumbnail"] == "https://example.com/thumb.jpg"

    def test_extracts_dimensions(self):
        """Should extract image dimensions."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {
                    "title": "Image",
                    "original": "https://example.com/img.jpg",
                    "original_width": 800,
                    "original_height": 1200,
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["width"] == 800
        assert results[0]["height"] == 1200

    def test_extracts_source(self):
        """Should extract image source."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Image", "original": "", "source": "whiskyadvocate.com"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["source"] == "whiskyadvocate.com"

    def test_classifies_bottle_images(self):
        """Should classify bottle images correctly."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Macallan 18 Bottle", "original": "https://example.com/img.jpg"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["type"] == "bottle"

    def test_classifies_label_images(self):
        """Should classify label images correctly."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Whisky Label Close-up", "original": "https://example.com/img.jpg"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["type"] == "label"

    def test_classifies_lifestyle_images(self):
        """Should classify lifestyle images correctly."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Whisky Tasting at Bar", "original": "https://example.com/img.jpg"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["type"] == "lifestyle"

    def test_classifies_generic_product_images(self):
        """Should classify generic images as product."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Glenfiddich 12", "original": "https://example.com/img.jpg"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["type"] == "product"

    def test_handles_empty_images(self):
        """Should handle empty images results."""
        parser = ImageResultParser()
        response = {"images_results": []}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_images_results(self):
        """Should handle missing images_results key."""
        parser = ImageResultParser()
        response = {}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_dimensions(self):
        """Should handle missing dimensions."""
        parser = ImageResultParser()
        response = {
            "images_results": [
                {"title": "Image", "original": "https://example.com/img.jpg"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["width"] == 0
        assert results[0]["height"] == 0


class TestNewsResultParser:
    """Tests for NewsResultParser."""

    def test_extracts_article_data(self):
        """Should extract title, source, date, snippet."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {
                    "title": "New Whisky Released",
                    "link": "https://news.example.com/article",
                    "source": {"name": "Whisky Advocate"},
                    "date": "2 days ago",
                    "snippet": "A new whisky has been announced...",
                }
            ]
        }

        results = parser.parse(response)

        assert len(results) == 1
        assert results[0]["title"] == "New Whisky Released"
        assert results[0]["url"] == "https://news.example.com/article"
        assert results[0]["source"] == "Whisky Advocate"
        assert results[0]["date"] == "2 days ago"
        assert results[0]["snippet"] == "A new whisky has been announced..."

    def test_extracts_thumbnail(self):
        """Should extract article thumbnail."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {
                    "title": "Article",
                    "link": "",
                    "source": {"name": "Source"},
                    "thumbnail": "https://example.com/thumb.jpg",
                }
            ]
        }

        results = parser.parse(response)

        assert results[0]["thumbnail"] == "https://example.com/thumb.jpg"

    def test_sets_mention_type_to_news(self):
        """Should set mention_type to news."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {"title": "Article", "link": "", "source": {"name": "Source"}}
            ]
        }

        results = parser.parse(response)

        assert results[0]["mention_type"] == "news"

    def test_handles_missing_source_name(self):
        """Should handle missing source name."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {"title": "Article", "link": "", "source": {}}
            ]
        }

        results = parser.parse(response)

        assert results[0]["source"] == ""

    def test_handles_missing_source_dict(self):
        """Should handle missing source dict."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {"title": "Article", "link": ""}
            ]
        }

        results = parser.parse(response)

        assert results[0]["source"] == ""

    def test_handles_missing_fields(self):
        """Should handle missing optional fields."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {"title": "Article"}
            ]
        }

        results = parser.parse(response)

        assert results[0]["url"] == ""
        assert results[0]["date"] == ""
        assert results[0]["snippet"] == ""

    def test_handles_empty_news_results(self):
        """Should handle empty news results."""
        parser = NewsResultParser()
        response = {"news_results": []}

        results = parser.parse(response)

        assert results == []

    def test_handles_missing_news_results(self):
        """Should handle missing news_results key."""
        parser = NewsResultParser()
        response = {}

        results = parser.parse(response)

        assert results == []

    def test_parses_multiple_articles(self):
        """Should parse multiple news articles."""
        parser = NewsResultParser()
        response = {
            "news_results": [
                {"title": "Article 1", "link": "https://a.com", "source": {"name": "A"}},
                {"title": "Article 2", "link": "https://b.com", "source": {"name": "B"}},
            ]
        }

        results = parser.parse(response)

        assert len(results) == 2
        assert results[0]["title"] == "Article 1"
        assert results[1]["title"] == "Article 2"
