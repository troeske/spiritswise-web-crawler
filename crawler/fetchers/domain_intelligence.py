"""
Domain Intelligence Store for Adaptive Site Fetching.

This module provides learning-based domain profiling to optimize
fetch strategies based on historical success/failure patterns.

Components:
- DomainProfile: Dataclass storing domain-specific metrics and settings
- DomainIntelligenceStore: Redis-backed storage for domain profiles

Usage:
    from crawler.fetchers.domain_intelligence import (
        DomainProfile,
        DomainIntelligenceStore,
    )

    store = DomainIntelligenceStore()
    profile = store.get_profile("whiskybase.com")

    # Check recommended settings
    tier = profile.recommended_tier
    timeout = profile.recommended_timeout_ms

    # Update after fetch
    profile.success_count += 1
    store.save_profile(profile)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from django.core.cache import caches

logger = logging.getLogger(__name__)


@dataclass
class DomainProfile:
    """
    Profile storing domain-specific fetch metrics and recommendations.

    This dataclass captures historical performance data for a domain,
    enabling intelligent tier selection and timeout configuration.

    Attributes:
        domain: The domain name (e.g., "whiskybase.com")
        avg_response_time_ms: Exponential moving average of response times
        timeout_count: Number of timeout failures
        success_count: Number of successful fetches
        failure_count: Number of failed fetches (non-timeout)
        tier1_success_rate: Success rate for Tier 1 (httpx) - 0.0 to 1.0
        tier2_success_rate: Success rate for Tier 2 (Playwright) - 0.0 to 1.0
        tier3_success_rate: Success rate for Tier 3 (ScrapingBee) - 0.0 to 1.0
        likely_js_heavy: Domain likely requires JavaScript rendering
        likely_bot_protected: Domain likely has bot protection
        likely_slow: Domain is typically slow to respond
        recommended_tier: Recommended starting tier (1, 2, or 3)
        recommended_timeout_ms: Recommended timeout in milliseconds
        last_updated: When the profile was last updated
        last_successful_fetch: When the last successful fetch occurred
        manual_override_tier: Force specific tier (for competition sites)
        manual_override_timeout_ms: Force specific timeout (for competition sites)
    """

    domain: str

    # Performance metrics
    avg_response_time_ms: float = 0.0
    timeout_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Tier success rates (start optimistic at 1.0)
    tier1_success_rate: float = 1.0
    tier2_success_rate: float = 1.0
    tier3_success_rate: float = 1.0

    # Behavior flags (learned from fetch patterns)
    likely_js_heavy: bool = False
    likely_bot_protected: bool = False
    likely_slow: bool = False

    # Recommended settings
    recommended_tier: int = 1
    recommended_timeout_ms: int = 20000  # 20s base

    # Timestamps
    last_updated: Optional[datetime] = None
    last_successful_fetch: Optional[datetime] = None

    # Manual overrides (for competition sites like IWSC, DWWA)
    manual_override_tier: Optional[int] = None
    manual_override_timeout_ms: Optional[int] = None

    @property
    def total_fetches(self) -> int:
        """Total number of fetch attempts."""
        return self.success_count + self.failure_count

    @property
    def overall_success_rate(self) -> float:
        """Overall success rate across all tiers."""
        total = self.total_fetches
        if total == 0:
            return 1.0  # Optimistic default for new domains
        return self.success_count / total

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert profile to dictionary.

        Handles datetime serialization to ISO format strings.

        Returns:
            Dictionary representation of the profile
        """
        data = asdict(self)

        # Convert datetimes to ISO format strings
        if self.last_updated:
            data["last_updated"] = self.last_updated.isoformat()
        if self.last_successful_fetch:
            data["last_successful_fetch"] = self.last_successful_fetch.isoformat()

        return data

    def to_json(self) -> str:
        """
        Serialize profile to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DomainProfile:
        """
        Create profile from dictionary.

        Handles datetime parsing from ISO format strings.

        Args:
            data: Dictionary with profile data

        Returns:
            DomainProfile instance
        """
        # Parse datetime strings back to datetime objects
        if data.get("last_updated") and isinstance(data["last_updated"], str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        if data.get("last_successful_fetch") and isinstance(
            data["last_successful_fetch"], str
        ):
            data["last_successful_fetch"] = datetime.fromisoformat(
                data["last_successful_fetch"]
            )

        # Filter to only known fields (ignore extra keys)
        known_fields = {
            "domain",
            "avg_response_time_ms",
            "timeout_count",
            "success_count",
            "failure_count",
            "tier1_success_rate",
            "tier2_success_rate",
            "tier3_success_rate",
            "likely_js_heavy",
            "likely_bot_protected",
            "likely_slow",
            "recommended_tier",
            "recommended_timeout_ms",
            "last_updated",
            "last_successful_fetch",
            "manual_override_tier",
            "manual_override_timeout_ms",
        }
        filtered_data = {k: v for k, v in data.items() if k in known_fields}

        return cls(**filtered_data)

    @classmethod
    def from_json(cls, json_str: str) -> DomainProfile:
        """
        Deserialize profile from JSON string.

        Args:
            json_str: JSON string representation

        Returns:
            DomainProfile instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)


