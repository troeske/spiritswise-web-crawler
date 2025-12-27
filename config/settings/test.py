"""
Test settings for Web Crawler Microservice.

Uses in-memory SQLite and eager Celery for fast test execution.
"""

import os
from .base import *

# Test mode
DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Test database - in-memory SQLite for speed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Test Cache - use local memory cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Test Celery - run tasks synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Test logging - minimal output
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["crawler"]["level"] = "WARNING"

# Password validators disabled for faster tests
AUTH_PASSWORD_VALIDATORS = []

# Use faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable Sentry in tests
SENTRY_DSN = ""

# Test crawler settings - fail fast
CRAWLER_REQUEST_TIMEOUT = 5
CRAWLER_MAX_RETRIES = 0
CRAWLER_RATE_LIMIT_DELAY = 0
