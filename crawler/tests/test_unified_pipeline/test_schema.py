"""
Schema TDD Tests - Phase 1

Spec Reference: docs/spec-parts/06-DATABASE-SCHEMA.md

These tests verify that the database schema matches the spec exactly.
Written FIRST according to TDD methodology.
"""

from decimal import Decimal
from django.test import TestCase
from django.db import models

from crawler.models import (
    DiscoveredProduct,
    WhiskeyDetails,
    PortWineDetails,
)


class TestDiscoveredProductSchema(TestCase):
    """Tests that verify DiscoveredProduct matches spec (Section 6.1)."""

    # ===================================================================
    # IDENTIFICATION FIELDS
    # ===================================================================

    def test_has_name_field_indexed(self):
        """Spec: name CharField(500), indexed"""
        field = DiscoveredProduct._meta.get_field("name")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 500)
        self.assertTrue(field.db_index, "name field should be indexed")

    def test_has_gtin_field_indexed(self):
        """Spec: gtin CharField(14), indexed"""
        field = DiscoveredProduct._meta.get_field("gtin")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 14)
        self.assertTrue(field.db_index, "gtin field should be indexed")

    def test_fingerprint_is_unique(self):
        """Spec: fingerprint CharField(64), unique, indexed"""
        field = DiscoveredProduct._meta.get_field("fingerprint")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 64)
        self.assertTrue(field.unique, "fingerprint field should be unique")
        self.assertTrue(field.db_index, "fingerprint field should be indexed")

    # ===================================================================
    # BASIC PRODUCT INFO FIELDS
    # ===================================================================

    def test_has_description_field(self):
        """Spec: description TextField"""
        field = DiscoveredProduct._meta.get_field("description")
        self.assertIsInstance(field, models.TextField)

    def test_abv_is_decimal_field_indexed(self):
        """Spec: abv DecimalField(4,1), indexed"""
        field = DiscoveredProduct._meta.get_field("abv")
        self.assertIsInstance(field, models.DecimalField)
        self.assertEqual(field.max_digits, 4)
        self.assertEqual(field.decimal_places, 1)
        self.assertTrue(field.db_index, "abv field should be indexed")

    def test_age_statement_is_char_field(self):
        """Spec: age_statement CharField(20) to support 'NAS'"""
        field = DiscoveredProduct._meta.get_field("age_statement")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 20)

    def test_country_is_indexed(self):
        """Spec: country CharField(100), indexed"""
        field = DiscoveredProduct._meta.get_field("country")
        self.assertIsInstance(field, models.CharField)
        self.assertTrue(field.db_index, "country field should be indexed")

    def test_region_is_indexed(self):
        """Spec: region CharField(100), indexed"""
        field = DiscoveredProduct._meta.get_field("region")
        self.assertIsInstance(field, models.CharField)
        self.assertTrue(field.db_index, "region field should be indexed")

    # ===================================================================
    # DEPRECATED FIELDS - MUST NOT EXIST
    # ===================================================================

    def test_no_extracted_data_json_blob(self):
        """Spec: extracted_data is DEPRECATED - must not exist"""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn(
            "extracted_data",
            field_names,
            "extracted_data field should be removed (DEPRECATED in spec)"
        )

    def test_no_enriched_data_json_blob(self):
        """Spec: enriched_data is DEPRECATED - must not exist"""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn(
            "enriched_data",
            field_names,
            "enriched_data field should be removed (DEPRECATED in spec)"
        )

    def test_no_taste_profile_json_blob(self):
        """Spec: taste_profile is DEPRECATED - must not exist"""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn(
            "taste_profile",
            field_names,
            "taste_profile field should be removed (DEPRECATED in spec)"
        )

    # ===================================================================
    # TASTING PROFILE - NOSE
    # ===================================================================

    def test_has_nose_description(self):
        """Spec: nose_description TextField"""
        field = DiscoveredProduct._meta.get_field("nose_description")
        self.assertIsInstance(field, models.TextField)

    def test_has_primary_aromas(self):
        """Spec: primary_aromas JSONField(list)"""
        field = DiscoveredProduct._meta.get_field("primary_aromas")
        self.assertIsInstance(field, models.JSONField)

    # ===================================================================
    # TASTING PROFILE - PALATE (CRITICAL)
    # ===================================================================

    def test_has_palate_description(self):
        """Spec: palate_description TextField"""
        field = DiscoveredProduct._meta.get_field("palate_description")
        self.assertIsInstance(field, models.TextField)

    def test_has_palate_flavors(self):
        """Spec: palate_flavors JSONField(list)"""
        field = DiscoveredProduct._meta.get_field("palate_flavors")
        self.assertIsInstance(field, models.JSONField)

    def test_has_initial_taste(self):
        """Spec: initial_taste TextField"""
        field = DiscoveredProduct._meta.get_field("initial_taste")
        self.assertIsInstance(field, models.TextField)

    # ===================================================================
    # TASTING PROFILE - FINISH
    # ===================================================================

    def test_has_finish_description(self):
        """Spec: finish_description TextField"""
        field = DiscoveredProduct._meta.get_field("finish_description")
        self.assertIsInstance(field, models.TextField)

    def test_has_finish_flavors(self):
        """Spec: finish_flavors JSONField(list)"""
        field = DiscoveredProduct._meta.get_field("finish_flavors")
        self.assertIsInstance(field, models.JSONField)

    # ===================================================================
    # STATUS & VERIFICATION
    # ===================================================================

    def test_has_completeness_score(self):
        """Spec: completeness_score IntegerField"""
        field = DiscoveredProduct._meta.get_field("completeness_score")
        self.assertIsInstance(field, models.IntegerField)

    def test_has_source_count(self):
        """Spec: source_count IntegerField"""
        field = DiscoveredProduct._meta.get_field("source_count")
        self.assertIsInstance(field, models.IntegerField)

    def test_has_verified_fields(self):
        """Spec: verified_fields JSONField(list)"""
        field = DiscoveredProduct._meta.get_field("verified_fields")
        self.assertIsInstance(field, models.JSONField)

    def test_extraction_confidence_is_decimal(self):
        """Spec: extraction_confidence DecimalField(3,2)"""
        field = DiscoveredProduct._meta.get_field("extraction_confidence")
        self.assertIsInstance(field, models.DecimalField)
        self.assertEqual(field.max_digits, 3)
        self.assertEqual(field.decimal_places, 2)


