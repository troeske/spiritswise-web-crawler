"""
Spoke Registry - Validates and registers discovered producer sources.

Handles:
- Domain validation (reachability check)
- CrawlerSource creation with discovery_method='hub'
- Duplicate detection and prevention
- Default crawl configuration
"""

import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from django.db import transaction
from django.utils.text import slugify

from crawler.models import (
    CrawlerSource,
    DiscoveryMethod,
    SourceCategory,
    AgeGateType,
)

logger = logging.getLogger(__name__)


class SpokeRegistry:
    """
    Registry for discovered spoke (producer) sources.

    Validates discovered domains and creates CrawlerSource records
    with appropriate configuration for hub-discovered sources.
    """

    # Default configuration for hub-discovered sources
    DEFAULT_CONFIG = {
        "category": SourceCategory.PRODUCER,
        "is_active": True,
        "priority": 5,  # Medium priority for new discoveries
        "crawl_frequency_hours": 168,  # Weekly
        "rate_limit_requests_per_minute": 5,  # Conservative for new sources
        "requires_javascript": False,
        "requires_proxy": False,
        "age_gate_type": AgeGateType.NONE,
        "robots_txt_compliant": True,
        "tos_compliant": True,
    }

    def __init__(
        self,
        validate_domains: bool = True,
        timeout: float = 10.0,
    ):
        """
        Initialize spoke registry.

        Args:
            validate_domains: Whether to check domain reachability
            timeout: Timeout for validation requests
        """
        self.validate_domains = validate_domains
        self.timeout = timeout

    def register_spoke(
        self,
        name: str,
        base_url: str,
        discovered_from_hub: str,
        product_types: Optional[list] = None,
        skip_validation: bool = False,
    ) -> Optional[CrawlerSource]:
        """
        Register a discovered spoke (producer) source.

        Args:
            name: Brand/producer name
            base_url: Official website URL
            discovered_from_hub: Domain of the hub that discovered this source
            product_types: List of product types (defaults to ['whiskey'])
            skip_validation: Skip domain validation check

        Returns:
            CrawlerSource instance, or None if validation failed
        """
        # Normalize URL
        base_url = self._normalize_url(base_url)

        # Check for existing source
        existing = self._find_existing_source(base_url)
        if existing:
            logger.info(f"Source already exists for {base_url}: {existing.name}")
            return existing

        # Validate domain if enabled
        if self.validate_domains and not skip_validation:
            if not self._validate_domain(base_url):
                logger.warning(f"Domain validation failed for {base_url}")
                return None

        # Create the source
        return self._create_source(
            name=name,
            base_url=base_url,
            discovered_from_hub=discovered_from_hub,
            product_types=product_types or ["whiskey"],
        )

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to consistent format."""
        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Parse and reconstruct
        parsed = urlparse(url)

        # Ensure trailing slash on base URL
        path = parsed.path
        if not path or path == "/":
            path = "/"

        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _find_existing_source(self, base_url: str) -> Optional[CrawlerSource]:
        """Check if a source already exists for this domain."""
        parsed = urlparse(base_url)
        domain = parsed.netloc.replace("www.", "")

        # Check for exact match or domain match
        try:
            return CrawlerSource.objects.filter(
                base_url__icontains=domain
            ).first()
        except Exception as e:
            logger.warning(f"Error checking for existing source: {e}")
            return None

    def _validate_domain(self, url: str) -> bool:
        """Validate that the domain is reachable."""
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.head(url)
                return response.status_code < 500
        except httpx.TimeoutException:
            logger.debug(f"Timeout validating {url}")
            return False
        except Exception as e:
            logger.debug(f"Validation failed for {url}: {e}")
            return False

    def _create_source(
        self,
        name: str,
        base_url: str,
        discovered_from_hub: str,
        product_types: list,
    ) -> CrawlerSource:
        """Create a new CrawlerSource for the discovered spoke."""
        # Generate unique slug
        slug = self._generate_unique_slug(name)

        # Build notes
        notes = f"Discovered via hub: {discovered_from_hub}"

        with transaction.atomic():
            source = CrawlerSource.objects.create(
                name=name,
                slug=slug,
                base_url=base_url,
                product_types=product_types,
                discovery_method=DiscoveryMethod.HUB,
                notes=notes,
                **self.DEFAULT_CONFIG,
            )

        logger.info(
            f"Created CrawlerSource '{name}' ({base_url}) "
            f"from hub {discovered_from_hub}"
        )
        return source

    def _generate_unique_slug(self, name: str) -> str:
        """Generate a unique slug for the source."""
        base_slug = slugify(name)
        slug = base_slug
        counter = 1

        while CrawlerSource.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    async def register_spoke_async(
        self,
        name: str,
        base_url: str,
        discovered_from_hub: str,
        product_types: Optional[list] = None,
        skip_validation: bool = False,
    ) -> Optional[CrawlerSource]:
        """
        Async version of register_spoke.

        Args:
            name: Brand/producer name
            base_url: Official website URL
            discovered_from_hub: Domain of the hub that discovered this source
            product_types: List of product types (defaults to ['whiskey'])
            skip_validation: Skip domain validation check

        Returns:
            CrawlerSource instance, or None if validation failed
        """
        from asgiref.sync import sync_to_async

        # Normalize URL
        base_url = self._normalize_url(base_url)

        # Check for existing source
        existing = await sync_to_async(self._find_existing_source)(base_url)
        if existing:
            logger.info(f"Source already exists for {base_url}: {existing.name}")
            return existing

        # Validate domain if enabled
        if self.validate_domains and not skip_validation:
            is_valid = await self._validate_domain_async(base_url)
            if not is_valid:
                logger.warning(f"Domain validation failed for {base_url}")
                return None

        # Create the source
        return await sync_to_async(self._create_source)(
            name=name,
            base_url=base_url,
            discovered_from_hub=discovered_from_hub,
            product_types=product_types or ["whiskey"],
        )

    async def _validate_domain_async(self, url: str) -> bool:
        """Async version of domain validation."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.head(url)
                return response.status_code < 500
        except httpx.TimeoutException:
            logger.debug(f"Timeout validating {url}")
            return False
        except Exception as e:
            logger.debug(f"Validation failed for {url}: {e}")
            return False
