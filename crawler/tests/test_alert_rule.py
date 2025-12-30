"""
Task Group 28: AlertRule Model Tests

Tests for the AlertRule model which enables configurable alerting
for crawler metrics, with condition choices, severity levels, and
cooldown behavior to prevent alert spam.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from crawler.models import AlertRule


class TestAlertRuleCreation(TestCase):
    """Test AlertRule model creation and basic functionality."""

    def test_alert_rule_creation(self):
        """
        Test that AlertRule can be created with required fields.

        Required fields: name, metric, condition, threshold, severity
        """
        alert = AlertRule.objects.create(
            name="Crawl Success Rate Low",
            metric="crawl_success_rate",
            condition="below",
            threshold=Decimal("80.00"),
            severity="critical",
            notification_channel="sentry",
        )

        alert.refresh_from_db()
        assert alert.id is not None
        assert alert.name == "Crawl Success Rate Low"
        assert alert.metric == "crawl_success_rate"
        assert alert.condition == "below"
        assert alert.threshold == Decimal("80.00")
        assert alert.severity == "critical"
        assert alert.notification_channel == "sentry"

    def test_uuid_primary_key(self):
        """
        Test that AlertRule uses UUID as primary key.
        """
        alert = AlertRule.objects.create(
            name="Test Alert",
            metric="test_metric",
            condition="above",
            threshold=Decimal("100.00"),
            severity="warning",
        )

        alert.refresh_from_db()
        # UUID should be a 36-character string when converted
        assert len(str(alert.id)) == 36
        assert "-" in str(alert.id)  # UUIDs contain dashes

    def test_default_values(self):
        """
        Test that default values are set correctly.

        - window_hours: default 24
        - is_active: default True
        - cooldown_hours: default 4
        """
        alert = AlertRule.objects.create(
            name="Default Values Test",
            metric="test_metric",
            condition="equals",
            threshold=Decimal("50.00"),
            severity="info",
        )

        alert.refresh_from_db()
        assert alert.window_hours == 24
        assert alert.is_active is True
        assert alert.cooldown_hours == 4
        assert alert.last_triggered is None


class TestConditionChoices(TestCase):
    """Test condition choices validation."""

    def test_below_condition(self):
        """Test 'below' condition choice."""
        alert = AlertRule.objects.create(
            name="Below Test",
            metric="success_rate",
            condition="below",
            threshold=Decimal("80.00"),
            severity="critical",
        )
        alert.refresh_from_db()
        assert alert.condition == "below"

    def test_above_condition(self):
        """Test 'above' condition choice."""
        alert = AlertRule.objects.create(
            name="Above Test",
            metric="queue_depth",
            condition="above",
            threshold=Decimal("1000.00"),
            severity="warning",
        )
        alert.refresh_from_db()
        assert alert.condition == "above"

    def test_equals_condition(self):
        """Test 'equals' condition choice."""
        alert = AlertRule.objects.create(
            name="Equals Test",
            metric="pages_crawled",
            condition="equals",
            threshold=Decimal("0.00"),
            severity="critical",
        )
        alert.refresh_from_db()
        assert alert.condition == "equals"

    def test_changed_by_condition(self):
        """Test 'changed_by' condition choice."""
        alert = AlertRule.objects.create(
            name="Changed By Test",
            metric="price_volatility",
            condition="changed_by",
            threshold=Decimal("20.00"),  # 20% change
            severity="info",
        )
        alert.refresh_from_db()
        assert alert.condition == "changed_by"


class TestSeverityLevels(TestCase):
    """Test severity level choices."""

    def test_info_severity(self):
        """Test 'info' severity level."""
        alert = AlertRule.objects.create(
            name="Info Alert",
            metric="products_created",
            condition="above",
            threshold=Decimal("100.00"),
            severity="info",
        )
        alert.refresh_from_db()
        assert alert.severity == "info"

    def test_warning_severity(self):
        """Test 'warning' severity level."""
        alert = AlertRule.objects.create(
            name="Warning Alert",
            metric="extraction_rate",
            condition="below",
            threshold=Decimal("70.00"),
            severity="warning",
        )
        alert.refresh_from_db()
        assert alert.severity == "warning"

    def test_critical_severity(self):
        """Test 'critical' severity level."""
        alert = AlertRule.objects.create(
            name="Critical Alert",
            metric="crawl_success_rate",
            condition="below",
            threshold=Decimal("50.00"),
            severity="critical",
        )
        alert.refresh_from_db()
        assert alert.severity == "critical"


class TestCooldownBehavior(TestCase):
    """Test cooldown behavior for alert rate limiting."""

    def test_cooldown_hours_setting(self):
        """
        Test cooldown_hours field for rate limiting.

        Cooldown prevents the same alert from triggering too frequently.
        """
        alert = AlertRule.objects.create(
            name="Cooldown Test",
            metric="test_metric",
            condition="below",
            threshold=Decimal("50.00"),
            severity="warning",
            cooldown_hours=8,  # 8 hour cooldown
        )

        alert.refresh_from_db()
        assert alert.cooldown_hours == 8

    def test_last_triggered_tracking(self):
        """
        Test last_triggered field for cooldown evaluation.
        """
        trigger_time = timezone.now()
        alert = AlertRule.objects.create(
            name="Trigger Tracking Test",
            metric="test_metric",
            condition="above",
            threshold=Decimal("100.00"),
            severity="critical",
            last_triggered=trigger_time,
        )

        alert.refresh_from_db()
        # Compare with some tolerance for database storage precision
        assert alert.last_triggered is not None
        assert abs((alert.last_triggered - trigger_time).total_seconds()) < 1

    def test_cooldown_evaluation_logic(self):
        """
        Test that cooldown can be evaluated based on last_triggered and cooldown_hours.

        An alert should not trigger if it was triggered within the cooldown period.
        """
        # Alert triggered 2 hours ago
        two_hours_ago = timezone.now() - timedelta(hours=2)
        alert = AlertRule.objects.create(
            name="Cooldown Evaluation Test",
            metric="test_metric",
            condition="below",
            threshold=Decimal("50.00"),
            severity="warning",
            cooldown_hours=4,  # 4 hour cooldown
            last_triggered=two_hours_ago,
        )

        alert.refresh_from_db()
        # Should still be in cooldown (2 < 4 hours)
        cooldown_end = alert.last_triggered + timedelta(hours=alert.cooldown_hours)
        assert timezone.now() < cooldown_end  # Still in cooldown

    def test_cooldown_expired(self):
        """
        Test detection of expired cooldown.
        """
        # Alert triggered 6 hours ago
        six_hours_ago = timezone.now() - timedelta(hours=6)
        alert = AlertRule.objects.create(
            name="Cooldown Expired Test",
            metric="test_metric",
            condition="below",
            threshold=Decimal("50.00"),
            severity="warning",
            cooldown_hours=4,  # 4 hour cooldown
            last_triggered=six_hours_ago,
        )

        alert.refresh_from_db()
        # Cooldown should be expired (6 > 4 hours)
        cooldown_end = alert.last_triggered + timedelta(hours=alert.cooldown_hours)
        assert timezone.now() > cooldown_end  # Cooldown expired


class TestNotificationChannels(TestCase):
    """Test notification channel choices."""

    def test_email_channel(self):
        """Test 'email' notification channel."""
        alert = AlertRule.objects.create(
            name="Email Alert",
            metric="test_metric",
            condition="above",
            threshold=Decimal("100.00"),
            severity="info",
            notification_channel="email",
        )
        alert.refresh_from_db()
        assert alert.notification_channel == "email"

    def test_slack_channel(self):
        """Test 'slack' notification channel."""
        alert = AlertRule.objects.create(
            name="Slack Alert",
            metric="test_metric",
            condition="below",
            threshold=Decimal("50.00"),
            severity="warning",
            notification_channel="slack",
        )
        alert.refresh_from_db()
        assert alert.notification_channel == "slack"

    def test_sentry_channel(self):
        """Test 'sentry' notification channel."""
        alert = AlertRule.objects.create(
            name="Sentry Alert",
            metric="crawl_success_rate",
            condition="below",
            threshold=Decimal("80.00"),
            severity="critical",
            notification_channel="sentry",
        )
        alert.refresh_from_db()
        assert alert.notification_channel == "sentry"


class TestActiveRuleFiltering(TestCase):
    """Test is_active field for filtering active alert rules."""

    def test_active_rules_filtering(self):
        """
        Test filtering active alert rules.
        """
        # Create active rule
        active_rule = AlertRule.objects.create(
            name="Active Rule",
            metric="test_metric",
            condition="above",
            threshold=Decimal("100.00"),
            severity="warning",
            is_active=True,
        )

        # Create inactive rule
        inactive_rule = AlertRule.objects.create(
            name="Inactive Rule",
            metric="test_metric",
            condition="below",
            threshold=Decimal("50.00"),
            severity="info",
            is_active=False,
        )

        # Filter for active rules only
        active_rules = AlertRule.objects.filter(is_active=True)
        inactive_rules = AlertRule.objects.filter(is_active=False)

        assert active_rules.count() == 1
        assert active_rules.first().name == "Active Rule"
        assert inactive_rules.count() == 1
        assert inactive_rules.first().name == "Inactive Rule"

    def test_deactivate_rule(self):
        """
        Test deactivating an alert rule.
        """
        alert = AlertRule.objects.create(
            name="To Be Deactivated",
            metric="test_metric",
            condition="above",
            threshold=Decimal("100.00"),
            severity="warning",
            is_active=True,
        )

        # Deactivate
        alert.is_active = False
        alert.save()

        alert.refresh_from_db()
        assert alert.is_active is False


class TestWindowHours(TestCase):
    """Test window_hours field for time-based metric evaluation."""

    def test_custom_window_hours(self):
        """
        Test custom window_hours setting for metric evaluation.

        Window hours defines the time period over which the metric is evaluated.
        """
        alert = AlertRule.objects.create(
            name="Custom Window Test",
            metric="crawl_success_rate",
            condition="below",
            threshold=Decimal("80.00"),
            severity="warning",
            window_hours=48,  # 48 hour window
        )

        alert.refresh_from_db()
        assert alert.window_hours == 48

    def test_short_window_for_real_time_alerts(self):
        """
        Test short window hours for near-real-time alerting.
        """
        alert = AlertRule.objects.create(
            name="Real-Time Alert",
            metric="queue_depth",
            condition="above",
            threshold=Decimal("1000.00"),
            severity="critical",
            window_hours=1,  # 1 hour window
        )

        alert.refresh_from_db()
        assert alert.window_hours == 1
