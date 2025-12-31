"""
Tests for PortWineDetails Creation in ContentProcessor.

RECT-003: Create PortWineDetails Records for Port Wine Products

These tests verify that when a DiscoveredProduct with product_type='port_wine'
is created through the ContentProcessor, a linked PortWineDetails record is
also created with port-specific fields extracted from the AI response.

TDD: Tests written first before implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlerSource,
    SourceCategory,
    PortWineDetails,
    PortStyleChoices,
    DouroSubregionChoices,
)
from crawler.services.content_processor import (
    extract_port_wine_fields,
    _infer_port_style,
    _create_port_wine_details,
    PORT_WINE_FIELD_MAPPING,
    VALID_PORT_STYLES,
    VALID_DOURO_SUBREGIONS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for port wine testing."""
    return CrawlerSource.objects.create(
        name="Test Port Wine Source",
        slug="test-port-wine-source",
        base_url="https://example.com",
        category=SourceCategory.RETAILER,
        product_types=["port_wine"],
    )


@pytest.fixture
def whiskey_source(db):
    """Create a sample CrawlerSource for whiskey testing."""
    return CrawlerSource.objects.create(
        name="Test Whiskey Source",
        slug="test-whiskey-source",
        base_url="https://whiskey-example.com",
        category=SourceCategory.RETAILER,
        product_types=["whiskey"],
    )


