"""
Django base settings for Web Crawler Microservice.

This module contains settings common to all environments.
For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-crawler-dev-key-change-in-production-xyz123"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "drf_spectacular",
    # Local apps
    "crawler",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# Shared PostgreSQL database with AI Enhancement Service
# Configured in environment-specific settings (development.py, production.py, test.py)

DATABASES = {
    # Override in environment-specific settings
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Redis Cache Configuration
# https://docs.djangoproject.com/en/4.2/topics/cache/
# Configured in environment-specific settings

CACHES = {
    # Override in environment-specific settings
}


# Celery Configuration
# https://docs.celeryproject.org/en/stable/django/first-steps-with-django.html

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max for crawl tasks

# Task routing - crawl and search queues
CELERY_TASK_ROUTES = {
    "crawler.tasks.crawl_*": {"queue": "crawl"},
    "crawler.tasks.search_*": {"queue": "search"},
    "crawler.tasks.process_source": {"queue": "crawl"},
    "crawler.tasks.keyword_search": {"queue": "search"},
}


# Django REST Framework Configuration
# https://www.django-rest-framework.org/

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}


# DRF Spectacular (OpenAPI/Swagger) Configuration
# https://drf-spectacular.readthedocs.io/

SPECTACULAR_SETTINGS = {
    "TITLE": "Web Crawler Microservice API",
    "DESCRIPTION": "Web crawler service for SpiritsWise whiskey database",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


# Logging Configuration
# https://docs.djangoproject.com/en/4.2/topics/logging/

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
        },
        "crawler": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
        },
    },
}


# External API Configuration

# AI Enhancement Service
AI_ENHANCEMENT_SERVICE_URL = os.getenv(
    "AI_ENHANCEMENT_SERVICE_URL",
    "http://localhost:8000"
)
AI_ENHANCEMENT_SERVICE_TOKEN = os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN", "")

# SerpAPI for search discovery
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# ScrapingBee for Tier 3 fetching
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "")


# Sentry Configuration
# https://docs.sentry.io/platforms/python/guides/django/

SENTRY_DSN = os.getenv(
    "SENTRY_DSN",
    "https://1790c5e0bd71082316ed75211b466a1b@o4510611012911104.ingest.de.sentry.io/4510611100467280"
)
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0"))
SENTRY_PROFILE_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILE_SAMPLE_RATE", "1.0"))

# Initialize Sentry
import sentry_sdk

sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Include request headers and IP for users
    send_default_pii=True,
    # Capture 100% of transactions for tracing
    traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
    # Profile sample rate (requires sentry-sdk[profiling])
    profiles_sample_rate=SENTRY_PROFILE_SAMPLE_RATE,
    environment=SENTRY_ENVIRONMENT,
)


# Crawler Configuration

# Default timeout for HTTP requests (seconds)
CRAWLER_REQUEST_TIMEOUT = int(os.getenv("CRAWLER_REQUEST_TIMEOUT", "30"))

# Maximum retries for failed requests
CRAWLER_MAX_RETRIES = int(os.getenv("CRAWLER_MAX_RETRIES", "3"))

# Rate limiting: minimum delay between requests to same domain (seconds)
CRAWLER_RATE_LIMIT_DELAY = float(os.getenv("CRAWLER_RATE_LIMIT_DELAY", "1.0"))

# Age gate detection content length threshold
CRAWLER_AGE_GATE_CONTENT_THRESHOLD = int(
    os.getenv("CRAWLER_AGE_GATE_CONTENT_THRESHOLD", "500")
)

# Default age gate cookies for unknown sites
CRAWLER_DEFAULT_AGE_COOKIES = {
    "age_verified": "true",
    "dob": "1990-01-01",
    "over18": "true",
    "over21": "true",
    "ageverified": "true",
    "av": "1",
}


# Monitoring Configuration (Task Group 9)
# https://docs.sentry.io/platforms/python/guides/django/

# Consecutive failure threshold - alert after N consecutive failures per source
CRAWLER_FAILURE_THRESHOLD = int(os.getenv("CRAWLER_FAILURE_THRESHOLD", "5"))

# Daily error rate threshold - alert when error rate exceeds this percentage
CRAWLER_ERROR_RATE_THRESHOLD = float(os.getenv("CRAWLER_ERROR_RATE_THRESHOLD", "0.10"))
