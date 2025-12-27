"""
Crawler URL configuration.

URL patterns for the crawler API endpoints.
"""

from django.urls import path
from . import views

app_name = "crawler"

urlpatterns = [
    path("health/", views.health_check, name="health-check"),
    # Additional endpoints will be added in later task groups
]