class TestWhiskeyDetailsSchema(TestCase):
    """Tests that verify WhiskeyDetails matches spec (Section 6.2)."""

    def test_has_product_one_to_one(self):
        """Spec: product OneToOne FK to DiscoveredProduct"""
        field = WhiskeyDetails._meta.get_field("product")
        self.assertIsInstance(field, models.OneToOneField)

    def test_has_distillery_indexed(self):
        """Spec: distillery CharField(200), indexed"""
        field = WhiskeyDetails._meta.get_field("distillery")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 200)
        self.assertTrue(field.db_index, "distillery field should be indexed")

    def test_has_peat_ppm(self):
        """Spec: peat_ppm IntegerField"""
        field = WhiskeyDetails._meta.get_field("peat_ppm")
        self.assertIsInstance(field, models.IntegerField)

    def test_has_natural_color(self):
        """Spec: natural_color BooleanField (not color_added)"""
        field = WhiskeyDetails._meta.get_field("natural_color")
        self.assertIsInstance(field, models.BooleanField)

    def test_has_non_chill_filtered(self):
        """Spec: non_chill_filtered BooleanField (not chill_filtered)"""
        field = WhiskeyDetails._meta.get_field("non_chill_filtered")
        self.assertIsInstance(field, models.BooleanField)

    def test_no_whiskey_country(self):
        """Spec: whiskey_country should not exist (use DiscoveredProduct.country)"""
        field_names = [f.name for f in WhiskeyDetails._meta.get_fields()]
        self.assertNotIn(
            "whiskey_country",
            field_names,
            "whiskey_country should be removed (not in spec)"
        )

    def test_no_whiskey_region(self):
        """Spec: whiskey_region should not exist (use DiscoveredProduct.region)"""
        field_names = [f.name for f in WhiskeyDetails._meta.get_fields()]
        self.assertNotIn(
            "whiskey_region",
            field_names,
            "whiskey_region should be removed (not in spec)"
        )

    def test_no_cask_type(self):
        """Spec: cask_type should not exist (use DiscoveredProduct.primary_cask)"""
        field_names = [f.name for f in WhiskeyDetails._meta.get_fields()]
        self.assertNotIn(
            "cask_type",
            field_names,
            "cask_type should be removed (not in spec)"
        )

    def test_no_cask_finish(self):
        """Spec: cask_finish should not exist (use DiscoveredProduct.finishing_cask)"""
        field_names = [f.name for f in WhiskeyDetails._meta.get_fields()]
        self.assertNotIn(
            "cask_finish",
            field_names,
            "cask_finish should be removed (not in spec)"
        )


