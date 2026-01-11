"""
Integration Tests for Discovery Orchestrator - AI Enhancement Service V2.

Task 7.4: Integration Test - Discovery Orchestrator Flow

These tests verify that the discovery orchestrator correctly handles
V2 AI service responses and integrates with completeness scoring.

Tests cover:
1. Award discovery extracts all V2 fields
2. Generic search extracts all V2 fields
3. Product update preserves existing data
4. Product creation with full V2 data
5. Completeness score reflects new V2 fields

Uses fixtures for mock AI service responses to test the integration
without making actual API calls.
"""

import pytest
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass


# ============================================================================
# Mock Data Classes
# ============================================================================


@dataclass
class MockExtractionResult:
    """Mock SmartCrawler extraction result."""
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    source_url: str = ""
    source_type: str = "retailer"
    name_match_score: float = 0.95
    needs_review: bool = False
    errors: Optional[List[str]] = None
    scrapingbee_calls: int = 1
    ai_calls: int = 1


@dataclass
class MockAIEnhanceResult:
    """Mock AI service enhancement result."""
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    status_code: int = 200
    source_url: str = ""
    error: Optional[str] = None


# ============================================================================
# Fixtures: Mock V2 AI Service Responses
# ============================================================================


@pytest.fixture
def mock_v2_whiskey_response_complete():
    """
    Complete V2 AI service response for whiskey with all fields.

    Includes:
    - Core fields (name, brand, type, abv, age)
    - Tasting notes with flavor arrays (nose_aromas, palate_flavors, finish_flavors)
    - Tasting evolution fields
    - Appearance fields
    - Ratings fields
    - Production fields
    - Description and category
    """
    return {
        "name": "Glenfarclas 21 Year Old",
        "brand": "Glenfarclas",
        "whiskey_type": "scotch_single_malt",
        "category": "Single Malt Scotch",
        "description": "A rich, sherried Highland single malt with exceptional depth. "
                      "This 21 year old expression showcases the distillery's signature "
                      "sherry cask maturation.",
        "abv": 43.0,
        "volume_ml": 700,
        "age_statement": 21,
        "region": "Speyside",
        "country": "Scotland",
        "distillery": "Glenfarclas",

        # Tasting notes with V2 flavor arrays
        "tasting_notes": {
            "nose": "Rich dried fruits, Christmas cake, sherry sweetness, hints of orange peel",
            "nose_aromas": ["dried fruit", "christmas cake", "sherry", "orange peel", "oak"],
            "palate": "Full-bodied with layers of dark chocolate, dried figs, and spicy oak",
            "palate_flavors": ["dark chocolate", "dried figs", "oak", "cinnamon", "nutmeg", "raisins"],
            "finish": "Long, warming finish with lingering sherry sweetness and gentle smoke",
            "finish_flavors": ["sherry", "smoke", "oak", "honey"]
        },

        # V2 Tasting evolution
        "tasting_evolution": {
            "initial_taste": "Rich sherry sweetness with immediate dried fruit notes",
            "mid_palate_evolution": "Develops complexity with oak spices and dark chocolate",
            "aroma_evolution": "Opens with sherry, becomes more complex with air",
            "finish_evolution": "Warming spice fades to gentle sweetness",
            "final_notes": "Lingering dried fruit and subtle smoke"
        },

        # V2 Additional tasting fields
        "secondary_aromas": ["vanilla", "toffee", "leather"],
        "mouthfeel": "full-rich",
        "finish_length": 9,
        "experience_level": "advanced",

        # V2 Appearance
        "appearance": {
            "color_description": "Deep mahogany with amber highlights",
            "color_intensity": 9,
            "clarity": "crystal_clear",
            "viscosity": "full_bodied"
        },

        # V2 Ratings
        "ratings": {
            "flavor_intensity": 8,
            "complexity": 9,
            "warmth": 7,
            "dryness": 4,
            "balance": 9,
            "overall_complexity": 9,
            "uniqueness": 7,
            "drinkability": 8
        },

        # V2 Production
        "production": {
            "distillery": "Glenfarclas",
            "cask_strength": False,
            "single_cask": False,
            "peated": False,
            "natural_color": True,
            "non_chill_filtered": True,
            "primary_cask": ["sherry", "oloroso"],
            "wood_type": ["european_oak"],
            "maturation_notes": "Aged exclusively in first-fill oloroso sherry casks"
        },

        # Other enrichment data
        "serving_recommendation": "neat or with a drop of water",
        "food_pairings": ["dark chocolate", "aged cheese", "christmas pudding"],
        "flavor_profile": ["sherry", "dried fruit", "oak", "chocolate"],

        # Awards
        "awards": [
            {"competition": "IWSC", "year": 2023, "medal": "Gold", "score": 96},
            {"competition": "WWA", "year": 2023, "medal": "Gold"}
        ]
    }


