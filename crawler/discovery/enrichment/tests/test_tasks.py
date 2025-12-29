"""
Tests for Enrichment Celery Tasks.

Phase 4: Product Enrichment - TDD Tests for tasks.py
"""

import pytest
from unittest.mock import MagicMock, patch


class TestEnrichProductTask:
    """Tests for enrich_product_task."""

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enriches_product_by_id(self, mock_client_class, mock_enricher_class, mock_model):
        """Should fetch product by ID and enrich it."""
        from crawler.discovery.enrichment.tasks import enrich_product_task

        mock_product = MagicMock()
        mock_model.objects.get.return_value = mock_product

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher
        mock_enricher.enrich_product.return_value = {"success": True}

        result = enrich_product_task(product_id=123)

        mock_model.objects.get.assert_called_with(id=123)
        mock_enricher.enrich_product.assert_called_once_with(mock_product)
        assert result["success"] is True

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_handles_product_not_found(self, mock_client_class, mock_enricher_class, mock_model):
        """Should handle case when product doesn't exist."""
        from django.core.exceptions import ObjectDoesNotExist
        from crawler.discovery.enrichment.tasks import enrich_product_task

        # Use Django's ObjectDoesNotExist as the base for DoesNotExist
        mock_model.DoesNotExist = ObjectDoesNotExist
        mock_model.objects.get.side_effect = ObjectDoesNotExist("Product not found")

        result = enrich_product_task(product_id=999)

        assert result["success"] is False
        assert "error" in result

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    @patch("crawler.discovery.enrichment.tasks.RateLimiter")
    def test_checks_rate_limit(self, mock_limiter_class, mock_client_class, mock_enricher_class, mock_model):
        """Should check rate limit before enriching."""
        from crawler.discovery.enrichment.tasks import enrich_product_task

        mock_limiter = MagicMock()
        mock_limiter_class.return_value = mock_limiter
        mock_limiter.can_make_request.return_value = False

        result = enrich_product_task(product_id=123)

        mock_limiter.can_make_request.assert_called()
        assert result["success"] is False
        assert "rate_limited" in result or "error" in result


class TestEnrichBatchTask:
    """Tests for enrich_batch_task."""

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enriches_multiple_products(self, mock_client_class, mock_enricher_class, mock_model):
        """Should enrich multiple products."""
        from crawler.discovery.enrichment.tasks import enrich_batch_task

        mock_products = [MagicMock() for _ in range(3)]
        mock_model.objects.filter.return_value = mock_products

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher
        mock_enricher.enrich_batch.return_value = [
            {"success": True} for _ in range(3)
        ]

        result = enrich_batch_task(product_ids=[1, 2, 3])

        mock_model.objects.filter.assert_called_with(id__in=[1, 2, 3])
        mock_enricher.enrich_batch.assert_called_once()
        assert result["processed"] == 3

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_returns_success_count(self, mock_client_class, mock_enricher_class, mock_model):
        """Should return count of successfully enriched products."""
        from crawler.discovery.enrichment.tasks import enrich_batch_task

        mock_products = [MagicMock() for _ in range(3)]
        mock_model.objects.filter.return_value = mock_products

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher
        mock_enricher.enrich_batch.return_value = [
            {"success": True},
            {"success": False},
            {"success": True},
        ]

        result = enrich_batch_task(product_ids=[1, 2, 3])

        assert result["successful"] == 2
        assert result["failed"] == 1


