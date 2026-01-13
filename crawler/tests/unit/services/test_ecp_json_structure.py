"""
Unit tests for ECP JSON Structure.

Task 3.3: Implement ECP JSON Structure

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3.3

Tests verify:
- JSON structure matches spec format
- last_updated timestamp
- Percentage calculation accuracy
"""

from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from crawler.services.ecp_calculator import ECPCalculator


class ECPJSONStructureTests(TestCase):
    """Tests for ECP JSON structure format."""

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

    def test_json_has_group_keys(self):
        """Test JSON has keys for each field group."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("basic_product_info", result)
        self.assertIn("tasting_nose", result)

    def test_json_group_has_populated_field(self):
        """Test each group has populated count."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("populated", result["basic_product_info"])
        self.assertEqual(result["basic_product_info"]["populated"], 2)

    def test_json_group_has_total_field(self):
        """Test each group has total count."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("total", result["basic_product_info"])
        self.assertEqual(result["basic_product_info"]["total"], 5)

    def test_json_group_has_percentage_field(self):
        """Test each group has percentage."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("percentage", result["basic_product_info"])
        self.assertAlmostEqual(result["basic_product_info"]["percentage"], 40.0, places=2)

    def test_json_group_has_missing_field(self):
        """Test each group has missing list."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("missing", result["basic_product_info"])
        self.assertEqual(set(result["basic_product_info"]["missing"]), {"abv", "volume_ml", "description"})


class ECPJSONTotalTests(TestCase):
    """Tests for ECP JSON total section."""

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

    def test_json_has_total_key(self):
        """Test JSON has total key for overall stats."""
        product_data = {"name": "Test Whiskey", "brand": "Test Brand"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("total", result)
        self.assertIsInstance(result["total"], dict)

    def test_total_has_populated_count(self):
        """Test total has populated count across all groups."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "nose_description": "Vanilla",
        }

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertEqual(result["total"]["populated"], 4)  # 3 basic + 1 tasting

    def test_total_has_total_count(self):
        """Test total has total field count across all groups."""
        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertEqual(result["total"]["total"], 8)  # 5 basic + 3 tasting

    def test_total_has_percentage(self):
        """Test total has percentage of all fields."""
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "volume_ml": 700,
        }

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        # 4 populated out of 8 = 50%
        self.assertAlmostEqual(result["total"]["percentage"], 50.0, places=2)


class ECPJSONTimestampTests(TestCase):
    """Tests for ECP JSON last_updated timestamp."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()
        self.sample_field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": ["name", "brand"],
                "is_active": True,
            },
        ]

    def test_json_has_last_updated(self):
        """Test JSON has last_updated field."""
        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertIn("last_updated", result)

    def test_last_updated_is_iso_format(self):
        """Test last_updated is in ISO 8601 format."""
        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result["last_updated"].replace("Z", "+00:00"))
        self.assertIsInstance(parsed, datetime)

    def test_last_updated_is_utc(self):
        """Test last_updated is in UTC timezone."""
        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        # Should end with Z or have +00:00 offset
        self.assertTrue(
            result["last_updated"].endswith("Z") or "+00:00" in result["last_updated"],
            f"Expected UTC timestamp, got: {result['last_updated']}"
        )

    @patch('crawler.services.ecp_calculator.datetime')
    def test_last_updated_uses_current_time(self, mock_datetime):
        """Test last_updated uses current UTC time."""
        fixed_time = datetime(2026, 1, 12, 10, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.timezone = timezone

        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.sample_field_groups)

        self.assertEqual(result["last_updated"], "2026-01-12T10:30:00+00:00")


class ECPJSONPercentageAccuracyTests(TestCase):
    """Tests for ECP JSON percentage calculation accuracy."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_percentage_rounded_to_two_decimals(self):
        """Test percentages are rounded to 2 decimal places."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["f1", "f2", "f3"],
                "is_active": True,
            },
        ]
        product_data = {"f1": "value"}  # 1/3 = 33.333...

        result = self.calculator.build_ecp_json(product_data, field_groups)

        self.assertEqual(result["test"]["percentage"], 33.33)

    def test_percentage_zero_when_no_fields_populated(self):
        """Test percentage is 0.0 when no fields populated."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["f1", "f2", "f3"],
                "is_active": True,
            },
        ]
        product_data = {}

        result = self.calculator.build_ecp_json(product_data, field_groups)

        self.assertEqual(result["test"]["percentage"], 0.0)
        self.assertEqual(result["total"]["percentage"], 0.0)

    def test_percentage_100_when_all_fields_populated(self):
        """Test percentage is 100.0 when all fields populated."""
        field_groups = [
            {
                "group_key": "test",
                "fields": ["f1", "f2", "f3"],
                "is_active": True,
            },
        ]
        product_data = {"f1": "v1", "f2": "v2", "f3": "v3"}

        result = self.calculator.build_ecp_json(product_data, field_groups)

        self.assertEqual(result["test"]["percentage"], 100.0)
        self.assertEqual(result["total"]["percentage"], 100.0)

    def test_percentage_whiskey_example(self):
        """Test percentage matches spec whiskey example."""
        # Simulating the spec example: basic_product_info 7/9 = 77.78%
        field_groups = [
            {
                "group_key": "basic_product_info",
                "fields": [
                    "name", "brand", "abv", "volume_ml", "description",
                    "country", "region", "bottler", "age_statement"
                ],
                "is_active": True,
            },
        ]
        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "46%",
            "volume_ml": 700,
            "description": "A fine Highland whiskey",
            "country": "Scotland",
            "region": "Highland",
            # Missing: bottler, age_statement
        }

        result = self.calculator.build_ecp_json(product_data, field_groups)

        self.assertEqual(result["basic_product_info"]["populated"], 7)
        self.assertEqual(result["basic_product_info"]["total"], 9)
        self.assertAlmostEqual(result["basic_product_info"]["percentage"], 77.78, places=2)
        self.assertEqual(set(result["basic_product_info"]["missing"]), {"bottler", "age_statement"})


