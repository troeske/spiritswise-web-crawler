"""
Unified Product Saver Module.

UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 1: Implementation

This module provides a SINGLE entry point (save_discovered_product) for creating
or updating DiscoveredProduct records across all discovery flows:
- Competition/Award discovery
- Search discovery
- Hub and Spoke crawling
- Direct crawling

The save_discovered_product() function:
1. Normalizes input data from different source formats
2. Checks for existing product (deduplication by fingerprint/name)
3. Extracts individual fields using FIELD_MAPPING
4. Gets or creates brand
5. Creates DiscoveredProduct with individual columns
6. Creates WhiskeyDetails/PortWineDetails based on product_type
7. Creates ProductAward, ProductRating, ProductImage records
8. Creates ProductSource and ProductFieldSource provenance records
9. Returns ProductSaveResult
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.text import slugify

from crawler.models import (
    CrawledSource,
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    ProductAward,
    ProductSource,
    ProductFieldSource,
    ProductRating,
    ProductImage,
    ImageTypeChoices,
    MedalChoices,
    WhiskeyDetails,
    WhiskeyTypeChoices,
    PeatLevelChoices,
    PortWineDetails,
    PortStyleChoices,
    DouroSubregionChoices,
    DiscoveredBrand,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ProductSaveResult Dataclass
# =============================================================================


@dataclass
class ProductSaveResult:
    """
    Result of save_discovered_product() operation.

    Contains the product and metadata about what was created/updated.
    """
    product: DiscoveredProduct
    created: bool = False
    whiskey_details_created: bool = False
    port_wine_details_created: bool = False
    awards_created: int = 0
    ratings_created: int = 0
    images_created: int = 0
    source_record_created: bool = False
    provenance_records_created: int = 0
    brand_created: bool = False
    brand: Optional[DiscoveredBrand] = None


# =============================================================================
# Type Converters (from content_processor.py)
# =============================================================================


def _safe_str(value: Any) -> Optional[str]:
    """Convert value to string, returning None for empty/null values."""
    if value is None:
        return None
    str_val = str(value).strip()
    return str_val if str_val else None


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to float, returning None for invalid/empty values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert value to int, returning None for invalid/empty values."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            # Handle decimal strings like "18.0"
            return int(float(value))
        except (ValueError, TypeError):
            return None
    return None


def _safe_list(value: Any) -> List:
    """Convert value to list, returning empty list for invalid values."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Attempt to parse comma-separated string
        value = value.strip()
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _safe_bool(value: Any) -> Optional[bool]:
    """
    Convert value to boolean, returning None for empty/null/invalid values.

    Handles:
    - True/False booleans
    - 'true'/'false', 'yes'/'no', '1'/'0' strings (case insensitive)
    - Integer 1/0
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        value = value.strip().lower()
        if not value:
            return None
        if value in ("true", "yes", "1"):
            return True
        if value in ("false", "no", "0"):
            return False
        return None
    return None


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """Convert value to Decimal, returning None for invalid/empty values."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


def _safe_date(value: Any):
    """Convert value to date, returning None for invalid/empty values."""
    from datetime import date, datetime
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            # Try ISO format (YYYY-MM-DD)
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            try:
                # Try other common formats
                return datetime.strptime(value, "%d/%m/%Y").date()
            except ValueError:
                return None
    return None


# =============================================================================
# Field Mappings (from content_processor.py)
# =============================================================================

# Core product fields: AI response key -> (model field name, type converter)
FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Core identification
    "name": ("name", _safe_str),
    "abv": ("abv", _safe_float),
    "age_statement": ("age_statement", _safe_int),
    "region": ("region", _safe_str),
    "country": ("country", _safe_str),
    "volume_ml": ("volume_ml", _safe_int),
    "gtin": ("gtin", _safe_str),

    # Tasting Profile: Appearance/Visual
    "color_description": ("color_description", _safe_str),
    "color_intensity": ("color_intensity", _safe_int),
    "clarity": ("clarity", _safe_str),
    "viscosity": ("viscosity", _safe_str),

    # Tasting Profile: Nose/Aroma
    "nose_description": ("nose_description", _safe_str),
    "primary_aromas": ("primary_aromas", _safe_list),
    "primary_intensity": ("primary_intensity", _safe_int),
    "secondary_aromas": ("secondary_aromas", _safe_list),
    "aroma_evolution": ("aroma_evolution", _safe_str),

    # Tasting Profile: Palate
    "palate_flavors": ("palate_flavors", _safe_list),
    "initial_taste": ("initial_taste", _safe_str),
    "mid_palate_evolution": ("mid_palate_evolution", _safe_str),
    "flavor_intensity": ("flavor_intensity", _safe_int),
    "complexity": ("complexity", _safe_int),
    "mouthfeel": ("mouthfeel", _safe_str),

    # Tasting Profile: Finish
    "finish_length": ("finish_length", _safe_int),
    "warmth": ("warmth", _safe_int),
    "dryness": ("dryness", _safe_int),
    "finish_flavors": ("finish_flavors", _safe_list),
    "finish_evolution": ("finish_evolution", _safe_str),
    "final_notes": ("final_notes", _safe_str),
}

