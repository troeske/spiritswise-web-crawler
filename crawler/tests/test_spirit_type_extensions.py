"""
Tests for Spirit-Type Extension Models.

Task Group 3: Spirit-Type Extension Models Implementation
These tests verify the WhiskeyDetails and PortWineDetails models
that extend DiscoveredProduct via OneToOne FK pattern.

TDD: Tests written first before model implementation.
"""

import pytest
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from crawler.models import (
    DiscoveredProduct,
    DiscoveredBrand,
    ProductType,
    CrawlerSource,
    SourceCategory,
)


@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Spirit Source",
        slug="test-spirit-source",
        base_url="https://example.com",
        category=SourceCategory.RETAILER,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for testing."""
    return DiscoveredBrand.objects.create(
        name="Test Distillery",
        country="Scotland",
        region="Speyside",
    )


@pytest.fixture
def whiskey_product(db, sample_source, sample_brand):
    """Create a sample whiskey DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/whiskey/test",
        fingerprint="whiskey-test-fingerprint-123",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test whiskey content</html>",
        raw_content_hash="whiskey123hash",
        extracted_data={"name": "Test Whiskey 18 Year", "brand": "Test Distillery"},
        name="Test Whiskey 18 Year",
        brand=sample_brand,
        abv=43.0,
        age_statement=18,
    )


