"""
Product Saving TDD Tests - Phase 4

Spec Reference: docs/spec-parts/08-IMPLEMENTATION-PLAN.md, Section 8.2

These tests verify that product saving uses individual columns, NOT deprecated JSON blobs.
Written FIRST according to TDD methodology.

Key Requirements:
1. All data saved to individual model columns (CharField, TextField, etc.)
2. NO data saved to deprecated JSON fields (extracted_data, enriched_data, taste_profile)
3. Related models (WhiskeyDetails, PortWineDetails) created correctly
4. Tasting profile data saved to individual columns
"""

from decimal import Decimal
from django.test import TestCase
from django.db import connection

from crawler.models import (
    DiscoveredProduct,
    DiscoveredBrand,
    WhiskeyDetails,
    PortWineDetails,
)


class TestSaveToIndividualColumns(TestCase):
    """Tests that verify data is saved to individual columns."""

    def test_saves_name_to_column(self):
        """Data saved to name CharField, retrieved via ORM."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey 12 Year",
            product_type="whiskey",
        )
        # Reload from database and verify
        saved_product = DiscoveredProduct.objects.get(id=product.id)
        self.assertEqual(saved_product.name, "Test Whiskey 12 Year")

    def test_saves_abv_to_decimal_column(self):
        """Data saved to abv DecimalField (verified via ORM)."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            abv=Decimal("43.0"),
        )
        # Reload from database and verify decimal precision preserved
        saved_product = DiscoveredProduct.objects.get(id=product.id)
        self.assertEqual(saved_product.abv, Decimal("43.0"))

    def test_saves_description_to_column(self):
        """Data saved to description TextField, not JSON blob."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            description="A fine single malt whiskey aged 12 years.",
        )
        # Reload and verify
        product.refresh_from_db()
        self.assertEqual(product.description, "A fine single malt whiskey aged 12 years.")


class TestSaveTastingProfileColumns(TestCase):
    """Tests that verify tasting profile saved to individual columns."""

    def test_saves_nose_description_to_column(self):
        """nose_description saved as TextField column."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            nose_description="Rich and fruity with notes of honey and vanilla.",
        )
        product.refresh_from_db()
        self.assertEqual(product.nose_description, "Rich and fruity with notes of honey and vanilla.")

    def test_saves_primary_aromas_to_json_column(self):
        """primary_aromas saved as JSONField column (list)."""
        aromas = ["honey", "vanilla", "fruit", "oak"]
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            primary_aromas=aromas,
        )
        product.refresh_from_db()
        self.assertEqual(product.primary_aromas, aromas)

    def test_saves_palate_description_to_column(self):
        """palate_description saved as TextField column."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            palate_description="Smooth and rich with vanilla and oak.",
        )
        product.refresh_from_db()
        self.assertEqual(product.palate_description, "Smooth and rich with vanilla and oak.")

    def test_saves_palate_flavors_to_json_column(self):
        """palate_flavors saved as JSONField column (list)."""
        flavors = ["vanilla", "oak", "honey", "spice"]
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            palate_flavors=flavors,
        )
        product.refresh_from_db()
        self.assertEqual(product.palate_flavors, flavors)

    def test_saves_initial_taste_to_column(self):
        """initial_taste saved as TextField column."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            initial_taste="Sweet entry with honey and vanilla.",
        )
        product.refresh_from_db()
        self.assertEqual(product.initial_taste, "Sweet entry with honey and vanilla.")

    def test_saves_finish_description_to_column(self):
        """finish_description saved as TextField column."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            finish_description="Long and warming with hints of spice.",
        )
        product.refresh_from_db()
        self.assertEqual(product.finish_description, "Long and warming with hints of spice.")

    def test_saves_finish_flavors_to_json_column(self):
        """finish_flavors saved as JSONField column (list)."""
        flavors = ["spice", "oak", "warmth"]
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            finish_flavors=flavors,
        )
        product.refresh_from_db()
        self.assertEqual(product.finish_flavors, flavors)


class TestNoDeprecatedJsonFields(TestCase):
    """Tests that verify deprecated JSON fields don't exist."""

    def test_no_extracted_data_field(self):
        """extracted_data field should not exist on model."""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn("extracted_data", field_names)

    def test_no_enriched_data_field(self):
        """enriched_data field should not exist on model."""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn("enriched_data", field_names)

    def test_no_taste_profile_field(self):
        """taste_profile field should not exist on model."""
        field_names = [f.name for f in DiscoveredProduct._meta.get_fields()]
        self.assertNotIn("taste_profile", field_names)

    def test_no_extracted_data_column_in_database(self):
        """extracted_data column should not exist in database table."""
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(discovered_products)")
            columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn("extracted_data", columns)

    def test_no_enriched_data_column_in_database(self):
        """enriched_data column should not exist in database table."""
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(discovered_products)")
            columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn("enriched_data", columns)

    def test_no_taste_profile_column_in_database(self):
        """taste_profile column should not exist in database table."""
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(discovered_products)")
            columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn("taste_profile", columns)


