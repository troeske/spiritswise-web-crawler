"""
Product Enricher Orchestrator.

Phase 4: Product Enrichment - Orchestrates all enrichment sources.
"""

import logging
from typing import List, Dict, Any

from crawler.models import DiscoveredProduct

from .price_finder import PriceFinder, PriceAggregator
from .review_finder import ReviewFinder, ReviewAggregator
from .image_finder import ImageFinder, ImageAggregator
from .article_finder import ArticleFinder, ArticleAggregator

logger = logging.getLogger(__name__)


class ProductEnricher:
    """Orchestrates product enrichment from all sources."""

    def __init__(self, client):
        """
        Initialize ProductEnricher.

        Args:
            client: SerpAPIClient instance
        """
        self.client = client

        # Initialize finders
        self.price_finder = PriceFinder(client=client)
        self.review_finder = ReviewFinder(client=client)
        self.image_finder = ImageFinder(client=client)
        self.article_finder = ArticleFinder(client=client)

        # Initialize aggregators
        self.price_aggregator = PriceAggregator()
        self.review_aggregator = ReviewAggregator()
        self.image_aggregator = ImageAggregator()
        self.article_aggregator = ArticleAggregator()

    def enrich_product(
        self,
        product,
        enrich_prices: bool = True,
        enrich_reviews: bool = True,
        enrich_images: bool = True,
        enrich_articles: bool = True,
    ) -> Dict[str, Any]:
        """
        Enrich a single product with all sources.

        Args:
            product: DiscoveredProduct instance
            enrich_prices: Whether to find prices
            enrich_reviews: Whether to find reviews
            enrich_images: Whether to find images
            enrich_articles: Whether to find articles

        Returns:
            Result dictionary with success status and counts
        """
        result = {
            "success": True,
            "prices_found": 0,
            "reviews_found": 0,
            "images_found": 0,
            "articles_found": 0,
        }

        try:
            # Find prices
            if enrich_prices:
                prices = self.price_finder.find_prices(product)
                result["prices_found"] = len(prices)
                self.price_aggregator.aggregate_prices(product, prices)

            # Find reviews
            if enrich_reviews:
                reviews = self.review_finder.find_reviews(product)
                result["reviews_found"] = len(reviews)
                self.review_aggregator.aggregate_reviews(product, reviews)

            # Find images
            if enrich_images:
                images = self.image_finder.find_images(product)
                result["images_found"] = len(images)
                self.image_aggregator.aggregate_images(product, images)

            # Find articles
            if enrich_articles:
                articles = self.article_finder.find_articles(product)
                result["articles_found"] = len(articles)
                self.article_aggregator.aggregate_articles(product, articles)

            # Update status
            product.enrichment_status = "completed"
            product.save()

            logger.info(
                f"Enriched product {product.id}: "
                f"{result['prices_found']} prices, "
                f"{result['reviews_found']} reviews, "
                f"{result['images_found']} images, "
                f"{result['articles_found']} articles"
            )

        except Exception as e:
            logger.error(f"Error enriching product {product.id}: {e}")
            result["success"] = False
            result["error"] = str(e)

            # Update status to failed
            product.enrichment_status = "failed"
            product.save()

        return result

    def enrich_batch(self, products: List) -> List[Dict[str, Any]]:
        """
        Enrich multiple products.

        Args:
            products: List of DiscoveredProduct instances

        Returns:
            List of result dictionaries
        """
        if not products:
            return []

        results = []
        for product in products:
            result = self.enrich_product(product)
            results.append(result)

        return results

    @classmethod
    def get_pending_products(cls, limit: int = 100) -> List:
        """
        Get products pending enrichment.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of DiscoveredProduct instances
        """
        queryset = DiscoveredProduct.objects.filter(
            enrichment_status="pending"
        ).order_by("-created_at")

        return list(queryset[:limit])
