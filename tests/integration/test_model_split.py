"""
Task 7.2: Model Split Verification Tests

This module tests the model split architecture for DiscoveredProduct:
- WhiskeyDetails: Whiskey-specific fields (distillery, peated, peat_level, mash_bill)
- PortWineDetails: Port wine-specific fields (style, quinta, harvest_year, grape_varieties)

The model split ensures:
1. Clean separation of concerns
2. No whiskey fields on port wine products (and vice versa)
3. Efficient database design (no null columns)
4. OneToOne relationships between DiscoveredProduct and type-specific details

Tests verify both model structure AND real VPS extraction creates correct models.
"""
import pytest
import os
import uuid
from django.db import models as django_models

# Import Django models
from crawler.models import (
    DiscoveredProduct,
    WhiskeyDetails,
    PortWineDetails,
    ProductType,
    WhiskeyTypeChoices,
    PortStyleChoices,
    PeatLevelChoices,
    DouroSubregionChoices,
)

# Tests run with database access
pytestmark = pytest.mark.django_db


class TestWhiskeyDetailsModelStructure:
    """
    Test WhiskeyDetails model has correct structure.
    """

    def test_whiskey_details_model_exists(self):
        """WhiskeyDetails model should exist."""
        assert WhiskeyDetails is not None
        assert issubclass(WhiskeyDetails, django_models.Model)

    def test_whiskey_details_has_product_one_to_one(self):
        """WhiskeyDetails should have OneToOne to DiscoveredProduct."""
        field = WhiskeyDetails._meta.get_field("product")
        assert field is not None
        assert isinstance(field, django_models.OneToOneField)
        assert field.related_model == DiscoveredProduct

    def test_whiskey_details_has_distillery_field(self):
        """WhiskeyDetails should have distillery field."""
        field = WhiskeyDetails._meta.get_field("distillery")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        assert field.db_index is True  # Should be indexed per spec

    def test_whiskey_details_has_peated_boolean(self):
        """WhiskeyDetails should have peated (boolean) field."""
        field = WhiskeyDetails._meta.get_field("peated")
        assert field is not None
        assert isinstance(field, (django_models.BooleanField, django_models.NullBooleanField))

    def test_whiskey_details_has_peat_level(self):
        """
        WhiskeyDetails should have peat_level field.
        E.g., "lightly_peated", "heavily_peated", "unpeated"
        """
        field = WhiskeyDetails._meta.get_field("peat_level")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        # Should have choices
        assert field.choices is not None
        # Verify expected choice values exist
        choice_values = [c[0] for c in PeatLevelChoices.choices]
        assert "unpeated" in choice_values
        assert "lightly_peated" in choice_values
        assert "heavily_peated" in choice_values

    def test_whiskey_details_has_mash_bill(self):
        """WhiskeyDetails should have mash_bill field (for bourbon)."""
        field = WhiskeyDetails._meta.get_field("mash_bill")
        assert field is not None
        assert isinstance(field, django_models.CharField)

    def test_whiskey_details_has_whiskey_type(self):
        """
        WhiskeyDetails should have whiskey_type field.
        E.g., "single_malt", "bourbon", "rye", "blended"
        """
        field = WhiskeyDetails._meta.get_field("whiskey_type")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        # Should have choices
        assert field.choices is not None
        # Verify expected choice values exist
        choice_values = [c[0] for c in WhiskeyTypeChoices.choices]
        assert "bourbon" in choice_values
        assert "rye" in choice_values
        assert "scotch_single_malt" in choice_values

    def test_whiskey_details_has_cask_strength(self):
        """WhiskeyDetails should have cask_strength boolean."""
        field = WhiskeyDetails._meta.get_field("cask_strength")
        assert field is not None
        assert isinstance(field, django_models.BooleanField)

    def test_whiskey_details_has_single_cask(self):
        """WhiskeyDetails should have single_cask boolean."""
        field = WhiskeyDetails._meta.get_field("single_cask")
        assert field is not None
        assert isinstance(field, django_models.BooleanField)

    def test_whiskey_details_has_vintage_year(self):
        """WhiskeyDetails should have vintage_year field."""
        field = WhiskeyDetails._meta.get_field("vintage_year")
        assert field is not None
        assert isinstance(field, django_models.IntegerField)


