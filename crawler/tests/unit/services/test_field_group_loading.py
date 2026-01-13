"""
Unit tests for Field Group Loading.

Task 3.2: Implement Field Group Loading

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 3

Tests verify:
- Loading whiskey field groups from database
- Loading port wine field groups
- Caching behavior
- Fallback when no groups exist
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from crawler.services.ecp_calculator import ECPCalculator


class FieldGroupLoadingBasicTests(TestCase):
    """Tests for basic field group loading."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_load_field_groups_from_model(self):
        """Test loading field groups from FieldGroup model."""
        mock_product_type_config = MagicMock()
        mock_field_groups = [
            MagicMock(
                group_key="basic_product_info",
                display_name="Basic Product Info",
                fields=["name", "brand", "abv"],
                is_active=True,
            ),
            MagicMock(
                group_key="tasting_nose",
                display_name="Tasting Profile - Nose",
                fields=["nose_description", "primary_aromas"],
                is_active=True,
            ),
        ]
        mock_product_type_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups

        result = self.calculator.load_field_groups(mock_product_type_config)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["group_key"], "basic_product_info")
        self.assertEqual(result[1]["group_key"], "tasting_nose")

    def test_load_field_groups_converts_to_dict(self):
        """Test field group model instances are converted to dicts."""
        mock_product_type_config = MagicMock()
        mock_field_group = MagicMock(
            group_key="test_group",
            display_name="Test Group",
            fields=["field1", "field2"],
            is_active=True,
        )
        mock_product_type_config.field_groups.filter.return_value.order_by.return_value = [mock_field_group]

        result = self.calculator.load_field_groups(mock_product_type_config)

        self.assertIsInstance(result[0], dict)
        self.assertIn("group_key", result[0])
        self.assertIn("fields", result[0])
        self.assertIn("is_active", result[0])

    def test_load_field_groups_empty_returns_empty_list(self):
        """Test empty field groups returns empty list."""
        mock_product_type_config = MagicMock()
        mock_product_type_config.field_groups.filter.return_value.order_by.return_value = []

        result = self.calculator.load_field_groups(mock_product_type_config)

        self.assertEqual(result, [])


