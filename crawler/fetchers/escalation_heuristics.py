"""
Escalation Heuristics for Adaptive Tier Selection.

This module provides heuristics for detecting when to escalate from a lower
fetching tier to a higher tier based on response characteristics.

Tier Overview:
- Tier 1: httpx (fast, lightweight)
- Tier 2: Playwright (JavaScript rendering)
- Tier 3: ScrapingBee (cloud browser, IP rotation, bot protection bypass)

Escalation Triggers:
- HTTP 403/429 status codes
- Cloudflare/CAPTCHA challenge pages
- JavaScript placeholder content
- Low historical success rate for the domain/tier
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crawler.fetchers.domain_intelligence import DomainProfile

logger = logging.getLogger(__name__)


@dataclass
class EscalationResult:
    """Result of escalation check."""

    should_escalate: bool
    reason: Optional[str] = None
    recommended_tier: Optional[int] = None


class EscalationHeuristics:
    """
    Heuristics for determining when to escalate to a higher fetch tier.

    Uses a combination of:
    - HTTP status codes (403, 429, etc.)
    - Content analysis (Cloudflare, CAPTCHA, JS placeholders)
    - Historical domain performance (success rates)
    """

    # Escalate if tier success rate below this threshold
    SUCCESS_RATE_THRESHOLD = 0.50  # 50%

    # Minimum content length for valid page (excludes HTML boilerplate)
    MIN_CONTENT_LENGTH = 200

    # Status codes that trigger immediate escalation
    ESCALATION_STATUS_CODES = {403, 429, 503}

    @classmethod
    def should_escalate(
        cls,
        status_code: int,
        content: str,
        domain_profile: "DomainProfile",
        current_tier: int,
    ) -> EscalationResult:
        """
        Determine if we should escalate to the next tier.

        Args:
            status_code: HTTP response status code
            content: Response body content
            domain_profile: Domain's historical performance profile
            current_tier: Current fetch tier (1, 2, or 3)

        Returns:
            EscalationResult with should_escalate flag and reason
        """
        # Can't escalate beyond tier 3
        if current_tier >= 3:
            return EscalationResult(should_escalate=False)

        # Check status code escalation
        if status_code in cls.ESCALATION_STATUS_CODES:
            return EscalationResult(
                should_escalate=True,
                reason=f"HTTP {status_code} status code",
                recommended_tier=current_tier + 1,
            )

        # Check content-based escalation (only for 200 responses)
        if status_code == 200:
            # Cloudflare challenge
            if cls.is_cloudflare_challenge(content):
                return EscalationResult(
                    should_escalate=True,
                    reason="Cloudflare challenge detected",
                    recommended_tier=current_tier + 1,
                )

            # CAPTCHA page
            if cls.is_captcha_page(content):
                return EscalationResult(
                    should_escalate=True,
                    reason="CAPTCHA challenge detected",
                    recommended_tier=current_tier + 1,
                )

            # JavaScript placeholder
            if cls.is_javascript_placeholder(content):
                return EscalationResult(
                    should_escalate=True,
                    reason="JavaScript placeholder page - requires JS rendering",
                    recommended_tier=current_tier + 1,
                )

            # Empty or loading page
            if cls.is_empty_or_loading(content):
                return EscalationResult(
                    should_escalate=True,
                    reason="Empty or loading page detected",
                    recommended_tier=current_tier + 1,
                )

        # Check historical success rate for this tier
        tier_success_rate = cls._get_tier_success_rate(domain_profile, current_tier)
        if tier_success_rate < cls.SUCCESS_RATE_THRESHOLD:
            return EscalationResult(
                should_escalate=True,
                reason=f"Low success rate for tier {current_tier}: {tier_success_rate:.0%}",
                recommended_tier=current_tier + 1,
            )

        # No escalation needed
        return EscalationResult(should_escalate=False)

    @classmethod
    def _get_tier_success_rate(
        cls, domain_profile: "DomainProfile", tier: int
    ) -> float:
        """Get success rate for a specific tier from domain profile."""
        if tier == 1:
            return domain_profile.tier1_success_rate
        elif tier == 2:
            return domain_profile.tier2_success_rate
        elif tier == 3:
            return domain_profile.tier3_success_rate
        return 1.0  # Default optimistic

    @staticmethod
    def is_cloudflare_challenge(content: str) -> bool:
        """
        Detect Cloudflare challenge pages.

        Cloudflare challenges typically include:
        - "Checking your browser" message
        - "Just a moment..." title
        - cf_chl challenge tokens

        Note: We only consider it a challenge if the content is short (< 50KB).
        Legitimate pages often have "cloudflare ray id" in footers but have
        substantial content. A real challenge page is typically under 10KB.
        """
        # Large pages with actual content aren't Cloudflare challenges
        # (they may just be hosted behind Cloudflare and show ray ID in footer)
        if len(content) > 50000:  # 50KB threshold
            return False

        content_lower = content.lower()

        # High-confidence patterns (definitely a challenge)
        challenge_patterns = [
            "checking your browser",
            "just a moment...",
            "cf_chl_opt",
            "cf_chl_prog",
            "cf-browser-verification",
            "challenge-platform",
            "__cf_chl_tk",
        ]

        for pattern in challenge_patterns:
            if pattern in content_lower:
                return True

        # Lower-confidence pattern: only flag if content is very short
        # (under 10KB, which is typical for challenge pages)
        if len(content) < 10000 and "cloudflare ray id" in content_lower:
            # Additional check: real challenge pages have minimal text content
            import re
            text_content = re.sub(r"<[^>]+>", "", content).strip()
            if len(text_content) < 1000:  # Very sparse text
                return True

        return False

    @staticmethod
    def is_captcha_page(content: str) -> bool:
        """
        Detect CAPTCHA challenge pages.

        Checks for:
        - Google reCAPTCHA
        - hCaptcha
        - Generic captcha form fields
        """
        content_lower = content.lower()

        captcha_patterns = [
            "g-recaptcha",
            "h-captcha",
            "recaptcha/api",
            "hcaptcha.com",
            'name="captcha',
            "captcha_token",
            "captcha-challenge",
            "data-sitekey",
        ]

        for pattern in captcha_patterns:
            if pattern in content_lower:
                return True

        return False

    @staticmethod
    def is_javascript_placeholder(content: str) -> bool:
        """
        Detect JavaScript framework placeholder pages.

        These are pages that rely entirely on client-side rendering
        and show empty shells without JavaScript execution.

        Detects:
        - React empty root div
        - Vue empty app div
        - Angular app-root element
        - Noscript messages requiring JS
        """
        content_lower = content.lower()

        # Check for common SPA patterns
        spa_patterns = [
            # React
            '<div id="root"></div>',
            '<div id="__next"></div>',
            # Vue
            '<div id="app"></div>',
            # Angular
            "<app-root></app-root>",
            "<app-root>",
        ]

        for pattern in spa_patterns:
            if pattern in content_lower:
                # Check if the div is actually empty (no content after it before closing)
                # This differentiates between placeholder and rendered content
                pattern_idx = content_lower.find(pattern)
                if pattern_idx != -1:
                    # Look for meaningful content after the placeholder
                    after_pattern = content[pattern_idx + len(pattern) :].strip()
                    # If there's minimal content after the pattern, it's a placeholder
                    stripped = re.sub(r"<[^>]+>", "", after_pattern).strip()
                    if len(stripped) < 100:  # Less than 100 chars of actual text
                        return True

        # Check for noscript messages
        noscript_patterns = [
            "you need to enable javascript",
            "please enable javascript",
            "javascript is required",
            "this app requires javascript",
        ]

        for pattern in noscript_patterns:
            if pattern in content_lower:
                return True

        return False

    @staticmethod
    def is_empty_or_loading(content: str) -> bool:
        """
        Detect empty or loading pages.

        Better than simple character count - looks for actual content
        vs HTML boilerplate.
        """
        # Strip HTML tags to get text content
        text_content = re.sub(r"<[^>]+>", "", content).strip()
        text_content = re.sub(r"\s+", " ", text_content)  # Normalize whitespace

        # Check for loading indicators
        loading_patterns = [
            "loading...",
            "please wait",
            "loading-spinner",
            "loading-indicator",
        ]

        content_lower = content.lower()
        for pattern in loading_patterns:
            if pattern in content_lower:
                # If loading pattern is present and content is sparse
                if len(text_content) < 200:
                    return True

        # Very short content is likely empty/loading
        if len(text_content) < 50:
            return True

        return False
