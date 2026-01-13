"""
Migration helper functions for crawler models.

This module contains data migration functions that can be used by Django migrations
or called directly for data transformations.
"""

import logging

logger = logging.getLogger(__name__)


def migrate_pipeline_config_data():
    """
    Migrate data from PipelineConfig to ProductTypeConfig.

    This function copies V3 fields from PipelineConfig to the parent ProductTypeConfig,
    as part of the config consolidation effort (Task 0.2).

    Fields migrated:
    - max_serpapi_searches
    - max_sources_per_product
    - max_enrichment_time_seconds
    - awards_search_enabled
    - awards_search_template
    - members_only_detection_enabled
    - members_only_patterns
    - status_thresholds
    - ecp_complete_threshold

    The PipelineConfig values always override ProductTypeConfig values.
    """
    # Import here to avoid circular imports during migrations
    from crawler.models import PipelineConfig, ProductTypeConfig

    migrated_count = 0

    for pipeline_config in PipelineConfig.objects.select_related("product_type_config").all():
        ptc = pipeline_config.product_type_config

        # Copy all V3 fields from PipelineConfig to ProductTypeConfig
        ptc.max_serpapi_searches = pipeline_config.max_serpapi_searches
        ptc.max_sources_per_product = pipeline_config.max_sources_per_product
        ptc.max_enrichment_time_seconds = pipeline_config.max_enrichment_time_seconds
        ptc.awards_search_enabled = pipeline_config.awards_search_enabled
        ptc.awards_search_template = pipeline_config.awards_search_template
        ptc.members_only_detection_enabled = pipeline_config.members_only_detection_enabled
        ptc.members_only_patterns = pipeline_config.members_only_patterns
        ptc.status_thresholds = pipeline_config.status_thresholds
        ptc.ecp_complete_threshold = pipeline_config.ecp_complete_threshold

        ptc.save()
        migrated_count += 1

        logger.info(
            "Migrated PipelineConfig to ProductTypeConfig: %s",
            ptc.product_type,
        )

    logger.info("Migrated %d PipelineConfig records to ProductTypeConfig", migrated_count)
    return migrated_count


def migrate_pipeline_config_data_for_migration(apps, schema_editor):
    """
    Django migration-compatible version of migrate_pipeline_config_data.

    This version uses the historical model state from apps.get_model()
    to ensure compatibility with the migration framework.
    """
    PipelineConfig = apps.get_model("crawler", "PipelineConfig")
    ProductTypeConfig = apps.get_model("crawler", "ProductTypeConfig")

    migrated_count = 0

    for pipeline_config in PipelineConfig.objects.select_related("product_type_config").all():
        ptc = pipeline_config.product_type_config

        # Copy all V3 fields from PipelineConfig to ProductTypeConfig
        ptc.max_serpapi_searches = pipeline_config.max_serpapi_searches
        ptc.max_sources_per_product = pipeline_config.max_sources_per_product
        ptc.max_enrichment_time_seconds = pipeline_config.max_enrichment_time_seconds
        ptc.awards_search_enabled = pipeline_config.awards_search_enabled
        ptc.awards_search_template = pipeline_config.awards_search_template
        ptc.members_only_detection_enabled = pipeline_config.members_only_detection_enabled
        ptc.members_only_patterns = pipeline_config.members_only_patterns
        ptc.status_thresholds = pipeline_config.status_thresholds
        ptc.ecp_complete_threshold = pipeline_config.ecp_complete_threshold

        ptc.save()
        migrated_count += 1

    print(f"Migrated {migrated_count} PipelineConfig records to ProductTypeConfig")
    return migrated_count
