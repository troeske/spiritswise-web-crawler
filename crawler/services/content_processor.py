"""
Content Processing Pipeline.

Task 7.3: Implements content processing for AI Enhancement integration.
RECT-001: Updated to populate individual columns from AI response.
RECT-002: Added WhiskeyDetails creation for whiskey products.
RECT-003: Added PortWineDetails creation for port wine products.
RECT-004: Added ProductAward creation from awards data.
RECT-005: Added ProductSource junction record creation.
RECT-006: Added ProductFieldSource provenance record creation.

UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 2:
- Updated _save_product() to use unified save_discovered_product() function
- Maintains backward compatibility with existing return signature
- Helper functions retained for Phase 5 cleanup

Pipeline steps:
1. Clean raw HTML content using trafilatura extraction
2. Determine product_type_hint from CrawlerSource.product_types
3. Call AI Enhancement Service
4. Parse response and populate individual DiscoveredProduct columns
5. Create WhiskeyDetails for whiskey products (RECT-002)
6. Create PortWineDetails for port wine products (RECT-003)
7. Create ProductAward records from awards data
8. Create ProductSource junction record linking product to crawled source
9. Create ProductFieldSource provenance records for each extracted field
10. Track costs for AI calls
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from asgiref.sync import sync_to_async
from django.db import transaction, IntegrityError
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    CrawledSource,
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlCost,
    CostService,
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
    BrandSource,
    BrandAward,
)
from crawler.services.ai_client import AIEnhancementClient, EnhancementResult, get_ai_client

# UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 2: Import unified product saver
from crawler.services.product_saver import save_discovered_product, ProductSaveResult

logger = logging.getLogger(__name__)

# Trafilatura import with fallback
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not available, will use raw content")


# =============================================================================
# RECT-001: Field Mapping from AI Response Keys to Model Fields
# =============================================================================
# Maps AI response keys to (model_field_name, type_converter) tuples.
# Type converters handle str->appropriate type conversion with null safety.

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

    RECT-002: Added for whiskey-specific boolean fields.

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


# Field mapping: AI response key -> (model field name, type converter)
# Core product fields
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


# =============================================================================
# RECT-002: Whiskey Field Mapping for WhiskeyDetails Model
# =============================================================================
# Maps AI response keys to (model_field_name, type_converter) tuples
# for whiskey-specific fields stored in WhiskeyDetails.

WHISKEY_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Classification
    "whiskey_type": ("whiskey_type", _safe_str),  # choices validation in model
    "whiskey_country": ("whiskey_country", _safe_str),
    "whiskey_region": ("whiskey_region", _safe_str),

    # Production
    "distillery": ("distillery", _safe_str),
    "mash_bill": ("mash_bill", _safe_str),

    # Cask Information
    "cask_strength": ("cask_strength", _safe_bool),
    "single_cask": ("single_cask", _safe_bool),
    "cask_number": ("cask_number", _safe_str),

    # Vintage/Batch Info
    "vintage_year": ("vintage_year", _safe_int),
    "bottling_year": ("bottling_year", _safe_int),
    "batch_number": ("batch_number", _safe_str),

    # Peat
    "peated": ("peated", _safe_bool),
    "peat_level": ("peat_level", _safe_str),  # choices validation in model
}

# Valid whiskey type values for validation
VALID_WHISKEY_TYPES = [choice.value for choice in WhiskeyTypeChoices]

# Valid peat level values for validation
VALID_PEAT_LEVELS = [choice.value for choice in PeatLevelChoices]


# =============================================================================
# RECT-003: Port Wine Field Mapping from AI Response to PortWineDetails Model
# =============================================================================
# Maps AI response keys to (model_field_name, type_converter) tuples.

PORT_WINE_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Style
    "style": ("style", _safe_str),  # choices validation handled separately
    "indication_age": ("indication_age", _safe_str),

    # Vintage Information
    "harvest_year": ("harvest_year", _safe_int),
    "bottling_year": ("bottling_year", _safe_int),

    # Production
    "grape_varieties": ("grape_varieties", _safe_list),
    "quinta": ("quinta", _safe_str),
    "douro_subregion": ("douro_subregion", _safe_str),  # choices validation handled separately
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


# =============================================================================
# RECT-004: Award Field Mapping from AI Response to ProductAward Model
# =============================================================================
# Maps AI award response keys to (model_field_name, type_converter) tuples.

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


# =============================================================================
# RECT-002: Whiskey Field Extraction and Details Creation
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

def extract_whiskey_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract whiskey-specific field values from AI response data.

    RECT-002: Extracts fields for WhiskeyDetails model.

    Applies type conversions and validates choice fields.

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

    RECT-002: Heuristic mapping from country/region to whiskey type.

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

    RECT-002: Creates linked WhiskeyDetails with whiskey-specific fields.
    NOTE: This function is retained for Phase 5 cleanup.

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
# RECT-003: Port Wine Field Extraction and Details Creation
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

def extract_port_wine_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract port wine-specific field values from AI response data.

    RECT-003: Extracts fields for PortWineDetails model.

    Applies type conversions and validates choice fields.

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

    RECT-003: Heuristic inference of port style from name.

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

    RECT-003: Creates linked PortWineDetails with port-specific fields.
    NOTE: This function is retained for Phase 5 cleanup.

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
# RECT-004: Award Creation Functions
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

def create_product_awards(
    product: DiscoveredProduct,
    awards_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    RECT-004: Create ProductAward records from awards data.

    Extracts awards from AI response and creates individual ProductAward
    records with proper field mapping and validation.
    NOTE: This function is retained for Phase 5 cleanup.

    Args:
        product: The DiscoveredProduct to create awards for
        awards_data: List of award dictionaries from AI response

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

        # Validate required fields
        required_fields = ["competition", "competition_country", "year", "medal", "award_category"]
        missing_required = [f for f in required_fields if not award_fields.get(f)]
        if missing_required:
            logger.warning(
                f"Award for product {product.id} missing required fields: {missing_required}"
            )
            continue

        # Validate medal choice
        medal = award_fields.get("medal")
        if medal not in VALID_MEDAL_CHOICES:
            logger.warning(
                f"Award for product {product.id} has invalid medal type: {medal}. "
                f"Valid choices are: {VALID_MEDAL_CHOICES}"
            )
            continue

        # Check for duplicate awards (same product + competition + year + medal + category)
        existing_award = ProductAward.objects.filter(
            product=product,
            competition=award_fields["competition"],
            year=award_fields["year"],
            medal=award_fields["medal"],
            award_category=award_fields["award_category"],
        ).exists()

        if existing_award:
            logger.debug(
                f"Award already exists for product {product.id}: "
                f"{award_fields['competition']} {award_fields['year']}"
            )
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
                f"{award_fields['competition']} {award_fields['year']} ({medal})"
            )
        except Exception as e:
            logger.error(
                f"Failed to create award for product {product.id}: {e}"
            )
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


# =============================================================================
# RECT-007: ProductRating Creation Functions
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

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


RATING_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Source
    "source": ("source", _safe_str),
    "source_country": ("source_country", _safe_str),

    # Score
    "score": ("score", _safe_decimal),
    "max_score": ("max_score", _safe_int),

    # Optional Details
    "reviewer": ("reviewer", _safe_str),
    "review_url": ("review_url", _safe_str),
    "date": ("date", _safe_date),
    "review_count": ("review_count", _safe_int),
}


def create_product_ratings(
    product: DiscoveredProduct,
    ratings_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    RECT-007: Create ProductRating records from ratings data.

    Extracts ratings from AI response and creates individual ProductRating
    records with proper field mapping and validation.
    NOTE: This function is retained for Phase 5 cleanup.

    Args:
        product: The DiscoveredProduct to create ratings for
        ratings_data: List of rating dictionaries from AI response

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

        # Check for duplicate ratings (same product + source + score)
        existing_rating = ProductRating.objects.filter(
            product=product,
            source=rating_fields["source"],
            score=rating_fields["score"],
        ).exists()

        if existing_rating:
            logger.debug(
                f"Rating already exists for product {product.id}: "
                f"{rating_fields['source']} - {rating_fields['score']}"
            )
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
            logger.error(
                f"Failed to create rating for product {product.id}: {e}"
            )
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


# =============================================================================
# RECT-008: ProductImage Creation Functions
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

IMAGE_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    # Required fields
    "url": ("url", _safe_str),
    "image_type": ("image_type", _safe_str),  # choices validation handled separately
    "source": ("source", _safe_str),

    # Dimensions
    "width": ("width", _safe_int),
    "height": ("height", _safe_int),

    # Status
    "is_primary": ("is_primary", _safe_bool),
}

# Valid image type values for validation
VALID_IMAGE_TYPES = [choice.value for choice in ImageTypeChoices]


def create_product_images(
    product: DiscoveredProduct,
    images_data: Optional[List[Dict[str, Any]]],
) -> int:
    """
    RECT-008: Create ProductImage records from images data.

    Extracts images from AI response and creates individual ProductImage
    records with proper field mapping and validation.
    NOTE: This function is retained for Phase 5 cleanup.

    Args:
        product: The DiscoveredProduct to create images for
        images_data: List of image dictionaries from AI response

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
                image_fields[model_field] = converted

        # Validate required fields
        required_fields = ["url", "image_type", "source"]
        missing_required = [f for f in required_fields if not image_fields.get(f)]
        if missing_required:
            logger.warning(
                f"Image for product {product.id} missing required fields: {missing_required}"
            )
            continue

        # Validate image_type is a valid choice
        image_type = image_fields.get("image_type")
        if image_type not in VALID_IMAGE_TYPES:
            logger.warning(
                f"Image for product {product.id} has invalid image_type: {image_type}. "
                f"Valid choices are: {VALID_IMAGE_TYPES}"
            )
            continue

        # Check for duplicate images (same product + url)
        existing_image = ProductImage.objects.filter(
            product=product,
            url=image_fields["url"],
        ).exists()

        if existing_image:
            logger.debug(
                f"Image already exists for product {product.id}: {image_fields['url']}"
            )
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
            logger.error(
                f"Failed to create image for product {product.id}: {e}"
            )
            continue

    if images_created > 0:
        logger.info(
            f"Created {images_created} images for product {product.id}"
        )

    return images_created


