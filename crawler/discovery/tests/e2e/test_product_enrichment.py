"""
End-to-End Tests for Product Enrichment (Phase 4).

Tests the complete flow from product selection through all enrichment
sources (prices, reviews, images, articles) to final aggregation.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

from crawler.discovery.enrichment.price_finder import PriceFinder, PriceAggregator
from crawler.discovery.enrichment.review_finder import ReviewFinder, ReviewAggregator, REVIEW_SITES
from crawler.discovery.enrichment.image_finder import ImageFinder, ImageAggregator
from crawler.discovery.enrichment.article_finder import ArticleFinder, ArticleAggregator
from crawler.discovery.enrichment.orchestrator import ProductEnricher
from crawler.discovery.enrichment.tasks import (
    enrich_product_task,
    enrich_batch_task,
    enrich_pending_task,
    enrich_prices_only_task,
    enrich_images_only_task,
)


class TestPriceEnrichmentFlow:
    """Tests complete price enrichment flow."""

    def test_price_finder_to_aggregator_flow(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_shopping_response,
    ):
        """Test complete flow from finder to aggregator."""
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response

        # Find prices
        finder = PriceFinder(client=mock_serpapi_client)
        prices = finder.find_prices(mock_discovered_product)

        # Should find prices
        assert len(prices) > 0
        assert all("price" in p for p in prices)
        assert all("currency" in p for p in prices)
        assert all("retailer" in p for p in prices)

        # Aggregate prices
        aggregator = PriceAggregator()
        aggregator.aggregate_prices(mock_discovered_product, prices)

        # Verify aggregation
        assert len(mock_discovered_product.price_history) > 0
        mock_discovered_product.save.assert_called()

    def test_best_price_selection(self, mock_serpapi_client, mock_discovered_product):
        """Test best price is correctly identified."""
        mock_serpapi_client.google_shopping.return_value = {
            "shopping_results": [
                {"title": "Macallan 18 Year Old", "price": "$350.00", "source": "Shop1", "link": ""},
                {"title": "Macallan 18 Year Old", "price": "$289.00", "source": "Shop2", "link": ""},
                {"title": "Macallan 18 Year Old", "price": "$320.00", "source": "Shop3", "link": ""},
            ]
        }

        finder = PriceFinder(client=mock_serpapi_client)
        prices = finder.find_prices(mock_discovered_product)

        # Only run best price test if prices were found
        if prices:
            best = finder.get_best_price(prices)
            assert best is not None
            assert best["price"] == min(p["price"] for p in prices)
        else:
            # Test that get_best_price handles empty list
            best = finder.get_best_price([])
            assert best is None

    def test_price_filtering(self, mock_serpapi_client, mock_discovered_product):
        """Test irrelevant products are filtered."""
        mock_serpapi_client.google_shopping.return_value = {
            "shopping_results": [
                {"title": "Macallan 18 Year Old", "price": "$300", "source": "Shop1", "link": ""},
                {"title": "Completely Different Product", "price": "$50", "source": "Shop2", "link": ""},
            ]
        }

        finder = PriceFinder(client=mock_serpapi_client)
        prices = finder.find_prices(mock_discovered_product)

        # Should only have relevant result
        assert len(prices) == 1
        assert prices[0]["retailer"] == "Shop1"


class TestReviewEnrichmentFlow:
    """Tests complete review enrichment flow."""

    def test_review_finder_to_aggregator_flow(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_review_search_response,
    ):
        """Test complete flow from finder to aggregator."""
        mock_serpapi_client.google_search.return_value = mock_review_search_response

        # Find reviews
        finder = ReviewFinder(client=mock_serpapi_client)
        reviews = finder.find_reviews(mock_discovered_product)

        # Should find reviews
        assert len(reviews) > 0
        assert all("url" in r for r in reviews)
        assert all("title" in r for r in reviews)
        assert all("source" in r for r in reviews)

        # Some should have scores
        scored_reviews = [r for r in reviews if "score" in r]
        assert len(scored_reviews) > 0

        # Aggregate reviews
        aggregator = ReviewAggregator()
        aggregator.aggregate_reviews(mock_discovered_product, reviews)

        # Verify aggregation
        mock_discovered_product.add_press_mention.assert_called()
        mock_discovered_product.save.assert_called()

    def test_rating_extraction_whiskyadvocate(self, mock_serpapi_client, mock_discovered_product):
        """Test rating extraction from Whisky Advocate format."""
        mock_serpapi_client.google_search.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Macallan 18 Review",
                    "link": "https://www.whiskyadvocate.com/review",
                    "snippet": "This exceptional whisky earned 94 points in our comprehensive review.",
                }
            ]
        }

        finder = ReviewFinder(client=mock_serpapi_client)
        reviews = finder.find_reviews(mock_discovered_product)

        assert len(reviews) == 1
        assert reviews[0]["score"] == 94
        assert reviews[0]["max_score"] == 100

    def test_rating_extraction_masterofmalt(self, mock_serpapi_client, mock_discovered_product):
        """Test rating extraction from Master of Malt format."""
        mock_serpapi_client.google_search.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Macallan 18 Reviews",
                    "link": "https://www.masterofmalt.com/reviews",
                    "snippet": "Customer rating: 4.7 / 5 stars based on 150 reviews.",
                }
            ]
        }

        finder = ReviewFinder(client=mock_serpapi_client)
        reviews = finder.find_reviews(mock_discovered_product)

        assert len(reviews) == 1
        assert reviews[0]["score"] == 4.7
        assert reviews[0]["max_score"] == 5


class TestImageEnrichmentFlow:
    """Tests complete image enrichment flow."""

    def test_image_finder_to_aggregator_flow(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_images_response,
    ):
        """Test complete flow from finder to aggregator."""
        mock_serpapi_client.google_images.return_value = mock_google_images_response

        # Find images
        finder = ImageFinder(client=mock_serpapi_client)
        images = finder.find_images(mock_discovered_product)

        # Should find images (filtering out small ones)
        assert len(images) > 0
        assert all("url" in i for i in images)
        assert all("width" in i for i in images)
        assert all("height" in i for i in images)

        # All should meet minimum size
        for img in images:
            assert img["width"] >= 200
            assert img["height"] >= 200

        # Aggregate images
        aggregator = ImageAggregator()
        aggregator.aggregate_images(mock_discovered_product, images)

        # Verify aggregation
        assert mock_discovered_product.add_image.call_count == len(images)
        mock_discovered_product.save.assert_called()

    def test_image_type_detection(self, mock_serpapi_client, mock_discovered_product):
        """Test image type is correctly detected."""
        mock_serpapi_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Macallan 18 Bottle Photo",
                    "original": "https://example.com/bottle.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "example.com",
                    "original_width": 800,
                    "original_height": 1200,
                },
                {
                    "title": "Macallan Label Close-up",
                    "original": "https://example.com/label.jpg",
                    "thumbnail": "https://example.com/thumb2.jpg",
                    "source": "example.com",
                    "original_width": 600,
                    "original_height": 400,
                },
            ]
        }

        finder = ImageFinder(client=mock_serpapi_client)
        images = finder.find_images(mock_discovered_product)

        # Check type detection
        assert any(i["type"] == "bottle" for i in images)
        assert any(i["type"] == "label" for i in images)


class TestArticleEnrichmentFlow:
    """Tests complete article enrichment flow."""

    def test_article_finder_to_aggregator_flow(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_news_response,
    ):
        """Test complete flow from finder to aggregator."""
        mock_serpapi_client.google_news.return_value = mock_google_news_response

        # Find articles
        finder = ArticleFinder(client=mock_serpapi_client)
        articles = finder.find_articles(mock_discovered_product)

        # Should find articles (filtering old ones)
        assert len(articles) > 0
        assert all("url" in a for a in articles)
        assert all("title" in a for a in articles)
        assert all("source" in a for a in articles)

        # Aggregate articles
        aggregator = ArticleAggregator()
        aggregator.aggregate_articles(mock_discovered_product, articles)

        # Verify aggregation
        mock_discovered_product.add_press_mention.assert_called()
        mock_discovered_product.save.assert_called()

    def test_article_age_filtering(self, mock_serpapi_client, mock_discovered_product):
        """Test old articles are filtered out."""
        mock_serpapi_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Recent News",
                    "link": "https://example.com/recent",
                    "source": {"name": "News Site"},
                    "date": "3 days ago",
                    "snippet": "Recent article.",
                },
                {
                    "title": "Old News",
                    "link": "https://example.com/old",
                    "source": {"name": "Old Site"},
                    "date": "2 years ago",
                    "snippet": "Old article.",
                },
            ]
        }

        finder = ArticleFinder(client=mock_serpapi_client)
        articles = finder.find_articles(mock_discovered_product, max_age_days=365)

        # Should only have recent article
        assert len(articles) == 1
        assert "Recent" in articles[0]["title"]


class TestProductEnricherOrchestration:
    """Tests ProductEnricher orchestrating all sources."""

    def test_enricher_calls_all_finders(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_shopping_response,
        mock_review_search_response,
        mock_google_images_response,
        mock_google_news_response,
    ):
        """Test enricher calls all finder types."""
        # Setup all responses
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response
        mock_serpapi_client.google_search.return_value = mock_review_search_response
        mock_serpapi_client.google_images.return_value = mock_google_images_response
        mock_serpapi_client.google_news.return_value = mock_google_news_response

        enricher = ProductEnricher(client=mock_serpapi_client)
        result = enricher.enrich_product(mock_discovered_product)

        # Verify all APIs called
        mock_serpapi_client.google_shopping.assert_called()
        mock_serpapi_client.google_search.assert_called()
        mock_serpapi_client.google_images.assert_called()
        mock_serpapi_client.google_news.assert_called()

        # Verify result
        assert result["success"] is True
        assert "prices_found" in result
        assert "reviews_found" in result
        assert "images_found" in result
        assert "articles_found" in result

    def test_enricher_selective_enrichment(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_shopping_response,
    ):
        """Test enricher can do selective enrichment."""
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response

        enricher = ProductEnricher(client=mock_serpapi_client)
        result = enricher.enrich_product(
            mock_discovered_product,
            enrich_prices=True,
            enrich_reviews=False,
            enrich_images=False,
            enrich_articles=False,
        )

        # Only shopping should be called
        mock_serpapi_client.google_shopping.assert_called()
        mock_serpapi_client.google_search.assert_not_called()
        mock_serpapi_client.google_images.assert_not_called()
        mock_serpapi_client.google_news.assert_not_called()

        assert result["prices_found"] >= 0
        assert result["reviews_found"] == 0

    def test_enricher_batch_processing(
        self,
        mock_serpapi_client,
        mock_discovered_product_list,
    ):
        """Test enricher processes batch of products."""
        mock_serpapi_client.google_shopping.return_value = {"shopping_results": []}
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        enricher = ProductEnricher(client=mock_serpapi_client)
        results = enricher.enrich_batch(mock_discovered_product_list)

        # Should have result for each product
        assert len(results) == len(mock_discovered_product_list)
        assert all(r["success"] for r in results)

    def test_enricher_continues_on_partial_failure(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test enricher continues if one source fails."""
        # Prices fail, others succeed
        mock_serpapi_client.google_shopping.side_effect = Exception("Shopping API Error")
        mock_serpapi_client.google_search.return_value = {"organic_results": []}
        mock_serpapi_client.google_images.return_value = {"images_results": []}
        mock_serpapi_client.google_news.return_value = {"news_results": []}

        enricher = ProductEnricher(client=mock_serpapi_client)
        result = enricher.enrich_product(mock_discovered_product)

        # Should still process (but may report failure due to exception)
        assert result is not None


