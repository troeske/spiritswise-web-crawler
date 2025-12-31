"""
Django signals for the crawler application.

Task Group 21: ProductAvailability - Availability Aggregation Updates
RECT-004: ProductAward - Award count updates
RECT-005: ProductSource junction table signal handlers

This module contains signal handlers that update denormalized counters
on DiscoveredProduct when related records are created/deleted.

Active Signals:
- ProductAvailability save/delete -> DiscoveredProduct aggregates (Task Group 21)
- ProductAward save/delete -> DiscoveredProduct.award_count (RECT-004)
- BrandAward save/delete -> DiscoveredBrand.award_count (RECT-004)
- ProductPrice save/delete -> DiscoveredProduct.price_count (Task Group 4)
- ProductRating save/delete -> DiscoveredProduct.rating_count (Task Group 4)
- ProductSource save/delete -> DiscoveredProduct.mention_count (RECT-005)
- BrandSource save/delete -> DiscoveredBrand.mention_count (RECT-005)

Planned Signals (uncomment when models exist):
- DiscoveredProduct save -> completeness_score recalculation (Task Group 19)
"""

from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Min, Max, Count, Q


# ============================================================
# Task Group 21: ProductAvailability Aggregation Signal Handlers
# ============================================================

# Fields that are updated by availability aggregation (to avoid infinite loop)
AVAILABILITY_AGGREGATE_FIELDS = {
    "retailer_count", "in_stock_count", "avg_price_usd", "min_price_usd", "max_price_usd",
}


def _update_product_availability_aggregates(product_id):
    """
    Task Group 21: Helper function to update DiscoveredProduct availability aggregates.

    Calculates and updates the following fields on DiscoveredProduct:
    - retailer_count: Total number of retailers with availability records
    - in_stock_count: Number of retailers with in_stock=True
    - avg_price_usd: Average price_usd across all availability records
    - min_price_usd: Minimum price_usd
    - max_price_usd: Maximum price_usd

    Args:
        product_id: The UUID of the product to update
    """
    from crawler.models import DiscoveredProduct, ProductAvailability

    # Check if product exists
    try:
        product = DiscoveredProduct.objects.get(pk=product_id)
    except DiscoveredProduct.DoesNotExist:
        return

    # Get all availability records for this product
    availability_queryset = ProductAvailability.objects.filter(product_id=product_id)

    # Calculate aggregates
    retailer_count = availability_queryset.count()
    in_stock_count = availability_queryset.filter(in_stock=True).count()

    # Calculate price aggregates only for records with price_usd set
    price_aggregates = availability_queryset.filter(
        price_usd__isnull=False
    ).aggregate(
        avg_price=Avg("price_usd"),
        min_price=Min("price_usd"),
        max_price=Max("price_usd"),
    )

    # Update the product
    product.retailer_count = retailer_count
    product.in_stock_count = in_stock_count
    product.avg_price_usd = price_aggregates["avg_price"]
    product.min_price_usd = price_aggregates["min_price"]
    product.max_price_usd = price_aggregates["max_price"]

    product.save(update_fields=[
        "retailer_count",
        "in_stock_count",
        "avg_price_usd",
        "min_price_usd",
        "max_price_usd",
    ])


@receiver(post_save, sender="crawler.ProductAvailability")
def update_product_availability_aggregates_on_save(sender, instance, created, **kwargs):
    """
    Task Group 21: Update DiscoveredProduct aggregates when ProductAvailability is saved.

    Updates retailer_count, in_stock_count, and price aggregates on the
    associated DiscoveredProduct when a ProductAvailability record is
    created or updated.

    Args:
        sender: The model class
        instance: The saved ProductAvailability instance
        created: True if this is a new record
        kwargs: Additional signal arguments
    """
    if instance.product_id:
        _update_product_availability_aggregates(instance.product_id)


@receiver(post_delete, sender="crawler.ProductAvailability")
def update_product_availability_aggregates_on_delete(sender, instance, **kwargs):
    """
    Task Group 21: Update DiscoveredProduct aggregates when ProductAvailability is deleted.

    Updates retailer_count, in_stock_count, and price aggregates on the
    associated DiscoveredProduct when a ProductAvailability record is deleted.

    Args:
        sender: The model class
        instance: The deleted ProductAvailability instance
        kwargs: Additional signal arguments
    """
    if instance.product_id:
        _update_product_availability_aggregates(instance.product_id)


# ============================================================
# RECT-004: ProductAward Counter Updates
# Updates DiscoveredProduct.award_count when ProductAward records change.
# ============================================================