@pytest.fixture
def mock_v2_port_wine_response_complete():
    """
    Complete V2 AI service response for port wine with all fields.
    """
    return {
        "name": "Taylor's 30 Year Old Tawny Port",
        "brand": "Taylor's",
        "style": "tawny",
        "category": "Tawny Port",
        "description": "An exceptional 30 year old tawny port with remarkable complexity. "
                      "Extended cask aging has produced intense flavors of dried fruit and nuts.",
        "abv": 20.0,
        "volume_ml": 750,
        "region": "Douro Valley",
        "country": "Portugal",
        "average_age": 30,

        # Tasting notes with V2 flavor arrays
        "tasting_notes": {
            "nose": "Intense aromas of caramel, walnuts, and dried apricots",
            "nose_aromas": ["caramel", "walnuts", "dried apricots", "orange peel", "vanilla"],
            "palate": "Rich and velvety with flavors of figs, nuts, and toffee",
            "palate_flavors": ["figs", "walnuts", "toffee", "honey", "orange", "spice"],
            "finish": "Exceptionally long finish with lingering nutty sweetness",
            "finish_flavors": ["nuts", "toffee", "honey", "spice"]
        },

        # V2 Tasting evolution
        "tasting_evolution": {
            "initial_taste": "Immediate sweetness with toffee and dried fruit",
            "mid_palate_evolution": "Develops complex nutty notes and subtle spice",
            "aroma_evolution": "Opens with caramel, reveals dried fruit complexity",
            "finish_evolution": "Nutty sweetness persists, gently fading to warmth",
            "final_notes": "Lingering dried fruit and walnut notes"
        },

        # V2 Additional tasting fields
        "secondary_aromas": ["honey", "butterscotch", "almond"],
        "mouthfeel": "syrupy-coating",
        "finish_length": 10,
        "experience_level": "advanced",

        # V2 Appearance
        "appearance": {
            "color_description": "Deep amber with golden-brown rim",
            "color_intensity": 10,
            "clarity": "crystal_clear",
            "viscosity": "syrupy"
        },

        # V2 Ratings
        "ratings": {
            "flavor_intensity": 9,
            "complexity": 10,
            "warmth": 6,
            "dryness": 2,
            "balance": 10,
            "overall_complexity": 10,
            "uniqueness": 8,
            "drinkability": 9
        },

        # Port-specific fields
        "grape_varieties": ["Touriga Nacional", "Touriga Franca", "Tinta Roriz"],
        "quinta": "Quinta de Vargellas",
        "douro_subregion": "Cima Corgo",
        "decanting_required": False,
        "aging_vessel": "Traditional oak casks",

        # Awards
        "awards": [
            {"competition": "Decanter", "year": 2023, "medal": "Platinum", "score": 97}
        ]
    }


@pytest.fixture
def mock_v2_whiskey_response_minimal():
    """
    Minimal V2 response with only core fields.

    Used to test partial data handling.
    """
    return {
        "name": "Test Whisky",
        "brand": "Test Brand",
        "whiskey_type": "scotch_single_malt",
        "abv": 40.0,
        "tasting_notes": {
            "nose": "Simple fruity notes",
            "palate": "Light and approachable"
        }
    }


@pytest.fixture
def mock_existing_product_data():
    """
    Mock existing product data for update tests.

    Contains some fields already populated that should be preserved.
    """
    return {
        "name": "Existing Whisky 12 Year Old",
        "brand": "Test Distillery",
        "whiskey_type": "scotch_single_malt",
        "abv": 46.0,
        "age_statement": 12,
        "region": "Highland",
        "country": "Scotland",
        "nose_description": "Original nose description - should be preserved",
        "palate_description": "Original palate description",
        "primary_aromas": ["honey", "vanilla"],
        "source_url": "https://example.com/original-source",
        "source_count": 1,
        "completeness_score": 45
    }


