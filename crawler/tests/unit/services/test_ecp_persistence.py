"""
Unit tests for ECP Persistence.

Task 3.5: Save ECP to DiscoveredProduct

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3

Tests verify:
- ECP saved after enrichment
- ECP updated on re-enrichment
- ecp_total indexed for queries
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from crawler.models import DiscoveredProduct
from crawler.services.ecp_calculator import ECPCalculator


class ECPSaveToProductTests(TestCase):
    """Tests for saving ECP to DiscoveredProduct."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand", "abv", "volume_ml", "description"],
                "is_active": True,
            },
            {
                "group_key": "tasting_nose",
                "fields": ["nose_description", "primary_aromas", "secondary_aromas"],
                "is_active": True,
            },
        ]

    def test_product_has_enrichment_completion_field(self):
        """Test DiscoveredProduct has enrichment_completion JSONField."""
        product = DiscoveredProduct()
        self.assertTrue(hasattr(product, "enrichment_completion"))
        self.assertEqual(product.enrichment_completion, {})

    def test_product_has_ecp_total_field(self):
        """Test DiscoveredProduct has ecp_total DecimalField."""
        product = DiscoveredProduct()
        self.assertTrue(hasattr(product, "ecp_total"))

    def test_save_ecp_json_to_product(self):
        """Test ECP JSON can be saved to product."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand", "abv": "40%"}

        ecp_json = self.calculator.build_ecp_json(product_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = ecp_json
        product.ecp_total = Decimal(str(ecp_json["total"]["percentage"]))

        self.assertEqual(product.enrichment_completion["basic_product_info"]["populated"], 3)
        self.assertEqual(product.ecp_total, Decimal("37.5"))

    def test_ecp_json_includes_all_groups(self):
        """Test saved ECP JSON includes all field groups."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "nose_description": "Vanilla",
        }

        ecp_json = self.calculator.build_ecp_json(product_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = ecp_json

        self.assertIn("basic_product_info", product.enrichment_completion)
        self.assertIn("tasting_nose", product.enrichment_completion)
        self.assertIn("total", product.enrichment_completion)


class ECPUpdateOnReEnrichmentTests(TestCase):
    """Tests for ECP updates during re-enrichment."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand", "abv", "volume_ml", "description"],
                "is_active": True,
            },
        ]

    def test_ecp_updates_when_fields_added(self):
        """Test ECP updates when new fields are enriched."""
        # Initial state
        initial_data = {"name": "Test Whiskey", "brand": "Test Brand"}
        initial_ecp = self.calculator.build_ecp_json(initial_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = initial_ecp
        product.ecp_total = Decimal(str(initial_ecp["total"]["percentage"]))

        initial_total = product.ecp_total

        # After enrichment adds more fields
        enriched_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
        }
        enriched_ecp = self.calculator.build_ecp_json(enriched_data, self.field_groups)

        product.enrichment_completion = enriched_ecp
        product.ecp_total = Decimal(str(enriched_ecp["total"]["percentage"]))

        self.assertGreater(product.ecp_total, initial_total)
        self.assertEqual(product.ecp_total, Decimal("100.0"))

    def test_last_updated_changes_on_re_enrichment(self):
        """Test last_updated timestamp changes on re-enrichment."""
        # Initial state
        initial_data = {"name": "Test Whiskey"}
        initial_ecp = self.calculator.build_ecp_json(initial_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = initial_ecp
        initial_timestamp = product.enrichment_completion["last_updated"]

        # Small delay then re-enrichment
        import time
        time.sleep(0.01)

        enriched_data = {"name": "Test Whiskey", "brand": "Test Brand"}
        enriched_ecp = self.calculator.build_ecp_json(enriched_data, self.field_groups)
        product.enrichment_completion = enriched_ecp

        self.assertNotEqual(
            product.enrichment_completion["last_updated"],
            initial_timestamp
        )


class ECPQueryTests(TestCase):
    """Tests for querying products by ECP."""

    def test_ecp_total_is_queryable_field(self):
        """Test ecp_total can be used in database queries."""
        # Verify the field exists and is a DecimalField
        from django.db import models
        ecp_field = DiscoveredProduct._meta.get_field("ecp_total")
        self.assertIsInstance(ecp_field, models.DecimalField)

    def test_ecp_total_has_db_index(self):
        """Test ecp_total has database index for efficient queries."""
        ecp_field = DiscoveredProduct._meta.get_field("ecp_total")
        self.assertTrue(ecp_field.db_index)


class ECPMissingFieldsTrackingTests(TestCase):
    """Tests for tracking missing fields in ECP."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand", "abv", "volume_ml", "description"],
                "is_active": True,
            },
        ]

    def test_ecp_json_tracks_missing_fields(self):
        """Test ECP JSON includes missing fields per group."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        ecp_json = self.calculator.build_ecp_json(product_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = ecp_json

        missing = product.enrichment_completion["basic_product_info"]["missing"]
        self.assertEqual(set(missing), {"abv", "volume_ml", "description"})

    def test_missing_fields_empty_when_all_populated(self):
        """Test missing fields is empty when all fields populated."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
        }

        ecp_json = self.calculator.build_ecp_json(product_data, self.field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/product",
            product_type="whiskey"
        )
        product.enrichment_completion = ecp_json

        missing = product.enrichment_completion["basic_product_info"]["missing"]
        self.assertEqual(missing, [])


