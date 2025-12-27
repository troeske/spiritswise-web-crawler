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
        - Import signal handlers
        - Perform any startup initialization
        """
        # Import signals to register handlers (when implemented)
        # from . import signals
        pass
