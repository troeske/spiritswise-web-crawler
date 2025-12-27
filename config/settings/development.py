"""
Development settings for Web Crawler Microservice.

Uses local PostgreSQL/SQLite, Redis, and relaxed security settings for development.
"""

import os
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Development database - SQLite for simplicity (switch to PostgreSQL for shared DB testing)
# For shared database testing with AI Enhancement Service, use PostgreSQL config below
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Uncomment below for shared PostgreSQL database testing
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("DB_NAME", "spiritswise"),
#         "USER": os.getenv("DB_USER", "postgres"),
#         "PASSWORD": os.getenv("DB_PASSWORD", ""),
#         "HOST": os.getenv("DB_HOST", "localhost"),
#         "PORT": os.getenv("DB_PORT", "5432"),
#     }
# }

# Development Cache - use database cache (no Redis needed for local dev)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
    }
}

# Development Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Development logging - verbose output
LOGGING["loggers"]["django"]["level"] = "DEBUG"
LOGGING["loggers"]["crawler"]["level"] = "DEBUG"

# Email backend for development - console output
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Development-specific settings
INTERNAL_IPS = ["127.0.0.1"]

# Less strict password validators for development
AUTH_PASSWORD_VALIDATORS = []

# Relaxed crawler settings for development
CRAWLER_REQUEST_TIMEOUT = 60  # More time for debugging
CRAWLER_MAX_RETRIES = 1  # Fail fast in development
CRAWLER_RATE_LIMIT_DELAY = 0.5  # Faster crawling for testing
