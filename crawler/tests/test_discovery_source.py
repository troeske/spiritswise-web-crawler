"""
Tests for DiscoverySource model.

Task Group 5: DiscoverySource Configuration Model
These tests verify the configurable crawl source model functionality.

Tests focus on:
- Source creation with required fields
- crawl_strategy choices validation
- reliability_score range validation (1-10)
- is_active toggle functionality
"""

import uuid
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from crawler.models import DiscoverySourceConfig


class DiscoverySourceCreationTestCase(TestCase):
    """Test DiscoverySourceConfig creation with required fields."""

    def test_create_discovery_source_with_required_fields(self):
        """Test creating a discovery source with all required fields succeeds."""
        source = DiscoverySourceConfig.objects.create(
            name="IWSC",
            base_url="https://iwsc.net",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
        )

        self.assertIsNotNone(source.id)
        self.assertIsInstance(source.id, uuid.UUID)
        self.assertEqual(source.name, "IWSC")
        self.assertEqual(source.base_url, "https://iwsc.net")
        self.assertEqual(source.source_type, "award_competition")
        self.assertEqual(source.crawl_priority, 8)
        self.assertEqual(source.crawl_frequency, "weekly")
        self.assertEqual(source.reliability_score, 9)

    def test_unique_name_constraint(self):
        """Test that name must be unique."""
        DiscoverySourceConfig.objects.create(
            name="Whisky Advocate",
            base_url="https://whiskyadvocate.com",
            source_type="review_blog",
            crawl_priority=7,
            crawl_frequency="daily",
            reliability_score=8,
        )

        with self.assertRaises(IntegrityError):
            DiscoverySourceConfig.objects.create(
                name="Whisky Advocate",  # Duplicate name
                base_url="https://different-url.com",
                source_type="news_outlet",
                crawl_priority=5,
                crawl_frequency="monthly",
                reliability_score=6,
            )


class DiscoverySourceCrawlStrategyTestCase(TestCase):
    """Test crawl_strategy choices validation."""

    def test_valid_crawl_strategies(self):
        """Test all valid crawl strategy choices are accepted."""
        valid_strategies = ["simple", "js_render", "stealth", "manual"]

        for i, strategy in enumerate(valid_strategies):
            source = DiscoverySourceConfig.objects.create(
                name=f"Test Source {i}",
                base_url=f"https://test{i}.com",
                source_type="review_blog",
                crawl_priority=5,
                crawl_frequency="weekly",
                reliability_score=5,
                crawl_strategy=strategy,
            )
            self.assertEqual(source.crawl_strategy, strategy)

    def test_default_crawl_strategy_is_simple(self):
        """Test that default crawl_strategy is 'simple'."""
        source = DiscoverySourceConfig.objects.create(
            name="Default Strategy Source",
            base_url="https://default-test.com",
            source_type="retailer",
            crawl_priority=5,
            crawl_frequency="daily",
            reliability_score=5,
        )
        self.assertEqual(source.crawl_strategy, "simple")


class DiscoverySourceReliabilityScoreTestCase(TestCase):
    """Test reliability_score range validation (1-10)."""

    def test_valid_reliability_scores(self):
        """Test that reliability scores 1-10 are valid."""
        for score in [1, 5, 10]:
            source = DiscoverySourceConfig(
                name=f"Score Test {score}",
                base_url=f"https://score-test-{score}.com",
                source_type="news_outlet",
                crawl_priority=5,
                crawl_frequency="monthly",
                reliability_score=score,
            )
            source.full_clean()  # Should not raise
            source.save()
            self.assertEqual(source.reliability_score, score)

    def test_reliability_score_below_minimum_fails(self):
        """Test that reliability_score below 1 fails validation."""
        source = DiscoverySourceConfig(
            name="Low Score Source",
            base_url="https://low-score.com",
            source_type="review_blog",
            crawl_priority=5,
            crawl_frequency="weekly",
            reliability_score=0,  # Invalid: below minimum
        )

        with self.assertRaises(ValidationError) as context:
            source.full_clean()

        self.assertIn("reliability_score", str(context.exception))

    def test_reliability_score_above_maximum_fails(self):
        """Test that reliability_score above 10 fails validation."""
        source = DiscoverySourceConfig(
            name="High Score Source",
            base_url="https://high-score.com",
            source_type="aggregator",
            crawl_priority=5,
            crawl_frequency="on_demand",
            reliability_score=11,  # Invalid: above maximum
        )

        with self.assertRaises(ValidationError) as context:
            source.full_clean()

        self.assertIn("reliability_score", str(context.exception))


class DiscoverySourceIsActiveTestCase(TestCase):
    """Test is_active toggle functionality."""

    def test_default_is_active_true(self):
        """Test that is_active defaults to True."""
        source = DiscoverySourceConfig.objects.create(
            name="Active By Default",
            base_url="https://active-default.com",
            source_type="distillery_official",
            crawl_priority=6,
            crawl_frequency="monthly",
            reliability_score=7,
        )
        self.assertTrue(source.is_active)

    def test_can_disable_source(self):
        """Test that a source can be disabled by setting is_active=False."""
        source = DiscoverySourceConfig.objects.create(
            name="Toggle Test Source",
            base_url="https://toggle-test.com",
            source_type="award_competition",
            crawl_priority=8,
            crawl_frequency="weekly",
            reliability_score=9,
            is_active=True,
        )

        self.assertTrue(source.is_active)

        # Disable the source
        source.is_active = False
        source.save()

        # Reload from database
        source.refresh_from_db()
        self.assertFalse(source.is_active)

    def test_can_enable_disabled_source(self):
        """Test that a disabled source can be re-enabled."""
        source = DiscoverySourceConfig.objects.create(
            name="Re-Enable Test",
            base_url="https://re-enable.com",
            source_type="retailer",
            crawl_priority=5,
            crawl_frequency="daily",
            reliability_score=6,
            is_active=False,  # Start disabled
        )

        self.assertFalse(source.is_active)

        # Enable the source
        source.is_active = True
        source.save()

        # Reload from database
        source.refresh_from_db()
        self.assertTrue(source.is_active)


class DiscoverySourceSourceTypeTestCase(TestCase):
    """Test source_type choices validation."""

    def test_valid_source_types(self):
        """Test all valid source_type choices are accepted."""
        valid_types = [
            "award_competition",
            "review_blog",
            "retailer",
            "distillery_official",
            "news_outlet",
            "aggregator",
        ]

        for i, source_type in enumerate(valid_types):
            source = DiscoverySourceConfig.objects.create(
                name=f"Source Type Test {i}",
                base_url=f"https://source-type-{i}.com",
                source_type=source_type,
                crawl_priority=5,
                crawl_frequency="weekly",
                reliability_score=5,
            )
            self.assertEqual(source.source_type, source_type)
