"""
Unit tests for ECPCalculator Service.

Task 3.1: Create ECPCalculator Service

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3

Tests verify:
- calculate_ecp_by_group() returns correct structure
- calculate_total_ecp() returns correct percentage
- get_missing_fields_by_group() returns missing fields
- Percentage calculations are accurate
"""

from django.test import TestCase

from crawler.services.ecp_calculator import ECPCalculator


class ECPCalculatorBasicTests(TestCase):
    """Tests for basic ECPCalculator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.sample_field_groups = [
            {
                "group_key": "basic_product_info",
                "display_name": "Basic Product Info",
                "fields": ["name", "brand", "abv", "volume_ml", "description"],
                "is_active": True,
            },
            {
                "group_key": "tasting_nose",
                "display_name": "Tasting Profile - Nose",
                "fields": ["nose_description", "primary_aromas", "secondary_aromas"],
                "is_active": True,
            },
        ]

    def test_calculate_ecp_by_group_basic(self):
        """Test calculate_ecp_by_group returns correct structure."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            # Missing: volume_ml, description
            "nose_description": "Vanilla and oak",
            # Missing: primary_aromas, secondary_aromas
        }

        result = self.calculator.calculate_ecp_by_group(product_data, self.sample_field_groups)

        # Check structure
        self.assertIn("basic_product_info", result)
        self.assertIn("tasting_nose", result)

        # Check basic_product_info
        self.assertEqual(result["basic_product_info"]["populated"], 3)
        self.assertEqual(result["basic_product_info"]["total"], 5)
        self.assertAlmostEqual(result["basic_product_info"]["percentage"], 60.0, places=2)
        self.assertIn("volume_ml", result["basic_product_info"]["missing"])
        self.assertIn("description", result["basic_product_info"]["missing"])

        # Check tasting_nose
        self.assertEqual(result["tasting_nose"]["populated"], 1)
        self.assertEqual(result["tasting_nose"]["total"], 3)
        self.assertAlmostEqual(result["tasting_nose"]["percentage"], 33.33, places=2)

    def test_calculate_ecp_by_group_all_populated(self):
        """Test calculate_ecp_by_group when all fields populated."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "nose_description": "Vanilla and oak",
            "primary_aromas": ["vanilla", "oak"],
            "secondary_aromas": ["spice"],
        }

        result = self.calculator.calculate_ecp_by_group(product_data, self.sample_field_groups)

        self.assertEqual(result["basic_product_info"]["percentage"], 100.0)
        self.assertEqual(result["basic_product_info"]["missing"], [])
        self.assertEqual(result["tasting_nose"]["percentage"], 100.0)
        self.assertEqual(result["tasting_nose"]["missing"], [])

    def test_calculate_ecp_by_group_empty_data(self):
        """Test calculate_ecp_by_group with empty product data."""
        product_data = {}

        result = self.calculator.calculate_ecp_by_group(product_data, self.sample_field_groups)

        self.assertEqual(result["basic_product_info"]["populated"], 0)
        self.assertEqual(result["basic_product_info"]["percentage"], 0.0)
        self.assertEqual(len(result["basic_product_info"]["missing"]), 5)


class ECPCalculatorTotalTests(TestCase):
    """Tests for calculate_total_ecp."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_calculate_total_ecp_basic(self):
        """Test calculate_total_ecp returns correct percentage."""
        ecp_by_group = {
            "basic_product_info": {
                "populated": 3,
                "total": 5,
                "percentage": 60.0,
                "missing": ["volume_ml", "description"],
            },
            "tasting_nose": {
                "populated": 2,
                "total": 3,
                "percentage": 66.67,
                "missing": ["secondary_aromas"],
            },
        }

        result = self.calculator.calculate_total_ecp(ecp_by_group)

        # Total: 5 populated out of 8 = 62.5%
        self.assertAlmostEqual(result, 62.5, places=2)

    def test_calculate_total_ecp_all_populated(self):
        """Test calculate_total_ecp when all fields populated."""
        ecp_by_group = {
            "basic_product_info": {
                "populated": 5,
                "total": 5,
                "percentage": 100.0,
                "missing": [],
            },
            "tasting_nose": {
                "populated": 3,
                "total": 3,
                "percentage": 100.0,
                "missing": [],
            },
        }

        result = self.calculator.calculate_total_ecp(ecp_by_group)

        self.assertEqual(result, 100.0)

    def test_calculate_total_ecp_empty(self):
        """Test calculate_total_ecp with no populated fields."""
        ecp_by_group = {
            "basic_product_info": {
                "populated": 0,
                "total": 5,
                "percentage": 0.0,
                "missing": ["name", "brand", "abv", "volume_ml", "description"],
            },
        }

        result = self.calculator.calculate_total_ecp(ecp_by_group)

        self.assertEqual(result, 0.0)

    def test_calculate_total_ecp_empty_groups(self):
        """Test calculate_total_ecp with empty groups dict."""
        result = self.calculator.calculate_total_ecp({})

        self.assertEqual(result, 0.0)


