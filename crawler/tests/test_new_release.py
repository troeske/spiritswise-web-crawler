"""
Tests for NewRelease Model.

Task Group 18: NewRelease Model
These tests verify:
- Release creation with status
- Hype score storage
- Status transitions
- Product linking when released

TDD: Tests written first before implementation.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone


class TestNewReleaseCreation:
    """Tests for NewRelease model creation."""

    def test_new_release_creation_with_required_fields(self, db):
        """NewRelease should be created with required fields and defaults."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release = NewRelease.objects.create(
            name="Highland Park 50 Year Old",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            hype_score=85,
        )

        assert release.id is not None
        assert release.name == "Highland Park 50 Year Old"
        assert release.product_type == "whiskey"
        assert release.release_status == ReleaseStatusChoices.ANNOUNCED
        assert release.hype_score == 85
        assert release.limited_edition is False
        assert release.is_tracked is True
        assert release.created_at is not None
        assert release.updated_at is not None

    def test_new_release_with_all_fields(self, db):
        """NewRelease should store all optional fields correctly."""
        from crawler.models import (
            NewRelease,
            ReleaseStatusChoices,
            DiscoveredBrand,
        )

        # Create a brand for linking
        brand = DiscoveredBrand.objects.create(
            name="Macallan",
            country="Scotland",
            region="Speyside",
        )

        release = NewRelease.objects.create(
            name="Macallan Horizon",
            brand=brand,
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            announced_date=date(2025, 1, 15),
            expected_release_date=date(2025, 6, 1),
            expected_price_eur=Decimal("5500.00"),
            expected_price_source="Official Press Release",
            limited_edition=True,
            expected_bottle_count=3000,
            hype_score=92,
            source_urls=["https://macallan.com/horizon", "https://whiskybase.com/release/123"],
            notes="New travel retail exclusive release",
            is_tracked=True,
        )

        assert release.brand == brand
        assert release.announced_date == date(2025, 1, 15)
        assert release.expected_release_date == date(2025, 6, 1)
        assert release.expected_price_eur == Decimal("5500.00")
        assert release.expected_price_source == "Official Press Release"
        assert release.limited_edition is True
        assert release.expected_bottle_count == 3000
        assert len(release.source_urls) == 2
        assert release.notes == "New travel retail exclusive release"


class TestNewReleaseHypeScore:
    """Tests for hype score storage and validation."""

    def test_hype_score_within_range(self, db):
        """Hype score should be stored when within valid range (1-100)."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release = NewRelease.objects.create(
            name="Low Hype Release",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.RUMORED,
            hype_score=15,
        )
        assert release.hype_score == 15

        release2 = NewRelease.objects.create(
            name="High Hype Release",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            hype_score=100,
        )
        assert release2.hype_score == 100

    def test_hype_score_boundary_values(self, db):
        """Hype score should accept boundary values 1 and 100."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release_min = NewRelease.objects.create(
            name="Min Hype",
            product_type="port_wine",
            release_status=ReleaseStatusChoices.RUMORED,
            hype_score=1,
        )
        assert release_min.hype_score == 1

        release_max = NewRelease.objects.create(
            name="Max Hype",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.PRE_ORDER,
            hype_score=100,
        )
        assert release_max.hype_score == 100


