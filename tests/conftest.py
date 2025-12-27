"""
Pytest configuration and fixtures for the Web Crawler test suite.
"""

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Configure the test database and run migrations."""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture
def api_client():
    """Create a test API client."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def crawler_source(db):
    """Create a test CrawlerSource instance."""
    from crawler.models import CrawlerSource

    return CrawlerSource.objects.create(
        name="Test Source",
        slug="test-source",
        base_url="https://example.com",
        category="retailer",
        is_active=True,
    )


@pytest.fixture
def crawler_source_with_cookies(db):
    """Create a CrawlerSource with age gate cookies configured."""
    from crawler.models import CrawlerSource

    return CrawlerSource.objects.create(
        name="Source With Cookies",
        slug="source-with-cookies",
        base_url="https://whisky-site.com",
        category="retailer",
        is_active=True,
        age_gate_type="cookie",
        age_gate_cookies={
            "age_verified": "true",
            "consent": "yes",
        },
    )


@pytest.fixture
def tier3_source(db):
    """Create a CrawlerSource that requires Tier 3."""
    from crawler.models import CrawlerSource

    return CrawlerSource.objects.create(
        name="Tier 3 Required Source",
        slug="tier3-required",
        base_url="https://blocked-site.com",
        category="retailer",
        is_active=True,
        requires_tier3=True,
    )
