"""
Crawler URL configuration.

URL patterns for the crawler API endpoints.
"""

from django.urls import path, include
from . import views

app_name = "crawler"

urlpatterns = [
    path("health/", views.health_check, name="health-check"),

    # Phase 6: REST API endpoints
    path("", include("crawler.api.urls")),
]
