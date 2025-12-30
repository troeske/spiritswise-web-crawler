"""
Task Group 25: European Market Fields Tests

Tests for European market-specific fields on DiscoveredProduct.
These fields enable the system to be specifically tailored for German/European
spirits retailers.

TDD approach: Tests written first, then implementation follows.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from crawler.models import (
    DiscoveredProduct,
    ProductType,
    OriginRegionChoices,
    ImportComplexityChoices,
)


class TestEURPricingFields(TestCase):
    """Test EUR pricing fields on DiscoveredProduct."""

    def test_primary_currency_default_eur(self):
        """
        Test that primary_currency defaults to 'EUR' for European market focus.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/eur_product1",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.primary_currency == "EUR"

    def test_eur_pricing_fields_storage(self):
        """
        Test EUR pricing fields: price_eur, price_includes_vat, vat_rate, price_excl_vat.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/eur_product2",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            price_eur=Decimal("79.99"),
            price_includes_vat=True,
            vat_rate=Decimal("19.00"),
            price_excl_vat=Decimal("67.22"),
        )

        product.refresh_from_db()
        assert product.price_eur == Decimal("79.99")
        assert product.price_includes_vat is True
        assert product.vat_rate == Decimal("19.00")
        assert product.price_excl_vat == Decimal("67.22")

    def test_price_includes_vat_default_true(self):
        """
        Test that price_includes_vat defaults to True (EU retail prices include VAT).
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/eur_product3",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.price_includes_vat is True