class TestWhiskeyDetailsSaving(TestCase):
    """Tests for WhiskeyDetails related model."""

    def test_creates_whiskey_details_for_whiskey(self):
        """WhiskeyDetails can be created and linked to whiskey product."""
        product = DiscoveredProduct.objects.create(
            name="Glenfiddich 12 Year",
            product_type="whiskey",
        )
        details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type="single_malt",
            distillery="Glenfiddich",
            peat_ppm=5,
            natural_color=True,
            non_chill_filtered=True,
        )
        # Verify relationship
        self.assertEqual(product.whiskey_details, details)
        self.assertEqual(details.product, product)

    def test_whiskey_details_fields_saved(self):
        """WhiskeyDetails fields saved to individual columns."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type="single_malt",
            distillery="Test Distillery",
            peat_ppm=25,
            natural_color=False,
            non_chill_filtered=True,
        )
        details.refresh_from_db()
        self.assertEqual(details.whiskey_type, "single_malt")
        self.assertEqual(details.distillery, "Test Distillery")
        self.assertEqual(details.peat_ppm, 25)
        self.assertFalse(details.natural_color)
        self.assertTrue(details.non_chill_filtered)

    def test_whiskey_details_one_to_one(self):
        """Only one WhiskeyDetails per product."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
        )
        WhiskeyDetails.objects.create(
            product=product,
            whiskey_type="single_malt",
        )
        # Attempting to create another should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            WhiskeyDetails.objects.create(
                product=product,
                whiskey_type="blended",
            )


class TestPortWineDetailsSaving(TestCase):
    """Tests for PortWineDetails related model."""

    def test_creates_port_details_for_port_wine(self):
        """PortWineDetails can be created and linked to port wine product."""
        product = DiscoveredProduct.objects.create(
            name="Taylor's Vintage Port 2017",
            product_type="port_wine",
        )
        details = PortWineDetails.objects.create(
            product=product,
            style="vintage",
            harvest_year=2017,
            producer_house="Taylor's",
        )
        # Verify relationship
        self.assertEqual(product.port_details, details)
        self.assertEqual(details.product, product)

    def test_port_details_fields_saved(self):
        """PortWineDetails fields saved to individual columns."""
        product = DiscoveredProduct.objects.create(
            name="Test Port",
            product_type="port_wine",
        )
        details = PortWineDetails.objects.create(
            product=product,
            style="tawny",
            harvest_year=2010,
            producer_house="Test House",
            indication_age="20 Year Old",
        )
        details.refresh_from_db()
        self.assertEqual(details.style, "tawny")
        self.assertEqual(details.harvest_year, 2010)
        self.assertEqual(details.producer_house, "Test House")
        self.assertEqual(details.indication_age, "20 Year Old")

    def test_port_details_one_to_one(self):
        """Only one PortWineDetails per product."""
        product = DiscoveredProduct.objects.create(
            name="Test Port",
            product_type="port_wine",
        )
        PortWineDetails.objects.create(
            product=product,
            style="vintage",
        )
        # Attempting to create another should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PortWineDetails.objects.create(
                product=product,
                style="tawny",
            )


