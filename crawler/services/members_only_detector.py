"""
Members-Only Site Detection Service.

V3 Feature: Detects login/paywall/membership walls to refund search budget.

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 4.2
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class MembersOnlyDetector:
    """
    Detects members-only, paywall, and login-gated content.

    When a site requires login/membership to view content, we don't want
    to penalize the search budget since we can't extract useful data.
    """

    # Login form patterns
    LOGIN_FORM_PATTERNS = [
        r'<form[^>]*login',
        r'<form[^>]*signin',
        r'<form[^>]*sign-in',
        r'<input[^>]*type=["\']password["\']',
    ]

    # "Sign in to..." patterns
    SIGN_IN_PATTERNS = [
        r'sign\s*in\s*to\s*(view|access|continue|read)',
        r'log\s*in\s*to\s*(view|access|continue|read)',
        r'login\s*to\s*(view|access|continue|read)',
    ]

    # Membership language patterns
    MEMBERSHIP_PATTERNS = [
        r'members?\s*only',
        r'member\s*exclusive',
        r'join\s*(now|today)\s*to\s*(access|view|read)',
        r'subscription\s*required',
        r'subscribe\s*to\s*(access|view|read|unlock)',
    ]

    # Paywall indicator patterns
    PAYWALL_PATTERNS = [
        r'\bpaywall\b',
        r'premium\s*content',
        r'unlock\s*(this|full|the)\s*(content|article)',
        r'paid\s*subscribers?\s*only',
    ]

    # Access denied patterns
    ACCESS_DENIED_PATTERNS = [
        r'access\s*denied',
        r'restricted\s*area',
        r'authentication\s*required',
        r'please\s*(log\s*in|login|sign\s*in)',
    ]

    # HTTP codes that indicate members-only (don't penalize budget)
    MEMBERS_ONLY_HTTP_CODES = [401, 402, 403]

    def __init__(self):
        """Initialize detector with compiled patterns."""
        # Compile all patterns for efficiency
        all_patterns = (
            self.LOGIN_FORM_PATTERNS +
            self.SIGN_IN_PATTERNS +
            self.MEMBERSHIP_PATTERNS +
            self.PAYWALL_PATTERNS +
            self.ACCESS_DENIED_PATTERNS
        )
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in all_patterns
        ]

    def is_members_only(self, content: Optional[str]) -> bool:
        """
        Check if content indicates a members-only/paywalled page.

        Args:
            content: HTML content to analyze

        Returns:
            True if content appears to be behind a login/paywall
        """
        if not content:
            return False

        # Check each pattern
        for pattern in self._compiled_patterns:
            if pattern.search(content):
                logger.debug("Members-only indicator matched: %s", pattern.pattern)
                return True

        return False

    def is_members_only_http_code(self, status_code: int) -> bool:
        """
        Check if HTTP status code indicates members-only content.

        Args:
            status_code: HTTP response status code

        Returns:
            True if status code indicates authentication/payment required
        """
        return status_code in self.MEMBERS_ONLY_HTTP_CODES

    def check_response(
        self,
        content: Optional[str],
        status_code: int = 200,
    ) -> bool:
        """
        Check both content and status code for members-only indicators.

        Args:
            content: HTML content to analyze
            status_code: HTTP response status code

        Returns:
            True if either content or status indicates members-only
        """
        if self.is_members_only_http_code(status_code):
            logger.info(
                "Members-only detected via HTTP status: %d",
                status_code
            )
            return True

        if self.is_members_only(content):
            logger.info("Members-only detected via content analysis")
            return True

        return False

    def get_matched_patterns(self, content: Optional[str]) -> List[str]:
        """
        Get list of patterns that matched in the content.

        Useful for debugging/logging.

        Args:
            content: HTML content to analyze

        Returns:
            List of pattern strings that matched
        """
        if not content:
            return []

        matched = []
        for pattern in self._compiled_patterns:
            if pattern.search(content):
                matched.append(pattern.pattern)

        return matched


# Singleton instance
_members_only_detector: Optional[MembersOnlyDetector] = None


def get_members_only_detector() -> MembersOnlyDetector:
    """Get singleton MembersOnlyDetector instance."""
    global _members_only_detector
    if _members_only_detector is None:
        _members_only_detector = MembersOnlyDetector()
    return _members_only_detector


def reset_members_only_detector() -> None:
    """Reset singleton for testing."""
    global _members_only_detector
    _members_only_detector = None
