"""
Tests for ProductImage Creation in ContentProcessor.

RECT-008: Create ProductImage Records from Images Data

These tests verify that images from AI response are extracted and
stored as individual ProductImage records instead of in JSONField.

TDD: Tests written first before implementation.
"""

import pytest

from crawler.models import (
    DiscoveredProduct,
    ProductType,
    CrawlerSource,
    SourceCategory,
    ProductImage,
    ImageTypeChoices,
)
from crawler.services.content_processor import (
    create_product_images,
    IMAGE_FIELD_MAPPING,
    VALID_IMAGE_TYPES,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Image Source",
        slug="test-image-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_product(db, sample_source):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/whiskey/test",
        fingerprint="image-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test whiskey content</html>",
        raw_content_hash="image001hash",
        extracted_data={"name": "Test Whiskey"},
        name="Test Whiskey",
    )


# =============================================================================
# Unit Tests for Image Field Mapping Coverage
# =============================================================================

class TestImageFieldMappingCoverage:
    """Tests to verify IMAGE_FIELD_MAPPING covers all required fields."""

    def test_mapping_includes_required_fields(self):
        """Mapping should include required fields."""
        required_fields = ["url", "image_type", "source"]
        for field in required_fields:
            assert field in IMAGE_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_dimension_fields(self):
        """Mapping should include dimension fields."""
        dimension_fields = ["width", "height"]
        for field in dimension_fields:
            assert field in IMAGE_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_is_primary(self):
        """Mapping should include is_primary field."""
        assert "is_primary" in IMAGE_FIELD_MAPPING


class TestValidImageTypes:
    """Tests for valid image types."""

    def test_all_image_types_valid(self):
        """All image types should be in ImageTypeChoices."""
        valid_types = ["bottle", "label", "packaging", "lifestyle"]
        for img_type in valid_types:
            assert img_type in VALID_IMAGE_TYPES, f"Missing image type: {img_type}"


# =============================================================================
# Integration Tests for ProductImage Creation
# =============================================================================

