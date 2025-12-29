"""
Skeleton Product Manager - Creates and manages skeleton products from competition data.

Skeleton products are created with status='skeleton' and minimal extracted_data,
awaiting enrichment from web crawling. They track awards data in a JSONField.
"""

import logging
import hashlib
import json
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.utils import timezone

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
)

logger = logging.getLogger(__name__)


class SkeletonProductManager:
    """
    Manager for creating and handling skeleton products from competition data.

    Skeleton products are created with minimal information (name, award data)
    and are later enriched through targeted web crawling.
    """

    def __init__(self):
        """Initialize the skeleton product manager."""
        pass

    def create_skeleton_product(
        self,
        award_data: Dict[str, Any],
        source=None,
        crawl_job=None,
    ) -> DiscoveredProduct:
        """
        Create a skeleton product from competition award data.

        Args:
            award_data: Dictionary with award information:
                - product_name: Name of the awarded product
                - producer: Producer/brand name (optional)
                - competition: Competition name (e.g., "IWSC")
                - year: Competition year
                - medal: Medal/award type (e.g., "Gold")
                - category: Product category (optional)
            source: CrawlerSource instance (optional)
            crawl_job: CrawlJob instance (optional)

        Returns:
            DiscoveredProduct instance with status='skeleton'
        """
        product_name = award_data.get("product_name", "")
        if not product_name:
            raise ValueError("product_name is required in award_data")

        # Build awards list
        award_entry = {
            "competition": award_data.get("competition", "Unknown"),
            "year": award_data.get("year", timezone.now().year),
            "medal": award_data.get("medal", "Award"),
        }

        # Add optional award fields
        if award_data.get("award_category"):
            award_entry["award_category"] = award_data["award_category"]
        if award_data.get("score"):
            award_entry["score"] = award_data["score"]
        
        # Add award image URL for display in shop
        # award_image_url is at top level of award_data (from parser's to_dict spread)
        if award_data.get("award_image_url"):
            award_entry["image_url"] = award_data["award_image_url"]

        # Build minimal extracted_data
        extracted_data = {
            "name": product_name,
            "discovery_type": "competition",
        }

        # Add optional fields to extracted_data
        if award_data.get("producer"):
            extracted_data["brand"] = award_data["producer"]
        if award_data.get("category"):
            extracted_data["category"] = award_data["category"]
        if award_data.get("country"):
            extracted_data["country"] = award_data["country"]

        # Determine product type (default to whiskey for now)
        product_type = self._determine_product_type(award_data)

        # Generate a preliminary fingerprint for deduplication
        fingerprint = self._compute_skeleton_fingerprint(award_data)

        # Check for existing skeleton with same fingerprint
        existing = DiscoveredProduct.objects.filter(
            fingerprint=fingerprint,
            status=DiscoveredProductStatus.SKELETON,
        ).first()

        if existing:
            # Add award to existing skeleton
            return self._add_award_to_skeleton(existing, award_entry)

        # Create new skeleton product
        with transaction.atomic():
            product = DiscoveredProduct.objects.create(
                source=source,
                crawl_job=crawl_job,
                source_url="",  # No URL yet for skeleton
                fingerprint=fingerprint,
                product_type=product_type,
                raw_content="",  # No content yet
                raw_content_hash=hashlib.sha256(b"").hexdigest(),
                extracted_data=extracted_data,
                enriched_data={},
                status=DiscoveredProductStatus.SKELETON,
                discovery_source=DiscoverySource.COMPETITION,
                awards=[award_entry],
            )

        logger.info(
            f"Created skeleton product: {product_name} "
            f"({award_entry['competition']} {award_entry['year']} {award_entry['medal']})"
        )

        return product

    def create_skeleton_products_batch(
        self,
        award_data_list: List[Dict[str, Any]],
        source=None,
        crawl_job=None,
    ) -> List[DiscoveredProduct]:
        """
        Create multiple skeleton products from competition data.

        Args:
            award_data_list: List of award data dictionaries
            source: CrawlerSource instance (optional)
            crawl_job: CrawlJob instance (optional)

        Returns:
            List of created DiscoveredProduct instances
        """
        products = []
        for award_data in award_data_list:
            try:
                product = self.create_skeleton_product(
                    award_data=award_data,
                    source=source,
                    crawl_job=crawl_job,
                )
                products.append(product)
            except Exception as e:
                logger.error(
                    f"Failed to create skeleton for {award_data.get('product_name')}: {e}"
                )
                continue

        logger.info(f"Created {len(products)} skeleton products from batch of {len(award_data_list)}")
        return products

    def _add_award_to_skeleton(
        self,
        skeleton: DiscoveredProduct,
        award_entry: Dict[str, Any],
    ) -> DiscoveredProduct:
        """Add another award to an existing skeleton product."""
        # Check if this award is already recorded
        existing_awards = skeleton.awards or []
        for existing in existing_awards:
            if (
                existing.get("competition") == award_entry["competition"]
                and existing.get("year") == award_entry["year"]
                and existing.get("medal") == award_entry["medal"]
            ):
                logger.debug(
                    f"Award already exists for skeleton: {skeleton.extracted_data.get('name')}"
                )
                return skeleton

        # Add new award
        skeleton.awards = existing_awards + [award_entry]
        skeleton.save(update_fields=["awards"])

        logger.info(
            f"Added award to existing skeleton: {skeleton.extracted_data.get('name')} "
            f"({award_entry['competition']} {award_entry['year']} {award_entry['medal']})"
        )

        return skeleton

    def _determine_product_type(self, award_data: Dict[str, Any]) -> str:
        """Determine product type from award data."""
        category = (award_data.get("category") or "").lower()
        competition = (award_data.get("competition") or "").lower()

        # Check for whiskey indicators
        whiskey_keywords = [
            "whisky",
            "whiskey",
            "scotch",
            "bourbon",
            "rye",
            "malt",
            "single malt",
            "blended",
            "irish whiskey",
            "japanese whisky",
        ]

        for keyword in whiskey_keywords:
            if keyword in category:
                return ProductType.WHISKEY

        # Check competition name
        if "whisky" in competition or "whiskey" in competition:
            return ProductType.WHISKEY

        # Check for port wine indicators
        port_keywords = ["port", "porto", "douro"]
        for keyword in port_keywords:
            if keyword in category:
                return ProductType.PORT_WINE

        # Default to whiskey (primary focus of current implementation)
        return ProductType.WHISKEY

    def _compute_skeleton_fingerprint(self, award_data: Dict[str, Any]) -> str:
        """
        Compute a fingerprint for skeleton product deduplication.

        Uses product name and producer for basic deduplication.
        """
        key_fields = {
            "name": str(award_data.get("product_name", "")).lower().strip(),
            "brand": str(award_data.get("producer", "")).lower().strip(),
            "type": "skeleton",
        }

        fingerprint_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    def get_skeleton_products(
        self,
        competition: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 100,
    ) -> List[DiscoveredProduct]:
        """
        Get skeleton products, optionally filtered by competition and year.

        Args:
            competition: Competition name to filter by
            year: Year to filter by
            limit: Maximum number of results

        Returns:
            List of skeleton DiscoveredProduct instances
        """
        queryset = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON,
            discovery_source=DiscoverySource.COMPETITION,
        ).order_by("-discovered_at")

        if competition:
            # Filter by awards JSONField
            queryset = queryset.filter(awards__contains=[{"competition": competition}])

        if year:
            queryset = queryset.filter(awards__contains=[{"year": year}])

        return list(queryset[:limit])

    def get_unenriched_skeletons(self, limit: int = 50) -> List[DiscoveredProduct]:
        """
        Get skeleton products that haven't been processed for enrichment yet.

        These are skeletons with no enriched_data.
        """
        return list(
            DiscoveredProduct.objects.filter(
                status=DiscoveredProductStatus.SKELETON,
                enriched_data={},
            )
            .order_by("discovered_at")[:limit]
        )

    def mark_skeleton_enriched(
        self,
        skeleton: DiscoveredProduct,
        enriched_data: Dict[str, Any],
        source_url: str = "",
    ) -> DiscoveredProduct:
        """
        Mark a skeleton as enriched and change status to pending.

        Args:
            skeleton: The skeleton product to update
            enriched_data: Data from web crawling
            source_url: URL where enriched data was found

        Returns:
            Updated DiscoveredProduct
        """
        skeleton.enriched_data = enriched_data
        skeleton.status = DiscoveredProductStatus.PENDING

        if source_url:
            skeleton.source_url = source_url

        # Update extracted_data with enriched information
        updated_extracted = skeleton.extracted_data.copy()
        for key in ["name", "brand", "price", "description", "volume_ml", "abv"]:
            if key in enriched_data and enriched_data[key]:
                updated_extracted[key] = enriched_data[key]

        skeleton.extracted_data = updated_extracted

        # Recompute fingerprint with enriched data
        skeleton.fingerprint = DiscoveredProduct.compute_fingerprint(skeleton.extracted_data)

        skeleton.save()

        logger.info(
            f"Enriched skeleton product: {skeleton.extracted_data.get('name')} "
            f"- status changed to pending"
        )

        return skeleton
