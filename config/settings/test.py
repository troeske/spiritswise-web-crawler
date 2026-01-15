"""
Test settings for Web Crawler Microservice.

Uses in-memory SQLite and eager Celery for fast test execution.
"""

import os
from .base import *

# Test mode
DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Test database - file-based SQLite for async compatibility
# Note: In-memory SQLite creates separate DBs per thread connection,
# which breaks async tests using sync_to_async
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
        "TEST": {
            "NAME": BASE_DIR / "test_db.sqlite3",
        },
        "OPTIONS": {
            "timeout": 60,  # Longer timeout for concurrent access
            "check_same_thread": False,  # Allow cross-thread access for async
        },
    }
}

# Configure SQLite to use WAL mode for better concurrency
# This is set via connection signal handler
from django.db.backends.signals import connection_created
def set_sqlite_wal_mode(sender, connection, **kwargs):
    """Set SQLite WAL mode on each connection for better concurrent access."""
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=60000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

connection_created.connect(set_sqlite_wal_mode)

# Test Cache - Use Redis for E2E tests (real domain intelligence tracking)
# Falls back to local memory cache if Redis not available
import redis as redis_lib
_redis_available = False
try:
    _test_redis = redis_lib.Redis(host='localhost', port=6379, db=3)
    _test_redis.ping()
    _redis_available = True
    _test_redis.close()
except Exception:
    pass

if _redis_available:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://localhost:6379/3",  # Use DB 3 for tests
        }
    }
else:
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

# Test crawler settings
# Note: E2E tests require longer timeouts for real network calls
CRAWLER_REQUEST_TIMEOUT = 30  # Increased for E2E tests with real external services
CRAWLER_MAX_RETRIES = 1  # At least 1 for E2E tests (0 means no attempts at all)
CRAWLER_RATE_LIMIT_DELAY = 0
