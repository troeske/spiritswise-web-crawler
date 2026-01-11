"""
Product Details Populator Service.

Populates WhiskeyDetails and PortWineDetails records from DiscoveredProduct data.
This ensures that products have their type-specific detail records created with
appropriate data from extracted_data, enriched_data, or inferred values.

Usage:
    from crawler.services.detail_populator import populate_product_details

    # Populate single product
    populate_product_details(product)

    # Populate all products
    populate_all_product_details()
"""

import logging
from typing import Optional, Dict, Any, Tuple
from django.db import transaction

logger = logging.getLogger(__name__)


def populate_product_details(product) -> Optional[Any]:
    """
    Create type-specific detail record for a DiscoveredProduct.

    For whiskey products, creates WhiskeyDetails.
    For port_wine products, creates PortWineDetails.

    Args:
        product: DiscoveredProduct instance

    Returns:
        Created detail record (WhiskeyDetails or PortWineDetails) or None
    """
    from crawler.models import WhiskeyDetails, PortWineDetails

    if product.product_type == 'whiskey':
        return _create_whiskey_details(product)
    elif product.product_type == 'port_wine':
        return _create_port_wine_details(product)

    return None


def _extract_from_product(product, *keys) -> Optional[Any]:
    """Extract value from product's individual column fields."""
    for key in keys:
        # Check if product has this field as an attribute
        if hasattr(product, key):
            value = getattr(product, key, None)
            if value is not None and value != '':
                return value
    return None


def _infer_whiskey_type(product) -> str:
    """Infer whiskey type from product data."""
    name_lower = (product.name or '').lower()

    # Check extracted_data for type hints
    whiskey_type = _extract_from_product(product, 'whiskey_type', 'type', 'category')
    if whiskey_type:
        whiskey_type_lower = whiskey_type.lower()
        if 'bourbon' in whiskey_type_lower:
            return 'bourbon'
        elif 'rye' in whiskey_type_lower:
            return 'rye'
        elif 'scotch' in whiskey_type_lower or 'single_malt' in whiskey_type_lower:
            return 'single_malt'
        elif 'irish' in whiskey_type_lower:
            return 'irish'
        elif 'japanese' in whiskey_type_lower:
            return 'japanese'

    # Infer from name
    if 'bourbon' in name_lower:
        return 'bourbon'
    elif 'rye' in name_lower and 'whiskey' in name_lower:
        return 'rye'
    elif 'scotch' in name_lower or 'single malt' in name_lower:
        return 'single_malt'
    elif 'irish' in name_lower:
        return 'irish'
    elif 'japanese' in name_lower or any(jp in name_lower for jp in ['suntory', 'nikka', 'yamazaki', 'hibiki']):
        return 'japanese'
    elif 'canadian' in name_lower:
        return 'canadian'
    elif 'tennessee' in name_lower:
        return 'tennessee'
    elif 'blend' in name_lower:
        return 'blended'

    # Check country
    country_lower = (product.country or '').lower()
    if 'scotland' in country_lower or 'scottish' in country_lower:
        return 'single_malt'
    elif 'ireland' in country_lower or 'irish' in country_lower:
        return 'irish'
    elif 'japan' in country_lower:
        return 'japanese'
    elif 'usa' in country_lower or 'america' in country_lower or 'kentucky' in country_lower:
        return 'bourbon'
    elif 'canada' in country_lower:
        return 'canadian'

    return 'other'


def _infer_whiskey_country(product) -> str:
    """Infer country of origin for whiskey."""
    # Direct country field
    if product.country:
        return product.country

    # Check extracted_data
    country = _extract_from_product(product, 'country', 'origin', 'country_of_origin')
    if country:
        return country

    # Infer from whiskey type or name
    name_lower = (product.name or '').lower()

    if any(x in name_lower for x in ['scotch', 'speyside', 'islay', 'highland', 'lowland']):
        return 'Scotland'
    elif any(x in name_lower for x in ['bourbon', 'tennessee', 'kentucky', 'american']):
        return 'United States'
    elif any(x in name_lower for x in ['irish', 'ireland']):
        return 'Ireland'
    elif any(x in name_lower for x in ['japanese', 'nikka', 'suntory', 'yamazaki']):
        return 'Japan'
    elif any(x in name_lower for x in ['canadian', 'canada']):
        return 'Canada'

    return 'Unknown'