class FieldGroupLoadingByProductTypeTests(TestCase):
    """Tests for loading field groups by product type string."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    @patch('crawler.models.ProductTypeConfig')
    def test_load_field_groups_for_product_type_whiskey(self, mock_product_type_config_cls):
        """Test loading field groups for whiskey product type."""
        mock_config = MagicMock()
        mock_field_groups = [
            MagicMock(
                group_key="basic_product_info",
                display_name="Basic Product Info",
                fields=["name", "brand", "abv", "category"],
                is_active=True,
            ),
            MagicMock(
                group_key="whiskey_details",
                display_name="Whiskey Details",
                fields=["distillery", "mash_bill"],
                is_active=True,
            ),
        ]
        mock_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups
        mock_product_type_config_cls.objects.get.return_value = mock_config

        result = self.calculator.load_field_groups_for_product_type("whiskey")

        self.assertEqual(len(result), 2)
        mock_product_type_config_cls.objects.get.assert_called_with(product_type="whiskey")

    @patch('crawler.models.ProductTypeConfig')
    def test_load_field_groups_for_product_type_port_wine(self, mock_product_type_config_cls):
        """Test loading field groups for port wine product type."""
        mock_config = MagicMock()
        mock_field_groups = [
            MagicMock(
                group_key="basic_product_info",
                display_name="Basic Product Info",
                fields=["name", "brand", "style"],
                is_active=True,
            ),
            MagicMock(
                group_key="port_details",
                display_name="Port Wine Details",
                fields=["indication_age", "producer_house"],
                is_active=True,
            ),
        ]
        mock_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups
        mock_product_type_config_cls.objects.get.return_value = mock_config

        result = self.calculator.load_field_groups_for_product_type("port_wine")

        self.assertEqual(len(result), 2)
        mock_product_type_config_cls.objects.get.assert_called_with(product_type="port_wine")

    @patch('crawler.models.ProductTypeConfig')
    def test_load_field_groups_not_found_returns_empty(self, mock_product_type_config_cls):
        """Test loading field groups when product type not found."""
        mock_product_type_config_cls.objects.get.side_effect = mock_product_type_config_cls.DoesNotExist

        result = self.calculator.load_field_groups_for_product_type("unknown")

        self.assertEqual(result, [])


class FieldGroupCachingTests(TestCase):
    """Tests for field group caching behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    @patch('crawler.models.ProductTypeConfig')
    def test_field_groups_cached_after_first_load(self, mock_product_type_config_cls):
        """Test field groups are cached after first load."""
        mock_config = MagicMock()
        mock_field_groups = [
            MagicMock(
                group_key="test",
                display_name="Test",
                fields=["field1"],
                is_active=True,
            ),
        ]
        mock_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups
        mock_product_type_config_cls.objects.get.return_value = mock_config

        # Clear cache first
        self.calculator.clear_cache()

        # First call
        result1 = self.calculator.load_field_groups_for_product_type("whiskey")
        # Second call
        result2 = self.calculator.load_field_groups_for_product_type("whiskey")

        # Should only query once
        self.assertEqual(mock_product_type_config_cls.objects.get.call_count, 1)
        self.assertEqual(result1, result2)

    @patch('crawler.models.ProductTypeConfig')
    def test_different_product_types_cached_separately(self, mock_product_type_config_cls):
        """Test different product types are cached separately."""
        mock_whiskey_config = MagicMock()
        mock_whiskey_groups = [
            MagicMock(group_key="whiskey_group", display_name="Whiskey", fields=["f1"], is_active=True),
        ]
        mock_whiskey_config.field_groups.filter.return_value.order_by.return_value = mock_whiskey_groups

        mock_port_config = MagicMock()
        mock_port_groups = [
            MagicMock(group_key="port_group", display_name="Port", fields=["f2"], is_active=True),
        ]
        mock_port_config.field_groups.filter.return_value.order_by.return_value = mock_port_groups

        def get_config(product_type):
            if product_type == "whiskey":
                return mock_whiskey_config
            return mock_port_config

        mock_product_type_config_cls.objects.get.side_effect = get_config

        # Clear cache first
        self.calculator.clear_cache()

        result_whiskey = self.calculator.load_field_groups_for_product_type("whiskey")
        result_port = self.calculator.load_field_groups_for_product_type("port_wine")

        self.assertEqual(result_whiskey[0]["group_key"], "whiskey_group")
        self.assertEqual(result_port[0]["group_key"], "port_group")

    def test_clear_cache_resets_cached_groups(self):
        """Test clear_cache resets cached field groups."""
        # Set some cached data
        self.calculator._field_groups_cache = {"whiskey": [{"group_key": "cached"}]}

        self.calculator.clear_cache()

        self.assertEqual(self.calculator._field_groups_cache, {})


class FieldGroupActiveFilteringTests(TestCase):
    """Tests for filtering active field groups."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_only_active_groups_returned(self):
        """Test only active field groups are returned."""
        mock_product_type_config = MagicMock()
        # The filter call should filter to is_active=True
        mock_field_groups = [
            MagicMock(
                group_key="active_group",
                display_name="Active",
                fields=["field1"],
                is_active=True,
            ),
        ]
        mock_product_type_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups

        result = self.calculator.load_field_groups(mock_product_type_config)

        # Verify filter was called with is_active=True
        mock_product_type_config.field_groups.filter.assert_called_with(is_active=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["group_key"], "active_group")


class FieldGroupOrderingTests(TestCase):
    """Tests for field group ordering."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ECPCalculator()

    def test_groups_ordered_by_sort_order(self):
        """Test field groups are ordered by sort_order."""
        mock_product_type_config = MagicMock()
        mock_field_groups = [
            MagicMock(group_key="group1", display_name="G1", fields=["f1"], is_active=True, sort_order=1),
            MagicMock(group_key="group2", display_name="G2", fields=["f2"], is_active=True, sort_order=2),
        ]
        mock_product_type_config.field_groups.filter.return_value.order_by.return_value = mock_field_groups

        result = self.calculator.load_field_groups(mock_product_type_config)

        # Verify order_by was called with sort_order
        mock_product_type_config.field_groups.filter.return_value.order_by.assert_called_with("sort_order")