class DomainIntelligenceStore:
    """
    Redis-backed storage for domain profiles.

    Uses Django's cache framework to store and retrieve domain profiles,
    enabling persistence across crawler restarts and sharing between workers.

    Attributes:
        CACHE_ALIAS: Django cache alias to use (default: "default")
        KEY_PREFIX: Prefix for cache keys
        TTL_SECONDS: Time-to-live for profiles (30 days)
    """

    CACHE_ALIAS = "default"
    KEY_PREFIX = "domain_intel:"
    TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

    def __init__(self, cache_alias: str = None):
        """
        Initialize the store.

        Args:
            cache_alias: Optional Django cache alias override
        """
        self._cache_alias = cache_alias or self.CACHE_ALIAS

    @property
    def _cache(self):
        """Get the cache backend."""
        return caches[self._cache_alias]

    def _get_cache_key(self, domain: str) -> str:
        """
        Generate cache key for a domain.

        Args:
            domain: Domain name

        Returns:
            Cache key string
        """
        # Normalize domain to lowercase
        normalized = domain.lower().strip()
        return f"{self.KEY_PREFIX}{normalized}"

    def get_profile(self, domain: str) -> DomainProfile:
        """
        Get profile for a domain.

        Returns existing profile from cache or creates a new one
        with default values if not found.

        Args:
            domain: Domain name to look up

        Returns:
            DomainProfile for the domain
        """
        key = self._get_cache_key(domain)

        try:
            cached = self._cache.get(key)
            if cached:
                return DomainProfile.from_json(cached)
        except Exception as e:
            logger.warning(
                "Failed to get domain profile from cache for %s: %s", domain, str(e)
            )

        # Return new profile with defaults
        return DomainProfile(domain=domain.lower().strip())

    def save_profile(self, profile: DomainProfile) -> bool:
        """
        Save profile to cache.

        Args:
            profile: DomainProfile to save

        Returns:
            True if saved successfully, False otherwise
        """
        key = self._get_cache_key(profile.domain)

        # Update last_updated timestamp
        profile.last_updated = datetime.now(timezone.utc)

        try:
            self._cache.set(key, profile.to_json(), timeout=self.TTL_SECONDS)
            logger.debug("Saved domain profile for %s", profile.domain)
            return True
        except Exception as e:
            logger.error(
                "Failed to save domain profile for %s: %s", profile.domain, str(e)
            )
            return False

    def delete_profile(self, domain: str) -> bool:
        """
        Delete profile from cache.

        Args:
            domain: Domain name to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        key = self._get_cache_key(domain)

        try:
            self._cache.delete(key)
            logger.debug("Deleted domain profile for %s", domain)
            return True
        except Exception as e:
            logger.error(
                "Failed to delete domain profile for %s: %s", domain, str(e)
            )
            return False
