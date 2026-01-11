"""
Verification Pipeline for Multi-Source Product Verification.

Unified Pipeline Phase 8: Searches for additional sources, extracts data,
compares and merges data from multiple sources, and tracks verified fields.

Usage:
    pipeline = VerificationPipeline()
    result = pipeline.verify_product(product)
    if result.success:
        print(f"Verified {result.source_count} sources")
        print(f"Verified fields: {result.verified_fields}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of multi-source product verification."""

    product_id: int
    source_count: int
    verified_fields: List[str]
    conflicts: List[Dict[str, Any]]
    merged_data: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class VerificationPipeline:
    """
    Multi-source verification pipeline.

    Searches for additional sources of product information, extracts data
    from those sources, compares and merges the data, and tracks which
    fields are verified by multiple sources.
    """

    # Maximum number of additional sources to search
    MAX_SEARCH_RESULTS = 5

    # Fields to verify
    VERIFIABLE_FIELDS = [
        'name', 'brand', 'abv', 'age', 'volume', 'country', 'region',
        'distillery', 'bottler', 'palate_description', 'nose_description',
        'finish_description', 'palate_flavors', 'price',
    ]

    def __init__(
        self,
        crawler=None,
        search_client=None,
    ):
        """
        Initialize the verification pipeline.

        Args:
            crawler: SmartCrawler instance (created if not provided)
            search_client: Search client for finding additional sources
        """
        if crawler is None:
            from crawler.services.smart_crawler import SmartCrawler
            crawler = SmartCrawler()

        self.crawler = crawler
        self.search_client = search_client

    def _build_data_from_product(self, product) -> Dict[str, Any]:
        """
        Build a data dictionary from individual product model fields.

        This replaces the removed extracted_data JSONField by reading
        data directly from the model's individual columns.

        Args:
            product: DiscoveredProduct instance

        Returns:
            Dictionary of field values for verification
        """
        data = {}

        # Map verifiable fields to model attributes
        field_mappings = {
            'name': 'name',
            'brand': None,  # Special handling - FK relationship
            'abv': 'abv',
            'age': 'age_statement',
            'volume': 'volume_ml',
            'country': 'country',
            'region': 'region',
            'distillery': None,  # May be in brand or separate field
            'bottler': 'bottler',
            'palate_description': 'palate_description',
            'nose_description': 'nose_description',
            'finish_description': 'finish_description',
            'palate_flavors': 'palate_flavors',
            'price': 'best_price',
        }

        for verifiable_field, model_attr in field_mappings.items():
            if model_attr is None:
                # Special handling for brand
                if verifiable_field == 'brand' and product.brand:
                    data['brand'] = product.brand.name
                # Distillery might be stored in brand or elsewhere
                elif verifiable_field == 'distillery' and product.brand:
                    # Check if brand has distillery info
                    if hasattr(product.brand, 'name'):
                        # Brand name might be distillery for single malts
                        pass  # Skip if no dedicated distillery field
            else:
                value = getattr(product, model_attr, None)
                if value is not None:
                    data[verifiable_field] = value

        return data

    def verify_product(self, product) -> VerificationResult:
        """
        Verify a product by searching for additional sources.

        Args:
            product: DiscoveredProduct instance to verify

        Returns:
            VerificationResult with merged data and verification status
        """
        try:
            # Get product's current data
            product_name = product.name or ''
            product_brand = product.brand.name if product.brand else ''

            # Build original source data from individual model fields
            # (extracted_data JSONField was removed per spec)
            original_data = self._build_data_from_product(product)
            all_sources_data = [original_data]

            # Search for additional sources
            additional_urls = self._search_additional_sources(
                product_name,
                product_brand,
            )

            logger.info(
                f"Found {len(additional_urls)} additional sources for "
                f"product {product.id}: {product_name}"
            )

            # Extract from each additional source
            for url in additional_urls:
                try:
                    extracted = self._extract_from_url(url)
                    if extracted:
                        all_sources_data.append(extracted)
                except Exception as e:
                    logger.warning(f"Failed to extract from {url}: {e}")

            # Calculate source count
            source_count = len(all_sources_data)

            # Merge data from all sources
            merged_data, conflicts = self._merge_data(all_sources_data)

            # Get verified fields
            verified_fields = self._get_verified_fields(all_sources_data)

            # Update product
            product.source_count = source_count
            product.verified_fields = verified_fields
            product.save(update_fields=['source_count', 'verified_fields'])

            return VerificationResult(
                product_id=product.id,
                source_count=source_count,
                verified_fields=verified_fields,
                conflicts=conflicts,
                merged_data=merged_data,
                success=True,
            )

        except Exception as e:
            logger.error(f"Verification failed for product {product.id}: {e}")
            return VerificationResult(
                product_id=product.id,
                source_count=1,
                verified_fields=[],
                conflicts=[],
                merged_data={},
                success=False,
                error=str(e),
            )

    def _search_additional_sources(
        self,
        product_name: str,
        brand_name: str,
    ) -> List[str]:
        """
        Search for additional sources of product information.

        Args:
            product_name: Product name to search
            brand_name: Brand name to include in search

        Returns:
            List of URLs for additional sources
        """
        if not self.search_client:
            return []

        try:
            # Build search query
            query = f"{brand_name} {product_name}".strip()

            # Search for sources
            results = self.search_client.search(query)

            # Extract URLs and limit
            urls = []
            for result in results[:self.MAX_SEARCH_RESULTS]:
                if isinstance(result, dict) and 'url' in result:
                    urls.append(result['url'])
                elif isinstance(result, str):
                    urls.append(result)

            return urls[:self.MAX_SEARCH_RESULTS]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _extract_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract product data from a URL.

        Args:
            url: URL to extract from

        Returns:
            Extracted product data or None
        """
        try:
            if hasattr(self.crawler, 'extract_product'):
                return self.crawler.extract_product(url)
            elif hasattr(self.crawler, 'extract'):
                return self.crawler.extract(url)
            return None
        except Exception as e:
            logger.warning(f"Extraction failed for {url}: {e}")
            return None

    def _merge_data(
        self,
        sources_data: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Merge data from multiple sources.

        Uses majority voting for conflicts when possible.

        Args:
            sources_data: List of data dictionaries from each source

        Returns:
            Tuple of (merged_data, conflicts)
        """
        merged = {}
        conflicts = []

        # Collect all values for each field
        field_values: Dict[str, List[Any]] = {}

        for data in sources_data:
            if not isinstance(data, dict):
                continue
            for field_name in self.VERIFIABLE_FIELDS:
                if field_name in data and data[field_name]:
                    if field_name not in field_values:
                        field_values[field_name] = []
                    field_values[field_name].append(data[field_name])

        # Merge each field
        for field_name, values in field_values.items():
            if not values:
                continue

            # Count occurrences of each value
            value_counts = Counter(str(v) for v in values)

            # Get most common value
            most_common_value, most_common_count = value_counts.most_common(1)[0]

            # Find the original (non-stringified) value
            for v in values:
                if str(v) == most_common_value:
                    merged[field_name] = v
                    break

            # Check for conflicts (multiple different values)
            unique_values = list(value_counts.keys())
            if len(unique_values) > 1:
                conflicts.append({
                    'field': field_name,
                    'values': unique_values,
                    'sources': len(values),
                })

        return merged, conflicts

    def _get_verified_fields(
        self,
        sources_data: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Get fields that are verified by multiple sources.

        A field is verified if 2+ sources have matching values for it.

        Args:
            sources_data: List of data dictionaries from each source

        Returns:
            List of verified field names
        """
        verified = []

        # Collect all values for each field
        field_values: Dict[str, List[Any]] = {}

        for data in sources_data:
            if not isinstance(data, dict):
                continue
            for field_name in self.VERIFIABLE_FIELDS:
                if field_name in data and data[field_name]:
                    if field_name not in field_values:
                        field_values[field_name] = []
                    field_values[field_name].append(str(data[field_name]))

        # Check which fields have matching values from 2+ sources
        for field_name, values in field_values.items():
            if len(values) < 2:
                continue

            # Count occurrences
            value_counts = Counter(values)

            # If any value appears 2+ times, field is verified
            for value, count in value_counts.items():
                if count >= 2:
                    verified.append(field_name)
                    break

        return verified
