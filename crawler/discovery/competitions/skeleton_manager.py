"""
Skeleton Product Manager - Creates and manages skeleton products from competition data.

.. deprecated::
    This module is DEPRECATED as of Phase 11 of the Unified Product Pipeline.

    The skeleton product pattern is being replaced by the unified pipeline which:
    - Uses `crawler.services.product_saver.save_discovered_product()` directly
    - Leverages AI extractors for richer data extraction
    - Uses the verification pipeline for multi-source data merging

    This module is kept for backward compatibility and reference. New code should
    use the product_saver and verification pipeline directly.

    Migration Guide:
    - Instead of SkeletonProductManager.create_skeleton_product(), use
      save_discovered_product() from crawler.services.product_saver
    - Instead of mark_skeleton_enriched(), use the VerificationPipeline
      from crawler.services.verification_pipeline
    - For award data, use the unified save flow with awards parameter

Skeleton products are created with status='skeleton' and minimal product data,
awaiting enrichment from web crawling. Awards are stored as ProductAward records.

Phase 4 Update: Now uses the unified save_discovered_product() function from
crawler.services.product_saver for consistent product creation across all flows.

Fix 2 Update: Now checks for existing products regardless of status to prevent
duplicates when the same award is crawled after a skeleton was enriched.

E2E Bug Fix: _determine_product_type() now returns None for non-MVP types
(only whiskey and port_wine are supported). create_skeleton_product() raises
ValueError when product type cannot be determined or is not supported for MVP.
"""

import logging
import hashlib
import json
import warnings
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    ProductAward,
)
from crawler.services.product_saver import (
    save_discovered_product,
    ProductSaveResult,
    create_product_awards,
)

logger = logging.getLogger(__name__)

# Deprecation message for this module
_DEPRECATION_MESSAGE = (
    "SkeletonProductManager is deprecated. Use crawler.services.product_saver "
    "and crawler.services.verification_pipeline instead. "
    "See module docstring for migration guide."
)

# MVP supported product types
MVP_PRODUCT_TYPES = {ProductType.WHISKEY, ProductType.PORT_WINE}


