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
        - Task Group 4: Related Data Tables counter updates (ProductAward, BrandAward, etc.)
        - RECT-004: ProductAward counter updates
        - RECT-005: ProductSource junction table mention count updates
        - Task Group 19: Completeness scoring auto-recalculation (planned)
        - Task Group 21: ProductAvailability aggregation updates
        """
        # Import signals to register handlers
        from crawler import signals  # noqa: F401
