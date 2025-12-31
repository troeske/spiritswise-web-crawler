"""
Tests for Conflict Detection in ContentProcessor.

RECT-009: Implement Conflict Detection Logic

These tests verify that when merging data from multiple sources,
conflicts are detected and products are flagged accordingly.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal

from crawler.models import (
    DiscoveredProduct,
    ProductType,
    CrawlerSource,
    SourceCategory,
    CrawledSource,
    ProductFieldSource,
)
from crawler.services.conflict_detector import (
    ConflictDetector,
    detect_conflicts,
    NUMERICAL_FIELDS,
    ARRAY_FIELDS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Conflict Source",
        slug="test-conflict-source",
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
        fingerprint="conflict-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test whiskey content</html>",
        raw_content_hash="conflict001hash",
        extracted_data={"name": "Test Whiskey"},
        name="Test Whiskey",
        abv=40.0,
        age_statement=12,
        region="Speyside",
    )


@pytest.fixture
def crawled_source_1(db):
    """Create first crawled source for testing."""
    return CrawledSource.objects.create(
        url="https://source1.com/product",
        content_hash="source1hash",
        title="Source 1",
    )


@pytest.fixture
def crawled_source_2(db):
    """Create second crawled source for testing."""
    return CrawledSource.objects.create(
        url="https://source2.com/product",
        content_hash="source2hash",
        title="Source 2",
    )


# =============================================================================
# Unit Tests for ConflictDetector Configuration
# =============================================================================

class TestConflictDetectorConfiguration:
    """Tests for ConflictDetector configuration."""

    def test_numerical_fields_includes_abv(self):
        """ABV should be in numerical fields for exact match comparison."""
        assert "abv" in NUMERICAL_FIELDS

    def test_numerical_fields_includes_age_statement(self):
        """age_statement should be in numerical fields."""
        assert "age_statement" in NUMERICAL_FIELDS

    def test_numerical_fields_includes_volume_ml(self):
        """volume_ml should be in numerical fields."""
        assert "volume_ml" in NUMERICAL_FIELDS

    def test_array_fields_includes_primary_aromas(self):
        """primary_aromas should be in array fields."""
        assert "primary_aromas" in ARRAY_FIELDS

    def test_array_fields_includes_palate_flavors(self):
        """palate_flavors should be in array fields."""
        assert "palate_flavors" in ARRAY_FIELDS


# =============================================================================
# Integration Tests for Numerical Conflict Detection
# =============================================================================

class TestNumericalConflictDetection:
    """Tests for detecting conflicts in numerical fields."""

    def test_abv_mismatch_flags_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Different ABV values from two sources -> has_conflicts=True."""
        # Create provenance records with different ABV values
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is True
        assert "abv" in conflicts["conflicting_fields"]
        assert conflicts["conflict_details"]["abv"]["values"] == ["40.0", "43.0"]

    def test_age_mismatch_flags_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Different age statements -> has_conflicts=True."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="age_statement",
            extracted_value="12",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="age_statement",
            extracted_value="18",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is True
        assert "age_statement" in conflicts["conflicting_fields"]

    def test_matching_numerical_values_no_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Same numerical values from two sources -> no conflict."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert "abv" not in conflicts.get("conflicting_fields", [])


# =============================================================================
# Integration Tests for String Conflict Detection
# =============================================================================

class TestStringConflictDetection:
    """Tests for detecting conflicts in string fields."""

    def test_region_mismatch_flags_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Different regions -> has_conflicts=True."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="region",
            extracted_value="Speyside",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="region",
            extracted_value="Highlands",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is True
        assert "region" in conflicts["conflicting_fields"]

    def test_matching_string_values_no_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Same string values from two sources -> no conflict."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="region",
            extracted_value="Speyside",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="region",
            extracted_value="Speyside",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert "region" not in conflicts.get("conflicting_fields", [])


# =============================================================================
# Integration Tests for Array Conflict Detection
# =============================================================================

class TestArrayConflictDetection:
    """Tests for detecting conflicts in array fields."""

    def test_additive_arrays_no_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Different aromas that complement -> no conflict (arrays are additive)."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="primary_aromas",
            extracted_value='["vanilla", "caramel"]',
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="primary_aromas",
            extracted_value='["honey", "oak"]',
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        # Arrays are additive by default - different values are NOT conflicts
        assert "primary_aromas" not in conflicts.get("conflicting_fields", [])

    def test_overlapping_arrays_no_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Arrays with overlapping values -> no conflict."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="palate_flavors",
            extracted_value='["vanilla", "caramel", "oak"]',
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="palate_flavors",
            extracted_value='["vanilla", "honey"]',
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert "palate_flavors" not in conflicts.get("conflicting_fields", [])