class TestProductImageCreation:
    """Integration tests for ProductImage creation."""

    def test_image_creates_record(self, db, sample_product):
        """Image URL in AI response creates ProductImage record."""
        images_data = [
            {
                "url": "https://example.com/images/bottle.jpg",
                "image_type": "bottle",
                "source": "Example.com",
            }
        ]

        count = create_product_images(sample_product, images_data)

        assert count == 1
        assert ProductImage.objects.filter(product=sample_product).count() == 1

    def test_multiple_images_create_multiple_records(self, db, sample_product):
        """Multiple images create multiple ProductImage records."""
        images_data = [
            {"url": "https://example.com/bottle.jpg", "image_type": "bottle", "source": "Example"},
            {"url": "https://example.com/label.jpg", "image_type": "label", "source": "Example"},
            {"url": "https://example.com/lifestyle.jpg", "image_type": "lifestyle", "source": "Example"},
        ]

        count = create_product_images(sample_product, images_data)

        assert count == 3
        assert ProductImage.objects.filter(product=sample_product).count() == 3

    def test_image_type_classified(self, db, sample_product):
        """image_type set correctly from AI response."""
        images_data = [
            {"url": "https://example.com/bottle.jpg", "image_type": "bottle", "source": "Example"},
        ]

        create_product_images(sample_product, images_data)

        image = ProductImage.objects.get(product=sample_product)
        assert image.image_type == ImageTypeChoices.BOTTLE

    def test_all_image_types_supported(self, db, sample_product):
        """All 4 image types should be supported."""
        images_data = [
            {"url": "https://example.com/bottle.jpg", "image_type": "bottle", "source": "Example"},
            {"url": "https://example.com/label.jpg", "image_type": "label", "source": "Example"},
            {"url": "https://example.com/packaging.jpg", "image_type": "packaging", "source": "Example"},
            {"url": "https://example.com/lifestyle.jpg", "image_type": "lifestyle", "source": "Example"},
        ]

        count = create_product_images(sample_product, images_data)

        assert count == 4
        images = ProductImage.objects.filter(product=sample_product)
        types = set(img.image_type for img in images)
        assert types == {"bottle", "label", "packaging", "lifestyle"}

    def test_dimensions_stored_if_available(self, db, sample_product):
        """width, height stored when provided."""
        images_data = [
            {
                "url": "https://example.com/bottle.jpg",
                "image_type": "bottle",
                "source": "Example",
                "width": 800,
                "height": 1200,
            }
        ]

        create_product_images(sample_product, images_data)

        image = ProductImage.objects.get(product=sample_product)
        assert image.width == 800
        assert image.height == 1200

    def test_dimensions_optional(self, db, sample_product):
        """Dimensions should be optional."""
        images_data = [
            {
                "url": "https://example.com/bottle.jpg",
                "image_type": "bottle",
                "source": "Example",
            }
        ]

        create_product_images(sample_product, images_data)

        image = ProductImage.objects.get(product=sample_product)
        assert image.width is None
        assert image.height is None

    def test_source_tracked(self, db, sample_product):
        """Source of image tracked for attribution."""
        images_data = [
            {
                "url": "https://example.com/bottle.jpg",
                "image_type": "bottle",
                "source": "IWSC 2024",
            }
        ]

        create_product_images(sample_product, images_data)

        image = ProductImage.objects.get(product=sample_product)
        assert image.source == "IWSC 2024"

    def test_is_primary_flag(self, db, sample_product):
        """is_primary flag should be stored."""
        images_data = [
            {
                "url": "https://example.com/primary.jpg",
                "image_type": "bottle",
                "source": "Example",
                "is_primary": True,
            },
            {
                "url": "https://example.com/secondary.jpg",
                "image_type": "label",
                "source": "Example",
                "is_primary": False,
            },
        ]

        create_product_images(sample_product, images_data)

        primary = ProductImage.objects.get(url="https://example.com/primary.jpg")
        secondary = ProductImage.objects.get(url="https://example.com/secondary.jpg")
        assert primary.is_primary is True
        assert secondary.is_primary is False

    def test_duplicate_images_prevented(self, db, sample_product):
        """Same image URL should not be duplicated."""
        images_data = [
            {"url": "https://example.com/bottle.jpg", "image_type": "bottle", "source": "Example"},
        ]

        # Create first image
        count1 = create_product_images(sample_product, images_data)
        assert count1 == 1

        # Try to create same image again
        count2 = create_product_images(sample_product, images_data)
        assert count2 == 0  # No new images created

        # Should still only have 1 image
        assert ProductImage.objects.filter(product=sample_product).count() == 1

    def test_missing_required_fields_skipped(self, db, sample_product):
        """Images missing required fields should be skipped."""
        images_data = [
            {"url": "https://valid.com/img.jpg", "image_type": "bottle", "source": "Valid"},  # Valid
            {"image_type": "bottle", "source": "Missing URL"},  # Missing url
            {"url": "https://test.com/img.jpg", "source": "Missing Type"},  # Missing image_type
            {"url": "https://test.com/img2.jpg", "image_type": "bottle"},  # Missing source
        ]

        count = create_product_images(sample_product, images_data)

        assert count == 1  # Only the valid one
        assert ProductImage.objects.filter(product=sample_product).count() == 1

    def test_null_images_data_returns_zero(self, db, sample_product):
        """None images_data should return 0."""
        count = create_product_images(sample_product, None)
        assert count == 0

    def test_empty_images_data_returns_zero(self, db, sample_product):
        """Empty list should return 0."""
        count = create_product_images(sample_product, [])
        assert count == 0

    def test_invalid_image_type_skipped(self, db, sample_product):
        """Invalid image_type should cause image to be skipped."""
        images_data = [
            {"url": "https://valid.com/img.jpg", "image_type": "bottle", "source": "Valid"},  # Valid
            {"url": "https://invalid.com/img.jpg", "image_type": "invalid_type", "source": "Invalid"},  # Invalid
        ]

        count = create_product_images(sample_product, images_data)

        assert count == 1
        assert ProductImage.objects.filter(product=sample_product).count() == 1

    def test_default_is_primary_false(self, db, sample_product):
        """Default is_primary should be False."""
        images_data = [
            {"url": "https://example.com/bottle.jpg", "image_type": "bottle", "source": "Example"},
        ]

        create_product_images(sample_product, images_data)

        image = ProductImage.objects.get(product=sample_product)
        assert image.is_primary is False