def _create_whiskey_details(product) -> Optional['WhiskeyDetails']:
    """Create WhiskeyDetails record for a whiskey product."""
    from crawler.models import WhiskeyDetails

    # Check if already exists
    if hasattr(product, 'whiskey_details') and product.whiskey_details:
        return product.whiskey_details

    try:
        # Get chill_filtered value and invert for non_chill_filtered
        chill_filtered = _extract_from_product(product, 'chill_filtered')
        non_chill_filtered = not chill_filtered if chill_filtered is not None else None

        # Get color_added value and invert for natural_color
        color_added = _extract_from_product(product, 'color_added', 'e150a')
        natural_color = not color_added if color_added is not None else None

        details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=_infer_whiskey_type(product),
            distillery=_extract_from_product(product, 'distillery', 'producer', 'brand'),
            mash_bill=_extract_from_product(product, 'mash_bill', 'mashbill'),
            cask_strength=_extract_from_product(product, 'cask_strength') or False,
            single_cask=_extract_from_product(product, 'single_cask') or False,
            cask_number=_extract_from_product(product, 'cask_number'),
            vintage_year=_extract_from_product(product, 'vintage_year', 'distillation_year'),
            bottling_year=_extract_from_product(product, 'bottling_year'),
            batch_number=_extract_from_product(product, 'batch_number', 'batch'),
            peated=_extract_from_product(product, 'peated', 'is_peated'),
            peat_level=_extract_from_product(product, 'peat_level'),
            peat_ppm=_extract_from_product(product, 'peat_ppm'),
            non_chill_filtered=non_chill_filtered,
            natural_color=natural_color,
        )
        logger.info(f"Created WhiskeyDetails for {product.name}")
        return details
    except Exception as e:
        logger.error(f"Failed to create WhiskeyDetails for {product.name}: {e}")
        return None


def _infer_port_style(product) -> str:
    """Infer port wine style from product data."""
    name_lower = (product.name or '').lower()

    # Check extracted_data
    style = _extract_from_product(product, 'style', 'port_style', 'type')
    if style:
        style_lower = style.lower()
        if 'vintage' in style_lower:
            return 'vintage'
        elif 'tawny' in style_lower:
            return 'tawny'
        elif 'ruby' in style_lower:
            return 'ruby'
        elif 'white' in style_lower:
            return 'white'
        elif 'rose' in style_lower or 'rosé' in style_lower:
            return 'rose'
        elif 'lbv' in style_lower or 'late bottled' in style_lower:
            return 'lbv'
        elif 'colheita' in style_lower:
            return 'colheita'
        elif 'crusted' in style_lower:
            return 'crusted'

    # Infer from name
    if 'vintage' in name_lower:
        return 'vintage'
    elif 'tawny' in name_lower:
        return 'tawny'
    elif 'ruby' in name_lower:
        return 'ruby'
    elif 'white' in name_lower:
        return 'white'
    elif 'rose' in name_lower or 'rosé' in name_lower:
        return 'rose'
    elif 'lbv' in name_lower or 'late bottled' in name_lower:
        return 'lbv'
    elif 'colheita' in name_lower:
        return 'colheita'
    elif 'crusted' in name_lower:
        return 'crusted'
    elif 'reserve' in name_lower:
        return 'reserve'

    # Default to ruby
    return 'ruby'


