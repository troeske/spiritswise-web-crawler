"""
Skeleton Product Manager - Creates and manages skeleton products from competition data.

Skeleton products are created with status='skeleton' and minimal extracted_data,
awaiting enrichment from web crawling. They track awards data in a JSONField.

Phase 1 Update: Now uses new model fields (discovery_sources, images, taste_profile, etc.)
for comprehensive product data collection.
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
            # Add award to existing skeleton and merge discovery sources
            return self._add_award_to_skeleton(existing, award_entry, award_data)

        # Create new skeleton product with Phase 1 fields initialized
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
                # Phase 1: Initialize new fields
                discovery_sources=["competition"],  # Track that this was discovered via competition
                taste_profile={},  # Empty until enriched
                images=[],  # Empty until enriched
                ratings=[],  # Empty until enriched
                press_mentions=[],  # Empty until enriched
                mention_count=0,
                price_history=[],  # Empty until enriched
                best_price=None,
                best_price_currency="USD",
                best_price_retailer="",
                best_price_url="",
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
        award_data: Dict[str, Any] = None,
    ) -> DiscoveredProduct:
        """
        Add another award to an existing skeleton product.

        Also ensures 'competition' is in discovery_sources for existing skeletons.
        """
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

        # Phase 1: Ensure 'competition' is in discovery_sources
        # This handles existing skeletons that may not have discovery_sources populated
        if skeleton.discovery_sources is None:
            skeleton.discovery_sources = []
        if "competition" not in skeleton.discovery_sources:
            skeleton.discovery_sources.append("competition")
            skeleton.save(update_fields=["awards", "discovery_sources"])
        else:
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
        discovery_method: str = None,
    ) -> DiscoveredProduct:
        """
        Mark a skeleton as enriched and change status to pending.

        Args:
            skeleton: The skeleton product to update
            enriched_data: Data from web crawling, may include:
                - name, brand, price, description, volume_ml, abv (basic fields)
                - taste_profile: dict with nose, palate, finish, flavor_tags
                - images: list of image dicts
                - ratings: list of rating dicts
            source_url: URL where enriched data was found
            discovery_method: Discovery method to add (e.g., 'serpapi', 'hub_crawl')

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

        # Phase 1: Handle new fields from enriched_data

        # Add discovery method if provided
        if discovery_method:
            if skeleton.discovery_sources is None:
                skeleton.discovery_sources = []
            if discovery_method not in skeleton.discovery_sources:
                skeleton.discovery_sources.append(discovery_method)

        # Merge taste profile if present
        if "taste_profile" in enriched_data and enriched_data["taste_profile"]:
            current_profile = skeleton.taste_profile or {}
            new_profile = enriched_data["taste_profile"]
            for key in ["nose", "palate", "finish", "flavor_tags"]:
                if key in new_profile:
                    existing = set(current_profile.get(key, []))
                    new_values = set(new_profile.get(key, []))
                    current_profile[key] = list(existing | new_values)
            if "overall_notes" in new_profile and not current_profile.get("overall_notes"):
                current_profile["overall_notes"] = new_profile["overall_notes"]
            skeleton.taste_profile = current_profile

        # Add images if present
        if "images" in enriched_data and enriched_data["images"]:
            current_images = skeleton.images or []
            existing_urls = {img.get("url") for img in current_images}
            for img in enriched_data["images"]:
                if img.get("url") and img["url"] not in existing_urls:
                    current_images.append(img)
                    existing_urls.add(img["url"])
            skeleton.images = current_images

        # Add ratings if present
        if "ratings" in enriched_data and enriched_data["ratings"]:
            current_ratings = skeleton.ratings or []
            existing_sources = {r.get("source") for r in current_ratings}
            for rating in enriched_data["ratings"]:
                if rating.get("source") and rating["source"] not in existing_sources:
                    current_ratings.append(rating)
                    existing_sources.add(rating["source"])
            skeleton.ratings = current_ratings

        # Handle price data if present
        if "price" in enriched_data and enriched_data["price"]:
            price_entry = {
                "price": enriched_data["price"],
                "currency": enriched_data.get("currency", "USD"),
                "retailer": enriched_data.get("retailer", "Unknown"),
                "url": source_url,
                "date": timezone.now().isoformat()[:10],
            }
            # Add to price history
            if skeleton.price_history is None:
                skeleton.price_history = []
            skeleton.price_history.append(price_entry)

            # Update best price if applicable
            try:
                new_price = float(enriched_data["price"])
                if skeleton.best_price is None or new_price < float(skeleton.best_price):
                    from decimal import Decimal
                    skeleton.best_price = Decimal(str(new_price))
                    skeleton.best_price_currency = enriched_data.get("currency", "USD")
                    skeleton.best_price_retailer = enriched_data.get("retailer", "Unknown")
                    skeleton.best_price_url = source_url
            except (ValueError, TypeError):
                pass  # Skip if price is not a valid number

        skeleton.save()

        logger.info(
            f"Enriched skeleton product: {skeleton.extracted_data.get('name')} "
            f"- status changed to pending"
        )

        return skeleton

    def merge_discovery_sources(
        self,
        product: DiscoveredProduct,
        new_sources: List[str],
    ) -> DiscoveredProduct:
        """
        Merge new discovery sources into an existing product.

        Phase 1: Helper method for when a product is discovered via multiple methods.

        Args:
            product: The product to update
            new_sources: List of new discovery source strings to add

        Returns:
            Updated DiscoveredProduct
        """
        if product.discovery_sources is None:
            product.discovery_sources = []

        sources_added = False
        for source in new_sources:
            if source not in product.discovery_sources:
                product.discovery_sources.append(source)
                sources_added = True

        if sources_added:
            product.save(update_fields=["discovery_sources"])
            logger.debug(
                f"Merged discovery sources for {product.extracted_data.get('name')}: "
                f"{product.discovery_sources}"
            )

        return product
