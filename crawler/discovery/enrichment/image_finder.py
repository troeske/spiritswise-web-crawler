"""
Image Finder for Product Enrichment.

Phase 4: Product Enrichment - Find images via Google Images API.
"""

import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

from crawler.discovery.serpapi.parsers import ImageResultParser

logger = logging.getLogger(__name__)

# Minimum image dimensions
MIN_WIDTH = 200
MIN_HEIGHT = 200


class ImageFinder:
    """Finds product images via Google Images search."""

    def __init__(self, client):
        """
        Initialize ImageFinder.

        Args:
            client: SerpAPIClient instance
        """
        self.client = client
        self.parser = ImageResultParser()

    def find_images(self, product, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find images for a product.

        Args:
            product: DiscoveredProduct instance
            max_results: Maximum number of results to return

        Returns:
            List of image entries with url, thumbnail, source, type, width, height
        """
        try:
            product_name = product.extracted_data.get("name", "")
            brand = product.extracted_data.get("brand", "")
            product_type = getattr(product, "product_type", "whisky")

            # Build search query
            query = f"{brand} {product_name} bottle".strip() if brand else f"{product_name} bottle"

            # Search Google Images
            response = self.client.google_images(query=query)

            # Parse results
            image_results = response.get("images_results", [])

            images = []
            for result in image_results:
                width = result.get("original_width", 0)
                height = result.get("original_height", 0)

                # Filter small images
                if width < MIN_WIDTH or height < MIN_HEIGHT:
                    continue

                # Extract source domain
                source = self._extract_source(result.get("source", ""))

                image_entry = {
                    "url": result.get("original", ""),
                    "thumbnail": result.get("thumbnail", ""),
                    "source": source,
                    "type": self._determine_image_type(result.get("title", ""), product_type),
                    "width": width,
                    "height": height,
                }
                images.append(image_entry)

                if len(images) >= max_results:
                    break

            return images

        except Exception as e:
            logger.error(f"Error finding images: {e}")
            return []

    def _extract_source(self, source: str) -> str:
        """
        Extract clean source domain.

        Args:
            source: Source string from API

        Returns:
            Clean domain name
        """
        if not source:
            return ""

        # If it's already a domain, return as is
        if "." in source and "/" not in source:
            return source.lower()

        # Try to parse as URL
        try:
            if not source.startswith("http"):
                source = "https://" + source
            parsed = urlparse(source)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return source.lower()

    def _determine_image_type(self, title: str, product_type: str) -> str:
        """
        Determine the type of image based on title.

        Args:
            title: Image title
            product_type: Product type (e.g., 'whisky')

        Returns:
            Image type string (bottle, product, label, etc.)
        """
        title_lower = title.lower()

        if "bottle" in title_lower:
            return "bottle"
        elif "label" in title_lower:
            return "label"
        elif "box" in title_lower or "package" in title_lower:
            return "packaging"
        elif "glass" in title_lower or "pour" in title_lower:
            return "serving"
        else:
            return "product"


class ImageAggregator:
    """Aggregates images to product model."""

    def aggregate_images(self, product, images: List[Dict[str, Any]]) -> None:
        """
        Aggregate image data to product.

        Args:
            product: DiscoveredProduct instance
            images: List of image entries
        """
        for image in images:
            product.add_image(image)

        product.save()
