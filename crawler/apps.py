"""
Crawler application configuration.
"""

from django.apps import AppConfig


class CrawlerConfig(AppConfig):
    """Configuration for the crawler Django application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "crawler"
    verbose_name = "Web Crawler"

    def ready(self):
        """
        Perform application initialization.

        This method is called when Django starts. It's used to:
        - Import signal handlers to register them

        Signals include:
        - Task Group 4: Related Data Tables counter updates
        - Task Group 7: Junction Tables mention count updates
        - Task Group 19: Completeness scoring auto-recalculation
        - Task Group 21: ProductAvailability aggregation updates

        NOTE: Signals are currently disabled because they reference models
        from future task groups (ProductAward, BrandAward, etc.) that
        don't exist yet. They will be enabled when those models are created.
        """
        # Import signals to register handlers
        # NOTE: Disabled until dependent models are created (Task Groups 4, 7)
        # from crawler import signals  # noqa: F401
        pass
