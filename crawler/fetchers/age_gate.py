"""
Age gate detection utilities.

Provides functions to detect age verification gates on whiskey/spirits websites.
Age gates are detected by:
1. Content length threshold (< 500 chars typically indicates gate page)
2. Keyword detection for age verification phrases
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# Age gate detection keywords - common phrases on verification pages
AGE_GATE_KEYWORDS = [
    "legal drinking age",
    "are you 21",
    "are you of legal drinking age",
    "age verification",
    "verify your age",
    "confirm your age",
    "you must be 21",
    "you must be of legal age",
    "enter your date of birth",
    "please verify your age",
    "are you over 18",
    "are you over 21",
    "i am 21 or older",
    "i am of legal drinking age",
    "by entering this site",
    "must be of legal purchasing age",
]


@dataclass
class AgeGateDetectionResult:
    """Result of age gate detection analysis."""

    is_age_gate: bool
    reason: str
    keyword_matched: Optional[str] = None
    content_length: int = 0


def detect_age_gate(
    content: str,
    threshold: Optional[int] = None,
) -> AgeGateDetectionResult:
    """
    Detect if content represents an age gate page.

    Detection is based on:
    1. Content length - if < threshold (default 500), likely an age gate
    2. Keyword presence - if age verification phrases found

    Args:
        content: The page content to analyze
        threshold: Content length threshold (defaults to settings value)

    Returns:
        AgeGateDetectionResult with detection status and reason
    """
    if threshold is None:
        threshold = getattr(
            settings,
            "CRAWLER_AGE_GATE_CONTENT_THRESHOLD",
            500
        )

    content_length = len(content)

    # Check 1: Content length threshold
    if content_length < threshold:
        logger.debug(
            f"Age gate detected: content length {content_length} < {threshold}"
        )
        return AgeGateDetectionResult(
            is_age_gate=True,
            reason=f"Content length ({content_length}) below threshold ({threshold})",
            content_length=content_length,
        )

    # Check 2: Keyword detection
    content_lower = content.lower()
    for keyword in AGE_GATE_KEYWORDS:
        if keyword in content_lower:
            logger.debug(f"Age gate detected: keyword '{keyword}' found")
            return AgeGateDetectionResult(
                is_age_gate=True,
                reason=f"Keyword detected: '{keyword}'",
                keyword_matched=keyword,
                content_length=content_length,
            )

    # No age gate detected
    return AgeGateDetectionResult(
        is_age_gate=False,
        reason="No age gate indicators found",
        content_length=content_length,
    )


def get_age_gate_button_selectors() -> list[str]:
    """
    Get CSS selectors for common age gate confirmation buttons.

    Used by Tier 2 Playwright fetcher to click through age gates.

    Returns:
        List of CSS selector strings for age gate buttons
    """
    return [
        # Text-based selectors (most common)
        'button:has-text("Yes")',
        'button:has-text("Enter")',
        'button:has-text("I am 21")',
        'button:has-text("I am 18")',
        'button:has-text("Confirm")',
        'button:has-text("Agree")',
        'button:has-text("Enter Site")',
        'button:has-text("I am of legal")',
        'button:has-text("21 or older")',
        'button:has-text("over 21")',
        'button:has-text("over 18")',
        # Common button classes/IDs
        'button.age-verify',
        'button.enter-site',
        'button#ageVerify',
        'button#enterSite',
        'button[data-age-verify]',
        # Anchor tags styled as buttons
        'a:has-text("Yes")',
        'a:has-text("Enter")',
        'a:has-text("I am 21")',
        'a.age-verify',
        'a.enter-site',
        # Input buttons
        'input[type="submit"][value*="Yes"]',
        'input[type="submit"][value*="Enter"]',
        'input[type="button"][value*="21"]',
    ]