class TestNewReleaseStatusTransitions:
    """Tests for release status transitions."""

    def test_status_choices(self, db):
        """NewRelease should support all status choices."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        statuses = [
            ReleaseStatusChoices.RUMORED,
            ReleaseStatusChoices.ANNOUNCED,
            ReleaseStatusChoices.PRE_ORDER,
            ReleaseStatusChoices.RELEASED,
            ReleaseStatusChoices.CANCELLED,
        ]

        for i, status in enumerate(statuses):
            release = NewRelease.objects.create(
                name=f"Release Status Test {i}",
                product_type="whiskey",
                release_status=status,
                hype_score=50,
            )
            assert release.release_status == status

    def test_status_transition_rumored_to_announced(self, db):
        """Status should transition from rumored to announced."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release = NewRelease.objects.create(
            name="Rumored Whiskey",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.RUMORED,
            hype_score=40,
        )

        # Transition to announced
        release.release_status = ReleaseStatusChoices.ANNOUNCED
        release.announced_date = date.today()
        release.save()
        release.refresh_from_db()

        assert release.release_status == ReleaseStatusChoices.ANNOUNCED
        assert release.announced_date == date.today()

    def test_status_transition_to_released(self, db):
        """Status should transition to released with actual release date."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release = NewRelease.objects.create(
            name="Announced Whiskey",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            announced_date=date(2025, 1, 1),
            expected_release_date=date(2025, 3, 1),
            hype_score=75,
        )

        # Transition to released
        release.release_status = ReleaseStatusChoices.RELEASED
        release.actual_release_date = date(2025, 3, 15)
        release.save()
        release.refresh_from_db()

        assert release.release_status == ReleaseStatusChoices.RELEASED
        assert release.actual_release_date == date(2025, 3, 15)

    def test_status_transition_to_cancelled(self, db):
        """Status should transition to cancelled."""
        from crawler.models import NewRelease, ReleaseStatusChoices

        release = NewRelease.objects.create(
            name="Cancelled Whiskey",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            hype_score=60,
        )

        release.release_status = ReleaseStatusChoices.CANCELLED
        release.notes = "Cancelled due to production issues"
        release.save()
        release.refresh_from_db()

        assert release.release_status == ReleaseStatusChoices.CANCELLED
        assert "Cancelled" in release.notes


class TestNewReleaseProductLinking:
    """Tests for linking NewRelease to DiscoveredProduct when released."""

    def test_product_link_when_released(self, db):
        """NewRelease should link to DiscoveredProduct when product is created."""
        from crawler.models import (
            NewRelease,
            ReleaseStatusChoices,
            DiscoveredProduct,
            ProductType,
        )

        # Create a release in announced state
        release = NewRelease.objects.create(
            name="Ardbeg Hypernova",
            product_type="whiskey",
            release_status=ReleaseStatusChoices.ANNOUNCED,
            hype_score=88,
        )

        # Create the actual product
        product = DiscoveredProduct.objects.create(
            source_url="https://ardbeg.com/hypernova",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="ardbeg123",
            fingerprint="fingerprint_ardbeg_hypernova",
            name="Ardbeg Hypernova",
        )

        # Link the product to the release
        release.product = product
        release.release_status = ReleaseStatusChoices.RELEASED
        release.actual_release_date = date.today()
        release.save()
        release.refresh_from_db()

        assert release.product == product
        assert release.release_status == ReleaseStatusChoices.RELEASED
        assert release.product.name == "Ardbeg Hypernova"

    def test_release_related_name_on_product(self, db):
        """DiscoveredProduct should access releases via related_name."""
        from crawler.models import (
            NewRelease,
            ReleaseStatusChoices,
            DiscoveredProduct,
            ProductType,
        )

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/released-product",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="released123",
            fingerprint="fingerprint_released",
            name="Released Whiskey",
        )

        release = NewRelease.objects.create(
            name="Released Whiskey",
            product=product,
            product_type="whiskey",
            release_status=ReleaseStatusChoices.RELEASED,
            actual_release_date=date.today(),
            hype_score=70,
        )

        # Access via related_name
        assert product.new_releases.count() == 1
        assert product.new_releases.first() == release


class TestDiscoveredProductReleaseTrackingFields:
    """Tests for release tracking fields on DiscoveredProduct."""

    def test_release_tracking_fields_exist(self, db):
        """DiscoveredProduct should have release tracking fields."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/release-tracking",
            product_type=ProductType.WHISKEY,
            raw_content="Test content",
            raw_content_hash="releasetrack123",
            fingerprint="fingerprint_releasetrack",
            name="Release Tracking Test Whiskey",
            release_date=date(2025, 1, 15),
            release_quarter="Q1 2025",
            is_new_release=True,
            is_upcoming_release=False,
            first_seen_at=timezone.now(),
        )

        product.refresh_from_db()

        assert product.release_date == date(2025, 1, 15)
        assert product.release_quarter == "Q1 2025"
        assert product.is_new_release is True
        assert product.is_upcoming_release is False
        assert product.first_seen_at is not None

    def test_release_tracking_defaults(self, db):
        """Release tracking fields should have correct defaults."""
        from crawler.models import DiscoveredProduct, ProductType

        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/release-defaults",
            product_type=ProductType.PORT_WINE,
            raw_content="Test content",
            raw_content_hash="releasedefaults123",
            fingerprint="fingerprint_releasedefaults",
            name="Release Defaults Test",
        )

        product.refresh_from_db()

        assert product.release_date is None
        assert product.release_quarter is None
        assert product.is_new_release is False
        assert product.is_upcoming_release is False
        assert product.first_seen_at is None