class ECPJSONWhiskeyFullStructureTests(TestCase):
    """Tests for ECP JSON with full whiskey field groups."""

    def setUp(self):
        """Set up test fixtures with whiskey field groups."""
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

    def test_all_groups_in_json(self):
        """Test all field groups appear in JSON."""
        product_data = {"name": "Test Whiskey"}

        result = self.calculator.build_ecp_json(product_data, self.whiskey_field_groups)

        self.assertIn("basic_product_info", result)
        self.assertIn("tasting_nose", result)
        self.assertIn("cask_info", result)
        self.assertIn("total", result)
        self.assertIn("last_updated", result)

    def test_total_aggregates_all_groups(self):
        """Test total correctly aggregates all groups."""
        product_data = {
            # 7 basic fields
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "46%",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "country": "Scotland",
            "region": "Highland",
            # 2 tasting nose fields
            "nose_description": "Vanilla and oak",
            "primary_aromas": ["vanilla", "oak"],
            # 1 cask field
            "primary_cask": "Ex-Bourbon",
        }

        result = self.calculator.build_ecp_json(product_data, self.whiskey_field_groups)

        # Total: 7 + 2 + 1 = 10 populated out of 9 + 5 + 5 = 19 total
        self.assertEqual(result["total"]["populated"], 10)
        self.assertEqual(result["total"]["total"], 19)
        self.assertAlmostEqual(result["total"]["percentage"], 52.63, places=2)


class ECPJSONPortWineStructureTests(TestCase):
    """Tests for ECP JSON with port wine field groups."""

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

    def test_port_wine_json_structure(self):
        """Test port wine ECP JSON structure."""
        product_data = {
            # 6 basic fields
            "name": "Graham's 20 Year Tawny",
            "brand": "Graham's",
            "style": "Tawny",
            "abv": "20%",
            "volume_ml": 750,
            "country": "Portugal",
            # 2 port details fields
            "indication_age": "20 Year Old",
            "producer_house": "Graham's",
        }

        result = self.calculator.build_ecp_json(product_data, self.port_field_groups)

        # basic_product_info: 6/8 = 75%
        self.assertEqual(result["basic_product_info"]["populated"], 6)
        self.assertEqual(result["basic_product_info"]["total"], 8)
        self.assertAlmostEqual(result["basic_product_info"]["percentage"], 75.0, places=2)

        # port_details: 2/7 = 28.57%
        self.assertEqual(result["port_details"]["populated"], 2)
        self.assertEqual(result["port_details"]["total"], 7)
        self.assertAlmostEqual(result["port_details"]["percentage"], 28.57, places=2)

        # Total: 8/15 = 53.33%
        self.assertEqual(result["total"]["populated"], 8)
        self.assertEqual(result["total"]["total"], 15)
        self.assertAlmostEqual(result["total"]["percentage"], 53.33, places=2)