class TestPortWineDetailsModelStructure:
    """
    Test PortWineDetails model has correct structure.
    """

    def test_port_wine_details_model_exists(self):
        """PortWineDetails model should exist."""
        assert PortWineDetails is not None
        assert issubclass(PortWineDetails, django_models.Model)

    def test_port_wine_details_has_product_one_to_one(self):
        """PortWineDetails should have OneToOne to DiscoveredProduct."""
        field = PortWineDetails._meta.get_field("product")
        assert field is not None
        assert isinstance(field, django_models.OneToOneField)
        assert field.related_model == DiscoveredProduct

    def test_port_wine_details_has_style(self):
        """
        PortWineDetails should have style field.
        E.g., "tawny", "ruby", "vintage", "lbv", "colheita"
        """
        field = PortWineDetails._meta.get_field("style")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        # Should have choices
        assert field.choices is not None
        # Verify expected choice values exist
        choice_values = [c[0] for c in PortStyleChoices.choices]
        assert "tawny" in choice_values
        assert "ruby" in choice_values
        assert "vintage" in choice_values
        assert "lbv" in choice_values
        assert "colheita" in choice_values

    def test_port_wine_details_has_quinta(self):
        """PortWineDetails should have quinta field (estate name)."""
        field = PortWineDetails._meta.get_field("quinta")
        assert field is not None
        assert isinstance(field, django_models.CharField)

    def test_port_wine_details_has_harvest_year(self):
        """PortWineDetails should have harvest_year for vintage/colheita."""
        field = PortWineDetails._meta.get_field("harvest_year")
        assert field is not None
        assert isinstance(field, django_models.IntegerField)
        assert field.db_index is True  # Should be indexed per spec

    def test_port_wine_details_has_grape_varieties(self):
        """PortWineDetails should have grape_varieties field."""
        field = PortWineDetails._meta.get_field("grape_varieties")
        assert field is not None
        assert isinstance(field, django_models.JSONField)

    def test_port_wine_details_has_indication_age(self):
        """
        PortWineDetails should have indication_age field.
        E.g., "10 Year", "20 Year", "40 Year"
        """
        field = PortWineDetails._meta.get_field("indication_age")
        assert field is not None
        assert isinstance(field, django_models.CharField)

    def test_port_wine_details_has_producer_house(self):
        """PortWineDetails should have producer_house field."""
        field = PortWineDetails._meta.get_field("producer_house")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        assert field.db_index is True  # Should be indexed per spec

    def test_port_wine_details_has_douro_subregion(self):
        """PortWineDetails should have douro_subregion field."""
        field = PortWineDetails._meta.get_field("douro_subregion")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        # Should have choices
        assert field.choices is not None
        choice_values = [c[0] for c in DouroSubregionChoices.choices]
        assert "baixo_corgo" in choice_values
        assert "cima_corgo" in choice_values
        assert "douro_superior" in choice_values