class ECPWhiskeyIntegrationTests(TestCase):
    """Tests for ECP with full whiskey field groups."""

    def setUp(self):
        """Set up test fixtures with whiskey-like field groups."""
        self.calculator = ECPCalculator()
        self.whiskey_field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand", "abv", "volume_ml", "description", "country", "region", "bottler", "age_statement"],
                "is_active": True,
            },
            {
                "group_key": "tasting_nose",
                "fields": ["nose_description", "primary_aromas", "primary_intensity", "secondary_aromas", "aroma_evolution"],
                "is_active": True,
            },
            {
                "group_key": "cask_info",
                "fields": ["primary_cask", "finishing_cask", "wood_type", "cask_treatment", "maturation_notes"],
                "is_active": True,
            },
        ]

    def test_whiskey_ecp_calculation_and_save(self):
        """Test ECP calculation and save for whiskey product."""
        product_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "abv": "43%",
            "volume_ml": 700,
            "description": "A rich and complex whisky",
            "country": "Scotland",
            "region": "Islands",
            # Missing: bottler, age_statement
            "nose_description": "Heather honey, peat smoke",
            "primary_aromas": ["honey", "smoke", "citrus"],
            # Missing: primary_intensity, secondary_aromas, aroma_evolution
            "primary_cask": "Sherry Oak",
            # Missing: finishing_cask, wood_type, cask_treatment, maturation_notes
        }

        ecp_json = self.calculator.build_ecp_json(product_data, self.whiskey_field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/highland-park-18",
            product_type="whiskey"
        )
        product.enrichment_completion = ecp_json
        product.ecp_total = Decimal(str(ecp_json["total"]["percentage"]))

        # Verify structure
        self.assertIn("basic_product_info", product.enrichment_completion)
        self.assertIn("tasting_nose", product.enrichment_completion)
        self.assertIn("cask_info", product.enrichment_completion)

        # Verify counts
        # basic: 7/9, tasting: 2/5, cask: 1/5 = 10/19 = 52.63%
        self.assertEqual(product.enrichment_completion["basic_product_info"]["populated"], 7)
        self.assertEqual(product.enrichment_completion["tasting_nose"]["populated"], 2)
        self.assertEqual(product.enrichment_completion["cask_info"]["populated"], 1)
        self.assertAlmostEqual(float(product.ecp_total), 52.63, places=2)


class ECPPortWineIntegrationTests(TestCase):
    """Tests for ECP with port wine field groups."""

    def setUp(self):
        """Set up test fixtures with port wine field groups."""
        self.calculator = ECPCalculator()
        self.port_field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand", "style", "abv", "volume_ml", "description", "country", "region"],
                "is_active": True,
            },
            {
                "group_key": "port_details",
                "fields": ["indication_age", "harvest_year", "bottling_year", "producer_house", "quinta", "douro_subregion", "grape_varieties"],
                "is_active": True,
            },
        ]

    def test_port_wine_ecp_calculation_and_save(self):
        """Test ECP calculation and save for port wine product."""
        product_data = {
            "name": "Graham's 20 Year Old Tawny Port",
            "brand": "Graham's",
            "style": "Tawny",
            "abv": "20%",
            "volume_ml": 750,
            "description": "A rich, complex tawny with notes of nuts and dried fruit",
            "country": "Portugal",
            # Missing: region
            "indication_age": "20 Year Old",
            "producer_house": "Graham's",
            # Missing: harvest_year, bottling_year, quinta, douro_subregion, grape_varieties
        }

        ecp_json = self.calculator.build_ecp_json(product_data, self.port_field_groups)

        product = DiscoveredProduct(
            source_url="https://example.com/grahams-20-year",
            product_type="port_wine"
        )
        product.enrichment_completion = ecp_json
        product.ecp_total = Decimal(str(ecp_json["total"]["percentage"]))

        # Verify structure
        self.assertIn("basic_product_info", product.enrichment_completion)
        self.assertIn("port_details", product.enrichment_completion)

        # Verify counts: basic: 7/8, port: 2/7 = 9/15 = 60%
        self.assertEqual(product.enrichment_completion["basic_product_info"]["populated"], 7)
        self.assertEqual(product.enrichment_completion["port_details"]["populated"], 2)
        self.assertAlmostEqual(float(product.ecp_total), 60.0, places=2)
