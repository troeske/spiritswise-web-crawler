"""
Tests for Product Enricher Orchestrator.

Phase 4: Product Enrichment - TDD Tests for orchestrator.py
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from crawler.discovery.enrichment.orchestrator import ProductEnricher


@pytest.fixture
def mock_client():
    """Create a mock SerpAPIClient."""
    return MagicMock()


@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct."""
    product = MagicMock()
    product.id = 1
    product.extracted_data = {
        "name": "Highland Park 12",
        "brand": "Highland Park",
    }
    product.product_type = "whisky"
    product.enrichment_status = "pending"
    return product


class TestProductEnricherInit:
    """Tests for ProductEnricher initialization."""

    def test_init_with_client(self, mock_client):
        """Should initialize with provided client."""
        enricher = ProductEnricher(client=mock_client)
        assert enricher.client == mock_client

    def test_init_creates_finders(self, mock_client):
        """Should create all finder instances."""
        enricher = ProductEnricher(client=mock_client)
        assert enricher.price_finder is not None
        assert enricher.review_finder is not None
        assert enricher.image_finder is not None
        assert enricher.article_finder is not None

    def test_init_creates_aggregators(self, mock_client):
        """Should create all aggregator instances."""
        enricher = ProductEnricher(client=mock_client)
        assert enricher.price_aggregator is not None
        assert enricher.review_aggregator is not None
        assert enricher.image_aggregator is not None
        assert enricher.article_aggregator is not None


class TestEnrichProduct:
    """Tests for enrich_product method."""

    def test_enrich_product_calls_all_finders(self, mock_client, mock_product):
        """Should call all finders for the product."""
        enricher = ProductEnricher(client=mock_client)

        # Mock all finders to return empty lists
        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.enrich_product(mock_product)

        enricher.price_finder.find_prices.assert_called_once_with(mock_product)
        enricher.review_finder.find_reviews.assert_called_once_with(mock_product)
        enricher.image_finder.find_images.assert_called_once_with(mock_product)
        enricher.article_finder.find_articles.assert_called_once_with(mock_product)

    def test_enrich_product_calls_all_aggregators(self, mock_client, mock_product):
        """Should call all aggregators with finder results."""
        enricher = ProductEnricher(client=mock_client)

        # Mock finders with sample data
        prices = [{"price": 45.99, "currency": "USD", "retailer": "Shop1", "url": ""}]
        reviews = [{"url": "", "title": "Review", "source": "site.com"}]
        images = [{"url": "", "thumbnail": "", "source": "", "type": "bottle", "width": 800, "height": 1200}]
        articles = [{"url": "", "title": "Article", "source": "", "date": "", "snippet": ""}]

        enricher.price_finder.find_prices = MagicMock(return_value=prices)
        enricher.review_finder.find_reviews = MagicMock(return_value=reviews)
        enricher.image_finder.find_images = MagicMock(return_value=images)
        enricher.article_finder.find_articles = MagicMock(return_value=articles)

        # Mock aggregators
        enricher.price_aggregator.aggregate_prices = MagicMock()
        enricher.review_aggregator.aggregate_reviews = MagicMock()
        enricher.image_aggregator.aggregate_images = MagicMock()
        enricher.article_aggregator.aggregate_articles = MagicMock()

        enricher.enrich_product(mock_product)

        enricher.price_aggregator.aggregate_prices.assert_called_once_with(mock_product, prices)
        enricher.review_aggregator.aggregate_reviews.assert_called_once_with(mock_product, reviews)
        enricher.image_aggregator.aggregate_images.assert_called_once_with(mock_product, images)
        enricher.article_aggregator.aggregate_articles.assert_called_once_with(mock_product, articles)

    def test_enrich_product_updates_status_on_success(self, mock_client, mock_product):
        """Should update enrichment_status to 'completed' on success."""
        enricher = ProductEnricher(client=mock_client)

        # Mock all finders
        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        # Mock aggregators to not fail
        enricher.price_aggregator.aggregate_prices = MagicMock()
        enricher.review_aggregator.aggregate_reviews = MagicMock()
        enricher.image_aggregator.aggregate_images = MagicMock()
        enricher.article_aggregator.aggregate_articles = MagicMock()

        enricher.enrich_product(mock_product)

        assert mock_product.enrichment_status == "completed"
        mock_product.save.assert_called()

    def test_enrich_product_updates_status_on_failure(self, mock_client, mock_product):
        """Should update enrichment_status to 'failed' on error."""
        enricher = ProductEnricher(client=mock_client)

        # Mock price_finder to raise exception
        enricher.price_finder.find_prices = MagicMock(side_effect=Exception("API Error"))

        enricher.enrich_product(mock_product)

        assert mock_product.enrichment_status == "failed"
        mock_product.save.assert_called()

    def test_enrich_product_returns_result_dict(self, mock_client, mock_product):
        """Should return a result dictionary."""
        enricher = ProductEnricher(client=mock_client)

        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.price_aggregator.aggregate_prices = MagicMock()
        enricher.review_aggregator.aggregate_reviews = MagicMock()
        enricher.image_aggregator.aggregate_images = MagicMock()
        enricher.article_aggregator.aggregate_articles = MagicMock()

        result = enricher.enrich_product(mock_product)

        assert isinstance(result, dict)
        assert "success" in result
        assert "prices_found" in result
        assert "reviews_found" in result
        assert "images_found" in result
        assert "articles_found" in result


