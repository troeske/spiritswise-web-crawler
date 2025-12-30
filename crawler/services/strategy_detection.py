"""
Strategy Detection Service for Crawl Strategy Auto-Detection.

Task Group 30: Implements obstacle detection patterns and escalation workflow
for automatically determining the best crawl strategy for a given source.

Features:
- Age gate detection (keywords, button patterns)
- JS-rendered content detection (content length, missing elements)
- Cookie consent detection (GDPR, consent keywords)
- CAPTCHA detection (reCAPTCHA scripts, challenge forms)
- Rate limiting detection (HTTP 429, IP block messages)
- Geo-blocking detection (HTTP 403 with geo keywords)
- Escalation workflow (simple -> js_render -> stealth -> manual)
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from crawler.models import (
    DiscoverySourceConfig,
    CrawlStrategyChoices,
)
from crawler.services.scrapingbee_client import ScrapingBeeClient, ScrapingBeeMode

logger = logging.getLogger(__name__)


class ObstacleType(Enum):
    """
    Types of obstacles that can be detected during crawling.

    Each type maps to potential escalation strategies.
    """

    AGE_GATE = "age_gate"
    JS_RENDERED = "js_rendered"
    COOKIE_CONSENT = "cookie_consent"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    GEO_BLOCKED = "geo_blocked"


@dataclass
class DetectedObstacle:
    """
    Represents a detected obstacle during crawling.

    Attributes:
        obstacle_type: Type of obstacle detected
        detected_pattern: The pattern or text that triggered detection
        confidence: Confidence score (0.0-1.0) of the detection
        details: Additional details about the obstacle
    """

    obstacle_type: ObstacleType
    detected_pattern: str
    confidence: float = 1.0
    details: Optional[Dict[str, Any]] = None


# Detection patterns for various obstacles
AGE_GATE_PATTERNS = [
    r"verify\s+your\s+age",
    r"(?:are\s+you\s+)?(?:of\s+)?legal\s+drinking\s+age",
    r"\b21\s*\+",
    r"21\s+(?:years?\s+)?(?:or\s+)?old(?:er)?",
    r"(?:i\s+am\s+)?(?:over\s+)?(?:18|19|20|21)\s+years?\s+old",
    r"age\s*(?:-|\s)?\s*gate",
    r"age\s*(?:-|\s)?\s*verification",
    r"enter\s+(?:your\s+)?(?:date\s+of\s+)?birth",
    r"confirm\s+(?:your\s+)?age",
]

CAPTCHA_PATTERNS = [
    r"\bcaptcha\b",
    r"\brecaptcha\b",
    r"g-recaptcha",
    r"hcaptcha",
    r"challenge[\s-]?form",
    r"google\.com/recaptcha",
    r"cloudflare.*challenge",
]

COOKIE_CONSENT_PATTERNS = [
    r"\bcookie\s*(?:consent|policy|notice)\b",
    r"\bgdpr\b",
    r"accept\s+(?:all\s+)?cookies",
    r"cookie\s+preferences",
    r"privacy\s+(?:consent|settings)",
]

RATE_LIMIT_PATTERNS = [
    r"too\s+many\s+requests",
    r"rate\s+limit(?:ed)?",
    r"slow\s+down",
    r"try\s+again\s+later",
    r"(?:ip|access)\s+blocked",
]

GEO_BLOCK_PATTERNS = [
    r"not\s+available\s+in\s+your\s+(?:region|country|location)",
    r"geo[\s-]?(?:blocked|restricted)",
    r"content\s+unavailable",
    r"access\s+denied.*(?:region|location)",
    r"restricted\s+(?:in\s+)?your\s+(?:region|country)",
]

# Threshold for JS-rendered content detection
JS_RENDER_CONTENT_LENGTH_THRESHOLD = 500


def detect_obstacles(
    html_content: str,
    status_code: int = 200,
    expected_elements: Optional[List[str]] = None,
) -> List[DetectedObstacle]:
    """
    Detect obstacles in the crawled HTML content.

    Args:
        html_content: The HTML content returned from the crawl
        status_code: HTTP status code of the response
        expected_elements: List of expected element IDs/classes to check for

    Returns:
        List of DetectedObstacle objects representing found obstacles
    """
    obstacles: List[DetectedObstacle] = []
    content_lower = html_content.lower()

    # Check HTTP status codes first
    if status_code == 429:
        obstacles.append(
            DetectedObstacle(
                obstacle_type=ObstacleType.RATE_LIMITED,
                detected_pattern="HTTP 429 Too Many Requests",
                confidence=1.0,
            )
        )

    if status_code == 403:
        # Check for geo-blocking patterns
        for pattern in GEO_BLOCK_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                obstacles.append(
                    DetectedObstacle(
                        obstacle_type=ObstacleType.GEO_BLOCKED,
                        detected_pattern=pattern,
                        confidence=0.9,
                    )
                )
                break
        else:
            # Generic 403 might still be geo-blocking
            obstacles.append(
                DetectedObstacle(
                    obstacle_type=ObstacleType.GEO_BLOCKED,
                    detected_pattern="HTTP 403 Forbidden",
                    confidence=0.7,
                )
            )

    # Check for age gate patterns
    for pattern in AGE_GATE_PATTERNS:
        match = re.search(pattern, content_lower, re.IGNORECASE)
        if match:
            obstacles.append(
                DetectedObstacle(
                    obstacle_type=ObstacleType.AGE_GATE,
                    detected_pattern=match.group(0),
                    confidence=0.9,
                    details={"pattern": pattern},
                )
            )
            break

    # Check for CAPTCHA patterns
    for pattern in CAPTCHA_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            obstacles.append(
                DetectedObstacle(
                    obstacle_type=ObstacleType.CAPTCHA,
                    detected_pattern=pattern,
                    confidence=0.95,
                )
            )
            break

    # Check for cookie consent patterns
    for pattern in COOKIE_CONSENT_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            obstacles.append(
                DetectedObstacle(
                    obstacle_type=ObstacleType.COOKIE_CONSENT,
                    detected_pattern=pattern,
                    confidence=0.8,
                )
            )
            break

    # Check for rate limit patterns in content
    if status_code != 429:
        for pattern in RATE_LIMIT_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                obstacles.append(
                    DetectedObstacle(
                        obstacle_type=ObstacleType.RATE_LIMITED,
                        detected_pattern=pattern,
                        confidence=0.85,
                    )
                )
                break

    # Check for JS-rendered content
    content_length = len(html_content.strip())
    is_short_content = content_length < JS_RENDER_CONTENT_LENGTH_THRESHOLD

    # Check for missing expected elements
    missing_elements = []
    if expected_elements:
        for element in expected_elements:
            # Check for both class and id patterns
            if element not in content_lower:
                missing_elements.append(element)

    if is_short_content or (expected_elements and len(missing_elements) == len(expected_elements)):
        obstacles.append(
            DetectedObstacle(
                obstacle_type=ObstacleType.JS_RENDERED,
                detected_pattern=f"Content length: {content_length}",
                confidence=0.8 if is_short_content else 0.7,
                details={
                    "content_length": content_length,
                    "missing_elements": missing_elements,
                    "threshold": JS_RENDER_CONTENT_LENGTH_THRESHOLD,
                },
            )
        )

    return obstacles


@dataclass
class EscalationResult:
    """
    Result of a strategy escalation attempt.

    Attributes:
        success: Whether the crawl was successful
        content: The fetched content (if successful)
        final_strategy: The strategy that succeeded
        escalation_steps: Number of escalation steps taken
        detected_obstacles: All obstacles detected during escalation
        error: Error message (if failed)
    """

    success: bool
    content: Optional[str] = None
    final_strategy: Optional[str] = None
    escalation_steps: int = 0
    detected_obstacles: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class StrategyEscalationService:
    """
    Service for managing crawl strategy escalation.

    Implements the escalation workflow:
    1. simple: Basic HTTP fetch
    2. js_render: ScrapingBee with JavaScript rendering
    3. stealth: ScrapingBee stealth + premium proxies
    4. manual: Flag for admin review

    On success, updates the DiscoverySourceConfig.crawl_strategy.
    """

    # Escalation step mapping
    ESCALATION_STEPS = {
        1: CrawlStrategyChoices.SIMPLE,
        2: CrawlStrategyChoices.JS_RENDER,
        3: CrawlStrategyChoices.STEALTH,
        4: CrawlStrategyChoices.MANUAL,
    }

    def __init__(self, scrapingbee_api_key: Optional[str] = None):
        """
        Initialize the escalation service.

        Args:
            scrapingbee_api_key: API key for ScrapingBee (optional for testing)
        """
        self.scrapingbee_api_key = scrapingbee_api_key
        self._client: Optional[ScrapingBeeClient] = None

    @property
    def client(self) -> ScrapingBeeClient:
        """Lazy initialization of ScrapingBee client."""
        if self._client is None:
            self._client = ScrapingBeeClient(api_key=self.scrapingbee_api_key or "")
        return self._client

    def get_strategy_for_step(self, step: int) -> str:
        """
        Get the crawl strategy for a given escalation step.

        Args:
            step: Escalation step number (1-4)

        Returns:
            CrawlStrategy value for the step
        """
        return self.ESCALATION_STEPS.get(step, CrawlStrategyChoices.MANUAL)

    def _is_content_valid(
        self,
        content: str,
        status_code: int,
        expected_elements: Optional[List[str]] = None,
    ) -> bool:
        """
        Check if the crawled content is valid (no blocking obstacles).

        Args:
            content: The HTML content
            status_code: HTTP status code
            expected_elements: List of expected elements

        Returns:
            True if content is valid, False otherwise
        """
        obstacles = detect_obstacles(content, status_code, expected_elements)

        # Filter out minor obstacles (cookie consent is acceptable)
        blocking_obstacles = [
            o for o in obstacles
            if o.obstacle_type not in [ObstacleType.COOKIE_CONSENT]
        ]

        return len(blocking_obstacles) == 0

    def escalate_and_crawl(
        self,
        url: str,
        source: Optional[DiscoverySourceConfig] = None,
        expected_elements: Optional[List[str]] = None,
        max_steps: int = 4,
    ) -> EscalationResult:
        """
        Attempt to crawl a URL with automatic strategy escalation.

        Args:
            url: URL to crawl
            source: Optional DiscoverySourceConfig to update on success
            expected_elements: Elements to check for valid content
            max_steps: Maximum escalation steps (default 4)

        Returns:
            EscalationResult with crawl outcome
        """
        all_obstacles: List[Dict[str, Any]] = []

        for step in range(1, max_steps + 1):
            strategy = self.get_strategy_for_step(step)
            logger.info(f"Escalation step {step}: Trying strategy '{strategy}' for {url}")

            if strategy == CrawlStrategyChoices.MANUAL:
                # Cannot auto-crawl with manual strategy
                logger.warning(f"Escalation reached manual step for {url}")
                return EscalationResult(
                    success=False,
                    escalation_steps=step,
                    detected_obstacles=all_obstacles,
                    error="Escalation exhausted, manual intervention required",
                )

            try:
                result = self._attempt_crawl(url, strategy)

                if result.get("success"):
                    content = result.get("content", "")
                    status_code = result.get("status_code", 200)

                    # Detect obstacles in the result
                    obstacles = detect_obstacles(content, status_code, expected_elements)

                    # Log obstacles
                    for obstacle in obstacles:
                        all_obstacles.append({
                            "step": step,
                            "strategy": strategy,
                            "type": obstacle.obstacle_type.value,
                            "pattern": obstacle.detected_pattern,
                            "confidence": obstacle.confidence,
                        })

                    # Check if content is valid
                    if self._is_content_valid(content, status_code, expected_elements):
                        # Success - update source strategy if provided
                        if source:
                            self._update_source_strategy(source, strategy, all_obstacles)

                        logger.info(
                            f"Crawl successful with strategy '{strategy}' after {step} step(s)"
                        )
                        return EscalationResult(
                            success=True,
                            content=content,
                            final_strategy=strategy,
                            escalation_steps=step,
                            detected_obstacles=all_obstacles,
                        )

                    # Content not valid, continue escalation
                    logger.info(
                        f"Strategy '{strategy}' returned content but obstacles detected, escalating"
                    )

            except Exception as e:
                logger.error(f"Error during crawl attempt with strategy '{strategy}': {e}")
                all_obstacles.append({
                    "step": step,
                    "strategy": strategy,
                    "type": "error",
                    "pattern": str(e),
                    "confidence": 1.0,
                })

        # All steps exhausted
        return EscalationResult(
            success=False,
            escalation_steps=max_steps,
            detected_obstacles=all_obstacles,
            error="All escalation strategies exhausted",
        )

    def _attempt_crawl(self, url: str, strategy: str) -> Dict[str, Any]:
        """
        Attempt to crawl a URL with a specific strategy.

        Args:
            url: URL to crawl
            strategy: Crawl strategy to use

        Returns:
            Dict with success, content, and status_code
        """
        if strategy == CrawlStrategyChoices.SIMPLE:
            return self._simple_crawl(url)
        elif strategy == CrawlStrategyChoices.JS_RENDER:
            return self.client.fetch(url, mode=ScrapingBeeMode.JS_RENDER)
        elif strategy == CrawlStrategyChoices.STEALTH:
            return self.client.fetch(url, mode=ScrapingBeeMode.STEALTH)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _simple_crawl(self, url: str) -> Dict[str, Any]:
        """
        Perform a simple HTTP crawl without ScrapingBee.

        Args:
            url: URL to crawl

        Returns:
            Dict with success, content, and status_code
        """
        import requests

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            response = requests.get(url, headers=headers, timeout=30)

            return {
                "success": True,
                "content": response.text,
                "status_code": response.status_code,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "content": "",
                "status_code": 0,
                "error": str(e),
            }

    def _update_source_strategy(
        self,
        source: DiscoverySourceConfig,
        strategy: str,
        obstacles: List[Dict[str, Any]],
    ) -> None:
        """
        Update the source configuration with successful strategy.

        Args:
            source: DiscoverySourceConfig to update
            strategy: Strategy that succeeded
            obstacles: Obstacles detected during escalation
        """
        source.crawl_strategy = strategy
        source.detected_obstacles = obstacles
        source.save(update_fields=["crawl_strategy", "detected_obstacles"])

        logger.info(
            f"Updated source '{source.name}' crawl_strategy to '{strategy}'"
        )