# Whiskey-specific fields: AI response key -> (model field name, type converter)
WHISKEY_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Classification
    "whiskey_type": ("whiskey_type", _safe_str),
    "whiskey_country": ("whiskey_country", _safe_str),
    "whiskey_region": ("whiskey_region", _safe_str),

    # Production
    "distillery": ("distillery", _safe_str),
    "mash_bill": ("mash_bill", _safe_str),

    # Cask Information
    "cask_type": ("cask_type", _safe_str),
    "cask_finish": ("cask_finish", _safe_str),
    "cask_strength": ("cask_strength", _safe_bool),
    "single_cask": ("single_cask", _safe_bool),
    "cask_number": ("cask_number", _safe_str),

    # Vintage/Batch Info
    "vintage_year": ("vintage_year", _safe_int),
    "bottling_year": ("bottling_year", _safe_int),
    "batch_number": ("batch_number", _safe_str),

    # Peat
    "peated": ("peated", _safe_bool),
    "peat_level": ("peat_level", _safe_str),
}

# Valid whiskey type values for validation
VALID_WHISKEY_TYPES = [choice.value for choice in WhiskeyTypeChoices]

# Valid peat level values for validation
VALID_PEAT_LEVELS = [choice.value for choice in PeatLevelChoices]

# Port wine-specific fields: AI response key -> (model field name, type converter)
PORT_WINE_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Style
    "style": ("style", _safe_str),
    "indication_age": ("indication_age", _safe_str),

    # Vintage Information
    "harvest_year": ("harvest_year", _safe_int),
    "bottling_year": ("bottling_year", _safe_int),

    # Production
    "grape_varieties": ("grape_varieties", _safe_list),
    "quinta": ("quinta", _safe_str),
    "douro_subregion": ("douro_subregion", _safe_str),
    "producer_house": ("producer_house", _safe_str),

    # Aging
    "aging_vessel": ("aging_vessel", _safe_str),

    # Serving
    "decanting_required": ("decanting_required", _safe_bool),
    "drinking_window": ("drinking_window", _safe_str),
}

# Valid port style values for validation
VALID_PORT_STYLES = [choice.value for choice in PortStyleChoices]

# Valid Douro subregion values for validation
VALID_DOURO_SUBREGIONS = [choice.value for choice in DouroSubregionChoices]

# Award field mapping: AI response key -> (model field name, type converter)
AWARD_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    "competition": ("competition", _safe_str),
    "competition_country": ("competition_country", _safe_str),
    "year": ("year", _safe_int),
    "medal": ("medal", _safe_str),
    "score": ("score", _safe_int),
    "category": ("award_category", _safe_str),
    "url": ("award_url", _safe_str),
    "image_url": ("image_url", _safe_str),
}

# Valid medal choices from MedalChoices enum
VALID_MEDAL_CHOICES = {choice.value for choice in MedalChoices}

# Rating field mapping
RATING_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    "source": ("source", _safe_str),
    "source_country": ("source_country", _safe_str),
    "score": ("score", _safe_decimal),
    "max_score": ("max_score", _safe_int),
    "reviewer": ("reviewer", _safe_str),
    "review_url": ("review_url", _safe_str),
    "date": ("date", _safe_date),
    "review_count": ("review_count", _safe_int),
}

# Image field mapping
IMAGE_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    "url": ("url", _safe_str),
    "image_type": ("image_type", _safe_str),
    "type": ("image_type", _safe_str),  # alternate key
    "source": ("source", _safe_str),
    "width": ("width", _safe_int),
    "height": ("height", _safe_int),
    "is_primary": ("is_primary", _safe_bool),
}

# Valid image type values for validation
VALID_IMAGE_TYPES = [choice.value for choice in ImageTypeChoices]


# =============================================================================
# Data Normalization Functions
# =============================================================================


def normalize_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize extracted data from different source formats.

    Competition data uses product_name/producer, while discovery data
    uses name/brand. This function normalizes to the canonical format.

    Args:
        data: Raw extracted data dict

    Returns:
        Normalized data dict with standard field names
    """
    normalized = data.copy()

    # Normalize product_name -> name
    if "product_name" in normalized:
        # Only use product_name if name is not already present
        if "name" not in normalized or not normalized.get("name"):
            normalized["name"] = normalized["product_name"]
        # Remove the original key to avoid confusion
        del normalized["product_name"]

    # Normalize producer -> brand
    if "producer" in normalized:
        # Only use producer if brand is not already present
        if "brand" not in normalized or not normalized.get("brand"):
            normalized["brand"] = normalized["producer"]
        # Remove the original key to avoid confusion
        del normalized["producer"]

    return normalized


def extract_core_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract core product fields from extracted data.

    Applies type conversion and handles null/empty values.

    Args:
        data: Extracted data dict

    Returns:
        Dict of field names to converted values (only non-None values)
    """
    fields = {}

    core_fields = {
        "name": _safe_str,
        "abv": _safe_float,
        "age_statement": _safe_int,
        "volume_ml": _safe_int,
        "region": _safe_str,
        "country": _safe_str,
        "gtin": _safe_str,
    }

    for field_name, converter in core_fields.items():
        value = data.get(field_name)
        converted = converter(value)
        if converted is not None:
            fields[field_name] = converted

    return fields


