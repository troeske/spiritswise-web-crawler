"""
Validators Module - Field validation and normalization utilities.

Phase 11: Integration Failure Validators

This module provides validators for cleaning and normalizing field values
from extracted product data, handling edge cases that cause integration failures.
"""

from crawler.validators.whiskey import (
    normalize_whiskey_type,
    clean_vintage_year,
    extract_brand_from_name,
    validate_whiskey_data,
)

from crawler.validators.port_wine import (
    clean_age_designation,
    validate_port_wine_data,
)

__all__ = [
    "normalize_whiskey_type",
    "clean_vintage_year",
    "extract_brand_from_name",
    "validate_whiskey_data",
    "clean_age_designation",
    "validate_port_wine_data",
]