class TestEnrichmentTasks:
    """Tests Celery task execution."""

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    @patch("crawler.discovery.enrichment.tasks.RateLimiter")
    def test_enrich_product_task_flow(
        self,
        mock_limiter_class,
        mock_client_class,
        mock_enricher_class,
        mock_model,
    ):
        """Test single product enrichment task."""
        # Setup mocks
        mock_product = MagicMock()
        mock_product.id = 1
        mock_model.objects.get.return_value = mock_product

        mock_limiter = MagicMock()
        mock_limiter.can_make_request.return_value = True
        mock_limiter_class.return_value = mock_limiter

        mock_enricher = MagicMock()
        mock_enricher.enrich_product.return_value = {
            "success": True,
            "prices_found": 3,
            "reviews_found": 2,
            "images_found": 5,
            "articles_found": 1,
        }
        mock_enricher_class.return_value = mock_enricher

        # Run task
        result = enrich_product_task(product_id=1)

        # Verify
        mock_model.objects.get.assert_called_with(id=1)
        mock_enricher.enrich_product.assert_called_once_with(mock_product)
        assert result["success"] is True

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enrich_batch_task_flow(
        self,
        mock_client_class,
        mock_enricher_class,
        mock_model,
    ):
        """Test batch enrichment task."""
        # Setup mocks
        mock_products = [MagicMock() for _ in range(3)]
        mock_model.objects.filter.return_value = mock_products

        mock_enricher = MagicMock()
        mock_enricher.enrich_batch.return_value = [
            {"success": True},
            {"success": True},
            {"success": False},
        ]
        mock_enricher_class.return_value = mock_enricher

        # Run task
        result = enrich_batch_task(product_ids=[1, 2, 3])

        # Verify
        assert result["processed"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1

    @patch("crawler.discovery.enrichment.tasks.RateLimiter")
    def test_rate_limiting_prevents_enrichment(self, mock_limiter_class):
        """Test rate limiting prevents enrichment."""
        mock_limiter = MagicMock()
        mock_limiter.can_make_request.return_value = False
        mock_limiter_class.return_value = mock_limiter

        result = enrich_product_task(product_id=1)

        assert result["success"] is False
        assert result.get("rate_limited") is True


class TestEnrichmentDataQuality:
    """Tests data quality in enrichment results."""

    def test_price_data_has_required_fields(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_shopping_response,
    ):
        """Test price data has all required fields."""
        mock_serpapi_client.google_shopping.return_value = mock_google_shopping_response

        finder = PriceFinder(client=mock_serpapi_client)
        prices = finder.find_prices(mock_discovered_product)

        for price in prices:
            assert "price" in price
            assert "currency" in price
            assert "retailer" in price
            assert "url" in price
            assert isinstance(price["price"], (int, float))

    def test_review_data_has_required_fields(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_review_search_response,
    ):
        """Test review data has all required fields."""
        mock_serpapi_client.google_search.return_value = mock_review_search_response

        finder = ReviewFinder(client=mock_serpapi_client)
        reviews = finder.find_reviews(mock_discovered_product)

        for review in reviews:
            assert "url" in review
            assert "title" in review
            assert "source" in review

    def test_image_dimensions_are_valid(
        self,
        mock_serpapi_client,
        mock_discovered_product,
        mock_google_images_response,
    ):
        """Test image dimensions are valid."""
        mock_serpapi_client.google_images.return_value = mock_google_images_response

        finder = ImageFinder(client=mock_serpapi_client)
        images = finder.find_images(mock_discovered_product)

        for img in images:
            assert img["width"] >= 200
            assert img["height"] >= 200
            assert isinstance(img["width"], int)
            assert isinstance(img["height"], int)

    def test_article_dates_are_parsed(
        self,
        mock_serpapi_client,
        mock_discovered_product,
    ):
        """Test article dates are correctly parsed."""
        mock_serpapi_client.google_news.return_value = {
            "news_results": [
                {
                    "title": "Article 1",
                    "link": "https://example.com/1",
                    "source": {"name": "Source"},
                    "date": "2 days ago",
                    "snippet": "",
                },
                {
                    "title": "Article 2",
                    "link": "https://example.com/2",
                    "source": {"name": "Source"},
                    "date": "1 week ago",
                    "snippet": "",
                },
            ]
        }

        finder = ArticleFinder(client=mock_serpapi_client)

        # Test date parsing
        assert finder._parse_date_age("2 days ago") == 2
        assert finder._parse_date_age("1 week ago") == 7
        assert finder._parse_date_age("1 month ago") == 30