def extract_tasting_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract tasting profile fields from extracted data.

    Applies type conversion for all tasting profile fields.

    Args:
        data: Extracted data dict

    Returns:
        Dict of tasting field names to converted values
    """
    fields = {}

    tasting_fields = {
        # Appearance
        "color_description": _safe_str,
        "color_intensity": _safe_int,
        "clarity": _safe_str,
        "viscosity": _safe_str,
        # Nose
        "nose_description": _safe_str,
        "primary_aromas": _safe_list,
        "primary_intensity": _safe_int,
        "secondary_aromas": _safe_list,
        "aroma_evolution": _safe_str,
        # Palate
        "palate_flavors": _safe_list,
        "initial_taste": _safe_str,
        "mid_palate_evolution": _safe_str,
        "flavor_intensity": _safe_int,
        "complexity": _safe_int,
        "mouthfeel": _safe_str,
        # Finish
        "finish_length": _safe_int,
        "warmth": _safe_int,
        "dryness": _safe_int,
        "finish_flavors": _safe_list,
        "finish_evolution": _safe_str,
        "final_notes": _safe_str,
    }

    for field_name, converter in tasting_fields.items():
        value = data.get(field_name)
        converted = converter(value)
        if converted is not None:
            fields[field_name] = converted

    return fields


def extract_individual_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract all individual field values from AI response data.

    Applies type conversions and handles null/empty values gracefully.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Dict of model field names to converted values
    """
    fields = {}

    for ai_key, (model_field, converter) in FIELD_MAPPING.items():
        value = extracted_data.get(ai_key)
        converted_value = converter(value)

        # Only include non-None values (except for lists which default to [])
        if converted_value is not None:
            fields[model_field] = converted_value
        elif converter == _safe_list:
            # Lists default to empty list, not None
            fields[model_field] = []

    return fields


# =============================================================================
# Brand Functions
# =============================================================================


def get_or_create_brand(
    extracted_data: Dict[str, Any],
    crawled_source: Optional[CrawledSource] = None,
    confidence: float = 0.8,
) -> Tuple[Optional[DiscoveredBrand], bool]:
    """
    Get or create a DiscoveredBrand from extracted data.

    Looks for brand name in these fields (in order):
    1. brand
    2. distillery
    3. producer
    4. producer_house

    Args:
        extracted_data: Dict from AI Enhancement Service
        crawled_source: Optional CrawledSource to create BrandSource junction
        confidence: Confidence score for brand extraction (0.0-1.0)

    Returns:
        Tuple of (DiscoveredBrand or None, was_created bool)
    """
    # Try to get brand name from multiple fields
    brand_name = None
    brand_country = None
    brand_region = None

    # Check "brand" field first
    brand_name = _safe_str(extracted_data.get("brand"))
    brand_country = _safe_str(extracted_data.get("brand_country"))
    brand_region = _safe_str(extracted_data.get("brand_region"))

    # Fallback to distillery
    if not brand_name:
        distillery = _safe_str(extracted_data.get("distillery"))
        if distillery:
            # Clean up distillery name (remove " Distillery" suffix if present)
            brand_name = distillery.replace(" Distillery", "").strip()
            brand_country = _safe_str(extracted_data.get("distillery_country"))
            brand_region = _safe_str(extracted_data.get("distillery_region"))

    # Fallback to producer
    if not brand_name:
        brand_name = _safe_str(extracted_data.get("producer"))
        brand_country = _safe_str(extracted_data.get("producer_country"))
        brand_region = _safe_str(extracted_data.get("producer_region"))

    # Fallback to producer_house
    if not brand_name:
        brand_name = _safe_str(extracted_data.get("producer_house"))

    # If no brand name found, return None
    if not brand_name:
        return None, False

    # Generate slug
    brand_slug = slugify(brand_name)

    # Try to find existing brand (case insensitive)
    try:
        existing = DiscoveredBrand.objects.filter(
            name__iexact=brand_name
        ).first()

        if existing:
            return existing, False

        # Also try to match by slug
        existing_by_slug = DiscoveredBrand.objects.filter(
            slug=brand_slug
        ).first()

        if existing_by_slug:
            return existing_by_slug, False

    except Exception as e:
        logger.warning(f"Error looking up brand {brand_name}: {e}")

    # Create new brand
    try:
        # Handle slug uniqueness
        base_slug = brand_slug
        counter = 1
        while DiscoveredBrand.objects.filter(slug=brand_slug).exists():
            brand_slug = f"{base_slug}-{counter}"
            counter += 1

        brand = DiscoveredBrand.objects.create(
            name=brand_name,
            slug=brand_slug,
            country=brand_country,
            region=brand_region,
        )

        logger.info(f"Created new brand: {brand_name} ({brand.id})")
        return brand, True

    except IntegrityError as e:
        # Race condition - brand was created between check and create
        logger.warning(f"IntegrityError creating brand {brand_name}, trying to fetch: {e}")
        existing = DiscoveredBrand.objects.filter(name__iexact=brand_name).first()
        if existing:
            return existing, False
        return None, False
    except Exception as e:
        logger.error(f"Failed to create brand {brand_name}: {e}")
        return None, False


# =============================================================================
# WhiskeyDetails Functions
# =============================================================================