class ECPCalculatorMissingFieldsTests(TestCase):
    """Tests for get_missing_fields_by_group."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.sample_field_groups = [
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

    def test_get_missing_fields_by_group_basic(self):
        """Test get_missing_fields_by_group returns correct missing fields."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "nose_description": "Vanilla",
        }

        result = self.calculator.get_missing_fields_by_group(product_data, self.sample_field_groups)

        self.assertIn("basic_product_info", result)
        self.assertIn("tasting_nose", result)
        self.assertEqual(set(result["basic_product_info"]), {"abv", "volume_ml", "description"})
        self.assertEqual(set(result["tasting_nose"]), {"primary_aromas", "secondary_aromas"})

    def test_get_missing_fields_by_group_none_missing(self):
        """Test get_missing_fields_by_group when all populated."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "nose_description": "Vanilla",
            "primary_aromas": ["vanilla"],
            "secondary_aromas": ["spice"],
        }

        result = self.calculator.get_missing_fields_by_group(product_data, self.sample_field_groups)

        self.assertEqual(result["basic_product_info"], [])
        self.assertEqual(result["tasting_nose"], [])

    def test_get_missing_fields_by_group_all_missing(self):
        """Test get_missing_fields_by_group when all fields missing."""
        product_data = {}

        result = self.calculator.get_missing_fields_by_group(product_data, self.sample_field_groups)

        self.assertEqual(len(result["basic_product_info"]), 5)
        self.assertEqual(len(result["tasting_nose"]), 3)


class ECPCalculatorEdgeCasesTests(TestCase):
    """Tests for edge cases in ECPCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_empty_string_not_counted_as_populated(self):
        """Test empty string fields are not counted as populated."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["field1", "field2", "field3"],
                "is_active": True,
            },
        ]
        product_data = {
            "field1": "value",
            "field2": "",  # Empty string
            "field3": "   ",  # Whitespace only
        }

        result = self.calculator.calculate_ecp_by_group(product_data, field_groups)

        self.assertEqual(result["test"]["populated"], 1)  # Only field1 counts

    def test_none_value_not_counted_as_populated(self):
        """Test None values are not counted as populated."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["field1", "field2"],
                "is_active": True,
            },
        ]
        product_data = {
            "field1": "value",
            "field2": None,
        }

        result = self.calculator.calculate_ecp_by_group(product_data, field_groups)

        self.assertEqual(result["test"]["populated"], 1)

    def test_empty_list_not_counted_as_populated(self):
        """Test empty lists are not counted as populated."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["field1", "field2"],
                "is_active": True,
            },
        ]
        product_data = {
            "field1": ["value"],
            "field2": [],  # Empty list
        }

        result = self.calculator.calculate_ecp_by_group(product_data, field_groups)

        self.assertEqual(result["test"]["populated"], 1)

    def test_inactive_group_skipped(self):
        """Test inactive field groups are skipped."""
        field_groups = [
            {
                "group_key": "active",
                "fields": ["field1"],
                "is_active": True,
            },
            {
                "group_key": "inactive",
                "fields": ["field2"],
                "is_active": False,
            },
        ]
        product_data = {"field1": "value", "field2": "value"}

        result = self.calculator.calculate_ecp_by_group(product_data, field_groups)

        self.assertIn("active", result)
        self.assertNotIn("inactive", result)

    def test_percentage_precision(self):
        """Test percentage calculations have proper precision."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["f1", "f2", "f3"],
                "is_active": True,
            },
        ]
        product_data = {"f1": "value"}

        result = self.calculator.calculate_ecp_by_group(product_data, field_groups)

        # 1/3 = 33.333...
        self.assertAlmostEqual(result["test"]["percentage"], 33.33, places=2)