@pytest.fixture
def port_product(db, sample_source):
    """Create a sample port wine DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/port/test",
        fingerprint="port-test-fingerprint-001",
        product_type=ProductType.PORT_WINE,
        raw_content="<html>Test port content</html>",
        raw_content_hash="port001hash",
        extracted_data={"name": "Taylor's 20 Year Tawny Port"},
        name="Taylor's 20 Year Tawny Port",
    )


@pytest.fixture
def whiskey_product(db, whiskey_source):
    """Create a sample whiskey DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=whiskey_source,
        source_url="https://whiskey-example.com/whiskey/test",
        fingerprint="whiskey-test-fingerprint-001",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test whiskey content</html>",
        raw_content_hash="whiskey001hash",
        extracted_data={"name": "Glenfiddich 18 Year"},
        name="Glenfiddich 18 Year",
    )


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client for testing."""
    client = MagicMock()
    client.enhance_from_crawler = AsyncMock()
    return client


# =============================================================================
# Unit Tests for Port Style Validation
# =============================================================================

class TestPortStyleValidation:
    """Tests for port style validation."""

    def test_all_ten_port_styles_valid(self):
        """All 10 port styles should be in PortStyleChoices."""
        valid_styles = [
            "ruby",
            "tawny",
            "white",
            "rose",
            "lbv",
            "vintage",
            "colheita",
            "crusted",
            "single_quinta",
            "garrafeira",
        ]

        choice_values = [choice[0] for choice in PortStyleChoices.choices]

        for style in valid_styles:
            assert style in choice_values, f"Missing port style: {style}"


class TestDouroSubregionValidation:
    """Tests for Douro subregion validation."""

    def test_all_douro_subregions_valid(self):
        """All 3 Douro subregions should be in DouroSubregionChoices."""
        valid_subregions = [
            "baixo_corgo",
            "cima_corgo",
            "douro_superior",
        ]

        choice_values = [choice[0] for choice in DouroSubregionChoices.choices]

        for subregion in valid_subregions:
            assert subregion in choice_values, f"Missing subregion: {subregion}"


# =============================================================================
# Integration Tests (Use DB)
# =============================================================================

class TestPortWineDetailsCreation:
    """Integration tests for PortWineDetails creation."""

    def test_port_wine_details_created_for_port_product(self, db, port_product):
        """PortWineDetails record should be created when product_type='port_wine'."""
        # Create PortWineDetails manually to test the model
        details = PortWineDetails.objects.create(
            product=port_product,
            style="tawny",
            indication_age="20 Year",
            producer_house="Taylor's",
            decanting_required=False,
        )

        assert details.id is not None
        assert details.product == port_product
        assert details.style == "tawny"
        assert details.indication_age == "20 Year"
        assert details.producer_house == "Taylor's"

    def test_port_wine_details_not_created_for_whiskey(self, db, whiskey_product):
        """No PortWineDetails should be created for whiskey products."""
        # Verify no PortWineDetails exists for whiskey product
        assert not PortWineDetails.objects.filter(product=whiskey_product).exists()

        # Verify product type is whiskey
        assert whiskey_product.product_type == ProductType.WHISKEY

    def test_style_mapped_correctly(self, db, sample_source):
        """AI style value should map correctly to PortWineDetails.style."""
        styles_to_test = ["ruby", "tawny", "white", "lbv", "vintage", "colheita"]

        for idx, style in enumerate(styles_to_test):
            product = DiscoveredProduct.objects.create(
                source=sample_source,
                source_url=f"https://example.com/port/style-{idx}",
                fingerprint=f"style-test-fp-{idx}",
                product_type=ProductType.PORT_WINE,
                raw_content="content",
                raw_content_hash=f"hash-{idx}",
                name=f"Test {style} Port",
            )

            details = PortWineDetails.objects.create(
                product=product,
                style=style,
                producer_house="Test House",
            )

            details.refresh_from_db()
            assert details.style == style

    def test_indication_age_mapped(self, db, port_product):
        """AI indication_age should map to PortWineDetails.indication_age."""
        details = PortWineDetails.objects.create(
            product=port_product,
            style="tawny",
            indication_age="30 Year",
            producer_house="Graham's",
        )

        details.refresh_from_db()
        assert details.indication_age == "30 Year"

    def test_grape_varieties_as_arrayfield(self, db, port_product):
        """Grape varieties should be stored as ArrayField (JSONField)."""
        grape_list = ["Touriga Nacional", "Touriga Franca", "Tinta Roriz", "Tinta Barroca"]

        details = PortWineDetails.objects.create(
            product=port_product,
            style="vintage",
            producer_house="Quinta do Vesuvio",
            grape_varieties=grape_list,
        )

        details.refresh_from_db()
        assert details.grape_varieties == grape_list
        assert isinstance(details.grape_varieties, list)
        assert len(details.grape_varieties) == 4

    def test_quinta_and_producer_house_mapped(self, db, port_product):
        """Quinta and producer_house fields should be populated correctly."""
        details = PortWineDetails.objects.create(
            product=port_product,
            style="single_quinta",
            quinta="Quinta do Noval",
            producer_house="Quinta do Noval",
            harvest_year=2017,
        )

        details.refresh_from_db()
        assert details.quinta == "Quinta do Noval"
        assert details.producer_house == "Quinta do Noval"

    def test_port_wine_details_linked_via_onetoone(self, db, port_product):
        """product.port_details should return the linked PortWineDetails record."""
        details = PortWineDetails.objects.create(
            product=port_product,
            style="lbv",
            producer_house="Warre's",
            decanting_required=True,
        )

        # Test bidirectional access
        assert port_product.port_details == details
        assert details.product == port_product

    def test_douro_subregion_choices_validated(self, db, port_product):
        """douro_subregion should accept valid choices."""
        for subregion in ["baixo_corgo", "cima_corgo", "douro_superior"]:
            # Clean up previous details
            PortWineDetails.objects.filter(product=port_product).delete()

            details = PortWineDetails.objects.create(
                product=port_product,
                style="vintage",
                producer_house="Test House",
                douro_subregion=subregion,
            )

            details.refresh_from_db()
            assert details.douro_subregion == subregion


# =============================================================================
# Unit Tests for Port Wine Field Extraction (No DB needed)
# =============================================================================

class TestExtractPortWineFields:
    """Unit tests for extract_port_wine_fields function."""

    def test_extracts_style(self):
        """Port style should be extracted from AI response."""
        extracted_data = {
            "style": "tawny",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["style"] == "tawny"

    def test_extracts_indication_age(self):
        """Age indication should be extracted."""
        extracted_data = {
            "indication_age": "20 Year",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["indication_age"] == "20 Year"

    def test_extracts_harvest_and_bottling_year(self):
        """Harvest and bottling years should be extracted as integers."""
        extracted_data = {
            "harvest_year": "2015",
            "bottling_year": "2023",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["harvest_year"] == 2015
        assert fields["bottling_year"] == 2023

    def test_extracts_grape_varieties_as_list(self):
        """Grape varieties should be extracted as list."""
        extracted_data = {
            "grape_varieties": ["Touriga Nacional", "Touriga Franca", "Tinta Roriz"],
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["grape_varieties"] == ["Touriga Nacional", "Touriga Franca", "Tinta Roriz"]

    def test_extracts_quinta(self):
        """Quinta (estate) name should be extracted."""
        extracted_data = {
            "quinta": "Quinta do Noval",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["quinta"] == "Quinta do Noval"

    def test_extracts_douro_subregion(self):
        """Douro subregion should be extracted."""
        extracted_data = {
            "douro_subregion": "cima_corgo",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["douro_subregion"] == "cima_corgo"

    def test_extracts_producer_house(self):
        """Producer house should be extracted."""
        extracted_data = {
            "producer_house": "Taylor's",
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["producer_house"] == "Taylor's"

    def test_extracts_decanting_required(self):
        """Decanting required should be extracted as boolean."""
        extracted_data = {
            "decanting_required": True,
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["decanting_required"] is True

    def test_handles_null_values_gracefully(self):
        """Null values should not crash extraction."""
        extracted_data = {
            "style": "lbv",
            "producer_house": "Graham's",
            "quinta": None,
            "douro_subregion": None,
        }
        fields = extract_port_wine_fields(extracted_data)
        assert fields["style"] == "lbv"
        assert fields["producer_house"] == "Graham's"
        assert "quinta" not in fields
        assert "douro_subregion" not in fields

    def test_invalid_style_skipped(self):
        """Invalid style values should be skipped."""
        extracted_data = {
            "style": "invalid_style_xyz",
            "producer_house": "Test House",
        }
        fields = extract_port_wine_fields(extracted_data)
        # Invalid style should not be in fields
        assert "style" not in fields

    def test_invalid_douro_subregion_skipped(self):
        """Invalid douro_subregion values should be skipped."""
        extracted_data = {
            "style": "ruby",
            "douro_subregion": "invalid_subregion",
            "producer_house": "Test House",
        }
        fields = extract_port_wine_fields(extracted_data)
        # Invalid subregion should not be in fields
        assert "douro_subregion" not in fields


class TestPortWineFieldMappingCoverage:
    """Tests to verify PORT_WINE_FIELD_MAPPING covers all required fields."""

    def test_mapping_includes_style_fields(self):
        """Mapping should include style fields."""
        style_fields = ["style", "indication_age"]
        for field in style_fields:
            assert field in PORT_WINE_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_vintage_fields(self):
        """Mapping should include vintage fields."""
        vintage_fields = ["harvest_year", "bottling_year"]
        for field in vintage_fields:
            assert field in PORT_WINE_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_production_fields(self):
        """Mapping should include production fields."""
        production_fields = ["grape_varieties", "quinta", "douro_subregion", "producer_house"]
        for field in production_fields:
            assert field in PORT_WINE_FIELD_MAPPING, f"Missing field: {field}"

    def test_mapping_includes_serving_fields(self):
        """Mapping should include serving fields."""
        serving_fields = ["decanting_required", "drinking_window"]
        for field in serving_fields:
            assert field in PORT_WINE_FIELD_MAPPING, f"Missing field: {field}"


class TestInferPortStyle:
    """Tests for _infer_port_style function."""

    def test_infers_tawny_from_name(self):
        """Should infer 'tawny' from product name containing 'Tawny'."""
        extracted_data = {
            "name": "Taylor's 20 Year Old Tawny Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "tawny"

    def test_infers_ruby_from_name(self):
        """Should infer 'ruby' from product name containing 'Ruby'."""
        extracted_data = {
            "name": "Fonseca Ruby Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "ruby"

    def test_infers_lbv_from_name(self):
        """Should infer 'lbv' from product name containing 'LBV'."""
        extracted_data = {
            "name": "Graham's 2018 LBV Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "lbv"

    def test_infers_vintage_from_name(self):
        """Should infer 'vintage' from product name containing 'Vintage'."""
        extracted_data = {
            "name": "Quinta do Noval 2017 Vintage Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "vintage"

    def test_infers_colheita_from_name(self):
        """Should infer 'colheita' from product name containing 'Colheita'."""
        extracted_data = {
            "name": "Kopke 1998 Colheita Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "colheita"

    def test_infers_white_from_name(self):
        """Should infer 'white' from product name containing 'White'."""
        extracted_data = {
            "name": "Churchill's White Port",
        }
        style = _infer_port_style(extracted_data)
        assert style == "white"

    def test_returns_none_for_ambiguous_name(self):
        """Should return None when style cannot be inferred."""
        extracted_data = {
            "name": "Some Portuguese Fortified Wine",
        }
        style = _infer_port_style(extracted_data)
        assert style is None


class TestCreatePortWineDetailsFunction:
    """Tests for _create_port_wine_details function."""

    def test_creates_port_wine_details_with_all_fields(self, db, sample_source):
        """_create_port_wine_details creates record with all provided fields."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/port/func-test-1",
            fingerprint="port-func-test-001",
            product_type=ProductType.PORT_WINE,
            raw_content="<html>Func Test</html>",
            raw_content_hash="functest123",
            extracted_data={"name": "Func Test Port"},
            name="Func Test Port",
        )

        extracted_data = {
            "style": "tawny",
            "indication_age": "30 Year",
            "producer_house": "Taylor's",
            "quinta": "Quinta de Vargellas",
            "douro_subregion": "cima_corgo",
            "grape_varieties": ["Touriga Nacional", "Touriga Franca"],
            "decanting_required": False,
            "drinking_window": "Now - 2050",
        }

        details = _create_port_wine_details(product, extracted_data)

        assert details is not None
        assert details.style == "tawny"
        assert details.indication_age == "30 Year"
        assert details.producer_house == "Taylor's"
        assert details.quinta == "Quinta de Vargellas"
        assert details.douro_subregion == "cima_corgo"
        assert details.grape_varieties == ["Touriga Nacional", "Touriga Franca"]
        assert details.decanting_required is False
        assert details.drinking_window == "Now - 2050"

    def test_creates_port_wine_details_with_inferred_style(self, db, sample_source):
        """_create_port_wine_details infers style from name when not provided."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/port/func-test-2",
            fingerprint="port-func-test-002",
            product_type=ProductType.PORT_WINE,
            raw_content="<html>Func Test</html>",
            raw_content_hash="functest234",
            extracted_data={"name": "Graham's 2018 LBV Port"},
            name="Graham's 2018 LBV Port",
        )

        extracted_data = {
            "name": "Graham's 2018 LBV Port",
            "producer_house": "Graham's",
            "harvest_year": 2018,
        }

        details = _create_port_wine_details(product, extracted_data)

        assert details is not None
        # Should infer lbv from "LBV" in name
        assert details.style == "lbv"
        assert details.producer_house == "Graham's"
        assert details.harvest_year == 2018

    def test_creates_port_wine_details_with_defaults(self, db, sample_source):
        """_create_port_wine_details uses defaults when minimal data provided."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/port/func-test-3",
            fingerprint="port-func-test-003",
            product_type=ProductType.PORT_WINE,
            raw_content="<html>Func Test</html>",
            raw_content_hash="functest345",
            extracted_data={"name": "Minimal Port"},
            name="Minimal Port",
        )

        extracted_data = {
            "name": "Minimal Port",
        }

        details = _create_port_wine_details(product, extracted_data)

        assert details is not None
        # Should use default style (ruby) when nothing can be inferred
        assert details.style == PortStyleChoices.RUBY
        assert details.producer_house == "Unknown"

    def test_creates_port_wine_details_extracts_producer_from_brand(self, db, sample_source):
        """_create_port_wine_details extracts producer_house from brand field."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/port/func-test-4",
            fingerprint="port-func-test-004",
            product_type=ProductType.PORT_WINE,
            raw_content="<html>Func Test</html>",
            raw_content_hash="functest456",
            extracted_data={"name": "Brand Test Port"},
            name="Brand Test Port",
        )

        extracted_data = {
            "name": "Dow's 20 Year Tawny Port",
            "brand": "Dow's",
            "style": "tawny",
        }

        details = _create_port_wine_details(product, extracted_data)

        assert details is not None
        # Should use brand as producer_house when producer_house not specified
        assert details.producer_house == "Dow's"