def extract_whiskey_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract whiskey-specific field values from AI response data.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Dict of WhiskeyDetails field names to converted values
    """
    fields = {}

    for ai_key, (model_field, converter) in WHISKEY_FIELD_MAPPING.items():
        value = extracted_data.get(ai_key)
        converted_value = converter(value)

        # Only include non-None values
        if converted_value is not None:
            # Validate choice fields
            if model_field == "whiskey_type" and converted_value not in VALID_WHISKEY_TYPES:
                logger.warning(f"Invalid whiskey_type '{converted_value}', skipping")
                continue
            if model_field == "peat_level" and converted_value not in VALID_PEAT_LEVELS:
                logger.warning(f"Invalid peat_level '{converted_value}', skipping")
                continue

            fields[model_field] = converted_value

    return fields


def _infer_whiskey_type(extracted_data: Dict[str, Any]) -> Optional[str]:
    """
    Attempt to infer whiskey_type from other extracted data.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Inferred whiskey type value or None
    """
    country = _safe_str(extracted_data.get("country") or extracted_data.get("whiskey_country"))
    region = _safe_str(extracted_data.get("region") or extracted_data.get("whiskey_region"))
    name = _safe_str(extracted_data.get("name")) or ""

    if not country:
        return None

    country_lower = country.lower()
    name_lower = name.lower()

    # Scotland
    if country_lower in ("scotland", "uk", "united kingdom"):
        if "blend" in name_lower or "blended" in name_lower:
            return WhiskeyTypeChoices.SCOTCH_BLEND
        return WhiskeyTypeChoices.SCOTCH_SINGLE_MALT

    # USA
    if country_lower in ("usa", "united states", "america"):
        if "bourbon" in name_lower:
            return WhiskeyTypeChoices.BOURBON
        if "tennessee" in name_lower:
            return WhiskeyTypeChoices.TENNESSEE
        if "rye" in name_lower:
            return WhiskeyTypeChoices.RYE
        if "single malt" in name_lower:
            return WhiskeyTypeChoices.AMERICAN_SINGLE_MALT
        # Default to bourbon for US whiskey
        return WhiskeyTypeChoices.BOURBON

    # Ireland
    if country_lower in ("ireland", "irish"):
        if "single pot" in name_lower or "pot still" in name_lower:
            return WhiskeyTypeChoices.IRISH_SINGLE_POT
        if "single malt" in name_lower:
            return WhiskeyTypeChoices.IRISH_SINGLE_MALT
        if "blend" in name_lower:
            return WhiskeyTypeChoices.IRISH_BLEND
        return WhiskeyTypeChoices.IRISH_BLEND

    # Japan
    if country_lower in ("japan", "japanese"):
        return WhiskeyTypeChoices.JAPANESE

    # Canada
    if country_lower in ("canada", "canadian"):
        return WhiskeyTypeChoices.CANADIAN

    # India
    if country_lower == "india":
        return WhiskeyTypeChoices.INDIAN

    # Taiwan
    if country_lower == "taiwan":
        return WhiskeyTypeChoices.TAIWANESE

    # Australia
    if country_lower == "australia":
        return WhiskeyTypeChoices.AUSTRALIAN

    # Default
    return WhiskeyTypeChoices.WORLD_WHISKEY


def _create_whiskey_details(
    product: DiscoveredProduct,
    extracted_data: Dict[str, Any],
) -> Optional[WhiskeyDetails]:
    """
    Create WhiskeyDetails record for a whiskey product.

    Args:
        product: The DiscoveredProduct to link to
        extracted_data: Dict from AI Enhancement Service

    Returns:
        WhiskeyDetails instance if created, None otherwise
    """
    # Extract whiskey-specific fields
    whiskey_fields = extract_whiskey_fields(extracted_data)

    # Require at least whiskey_type and whiskey_country
    whiskey_type = whiskey_fields.get("whiskey_type")
    whiskey_country = whiskey_fields.get("whiskey_country")

    if not whiskey_type:
        # Try to infer whiskey_type from country/region
        whiskey_type = _infer_whiskey_type(extracted_data)
        if whiskey_type:
            whiskey_fields["whiskey_type"] = whiskey_type

    if not whiskey_country:
        # Try to use the product's country field
        whiskey_country = extracted_data.get("country")
        if whiskey_country:
            whiskey_fields["whiskey_country"] = whiskey_country

    # Still no whiskey_type or country? Use defaults
    if not whiskey_fields.get("whiskey_type"):
        whiskey_fields["whiskey_type"] = WhiskeyTypeChoices.WORLD_WHISKEY
    if not whiskey_fields.get("whiskey_country"):
        whiskey_fields["whiskey_country"] = "Unknown"

    # Also populate whiskey_region from main region if not set
    if not whiskey_fields.get("whiskey_region") and extracted_data.get("region"):
        whiskey_fields["whiskey_region"] = extracted_data.get("region")

    try:
        details = WhiskeyDetails.objects.create(
            product=product,
            **whiskey_fields
        )
        logger.info(f"Created WhiskeyDetails for product {product.id}: {whiskey_fields.get('whiskey_type')}")
        return details
    except Exception as e:
        logger.error(f"Failed to create WhiskeyDetails for product {product.id}: {e}")
        return None


# =============================================================================
# PortWineDetails Functions
# =============================================================================


def extract_port_wine_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract port wine-specific field values from AI response data.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Dict of PortWineDetails field names to converted values
    """
    fields = {}

    for ai_key, (model_field, converter) in PORT_WINE_FIELD_MAPPING.items():
        value = extracted_data.get(ai_key)
        converted_value = converter(value)

        # Only include non-None values
        if converted_value is not None:
            # Validate choice fields
            if model_field == "style" and converted_value not in VALID_PORT_STYLES:
                logger.warning(f"Invalid port style '{converted_value}', skipping")
                continue
            if model_field == "douro_subregion" and converted_value not in VALID_DOURO_SUBREGIONS:
                logger.warning(f"Invalid douro_subregion '{converted_value}', skipping")
                continue

            fields[model_field] = converted_value

    return fields


