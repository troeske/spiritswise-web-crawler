"""
ConfigService: Schema Builder Service for V2 Architecture.

Task 0.3.4-0.3.6: Implement ConfigService class.

Service for loading product type configuration and building extraction schemas.
Used by crawler to:
1. Load ProductTypeConfig for a product type
2. Build extraction_schema from FieldDefinitions for AI Service
3. Get QualityGateConfig for quality assessment
4. Get EnrichmentConfig templates for enrichment searches

Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 2
"""

from typing import Dict, List, Optional

from django.core.cache import cache
from django.db import models

from crawler.models import (
    ProductTypeConfig,
    FieldDefinition,
    QualityGateConfig,
    EnrichmentConfig,
)


class ConfigService:
    """
    Service for loading product type configuration and building extraction schemas.

    Used by crawler to:
    1. Load ProductTypeConfig for a product type
    2. Build extraction_schema from FieldDefinitions for AI Service
    3. Get QualityGateConfig for quality assessment
    4. Get EnrichmentConfig templates for enrichment searches

    All methods use caching to minimize database queries.
    """

    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = "config_service"

    def get_product_type_config(self, product_type: str) -> Optional[ProductTypeConfig]:
        """
        Load ProductTypeConfig by product_type string.

        Returns None if not found or inactive.
        Uses cache with 5-minute TTL.

        Args:
            product_type: Product type identifier (e.g., 'whiskey', 'port_wine')

        Returns:
            ProductTypeConfig instance or None if not found/inactive
        """
        cache_key = f"{self.CACHE_PREFIX}:product_type:{product_type}"
        config = cache.get(cache_key)

        if config is None:
            try:
                config = ProductTypeConfig.objects.get(
                    product_type=product_type,
                    is_active=True
                )
                cache.set(cache_key, config, self.CACHE_TTL)
            except ProductTypeConfig.DoesNotExist:
                return None

        return config

    def build_extraction_schema(self, product_type: str) -> List[Dict]:
        """
        Build extraction schema for AI Service from FieldDefinitions.

        Returns list of field schemas suitable for AI Service extraction request.
        Includes:
        - Shared/base fields (product_type_config=None)
        - Type-specific fields (product_type_config matches)

        Each field schema contains:
        - field_name: str
        - type: str
        - description: str
        - examples: list (optional)
        - allowed_values: list (optional)
        - item_type: str (optional, for arrays)
        - item_schema: dict (optional, for complex arrays)

        Args:
            product_type: Product type identifier (e.g., 'whiskey', 'port_wine')

        Returns:
            List of field schema dictionaries, or empty list if product type not found
        """
        cache_key = f"{self.CACHE_PREFIX}:schema:{product_type}"
        schema = cache.get(cache_key)

        if schema is not None:
            return schema

        config = self.get_product_type_config(product_type)
        if config is None:
            return []

        # Get shared fields (product_type_config=None) + type-specific fields
        fields = FieldDefinition.objects.filter(
            is_active=True
        ).filter(
            models.Q(product_type_config=None) |
            models.Q(product_type_config=config)
        ).order_by('field_group', 'sort_order', 'field_name')

        schema = []
        for field in fields:
            field_schema = field.to_extraction_schema()
            field_schema['field_name'] = field.field_name
            schema.append(field_schema)

        cache.set(cache_key, schema, self.CACHE_TTL)
        return schema

    def get_quality_gate_config(self, product_type: str) -> Optional[QualityGateConfig]:
        """
        Load QualityGateConfig for a product type.

        Args:
            product_type: Product type identifier (e.g., 'whiskey', 'port_wine')

        Returns:
            QualityGateConfig instance or None if not found
        """
        cache_key = f"{self.CACHE_PREFIX}:quality_gate:{product_type}"
        config = cache.get(cache_key)

        if config is None:
            product_config = self.get_product_type_config(product_type)
            if product_config is None:
                return None
            try:
                config = QualityGateConfig.objects.get(
                    product_type_config=product_config
                )
                cache.set(cache_key, config, self.CACHE_TTL)
            except QualityGateConfig.DoesNotExist:
                return None

        return config

    def get_enrichment_templates(self, product_type: str) -> List[EnrichmentConfig]:
        """
        Load active EnrichmentConfig templates for a product type, ordered by priority.

        Templates are returned in priority order (highest priority first) for use
        by the enrichment orchestrator.

        Args:
            product_type: Product type identifier (e.g., 'whiskey', 'port_wine')

        Returns:
            List of EnrichmentConfig instances, ordered by priority (descending)
        """
        cache_key = f"{self.CACHE_PREFIX}:enrichment:{product_type}"
        templates = cache.get(cache_key)

        if templates is None:
            product_config = self.get_product_type_config(product_type)
            if product_config is None:
                return []
            templates = list(EnrichmentConfig.objects.filter(
                product_type_config=product_config,
                is_active=True
            ).order_by('-priority'))
            cache.set(cache_key, templates, self.CACHE_TTL)

        return templates

    def invalidate_cache(self, product_type: str = None):
        """
        Invalidate cache for a product type or all product types.

        Call this when configuration is updated via Django Admin or API.

        Args:
            product_type: Product type to invalidate, or None to clear all cache
        """
        if product_type:
            keys = [
                f"{self.CACHE_PREFIX}:product_type:{product_type}",
                f"{self.CACHE_PREFIX}:schema:{product_type}",
                f"{self.CACHE_PREFIX}:quality_gate:{product_type}",
                f"{self.CACHE_PREFIX}:enrichment:{product_type}",
            ]
            cache.delete_many(keys)
        else:
            # Clear all config cache (pattern delete if supported)
            # Django's default cache may not support pattern delete,
            # so we clear the entire cache as a fallback
            cache.clear()

    def get_field_names(self, product_type: str) -> List[str]:
        """
        Get list of field names for a product type (convenience method).

        Useful for building flat field lists for AI Service requests.

        Args:
            product_type: Product type identifier

        Returns:
            List of field name strings
        """
        schema = self.build_extraction_schema(product_type)
        return [field['field_name'] for field in schema]


# Module-level singleton for convenience
_config_service = None


def get_config_service() -> ConfigService:
    """
    Get the singleton ConfigService instance.

    Returns:
        ConfigService instance
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