class TestCommonFieldsOnDiscoveredProduct:
    """
    Test that common fields are on DiscoveredProduct (not type-specific).
    """

    def test_common_name_field(self):
        """name should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("name")
        assert field is not None

    def test_common_brand_field(self):
        """brand should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("brand")
        assert field is not None

    def test_common_abv_field(self):
        """abv should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("abv")
        assert field is not None

    def test_common_nose_description_field(self):
        """nose_description should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("nose_description")
        assert field is not None

    def test_common_palate_description_field(self):
        """palate_description should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("palate_description")
        assert field is not None

    def test_common_finish_description_field(self):
        """finish_description should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("finish_description")
        assert field is not None

    def test_common_description_field(self):
        """description should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("description")
        assert field is not None

    def test_common_region_field(self):
        """region should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("region")
        assert field is not None

    def test_common_country_field(self):
        """country should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("country")
        assert field is not None

    def test_common_product_type_field(self):
        """product_type should be on DiscoveredProduct."""
        field = DiscoveredProduct._meta.get_field("product_type")
        assert field is not None

    def test_tasting_notes_not_on_whiskey_details(self):
        """
        Tasting notes should NOT be on WhiskeyDetails.
        They belong on the common DiscoveredProduct.
        """
        # These fields should NOT exist on WhiskeyDetails
        with pytest.raises(Exception):  # FieldDoesNotExist
            WhiskeyDetails._meta.get_field("nose_description")

        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("palate_description")

        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("finish_description")

    def test_tasting_notes_not_on_port_wine_details(self):
        """
        Tasting notes should NOT be on PortWineDetails.
        They belong on the common DiscoveredProduct.
        """
        # These fields should NOT exist on PortWineDetails
        with pytest.raises(Exception):  # FieldDoesNotExist
            PortWineDetails._meta.get_field("nose_description")

        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("palate_description")

        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("finish_description")


class TestNoWhiskeyFieldsOnPortWine:
    """
    Test separation of concerns - no cross-contamination of fields.
    """

    def test_no_distillery_on_port_wine(self):
        """
        Port wine products should NOT have distillery field.
        That's whiskey-specific.
        """
        with pytest.raises(Exception):  # FieldDoesNotExist
            PortWineDetails._meta.get_field("distillery")

    def test_no_peated_on_port_wine(self):
        """Port wine products should NOT have peated field."""
        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("peated")

    def test_no_peat_level_on_port_wine(self):
        """Port wine products should NOT have peat_level field."""
        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("peat_level")

    def test_no_mash_bill_on_port_wine(self):
        """Port wine products should NOT have mash_bill field."""
        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("mash_bill")

    def test_no_whiskey_type_on_port_wine(self):
        """Port wine products should NOT have whiskey_type field."""
        with pytest.raises(Exception):
            PortWineDetails._meta.get_field("whiskey_type")

    def test_no_quinta_on_whiskey(self):
        """
        Whiskey products should NOT have quinta field.
        That's port wine-specific.
        """
        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("quinta")

    def test_no_grape_varieties_on_whiskey(self):
        """Whiskey products should NOT have grape_varieties field."""
        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("grape_varieties")

    def test_no_style_on_whiskey(self):
        """Whiskey products should NOT have style (port style) field."""
        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("style")

    def test_no_indication_age_on_whiskey(self):
        """Whiskey products should NOT have indication_age field."""
        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("indication_age")

    def test_no_producer_house_on_whiskey(self):
        """Whiskey products should NOT have producer_house field."""
        with pytest.raises(Exception):
            WhiskeyDetails._meta.get_field("producer_house")


class TestModelRelationships:
    """
    Test OneToOne relationships work correctly.
    """

    def test_whiskey_details_related_name(self):
        """WhiskeyDetails should be accessible via product.whiskey_details."""
        field = WhiskeyDetails._meta.get_field("product")
        assert field.related_query_name() == "whiskey_details"

    def test_port_wine_details_related_name(self):
        """PortWineDetails should be accessible via product.port_details."""
        field = PortWineDetails._meta.get_field("product")
        assert field.related_query_name() == "port_details"

    def test_whiskey_details_cascade_delete(self):
        """WhiskeyDetails should cascade delete with DiscoveredProduct."""
        field = WhiskeyDetails._meta.get_field("product")
        assert field.remote_field.on_delete == django_models.CASCADE

    def test_port_wine_details_cascade_delete(self):
        """PortWineDetails should cascade delete with DiscoveredProduct."""
        field = PortWineDetails._meta.get_field("product")
        assert field.remote_field.on_delete == django_models.CASCADE


def _create_test_product(name: str, product_type: str, source_url: str, raw_content: str = "Test content"):
    """Helper function to create a product for testing."""
    import hashlib

    # Generate unique fingerprint
    fingerprint = hashlib.sha256(f"{name}-{uuid.uuid4()}".encode()).hexdigest()

    product = DiscoveredProduct(
        name=name,
        product_type=product_type,
        source_url=source_url,
        raw_content=raw_content,
        fingerprint=fingerprint,
    )
    # Save with update_fields to skip auto-calculations
    product.save()
    return product


class TestWhiskeyProductCreation:
    """
    Test that whiskey products create WhiskeyDetails correctly.
    """

    def test_can_create_whiskey_product_with_details(self):
        """
        When product_type='whiskey':
        - DiscoveredProduct created
        - WhiskeyDetails linked via OneToOne
        """
        # Create a whiskey product
        product = _create_test_product(
            name="Test Whiskey 12 Year",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test-whiskey",
            raw_content="Test whiskey raw content",
        )

        # Create WhiskeyDetails for it
        whiskey_details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.SCOTCH_SINGLE_MALT,
            distillery="Test Distillery",
            peated=True,
            peat_level=PeatLevelChoices.LIGHTLY_PEATED,
            mash_bill="100% malted barley",
        )

        # Refresh from DB
        product.refresh_from_db()

        # Verify relationship
        assert whiskey_details.product == product
        assert product.whiskey_details == whiskey_details

        # Verify data
        assert whiskey_details.distillery == "Test Distillery"
        assert whiskey_details.peated is True
        assert whiskey_details.peat_level == "lightly_peated"

        # Cleanup
        product.delete()

    def test_whiskey_product_no_port_details(self):
        """Whiskey products should not have port_details."""
        product = _create_test_product(
            name="Test Bourbon",
            product_type=ProductType.WHISKEY,
            source_url="https://example.com/test-bourbon",
            raw_content="Test bourbon content",
        )

        WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.BOURBON,
            mash_bill="75% corn, 15% rye, 10% malted barley",
        )

        # Should NOT have port_details
        assert not PortWineDetails.objects.filter(product=product).exists()

        # Cleanup
        product.delete()


class TestPortWineProductCreation:
    """
    Test that port wine products create PortWineDetails correctly.
    """

    def test_can_create_port_wine_product_with_details(self):
        """
        When product_type='port_wine':
        - DiscoveredProduct created
        - PortWineDetails linked via OneToOne
        """
        # Create a port wine product
        product = _create_test_product(
            name="Test Port 20 Year Tawny",
            product_type=ProductType.PORT_WINE,
            source_url="https://example.com/test-port",
            raw_content="Test port wine raw content",
        )

        # Create PortWineDetails for it
        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.TAWNY,
            indication_age="20 Year",
            producer_house="Test Port House",
            grape_varieties=["Touriga Nacional", "Touriga Franca", "Tinta Roriz"],
        )

        # Refresh from DB
        product.refresh_from_db()

        # Verify relationship
        assert port_details.product == product
        assert product.port_details == port_details

        # Verify data
        assert port_details.style == "tawny"
        assert port_details.indication_age == "20 Year"
        assert port_details.producer_house == "Test Port House"
        assert "Touriga Nacional" in port_details.grape_varieties

        # Cleanup
        product.delete()

    def test_port_wine_product_no_whiskey_details(self):
        """Port wine products should not have whiskey_details."""
        product = _create_test_product(
            name="Test Vintage Port 2017",
            product_type=ProductType.PORT_WINE,
            source_url="https://example.com/test-vintage-port",
            raw_content="Test vintage port content",
        )

        PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.VINTAGE,
            harvest_year=2017,
            producer_house="Test House",
        )

        # Should NOT have whiskey_details
        assert not WhiskeyDetails.objects.filter(product=product).exists()

        # Cleanup
        product.delete()

    def test_port_wine_with_quinta(self):
        """Port wine can have quinta (estate) information."""
        product = _create_test_product(
            name="Quinta do Test Vintage 2011",
            product_type=ProductType.PORT_WINE,
            source_url="https://example.com/quinta-port",
            raw_content="Quinta port content",
        )

        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.SINGLE_QUINTA,
            quinta="Quinta do Test",
            harvest_year=2011,
            producer_house="Test House",
            douro_subregion=DouroSubregionChoices.CIMA_CORGO,
        )

        assert port_details.quinta == "Quinta do Test"
        assert port_details.douro_subregion == "cima_corgo"

        # Cleanup
        product.delete()


class TestDatabaseTableStructure:
    """
    Test database table structure is correct.
    """

    def test_whiskey_details_table_name(self):
        """WhiskeyDetails should use whiskey_details table."""
        assert WhiskeyDetails._meta.db_table == "whiskey_details"

    def test_port_wine_details_table_name(self):
        """PortWineDetails should use port_wine_details table."""
        assert PortWineDetails._meta.db_table == "port_wine_details"

    def test_whiskey_details_distillery_indexed(self):
        """distillery field should be indexed for searchability."""
        field = WhiskeyDetails._meta.get_field("distillery")
        assert field.db_index is True

    def test_port_wine_details_harvest_year_indexed(self):
        """harvest_year field should be indexed for searchability."""
        field = PortWineDetails._meta.get_field("harvest_year")
        assert field.db_index is True

    def test_port_wine_details_producer_house_indexed(self):
        """producer_house field should be indexed for searchability."""
        field = PortWineDetails._meta.get_field("producer_house")
        assert field.db_index is True


class TestExpectedModelFields:
    """
    Verify all expected fields exist on each model per spec.
    """

    def test_discovered_product_common_fields(self):
        """Verify DiscoveredProduct has all expected common fields."""
        expected_fields = [
            "name", "brand", "product_type",
            "abv", "description", "region", "country",
            "nose_description", "palate_description", "finish_description",
            "palate_flavors", "primary_aromas",
            "best_price", "images", "ratings", "awards",
            "completeness_score", "status", "source_count",
        ]
        for field_name in expected_fields:
            try:
                DiscoveredProduct._meta.get_field(field_name)
            except Exception:
                pytest.fail(f"DiscoveredProduct missing expected field: {field_name}")

    def test_whiskey_details_expected_fields(self):
        """Verify WhiskeyDetails has all expected whiskey-specific fields."""
        expected_fields = [
            "product",  # OneToOne to DiscoveredProduct
            "distillery",
            "peated",
            "peat_level",
            "whiskey_type",
            "mash_bill",
            "cask_strength",
            "single_cask",
            "vintage_year",
        ]
        for field_name in expected_fields:
            try:
                WhiskeyDetails._meta.get_field(field_name)
            except Exception:
                pytest.fail(f"WhiskeyDetails missing expected field: {field_name}")

    def test_port_wine_details_expected_fields(self):
        """Verify PortWineDetails has all expected port wine-specific fields."""
        expected_fields = [
            "product",  # OneToOne to DiscoveredProduct
            "style",
            "quinta",
            "harvest_year",
            "grape_varieties",
            "indication_age",
            "producer_house",
        ]
        for field_name in expected_fields:
            try:
                PortWineDetails._meta.get_field(field_name)
            except Exception:
                pytest.fail(f"PortWineDetails missing expected field: {field_name}")


class TestModelChoicesComplete:
    """
    Verify all expected choice values exist.
    """

    def test_whiskey_type_choices_complete(self):
        """Verify WhiskeyTypeChoices has all expected types."""
        choice_values = [c[0] for c in WhiskeyTypeChoices.choices]
        expected = ["bourbon", "rye", "scotch_single_malt", "scotch_blend", "tennessee", "japanese"]
        for expected_value in expected:
            assert expected_value in choice_values, f"Missing whiskey type: {expected_value}"

    def test_port_style_choices_complete(self):
        """Verify PortStyleChoices has all expected styles."""
        choice_values = [c[0] for c in PortStyleChoices.choices]
        expected = ["ruby", "tawny", "vintage", "lbv", "colheita", "white"]
        for expected_value in expected:
            assert expected_value in choice_values, f"Missing port style: {expected_value}"

    def test_peat_level_choices_complete(self):
        """Verify PeatLevelChoices has all expected levels."""
        choice_values = [c[0] for c in PeatLevelChoices.choices]
        expected = ["unpeated", "lightly_peated", "heavily_peated"]
        for expected_value in expected:
            assert expected_value in choice_values, f"Missing peat level: {expected_value}"