class TestFullProductSaving(TestCase):
    """Integration tests for complete product saving."""

    def test_save_complete_whiskey_product(self):
        """Save a complete whiskey product with all data to individual columns."""
        brand = DiscoveredBrand.objects.create(name="Glenfiddich", slug="glenfiddich")
        product = DiscoveredProduct.objects.create(
            # Identification
            name="Glenfiddich 12 Year Old",
            brand=brand,
            gtin="5010327000176",
            # Basic Info
            product_type="whiskey",
            abv=Decimal("40.0"),
            volume_ml=700,
            description="A smooth and mellow single malt.",
            age_statement="12",
            country="Scotland",
            region="Speyside",
            # Tasting Profile
            nose_description="Fresh pear and subtle oak.",
            primary_aromas=["pear", "oak", "malt"],
            palate_description="Creamy with butterscotch and oak.",
            palate_flavors=["butterscotch", "oak", "vanilla"],
            initial_taste="Sweet and fruity.",
            mid_palate_evolution="Develops creaminess.",
            mouthfeel="smooth",
            finish_description="Long and mellow.",
            finish_flavors=["oak", "spice"],
            finish_length=7,
            # Enrichment
            best_price=Decimal("32.99"),
            images=[{"url": "http://example.com/glenfiddich.jpg"}],
            ratings=[{"source": "whiskybase", "score": 85}],
            awards=[{"name": "Gold", "competition": "IWSC"}],
            # Verification
            source_count=3,
        )

        # Create whiskey details
        details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type="single_malt",
            distillery="Glenfiddich",
            natural_color=True,
            non_chill_filtered=False,
        )

        # Reload and verify all data in columns
        product.refresh_from_db()
        details.refresh_from_db()

        # Identification
        self.assertEqual(product.name, "Glenfiddich 12 Year Old")
        self.assertEqual(product.brand, brand)
        self.assertEqual(product.gtin, "5010327000176")

        # Basic Info
        self.assertEqual(product.product_type, "whiskey")
        self.assertEqual(product.abv, Decimal("40.0"))
        self.assertEqual(product.age_statement, "12")
        self.assertEqual(product.country, "Scotland")
        self.assertEqual(product.region, "Speyside")

        # Tasting Profile
        self.assertEqual(product.nose_description, "Fresh pear and subtle oak.")
        self.assertEqual(product.primary_aromas, ["pear", "oak", "malt"])
        self.assertEqual(product.palate_description, "Creamy with butterscotch and oak.")
        self.assertEqual(product.palate_flavors, ["butterscotch", "oak", "vanilla"])

        # WhiskeyDetails
        self.assertEqual(details.whiskey_type, "single_malt")
        self.assertEqual(details.distillery, "Glenfiddich")

    def test_save_complete_port_wine_product(self):
        """Save a complete port wine product with all data to individual columns."""
        brand = DiscoveredBrand.objects.create(name="Taylor's", slug="taylors")
        product = DiscoveredProduct.objects.create(
            # Identification
            name="Taylor's Vintage Port 2017",
            brand=brand,
            # Basic Info
            product_type="port_wine",
            abv=Decimal("20.0"),
            volume_ml=750,
            description="A classic vintage port.",
            country="Portugal",
            region="Douro",
            # Tasting Profile
            nose_description="Dark fruit and floral notes.",
            primary_aromas=["blackberry", "plum", "violet"],
            palate_description="Rich and concentrated.",
            palate_flavors=["blackberry", "chocolate", "spice"],
            finish_description="Long and persistent.",
            finish_flavors=["fruit", "tannin"],
        )

        # Create port details
        details = PortWineDetails.objects.create(
            product=product,
            style="vintage",
            harvest_year=2017,
            producer_house="Taylor's",
        )

        # Reload and verify
        product.refresh_from_db()
        details.refresh_from_db()

        self.assertEqual(product.name, "Taylor's Vintage Port 2017")
        self.assertEqual(product.product_type, "port_wine")
        self.assertEqual(details.style, "vintage")
        self.assertEqual(details.harvest_year, 2017)
        self.assertEqual(details.producer_house, "Taylor's")


class TestBrandRelationship(TestCase):
    """Tests for brand relationship."""

    def test_brand_saved_to_foreign_key(self):
        """Brand relationship saved via ForeignKey, not JSON."""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            product_type="whiskey",
            brand=brand,
        )
        # Reload and verify FK relationship
        saved_product = DiscoveredProduct.objects.get(id=product.id)
        self.assertEqual(saved_product.brand_id, brand.id)
        self.assertEqual(saved_product.brand.name, "Test Brand")

    def test_product_without_brand(self):
        """Product can be created without brand (nullable FK)."""
        product = DiscoveredProduct.objects.create(
            name="Unknown Brand Whiskey",
            product_type="whiskey",
        )
        self.assertIsNone(product.brand)