def _infer_port_style(extracted_data: Dict[str, Any]) -> Optional[str]:
    """
    Attempt to infer port style from product name.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Inferred port style value or None
    """
    name = _safe_str(extracted_data.get("name")) or ""
    name_lower = name.lower()

    # Check for specific styles in name
    if "lbv" in name_lower or "late bottled vintage" in name_lower:
        return PortStyleChoices.LBV

    if "colheita" in name_lower:
        return PortStyleChoices.COLHEITA

    if "vintage" in name_lower:
        return PortStyleChoices.VINTAGE

    if "tawny" in name_lower:
        return PortStyleChoices.TAWNY

    if "ruby" in name_lower:
        return PortStyleChoices.RUBY

    if "white" in name_lower or "branco" in name_lower:
        return PortStyleChoices.WHITE

    if "rose" in name_lower or "rosé" in name_lower or "pink" in name_lower:
        return PortStyleChoices.ROSE

    if "crusted" in name_lower:
        return PortStyleChoices.CRUSTED

    if "single quinta" in name_lower or "quinta" in name_lower:
        return PortStyleChoices.SINGLE_QUINTA

    if "garrafeira" in name_lower:
        return PortStyleChoices.GARRAFEIRA

    return None


def _create_port_wine_details(
    product: DiscoveredProduct,
    extracted_data: Dict[str, Any],
) -> Optional[PortWineDetails]:
    """
    Create PortWineDetails record for a port wine product.

    Args:
        product: The DiscoveredProduct to link to
        extracted_data: Dict from AI Enhancement Service

    Returns:
        PortWineDetails instance if created, None otherwise
    """
    # Extract port wine-specific fields
    port_fields = extract_port_wine_fields(extracted_data)

    # Get or infer style
    style = port_fields.get("style")
    if not style:
        # Try to infer style from product name
        style = _infer_port_style(extracted_data)
        if style:
            port_fields["style"] = style

    # If still no style, use default
    if not port_fields.get("style"):
        port_fields["style"] = PortStyleChoices.RUBY

    # Get producer_house - try multiple fields
    producer_house = port_fields.get("producer_house")
    if not producer_house:
        # Try brand field
        producer_house = _safe_str(extracted_data.get("brand"))
        if producer_house:
            port_fields["producer_house"] = producer_house

    # If still no producer_house, use default
    if not port_fields.get("producer_house"):
        port_fields["producer_house"] = "Unknown"

    # Handle grape_varieties - ensure it's a list or use empty list
    if "grape_varieties" not in port_fields:
        port_fields["grape_varieties"] = []

    try:
        details = PortWineDetails.objects.create(
            product=product,
            **port_fields
        )
        logger.info(f"Created PortWineDetails for product {product.id}: {port_fields.get('style')}")
        return details
    except Exception as e:
        logger.error(f"Failed to create PortWineDetails for product {product.id}: {e}")
        return None


# =============================================================================
# Award, Rating, Image Creation Functions
# =============================================================================


