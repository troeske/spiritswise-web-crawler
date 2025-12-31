"""
Tests for Missing Model Fields per Spec.

RECT-011: Add Missing Model Fields per Spec

These tests verify that DiscoveredProduct has all required
fields as specified in the spec.

TDD: Tests written first before implementation.
"""

import pytest
from django.db import models

from crawler.models import DiscoveredProduct


class TestMissingModelFields:
    """Tests for missing model fields on DiscoveredProduct."""

    def test_bottler_field_exists(self):
        """DiscoveredProduct has bottler CharField."""
        field = DiscoveredProduct._meta.get_field("bottler")
        assert isinstance(field, models.CharField)
        assert field.max_length == 200
        assert field.null is True
        assert field.blank is True

    def test_maturation_notes_field_exists(self):
        """DiscoveredProduct has maturation_notes TextField."""
        field = DiscoveredProduct._meta.get_field("maturation_notes")
        assert isinstance(field, models.TextField)
        assert field.null is True
        assert field.blank is True

    def test_primary_cask_is_jsonfield(self):
        """primary_cask is JSONField (stores list of cask types)."""
        field = DiscoveredProduct._meta.get_field("primary_cask")
        assert isinstance(field, models.JSONField)

    def test_finishing_cask_is_jsonfield(self):
        """finishing_cask is JSONField (stores list of cask types)."""
        field = DiscoveredProduct._meta.get_field("finishing_cask")
        assert isinstance(field, models.JSONField)

    def test_wood_type_is_jsonfield(self):
        """wood_type is JSONField (stores list of wood types)."""
        field = DiscoveredProduct._meta.get_field("wood_type")
        assert isinstance(field, models.JSONField)

    def test_cask_treatment_is_jsonfield(self):
        """cask_treatment is JSONField (stores list of treatments)."""
        field = DiscoveredProduct._meta.get_field("cask_treatment")
        assert isinstance(field, models.JSONField)


class TestBottlerField:
    """Tests for bottler field functionality."""

    def test_bottler_can_be_set(self, db):
        """Bottler field can be set on product."""
        from crawler.models import CrawlerSource, SourceCategory, ProductType

        source = CrawlerSource.objects.create(
            name="Test Source",
            slug="test-source",
            base_url="https://example.com",
            category=SourceCategory.COMPETITION,
            product_types=["whiskey"],
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/whiskey/1",
            fingerprint="bottler-test-001",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            raw_content_hash="bottlerhash",
            name="Test Whiskey",
            bottler="Gordon & MacPhail",
        )

        assert product.bottler == "Gordon & MacPhail"

    def test_bottler_can_be_null(self, db):
        """Bottler field can be null."""
        from crawler.models import CrawlerSource, SourceCategory, ProductType

        source = CrawlerSource.objects.create(
            name="Test Source 2",
            slug="test-source-2",
            base_url="https://example.com",
            category=SourceCategory.COMPETITION,
            product_types=["whiskey"],
        )

        product = DiscoveredProduct.objects.create(
            source=source,
            source_url="https://example.com/whiskey/2",
            fingerprint="bottler-test-002",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test</html>",
            raw_content_hash="bottlerhash2",
            name="Test Whiskey 2",
        )

        assert product.bottler is None
