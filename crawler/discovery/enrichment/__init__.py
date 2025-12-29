"""
Product Enrichment Module - Phase 4 Product Discovery.

This module enriches skeleton products with detailed information by
searching for product-specific data: prices, reviews, images, and articles.

Components:
- PriceFinder: Find prices via Google Shopping
- ReviewFinder: Find reviews and ratings from review sites
- ImageFinder: Find product images via Google Images
- ArticleFinder: Find article mentions via Google News
- ProductEnricher: Orchestrate all enrichment sources
"""

from .price_finder import PriceFinder, PriceAggregator
from .review_finder import ReviewFinder, ReviewAggregator
from .image_finder import ImageFinder, ImageAggregator
from .article_finder import ArticleFinder, ArticleAggregator
from .orchestrator import ProductEnricher

__all__ = [
    "PriceFinder",
    "PriceAggregator",
    "ReviewFinder",
    "ReviewAggregator",
    "ImageFinder",
    "ImageAggregator",
    "ArticleFinder",
    "ArticleAggregator",
    "ProductEnricher",
]