# =============================================================================
# Integration Tests for Conflict Details
# =============================================================================

class TestConflictDetails:
    """Tests for conflict_details structure."""

    def test_conflict_details_populated(self, db, sample_product, crawled_source_1, crawled_source_2):
        """conflict_details JSONField contains source comparisons."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert "conflict_details" in conflicts
        assert "abv" in conflicts["conflict_details"]
        details = conflicts["conflict_details"]["abv"]
        assert "values" in details
        assert "sources" in details
        assert len(details["sources"]) == 2

    def test_conflict_details_includes_confidence(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Conflict details include confidence scores."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        details = conflicts["conflict_details"]["abv"]
        assert "confidences" in details
        assert 0.9 in details["confidences"]
        assert 0.85 in details["confidences"]

    def test_no_conflicts_returns_empty_details(self, db, sample_product, crawled_source_1):
        """No conflicts returns empty conflict_details."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )

        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is False
        assert conflicts["conflicting_fields"] == []
        assert conflicts["conflict_details"] == {}


# =============================================================================
# Integration Tests for Product Update with Conflicts
# =============================================================================

class TestProductConflictUpdate:
    """Tests for updating product with conflict information."""

    def test_product_has_conflicts_updated(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Product.has_conflicts is set when conflicts detected."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.85,
        )

        detector = ConflictDetector()
        detector.update_product_conflicts(sample_product)

        sample_product.refresh_from_db()
        assert sample_product.has_conflicts is True
        assert sample_product.conflict_details is not None
        assert "abv" in sample_product.conflict_details

    def test_product_conflicts_cleared_when_resolved(self, db, sample_product, crawled_source_1):
        """Product.has_conflicts is cleared when no conflicts exist."""
        # Set up initial conflict state
        sample_product.has_conflicts = True
        sample_product.conflict_details = {"abv": {"values": ["40.0", "43.0"]}}
        sample_product.save()

        # Now only one source
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )

        detector = ConflictDetector()
        detector.update_product_conflicts(sample_product)

        sample_product.refresh_from_db()
        assert sample_product.has_conflicts is False
        assert sample_product.conflict_details == {}


# =============================================================================
# Edge Cases
# =============================================================================

class TestConflictDetectionEdgeCases:
    """Edge case tests for conflict detection."""

    def test_single_source_no_conflict(self, db, sample_product, crawled_source_1):
        """Single source for a field -> no conflict."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )

        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is False

    def test_no_provenance_records_no_conflict(self, db, sample_product):
        """No provenance records -> no conflict."""
        conflicts = detect_conflicts(sample_product)

        assert conflicts["has_conflicts"] is False
        assert conflicts["conflicting_fields"] == []

    def test_low_confidence_values_ignored(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Low confidence values (<0.5) don't trigger conflicts."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="abv",
            extracted_value="40.0",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="abv",
            extracted_value="43.0",
            confidence=0.3,  # Low confidence
        )

        conflicts = detect_conflicts(sample_product, min_confidence=0.5)

        # The low confidence value should be ignored
        assert conflicts["has_conflicts"] is False

    def test_whitespace_differences_ignored(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Whitespace differences in strings -> no conflict."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="region",
            extracted_value="Speyside",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="region",
            extracted_value="  Speyside  ",
            confidence=0.85,
        )

        conflicts = detect_conflicts(sample_product)

        assert "region" not in conflicts.get("conflicting_fields", [])

    def test_case_differences_in_strings_flag_conflict(self, db, sample_product, crawled_source_1, crawled_source_2):
        """Case differences in important fields -> has_conflicts=True."""
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_1,
            field_name="country",
            extracted_value="Scotland",
            confidence=0.9,
        )
        ProductFieldSource.objects.create(
            product=sample_product,
            source=crawled_source_2,
            field_name="country",
            extracted_value="scotland",
            confidence=0.85,
        )

        # Case differences are NOT conflicts for case-insensitive fields
        conflicts = detect_conflicts(sample_product)

        assert "country" not in conflicts.get("conflicting_fields", [])