class SkeletonProductManager:
    """
    Manager for creating and handling skeleton products from competition data.

    .. deprecated::
        Use `crawler.services.product_saver.save_discovered_product()` directly
        and `crawler.services.verification_pipeline.VerificationPipeline` for
        multi-source verification.

    Skeleton products are created with minimal information (name, award data)
    and are later enriched through targeted web crawling.

    Phase 4: Uses unified save_discovered_product() for consistent product creation.
    Awards are stored as ProductAward records (not JSON fields).

    Fix 2: Checks for existing products regardless of status (SKELETON, PENDING,
    APPROVED, REJECTED) to prevent duplicate creation when re-crawling awards.
    """

    def __init__(self):
        """Initialize the skeleton product manager."""
        warnings.warn(
            _DEPRECATION_MESSAGE,
            DeprecationWarning,
            stacklevel=2
        )

    def create_skeleton_product(
        self,
        award_data: Dict[str, Any],
        source=None,
        crawl_job=None,
    ) -> DiscoveredProduct:
        """
        Create a skeleton product from competition award data.

        If a product with the same fingerprint or name already exists (regardless
        of status), adds the award to the existing product instead of creating
        a duplicate.

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
            DiscoveredProduct instance (existing or newly created with status='skeleton')

        Raises:
            ValueError: If product_name is missing or product type is not supported for MVP
        """
        product_name = award_data.get("product_name", "")
        if not product_name:
            raise ValueError("product_name is required in award_data")

        # Determine product type - returns None for non-MVP types
        product_type = self._determine_product_type(award_data)

        # Reject products with unsupported types for MVP
        if product_type is None:
            logger.info(
                f"Skipping non-MVP product: {product_name} "
                f"(category: {award_data.get('category', 'unknown')})"
            )
            raise ValueError(
                f"Product type not supported for MVP: '{product_name}'. "
                "Only whiskey and port_wine products are supported."
            )

        # Generate a preliminary fingerprint for deduplication
        fingerprint = self._compute_skeleton_fingerprint(award_data)

        # Check for ANY existing product with matching fingerprint OR name
        # Fix 2: REMOVED status=DiscoveredProductStatus.SKELETON filter
        # This prevents duplicates when skeleton was enriched to PENDING/APPROVED
        existing = DiscoveredProduct.objects.filter(
            Q(fingerprint=fingerprint) | Q(name__iexact=product_name)
        ).first()

        if existing:
            # Add award to existing product (regardless of status)
            return self._add_award_to_existing(existing, award_data)

        # Build extracted_data for save_discovered_product
        # Normalize competition fields to standard format
        extracted_data = {
            "name": product_name,
            "discovery_type": "competition",
        }

        # Add optional fields
        if award_data.get("producer"):
            extracted_data["brand"] = award_data["producer"]
        if award_data.get("category"):
            extracted_data["category"] = award_data["category"]
        if award_data.get("country"):
            extracted_data["country"] = award_data["country"]

        # Build award entry for save_discovered_product
        award_entry = {
            "competition": award_data.get("competition", "Unknown"),
            "year": award_data.get("year", timezone.now().year),
            "medal": award_data.get("medal", "gold"),
            "competition_country": award_data.get("competition_country", "Unknown"),
        }

        # Add optional award fields
        if award_data.get("award_category"):
            award_entry["category"] = award_data["award_category"]
        elif award_data.get("category"):
            award_entry["category"] = award_data["category"]

        if award_data.get("score"):
            award_entry["score"] = award_data["score"]

        # Add award image URL if present
        if award_data.get("award_image_url"):
            award_entry["image_url"] = award_data["award_image_url"]

        # Add awards to extracted_data
        extracted_data["awards"] = [award_entry]

        # Use save_discovered_product to create the product
        with transaction.atomic():
            result = save_discovered_product(
                extracted_data=extracted_data,
                source_url="",  # No URL yet for skeleton
                product_type=product_type,
                discovery_source="competition",
                check_existing=False,  # We already checked above
                extraction_confidence=0.7,  # Lower confidence for competition-only data
                raw_content="",
            )

            product = result.product

            # Override status to SKELETON (save_discovered_product sets PENDING)
            product.status = DiscoveredProductStatus.SKELETON
            product.discovery_source = DiscoverySource.COMPETITION
            product.fingerprint = fingerprint

            # Set source and crawl_job if provided
            if source:
                product.source = source
            if crawl_job:
                product.crawl_job = crawl_job

            product.save(update_fields=[
                "status", "discovery_source", "fingerprint", "source", "crawl_job"
            ])

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
        skipped_count = 0
        for award_data in award_data_list:
            try:
                product = self.create_skeleton_product(
                    award_data=award_data,
                    source=source,
                    crawl_job=crawl_job,
                )
                products.append(product)
            except ValueError as e:
                # Expected for non-MVP types - log at debug level
                if "not supported for MVP" in str(e):
                    skipped_count += 1
                    logger.debug(
                        f"Skipped non-MVP product: {award_data.get('product_name')}"
                    )
                else:
                    logger.error(
                        f"Failed to create skeleton for {award_data.get('product_name')}: {e}"
                    )
                continue
            except Exception as e:
                logger.error(
                    f"Failed to create skeleton for {award_data.get('product_name')}: {e}"
                )
                continue

        logger.info(
            f"Created {len(products)} skeleton products from batch of {len(award_data_list)} "
            f"(skipped {skipped_count} non-MVP products)"
        )
        return products

    def _add_award_to_existing(
        self,
        product: DiscoveredProduct,
        award_data: Dict[str, Any],
    ) -> DiscoveredProduct:
        """
        Add another award to an existing product.

        Works for products of ANY status (skeleton, pending, approved, rejected).
        This is the Fix 2 enhancement - previously this only worked for skeletons.

        Args:
            product: The existing DiscoveredProduct to add the award to
            award_data: Dictionary with award information

        Returns:
            The updated DiscoveredProduct
        """
        # Build award entry for the ProductAward model
        award_entry = {
            "competition": award_data.get("competition", "Unknown"),
            "year": award_data.get("year", timezone.now().year),
            "medal": award_data.get("medal", "gold"),
            "competition_country": award_data.get("competition_country", "Unknown"),
        }

        # Add optional award fields
        if award_data.get("award_category"):
            award_entry["category"] = award_data["award_category"]
        elif award_data.get("category"):
            award_entry["category"] = award_data["category"]

        if award_data.get("score"):
            award_entry["score"] = award_data["score"]

        # Add award image URL if present
        if award_data.get("award_image_url"):
            award_entry["image_url"] = award_data["award_image_url"]

        # Check if this exact award already exists as a ProductAward
        existing_award = ProductAward.objects.filter(
            product=product,
            competition=award_entry["competition"],
            year=award_entry["year"],
            medal=award_entry["medal"],
        ).exists()

        if existing_award:
            logger.debug(
                f"Award already exists for product: {product.name}"
            )
            return product

        # Use create_product_awards from product_saver
        awards_created = create_product_awards(product, [award_entry])

        # Ensure 'competition' is in discovery_sources
        if product.discovery_sources is None:
            product.discovery_sources = []
        if "competition" not in product.discovery_sources:
            product.discovery_sources.append("competition")
            product.save(update_fields=["discovery_sources"])

        if awards_created > 0:
            logger.info(
                f"Added award to existing product ({product.status}): "
                f"{product.name} "
                f"({award_entry['competition']} {award_entry['year']} {award_entry['medal']})"
            )

        return product

    # Keep old method name as alias for backward compatibility
    def _add_award_to_skeleton(
        self,
        skeleton: DiscoveredProduct,
        award_data: Dict[str, Any],
    ) -> DiscoveredProduct:
        """
        Add another award to an existing skeleton product.

        Deprecated: Use _add_award_to_existing() instead.
        This method is kept for backward compatibility.
        """
        return self._add_award_to_existing(skeleton, award_data)

    def _determine_product_type(self, award_data: Dict[str, Any]) -> Optional[str]:
        """
        Determine product type from award data.

        Checks product_name, category, and competition fields for type keywords.
        For MVP, only returns 'whiskey' or 'port_wine'. Returns None for all
        other product types (wine, brandy, gin, vodka, rum, tequila, unknown).

        Args:
            award_data: Dictionary with product_name, category, competition fields

        Returns:
            ProductType.WHISKEY, ProductType.PORT_WINE, or None if not MVP-supported
        """
        # Get all text fields to check
        product_name = (award_data.get("product_name") or "").lower()
        category = (award_data.get("category") or "").lower()
        competition = (award_data.get("competition") or "").lower()

        # Combine all text for keyword matching
        all_text = f"{product_name} {category} {competition}"

        # Define keywords for each product type (ordered by specificity)
        # More specific types should be checked first

        # Port wine indicators (check before generic wine)
        port_keywords = [
            "tawny port", "ruby port", "vintage port", "late bottled vintage",
            "lbv port", "colheita", "white port", "port wine", "porto",
        ]
        for keyword in port_keywords:
            if keyword in all_text:
                return ProductType.PORT_WINE

        # Also check for just "port" but be more careful (avoid "portobello", "import", etc.)
        if " port" in all_text or all_text.startswith("port") or "port " in product_name:
            # Additional check: must not contain wine-unrelated words
            if "brandy" not in all_text and "cognac" not in all_text:
                return ProductType.PORT_WINE

        # Whiskey indicators
        whiskey_keywords = [
            "whisky", "whiskey", "scotch", "bourbon", "rye whiskey",
            "single malt", "blended malt", "blended scotch", "irish whiskey",
            "tennessee whiskey", "canadian whisky", "japanese whisky",
            "grain whisky", "malt whisky",
        ]
        for keyword in whiskey_keywords:
            if keyword in all_text:
                return ProductType.WHISKEY

        # Check competition name as fallback for whiskey
        if "whisky" in competition or "whiskey" in competition:
            return ProductType.WHISKEY

        # ========================================
        # NON-MVP TYPES - Return None to reject
        # ========================================

        # Brandy/Cognac indicators (NOT supported for MVP)
        brandy_keywords = [
            "brandy", "cognac", "armagnac", "calvados", "pisco",
            "grappa", "eau de vie", "eau-de-vie", "marc",
        ]
        for keyword in brandy_keywords:
            if keyword in all_text:
                logger.debug(
                    f"Skipping brandy/cognac product (not MVP): {product_name}"
                )
                return None

        # Wine indicators (NOT supported for MVP - not port wine)
        wine_keywords = [
            "chardonnay", "merlot", "cabernet", "sauvignon", "syrah",
            "shiraz", "pinot", "riesling", "malbec", "tempranillo",
            "sangiovese", "zinfandel", "grenache", "vineyard", "vintage",
            "wine", "vino", "vin", "winery",
        ]
        for keyword in wine_keywords:
            if keyword in all_text:
                logger.debug(f"Skipping wine product (not MVP): {product_name}")
                return None

        # Gin indicators (NOT supported for MVP)
        gin_keywords = ["gin", "genever", "london dry"]
        for keyword in gin_keywords:
            if keyword in all_text:
                logger.debug(f"Skipping gin product (not MVP): {product_name}")
                return None

        # Vodka indicators (NOT supported for MVP)
        if "vodka" in all_text:
            logger.debug(f"Skipping vodka product (not MVP): {product_name}")
            return None

        # Rum indicators (NOT supported for MVP)
        rum_keywords = ["rum", "rhum", "cachaça", "ron "]
        for keyword in rum_keywords:
            if keyword in all_text:
                logger.debug(f"Skipping rum product (not MVP): {product_name}")
                return None

        # Tequila/Mezcal indicators (NOT supported for MVP)
        tequila_keywords = ["tequila", "mezcal", "sotol", "agave"]
        for keyword in tequila_keywords:
            if keyword in all_text:
                logger.debug(f"Skipping tequila product (not MVP): {product_name}")
                return None

        # If we can't determine type, return None (unknown = not supported for MVP)
        logger.warning(
            f"Could not determine product type for: {product_name} - skipping (not MVP)"
        )
        return None

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
            # Filter by ProductAward records
            queryset = queryset.filter(awards_rel__competition=competition)

        if year:
            queryset = queryset.filter(awards_rel__year=year)

        # Use distinct to avoid duplicates from joins
        return list(queryset.distinct()[:limit])

    def get_unenriched_skeletons(self, limit: int = 50) -> List[DiscoveredProduct]:
        """
        Get skeleton products that haven't been processed for enrichment yet.

        These are skeletons that still have skeleton status and no source_url
        (indicating they haven't been enriched from a web source).
        """
        return list(
            DiscoveredProduct.objects.filter(
                status=DiscoveredProductStatus.SKELETON,
                source_url="",
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

        Uses save_discovered_product with check_existing=True to update
        the skeleton with enriched data using individual columns.

        Args:
            skeleton: The skeleton product to update
            enriched_data: Data from web crawling, may include:
                - name, brand, price, description, volume_ml, abv (basic fields)
                - nose_description, palate_description, finish_description (tasting notes)
                - primary_aromas, palate_flavors, finish_flavors (flavor lists)
                - images: list of image dicts
                - ratings: list of rating dicts
            source_url: URL where enriched data was found
            discovery_method: Discovery method to add (e.g., 'serpapi', 'hub_crawl')

        Returns:
            Updated DiscoveredProduct
        """
        # Prepare enriched_data with discovery info
        data_for_save = enriched_data.copy()

        # Add discovery method to track source
        if discovery_method:
            data_for_save["discovery_method"] = discovery_method

        # Use save_discovered_product with check_existing to update
        # This will merge data and create ratings/images as records
        result = save_discovered_product(
            extracted_data=data_for_save,
            source_url=source_url or skeleton.source_url,
            product_type=skeleton.product_type,
            discovery_source="hub_spoke" if discovery_method else "search",
            check_existing=True,  # Will find existing product and update
            extraction_confidence=0.8,  # Higher confidence for enriched data
            raw_content="",
        )

        updated_product = result.product

        # If save_discovered_product found the existing skeleton, update its status
        if updated_product.id == skeleton.id:
            updated_product.status = DiscoveredProductStatus.PENDING

            if source_url:
                updated_product.source_url = source_url

            updated_product.save(update_fields=["status", "source_url"])
        else:
            # Different product was matched/created - link skeleton to it
            # Mark original skeleton as merged
            skeleton.status = DiscoveredProductStatus.MERGED
            skeleton.save(update_fields=["status"])
            updated_product = result.product

        logger.info(
            f"Enriched skeleton product: {updated_product.name} "
            f"- status changed to {updated_product.status}"
        )

        return updated_product

    def merge_discovery_sources(
        self,
        product: DiscoveredProduct,
        new_sources: List[str],
    ) -> DiscoveredProduct:
        """
        Merge new discovery sources into an existing product.

        Helper method for when a product is discovered via multiple methods.

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
                f"Merged discovery sources for {product.name}: "
                f"{product.discovery_sources}"
            )

        return product