# =============================================================================
# RECT-005: ProductSource Junction Record Creation
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

def get_extracted_field_names(extracted_data: Dict[str, Any]) -> List[str]:
    """
    RECT-005: Get list of field names that were successfully extracted.

    Identifies which fields in the AI response have non-null, non-empty values.
    This is used for tracking provenance - which source provided which data.
    NOTE: This function is retained for Phase 5 cleanup.

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
    RECT-005: Create ProductSource junction record.

    Links a DiscoveredProduct to the CrawledSource it was extracted from,
    storing extraction metadata for provenance tracking.
    NOTE: This function is retained for Phase 5 cleanup.

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
            # Merge fields_extracted lists
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
        # Unique constraint violation - should not happen with get_or_create but handle just in case
        logger.warning(
            f"IntegrityError creating ProductSource for product {product.id} and source {crawled_source.id}: {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Failed to create ProductSource for product {product.id}: {e}"
        )
        return None


# =============================================================================
# RECT-006: Field Provenance Tracking
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================


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

    RECT-006: Tracks which source provided each field value for conflict
    resolution and data quality tracking.
    NOTE: This function is retained for Phase 5 cleanup.

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


def extract_individual_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract individual field values from AI response data.

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
# RECT-010: Brand Creation Functions
# NOTE: These functions are retained for Phase 5 cleanup.
# The actual creation is now done via save_discovered_product().
# =============================================================================

# Brand field mapping: AI response key -> (model field name, type converter)
BRAND_FIELD_MAPPING: Dict[str, Tuple[str, Callable]] = {
    "name": ("name", _safe_str),
    "country": ("country", _safe_str),
    "region": ("region", _safe_str),
    "official_website": ("official_website", _safe_str),
    "founded_year": ("founded_year", _safe_int),
}


def create_brand_source(
    brand: Optional["DiscoveredBrand"],
    crawled_source: Optional["CrawledSource"],
    confidence: float = 0.8,
    mention_type: Optional[str] = None,
) -> Optional["BrandSource"]:
    """
    Create or update a BrandSource junction record.

    RECT-013: Links a DiscoveredBrand to a CrawledSource that mentioned it.
    NOTE: This function is retained for Phase 5 cleanup.

    Args:
        brand: The DiscoveredBrand that was mentioned
        crawled_source: The CrawledSource that mentioned the brand
        confidence: Confidence score for the extraction (0.0-1.0)
        mention_type: Optional type of mention (e.g., "award_winner", "review")

    Returns:
        BrandSource record or None if brand or source is None
    """
    if not brand or not crawled_source:
        return None

    try:
        # Convert confidence to Decimal for storage
        from decimal import Decimal
        confidence_decimal = Decimal(str(confidence))

        # Use get_or_create to handle unique constraint
        brand_source, created = BrandSource.objects.get_or_create(
            brand=brand,
            source=crawled_source,
            defaults={
                "extraction_confidence": confidence_decimal,
                "mention_type": mention_type,
                "mention_count": 1,
            },
        )

        if created:
            # Update brand mention_count
            brand.mention_count = (brand.mention_count or 0) + 1
            brand.save(update_fields=["mention_count"])
            logger.info(f"Created BrandSource: {brand.name} <- {crawled_source.url}")
        else:
            # Update confidence if higher
            if confidence_decimal > brand_source.extraction_confidence:
                brand_source.extraction_confidence = confidence_decimal
                brand_source.save(update_fields=["extraction_confidence"])
                logger.debug(f"Updated BrandSource confidence for {brand.name}")

        return brand_source

    except Exception as e:
        logger.error(f"Failed to create BrandSource for {brand.name}: {e}")
        return None


def create_brand_award(
    brand: Optional["DiscoveredBrand"],
    competition: Optional[str],
    competition_country: str,
    year: int,
    medal: str,
    award_category: str,
    score: Optional[int] = None,
    award_url: Optional[str] = None,
) -> Optional["BrandAward"]:
    """
    Create a BrandAward record for brand-level awards.

    RECT-013: Creates BrandAward records for awards given to brands
    (as opposed to product-level awards stored in ProductAward).
    NOTE: This function is retained for Phase 5 cleanup.

    Args:
        brand: The DiscoveredBrand that won the award
        competition: Competition name
        competition_country: Country where competition is held
        year: Year the award was given
        medal: Medal/award level (must be valid MedalChoices)
        award_category: Category within the competition
        score: Optional score given
        award_url: Optional URL to award page

    Returns:
        BrandAward record or None if required fields missing
    """
    if not brand or not competition:
        return None

    # Validate medal choice
    valid_medals = [choice.value for choice in MedalChoices]
    if medal not in valid_medals:
        logger.warning(f"Invalid medal type '{medal}' for brand award, skipping")
        return None

    try:
        # Check for duplicate (same brand + competition + year + medal + category)
        existing = BrandAward.objects.filter(
            brand=brand,
            competition=competition,
            year=year,
            medal=medal,
            award_category=award_category,
        ).first()

        if existing:
            logger.debug(f"BrandAward already exists: {brand.name} - {competition} {year}")
            return existing

        # Create new award
        award = BrandAward.objects.create(
            brand=brand,
            competition=competition,
            competition_country=competition_country,
            year=year,
            medal=medal,
            award_category=award_category,
            score=score,
            award_url=award_url,
        )

        # Update brand award_count
        brand.award_count = (brand.award_count or 0) + 1
        brand.save(update_fields=["award_count"])

        logger.info(f"Created BrandAward: {brand.name} - {competition} {year} ({medal})")
        return award

    except Exception as e:
        logger.error(f"Failed to create BrandAward for {brand.name}: {e}")
        return None


def get_or_create_brand(
    extracted_data: Dict[str, Any],
    crawled_source: Optional["CrawledSource"] = None,
    confidence: float = 0.8,
) -> Tuple[Optional["DiscoveredBrand"], bool]:
    """
    Get or create a DiscoveredBrand from extracted data.

    RECT-010: Creates brand records from AI extraction and links to products.
    RECT-013: Now also creates BrandSource junction record when crawled_source provided.
    NOTE: This function is retained for Phase 5 cleanup.

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
    from crawler.models import DiscoveredBrand

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
    from django.utils.text import slugify
    brand_slug = slugify(brand_name)

    # Try to find existing brand (case insensitive)
    try:
        existing = DiscoveredBrand.objects.filter(
            name__iexact=brand_name
        ).first()

        if existing:
            # Create BrandSource junction if crawled_source provided
            if crawled_source:
                create_brand_source(existing, crawled_source, confidence)
            return existing, False

        # Also try to match by slug
        existing_by_slug = DiscoveredBrand.objects.filter(
            slug=brand_slug
        ).first()

        if existing_by_slug:
            # Create BrandSource junction if crawled_source provided
            if crawled_source:
                create_brand_source(existing_by_slug, crawled_source, confidence)
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

        # Create BrandSource junction if crawled_source provided
        if crawled_source:
            create_brand_source(brand, crawled_source, confidence)

        return brand, True

    except IntegrityError as e:
        # Race condition - brand was created between check and create
        logger.warning(f"IntegrityError creating brand {brand_name}, trying to fetch: {e}")
        existing = DiscoveredBrand.objects.filter(name__iexact=brand_name).first()
        if existing:
            # Create BrandSource junction if crawled_source provided
            if crawled_source:
                create_brand_source(existing, crawled_source, confidence)
            return existing, False
        return None, False
    except Exception as e:
        logger.error(f"Failed to create brand {brand_name}: {e}")
        return None, False


