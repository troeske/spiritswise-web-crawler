"""
Unit tests for V3 Threshold Loading from Database.

Task 2.6: Load Thresholds from Database

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 6

Tests verify:
- Loading whiskey thresholds from QualityGateConfig
- Loading port wine thresholds
- Fallback to defaults if no config
- Proper handling of database errors
"""

from unittest.mock import MagicMock, patch, PropertyMock
from django.test import TestCase

from crawler.services.quality_gate_v3 import QualityGateV3, ProductStatus


class ThresholdLoadingBasicTests(TestCase):
    """Tests for basic threshold loading behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_loads_skeleton_required_from_config(self):
        """Test loading skeleton_required_fields from config."""
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name", "custom_partial_field"]
        mock_config.baseline_required_fields = ["name", "custom_baseline_field"]
        mock_config.baseline_or_fields = []
        mock_config.baseline_or_field_exceptions = {}
        mock_config.enriched_required_fields = []
        mock_config.enriched_or_fields = []

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            # Product with only name - should be SKELETON
            data = {"name": "Test"}
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.SKELETON)

    def test_loads_partial_required_from_config(self):
        """Test loading partial_required_fields from config."""
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name", "brand", "custom_field"]
        mock_config.baseline_required_fields = []
        mock_config.baseline_or_fields = []
        mock_config.baseline_or_field_exceptions = {}
        mock_config.enriched_required_fields = []
        mock_config.enriched_or_fields = []

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            # Missing custom_field
            data = {"name": "Test", "brand": "Test Brand"}
            result = self.quality_gate.assess(data, "whiskey")
            # Should be SKELETON because missing custom_field
            self.assertEqual(result.status, ProductStatus.SKELETON)

            # With custom_field
            data["custom_field"] = "value"
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_loads_baseline_required_from_config(self):
        """Test loading baseline_required_fields from config."""
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name", "brand"]
        mock_config.baseline_required_fields = ["name", "brand", "special_field"]
        mock_config.baseline_or_fields = []
        mock_config.baseline_or_field_exceptions = {}
        mock_config.enriched_required_fields = []
        mock_config.enriched_or_fields = []

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            # Missing special_field
            data = {"name": "Test", "brand": "Test Brand"}
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

            # With special_field
            data["special_field"] = "value"
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class DefaultFallbackTests(TestCase):
    """Tests for fallback to defaults when no config exists."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_fallback_to_default_skeleton(self):
        """Test fallback to default skeleton requirements."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=None):
            data = {"name": "Test Whiskey"}
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.SKELETON)

    def test_fallback_to_default_partial(self):
        """Test fallback to default partial requirements."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=None):
            # Default partial: name, brand, abv, region, country, category
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

    def test_fallback_to_default_baseline(self):
        """Test fallback to default baseline requirements."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=None):
            data = {
                "name": "Test Whiskey",
                "brand": "Test Brand",
                "abv": "40%",
                "region": "Scotland",
                "country": "Scotland",
                "category": "Single Malt",
                "volume_ml": 700,
                "description": "A fine whiskey",
                "primary_aromas": ["vanilla"],
                "finish_flavors": ["oak"],
                "age_statement": "12 Years",
                "primary_cask": "Ex-Bourbon",
                "palate_flavors": ["honey"],
            }
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.BASELINE)

    def test_fallback_to_default_enriched_or_fields(self):
        """Test fallback to default enriched OR fields."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=None):
            data = {
                "name": "Test Whiskey",
                "brand": "Test Brand",
                "abv": "40%",
                "region": "Scotland",
                "country": "Scotland",
                "category": "Single Malt",
                "volume_ml": 700,
                "description": "A fine whiskey",
                "primary_aromas": ["vanilla"],
                "finish_flavors": ["oak"],
                "age_statement": "12 Years",
                "primary_cask": "Ex-Bourbon",
                "palate_flavors": ["honey"],
                "mouthfeel": "Full-bodied",
                "complexity": "Complex",
                "finishing_cask": "Sherry",
            }
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.ENRICHED)


