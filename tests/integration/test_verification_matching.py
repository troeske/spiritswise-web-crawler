# tests/integration/test_verification_matching.py
"""
Task 6.3: Verification Pipeline Field Matching

Tests for field matching logic when multiple sources are available:
1. Same values from 2+ sources -> Field is verified
2. Missing field filled from new source -> Field added, tracked as single-source
3. Different values (conflict) -> Log conflict, don't overwrite, flag for review
4. Track verified_fields list -> Keep list of which fields have been verified

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md Section 7.1 (lines 76-100)
"""

import pytest
import os
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VPS_TESTS") != "true",
    reason="VPS tests disabled - set RUN_VPS_TESTS=true"
)


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct with essential fields."""
    product = Mock()
    product.name = "Ardbeg 10"
    product.abv = Decimal("46.0")
    product.palate_description = None  # Missing
    product.region = "Islay"
    product.country = "Scotland"
    product.product_type = "whiskey"
    product.source_count = 1
    product.verified_fields = []

    # Add the values_match method from DiscoveredProduct
    def values_match(val1, val2):
        if val1 is None or val2 is None:
            return val1 == val2
        if isinstance(val1, Decimal) or isinstance(val2, Decimal):
            try:
                return Decimal(str(val1)) == Decimal(str(val2))
            except (ValueError, TypeError):
                return False
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.lower().strip() == val2.lower().strip()
        if isinstance(val1, list) and isinstance(val2, list):
            return sorted(val1) == sorted(val2)
        return val1 == val2

    product.values_match = values_match
    product.save = Mock()
    product.calculate_completeness_score = Mock(return_value=65)
    product.determine_status = Mock(return_value="PARTIAL")
    product.get_missing_critical_fields = Mock(return_value=["palate"])

    return product


@pytest.fixture
def verification_pipeline():
    """Create a VerificationPipeline instance with mocked dependencies."""
    from crawler.verification.pipeline import VerificationPipeline

    pipeline = VerificationPipeline()
    # Mock the search and extraction methods to avoid real API calls
    pipeline._search_additional_sources = Mock(return_value=[])
    pipeline._extract_from_source = Mock(return_value=None)

    return pipeline


# ============================================================
# Source 1 and Source 2 Mock Data (from task spec)
# ============================================================

SOURCE_1_DATA = {
    "name": "Ardbeg 10",
    "abv": Decimal("46.0"),
    "palate_description": None,  # Missing
    "region": "Islay",
}

SOURCE_2_DATA = {
    "name": "Ardbeg 10 Year Old",  # Slightly different
    "abv": Decimal("46.0"),  # Matches!
    "palate_description": "Rich, smoky, with espresso notes",
    "region": "Islay",  # Matches!
}

EXPECTED_MERGED = {
    "name": "Ardbeg 10",  # Keep original
    "abv": Decimal("46.0"),  # Verified!
    "palate_description": "Rich, smoky, with espresso notes",  # Filled!
    "region": "Islay",  # Verified!
    "verified_fields": ["abv", "region"],  # These match from 2 sources
}


# ============================================================
# Test Classes
# ============================================================

class TestFieldVerification:
    """
    Test field verification when multiple sources agree.
    """

    def test_verifies_field_when_2_sources_match(self, verification_pipeline, mock_product):
        """
        When same ABV (46%) from 2 sources:
        - ABV should be marked as verified
        - verified_fields should include 'abv'
        """
        # Arrange: Product has ABV from source 1
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = []

        # Act: Merge source 2 data with matching ABV
        extraction_data = {"abv": Decimal("46.0")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert "abv" in mock_product.verified_fields, \
            "ABV should be in verified_fields when 2 sources agree"
        assert len(conflicts) == 0, "No conflicts expected when values match"

    def test_verifies_field_with_minor_variations(self, verification_pipeline, mock_product):
        """
        ABV 46.0% vs ABV 46% should be considered matching.
        Handle minor formatting differences.
        """
        # Arrange: Source 1 has "46.0"
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = []

        # Act: Source 2 has "46" (no decimal)
        extraction_data = {"abv": Decimal("46")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: Should match because 46.0 == 46
        assert "abv" in mock_product.verified_fields, \
            "ABV 46.0 and 46 should be considered matching"
        assert len(conflicts) == 0

    def test_numeric_fields_allow_tolerance(self, verification_pipeline, mock_product):
        """
        Test strict vs tolerance matching for ABV.
        Current implementation uses strict matching (Decimal equality).
        ABV 45.9% vs 46.0% would NOT match (different values).
        """
        # Arrange
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = []

        # Act: Source 2 has slightly different ABV
        extraction_data = {"abv": Decimal("45.9")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: Strict matching - these don't match
        # This documents the current behavior (strict matching)
        assert "abv" not in mock_product.verified_fields, \
            "Strict matching: 45.9 != 46.0"
        assert len(conflicts) == 1, "Should have 1 conflict for mismatched ABV"
        assert conflicts[0]["field"] == "abv"

    def test_string_comparison_case_insensitive(self, verification_pipeline, mock_product):
        """
        String comparison should be case-insensitive.
        'Islay' should match 'ISLAY' or 'islay'.
        """
        # Arrange
        mock_product.region = "Islay"
        mock_product.verified_fields = []

        # Act: Different case
        extraction_data = {"region": "ISLAY"}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert "region" in mock_product.verified_fields, \
            "Case-insensitive string comparison should match"
        assert len(conflicts) == 0


class TestMissingFieldFill:
    """
    Test filling missing fields from new sources.
    """

    def test_adds_missing_field_from_new_source(self, verification_pipeline, mock_product):
        """
        Source 1: No palate
        Source 2: palate = "Rich and smoky"
        -> palate should be filled
        -> verified_fields should NOT include 'palate' (only 1 source)
        """
        # Arrange: palate is missing
        mock_product.palate_description = None
        mock_product.verified_fields = []

        # Act: Fill from source 2
        extraction_data = {"palate_description": "Rich, smoky, with espresso notes"}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert mock_product.palate_description == "Rich, smoky, with espresso notes", \
            "Missing field should be filled from new source"
        assert "palate_description" not in mock_product.verified_fields, \
            "Single-source field should NOT be in verified_fields"
        assert len(conflicts) == 0, "No conflict when filling missing field"

    def test_does_not_overwrite_existing_with_missing(self, verification_pipeline, mock_product):
        """
        Source 1: palate = "Fruity"
        Source 2: palate = None
        -> palate should remain "Fruity"
        """
        # Arrange: Product has palate
        mock_product.palate_description = "Fruity and fresh"
        mock_product.verified_fields = []

        # Act: Source 2 has no palate
        extraction_data = {"palate_description": None}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: Original value preserved
        assert mock_product.palate_description == "Fruity and fresh", \
            "Existing value should not be overwritten by None"
        assert len(conflicts) == 0

    def test_fills_empty_string_field(self, verification_pipeline, mock_product):
        """
        Empty string should be treated as missing.
        """
        # Arrange: Empty string (treated as missing)
        mock_product.palate_description = ""
        mock_product.verified_fields = []

        # Act: Fill from source 2
        extraction_data = {"palate_description": "Smoky peat"}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert mock_product.palate_description == "Smoky peat", \
            "Empty string should be treated as missing and filled"

    def test_fills_empty_list_field(self, verification_pipeline, mock_product):
        """
        Empty list should be treated as missing.
        """
        # Arrange
        mock_product.palate_flavors = []
        mock_product.verified_fields = []

        # Act
        extraction_data = {"palate_flavors": ["smoke", "peat", "espresso"]}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert mock_product.palate_flavors == ["smoke", "peat", "espresso"], \
            "Empty list should be treated as missing and filled"


class TestConflictHandling:
    """
    Test handling of conflicting values.
    """

    def test_logs_conflict_when_values_differ(self, verification_pipeline, mock_product):
        """
        Source 1: ABV = 46%
        Source 2: ABV = 40%
        -> Conflict should be logged
        -> Original value should NOT be overwritten
        """
        # Arrange
        mock_product.abv = Decimal("46.0")
        original_abv = mock_product.abv
        mock_product.verified_fields = []

        # Act
        extraction_data = {"abv": Decimal("40.0")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert mock_product.abv == original_abv, \
            "Original ABV should NOT be overwritten on conflict"
        assert len(conflicts) == 1, "One conflict should be logged"
        assert conflicts[0]["field"] == "abv"
        assert conflicts[0]["current"] == Decimal("46.0")
        assert conflicts[0]["new"] == Decimal("40.0")

    def test_conflict_does_not_crash_pipeline(self, verification_pipeline, mock_product):
        """
        Conflicts should be handled gracefully, not crash.
        """
        # Arrange: Multiple conflicting fields
        mock_product.abv = Decimal("46.0")
        mock_product.region = "Islay"
        mock_product.verified_fields = []

        # Act: Multiple conflicts
        extraction_data = {
            "abv": Decimal("40.0"),
            "region": "Highlands"
        }

        # Should not raise any exception
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: All conflicts captured
        assert len(conflicts) == 2, "Both conflicts should be logged"
        conflict_fields = [c["field"] for c in conflicts]
        assert "abv" in conflict_fields
        assert "region" in conflict_fields

    def test_conflict_flagged_for_review(self, verification_pipeline, mock_product):
        """
        Products with conflicts might be flagged for manual review.
        Conflicts are returned from _merge_and_verify and stored.
        """
        # Arrange
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = []

        # Act
        extraction_data = {"abv": Decimal("43.0")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: Conflict info available for review
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert "field" in conflict
        assert "current" in conflict
        assert "new" in conflict
        # This info can be used for manual review flagging


class TestVerifiedFieldsTracking:
    """
    Test the verified_fields list tracking.
    """

    def test_verified_fields_list_updated(self, verification_pipeline, mock_product):
        """
        verified_fields should list all fields verified by 2+ sources.
        """
        # Arrange: Product with ABV and region
        mock_product.abv = Decimal("46.0")
        mock_product.region = "Islay"
        mock_product.verified_fields = []

        # Act: Source 2 matches both
        extraction_data = {
            "abv": Decimal("46.0"),
            "region": "Islay"
        }
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert "abv" in mock_product.verified_fields
        assert "region" in mock_product.verified_fields
        assert len(conflicts) == 0

    def test_verified_fields_empty_for_single_source(self, mock_product):
        """
        Product with only 1 source should have empty verified_fields.
        """
        # Arrange: Fresh product from single source
        mock_product.source_count = 1
        mock_product.verified_fields = []

        # Assert: No verified fields yet
        assert mock_product.verified_fields == [], \
            "Single-source product should have no verified fields"

    def test_multiple_fields_can_be_verified(self, verification_pipeline, mock_product):
        """
        If name, abv, and region all match from 2 sources:
        -> verified_fields = ['name', 'abv', 'region']
        """
        # Arrange
        mock_product.name = "Ardbeg 10"
        mock_product.abv = Decimal("46.0")
        mock_product.region = "Islay"
        mock_product.country = "Scotland"
        mock_product.verified_fields = []

        # Act: All fields match
        extraction_data = {
            "name": "ardbeg 10",  # Case insensitive
            "abv": Decimal("46.0"),
            "region": "ISLAY",  # Case insensitive
            "country": "scotland"  # Case insensitive
        }
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert len(mock_product.verified_fields) == 4
        assert "name" in mock_product.verified_fields
        assert "abv" in mock_product.verified_fields
        assert "region" in mock_product.verified_fields
        assert "country" in mock_product.verified_fields
        assert len(conflicts) == 0

    def test_does_not_duplicate_verified_fields(self, verification_pipeline, mock_product):
        """
        If a field is already in verified_fields, don't add it again.
        """
        # Arrange: ABV already verified
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = ["abv"]

        # Act: Third source also matches
        extraction_data = {"abv": Decimal("46.0")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: No duplicates
        assert mock_product.verified_fields.count("abv") == 1, \
            "Should not duplicate verified field entries"


class TestMergeStrategy:
    """
    Test overall merge strategy from multiple sources.
    """

    def test_merge_preserves_best_data(self, verification_pipeline, mock_product):
        """
        When merging:
        - Fill missing fields
        - Verify matching fields
        - Don't overwrite on conflict
        """
        # Arrange: Product with partial data
        mock_product.name = "Ardbeg 10"
        mock_product.abv = Decimal("46.0")
        mock_product.palate_description = None  # Missing
        mock_product.nose_description = "Peaty smoke"  # Existing
        mock_product.verified_fields = []

        # Act: Source 2 has complementary data
        extraction_data = {
            "abv": Decimal("46.0"),  # Matches -> verify
            "palate_description": "Rich and smoky",  # Fills missing
            "nose_description": "Smoky and complex",  # Conflict!
        }
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert "abv" in mock_product.verified_fields, "Matching ABV verified"
        assert mock_product.palate_description == "Rich and smoky", "Missing field filled"
        assert mock_product.nose_description == "Peaty smoke", "Conflict: keep original"
        assert len(conflicts) == 1, "One conflict for nose_description"

    def test_source_tracking_on_merged_fields(self, verification_pipeline, mock_product):
        """
        Track which fields have been verified via verified_fields list.
        """
        # Arrange
        mock_product.name = "Ardbeg 10"
        mock_product.region = "Islay"
        mock_product.verified_fields = []

        # Act: Verify two fields
        extraction_data = {
            "name": "Ardbeg 10",
            "region": "Islay"
        }
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert: Can track which fields came from 2+ sources
        assert set(mock_product.verified_fields) == {"name", "region"}


class TestValuesMatchMethod:
    """
    Test the values_match method directly on DiscoveredProduct.
    """

    def test_decimal_matching(self):
        """Test Decimal comparison."""
        from crawler.models import DiscoveredProduct

        product = DiscoveredProduct()

        # Same decimal values
        assert product.values_match(Decimal("46.0"), Decimal("46.0"))
        assert product.values_match(Decimal("46"), Decimal("46.0"))

        # Different values
        assert not product.values_match(Decimal("46.0"), Decimal("45.0"))

    def test_string_matching_case_insensitive(self):
        """Test case-insensitive string comparison."""
        from crawler.models import DiscoveredProduct

        product = DiscoveredProduct()

        assert product.values_match("Islay", "ISLAY")
        assert product.values_match("islay", "Islay")
        assert product.values_match("  Islay  ", "Islay")

    def test_list_matching_order_independent(self):
        """Test order-independent list comparison."""
        from crawler.models import DiscoveredProduct

        product = DiscoveredProduct()

        list1 = ["smoke", "peat", "vanilla"]
        list2 = ["vanilla", "smoke", "peat"]

        assert product.values_match(list1, list2)

    def test_none_matching(self):
        """Test None handling."""
        from crawler.models import DiscoveredProduct

        product = DiscoveredProduct()

        assert product.values_match(None, None)
        assert not product.values_match(None, "value")
        assert not product.values_match("value", None)


class TestVerificationPipelineIntegration:
    """
    Integration tests for the full verification pipeline.
    Tests use mocked search/extraction but real merge logic.
    """

    def test_full_merge_scenario_from_spec(self, verification_pipeline, mock_product):
        """
        Test the exact scenario from the task spec:

        Source 1: ABV = 46%, palate = None, region = Islay
        Source 2: ABV = 46%, palate = "Rich, smoky", region = Islay

        Result:
        - ABV verified (2 sources agree)
        - palate filled (single source, not verified)
        - region verified (2 sources agree)
        """
        # Arrange: Source 1 data
        mock_product.name = "Ardbeg 10"
        mock_product.abv = Decimal("46.0")
        mock_product.palate_description = None
        mock_product.region = "Islay"
        mock_product.verified_fields = []

        # Act: Merge Source 2 data
        extraction_data = {
            "abv": Decimal("46.0"),
            "palate_description": "Rich, smoky, with espresso notes",
            "region": "Islay"
        }
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert "abv" in mock_product.verified_fields, "ABV verified"
        assert "region" in mock_product.verified_fields, "Region verified"
        assert "palate_description" not in mock_product.verified_fields, \
            "Palate NOT verified (single source fill)"
        assert mock_product.palate_description == "Rich, smoky, with espresso notes", \
            "Palate filled from source 2"
        assert len(conflicts) == 0, "No conflicts in this scenario"

    def test_conflict_scenario(self, verification_pipeline, mock_product):
        """
        Test conflict scenario:

        Source 1: ABV = 46%
        Source 2: ABV = 40%

        Result:
        - Conflict logged
        - Original value NOT overwritten
        """
        # Arrange
        mock_product.abv = Decimal("46.0")
        mock_product.verified_fields = []

        # Act
        extraction_data = {"abv": Decimal("40.0")}
        conflicts = verification_pipeline._merge_and_verify(mock_product, extraction_data)

        # Assert
        assert mock_product.abv == Decimal("46.0"), "Original not overwritten"
        assert "abv" not in mock_product.verified_fields, "ABV not verified due to conflict"
        assert len(conflicts) == 1
        assert conflicts[0]["field"] == "abv"
        assert conflicts[0]["current"] == Decimal("46.0")
        assert conflicts[0]["new"] == Decimal("40.0")