class ECPCalculatorWhiskeyTests(TestCase):
    """Tests for ECPCalculator with whiskey field groups."""

    def setUp(self):
        """Set up test fixtures with whiskey field groups."""
        self.calculator = ECPCalculator()
        # Simplified whiskey field groups for testing
        self.whiskey_field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["product_type", "category", "abv", "volume_ml", "description", "age_statement", "country", "region", "bottler"],
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

    def test_whiskey_partial_data(self):
        """Test ECP calculation for whiskey with partial data."""
        product_data = {
            "product_type": "whiskey",
            "category": "Single Malt",
            "abv": "46%",
            "volume_ml": 700,
            "description": "A Highland single malt",
            "country": "Scotland",
            "region": "Highland",
            # Missing: age_statement, bottler
            "nose_description": "Vanilla and honey",
            "primary_aromas": ["vanilla", "honey"],
            # Missing: primary_intensity, secondary_aromas, aroma_evolution
            "primary_cask": "Ex-Bourbon",
            # Missing: finishing_cask, wood_type, cask_treatment, maturation_notes
        }

        result = self.calculator.calculate_ecp_by_group(product_data, self.whiskey_field_groups)
        total = self.calculator.calculate_total_ecp(result)

        # basic_product_info: 7/9 = 77.78%
        # tasting_nose: 2/5 = 40%
        # cask_info: 1/5 = 20%
        # Total: 10/19 = 52.63%
        self.assertEqual(result["basic_product_info"]["populated"], 7)
        self.assertEqual(result["tasting_nose"]["populated"], 2)
        self.assertEqual(result["cask_info"]["populated"], 1)
        self.assertAlmostEqual(total, 52.63, places=2)


class ECPCalculatorPortWineTests(TestCase):
    """Tests for ECPCalculator with port wine field groups."""

    def setUp(self):
        """Set up test fixtures with port wine field groups."""
        self.calculator = ECPCalculator()
        self.port_field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["product_type", "style", "abv", "volume_ml", "description", "country", "region", "bottler"],
                "is_active": True,
            },
            {
                "group_key": "port_details",
                "fields": ["indication_age", "harvest_year", "bottling_year", "producer_house", "quinta", "douro_subregion", "grape_varieties"],
                "is_active": True,
            },
        ]

    def test_port_wine_partial_data(self):
        """Test ECP calculation for port wine with partial data."""
        product_data = {
            "product_type": "port_wine",
            "style": "Tawny",
            "abv": "20%",
            "volume_ml": 750,
            "description": "A 20 year old tawny",
            "country": "Portugal",
            # Missing: region, bottler
            "indication_age": "20 Year Old",
            "producer_house": "Graham's",
            # Missing: harvest_year, bottling_year, quinta, douro_subregion, grape_varieties
        }

        result = self.calculator.calculate_ecp_by_group(product_data, self.port_field_groups)
        total = self.calculator.calculate_total_ecp(result)

        # basic_product_info: 6/8 = 75%
        # port_details: 2/7 = 28.57%
        # Total: 8/15 = 53.33%
        self.assertEqual(result["basic_product_info"]["populated"], 6)
        self.assertEqual(result["port_details"]["populated"], 2)
        self.assertAlmostEqual(total, 53.33, places=2)