@receiver(post_save, sender="crawler.ProductAward")
def update_product_award_count_on_save(sender, instance, created, **kwargs):
    """
    RECT-004: Update DiscoveredProduct.award_count when a ProductAward is created.

    Args:
        sender: The ProductAward model class
        instance: The saved ProductAward instance
        created: True if this is a new record
        kwargs: Additional signal arguments
    """
    if created and instance.product_id:
        from crawler.models import DiscoveredProduct
        DiscoveredProduct.objects.filter(pk=instance.product_id).update(
            award_count=instance.product.awards_rel.count()
        )


@receiver(post_delete, sender="crawler.ProductAward")
def update_product_award_count_on_delete(sender, instance, **kwargs):
    """
    RECT-004: Update DiscoveredProduct.award_count when a ProductAward is deleted.

    Args:
        sender: The ProductAward model class
        instance: The deleted ProductAward instance
        kwargs: Additional signal arguments
    """
    if instance.product_id:
        from crawler.models import DiscoveredProduct
        try:
            product = DiscoveredProduct.objects.get(pk=instance.product_id)
            product.award_count = product.awards_rel.count()
            product.save(update_fields=["award_count"])
        except DiscoveredProduct.DoesNotExist:
            pass


@receiver(post_save, sender="crawler.BrandAward")
def update_brand_award_count_on_save(sender, instance, created, **kwargs):
    """Update DiscoveredBrand.award_count when a BrandAward is created."""
    if created and instance.brand_id:
        from crawler.models import DiscoveredBrand
        DiscoveredBrand.objects.filter(pk=instance.brand_id).update(
            award_count=instance.brand.awards.count()
        )


@receiver(post_delete, sender="crawler.BrandAward")
def update_brand_award_count_on_delete(sender, instance, **kwargs):
    """Update DiscoveredBrand.award_count when a BrandAward is deleted."""
    if instance.brand_id:
        from crawler.models import DiscoveredBrand
        try:
            brand = DiscoveredBrand.objects.get(pk=instance.brand_id)
            brand.award_count = brand.awards.count()
            brand.save(update_fields=["award_count"])
        except DiscoveredBrand.DoesNotExist:
            pass


# ============================================================
# Task Group 4: ProductPrice and ProductRating Counter Updates
# ============================================================

@receiver(post_save, sender="crawler.ProductPrice")
def update_product_price_count_on_save(sender, instance, created, **kwargs):
    """Update DiscoveredProduct.price_count when a ProductPrice is created."""
    if created and instance.product_id:
        from crawler.models import DiscoveredProduct
        DiscoveredProduct.objects.filter(pk=instance.product_id).update(
            price_count=instance.product.prices.count()
        )


@receiver(post_delete, sender="crawler.ProductPrice")
def update_product_price_count_on_delete(sender, instance, **kwargs):
    """Update DiscoveredProduct.price_count when a ProductPrice is deleted."""
    if instance.product_id:
        from crawler.models import DiscoveredProduct
        try:
            product = DiscoveredProduct.objects.get(pk=instance.product_id)
            product.price_count = product.prices.count()
            product.save(update_fields=["price_count"])
        except DiscoveredProduct.DoesNotExist:
            pass


@receiver(post_save, sender="crawler.ProductRating")
def update_product_rating_count_on_save(sender, instance, created, **kwargs):
    """Update DiscoveredProduct.rating_count when a ProductRating is created."""
    if created and instance.product_id:
        from crawler.models import DiscoveredProduct
        DiscoveredProduct.objects.filter(pk=instance.product_id).update(
            rating_count=instance.product.ratings_rel.count()
        )


@receiver(post_delete, sender="crawler.ProductRating")
def update_product_rating_count_on_delete(sender, instance, **kwargs):
    """Update DiscoveredProduct.rating_count when a ProductRating is deleted."""
    if instance.product_id:
        from crawler.models import DiscoveredProduct
        try:
            product = DiscoveredProduct.objects.get(pk=instance.product_id)
            product.rating_count = product.ratings_rel.count()
            product.save(update_fields=["rating_count"])
        except DiscoveredProduct.DoesNotExist:
            pass


# ============================================================
# RECT-005: ProductSource Junction Table Signal Handlers
# Updates DiscoveredProduct.mention_count when ProductSource records change.
# ============================================================

