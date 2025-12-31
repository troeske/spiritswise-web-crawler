"""
Tests for ContentProcessor Individual Column Population.

RECT-001: Update ContentProcessor Save Logic for Individual Columns

These tests verify that the ContentProcessor extracts fields from
AI Enhancement response and populates individual DiscoveredProduct
columns instead of only dumping everything into JSONFields.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlerSource,
    SourceCategory,
)
from crawler.services.content_processor import (
    ContentProcessor,
    ProcessingResult,
    extract_individual_fields,
    _safe_str,
    _safe_float,
    _safe_int,
    _safe_list,
    FIELD_MAPPING,
)
from crawler.services.ai_client import EnhancementResult


# =============================================================================
# Unit Tests for Type Converters (No DB needed)
# =============================================================================

class TestSafeTypeConverters:
    """Unit tests for safe type conversion functions."""

    def test_safe_str_with_valid_string(self):
        """Valid string should be returned as-is."""
        assert _safe_str("Glenfiddich 18") == "Glenfiddich 18"

    def test_safe_str_with_whitespace(self):
        """String with leading/trailing whitespace should be trimmed."""
        assert _safe_str("  Glenfiddich 18  ") == "Glenfiddich 18"

    def test_safe_str_with_none(self):
        """None should return None."""
        assert _safe_str(None) is None

    def test_safe_str_with_empty_string(self):
        """Empty string should return None."""
        assert _safe_str("") is None
        assert _safe_str("   ") is None

    def test_safe_float_with_valid_float(self):
        """Valid float should be returned."""
        assert _safe_float(43.0) == 43.0

    def test_safe_float_with_valid_int(self):
        """Int should be converted to float."""
        assert _safe_float(43) == 43.0

    def test_safe_float_with_string(self):
        """String number should be converted to float."""
        assert _safe_float("43.0") == 43.0
        assert _safe_float("  43.5  ") == 43.5

    def test_safe_float_with_none(self):
        """None should return None."""
        assert _safe_float(None) is None

    def test_safe_float_with_empty_string(self):
        """Empty string should return None."""
        assert _safe_float("") is None
        assert _safe_float("   ") is None

    def test_safe_float_with_invalid_string(self):
        """Invalid string should return None."""
        assert _safe_float("not-a-number") is None

    def test_safe_int_with_valid_int(self):
        """Valid int should be returned."""
        assert _safe_int(18) == 18

    def test_safe_int_with_valid_float(self):
        """Float should be truncated to int."""
        assert _safe_int(18.5) == 18

    def test_safe_int_with_string(self):
        """String number should be converted to int."""
        assert _safe_int("18") == 18
        assert _safe_int("  18  ") == 18
        assert _safe_int("18.0") == 18  # Handle decimal strings

    def test_safe_int_with_none(self):
        """None should return None."""
        assert _safe_int(None) is None

    def test_safe_int_with_empty_string(self):
        """Empty string should return None."""
        assert _safe_int("") is None
        assert _safe_int("   ") is None

    def test_safe_int_with_invalid_string(self):
        """Invalid string should return None."""
        assert _safe_int("not-a-number") is None

    def test_safe_list_with_valid_list(self):
        """Valid list should be returned as-is."""
        assert _safe_list(["oak", "honey"]) == ["oak", "honey"]

    def test_safe_list_with_none(self):
        """None should return empty list."""
        assert _safe_list(None) == []

    def test_safe_list_with_comma_separated_string(self):
        """Comma-separated string should be parsed to list."""
        assert _safe_list("oak, honey, vanilla") == ["oak", "honey", "vanilla"]

    def test_safe_list_with_empty_string(self):
        """Empty string should return empty list."""
        assert _safe_list("") == []
        assert _safe_list("   ") == []


# =============================================================================
# Unit Tests for Field Extraction (No DB needed)
# =============================================================================

class TestExtractIndividualFields:
    """Unit tests for extract_individual_fields function."""

    def test_extracts_core_fields(self):
        """Core fields should be extracted and converted."""
        extracted_data = {
            "name": "Glenfiddich 18 Year Old",
            "abv": "43.0",
            "age_statement": "18",
            "region": "Speyside",
            "country": "Scotland",
            "volume_ml": "700",
            "gtin": "5010327325125",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["name"] == "Glenfiddich 18 Year Old"
        assert fields["abv"] == 43.0
        assert fields["age_statement"] == 18
        assert fields["region"] == "Speyside"
        assert fields["country"] == "Scotland"
        assert fields["volume_ml"] == 700
        assert fields["gtin"] == "5010327325125"

    def test_extracts_tasting_profile_appearance(self):
        """Tasting profile appearance fields should be extracted."""
        extracted_data = {
            "color_description": "Deep amber with golden highlights",
            "color_intensity": "7",
            "clarity": "brilliant",
            "viscosity": "medium",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["color_description"] == "Deep amber with golden highlights"
        assert fields["color_intensity"] == 7
        assert fields["clarity"] == "brilliant"
        assert fields["viscosity"] == "medium"

    def test_extracts_tasting_profile_nose(self):
        """Tasting profile nose/aroma fields should be extracted."""
        extracted_data = {
            "nose_description": "Rich oak with hints of dried fruit",
            "primary_aromas": ["oak", "honey", "dried fruit"],
            "primary_intensity": "8",
            "secondary_aromas": ["vanilla", "almond"],
            "aroma_evolution": "Opens with honey, evolves to oak",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["nose_description"] == "Rich oak with hints of dried fruit"
        assert fields["primary_aromas"] == ["oak", "honey", "dried fruit"]
        assert fields["primary_intensity"] == 8
        assert fields["secondary_aromas"] == ["vanilla", "almond"]
        assert fields["aroma_evolution"] == "Opens with honey, evolves to oak"

    def test_extracts_tasting_profile_palate(self):
        """Tasting profile palate fields should be extracted."""
        extracted_data = {
            "palate_flavors": ["toffee", "cinnamon", "dark chocolate"],
            "initial_taste": "Sweet honey and toffee",
            "mid_palate_evolution": "Develops spice notes",
            "flavor_intensity": "7",
            "complexity": "8",
            "mouthfeel": "creamy",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["palate_flavors"] == ["toffee", "cinnamon", "dark chocolate"]
        assert fields["initial_taste"] == "Sweet honey and toffee"
        assert fields["mid_palate_evolution"] == "Develops spice notes"
        assert fields["flavor_intensity"] == 7
        assert fields["complexity"] == 8
        assert fields["mouthfeel"] == "creamy"

    def test_extracts_tasting_profile_finish(self):
        """Tasting profile finish fields should be extracted."""
        extracted_data = {
            "finish_length": "8",
            "warmth": "6",
            "dryness": "4",
            "finish_flavors": ["oak", "spice", "tobacco"],
            "finish_evolution": "Lingering oak with subtle smoke",
            "final_notes": "Long, elegant finish",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["finish_length"] == 8
        assert fields["warmth"] == 6
        assert fields["dryness"] == 4
        assert fields["finish_flavors"] == ["oak", "spice", "tobacco"]
        assert fields["finish_evolution"] == "Lingering oak with subtle smoke"
        assert fields["final_notes"] == "Long, elegant finish"

    def test_handles_null_values_gracefully(self):
        """Null values should not crash extraction."""
        extracted_data = {
            "name": "Mystery Whiskey",
            "abv": None,
            "age_statement": None,
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["name"] == "Mystery Whiskey"
        assert "abv" not in fields  # None values excluded
        assert "age_statement" not in fields

    def test_handles_empty_strings_gracefully(self):
        """Empty strings should be treated as None."""
        extracted_data = {
            "name": "Mystery Whiskey",
            "abv": "",
            "age_statement": "",
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["name"] == "Mystery Whiskey"
        assert "abv" not in fields
        assert "age_statement" not in fields

    def test_list_fields_default_to_empty_list(self):
        """List fields should default to empty list when None."""
        extracted_data = {
            "name": "Mystery Whiskey",
            "primary_aromas": None,
            "palate_flavors": None,
        }

        fields = extract_individual_fields(extracted_data)

        assert fields["primary_aromas"] == []
        assert fields["palate_flavors"] == []


# =============================================================================
# Integration Tests (Use DB)
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Content Processor Source",
        slug="test-content-processor-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


class TestDiscoveredProductCreation:
    """Integration tests for DiscoveredProduct creation with individual fields."""

    def test_create_product_with_individual_fields(self, db, sample_source):
        """Product can be created with individual field columns populated."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/test",
            fingerprint="test-fingerprint-001",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Test content</html>",
            raw_content_hash="abc123hash",
            extracted_data={"name": "Test Whiskey"},
            # Individual columns
            name="Glenfiddich 18 Year Old",
            abv=43.0,
            age_statement=18,
            region="Speyside",
            country="Scotland",
            volume_ml=700,
            gtin="5010327325125",
        )

        product.refresh_from_db()

        assert product.name == "Glenfiddich 18 Year Old"
        assert product.abv == 43.0
        assert product.age_statement == 18
        assert product.region == "Speyside"
        assert product.country == "Scotland"
        assert product.volume_ml == 700
        assert product.gtin == "5010327325125"

    def test_create_product_with_tasting_profile(self, db, sample_source):
        """Product can be created with tasting profile fields populated."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/tasting",
            fingerprint="test-fingerprint-002",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Tasting content</html>",
            raw_content_hash="def456hash",
            extracted_data={},
            # Tasting profile
            color_description="Deep amber",
            color_intensity=7,
            clarity="brilliant",
            nose_description="Rich oak notes",
            primary_aromas=["oak", "honey"],
            palate_flavors=["toffee", "cinnamon"],
            finish_length=8,
        )

        product.refresh_from_db()

        assert product.color_description == "Deep amber"
        assert product.color_intensity == 7
        assert product.clarity == "brilliant"
        assert product.nose_description == "Rich oak notes"
        assert product.primary_aromas == ["oak", "honey"]
        assert product.palate_flavors == ["toffee", "cinnamon"]
        assert product.finish_length == 8

    def test_create_product_with_null_optional_fields(self, db, sample_source):
        """Product can be created with null optional fields."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/null",
            fingerprint="test-fingerprint-003",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Null test</html>",
            raw_content_hash="ghi789hash",
            extracted_data={},
            name="NAS Whiskey",
            abv=40.0,
            age_statement=None,  # No Age Statement
        )

        product.refresh_from_db()

        assert product.name == "NAS Whiskey"
        assert product.abv == 40.0
        assert product.age_statement is None