def _infer_producer_house(product) -> str:
    """Infer port producer house from product data."""
    # Check extracted_data
    producer = _extract_from_product(product, 'producer', 'producer_house', 'house', 'brand')
    if producer:
        return producer

    # Try to extract from name (common port houses)
    name_lower = (product.name or '').lower()
    known_houses = [
        'Taylor', 'Fonseca', 'Graham', 'Cockburn', 'Dow', 'Warre',
        'Croft', 'Sandeman', 'Niepoort', 'Quinta do Noval', 'Ramos Pinto',
        'Burmester', 'Ferreira', 'Kopke', 'Barros', 'Calem', 'Offley'
    ]

    for house in known_houses:
        if house.lower() in name_lower:
            return house

    # Use first word of name as fallback
    if product.name:
        first_word = product.name.split()[0]
        return first_word

    return 'Unknown Producer'


def _create_port_wine_details(product) -> Optional['PortWineDetails']:
    """Create PortWineDetails record for a port wine product."""
    from crawler.models import PortWineDetails

    # Check if already exists
    if hasattr(product, 'port_details') and product.port_details:
        return product.port_details

    try:
        details = PortWineDetails.objects.create(
            product=product,
            style=_infer_port_style(product),
            producer_house=_infer_producer_house(product),
            indication_age=_extract_from_product(product, 'age_indication', 'age', 'indication_age'),
            harvest_year=_extract_from_product(product, 'harvest_year', 'vintage'),
            bottling_year=_extract_from_product(product, 'bottling_year'),
            grape_varieties=_extract_from_product(product, 'grape_varieties', 'grapes') or [],
            quinta=_extract_from_product(product, 'quinta', 'estate'),
            douro_subregion=_extract_from_product(product, 'douro_subregion', 'subregion'),
            aging_vessel=_extract_from_product(product, 'aging_vessel', 'aging', 'maturation'),
        )
        logger.info(f"Created PortWineDetails for {product.name}")
        return details
    except Exception as e:
        logger.error(f"Failed to create PortWineDetails for {product.name}: {e}")
        return None


@transaction.atomic
def populate_all_product_details(force_recreate: bool = False) -> Tuple[int, int]:
    """
    Populate details for all products that don't have them.

    Args:
        force_recreate: If True, delete existing details and recreate

    Returns:
        Tuple of (whiskey_count, port_count) created
    """
    from crawler.models import DiscoveredProduct, WhiskeyDetails, PortWineDetails

    whiskey_created = 0
    port_created = 0

    # Get products needing details
    if force_recreate:
        # Delete existing
        WhiskeyDetails.objects.all().delete()
        PortWineDetails.objects.all().delete()
        whiskey_products = DiscoveredProduct.objects.filter(product_type='whiskey')
        port_products = DiscoveredProduct.objects.filter(product_type='port_wine')
    else:
        # Only products without details
        existing_whiskey_ids = WhiskeyDetails.objects.values_list('product_id', flat=True)
        existing_port_ids = PortWineDetails.objects.values_list('product_id', flat=True)

        whiskey_products = DiscoveredProduct.objects.filter(
            product_type='whiskey'
        ).exclude(id__in=existing_whiskey_ids)

        port_products = DiscoveredProduct.objects.filter(
            product_type='port_wine'
        ).exclude(id__in=existing_port_ids)

    logger.info(f"Populating details for {whiskey_products.count()} whiskeys and {port_products.count()} ports")

    # Create whiskey details
    for product in whiskey_products:
        details = _create_whiskey_details(product)
        if details:
            whiskey_created += 1

    # Create port wine details
    for product in port_products:
        details = _create_port_wine_details(product)
        if details:
            port_created += 1

    logger.info(f"Created {whiskey_created} WhiskeyDetails and {port_created} PortWineDetails")
    return whiskey_created, port_created


def update_completeness_and_details(product) -> None:
    """
    Update product completeness score and ensure details exist.

    Args:
        product: DiscoveredProduct instance
    """
    from crawler.services.completeness import calculate_completeness_score, determine_status

    # Create type-specific details if needed
    populate_product_details(product)

    # Update completeness score
    product.completeness_score = calculate_completeness_score(product)
    product.status = determine_status(product)
    product.save(update_fields=['completeness_score', 'status'])