class TestEnrichPendingTask:
    """Tests for enrich_pending_task."""

    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enriches_pending_products(self, mock_client_class, mock_enricher_class):
        """Should fetch and enrich pending products."""
        from crawler.discovery.enrichment.tasks import enrich_pending_task

        mock_products = [MagicMock() for _ in range(5)]
        mock_enricher_class.get_pending_products = MagicMock(return_value=mock_products)

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher
        mock_enricher.enrich_batch.return_value = [{"success": True} for _ in range(5)]

        result = enrich_pending_task(limit=10)

        mock_enricher_class.get_pending_products.assert_called_with(limit=10)
        assert result["processed"] == 5

    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_respects_batch_limit(self, mock_client_class, mock_enricher_class):
        """Should respect the batch limit parameter."""
        from crawler.discovery.enrichment.tasks import enrich_pending_task

        mock_enricher_class.get_pending_products = MagicMock(return_value=[])

        enrich_pending_task(limit=25)

        mock_enricher_class.get_pending_products.assert_called_with(limit=25)

    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    @patch("crawler.discovery.enrichment.tasks.RateLimiter")
    def test_stops_when_rate_limited(self, mock_limiter_class, mock_client_class, mock_enricher_class):
        """Should stop processing when rate limited."""
        from crawler.discovery.enrichment.tasks import enrich_pending_task

        mock_limiter = MagicMock()
        mock_limiter_class.return_value = mock_limiter
        mock_limiter.can_make_request.return_value = False

        result = enrich_pending_task(limit=10)

        assert result["processed"] == 0
        assert result.get("rate_limited", False) is True


class TestScheduleEnrichmentTask:
    """Tests for schedule_enrichment_task."""

    @patch("crawler.discovery.enrichment.tasks.enrich_product_task")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    def test_schedules_individual_tasks(self, mock_enricher_class, mock_task):
        """Should schedule individual enrichment tasks."""
        from crawler.discovery.enrichment.tasks import schedule_enrichment_task

        mock_products = [MagicMock(id=i) for i in range(3)]
        mock_enricher_class.get_pending_products = MagicMock(return_value=mock_products)

        result = schedule_enrichment_task(limit=10)

        assert mock_task.delay.call_count == 3
        assert result["scheduled"] == 3

    @patch("crawler.discovery.enrichment.tasks.enrich_product_task")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    def test_returns_scheduled_count(self, mock_enricher_class, mock_task):
        """Should return count of scheduled tasks."""
        from crawler.discovery.enrichment.tasks import schedule_enrichment_task

        mock_products = [MagicMock(id=i) for i in range(5)]
        mock_enricher_class.get_pending_products = MagicMock(return_value=mock_products)

        result = schedule_enrichment_task(limit=5)

        assert result["scheduled"] == 5


class TestEnrichPricesOnlyTask:
    """Tests for enrich_prices_only_task."""

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enriches_only_prices(self, mock_client_class, mock_enricher_class, mock_model):
        """Should only enrich prices for the product."""
        from crawler.discovery.enrichment.tasks import enrich_prices_only_task

        mock_product = MagicMock()
        mock_model.objects.get.return_value = mock_product

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher

        enrich_prices_only_task(product_id=123)

        mock_enricher.enrich_product.assert_called_once_with(
            mock_product,
            enrich_prices=True,
            enrich_reviews=False,
            enrich_images=False,
            enrich_articles=False
        )


class TestEnrichImagesOnlyTask:
    """Tests for enrich_images_only_task."""

    @patch("crawler.discovery.enrichment.tasks.DiscoveredProduct")
    @patch("crawler.discovery.enrichment.tasks.ProductEnricher")
    @patch("crawler.discovery.enrichment.tasks.SerpAPIClient")
    def test_enriches_only_images(self, mock_client_class, mock_enricher_class, mock_model):
        """Should only enrich images for the product."""
        from crawler.discovery.enrichment.tasks import enrich_images_only_task

        mock_product = MagicMock()
        mock_model.objects.get.return_value = mock_product

        mock_enricher = MagicMock()
        mock_enricher_class.return_value = mock_enricher

        enrich_images_only_task(product_id=123)

        mock_enricher.enrich_product.assert_called_once_with(
            mock_product,
            enrich_prices=False,
            enrich_reviews=False,
            enrich_images=True,
            enrich_articles=False
        )