class TestFieldMappingCoverage:
    """Tests to verify field mapping covers all required fields."""

    def test_field_mapping_includes_core_fields(self):
        """Field mapping should include all core product fields."""
        core_fields = ["name", "abv", "age_statement", "region", "country", "volume_ml", "gtin"]
        for field in core_fields:
            assert field in FIELD_MAPPING, f"Missing core field: {field}"

    def test_field_mapping_includes_appearance_fields(self):
        """Field mapping should include appearance/visual fields."""
        appearance_fields = ["color_description", "color_intensity", "clarity", "viscosity"]
        for field in appearance_fields:
            assert field in FIELD_MAPPING, f"Missing appearance field: {field}"

    def test_field_mapping_includes_nose_fields(self):
        """Field mapping should include nose/aroma fields."""
        nose_fields = ["nose_description", "primary_aromas", "primary_intensity", "secondary_aromas", "aroma_evolution"]
        for field in nose_fields:
            assert field in FIELD_MAPPING, f"Missing nose field: {field}"

    def test_field_mapping_includes_palate_fields(self):
        """Field mapping should include palate fields."""
        palate_fields = ["palate_flavors", "initial_taste", "mid_palate_evolution", "flavor_intensity", "complexity", "mouthfeel"]
        for field in palate_fields:
            assert field in FIELD_MAPPING, f"Missing palate field: {field}"

    def test_field_mapping_includes_finish_fields(self):
        """Field mapping should include finish fields."""
        finish_fields = ["finish_length", "warmth", "dryness", "finish_flavors", "finish_evolution", "final_notes"]
        for field in finish_fields:
            assert field in FIELD_MAPPING, f"Missing finish field: {field}"


