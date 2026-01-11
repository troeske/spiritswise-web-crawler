"""
Unit tests for SkeletonProductManager.

Task 2 from E2E_BUG_FIXES_TASKS.md:
- For MVP, only return 'whiskey' or 'port_wine' from type detection
- If product doesn't match whiskey or port wine keywords, return None (reject)
- Skip creating skeleton products for non-MVP types
"""

import pytest
import warnings
from unittest.mock import patch, MagicMock

from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager


class TestDetermineProductType:
    """Tests for _determine_product_type() method."""

    @pytest.fixture
    def manager(self):
        """Create a SkeletonProductManager instance, suppressing deprecation warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return SkeletonProductManager()

    def test_determine_type_returns_none_for_wine(self, manager):
        """Wine products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Winery Gurjaani 2024",
            "category": "General",
        })
        assert result is None

    def test_determine_type_returns_none_for_unknown(self, manager):
        """Unknown products should return None."""
        result = manager._determine_product_type({
            "product_name": "Random Company LLC",
            "category": "General",
        })
        assert result is None

    def test_determine_type_returns_none_for_brandy(self, manager):
        """Brandy products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Hennessy VS Cognac",
            "category": "Spirits",
        })
        assert result is None

    def test_determine_type_returns_none_for_gin(self, manager):
        """Gin products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Tanqueray London Dry Gin",
            "category": "Spirits",
        })
        assert result is None

    def test_determine_type_returns_none_for_vodka(self, manager):
        """Vodka products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Grey Goose Vodka",
            "category": "Spirits",
        })
        assert result is None

    def test_determine_type_returns_none_for_rum(self, manager):
        """Rum products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Bacardi Gold Rum",
            "category": "Spirits",
        })
        assert result is None

    def test_determine_type_returns_none_for_tequila(self, manager):
        """Tequila products should return None (not valid for MVP)."""
        result = manager._determine_product_type({
            "product_name": "Patron Silver Tequila",
            "category": "Spirits",
        })
        assert result is None

    def test_determine_type_returns_whiskey(self, manager):
        """Whiskey products should return 'whiskey'."""
        result = manager._determine_product_type({
            "product_name": "Glenfiddich 12 Year Single Malt",
            "category": "Scotch Whisky",
        })
        assert result == "whiskey"

    def test_determine_type_returns_whiskey_for_bourbon(self, manager):
        """Bourbon products should return 'whiskey'."""
        result = manager._determine_product_type({
            "product_name": "Maker's Mark Bourbon",
            "category": "Bourbon",
        })
        assert result == "whiskey"

    def test_determine_type_returns_port_wine(self, manager):
        """Port products should return 'port_wine'."""
        result = manager._determine_product_type({
            "product_name": "Taylor's 20 Year Tawny Port",
            "category": "Port",
        })
        assert result == "port_wine"

    def test_determine_type_returns_port_wine_for_lbv(self, manager):
        """Late Bottled Vintage Port should return 'port_wine'."""
        result = manager._determine_product_type({
            "product_name": "Graham's Late Bottled Vintage 2017",
            "category": "Port",
        })
        assert result == "port_wine"


class TestCreateSkeletonProduct:
    """Tests for create_skeleton_product() method."""

    @pytest.fixture
    def manager(self):
        """Create a SkeletonProductManager instance, suppressing deprecation warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return SkeletonProductManager()

    def test_create_skeleton_skips_non_mvp_types(self, manager):
        """Should not create skeleton for wine products - raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            manager.create_skeleton_product({
                "product_name": "Winery Gurjaani 2024",
                "category": "General",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Bronze",
            })
        assert "not supported for mvp" in str(exc_info.value).lower()

    def test_create_skeleton_skips_unknown_type(self, manager):
        """Should not create skeleton for unknown products - raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            manager.create_skeleton_product({
                "product_name": "Random Company LLC",
                "category": "General",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Bronze",
            })
        assert "not supported for mvp" in str(exc_info.value).lower()

    def test_create_skeleton_skips_brandy(self, manager):
        """Should not create skeleton for brandy products - raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            manager.create_skeleton_product({
                "product_name": "Hennessy VS Cognac",
                "category": "Spirits",
                "competition": "IWSC",
                "year": 2024,
                "medal": "Gold",
            })
        assert "not supported for mvp" in str(exc_info.value).lower()