class TestImportComplexityFields(TestCase):
    """Test import complexity and availability fields."""

    def test_origin_region_choices(self):
        """
        Test origin_region accepts all valid choices from OriginRegionChoices.

        Origin regions: eu, uk, usa, japan, rest_of_world
        """
        regions = [
            (OriginRegionChoices.EU, "eu"),
            (OriginRegionChoices.UK, "uk"),
            (OriginRegionChoices.USA, "usa"),
            (OriginRegionChoices.JAPAN, "japan"),
            (OriginRegionChoices.REST_OF_WORLD, "rest_of_world"),
        ]

        for choice, expected_value in regions:
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/origin_{expected_value}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
                origin_region=choice,
            )
            product.refresh_from_db()
            assert product.origin_region == expected_value, f"Expected {expected_value}, got {product.origin_region}"

    def test_import_complexity_choices(self):
        """
        Test import_complexity accepts all valid choices from ImportComplexityChoices.

        Import complexities: eu_domestic, uk_post_brexit, usa_import, japan_import, other_import
        """
        complexities = [
            (ImportComplexityChoices.EU_DOMESTIC, "eu_domestic"),
            (ImportComplexityChoices.UK_POST_BREXIT, "uk_post_brexit"),
            (ImportComplexityChoices.USA_IMPORT, "usa_import"),
            (ImportComplexityChoices.JAPAN_IMPORT, "japan_import"),
            (ImportComplexityChoices.OTHER_IMPORT, "other_import"),
        ]

        for choice, expected_value in complexities:
            product = DiscoveredProduct.objects.create(
                source_url=f"https://example.com/import_{expected_value}",
                product_type=ProductType.WHISKEY,
                raw_content="<html>test</html>",
                import_complexity=choice,
            )
            product.refresh_from_db()
            assert product.import_complexity == expected_value

    def test_eu_and_german_availability_flags(self):
        """
        Test eu_available and german_available boolean fields.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/avail_test",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            eu_available=True,
            german_available=True,
        )

        product.refresh_from_db()
        assert product.eu_available is True
        assert product.german_available is True

    def test_availability_flags_default_false(self):
        """
        Test that eu_available and german_available default to False.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/avail_default",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.eu_available is False
        assert product.german_available is False

    def test_estimated_landed_cost_eur(self):
        """
        Test estimated_landed_cost_eur DecimalField (nullable).
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/landed_cost",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            estimated_landed_cost_eur=Decimal("95.50"),
        )

        product.refresh_from_db()
        assert product.estimated_landed_cost_eur == Decimal("95.50")


class TestGermanMarketFitField(TestCase):
    """Test german_market_fit field."""

    def test_german_market_fit_storage(self):
        """
        Test german_market_fit IntegerField (1-10, nullable).

        Score indicates suitability for German market based on various factors.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/market_fit",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            german_market_fit=8,
        )

        product.refresh_from_db()
        assert product.german_market_fit == 8

    def test_german_market_fit_nullable(self):
        """
        Test that german_market_fit can be null (not yet calculated).
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/market_fit_null",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.german_market_fit is None


class TestEURegulatoryFields(TestCase):
    """Test EU regulatory compliance fields."""

    def test_eu_regulatory_fields_storage(self):
        """
        Test EU regulatory fields: eu_label_compliant, contains_allergens,
        organic_certified, bottle_size_ml, alcohol_duty_category.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/regulatory",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            eu_label_compliant=True,
            contains_allergens=False,
            organic_certified=True,
            bottle_size_ml=700,
            alcohol_duty_category="spirits",
        )

        product.refresh_from_db()
        assert product.eu_label_compliant is True
        assert product.contains_allergens is False
        assert product.organic_certified is True
        assert product.bottle_size_ml == 700
        assert product.alcohol_duty_category == "spirits"

    def test_bottle_size_ml_common_values(self):
        """
        Test bottle_size_ml with common EU values (700ml spirits, 750ml wine).
        """
        # Spirits typically 700ml in EU
        spirits_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/bottle_700",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            bottle_size_ml=700,
        )
        spirits_product.refresh_from_db()
        assert spirits_product.bottle_size_ml == 700

        # Wine typically 750ml
        wine_product = DiscoveredProduct.objects.create(
            source_url="https://example.com/bottle_750",
            product_type=ProductType.PORT_WINE,
            raw_content="<html>test</html>",
            bottle_size_ml=750,
        )
        wine_product.refresh_from_db()
        assert wine_product.bottle_size_ml == 750

    def test_regulatory_fields_nullable(self):
        """
        Test that regulatory fields can be null (not yet determined).
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/regulatory_null",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.eu_label_compliant is None
        assert product.contains_allergens is None
        assert product.organic_certified is None
        assert product.bottle_size_ml is None
        assert product.alcohol_duty_category is None


class TestGermanLanguageFields(TestCase):
    """Test German language fields."""

    def test_german_language_fields_storage(self):
        """
        Test name_de and description_de fields for German localization.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/german_lang",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            name_de="Glenfiddich 12 Jahre",
            description_de="Ein leichter und eleganter Single Malt mit fruchtigen Noten.",
        )

        product.refresh_from_db()
        assert product.name_de == "Glenfiddich 12 Jahre"
        assert product.description_de == "Ein leichter und eleganter Single Malt mit fruchtigen Noten."

    def test_german_language_fields_nullable(self):
        """
        Test that German language fields can be null.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/german_lang_null",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
        )

        product.refresh_from_db()
        assert product.name_de is None
        assert product.description_de is None


class TestEuropeanMarketFieldsIntegration(TestCase):
    """Integration tests for all European market fields together."""

    def test_full_european_market_profile(self):
        """
        Test creating a product with all European market fields populated.
        """
        product = DiscoveredProduct.objects.create(
            source_url="https://example.com/full_eu_profile",
            product_type=ProductType.WHISKEY,
            raw_content="<html>test</html>",
            # EUR pricing fields
            primary_currency="EUR",
            price_eur=Decimal("89.99"),
            price_includes_vat=True,
            vat_rate=Decimal("19.00"),
            price_excl_vat=Decimal("75.62"),
            # Import/availability fields
            origin_region=OriginRegionChoices.UK,
            import_complexity=ImportComplexityChoices.UK_POST_BREXIT,
            eu_available=True,
            german_available=True,
            estimated_landed_cost_eur=Decimal("102.50"),
            # EU regulatory fields
            eu_label_compliant=True,
            contains_allergens=False,
            organic_certified=False,
            bottle_size_ml=700,
            alcohol_duty_category="spirits",
            # German market fit
            german_market_fit=7,
            # German language fields
            name_de="Talisker 10 Jahre",
            description_de="Ein kraftvoller Single Malt von der Isle of Skye.",
        )

        product.refresh_from_db()

        # Verify all EUR pricing fields
        assert product.primary_currency == "EUR"
        assert product.price_eur == Decimal("89.99")
        assert product.price_includes_vat is True
        assert product.vat_rate == Decimal("19.00")
        assert product.price_excl_vat == Decimal("75.62")

        # Verify import/availability fields
        assert product.origin_region == "uk"
        assert product.import_complexity == "uk_post_brexit"
        assert product.eu_available is True
        assert product.german_available is True
        assert product.estimated_landed_cost_eur == Decimal("102.50")

        # Verify EU regulatory fields
        assert product.eu_label_compliant is True
        assert product.contains_allergens is False
        assert product.organic_certified is False
        assert product.bottle_size_ml == 700
        assert product.alcohol_duty_category == "spirits"

        # Verify German market fit
        assert product.german_market_fit == 7

        # Verify German language fields
        assert product.name_de == "Talisker 10 Jahre"
        assert product.description_de == "Ein kraftvoller Single Malt von der Isle of Skye."