@pytest.fixture
def mock_v2_update_data():
    """
    V2 data for updating an existing product.

    Contains new fields that should be added without overwriting existing data.
    """
    return {
        "name": "Existing Whisky 12 Year Old",
        "brand": "Test Distillery",
        # New V2 fields to add
        "tasting_notes": {
            "palate_flavors": ["butterscotch", "oak", "vanilla", "spice"],
            "finish_flavors": ["oak", "honey", "smoke"]
        },
        "tasting_evolution": {
            "initial_taste": "Sweet honey upfront",
            "mid_palate_evolution": "Develops into oak and spice"
        },
        "appearance": {
            "color_description": "Golden amber",
            "color_intensity": 7,
            "clarity": "crystal_clear"
        },
        "ratings": {
            "balance": 8,
            "complexity": 7,
            "drinkability": 9
        },
        "description": "A fine Highland single malt.",
        "category": "Single Malt Scotch"
    }


@pytest.fixture
def mock_award_discovery_response():
    """
    Mock response from award discovery flow (competition site).

    Includes award information along with V2 product data.
    """
    return {
        "name": "Award Winner Whisky 15 Year Old",
        "brand": "Championship Distillery",
        "whiskey_type": "scotch_single_malt",
        "category": "Single Malt Scotch",
        "description": "Gold medal winner at IWSC 2023.",
        "abv": 48.0,
        "age_statement": 15,
        "region": "Speyside",
        "country": "Scotland",

        # V2 tasting data
        "tasting_notes": {
            "nose": "Complex aromas of vanilla, toffee, and spice",
            "nose_aromas": ["vanilla", "toffee", "spice", "citrus"],
            "palate": "Rich and full with honey, oak, and dried fruit",
            "palate_flavors": ["honey", "oak", "dried fruit", "vanilla", "butterscotch"],
            "finish": "Long and warming",
            "finish_flavors": ["oak", "spice", "honey"]
        },

        # V2 additional fields
        "mouthfeel": "full-rich",
        "finish_length": 8,
        "appearance": {
            "color_description": "Rich gold",
            "color_intensity": 8
        },
        "ratings": {
            "complexity": 8,
            "balance": 9,
            "drinkability": 8
        },

        # Award data from competition
        "awards": [
            {
                "competition": "IWSC",
                "year": 2023,
                "medal": "Gold",
                "category": "Single Malt Scotch",
                "score": 95
            }
        ]
    }


@pytest.fixture
def mock_search_discovery_response():
    """
    Mock response from generic search discovery flow.

    Includes full V2 enrichment data.
    """
    return {
        "name": "Search Discovery Bourbon",
        "brand": "Kentucky Reserve",
        "whiskey_type": "bourbon",
        "category": "Kentucky Bourbon",
        "description": "A premium small batch bourbon with rich caramel notes.",
        "abv": 45.0,
        "age_statement": 8,
        "region": "Kentucky",
        "country": "USA",

        # V2 tasting data
        "tasting_notes": {
            "nose": "Caramel, vanilla, and toasted oak",
            "nose_aromas": ["caramel", "vanilla", "oak", "corn"],
            "palate": "Sweet and smooth with butterscotch and spice",
            "palate_flavors": ["butterscotch", "spice", "vanilla", "caramel", "oak"],
            "finish": "Medium-long with gentle warmth",
            "finish_flavors": ["oak", "vanilla", "caramel"]
        },

        "tasting_evolution": {
            "initial_taste": "Sweet caramel and vanilla",
            "mid_palate_evolution": "Spice develops with corn sweetness"
        },

        "secondary_aromas": ["leather", "tobacco"],
        "mouthfeel": "medium-balanced",
        "finish_length": 7,

        "appearance": {
            "color_description": "Amber with reddish hue",
            "color_intensity": 7
        },

        "ratings": {
            "flavor_intensity": 7,
            "complexity": 6,
            "warmth": 7,
            "balance": 8,
            "drinkability": 9
        },

        "production": {
            "cask_strength": False,
            "primary_cask": ["new american oak"],
            "cask_treatment": ["charred"]
        }
    }


# ============================================================================
# Helper Classes for Testing
# ============================================================================


class MockOrchestrator:
    """
    Mock DiscoveryOrchestrator for isolated integration testing.

    Provides access to the _normalize_data_for_save method and
    tracks method calls for verification.
    """

    def __init__(self):
        self._saved_products = []
        self._normalized_data_calls = []

    def _normalize_data_for_save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import and use the real normalization method.
        """
        from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

        orchestrator = DiscoveryOrchestrator.__new__(DiscoveryOrchestrator)
        result = orchestrator._normalize_data_for_save(data)
        self._normalized_data_calls.append({"input": data, "output": result})
        return result


class MockProduct:
    """
    Mock DiscoveredProduct for completeness scoring tests.

    Simulates the product model with attribute access.
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        return None


# ============================================================================
# Test Class: Award Discovery Flow
# ============================================================================


