"""
URL configuration for Web Crawler Microservice.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from crawler.views import health_check

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),

    # Health Check Endpoint (no auth required for load balancer checks)
    # Task Group 29: Maps /api/health/ to health check view
    path("api/health/", health_check, name="health-check"),

    # Crawler API (to be implemented in later task groups)
    path("api/v1/", include("crawler.urls")),
]
