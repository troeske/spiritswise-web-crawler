"""
Port Wine Validators - Normalization and cleaning for port wine product data.

Phase 11: Integration Failure Validators

Fixes:
- Age designation cleaning (1 product: Sandeman 30 Year Old Tawny)
"""

import re
from typing import Any, Dict, Optional


# =============================================================================
# Age Designation Cleaning
# =============================================================================


def clean_age_designation(age_designation: Any) -> Optional[int]:
    """
    Clean and validate port wine age designation values.

    Port wines typically have age designations in multiples of 10:
    10, 20, 30, 40 year tawny ports.

    Handles:
    - String values: "30 years", "30 Year Old", "30"
    - Integer values: 30
    - Values that need rounding: 32 -> 30
    - Null-like values: "N/A", "None"

    Args:
        age_designation: Raw age designation value

    Returns:
        Valid age as integer (10, 20, 30, 40, etc.) or None if invalid
    """
    if age_designation is None:
        return None

    # Handle string inputs
    if isinstance(age_designation, str):
        cleaned = age_designation.strip()

        # Handle empty string
        if not cleaned:
            return None

        # Handle null-like strings
        null_values = ["n/a", "na", "none", "nv", "-", ""]
        if cleaned.lower() in null_values:
            return None

        # Extract number from strings like "30 years", "30 Year Old"
        match = re.search(r'(\d+)', cleaned)
        if match:
            age = int(match.group(1))
        else:
            return None
    elif isinstance(age_designation, (int, float)):
        age = int(age_designation)
    else:
        return None

    # Validate minimum age (port age designations start at 10)
    if age < 10:
        return None

    # Round to nearest 10 for standard port age categories
    # 10, 20, 30, 40, etc.
    rounded_age = round(age / 10) * 10

    # Ensure minimum of 10
    if rounded_age < 10:
        rounded_age = 10

    return rounded_age


# =============================================================================
# Full Validation Pipeline
# =============================================================================


def validate_port_wine_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full validation pipeline for port wine product data.

    Applies all validators:
    1. Clean age_designation

    Args:
        data: Raw port wine data dictionary

    Returns:
        Validated and cleaned data dictionary
    """
    validated = data.copy()

    # Clean age_designation
    if "age_designation" in validated:
        validated["age_designation"] = clean_age_designation(validated["age_designation"])

    return validated