class TestPortWineDetailsSchema(TestCase):
    """Tests that verify PortWineDetails matches spec (Section 6.3)."""

    def test_has_product_one_to_one(self):
        """Spec: product OneToOne FK to DiscoveredProduct"""
        field = PortWineDetails._meta.get_field("product")
        self.assertIsInstance(field, models.OneToOneField)

    def test_style_max_length_30(self):
        """Spec: style CharField(30)"""
        field = PortWineDetails._meta.get_field("style")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 30)

    def test_harvest_year_indexed(self):
        """Spec: harvest_year IntegerField, indexed"""
        field = PortWineDetails._meta.get_field("harvest_year")
        self.assertIsInstance(field, models.IntegerField)
        self.assertTrue(field.db_index, "harvest_year field should be indexed")

    def test_producer_house_indexed(self):
        """Spec: producer_house CharField(200), indexed"""
        field = PortWineDetails._meta.get_field("producer_house")
        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 200)
        self.assertTrue(field.db_index, "producer_house field should be indexed")


class TestSchemaIntegration(TestCase):
    """Integration tests for schema - create actual records."""

    def test_create_discovered_product_with_individual_columns(self):
        """Verify products can be created using individual columns (not JSON blobs)."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey 12 Year",
            product_type="whiskey",
            abv=Decimal("43.0"),
            age_statement="12",
            country="Scotland",
            region="Speyside",
            description="A fine single malt whiskey.",
            nose_description="Rich and fruity with notes of honey.",
            palate_description="Smooth with vanilla and oak.",
            finish_description="Long and warming.",
            primary_aromas=["honey", "fruit"],
            palate_flavors=["vanilla", "oak"],
            finish_flavors=["spice", "warmth"],
        )

        # Verify saved correctly
        saved = DiscoveredProduct.objects.get(id=product.id)
        self.assertEqual(saved.name, "Test Whiskey 12 Year")
        self.assertEqual(saved.abv, Decimal("43.0"))
        self.assertEqual(saved.age_statement, "12")
        self.assertEqual(saved.nose_description, "Rich and fruity with notes of honey.")
        self.assertEqual(saved.palate_flavors, ["vanilla", "oak"])

    def test_create_whiskey_details(self):
        """Verify WhiskeyDetails can be created with spec fields."""
        product = DiscoveredProduct.objects.create(
            name="Test Single Malt",
            product_type="whiskey",
        )

        details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type="single_malt",
            distillery="Test Distillery",
            peat_ppm=25,
            natural_color=True,
            non_chill_filtered=True,
        )

        # Verify saved correctly
        saved = WhiskeyDetails.objects.get(id=details.id)
        self.assertEqual(saved.distillery, "Test Distillery")
        self.assertEqual(saved.peat_ppm, 25)
        self.assertTrue(saved.natural_color)
        self.assertTrue(saved.non_chill_filtered)

    def test_create_port_wine_details(self):
        """Verify PortWineDetails can be created with spec fields."""
        product = DiscoveredProduct.objects.create(
            name="Test Vintage Port 2017",
            product_type="port_wine",
        )

        details = PortWineDetails.objects.create(
            product=product,
            style="vintage",
            harvest_year=2017,
            producer_house="Test House",
        )

        # Verify saved correctly
        saved = PortWineDetails.objects.get(id=details.id)
        self.assertEqual(saved.style, "vintage")
        self.assertEqual(saved.harvest_year, 2017)
        self.assertEqual(saved.producer_house, "Test House")
