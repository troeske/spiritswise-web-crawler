"""
Unit tests for product_saver module - MVP product type validation.

Task 1: Fix Silent Product Type Override
TDD Instruction: Write these tests BEFORE implementing the fix.

These tests verify that save_discovered_product() correctly:
1. Rejects invalid product types (wine, unknown, etc.)
2. Accepts valid MVP product types (whiskey, port_wine)
3. Returns appropriate error messages for rejected products
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


class TestProductTypeValidation:
    """Tests for product type validation in save_discovered_product()."""

    def test_rejects_invalid_product_type_wine(self):
        """
        Should reject products with product_type='wine'.

        Wine is not a valid MVP product type. The save operation should
        return created=False and include an error message indicating
        the product type is invalid.
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "Test Wine"},
            source_url="http://example.com",
            product_type="wine",
            discovery_source="competition",
        )

        assert result.created is False, "Product with invalid type 'wine' should not be created"
        assert result.error is not None, "Should have an error message"
        assert "invalid product type" in result.error.lower(), \
            f"Error message should mention invalid product type, got: {result.error}"
        assert result.product is None, "No product should be returned for invalid type"

    def test_rejects_invalid_product_type_unknown(self):
        """
        Should reject products with product_type='unknown'.

        Unknown is not a valid MVP product type. The save operation should
        return created=False and include an error message.
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "Unknown Product"},
            source_url="http://example.com",
            product_type="unknown",
            discovery_source="competition",
        )

        assert result.created is False, "Product with invalid type 'unknown' should not be created"
        assert result.error is not None, "Should have an error message"
        assert result.product is None, "No product should be returned for invalid type"

    def test_rejects_invalid_product_type_gin(self):
        """
        Should reject products with product_type='gin'.

        Gin is in ProductType enum but not valid for MVP (only whiskey and port_wine).
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "London Dry Gin"},
            source_url="http://example.com",
            product_type="gin",
            discovery_source="search",
        )

        assert result.created is False, "Product with type 'gin' should not be created (not MVP)"
        assert result.error is not None, "Should have an error message"
        assert result.product is None, "No product should be returned for invalid type"

    def test_rejects_invalid_product_type_empty_string(self):
        """
        Should reject products with product_type=''.

        Empty string is not a valid product type.
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "Empty Type Product"},
            source_url="http://example.com",
            product_type="",
            discovery_source="search",
        )

        assert result.created is False, "Product with empty type should not be created"
        assert result.error is not None, "Should have an error message"
        assert result.product is None, "No product should be returned for invalid type"

    @pytest.mark.django_db
    def test_accepts_whiskey_product_type(self):
        """
        Should accept whiskey products.

        Whiskey is a valid MVP product type. The save operation should
        succeed and create the product.
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "Glenfiddich 12 Year Old"},
            source_url="http://example.com/glenfiddich",
            product_type="whiskey",
            discovery_source="search",
        )

        assert result.created is True, "Whiskey product should be created successfully"
        assert result.error is None, "Should not have an error message for valid product type"
        assert result.product is not None, "Product should be returned"
        assert result.product.product_type == "whiskey"

    @pytest.mark.django_db
    def test_accepts_port_wine_product_type(self):
        """
        Should accept port wine products.

        Port wine is a valid MVP product type. The save operation should
        succeed and create the product.
        """
        from crawler.services.product_saver import save_discovered_product

        result = save_discovered_product(
            extracted_data={"name": "Taylor's Vintage Port 2015"},
            source_url="http://example.com/taylors",
            product_type="port_wine",
            discovery_source="search",
        )

        assert result.created is True, "Port wine product should be created successfully"
        assert result.error is None, "Should not have an error message for valid product type"
        assert result.product is not None, "Product should be returned"
        assert result.product.product_type == "port_wine"


class TestProductSaveResultError:
    """Tests for ProductSaveResult error field."""

    def test_product_save_result_has_error_field(self):
        """
        ProductSaveResult should have an optional error field.

        The error field is used to communicate validation failures
        and other save errors.
        """
        from crawler.services.product_saver import ProductSaveResult
        from unittest.mock import MagicMock

        # Create a result with error
        mock_product = MagicMock()
        result = ProductSaveResult(
            product=mock_product,
            created=False,
            error="Test error message"
        )

        assert hasattr(result, 'error'), "ProductSaveResult should have 'error' attribute"
        assert result.error == "Test error message"

    def test_product_save_result_error_defaults_to_none(self):
        """
        ProductSaveResult.error should default to None when not provided.
        """
        from crawler.services.product_saver import ProductSaveResult
        from unittest.mock import MagicMock

        mock_product = MagicMock()
        result = ProductSaveResult(
            product=mock_product,
            created=True,
        )

        assert result.error is None, "Error should default to None"


class TestMVPValidProductTypes:
    """Tests to verify MVP_VALID_PRODUCT_TYPES constant."""

    def test_mvp_valid_product_types_contains_whiskey(self):
        """MVP_VALID_PRODUCT_TYPES should contain 'whiskey'."""
        from crawler.services.product_saver import MVP_VALID_PRODUCT_TYPES

        assert "whiskey" in MVP_VALID_PRODUCT_TYPES, "whiskey should be in MVP valid types"

    def test_mvp_valid_product_types_contains_port_wine(self):
        """MVP_VALID_PRODUCT_TYPES should contain 'port_wine'."""
        from crawler.services.product_saver import MVP_VALID_PRODUCT_TYPES

        assert "port_wine" in MVP_VALID_PRODUCT_TYPES, "port_wine should be in MVP valid types"

    def test_mvp_valid_product_types_excludes_gin(self):
        """MVP_VALID_PRODUCT_TYPES should NOT contain 'gin'."""
        from crawler.services.product_saver import MVP_VALID_PRODUCT_TYPES

        assert "gin" not in MVP_VALID_PRODUCT_TYPES, "gin should NOT be in MVP valid types"

    def test_mvp_valid_product_types_excludes_wine(self):
        """MVP_VALID_PRODUCT_TYPES should NOT contain 'wine'."""
        from crawler.services.product_saver import MVP_VALID_PRODUCT_TYPES

        assert "wine" not in MVP_VALID_PRODUCT_TYPES, "wine should NOT be in MVP valid types"

    def test_mvp_valid_product_types_has_only_two_types(self):
        """MVP should only support exactly 2 product types for now."""
        from crawler.services.product_saver import MVP_VALID_PRODUCT_TYPES

        assert len(MVP_VALID_PRODUCT_TYPES) == 2, \
            f"MVP should have exactly 2 valid types, got {len(MVP_VALID_PRODUCT_TYPES)}"
