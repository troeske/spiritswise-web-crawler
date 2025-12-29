"""
Tests for Image Finder.

Phase 4: Product Enrichment - TDD Tests for image_finder.py
"""

import pytest
from unittest.mock import MagicMock

from crawler.discovery.enrichment.image_finder import ImageFinder, ImageAggregator


@pytest.fixture
def mock_client():
    """Create a mock SerpAPIClient."""
    return MagicMock()


@pytest.fixture
def image_finder(mock_client):
    """Create an ImageFinder with mock client."""
    return ImageFinder(client=mock_client)


@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct."""
    product = MagicMock()
    product.extracted_data = {
        "name": "Macallan 18",
        "brand": "Macallan",
    }
    product.product_type = "whisky"
    return product


class TestImageFinderInit:
    """Tests for ImageFinder initialization."""

    def test_init_with_client(self, mock_client):
        """Should initialize with provided client."""
        finder = ImageFinder(client=mock_client)
        assert finder.client == mock_client

    def test_init_creates_parser(self, mock_client):
        """Should create ImageResultParser."""
        finder = ImageFinder(client=mock_client)
        assert finder.parser is not None


class TestFindImages:
    """Tests for find_images method."""

    def test_find_images_returns_list(self, image_finder, mock_client, mock_product):
        """Should return list of image entries."""
        mock_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Macallan 18 Bottle",
                    "original": "https://example.com/macallan.jpg",
                    "thumbnail": "https://example.com/macallan_thumb.jpg",
                    "source": "example.com",
                    "original_width": 800,
                    "original_height": 1200,
                }
            ]
        }

        images = image_finder.find_images(mock_product)

        assert isinstance(images, list)

    def test_find_images_includes_url_source_type(self, image_finder, mock_client, mock_product):
        """Should include url, source, type in results."""
        mock_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Macallan 18 Bottle",
                    "original": "https://example.com/macallan.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "example.com",
                    "original_width": 800,
                    "original_height": 1200,
                }
            ]
        }

        images = image_finder.find_images(mock_product)

        assert len(images) > 0
        first = images[0]
        assert "url" in first
        assert "source" in first
        assert "type" in first
        assert "width" in first
        assert "height" in first

    def test_find_images_filters_small_images(self, image_finder, mock_client, mock_product):
        """Should filter out small images."""
        mock_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Large Image",
                    "original": "https://example.com/large.jpg",
                    "original_width": 800,
                    "original_height": 1200,
                },
                {
                    "title": "Small Image",
                    "original": "https://example.com/small.jpg",
                    "original_width": 100,
                    "original_height": 100,
                },
            ]
        }

        images = image_finder.find_images(mock_product)

        # Should only include large image
        assert len(images) == 1
        assert images[0]["width"] == 800

    def test_find_images_handles_api_error(self, image_finder, mock_client, mock_product):
        """Should return empty list on API error."""
        mock_client.google_images.side_effect = Exception("API Error")

        images = image_finder.find_images(mock_product)

        assert images == []

    def test_find_images_respects_max_results(self, image_finder, mock_client, mock_product):
        """Should respect max_results limit."""
        mock_client.google_images.return_value = {
            "images_results": [
                {
                    "title": f"Image {i}",
                    "original": f"https://example.com/img{i}.jpg",
                    "original_width": 800,
                    "original_height": 1200,
                }
                for i in range(20)
            ]
        }

        images = image_finder.find_images(mock_product, max_results=3)

        assert len(images) <= 3

    def test_find_images_includes_thumbnail(self, image_finder, mock_client, mock_product):
        """Should include thumbnail URL."""
        mock_client.google_images.return_value = {
            "images_results": [
                {
                    "title": "Image",
                    "original": "https://example.com/img.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "original_width": 800,
                    "original_height": 1200,
                }
            ]
        }

        images = image_finder.find_images(mock_product)

        assert images[0]["thumbnail"] == "https://example.com/thumb.jpg"


class TestImageAggregator:
    """Tests for ImageAggregator."""

    def test_aggregates_images(self, mock_product):
        """Should add images to product."""
        aggregator = ImageAggregator()
        images = [
            {
                "url": "https://example.com/img1.jpg",
                "thumbnail": "https://example.com/thumb1.jpg",
                "source": "example.com",
                "type": "bottle",
                "width": 800,
                "height": 1200,
            },
            {
                "url": "https://example.com/img2.jpg",
                "thumbnail": "https://example.com/thumb2.jpg",
                "source": "example.com",
                "type": "product",
                "width": 600,
                "height": 800,
            },
        ]

        aggregator.aggregate_images(mock_product, images)

        assert mock_product.add_image.call_count == 2

    def test_saves_product(self, mock_product):
        """Should save the product after aggregation."""
        aggregator = ImageAggregator()

        aggregator.aggregate_images(mock_product, [])

        mock_product.save.assert_called_once()

    def test_handles_empty_images(self, mock_product):
        """Should handle empty images list."""
        aggregator = ImageAggregator()

        aggregator.aggregate_images(mock_product, [])

        mock_product.add_image.assert_not_called()
        mock_product.save.assert_called_once()