@pytest.fixture
def port_product(db, sample_source):
    """Create a sample port wine DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/port/test",
        fingerprint="port-test-fingerprint-456",
        product_type=ProductType.PORT_WINE,
        raw_content="<html>Test port content</html>",
        raw_content_hash="port456hash",
        extracted_data={"name": "Test Tawny Port 20 Year", "producer": "Test House"},
        name="Test Tawny Port 20 Year",
    )


class TestWhiskeyDetailsOneToOneRelationship:
    """Tests for WhiskeyDetails OneToOne relationship to DiscoveredProduct."""

    def test_whiskey_details_creation_with_product(self, whiskey_product):
        """WhiskeyDetails should be created and linked to DiscoveredProduct."""
        from crawler.models import WhiskeyDetails

        details = WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="scotch_single_malt",
            whiskey_country="Scotland",
            whiskey_region="Speyside",
            distillery="Test Distillery",
        )

        assert details.id is not None
        assert details.product == whiskey_product
        assert details.whiskey_type == "scotch_single_malt"

    def test_whiskey_details_accessible_via_related_name(self, whiskey_product):
        """WhiskeyDetails should be accessible via product.whiskey_details."""
        from crawler.models import WhiskeyDetails

        WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="scotch_single_malt",
            whiskey_country="Scotland",
            whiskey_region="Speyside",
            distillery="Test Distillery",
        )

        # Access via related_name
        assert whiskey_product.whiskey_details is not None
        assert whiskey_product.whiskey_details.whiskey_type == "scotch_single_malt"

    def test_whiskey_details_one_to_one_enforced(self, whiskey_product):
        """Only one WhiskeyDetails should be allowed per DiscoveredProduct."""
        from crawler.models import WhiskeyDetails

        WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="scotch_single_malt",
            whiskey_country="Scotland",
            whiskey_region="Speyside",
            distillery="Test Distillery",
        )

        # Attempting to create another should raise IntegrityError
        with pytest.raises(IntegrityError):
            WhiskeyDetails.objects.create(
                product=whiskey_product,
                whiskey_type="bourbon",
                whiskey_country="USA",
                whiskey_region="Kentucky",
                distillery="Another Distillery",
            )

    def test_whiskey_details_cascade_delete(self, whiskey_product):
        """WhiskeyDetails should be deleted when product is deleted."""
        from crawler.models import WhiskeyDetails

        details = WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="scotch_single_malt",
            whiskey_country="Scotland",
            whiskey_region="Speyside",
            distillery="Test Distillery",
        )
        details_id = details.id

        # Delete the product
        whiskey_product.delete()

        # WhiskeyDetails should also be deleted
        assert not WhiskeyDetails.objects.filter(id=details_id).exists()


class TestPortWineDetailsOneToOneRelationship:
    """Tests for PortWineDetails OneToOne relationship to DiscoveredProduct."""

    def test_port_details_creation_with_product(self, port_product):
        """PortWineDetails should be created and linked to DiscoveredProduct."""
        from crawler.models import PortWineDetails

        details = PortWineDetails.objects.create(
            product=port_product,
            style="tawny",
            indication_age="20 Year",
            producer_house="Test House",
            decanting_required=False,
        )

        assert details.id is not None
        assert details.product == port_product
        assert details.style == "tawny"

    def test_port_details_accessible_via_related_name(self, port_product):
        """PortWineDetails should be accessible via product.port_details."""
        from crawler.models import PortWineDetails

        PortWineDetails.objects.create(
            product=port_product,
            style="vintage",
            harvest_year=2007,
            producer_house="Test House",
            decanting_required=True,
        )

        # Access via related_name
        assert port_product.port_details is not None
        assert port_product.port_details.style == "vintage"
        assert port_product.port_details.harvest_year == 2007

    def test_port_details_one_to_one_enforced(self, port_product):
        """Only one PortWineDetails should be allowed per DiscoveredProduct."""
        from crawler.models import PortWineDetails

        PortWineDetails.objects.create(
            product=port_product,
            style="tawny",
            producer_house="Test House",
            decanting_required=False,
        )

        # Attempting to create another should raise IntegrityError
        with pytest.raises(IntegrityError):
            PortWineDetails.objects.create(
                product=port_product,
                style="ruby",
                producer_house="Another House",
                decanting_required=True,
            )

    def test_port_details_cascade_delete(self, port_product):
        """PortWineDetails should be deleted when product is deleted."""
        from crawler.models import PortWineDetails

        details = PortWineDetails.objects.create(
            product=port_product,
            style="lbv",
            producer_house="Test House",
            decanting_required=True,
        )
        details_id = details.id

        # Delete the product
        port_product.delete()

        # PortWineDetails should also be deleted
        assert not PortWineDetails.objects.filter(id=details_id).exists()


class TestWhiskeyTypeChoicesValidation:
    """Tests for whiskey_type choices validation on WhiskeyDetails."""

    def test_valid_whiskey_types(self, whiskey_product):
        """All 14 valid whiskey types should be accepted."""
        from crawler.models import WhiskeyDetails, WhiskeyTypeChoices

        valid_types = [
            "scotch_single_malt",
            "scotch_blend",
            "bourbon",
            "tennessee",
            "rye",
            "irish_single_pot",
            "irish_single_malt",
            "irish_blend",
            "japanese",
            "canadian",
            "indian",
            "taiwanese",
            "australian",
            "american_single_malt",
            "world_whiskey",
        ]

        # Verify all expected types are in the choices
        choice_values = [choice[0] for choice in WhiskeyTypeChoices.choices]
        for whiskey_type in valid_types:
            assert whiskey_type in choice_values, f"{whiskey_type} not in WhiskeyTypeChoices"

    def test_whiskey_type_stores_correctly(self, db, sample_source, sample_brand):
        """Each whiskey type should store and retrieve correctly."""
        from crawler.models import WhiskeyDetails

        test_types = [
            ("scotch_single_malt", "Scotland", "Speyside"),
            ("bourbon", "USA", "Kentucky"),
            ("japanese", "Japan", "Hokkaido"),
            ("irish_single_pot", "Ireland", "Cork"),
            ("taiwanese", "Taiwan", "Kavalan"),
        ]

        for idx, (w_type, country, region) in enumerate(test_types):
            product = DiscoveredProduct.objects.create(
                source=sample_source,
                source_url=f"https://example.com/whiskey/type-test-{idx}",
                fingerprint=f"type-test-fp-{idx}",
                product_type=ProductType.WHISKEY,
                raw_content="content",
                raw_content_hash=f"hash-type-{idx}",
                name=f"Test {w_type} Whiskey",
            )

            details = WhiskeyDetails.objects.create(
                product=product,
                whiskey_type=w_type,
                whiskey_country=country,
                whiskey_region=region,
                distillery="Test Distillery",
            )

            details.refresh_from_db()
            assert details.whiskey_type == w_type
            assert details.whiskey_country == country
            assert details.whiskey_region == region


class TestPortStyleChoicesValidation:
    """Tests for port style choices validation on PortWineDetails."""

    def test_valid_port_styles(self, port_product):
        """All 10 valid port styles should be accepted."""
        from crawler.models import PortWineDetails, PortStyleChoices

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

        # Verify all expected styles are in the choices
        choice_values = [choice[0] for choice in PortStyleChoices.choices]
        for style in valid_styles:
            assert style in choice_values, f"{style} not in PortStyleChoices"

    def test_port_style_stores_correctly(self, db, sample_source):
        """Each port style should store and retrieve correctly."""
        from crawler.models import PortWineDetails

        test_styles = [
            ("tawny", "20 Year", None, False),
            ("vintage", None, 2007, True),
            ("lbv", None, 2018, True),
            ("colheita", "Single Harvest", 1997, False),
            ("ruby", None, None, False),
        ]

        for idx, (style, indication_age, harvest_year, decanting) in enumerate(test_styles):
            product = DiscoveredProduct.objects.create(
                source=sample_source,
                source_url=f"https://example.com/port/style-test-{idx}",
                fingerprint=f"style-test-fp-{idx}",
                product_type=ProductType.PORT_WINE,
                raw_content="content",
                raw_content_hash=f"hash-style-{idx}",
                name=f"Test {style} Port",
            )

            details = PortWineDetails.objects.create(
                product=product,
                style=style,
                indication_age=indication_age,
                harvest_year=harvest_year,
                producer_house="Test House",
                decanting_required=decanting,
            )

            details.refresh_from_db()
            assert details.style == style
            assert details.indication_age == indication_age
            assert details.harvest_year == harvest_year
            assert details.decanting_required == decanting


class TestWhiskeyDetailsAllFields:
    """Tests for all WhiskeyDetails fields."""

    def test_whiskey_details_all_fields(self, whiskey_product):
        """All WhiskeyDetails fields should store correctly."""
        from crawler.models import WhiskeyDetails

        details = WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="scotch_single_malt",
            whiskey_country="Scotland",
            whiskey_region="Islay",
            distillery="Laphroaig",
            mash_bill="100% malted barley",
            cask_strength=True,
            single_cask=True,
            cask_number="1234",
            vintage_year=2010,
            bottling_year=2024,
            batch_number="Batch 001",
            peated=True,
            peat_level="heavily_peated",
        )

        details.refresh_from_db()

        assert details.whiskey_type == "scotch_single_malt"
        assert details.whiskey_country == "Scotland"
        assert details.whiskey_region == "Islay"
        assert details.distillery == "Laphroaig"
        assert details.mash_bill == "100% malted barley"
        assert details.cask_strength is True
        assert details.single_cask is True
        assert details.cask_number == "1234"
        assert details.vintage_year == 2010
        assert details.bottling_year == 2024
        assert details.batch_number == "Batch 001"
        assert details.peated is True
        assert details.peat_level == "heavily_peated"

    def test_whiskey_details_nullable_fields(self, whiskey_product):
        """Nullable WhiskeyDetails fields should accept None."""
        from crawler.models import WhiskeyDetails

        details = WhiskeyDetails.objects.create(
            product=whiskey_product,
            whiskey_type="bourbon",
            whiskey_country="USA",
            whiskey_region="Kentucky",
            distillery="Buffalo Trace",
            # All nullable fields left as default
        )

        details.refresh_from_db()

        assert details.mash_bill is None
        assert details.cask_number is None
        assert details.vintage_year is None
        assert details.bottling_year is None
        assert details.batch_number is None
        assert details.peated is None
        assert details.peat_level is None


class TestPortWineDetailsAllFields:
    """Tests for all PortWineDetails fields."""

    def test_port_details_all_fields(self, port_product):
        """All PortWineDetails fields should store correctly."""
        from crawler.models import PortWineDetails

        details = PortWineDetails.objects.create(
            product=port_product,
            style="vintage",
            indication_age=None,
            harvest_year=2007,
            bottling_year=2009,
            grape_varieties=["Touriga Nacional", "Touriga Franca", "Tinta Roriz"],
            quinta="Quinta do Noval",
            douro_subregion="cima_corgo",
            producer_house="Taylor's",
            decanting_required=True,
            drinking_window="2025-2060",
        )

        details.refresh_from_db()

        assert details.style == "vintage"
        assert details.harvest_year == 2007
        assert details.bottling_year == 2009
        assert details.grape_varieties == ["Touriga Nacional", "Touriga Franca", "Tinta Roriz"]
        assert details.quinta == "Quinta do Noval"
        assert details.douro_subregion == "cima_corgo"
        assert details.producer_house == "Taylor's"
        assert details.decanting_required is True
        assert details.drinking_window == "2025-2060"

    def test_port_details_nullable_fields(self, port_product):
        """Nullable PortWineDetails fields should accept None."""
        from crawler.models import PortWineDetails

        details = PortWineDetails.objects.create(
            product=port_product,
            style="ruby",
            producer_house="Graham's",
            decanting_required=False,
            # All nullable fields left as default
        )

        details.refresh_from_db()

        assert details.indication_age is None
        assert details.harvest_year is None
        assert details.bottling_year is None
        assert details.grape_varieties == []
        assert details.quinta is None
        assert details.douro_subregion is None
        assert details.drinking_window is None