class TestEnrichProductSelective:
    """Tests for selective enrichment."""

    def test_enrich_prices_only(self, mock_client, mock_product):
        """Should only enrich prices when specified."""
        enricher = ProductEnricher(client=mock_client)

        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.price_aggregator.aggregate_prices = MagicMock()

        enricher.enrich_product(mock_product, enrich_prices=True, enrich_reviews=False,
                               enrich_images=False, enrich_articles=False)

        enricher.price_finder.find_prices.assert_called_once()
        enricher.review_finder.find_reviews.assert_not_called()
        enricher.image_finder.find_images.assert_not_called()
        enricher.article_finder.find_articles.assert_not_called()

    def test_enrich_reviews_only(self, mock_client, mock_product):
        """Should only enrich reviews when specified."""
        enricher = ProductEnricher(client=mock_client)

        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.review_aggregator.aggregate_reviews = MagicMock()

        enricher.enrich_product(mock_product, enrich_prices=False, enrich_reviews=True,
                               enrich_images=False, enrich_articles=False)

        enricher.price_finder.find_prices.assert_not_called()
        enricher.review_finder.find_reviews.assert_called_once()
        enricher.image_finder.find_images.assert_not_called()
        enricher.article_finder.find_articles.assert_not_called()


class TestEnrichBatch:
    """Tests for batch enrichment."""

    def test_enrich_batch_processes_multiple_products(self, mock_client):
        """Should process multiple products."""
        enricher = ProductEnricher(client=mock_client)

        products = [MagicMock() for _ in range(3)]
        for p in products:
            p.extracted_data = {"name": "Test"}
            p.enrichment_status = "pending"

        # Mock all finders
        enricher.price_finder.find_prices = MagicMock(return_value=[])
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.price_aggregator.aggregate_prices = MagicMock()
        enricher.review_aggregator.aggregate_reviews = MagicMock()
        enricher.image_aggregator.aggregate_images = MagicMock()
        enricher.article_aggregator.aggregate_articles = MagicMock()

        results = enricher.enrich_batch(products)

        assert len(results) == 3
        assert enricher.price_finder.find_prices.call_count == 3

    def test_enrich_batch_continues_on_error(self, mock_client):
        """Should continue processing after individual product errors."""
        enricher = ProductEnricher(client=mock_client)

        products = [MagicMock() for _ in range(3)]
        for p in products:
            p.extracted_data = {"name": "Test"}
            p.enrichment_status = "pending"

        # Mock price_finder to fail on second product
        call_count = [0]
        def side_effect(product):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Error on product 2")
            return []

        enricher.price_finder.find_prices = MagicMock(side_effect=side_effect)
        enricher.review_finder.find_reviews = MagicMock(return_value=[])
        enricher.image_finder.find_images = MagicMock(return_value=[])
        enricher.article_finder.find_articles = MagicMock(return_value=[])

        enricher.price_aggregator.aggregate_prices = MagicMock()
        enricher.review_aggregator.aggregate_reviews = MagicMock()
        enricher.image_aggregator.aggregate_images = MagicMock()
        enricher.article_aggregator.aggregate_articles = MagicMock()

        results = enricher.enrich_batch(products)

        # Should still process all 3 products
        assert len(results) == 3
        # First and third should succeed, second should fail
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    def test_enrich_batch_returns_empty_for_empty_list(self, mock_client):
        """Should return empty list for empty input."""
        enricher = ProductEnricher(client=mock_client)

        results = enricher.enrich_batch([])

        assert results == []


class TestGetPendingProducts:
    """Tests for get_pending_products class method."""

    @patch("crawler.discovery.enrichment.orchestrator.DiscoveredProduct")
    def test_get_pending_products_filters_by_status(self, mock_model, mock_client):
        """Should filter products by enrichment_status."""
        mock_queryset = MagicMock()
        mock_model.objects.filter.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.__iter__ = lambda self: iter([])

        ProductEnricher.get_pending_products()

        mock_model.objects.filter.assert_called_with(enrichment_status="pending")

    @patch("crawler.discovery.enrichment.orchestrator.DiscoveredProduct")
    def test_get_pending_products_respects_limit(self, mock_model, mock_client):
        """Should respect the limit parameter."""
        mock_queryset = MagicMock()
        mock_model.objects.filter.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.__getitem__ = MagicMock(return_value=[])

        ProductEnricher.get_pending_products(limit=10)

        mock_queryset.__getitem__.assert_called_with(slice(None, 10))