def create_product_awards(
    product: DiscoveredProduct,
    awards_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    Create ProductAward records from awards data.

    Args:
        product: The DiscoveredProduct to create awards for
        awards_data: List of award dictionaries

    Returns:
        Number of awards created
    """
    if not awards_data:
        return 0

    awards_created = 0

    for award_data in awards_data:
        # Extract and convert award fields
        award_fields = {}
        for ai_key, (model_field, converter) in AWARD_FIELD_MAPPING.items():
            value = award_data.get(ai_key)
            converted = converter(value)
            if converted is not None:
                award_fields[model_field] = converted

        # competition_country may come as "country" in some formats
        if not award_fields.get("competition_country"):
            award_fields["competition_country"] = _safe_str(award_data.get("country")) or "Unknown"

        # award_category may come as "category" directly
        if not award_fields.get("award_category"):
            award_fields["award_category"] = _safe_str(award_data.get("category")) or "General"

        # Validate required fields (relaxed validation for minimal competition data)
        if not award_fields.get("competition"):
            logger.warning(f"Award for product {product.id} missing competition name")
            continue
        if not award_fields.get("year"):
            logger.warning(f"Award for product {product.id} missing year")
            continue

        # Normalize and validate medal
        medal = award_fields.get("medal")
        if medal:
            medal_lower = medal.lower()
            # Map common medal names to valid choices
            medal_map = {
                "gold": MedalChoices.GOLD,
                "silver": MedalChoices.SILVER,
                "bronze": MedalChoices.BRONZE,
                "double gold": MedalChoices.DOUBLE_GOLD,
                "double_gold": MedalChoices.DOUBLE_GOLD,
                "best in class": MedalChoices.BEST_IN_CLASS,
                "best_in_class": MedalChoices.BEST_IN_CLASS,
                "category winner": MedalChoices.CATEGORY_WINNER,
                "category_winner": MedalChoices.CATEGORY_WINNER,
            }
            award_fields["medal"] = medal_map.get(medal_lower, medal)

        if not award_fields.get("medal") or award_fields["medal"] not in VALID_MEDAL_CHOICES:
            logger.warning(
                f"Award for product {product.id} has invalid medal type: {award_fields.get('medal')}. "
                f"Valid choices are: {VALID_MEDAL_CHOICES}"
            )
            continue

        # Check for duplicate awards
        existing_award = ProductAward.objects.filter(
            product=product,
            competition=award_fields["competition"],
            year=award_fields["year"],
            medal=award_fields["medal"],
        ).exists()

        if existing_award:
            logger.debug(f"Award already exists for product {product.id}")
            continue

        # Create the award record
        try:
            ProductAward.objects.create(
                product=product,
                **award_fields,
            )
            awards_created += 1
            logger.debug(
                f"Created award for product {product.id}: "
                f"{award_fields['competition']} {award_fields['year']} ({award_fields['medal']})"
            )
        except Exception as e:
            logger.error(f"Failed to create award for product {product.id}: {e}")
            continue

    # Update denormalized award_count on the product
    if awards_created > 0:
        product.award_count = product.awards_rel.count()
        product.save(update_fields=["award_count"])
        logger.info(
            f"Created {awards_created} awards for product {product.id}, "
            f"total award_count: {product.award_count}"
        )

    return awards_created


def create_product_ratings(
    product: DiscoveredProduct,
    ratings_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    Create ProductRating records from ratings data.

    Args:
        product: The DiscoveredProduct to create ratings for
        ratings_data: List of rating dictionaries

    Returns:
        Number of ratings created
    """
    if not ratings_data:
        return 0

    ratings_created = 0

    for rating_data in ratings_data:
        # Extract and convert rating fields
        rating_fields = {}
        for ai_key, (model_field, converter) in RATING_FIELD_MAPPING.items():
            value = rating_data.get(ai_key)
            converted = converter(value)
            if converted is not None:
                rating_fields[model_field] = converted

        # Validate required fields
        required_fields = ["source", "score", "max_score"]
        missing_required = [f for f in required_fields if not rating_fields.get(f)]
        if missing_required:
            logger.warning(
                f"Rating for product {product.id} missing required fields: {missing_required}"
            )
            continue

        # Check for duplicate ratings
        existing_rating = ProductRating.objects.filter(
            product=product,
            source=rating_fields["source"],
            score=rating_fields["score"],
        ).exists()

        if existing_rating:
            logger.debug(f"Rating already exists for product {product.id}")
            continue

        # Create the rating record
        try:
            ProductRating.objects.create(
                product=product,
                **rating_fields,
            )
            ratings_created += 1
            logger.debug(
                f"Created rating for product {product.id}: "
                f"{rating_fields['source']} - {rating_fields['score']}/{rating_fields['max_score']}"
            )
        except Exception as e:
            logger.error(f"Failed to create rating for product {product.id}: {e}")
            continue

    # Update denormalized rating_count on the product
    if ratings_created > 0:
        product.rating_count = product.ratings_rel.count()
        product.save(update_fields=["rating_count"])
        logger.info(
            f"Created {ratings_created} ratings for product {product.id}, "
            f"total rating_count: {product.rating_count}"
        )

    return ratings_created


def create_product_images(
    product: DiscoveredProduct,
    images_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    Create ProductImage records from images data.

    Args:
        product: The DiscoveredProduct to create images for
        images_data: List of image dictionaries

    Returns:
        Number of images created
    """
    if not images_data:
        return 0

    images_created = 0

    for image_data in images_data:
        # Extract and convert image fields
        image_fields = {}
        for ai_key, (model_field, converter) in IMAGE_FIELD_MAPPING.items():
            value = image_data.get(ai_key)
            converted = converter(value)
            if converted is not None:
                # Handle alternate key for image_type
                if model_field == "image_type" and "image_type" in image_fields:
                    continue  # Skip if already set
                image_fields[model_field] = converted

        # Validate required fields
        required_fields = ["url", "image_type", "source"]
        missing_required = [f for f in required_fields if not image_fields.get(f)]
        if missing_required:
            logger.warning(
                f"Image for product {product.id} missing required fields: {missing_required}"
            )
            continue

        # Validate image_type
        image_type = image_fields.get("image_type")
        if image_type not in VALID_IMAGE_TYPES:
            logger.warning(
                f"Image for product {product.id} has invalid image_type: {image_type}. "
                f"Valid choices are: {VALID_IMAGE_TYPES}"
            )
            continue

        # Check for duplicate images
        existing_image = ProductImage.objects.filter(
            product=product,
            url=image_fields["url"],
        ).exists()

        if existing_image:
            logger.debug(f"Image already exists for product {product.id}")
            continue

        # Default is_primary to False if not provided
        if "is_primary" not in image_fields:
            image_fields["is_primary"] = False

        # Create the image record
        try:
            ProductImage.objects.create(
                product=product,
                **image_fields,
            )
            images_created += 1
            logger.debug(
                f"Created image for product {product.id}: "
                f"{image_fields['url']} ({image_fields['image_type']})"
            )
        except Exception as e:
            logger.error(f"Failed to create image for product {product.id}: {e}")
            continue

    if images_created > 0:
        logger.info(f"Created {images_created} images for product {product.id}")

    return images_created


# =============================================================================
# ProductSource and Provenance Functions
# =============================================================================


def get_extracted_field_names(extracted_data: Dict[str, Any]) -> List[str]:
    """
    Get list of field names that were successfully extracted.

    Args:
        extracted_data: Dict from AI Enhancement Service

    Returns:
        List of field names that have values
    """
    extracted_fields = []

    for ai_key, (model_field, converter) in FIELD_MAPPING.items():
        value = extracted_data.get(ai_key)
        converted = converter(value)

        # Include field if it has a meaningful value
        if converted is not None:
            # For lists, only include if non-empty
            if isinstance(converted, list):
                if converted:  # Non-empty list
                    extracted_fields.append(model_field)
            else:
                extracted_fields.append(model_field)

    return extracted_fields


def create_product_source(
    product: DiscoveredProduct,
    crawled_source: Optional[CrawledSource],
    extraction_confidence: float,
    extracted_data: Dict[str, Any],
) -> Optional[ProductSource]:
    """
    Create ProductSource junction record.

    Args:
        product: The DiscoveredProduct that was created/updated
        crawled_source: The CrawledSource the product was extracted from
        extraction_confidence: AI confidence score for the extraction
        extracted_data: Dict from AI Enhancement Service

    Returns:
        Created ProductSource instance, or None if not applicable
    """
    if not crawled_source:
        logger.debug(f"No crawled_source provided for product {product.id}, skipping ProductSource")
        return None

    # Get list of fields that were extracted
    fields_extracted = get_extracted_field_names(extracted_data)

    # Convert confidence to Decimal for the model field
    confidence_decimal = Decimal(str(extraction_confidence)).quantize(Decimal("0.01"))

    try:
        # Use get_or_create to handle unique constraint gracefully
        product_source, created = ProductSource.objects.get_or_create(
            product=product,
            source=crawled_source,
            defaults={
                "extraction_confidence": confidence_decimal,
                "fields_extracted": fields_extracted,
                "mention_count": 1,
            }
        )

        if created:
            logger.debug(
                f"Created ProductSource linking product {product.id} to source {crawled_source.id}, "
                f"confidence: {confidence_decimal}, fields: {len(fields_extracted)}"
            )
        else:
            # Update existing record with new/merged data
            existing_fields = set(product_source.fields_extracted or [])
            new_fields = set(fields_extracted)
            merged_fields = list(existing_fields | new_fields)

            # Take higher confidence
            if confidence_decimal > product_source.extraction_confidence:
                product_source.extraction_confidence = confidence_decimal

            product_source.fields_extracted = merged_fields
            product_source.save(update_fields=["extraction_confidence", "fields_extracted"])

            logger.debug(
                f"Updated existing ProductSource for product {product.id} and source {crawled_source.id}"
            )

        return product_source

    except IntegrityError as e:
        logger.warning(
            f"IntegrityError creating ProductSource for product {product.id} and source {crawled_source.id}: {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Failed to create ProductSource for product {product.id}: {e}"
        )
        return None


def _is_empty_value(value: Any) -> bool:
    """Check if a value should be considered empty/null."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _value_to_string(value: Any) -> str:
    """Convert a value to string for storage in ProductFieldSource.extracted_value."""
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def create_field_provenance_records(
    product: DiscoveredProduct,
    source: CrawledSource,
    extracted_data: Dict[str, Any],
    field_confidences: Optional[Dict[str, float]],
    overall_confidence: float,
) -> int:
    """
    Create ProductFieldSource records for each extracted field.

    Args:
        product: The DiscoveredProduct to link provenance to
        source: The CrawledSource where data was extracted from
        extracted_data: Dict of extracted field values from AI
        field_confidences: Optional dict of per-field confidence scores
        overall_confidence: Overall extraction confidence to use as default

    Returns:
        Number of provenance records created
    """
    records_created = 0

    for ai_key in FIELD_MAPPING.keys():
        value = extracted_data.get(ai_key)

        # Skip empty values
        if _is_empty_value(value):
            continue

        # Get field confidence (use field-specific if available, else overall)
        confidence = overall_confidence
        if field_confidences and ai_key in field_confidences:
            confidence = field_confidences[ai_key]

        # Skip fields with zero confidence
        if confidence <= 0:
            continue

        # Convert value to string for storage
        extracted_value = _value_to_string(value)

        # Use update_or_create to handle unique constraint gracefully
        _, created = ProductFieldSource.objects.update_or_create(
            product=product,
            field_name=ai_key,
            source=source,
            defaults={
                "confidence": Decimal(str(confidence)),
                "extracted_value": extracted_value,
            },
        )

        if created:
            records_created += 1

    logger.debug(
        f"Created {records_created} field provenance records for product {product.id}"
    )

    return records_created


# =============================================================================
# Main Entry Point: save_discovered_product
# =============================================================================


def save_discovered_product(
    extracted_data: Dict[str, Any],
    source_url: str,
    product_type: str,
    discovery_source: str,
    crawled_source: Optional[CrawledSource] = None,
    check_existing: bool = False,
    field_confidences: Optional[Dict[str, float]] = None,
    extraction_confidence: float = 0.8,
    raw_content: str = "",
) -> ProductSaveResult:
    """
    UNIFIED entry point for creating/updating DiscoveredProduct records.

    This function handles:
    1. Normalizing input data
    2. Checking for existing product (deduplication)
    3. Extracting individual fields using FIELD_MAPPING
    4. Getting or creating brand
    5. Creating DiscoveredProduct with individual columns
    6. Creating WhiskeyDetails/PortWineDetails based on product_type
    7. Creating ProductAward, ProductRating, ProductImage records
    8. Creating ProductSource and ProductFieldSource provenance records

    Args:
        extracted_data: Dict of extracted product data
        source_url: URL where product was discovered
        product_type: Product type ('whiskey', 'port_wine', etc.)
        discovery_source: How product was discovered ('competition', 'search', etc.)
        crawled_source: Optional CrawledSource for provenance tracking
        check_existing: If True, check for existing product by fingerprint/name
        field_confidences: Optional dict of per-field confidence scores
        extraction_confidence: Overall extraction confidence (0.0-1.0)
        raw_content: Optional raw HTML content

    Returns:
        ProductSaveResult with product and creation metadata
    """
    # Step 1: Normalize extracted data
    normalized_data = normalize_extracted_data(extracted_data)

    # Add source_url to data for fingerprint computation
    normalized_data["source_url"] = source_url

    # Step 2: Extract individual field values
    individual_fields = extract_individual_fields(normalized_data)
    tasting_fields = extract_tasting_fields(normalized_data)

    # Merge tasting fields
    all_fields = {**individual_fields, **tasting_fields}

    # Step 3: Compute fingerprint for deduplication
    fingerprint = DiscoveredProduct.compute_fingerprint({
        **normalized_data,
        "product_type": product_type,
    })

    # Step 4: Compute content hash
    content_hash = hashlib.sha256((raw_content or source_url).encode()).hexdigest()

    # Step 5: Get or create brand
    brand, brand_created = get_or_create_brand(normalized_data, crawled_source, extraction_confidence)

    # Step 6: Extract awards, ratings, images data
    awards_data = normalized_data.get("awards", [])
    ratings_data = normalized_data.get("ratings", [])
    images_data = normalized_data.get("images", [])

    # Handle competition data where award info is in top-level fields
    if not awards_data and normalized_data.get("medal"):
        awards_data = [{
            "competition": normalized_data.get("competition"),
            "year": normalized_data.get("year"),
            "medal": normalized_data.get("medal"),
            "category": normalized_data.get("category"),
            "competition_country": normalized_data.get("competition_country", "Unknown"),
        }]

    with transaction.atomic():
        # Step 7: Check for existing product if requested
        existing_product = None
        if check_existing:
            # First try fingerprint match
            existing_product = DiscoveredProduct.objects.filter(
                fingerprint=fingerprint
            ).first()

            # Then try name match
            if not existing_product:
                name = all_fields.get("name") or normalized_data.get("name")
                if name:
                    existing_product = DiscoveredProduct.objects.filter(
                        name__iexact=name
                    ).first()

        if existing_product:
            # Update existing product with merged data
            for field_name, value in all_fields.items():
                current_value = getattr(existing_product, field_name, None)
                # Only update if current value is empty/None
                if current_value is None or current_value == "" or current_value == []:
                    setattr(existing_product, field_name, value)

            # Update confidence if higher
            if extraction_confidence > (existing_product.extraction_confidence or 0):
                existing_product.extraction_confidence = extraction_confidence

            existing_product.save()

            # Create awards, ratings, images for existing product
            awards_created = create_product_awards(existing_product, awards_data)
            ratings_created = create_product_ratings(existing_product, ratings_data)
            images_created = create_product_images(existing_product, images_data)

            # Create provenance records if crawled_source provided
            source_record_created = False
            provenance_records = 0
            if crawled_source:
                product_source = create_product_source(
                    existing_product, crawled_source, extraction_confidence, normalized_data
                )
                source_record_created = product_source is not None

                provenance_records = create_field_provenance_records(
                    existing_product, crawled_source, normalized_data,
                    field_confidences, extraction_confidence
                )

            return ProductSaveResult(
                product=existing_product,
                created=False,
                whiskey_details_created=False,
                port_wine_details_created=False,
                awards_created=awards_created,
                ratings_created=ratings_created,
                images_created=images_created,
                source_record_created=source_record_created,
                provenance_records_created=provenance_records,
                brand_created=brand_created,
                brand=brand,
            )

        # Step 8: Create new product
        # Validate product type
        valid_types = [pt.value for pt in ProductType]
        if product_type not in valid_types:
            product_type = ProductType.WHISKEY

        # Map discovery_source string to enum
        discovery_source_value = discovery_source
        if discovery_source == "competition":
            discovery_source_value = DiscoverySource.COMPETITION
        elif discovery_source == "search":
            discovery_source_value = DiscoverySource.SEARCH
        elif discovery_source == "hub_spoke":
            discovery_source_value = DiscoverySource.HUB_SPOKE
        else:
            discovery_source_value = DiscoverySource.DIRECT

        create_kwargs = {
            # Core required fields
            "source_url": source_url,
            "product_type": product_type,
            "raw_content": raw_content[:50000] if raw_content else "",
            "raw_content_hash": content_hash,
            # JSONFields (dual-write for transition)
            "extracted_data": normalized_data,
            "enriched_data": {},
            "extraction_confidence": extraction_confidence,
            "fingerprint": fingerprint,
            "status": DiscoveredProductStatus.PENDING,
            "discovery_source": discovery_source_value,
            "brand": brand,
        }

        # Add individual field values
        create_kwargs.update(all_fields)

        product = DiscoveredProduct.objects.create(**create_kwargs)

        # Step 9: Create WhiskeyDetails for whiskey products
        whiskey_details_created = False
        if product_type == ProductType.WHISKEY or product_type == "whiskey":
            whiskey_details = _create_whiskey_details(product, normalized_data)
            whiskey_details_created = whiskey_details is not None

        # Step 10: Create PortWineDetails for port wine products
        port_wine_details_created = False
        if product_type == ProductType.PORT_WINE or product_type == "port_wine":
            port_wine_details = _create_port_wine_details(product, normalized_data)
            port_wine_details_created = port_wine_details is not None

        # Step 11: Create awards, ratings, images
        awards_created = create_product_awards(product, awards_data)
        ratings_created = create_product_ratings(product, ratings_data)
        images_created = create_product_images(product, images_data)

        # Step 12: Create provenance records if crawled_source provided
        source_record_created = False
        provenance_records = 0
        if crawled_source:
            product_source = create_product_source(
                product, crawled_source, extraction_confidence, normalized_data
            )
            source_record_created = product_source is not None

            provenance_records = create_field_provenance_records(
                product, crawled_source, normalized_data,
                field_confidences, extraction_confidence
            )

        logger.info(
            f"Created new product {product.id}: "
            f"{all_fields.get('name', normalized_data.get('name', 'Unknown'))}"
        )

        return ProductSaveResult(
            product=product,
            created=True,
            whiskey_details_created=whiskey_details_created,
            port_wine_details_created=port_wine_details_created,
            awards_created=awards_created,
            ratings_created=ratings_created,
            images_created=images_created,
            source_record_created=source_record_created,
            provenance_records_created=provenance_records,
            brand_created=brand_created,
            brand=brand,
        )