class WhiskeyThresholdLoadingTests(TestCase):
    """Tests for whiskey-specific threshold loading."""

    def setUp(self):
        """Set up test fixtures with whiskey config."""
        self.quality_gate = QualityGateV3()
        self.mock_whiskey_config = MagicMock()
        self.mock_whiskey_config.skeleton_required_fields = ["name"]
        self.mock_whiskey_config.partial_required_fields = [
            "name", "brand", "abv", "region", "country", "category"
        ]
        self.mock_whiskey_config.baseline_required_fields = [
            "name", "brand", "abv", "region", "country", "category",
            "volume_ml", "description", "primary_aromas", "finish_flavors",
            "age_statement", "primary_cask", "palate_flavors"
        ]
        self.mock_whiskey_config.baseline_or_fields = []
        self.mock_whiskey_config.baseline_or_field_exceptions = {}
        self.mock_whiskey_config.enriched_required_fields = ["mouthfeel"]
        self.mock_whiskey_config.enriched_or_fields = [
            ["complexity", "overall_complexity"],
            ["finishing_cask", "maturation_notes"]
        ]

    def test_whiskey_config_loaded(self):
        """Test whiskey config is loaded correctly."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_whiskey_config):
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


class PortWineThresholdLoadingTests(TestCase):
    """Tests for port wine-specific threshold loading."""

    def setUp(self):
        """Set up test fixtures with port wine config."""
        self.quality_gate = QualityGateV3()
        self.mock_port_config = MagicMock()
        self.mock_port_config.skeleton_required_fields = ["name"]
        self.mock_port_config.partial_required_fields = [
            "name", "brand", "abv", "style"
        ]
        self.mock_port_config.baseline_required_fields = [
            "name", "brand", "abv", "style",
            "volume_ml", "description",
            "primary_aromas", "finish_flavors", "palate_flavors",
            "producer_house"
        ]
        self.mock_port_config.baseline_or_fields = [["indication_age", "harvest_year"]]
        self.mock_port_config.baseline_or_field_exceptions = {"style": ["ruby", "reserve_ruby"]}
        self.mock_port_config.enriched_required_fields = ["mouthfeel"]
        self.mock_port_config.enriched_or_fields = [
            ["complexity", "overall_complexity"],
            ["grape_varieties", "quinta"]
        ]

    def test_port_wine_config_loaded(self):
        """Test port wine config is loaded correctly."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_port_config):
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Ruby",
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.PARTIAL)

    def test_port_wine_or_exception_loaded(self):
        """Test port wine OR exception is loaded correctly."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=self.mock_port_config):
            # Ruby style should waive age requirement
            data = {
                "name": "Graham's Six Grapes",
                "brand": "Graham's",
                "abv": "20%",
                "style": "Ruby",
                "volume_ml": 750,
                "description": "A ruby port",
                "primary_aromas": ["plum"],
                "finish_flavors": ["spice"],
                "palate_flavors": ["cherry"],
                "producer_house": "Graham's",
                # No indication_age - should still be BASELINE for Ruby
            }
            result = self.quality_gate.assess(data, "port_wine")
            self.assertEqual(result.status, ProductStatus.BASELINE)


class DatabaseErrorHandlingTests(TestCase):
    """Tests for handling database errors gracefully."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_database_error_falls_back_to_defaults(self):
        """Test database error falls back to default thresholds."""
        mock_config_service = MagicMock()
        mock_config_service.get_quality_gate_config.side_effect = Exception("Database error")

        self.quality_gate.config_service = mock_config_service

        # Should not raise, should use defaults
        data = {"name": "Test Whiskey"}
        result = self.quality_gate.assess(data, "whiskey")
        self.assertEqual(result.status, ProductStatus.SKELETON)

    def test_none_config_uses_defaults(self):
        """Test None config uses default thresholds."""
        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=None):
            data = {"name": "Test Whiskey"}
            result = self.quality_gate.assess(data, "whiskey")
            self.assertEqual(result.status, ProductStatus.SKELETON)


class ConfigFieldNoneHandlingTests(TestCase):
    """Tests for handling None/missing config fields."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = QualityGateV3()

    def test_none_skeleton_required_uses_default(self):
        """Test None skeleton_required_fields uses default."""
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = None
        mock_config.partial_required_fields = None
        mock_config.baseline_required_fields = None
        mock_config.baseline_or_fields = None
        mock_config.baseline_or_field_exceptions = None
        mock_config.enriched_required_fields = None
        mock_config.enriched_or_fields = None

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            data = {"name": "Test Whiskey"}
            result = self.quality_gate.assess(data, "whiskey")
            # Should use default which requires only name for SKELETON
            self.assertEqual(result.status, ProductStatus.SKELETON)

    def test_empty_list_enriched_required_uses_default(self):
        """Test empty list enriched_required_fields falls back to default (mouthfeel)."""
        # Note: In Python, `[] or DEFAULT` returns DEFAULT because [] is falsy
        # This is intentional - empty list falls back to defaults
        mock_config = MagicMock()
        mock_config.skeleton_required_fields = ["name"]
        mock_config.partial_required_fields = ["name"]  # Minimal partial
        mock_config.baseline_required_fields = ["name"]  # Minimal baseline
        mock_config.baseline_or_fields = []
        mock_config.baseline_or_field_exceptions = {}
        mock_config.enriched_required_fields = []  # Empty list - falls back to default ["mouthfeel"]
        mock_config.enriched_or_fields = []  # Empty list - falls back to defaults

        with patch.object(self.quality_gate, '_get_quality_gate_config', return_value=mock_config):
            data = {"name": "Test Whiskey"}
            result = self.quality_gate.assess(data, "whiskey")
            # Should be BASELINE because enriched_required falls back to defaults (mouthfeel)
            self.assertEqual(result.status, ProductStatus.BASELINE)