@dataclass
class ProcessingResult:
    """Result of content processing."""

    success: bool
    product_id: Optional[str] = None
    is_new: bool = False
    product_type: str = ""
    confidence: float = 0.0
    error: Optional[str] = None
    cost_cents: int = 0
    awards_created: int = 0
    product_source_created: bool = False
    provenance_records_created: int = 0
    whiskey_details_created: bool = False
    port_wine_details_created: bool = False


class ContentProcessor:
    """
    Content processing pipeline for AI Enhancement integration.

    Handles the full flow from raw HTML to enriched DiscoveredProduct:
    1. Extract main content from HTML using trafilatura
    2. Determine product type hint from source configuration
    3. Call AI Enhancement Service
    4. Create/update DiscoveredProduct with individual columns populated
    5. Create WhiskeyDetails for whiskey products (RECT-002)
    6. Create ProductAward records from awards data
    7. Create ProductSource junction record
    8. Create ProductFieldSource provenance records
    9. Track API costs

    UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 2:
    - Now uses unified save_discovered_product() function
    - Maintains backward compatibility with existing return signature
    """

    # Estimated cost per AI enhancement call in cents
    # Based on average GPT-4 usage (~2000 tokens @ $0.03/1k input + $0.06/1k output)
    ESTIMATED_COST_CENTS = 12

    def __init__(self, ai_client: Optional[AIEnhancementClient] = None):
        """
        Initialize content processor.

        Args:
            ai_client: Optional pre-configured AI Enhancement client
        """
        self.ai_client = ai_client or get_ai_client()

    def extract_content(self, raw_html: str) -> str:
        """
        Extract main content from raw HTML using trafilatura.

        Args:
            raw_html: Raw HTML content from crawler

        Returns:
            Cleaned text content
        """
        if not TRAFILATURA_AVAILABLE or not raw_html:
            return raw_html

        try:
            # Use trafilatura to extract main content
            extracted = trafilatura.extract(
                raw_html,
                include_links=False,
                include_images=False,
                include_tables=True,
                output_format="txt",
            )

            if extracted and len(extracted) >= 50:
                logger.debug(f"Extracted {len(extracted)} chars from {len(raw_html)} char HTML")
                return extracted

            # If extraction is too short, fall back to raw HTML
            logger.debug("Trafilatura extraction too short, using raw HTML")
            return raw_html

        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {e}, using raw HTML")
            return raw_html

    def determine_product_type_hint(self, source: Optional[CrawlerSource]) -> str:
        """
        Determine product type hint from CrawlerSource.product_types.

        Args:
            source: CrawlerSource instance

        Returns:
            Product type string (e.g., 'whiskey', 'port_wine')
        """
        if not source:
            return "whiskey"

        product_types = source.product_types or []

        if not product_types:
            return "whiskey"

        # Return the first product type
        return product_types[0]

    async def process(
        self,
        url: str,
        raw_content: str,
        source: Optional[CrawlerSource] = None,
        crawl_job: Optional[CrawlJob] = None,
        crawled_source: Optional[CrawledSource] = None,
    ) -> ProcessingResult:
        """
        Process crawled content through the AI Enhancement pipeline.

        RECT-005: Added crawled_source parameter for ProductSource creation.
        RECT-006: Creates ProductFieldSource provenance records.

        Args:
            url: Source URL of the content
            raw_content: Raw HTML content from crawler
            source: CrawlerSource instance (the source configuration)
            crawl_job: CrawlJob instance for tracking
            crawled_source: CrawledSource instance (the actual crawled page)

        Returns:
            ProcessingResult with outcome
        """
        logger.info(f"Processing content from {url}")

        # Step 1: Extract content using trafilatura
        extracted_content = self.extract_content(raw_content)

        # Limit content size
        max_content_length = 50000
        if len(extracted_content) > max_content_length:
            extracted_content = extracted_content[:max_content_length]

        # Step 2: Determine product type hint
        product_type_hint = self.determine_product_type_hint(source)

        # Step 3: Call AI Enhancement Service
        result = await self.ai_client.enhance_from_crawler(
            content=extracted_content,
            source_url=url,
            product_type_hint=product_type_hint,
        )

        # Step 4: Track costs
        await self._track_cost(crawl_job, result)

        # Handle failure
        if not result.success:
            logger.warning(f"AI Enhancement failed for {url}: {result.error}")
            return ProcessingResult(
                success=False,
                error=result.error,
                cost_cents=self.ESTIMATED_COST_CENTS,
            )

        # Step 5: Create/update DiscoveredProduct, WhiskeyDetails, awards, ProductSource, and provenance
        product_id, is_new, awards_created, product_source_created, provenance_records, whiskey_details_created, port_wine_details_created = await self._save_product(
            url=url,
            raw_content=raw_content,
            result=result,
            source=source,
            crawl_job=crawl_job,
            crawled_source=crawled_source,
        )

        return ProcessingResult(
            success=True,
            product_id=product_id,
            is_new=is_new,
            product_type=result.product_type,
            confidence=result.confidence,
            cost_cents=self.ESTIMATED_COST_CENTS,
            awards_created=awards_created,
            product_source_created=product_source_created,
            provenance_records_created=provenance_records,
            whiskey_details_created=whiskey_details_created,
            port_wine_details_created=port_wine_details_created,
        )

    async def _track_cost(
        self,
        crawl_job: Optional[CrawlJob],
        result: EnhancementResult,
    ) -> None:
        """
        Track AI Enhancement API cost.

        Creates CrawlCost record for budget monitoring.

        Args:
            crawl_job: CrawlJob to link cost to
            result: EnhancementResult from API
        """
        try:
            @sync_to_async
            def create_cost():
                CrawlCost.objects.create(
                    service=CostService.OPENAI,
                    cost_cents=self.ESTIMATED_COST_CENTS,
                    crawl_job=crawl_job,
                    request_count=1,
                    timestamp=timezone.now(),
                )

            await create_cost()
            logger.debug(f"Tracked AI cost: {self.ESTIMATED_COST_CENTS} cents")

        except Exception as e:
            # Don't fail if cost tracking fails
            logger.warning(f"Failed to track AI cost: {e}")

    async def _save_product(
        self,
        url: str,
        raw_content: str,
        result: EnhancementResult,
        source: Optional[CrawlerSource],
        crawl_job: Optional[CrawlJob],
        crawled_source: Optional[CrawledSource] = None,
    ) -> Tuple[str, bool, int, bool, int, bool, bool]:
        """
        Save or update DiscoveredProduct from AI Enhancement result.

        UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 2:
        Now uses unified save_discovered_product() function from product_saver.py.
        Maintains backward compatibility with existing return signature.

        Args:
            url: Source URL
            raw_content: Raw HTML content
            result: EnhancementResult from AI service
            source: CrawlerSource instance
            crawl_job: CrawlJob instance
            crawled_source: CrawledSource instance for ProductSource and provenance

        Returns:
            Tuple of (product_id, is_new, awards_created, product_source_created, provenance_records, whiskey_details_created, port_wine_details_created)
        """
        @sync_to_async
        def save_product():
            # Use the unified save_discovered_product() function
            save_result: ProductSaveResult = save_discovered_product(
                extracted_data=result.extracted_data,
                source_url=url,
                product_type=result.product_type,
                discovery_source="direct",  # ContentProcessor uses direct discovery
                crawled_source=crawled_source,
                check_existing=True,  # Check for existing products by fingerprint
                field_confidences=result.field_confidences,
                extraction_confidence=result.confidence,
                raw_content=raw_content,
            )

            product = save_result.product

            # Update product with ContentProcessor-specific fields
            # (source, crawl_job are not part of unified save_discovered_product)
            update_fields = []
            if source is not None and product.source != source:
                product.source = source
                update_fields.append("source")
            if crawl_job is not None and product.crawl_job != crawl_job:
                product.crawl_job = crawl_job
                update_fields.append("crawl_job")

            # For existing products, merge enrichment data
            if not save_result.created:
                enriched_data = product.enriched_data or {}
                enriched_data = {
                    **enriched_data,
                    **result.enrichment,
                    "additional_sources": enriched_data.get(
                        "additional_sources", []
                    ) + [url],
                }
                product.enriched_data = enriched_data
                update_fields.append("enriched_data")

            if update_fields:
                product.save(update_fields=update_fields)

            # Map ProductSaveResult to expected return tuple
            return (
                str(product.id),
                save_result.created,
                save_result.awards_created,
                save_result.source_record_created,
                save_result.provenance_records_created,
                save_result.whiskey_details_created,
                save_result.port_wine_details_created,
            )

        return await save_product()


def get_content_processor() -> ContentProcessor:
    """
    Factory function to get configured ContentProcessor.

    Returns:
        ContentProcessor configured from Django settings
    """
    return ContentProcessor()