class TestAwardDiscoveryExtractsAllV2Fields:
    """
    Test that award discovery flow extracts all V2 fields.

    Award discovery involves:
    1. Crawling competition results pages (IWSC, SFWSC, etc.)
    2. Extracting award information and product data
    3. Enriching product with full V2 AI service data
    4. Saving with awards and all tasting profile fields
    """

    def test_award_discovery_extracts_all_v2_fields(
        self,
        mock_award_discovery_response
    ):
        """
        Verify award flow extracts all new V2 fields from AI response.
        """
        orchestrator = MockOrchestrator()

        # Normalize the award discovery response
        normalized = orchestrator._normalize_data_for_save(mock_award_discovery_response)

        # Verify core fields
        assert normalized["name"] == "Award Winner Whisky 15 Year Old"
        assert normalized.get("category") == "Single Malt Scotch"
        assert normalized.get("description") == "Gold medal winner at IWSC 2023."

        # Verify V2 tasting notes arrays (CRITICAL fields)
        assert "primary_aromas" in normalized
        assert normalized["primary_aromas"] == ["vanilla", "toffee", "spice", "citrus"]

        assert "palate_flavors" in normalized
        assert len(normalized["palate_flavors"]) >= 3
        assert "honey" in normalized["palate_flavors"]

        assert "finish_flavors" in normalized
        assert len(normalized["finish_flavors"]) >= 2

        # Verify V2 appearance fields
        assert normalized.get("color_description") == "Rich gold"
        assert normalized.get("color_intensity") == 8

        # Verify V2 ratings fields
        assert normalized.get("complexity") == 8
        assert normalized.get("balance") == 9
        assert normalized.get("drinkability") == 8

        # Verify other V2 fields
        assert normalized.get("mouthfeel") == "full-rich"
        assert normalized.get("finish_length") == 8

        # Verify awards are preserved
        assert "awards" in normalized
        assert len(normalized["awards"]) == 1
        assert normalized["awards"][0]["medal"] == "Gold"
        assert normalized["awards"][0]["score"] == 95

    def test_award_discovery_maps_tasting_descriptions(
        self,
        mock_award_discovery_response
    ):
        """
        Verify award flow maps tasting descriptions correctly.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_award_discovery_response)

        # Check tasting descriptions are mapped
        assert normalized.get("nose_description") == "Complex aromas of vanilla, toffee, and spice"
        assert normalized.get("palate_description") == "Rich and full with honey, oak, and dried fruit"
        assert normalized.get("finish_description") == "Long and warming"

    def test_award_discovery_with_port_wine(
        self,
        mock_v2_port_wine_response_complete
    ):
        """
        Verify award flow works with port wine V2 response.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_port_wine_response_complete)

        # Verify port wine specific V2 fields
        assert normalized.get("category") == "Tawny Port"
        assert normalized.get("primary_aromas") == ["caramel", "walnuts", "dried apricots", "orange peel", "vanilla"]
        assert len(normalized.get("palate_flavors", [])) >= 3

        # Verify appearance
        assert normalized.get("color_description") == "Deep amber with golden-brown rim"
        assert normalized.get("color_intensity") == 10

        # Verify ratings
        assert normalized.get("complexity") == 10
        assert normalized.get("balance") == 10


# ============================================================================
# Test Class: Generic Search Discovery Flow
# ============================================================================