@receiver(post_save, sender="crawler.ProductSource")
def update_product_mention_count_on_save(sender, instance, created, **kwargs):
    """
    RECT-005: Update DiscoveredProduct.mention_count when ProductSource is created.

    When a new ProductSource junction record is created linking a product
    to a crawled source, increment the product's mention_count.

    Args:
        sender: The ProductSource model class
        instance: The saved ProductSource instance
        created: True if this is a new record
        kwargs: Additional signal arguments
    """
    if created and instance.product_id:
        from crawler.models import DiscoveredProduct
        DiscoveredProduct.objects.filter(pk=instance.product_id).update(
            mention_count=instance.product.product_sources.count()
        )


@receiver(post_delete, sender="crawler.ProductSource")
def update_product_mention_count_on_delete(sender, instance, **kwargs):
    """
    RECT-005: Update DiscoveredProduct.mention_count when ProductSource is deleted.

    When a ProductSource junction record is deleted, decrement the
    product's mention_count.

    Args:
        sender: The ProductSource model class
        instance: The deleted ProductSource instance
        kwargs: Additional signal arguments
    """
    if instance.product_id:
        from crawler.models import DiscoveredProduct
        try:
            product = DiscoveredProduct.objects.get(pk=instance.product_id)
            product.mention_count = product.product_sources.count()
            product.save(update_fields=["mention_count"])
        except DiscoveredProduct.DoesNotExist:
            pass


# ============================================================
# RECT-005: BrandSource Junction Table Signal Handlers
# Updates DiscoveredBrand.mention_count when BrandSource records change.
# ============================================================

@receiver(post_save, sender="crawler.BrandSource")
def update_brand_mention_count_on_save(sender, instance, created, **kwargs):
    """
    RECT-005: Update DiscoveredBrand.mention_count when BrandSource is created.

    When a new BrandSource junction record is created linking a brand
    to a crawled source, increment the brand's mention_count.

    Args:
        sender: The BrandSource model class
        instance: The saved BrandSource instance
        created: True if this is a new record
        kwargs: Additional signal arguments
    """
    if created and instance.brand_id:
        from crawler.models import DiscoveredBrand
        DiscoveredBrand.objects.filter(pk=instance.brand_id).update(
            mention_count=instance.brand.sources.count()
        )


@receiver(post_delete, sender="crawler.BrandSource")
def update_brand_mention_count_on_delete(sender, instance, **kwargs):
    """
    RECT-005: Update DiscoveredBrand.mention_count when BrandSource is deleted.

    When a BrandSource junction record is deleted, decrement the
    brand's mention_count.

    Args:
        sender: The BrandSource model class
        instance: The deleted BrandSource instance
        kwargs: Additional signal arguments
    """
    if instance.brand_id:
        from crawler.models import DiscoveredBrand
        try:
            brand = DiscoveredBrand.objects.get(pk=instance.brand_id)
            brand.mention_count = brand.sources.count()
            brand.save(update_fields=["mention_count"])
        except DiscoveredBrand.DoesNotExist:
            pass


# ============================================================
# Task Group 19: Completeness Scoring Signal Handler
# NOTE: This requires the completeness service from Task Group 19.
# Uncomment when that service is implemented.
# ============================================================

# # Fields that should trigger completeness recalculation when changed
# COMPLETENESS_TRIGGER_FIELDS = {
#     "name", "brand_id", "product_type", "abv", "age_statement", "region",
#     "category", "primary_cask", "finishing_cask", "nose_description",
#     "palate_flavors", "finish_length", "primary_aromas", "color_description",
#     "maturation_notes", "food_pairings", "serving_recommendation",
#     "best_price", "award_count", "rating_count",
# }
#
# # Fields that are part of completeness scoring (to avoid infinite loop)
# COMPLETENESS_FIELDS = {
#     "completeness_score", "completeness_tier", "missing_fields", "enrichment_priority",
# }
#
# @receiver(post_save, sender="crawler.DiscoveredProduct")
# def recalculate_completeness_on_save(sender, instance, created, **kwargs):
#     """
#     Task Group 19: Recalculate completeness score when DiscoveredProduct is saved.
#     """
#     update_fields = kwargs.get("update_fields")
#     if update_fields is not None:
#         update_fields_set = set(update_fields) if update_fields else set()
#         if update_fields_set and update_fields_set.issubset(COMPLETENESS_FIELDS):
#             return
#         if update_fields_set and not update_fields_set.intersection(COMPLETENESS_TRIGGER_FIELDS):
#             return
#     try:
#         from crawler.services.completeness import update_product_completeness
#         update_product_completeness(instance, save=True)
#     except ImportError:
#         pass
