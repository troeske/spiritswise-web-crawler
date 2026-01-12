"""
Unit tests for V3 Simplified Status Determination.

Task 2.2: Implement Simplified Status Determination (No Any-Of)

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 2

Tests verify:
- PARTIAL requires ALL partial_required_fields (no any-of logic)
- BASELINE requires ALL baseline_required_fields
- Whiskey vs port wine have different thresholds
- Status progression works correctly
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class SimplifiedStatusDeterminationTests(TestCase):
    """Tests for simplified status determination (no any-of logic)."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_rejected_without_name(self):
        """Test REJECTED status when name is missing."""
        data = {"brand": "Test Brand", "abv": "40%"}
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.REJECTED)

    def test_skeleton_with_name_only(self):
        """Test SKELETON status with only name."""
        data = {"name": "Test Whiskey"}
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.SKELETON)

    def test_partial_requires_all_fields(self):
        """Test PARTIAL requires ALL partial_required_fields (no any-of)."""
        # Partial requires: name, brand, abv, region, country, category
        # Missing country - should NOT be PARTIAL
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "category": "Single Malt",
            # Missing: country
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.SKELETON)
        self.assertIn("country", result.missing_required_fields)

    def test_partial_achieved_with_all_required(self):
        """Test PARTIAL achieved when ALL required fields present."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_baseline_requires_all_fields(self):
        """Test BASELINE requires ALL baseline_required_fields."""
        # Baseline requires: name, brand, abv, region, country, category,
        #                    volume_ml, description, primary_aromas, finish_flavors,
        #                    age_statement, primary_cask, palate_flavors
        # Missing primary_cask - should NOT be BASELINE
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            # Missing: primary_cask
            "palate_flavors": ["honey", "caramel"],
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.PARTIAL)
        self.assertIn("primary_cask", result.missing_required_fields)

    def test_baseline_achieved_with_all_required(self):
        """Test BASELINE achieved when ALL required fields present."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey", "caramel"],
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.BASELINE)


class WhiskeyThresholdsTests(TestCase):
    """Tests for whiskey-specific thresholds."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_whiskey_partial_threshold(self):
        """Test whiskey partial requires region, country, category."""
        # Whiskey partial: name, brand, abv, region, country, category
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Highland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_whiskey_baseline_includes_cask(self):
        """Test whiskey baseline requires primary_cask."""
        # Partial but missing primary_cask
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Highland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla"],
            "finish_flavors": ["oak"],
            "age_statement": "12 Years",
            "palate_flavors": ["honey"],
            # Missing primary_cask
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.PARTIAL)


class PortWineThresholdsTests(TestCase):
    """Tests for port wine-specific thresholds."""

    def setUp(self):
        """Set up test fixtures with mocked config."""
        self.quality_gate = QualityGateV3()

    def test_port_partial_threshold(self):
        """Test port wine partial requires style instead of region/country/category."""
        # Port wine partial: name, brand, abv, style (not region/country/category)
        # Using mock config
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name", "brand", "abv", "style"]
        mock_config.baseline_required_fields = [
            "name", "brand", "abv", "style",
            "volume_ml", "description",
            "primary_aromas", "finish_flavors", "palate_flavors",
            "producer_house"
        ]
        mock_config.baseline_or_fields = [["indication_age", "harvest_year"]]
        mock_config.baseline_or_field_exceptions = {"style": ["ruby", "reserve_ruby"]}
        mock_config.enriched_required_fields = ["mouthfeel"]
        mock_config.enriched_or_fields = [
            ["complexity", "overall_complexity"],
            ["grape_varieties", "quinta"]
        ]

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Reserve Ruby",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_port_baseline_requires_producer_house(self):
        """Test port wine baseline requires producer_house."""
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name", "brand", "abv", "style"]
        mock_config.baseline_required_fields = [
            "name", "brand", "abv", "style",
            "volume_ml", "description",
            "primary_aromas", "finish_flavors", "palate_flavors",
            "producer_house"
        ]
        mock_config.baseline_or_fields = []
        mock_config.baseline_or_field_exceptions = {}
        mock_config.enriched_required_fields = ["mouthfeel"]
        mock_config.enriched_or_fields = []

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            # Missing producer_house
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Reserve Ruby",
                "volume_ml": 750,
                "description": "A rich port wine",
                "primary_aromas": ["plum", "cherry"],
                "finish_flavors": ["chocolate"],
                "palate_flavors": ["blackberry"],
                # Missing: producer_house
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)
            self.assertIn("producer_house", result.missing_required_fields)


class StatusProgressionTests(TestCase):
    """Tests for status progression through all levels."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_status_progression_rejected_to_skeleton(self):
        """Test adding name moves from REJECTED to SKELETON."""
        data = {"brand": "Test"}
        result1 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result1.status, ProductStatus.REJECTED)

        data["name"] = "Test Whiskey"
        result2 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result2.status, ProductStatus.SKELETON)

    def test_status_progression_skeleton_to_partial(self):
        """Test adding partial fields moves from SKELETON to PARTIAL."""
        data = {"name": "Test Whiskey"}
        result1 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result1.status, ProductStatus.SKELETON)

        data.update({
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        })
        result2 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result2.status, ProductStatus.PARTIAL)

    def test_status_progression_partial_to_baseline(self):
        """Test adding baseline fields moves from PARTIAL to BASELINE."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result1 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result1.status, ProductStatus.PARTIAL)

        data.update({
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey", "caramel"],
        })
        result2 = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result2.status, ProductStatus.BASELINE)


class MissingFieldsReportingTests(TestCase):
    """Tests for missing fields reporting."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_missing_fields_for_partial_upgrade(self):
        """Test missing fields reported for PARTIAL upgrade."""
        data = {"name": "Test Whiskey"}
        result = self.quality_gate.assess(data, "whiskey")

        # Should list fields needed to reach PARTIAL
        self.assertIn("brand", result.missing_required_fields)
        self.assertIn("abv", result.missing_required_fields)
        self.assertIn("region", result.missing_required_fields)
        self.assertIn("country", result.missing_required_fields)
        self.assertIn("category", result.missing_required_fields)

    def test_missing_fields_for_baseline_upgrade(self):
        """Test missing fields reported for BASELINE upgrade."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
        }
        result = self.quality_gate.assess(data, "whiskey")

        # Should list fields needed to reach BASELINE
        self.assertIn("volume_ml", result.missing_required_fields)
        self.assertIn("description", result.missing_required_fields)
        self.assertIn("primary_aromas", result.missing_required_fields)
        self.assertIn("finish_flavors", result.missing_required_fields)
        self.assertIn("age_statement", result.missing_required_fields)
        self.assertIn("primary_cask", result.missing_required_fields)
        self.assertIn("palate_flavors", result.missing_required_fields)

    def test_no_missing_fields_at_baseline(self):
        """Test no missing required fields when BASELINE achieved."""
        data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": "40%",
            "region": "Scotland",
            "country": "Scotland",
            "category": "Single Malt",
            "volume_ml": 700,
            "description": "A fine whiskey",
            "primary_aromas": ["vanilla", "oak"],
            "finish_flavors": ["spice", "smoke"],
            "age_statement": "12 Years",
            "primary_cask": "Ex-Bourbon",
            "palate_flavors": ["honey", "caramel"],
        }
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.BASELINE)
        # Missing required for next level (ENRICHED) should be mouthfeel
        self.assertIn("mouthfeel", result.missing_required_fields)