class TestGenericSearchExtractsAllV2Fields:
    """
    Test that generic search discovery flow extracts all V2 fields.

    Generic search discovery involves:
    1. SerpAPI search for product mentions
    2. Crawling identified product pages
    3. AI service extraction with V2 response
    4. Saving with full tasting profile and enrichment
    """

    def test_generic_search_extracts_all_v2_fields(
        self,
        mock_search_discovery_response
    ):
        """
        Verify search flow extracts all new V2 fields from AI response.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_search_discovery_response)

        # Verify core fields
        assert normalized["name"] == "Search Discovery Bourbon"
        assert normalized.get("category") == "Kentucky Bourbon"
        assert normalized.get("description") == "A premium small batch bourbon with rich caramel notes."

        # Verify V2 tasting notes arrays (CRITICAL)
        assert "primary_aromas" in normalized
        assert "caramel" in normalized["primary_aromas"]

        assert "palate_flavors" in normalized
        assert len(normalized["palate_flavors"]) >= 3

        assert "finish_flavors" in normalized
        assert len(normalized["finish_flavors"]) >= 2

        # Verify V2 tasting evolution
        assert normalized.get("initial_taste") == "Sweet caramel and vanilla"
        assert "Spice develops" in normalized.get("mid_palate_evolution", "")

        # Verify V2 appearance
        assert normalized.get("color_description") == "Amber with reddish hue"
        assert normalized.get("color_intensity") == 7

        # Verify V2 ratings
        assert normalized.get("flavor_intensity") == 7
        assert normalized.get("complexity") == 6
        assert normalized.get("warmth") == 7
        assert normalized.get("balance") == 8
        assert normalized.get("drinkability") == 9

        # Verify V2 additional fields
        assert normalized.get("secondary_aromas") == ["leather", "tobacco"]
        assert normalized.get("mouthfeel") == "medium-balanced"
        assert normalized.get("finish_length") == 7

    def test_generic_search_maps_production_fields(
        self,
        mock_search_discovery_response
    ):
        """
        Verify search flow maps production fields from V2 response.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_search_discovery_response)

        # Verify production fields are mapped
        assert normalized.get("primary_cask") == ["new american oak"]
        assert normalized.get("cask_treatment") == ["charred"]

    def test_generic_search_with_complete_v2_data(
        self,
        mock_v2_whiskey_response_complete
    ):
        """
        Verify search flow handles complete V2 response with all fields.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_whiskey_response_complete)

        # Verify all major V2 field categories are mapped

        # Core V2 fields
        assert normalized.get("category") == "Single Malt Scotch"
        assert "rich, sherried Highland" in normalized.get("description", "")

        # Tasting arrays
        assert len(normalized.get("primary_aromas", [])) >= 4
        assert len(normalized.get("palate_flavors", [])) >= 5
        assert len(normalized.get("finish_flavors", [])) >= 3

        # Evolution fields
        assert normalized.get("initial_taste") is not None
        assert normalized.get("mid_palate_evolution") is not None
        assert normalized.get("aroma_evolution") is not None
        assert normalized.get("finish_evolution") is not None
        assert normalized.get("final_notes") is not None

        # Appearance
        assert normalized.get("color_description") is not None
        assert normalized.get("color_intensity") == 9
        assert normalized.get("clarity") == "crystal_clear"
        assert normalized.get("viscosity") == "full_bodied"

        # Ratings
        assert normalized.get("flavor_intensity") == 8
        assert normalized.get("complexity") == 9
        assert normalized.get("warmth") == 7
        assert normalized.get("dryness") == 4
        assert normalized.get("balance") == 9
        assert normalized.get("overall_complexity") == 9
        assert normalized.get("uniqueness") == 7
        assert normalized.get("drinkability") == 8

        # Production
        assert normalized.get("natural_color") is True
        assert normalized.get("non_chill_filtered") is True
        assert normalized.get("primary_cask") == ["sherry", "oloroso"]


# ============================================================================
# Test Class: Product Update Preserves Existing Data
# ============================================================================


class TestProductUpdatePreservesExistingData:
    """
    Test that product updates don't lose existing data.

    When updating a product with new V2 data, existing fields that
    are not in the new data should be preserved.
    """

    def test_product_update_preserves_existing_data(
        self,
        mock_existing_product_data,
        mock_v2_update_data
    ):
        """
        Verify updates don't overwrite existing fields when new data is empty.
        """
        orchestrator = MockOrchestrator()

        # First normalize the update data
        normalized_update = orchestrator._normalize_data_for_save(mock_v2_update_data)

        # Simulate merging with existing data (like _merge_product_data does)
        # The update should ADD new fields without removing existing ones
        merged = {**mock_existing_product_data}
        for key, value in normalized_update.items():
            if value is not None and (key not in merged or merged[key] is None):
                merged[key] = value
            elif isinstance(value, list) and value and key not in merged:
                merged[key] = value

        # Verify existing data is preserved
        assert merged["nose_description"] == "Original nose description - should be preserved"
        assert merged["palate_description"] == "Original palate description"
        assert merged["primary_aromas"] == ["honey", "vanilla"]  # Original values

        # Verify new V2 fields are added
        assert "palate_flavors" in merged
        assert len(merged["palate_flavors"]) >= 3
        assert "finish_flavors" in merged

        # Verify new V2 tasting evolution is added
        assert merged.get("initial_taste") == "Sweet honey upfront"
        assert "oak and spice" in merged.get("mid_palate_evolution", "")

        # Verify new V2 appearance is added
        assert merged.get("color_description") == "Golden amber"
        assert merged.get("color_intensity") == 7
        assert merged.get("clarity") == "crystal_clear"

        # Verify new V2 ratings are added
        assert merged.get("balance") == 8
        assert merged.get("complexity") == 7
        assert merged.get("drinkability") == 9

        # Verify new description and category are added
        assert merged.get("description") == "A fine Highland single malt."
        assert merged.get("category") == "Single Malt Scotch"

    def test_product_update_does_not_overwrite_populated_fields(self):
        """
        Verify that populated fields are not overwritten by new data.
        """
        orchestrator = MockOrchestrator()

        # Existing data with populated nose_description
        existing = {
            "name": "Test Whisky",
            "nose_description": "Original nose - DO NOT OVERWRITE"
        }

        # New data also has nose_description
        new_data = {
            "name": "Test Whisky",
            "tasting_notes": {
                "nose": "New nose description that should not replace existing"
            }
        }

        normalized = orchestrator._normalize_data_for_save(new_data)

        # Simulate update logic - existing populated fields should be preserved
        # The normalization puts the value in, but merge logic should skip
        assert normalized.get("nose_description") == "New nose description that should not replace existing"

        # When merging, existing populated values should be kept
        merged = {**existing}
        for key, value in normalized.items():
            if key not in merged or merged[key] is None:
                merged[key] = value

        # Existing nose_description is preserved
        assert merged["nose_description"] == "Original nose - DO NOT OVERWRITE"

    def test_product_update_adds_missing_v2_fields(self):
        """
        Verify that missing V2 fields are added during update.
        """
        orchestrator = MockOrchestrator()

        # Existing product without V2 fields
        existing = {
            "name": "Legacy Product",
            "brand": "Old Brand",
            "abv": 40.0,
            "nose_description": "Original nose"
        }

        # New V2 data
        new_data = {
            "name": "Legacy Product",
            "appearance": {
                "color_description": "Amber",
                "color_intensity": 6
            },
            "ratings": {
                "balance": 7,
                "drinkability": 8
            },
            "category": "Blended Scotch",
            "description": "A smooth blend."
        }

        normalized = orchestrator._normalize_data_for_save(new_data)

        # Merge
        merged = {**existing}
        for key, value in normalized.items():
            if value is not None and (key not in merged or merged[key] is None):
                merged[key] = value

        # Original fields preserved
        assert merged["nose_description"] == "Original nose"
        assert merged["abv"] == 40.0

        # New V2 fields added
        assert merged.get("color_description") == "Amber"
        assert merged.get("color_intensity") == 6
        assert merged.get("balance") == 7
        assert merged.get("drinkability") == 8
        assert merged.get("category") == "Blended Scotch"
        assert merged.get("description") == "A smooth blend."


# ============================================================================
# Test Class: Product Creation with Full V2 Data
# ============================================================================


class TestProductCreationWithFullV2Data:
    """
    Test that new products get all V2 fields populated correctly.

    When creating a new product from a V2 AI response, all fields
    should be mapped correctly to the product model.
    """

    def test_product_creation_with_full_v2_data(
        self,
        mock_v2_whiskey_response_complete
    ):
        """
        Verify new products get all V2 fields populated.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_whiskey_response_complete)

        # Verify all fields are present for product creation

        # Core identification
        assert normalized["name"] == "Glenfarclas 21 Year Old"
        assert normalized.get("brand") == "Glenfarclas"
        assert normalized.get("whiskey_type") == "scotch_single_malt"

        # V2 Critical fields
        assert normalized.get("category") == "Single Malt Scotch"
        assert normalized.get("description") is not None

        # V2 Tasting arrays (CRITICAL)
        assert len(normalized.get("primary_aromas", [])) >= 2
        assert len(normalized.get("palate_flavors", [])) >= 3
        assert len(normalized.get("finish_flavors", [])) >= 2

        # V2 Tasting descriptions
        assert normalized.get("nose_description") is not None
        assert normalized.get("palate_description") is not None
        assert normalized.get("finish_description") is not None

        # V2 Evolution fields
        assert normalized.get("initial_taste") is not None
        assert normalized.get("mid_palate_evolution") is not None
        assert normalized.get("aroma_evolution") is not None
        assert normalized.get("finish_evolution") is not None
        assert normalized.get("final_notes") is not None

        # V2 Additional tasting
        assert normalized.get("secondary_aromas") is not None
        assert normalized.get("mouthfeel") is not None
        assert normalized.get("finish_length") is not None
        assert normalized.get("experience_level") is not None

        # V2 Appearance
        assert normalized.get("color_description") is not None
        assert normalized.get("color_intensity") is not None
        assert normalized.get("clarity") is not None
        assert normalized.get("viscosity") is not None

        # V2 Ratings
        rating_fields = [
            "flavor_intensity", "complexity", "warmth", "dryness",
            "balance", "overall_complexity", "uniqueness", "drinkability"
        ]
        for field in rating_fields:
            assert normalized.get(field) is not None, f"Missing rating field: {field}"

        # V2 Production
        assert normalized.get("natural_color") is not None
        assert normalized.get("non_chill_filtered") is not None
        assert normalized.get("primary_cask") is not None
        assert normalized.get("wood_type") is not None

    def test_product_creation_with_port_wine_v2_data(
        self,
        mock_v2_port_wine_response_complete
    ):
        """
        Verify port wine products get all V2 fields populated.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_port_wine_response_complete)

        # Core identification
        assert normalized["name"] == "Taylor's 30 Year Old Tawny Port"
        assert normalized.get("style") == "tawny"

        # V2 Critical fields
        assert normalized.get("category") == "Tawny Port"
        assert normalized.get("description") is not None

        # V2 Tasting arrays
        assert len(normalized.get("primary_aromas", [])) >= 2
        assert len(normalized.get("palate_flavors", [])) >= 3
        assert len(normalized.get("finish_flavors", [])) >= 2

        # V2 Evolution fields
        assert normalized.get("initial_taste") is not None
        assert normalized.get("mid_palate_evolution") is not None

        # V2 Appearance
        assert normalized.get("color_description") is not None
        assert normalized.get("color_intensity") == 10

        # V2 Ratings
        assert normalized.get("complexity") == 10
        assert normalized.get("balance") == 10

        # Port-specific fields preserved
        assert normalized.get("grape_varieties") is not None
        assert normalized.get("quinta") is not None

    def test_product_creation_with_minimal_v2_data(
        self,
        mock_v2_whiskey_response_minimal
    ):
        """
        Verify products can be created with minimal V2 data without errors.
        """
        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_whiskey_response_minimal)

        # Core fields should be present
        assert normalized["name"] == "Test Whisky"
        assert normalized.get("brand") == "Test Brand"
        assert normalized.get("whiskey_type") == "scotch_single_malt"
        assert normalized.get("abv") == 40.0

        # Tasting descriptions should be mapped
        assert normalized.get("nose_description") == "Simple fruity notes"
        assert normalized.get("palate_description") == "Light and approachable"

        # V2 fields may be missing but should not cause errors
        # Arrays may be empty or None
        assert "primary_aromas" not in normalized or normalized.get("primary_aromas") is None


# ============================================================================
# Test Class: Completeness Score Reflects New Fields
# ============================================================================


class TestCompletenessScoreReflectsNewFields:
    """
    Test that completeness scoring includes new V2 fields.

    The completeness score should:
    1. Include points for palate_flavors (3+ items)
    2. Include points for primary_aromas (2+ items)
    3. Include points for finish_flavors (2+ items)
    4. Include points for description
    5. Include points for category
    6. Include points for appearance fields
    7. Include points for ratings fields
    """

    def test_completeness_score_reflects_new_fields(
        self,
        mock_v2_whiskey_response_complete
    ):
        """
        Verify scoring includes new V2 fields.
        """
        from crawler.services.completeness import (
            calculate_completeness_score,
            calculate_tasting_profile_score,
            calculate_palate_score,
            calculate_nose_score,
            calculate_finish_score,
            calculate_appearance_score,
            calculate_ratings_score,
        )

        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_whiskey_response_complete)

        # Create a mock product with the normalized data
        product = MockProduct(**normalized)

        # Test individual scoring functions

        # Palate score (max 20)
        palate_score = calculate_palate_score(product)
        assert palate_score >= 10, "palate_flavors with 3+ items should give 10+ points"

        # Nose score (max 10)
        nose_score = calculate_nose_score(product)
        assert nose_score >= 5, "primary_aromas with 2+ items should give 5+ points"

        # Finish score (max 10)
        finish_score = calculate_finish_score(product)
        assert finish_score >= 5, "finish_flavors with 2+ items should give 5+ points"

        # Tasting profile total (max 40)
        tasting_score = calculate_tasting_profile_score(product)
        assert tasting_score >= 20, "Complete tasting profile should score 20+"

        # Appearance score (max 3)
        appearance_score = calculate_appearance_score(product)
        assert appearance_score == 3, "Populated appearance fields should give 3 points"

        # Ratings score (max 5)
        ratings_score = calculate_ratings_score(product)
        assert ratings_score == 5, "Populated ratings fields should give 5 points"

        # Total completeness score
        total_score = calculate_completeness_score(product)
        assert total_score >= 60, "Complete V2 product should score 60+"

    def test_completeness_requires_palate_flavors_for_high_score(self):
        """
        Verify that palate_flavors is weighted appropriately.
        """
        from crawler.services.completeness import (
            calculate_palate_score,
            calculate_completeness_score,
        )

        # Product without palate_flavors
        product_without = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            palate_description="Good palate",
            # palate_flavors is missing
        )

        palate_score_without = calculate_palate_score(product_without)

        # Product with palate_flavors
        product_with = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            palate_description="Good palate",
            palate_flavors=["vanilla", "oak", "honey", "spice"]
        )

        palate_score_with = calculate_palate_score(product_with)

        # Should be a significant difference
        assert palate_score_with > palate_score_without
        assert palate_score_with >= 10, "3+ palate_flavors should give 10 points"

    def test_completeness_includes_v2_appearance_points(self):
        """
        Verify appearance fields contribute to score.
        """
        from crawler.services.completeness import calculate_appearance_score

        # Product with appearance
        product_with = MockProduct(
            color_description="Golden amber",
            color_intensity=7,
            clarity="crystal_clear"
        )

        score_with = calculate_appearance_score(product_with)
        assert score_with == 3, "Any appearance field should give 3 points"

        # Product without appearance
        product_without = MockProduct(name="Test")

        score_without = calculate_appearance_score(product_without)
        assert score_without == 0, "No appearance fields should give 0 points"

    def test_completeness_includes_v2_ratings_points(self):
        """
        Verify ratings fields contribute to score.
        """
        from crawler.services.completeness import calculate_ratings_score

        # Product with ratings
        product_with = MockProduct(
            flavor_intensity=7,
            complexity=8,
            balance=9
        )

        score_with = calculate_ratings_score(product_with)
        assert score_with == 5, "Any rating field should give 5 points"

        # Product without ratings
        product_without = MockProduct(name="Test")

        score_without = calculate_ratings_score(product_without)
        assert score_without == 0, "No rating fields should give 0 points"

    def test_completeness_score_with_all_v2_fields_high(
        self,
        mock_v2_whiskey_response_complete
    ):
        """
        Verify that a product with all V2 fields achieves a high score.
        """
        from crawler.services.completeness import (
            calculate_completeness_score,
            determine_status,
            has_palate_data,
        )

        orchestrator = MockOrchestrator()
        normalized = orchestrator._normalize_data_for_save(mock_v2_whiskey_response_complete)

        # Add fields needed for complete status
        normalized["brand_id"] = 1
        normalized["product_type"] = "whiskey"
        normalized["source_count"] = 2  # For verified status

        product = MockProduct(**normalized)

        # Should have palate data
        assert has_palate_data(product) is True

        # Calculate score
        score = calculate_completeness_score(product)

        # With all V2 fields, score should be high
        # Breakdown:
        # - Identification: 15 (name 10, brand 5)
        # - Basic info: 13 (type 5, ABV 5, category 3)
        # - Description: 5
        # - Tasting: 40 (palate 20, nose 10, finish 10)
        # - Appearance: 3
        # - Ratings: 5
        # - Enrichment: 4+ (awards 2, images 2)
        # - Verification: 10 (source_count >= 2)

        assert score >= 70, f"Complete V2 product should score 70+, got {score}"

        # Set the score for status determination
        product.completeness_score = score

        # Status should be complete or verified
        status = determine_status(product)
        assert status in ["complete", "verified"], f"Expected complete/verified, got {status}"

    def test_completeness_requires_palate_for_complete_status(self):
        """
        Verify that COMPLETE/VERIFIED status requires palate data.
        """
        from crawler.services.completeness import (
            calculate_completeness_score,
            determine_status,
            has_palate_data,
        )

        # Product with high score but no palate
        product = MockProduct(
            name="Test Whisky",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            category="Single Malt Scotch",
            description="A fine whisky.",
            nose_description="Honey and vanilla",
            primary_aromas=["honey", "vanilla", "oak"],
            finish_description="Long finish",
            finish_flavors=["oak", "spice", "honey"],
            color_description="Golden",
            color_intensity=7,
            flavor_intensity=7,
            complexity=8,
            balance=8,
            best_price=50.0,
            source_count=2
            # Missing: palate_flavors, palate_description, initial_taste
        )

        # Should NOT have palate data
        assert has_palate_data(product) is False

        # Calculate score
        score = calculate_completeness_score(product)
        product.completeness_score = score

        # Even with high score, status should be partial due to missing palate
        status = determine_status(product)
        assert status == "partial", f"Expected partial without palate, got {status}"