class TestContentProcessorExtractContent:
    """Tests for ContentProcessor.extract_content method."""

    def test_returns_raw_content_when_empty(self):
        """Should return empty string for empty input."""
        processor = ContentProcessor(ai_client=MagicMock())
        result = processor.extract_content("")
        assert result == ""

    def test_returns_raw_html_when_trafilatura_not_available(self):
        """Should return raw HTML when trafilatura extraction fails."""
        processor = ContentProcessor(ai_client=MagicMock())
        html = "<html><body><p>Test content</p></body></html>"
        with patch("crawler.services.content_processor.TRAFILATURA_AVAILABLE", False):
            result = processor.extract_content(html)
            assert result == html


class TestContentProcessorDetermineProductTypeHint:
    """Tests for ContentProcessor.determine_product_type_hint method."""

    def test_returns_whiskey_for_none_source(self):
        """Should return 'whiskey' when source is None."""
        processor = ContentProcessor(ai_client=MagicMock())
        result = processor.determine_product_type_hint(None)
        assert result == "whiskey"

    def test_returns_first_product_type_from_source(self, db, sample_source):
        """Should return first product type from source configuration."""
        processor = ContentProcessor(ai_client=MagicMock())
        result = processor.determine_product_type_hint(sample_source)
        assert result == "whiskey"

    def test_returns_whiskey_for_empty_product_types(self, db):
        """Should return 'whiskey' when source has no product types."""
        source = CrawlerSource.objects.create(
            name="Empty Source",
            slug="empty-source",
            base_url="https://empty.com",
            category=SourceCategory.COMPETITION,
            product_types=[],
        )
        processor = ContentProcessor(ai_client=MagicMock())
        result = processor.determine_product_type_hint(source)
        assert result == "whiskey"
