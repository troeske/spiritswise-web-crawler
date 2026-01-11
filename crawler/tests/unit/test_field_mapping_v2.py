"""
Unit tests for crawler field mapping - AI Enhancement Service V2.

Task 6.8: Unit Tests - Crawler Field Mapping

These tests verify that the normalize_extracted_data() function in product_saver.py
correctly maps AI service response fields to the DiscoveredProduct model fields.

Updated 2026-01-11: Migrated from V1 to V2 architecture.
Uses normalize_extracted_data from product_saver instead of V1's _normalize_data_for_save.
"""

import pytest
from typing import Dict, Any

from crawler.services.product_saver import normalize_extracted_data


@pytest.fixture
def mock_ai_response_with_tasting_notes():
    """
    Mock AI service response with complete tasting_notes structure.

    This represents the V2 AI service response format with:
    - nose_aromas array (maps to primary_aromas)
    - palate_flavors array
    - finish_flavors array
    """
    return {
        "name": "Test Whiskey 12 Year Old",
        "brand": "Test Distillery",
        "whiskey_type": "scotch_single_malt",
        "abv": 46.0,
        "age_statement": 12,
        "region": "Highland",
        "country": "Scotland",
        "tasting_notes": {
            "nose": "Rich honey and vanilla with floral notes",
            "nose_aromas": ["honey", "vanilla", "floral", "citrus"],
            "palate": "Smooth with butterscotch and oak flavors",
            "palate_flavors": ["butterscotch", "oak", "vanilla", "spice", "dried fruit"],
            "finish": "Long and warming with lingering oak",
            "finish_flavors": ["oak", "spice", "honey"]
        }
    }


@pytest.fixture
def mock_ai_response_with_appearance():
    """
    Mock AI service response with appearance object.

    V2 format with nested appearance fields:
    - color_description
    - color_intensity
    - clarity
    - viscosity
    """
    return {
        "name": "Test Port Wine Vintage 2020",
        "brand": "Test Producer",
        "product_type": "port_wine",
        "appearance": {
            "color_description": "Deep ruby red with purple rim",
            "color_intensity": 8,
            "clarity": "crystal_clear",
            "viscosity": "full_bodied"
        }
    }


@pytest.fixture
def mock_ai_response_with_ratings():
    """
    Mock AI service response with ratings object.

    V2 format with nested ratings fields:
    - flavor_intensity
    - complexity
    - warmth
    - dryness
    - balance
    - overall_complexity
    - uniqueness
    - drinkability
    """
    return {
        "name": "Test Bourbon Premium",
        "brand": "Kentucky Distillery",
        "whiskey_type": "bourbon",
        "ratings": {
            "flavor_intensity": 8,
            "complexity": 7,
            "warmth": 6,
            "dryness": 4,
            "balance": 8,
            "overall_complexity": 7,
            "uniqueness": 5,
            "drinkability": 9
        },
        "experience_level": "intermediate"
    }


@pytest.fixture
def mock_ai_response_with_production():
    """
    Mock AI service response with production object.

    V2 format with nested production fields:
    - peat_ppm
    - natural_color
    - non_chill_filtered
    - primary_cask (array)
    - wood_type (array)
    - cask_treatment (array)
    - maturation_notes
    """
    return {
        "name": "Test Islay Single Malt",
        "brand": "Islay Distillery",
        "whiskey_type": "scotch_single_malt",
        "region": "Islay",
        "production": {
            "distillery": "Islay Distillery",
            "peat_ppm": 55,
            "natural_color": True,
            "non_chill_filtered": True,
            "primary_cask": ["ex-bourbon", "sherry"],
            "finishing_cask": ["port"],
            "wood_type": ["american_oak", "european_oak"],
            "cask_treatment": ["charred", "toasted"],
            "maturation_notes": "Aged 12 years in ex-bourbon casks with 2 year port finish"
        }
    }


@pytest.fixture
def mock_ai_response_with_tasting_evolution():
    """
    Mock AI service response with tasting_evolution object.

    V2 format with nested evolution fields:
    - initial_taste
    - mid_palate_evolution
    - aroma_evolution
    - finish_evolution
    - final_notes
    """
    return {
        "name": "Test Complex Whisky",
        "brand": "Highland Estate",
        "tasting_evolution": {
            "initial_taste": "Sweet honey and vanilla upfront",
            "mid_palate_evolution": "Develops into oak spice with hints of dark chocolate",
            "aroma_evolution": "Opens with fruit, becomes more complex with time in the glass",
            "finish_evolution": "Starts warm and spicy, fades to gentle sweetness",
            "final_notes": "Lingering warmth with hints of vanilla and oak tannins"
        },
        "secondary_aromas": ["citrus", "floral", "heather"],
        "mouthfeel": "smooth-creamy",
        "finish_length": 8
    }


@pytest.fixture
def mock_ai_response_complete():
    """
    Complete mock AI service V2 response with all fields.

    This represents a fully populated AI service response
    including all nested objects.
    """
    return {
        "name": "Glencadam 10 Year Old",
        "brand": "Glencadam",
        "whiskey_type": "scotch_single_malt",
        "category": "Single Malt Scotch",
        "description": "A superb Highland single malt with notes of honey and green apple.",
        "abv": 46.0,
        "volume_ml": 700,
        "age_statement": 10,
        "region": "Highland",
        "country": "Scotland",
        "appearance": {
            "color_description": "Deep amber with golden highlights",
            "color_intensity": 7,
            "clarity": "crystal_clear",
            "viscosity": "medium"
        },
        "tasting_notes": {
            "nose": "Fresh and floral with notes of honey and green apple",
            "nose_aromas": ["honey", "green apple", "vanilla", "floral"],
            "palate": "Smooth and creamy with flavors of butterscotch and citrus",
            "palate_flavors": ["butterscotch", "oak", "citrus", "vanilla"],
            "finish": "Medium-long with lingering honey and oak",
            "finish_flavors": ["honey", "spice", "oak"]
        },
        "tasting_evolution": {
            "initial_taste": "Sweet honey and vanilla",
            "mid_palate_evolution": "Develops oak and spice notes",
            "aroma_evolution": "Opens with fruit, becomes more complex",
            "finish_evolution": "Starts warm, fades to sweet",
            "final_notes": "Lingering warmth with vanilla"
        },
        "secondary_aromas": ["citrus", "floral"],
        "mouthfeel": "smooth-creamy",
        "finish_length": 7,
        "ratings": {
            "flavor_intensity": 7,
            "complexity": 8,
            "warmth": 5,
            "dryness": 4,
            "balance": 8,
            "overall_complexity": 7,
            "uniqueness": 6,
            "drinkability": 9
        },
        "experience_level": "intermediate",
        "serving_recommendation": "neat",
        "food_pairings": ["dark chocolate", "aged cheese", "smoked salmon"],
        "flavor_profile": ["honey", "vanilla", "oak", "butterscotch"],
        "production": {
            "distillery": "Glencadam",
            "cask_strength": False,
            "single_cask": False,
            "peated": False,
            "primary_cask": ["ex-bourbon"],
            "wood_type": ["american_oak"],
            "natural_color": True,
            "non_chill_filtered": True
        },
        "awards": [
            {"competition": "IWSC", "year": 2023, "medal": "Gold", "score": 95}
        ]
    }


class TestNoseAromasMapping:
    """Tests for tasting_notes.nose_aromas -> primary_aromas mapping."""

    def test_maps_nose_aromas_to_primary_aromas(self, mock_ai_response_with_tasting_notes):
        """
        Verify that tasting_notes.nose_aromas is correctly mapped to primary_aromas.

        The AI service returns nose_aromas as an array inside tasting_notes,
        which should be mapped to the primary_aromas field on DiscoveredProduct.
        """
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        # primary_aromas should contain the nose_aromas values
        assert "primary_aromas" in result, "primary_aromas field should be present"
        assert result["primary_aromas"] == ["honey", "vanilla", "floral", "citrus"]
        assert isinstance(result["primary_aromas"], list)
        assert len(result["primary_aromas"]) >= 2, "Should have at least 2 aroma items"

    def test_nose_aromas_preserves_array_order(self):
        """Verify that the order of nose_aromas is preserved in primary_aromas."""
        data = {
            "name": "Test",
            "tasting_notes": {
                "nose_aromas": ["apple", "pear", "honey", "oak"]
            }
        }
        result = normalize_extracted_data(data)

        assert result.get("primary_aromas") == ["apple", "pear", "honey", "oak"]

    def test_nose_description_still_maps_correctly(self, mock_ai_response_with_tasting_notes):
        """Verify nose description still maps to nose_description field."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        assert "nose_description" in result
        assert result["nose_description"] == "Rich honey and vanilla with floral notes"


class TestPalateFlavorsMapping:
    """Tests for tasting_notes.palate_flavors mapping."""

    def test_maps_palate_flavors_correctly(self, mock_ai_response_with_tasting_notes):
        """
        Verify that tasting_notes.palate_flavors is correctly mapped.

        The AI service returns palate_flavors as an array inside tasting_notes,
        which should be mapped to the palate_flavors field on DiscoveredProduct.
        """
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        assert "palate_flavors" in result, "palate_flavors field should be present"
        assert result["palate_flavors"] == ["butterscotch", "oak", "vanilla", "spice", "dried fruit"]
        assert isinstance(result["palate_flavors"], list)
        assert len(result["palate_flavors"]) >= 3, "Should have at least 3 flavor items (CRITICAL)"

    def test_palate_description_maps_correctly(self, mock_ai_response_with_tasting_notes):
        """Verify palate description maps to palate_description field."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        assert "palate_description" in result
        assert result["palate_description"] == "Smooth with butterscotch and oak flavors"

    def test_finish_flavors_maps_correctly(self, mock_ai_response_with_tasting_notes):
        """Verify finish_flavors array is mapped correctly."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        assert "finish_flavors" in result, "finish_flavors field should be present"
        assert result["finish_flavors"] == ["oak", "spice", "honey"]
        assert len(result["finish_flavors"]) >= 2, "Should have at least 2 finish flavors"

    def test_finish_description_maps_correctly(self, mock_ai_response_with_tasting_notes):
        """Verify finish description maps to finish_description field."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_notes)

        assert "finish_description" in result
        assert result["finish_description"] == "Long and warming with lingering oak"


class TestNestedAppearanceFields:
    """Tests for appearance.* field mapping."""

    def test_maps_nested_appearance_fields(self, mock_ai_response_with_appearance):
        """
        Verify that all appearance.* fields are correctly mapped.

        The AI service returns appearance as a nested object with:
        - color_description -> color_description
        - color_intensity -> color_intensity
        - clarity -> clarity
        - viscosity -> viscosity
        """
        result = normalize_extracted_data(mock_ai_response_with_appearance)

        # All appearance fields should be flattened to top level
        assert "color_description" in result
        assert result["color_description"] == "Deep ruby red with purple rim"

        assert "color_intensity" in result
        assert result["color_intensity"] == 8
        assert isinstance(result["color_intensity"], int)

        assert "clarity" in result
        assert result["clarity"] == "crystal_clear"

        assert "viscosity" in result
        assert result["viscosity"] == "full_bodied"

    def test_appearance_color_intensity_range(self):
        """Verify color_intensity is mapped even at boundary values (1-10)."""
        data = {
            "name": "Test",
            "appearance": {
                "color_intensity": 1  # Minimum value
            }
        }
        result = normalize_extracted_data(data)
        assert result.get("color_intensity") == 1

        data["appearance"]["color_intensity"] = 10  # Maximum value
        result = normalize_extracted_data(data)
        assert result.get("color_intensity") == 10

    def test_appearance_partial_fields(self):
        """Verify partial appearance objects are handled correctly."""
        data = {
            "name": "Test",
            "appearance": {
                "color_description": "Golden amber",
                # Missing other fields
            }
        }
        result = normalize_extracted_data(data)

        assert result.get("color_description") == "Golden amber"
        # Missing fields should not raise errors


class TestNestedRatingsFields:
    """Tests for ratings.* field mapping."""

    def test_maps_nested_ratings_fields(self, mock_ai_response_with_ratings):
        """
        Verify that all ratings.* fields are correctly mapped.

        The AI service returns ratings as a nested object with:
        - flavor_intensity -> flavor_intensity
        - complexity -> complexity
        - warmth -> warmth
        - dryness -> dryness
        - balance -> balance
        - overall_complexity -> overall_complexity
        - uniqueness -> uniqueness
        - drinkability -> drinkability
        """
        result = normalize_extracted_data(mock_ai_response_with_ratings)

        # All ratings fields should be flattened to top level
        assert "flavor_intensity" in result
        assert result["flavor_intensity"] == 8

        assert "complexity" in result
        assert result["complexity"] == 7

        assert "warmth" in result
        assert result["warmth"] == 6

        assert "dryness" in result
        assert result["dryness"] == 4

        assert "balance" in result
        assert result["balance"] == 8

        assert "overall_complexity" in result
        assert result["overall_complexity"] == 7

        assert "uniqueness" in result
        assert result["uniqueness"] == 5

        assert "drinkability" in result
        assert result["drinkability"] == 9

    def test_ratings_are_integers(self, mock_ai_response_with_ratings):
        """Verify that all ratings are mapped as integers."""
        result = normalize_extracted_data(mock_ai_response_with_ratings)

        rating_fields = [
            "flavor_intensity", "complexity", "warmth", "dryness",
            "balance", "overall_complexity", "uniqueness", "drinkability"
        ]

        for field in rating_fields:
            if field in result:
                assert isinstance(result[field], int), f"{field} should be an integer"

    def test_experience_level_maps_correctly(self, mock_ai_response_with_ratings):
        """Verify experience_level is mapped to top level."""
        result = normalize_extracted_data(mock_ai_response_with_ratings)

        assert "experience_level" in result
        assert result["experience_level"] == "intermediate"

    def test_ratings_partial_fields(self):
        """Verify partial ratings objects are handled correctly."""
        data = {
            "name": "Test",
            "ratings": {
                "balance": 7,
                "drinkability": 8
                # Missing other rating fields
            }
        }
        result = normalize_extracted_data(data)

        assert result.get("balance") == 7
        assert result.get("drinkability") == 8


class TestProductionFieldsMapping:
    """Tests for production.* field mapping."""

    def test_maps_production_fields(self, mock_ai_response_with_production):
        """
        Verify that all production.* fields are correctly mapped.

        The AI service returns production as a nested object with:
        - peat_ppm -> peat_ppm
        - natural_color -> natural_color
        - non_chill_filtered -> non_chill_filtered
        - primary_cask -> primary_cask (as array)
        - finishing_cask -> finishing_cask (as array)
        - wood_type -> wood_type (as array)
        - cask_treatment -> cask_treatment (as array)
        - maturation_notes -> maturation_notes
        """
        result = normalize_extracted_data(mock_ai_response_with_production)

        # Boolean fields
        assert "natural_color" in result
        assert result["natural_color"] is True

        assert "non_chill_filtered" in result
        assert result["non_chill_filtered"] is True

        # Integer fields
        assert "peat_ppm" in result
        assert result["peat_ppm"] == 55
        assert isinstance(result["peat_ppm"], int)

        # Array fields
        assert "primary_cask" in result
        assert result["primary_cask"] == ["ex-bourbon", "sherry"]
        assert isinstance(result["primary_cask"], list)

        assert "finishing_cask" in result
        assert result["finishing_cask"] == ["port"]

        assert "wood_type" in result
        assert result["wood_type"] == ["american_oak", "european_oak"]

        assert "cask_treatment" in result
        assert result["cask_treatment"] == ["charred", "toasted"]

        # Text fields
        assert "maturation_notes" in result
        assert "12 years" in result["maturation_notes"]

    def test_production_boolean_false_values(self):
        """Verify that False boolean values are preserved."""
        data = {
            "name": "Test",
            "production": {
                "natural_color": False,
                "non_chill_filtered": False,
                "cask_strength": False,
                "single_cask": False
            }
        }
        result = normalize_extracted_data(data)

        assert result.get("natural_color") is False
        assert result.get("non_chill_filtered") is False

    def test_production_cask_arrays_empty(self):
        """Verify empty cask arrays are handled correctly."""
        data = {
            "name": "Test",
            "production": {
                "primary_cask": [],
                "wood_type": []
            }
        }
        result = normalize_extracted_data(data)

        # Empty arrays should be preserved or not cause errors
        # Implementation may choose to exclude empty arrays
        assert "name" in result  # Ensure processing completed


class TestTastingEvolutionMapping:
    """Tests for tasting_evolution.* field mapping."""

    def test_maps_tasting_evolution_fields(self, mock_ai_response_with_tasting_evolution):
        """
        Verify that all tasting_evolution.* fields are correctly mapped.
        """
        result = normalize_extracted_data(mock_ai_response_with_tasting_evolution)

        assert "initial_taste" in result
        assert result["initial_taste"] == "Sweet honey and vanilla upfront"

        assert "mid_palate_evolution" in result
        assert "oak spice" in result["mid_palate_evolution"]

        assert "aroma_evolution" in result
        assert "Opens with fruit" in result["aroma_evolution"]

        assert "finish_evolution" in result
        assert "warm and spicy" in result["finish_evolution"]

        assert "final_notes" in result
        assert "Lingering warmth" in result["final_notes"]

    def test_secondary_aromas_maps_correctly(self, mock_ai_response_with_tasting_evolution):
        """Verify secondary_aromas array is mapped correctly."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_evolution)

        assert "secondary_aromas" in result
        assert result["secondary_aromas"] == ["citrus", "floral", "heather"]
        assert isinstance(result["secondary_aromas"], list)

    def test_mouthfeel_maps_correctly(self, mock_ai_response_with_tasting_evolution):
        """Verify mouthfeel is mapped to top level."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_evolution)

        assert "mouthfeel" in result
        assert result["mouthfeel"] == "smooth-creamy"

    def test_finish_length_maps_correctly(self, mock_ai_response_with_tasting_evolution):
        """Verify finish_length is mapped to top level."""
        result = normalize_extracted_data(mock_ai_response_with_tasting_evolution)

        assert "finish_length" in result
        assert result["finish_length"] == 8
        assert isinstance(result["finish_length"], int)


class TestMissingNestedObjects:
    """Tests for graceful handling of missing nested objects."""

    def test_handles_missing_nested_objects(self):
        """
        Verify graceful handling when nested objects are missing.

        The normalizer should not raise errors when optional nested
        objects (tasting_notes, appearance, ratings, production, etc.)
        are not present in the input data.
        """
        minimal_data = {
            "name": "Basic Product",
            "brand": "Test Brand",
            "abv": 40.0
        }

        # Should not raise any exceptions
        result = normalize_extracted_data(minimal_data)

        # Core fields should be preserved
        assert result["name"] == "Basic Product"
        assert result["brand"] == "Test Brand"
        assert result["abv"] == 40.0

    def test_handles_missing_tasting_notes(self):
        """Verify handling when tasting_notes is missing entirely."""
        data = {
            "name": "Test Product",
            "ratings": {"balance": 7}
        }

        result = normalize_extracted_data(data)

        # Should complete without errors
        assert result["name"] == "Test Product"
        # tasting fields should be absent or None, not cause errors

    def test_handles_missing_appearance(self):
        """Verify handling when appearance is missing entirely."""
        data = {
            "name": "Test Product",
            "tasting_notes": {"nose": "Fruity"}
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        # appearance fields should be absent, not cause errors

    def test_handles_missing_ratings(self):
        """Verify handling when ratings is missing entirely."""
        data = {
            "name": "Test Product",
            "appearance": {"color_description": "Amber"}
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        # rating fields should be absent, not cause errors

    def test_handles_missing_production(self):
        """Verify handling when production is missing entirely."""
        data = {
            "name": "Test Product",
            "ratings": {"balance": 7}
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        # production fields should be absent, not cause errors

    def test_handles_empty_nested_objects(self):
        """Verify handling when nested objects are present but empty."""
        data = {
            "name": "Test Product",
            "tasting_notes": {},
            "appearance": {},
            "ratings": {},
            "production": {}
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        # Empty objects should not cause errors

    def test_handles_null_nested_objects(self):
        """Verify handling when nested objects are explicitly None."""
        data = {
            "name": "Test Product",
            "tasting_notes": None,
            "appearance": None,
            "ratings": None,
            "production": None
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        # None values should not cause errors

    def test_handles_partial_nested_objects(self):
        """Verify handling when nested objects have only some fields."""
        data = {
            "name": "Test Product",
            "tasting_notes": {
                "nose": "Honey and vanilla"
                # Missing palate, finish, arrays
            },
            "appearance": {
                "color_description": "Gold"
                # Missing intensity, clarity, viscosity
            },
            "ratings": {
                "balance": 8
                # Missing other ratings
            }
        }

        result = normalize_extracted_data(data)

        assert result["name"] == "Test Product"
        assert result.get("nose_description") == "Honey and vanilla"
        assert result.get("color_description") == "Gold"
        assert result.get("balance") == 8


class TestCompleteFieldMapping:
    """Tests for complete field mapping with all V2 fields."""

    def test_complete_v2_response_mapping(self, mock_ai_response_complete):
        """
        Verify that a complete V2 AI response is correctly mapped.

        This is the comprehensive test ensuring all fields from the
        AI Enhancement Service V2 spec are correctly mapped.
        """
        result = normalize_extracted_data(mock_ai_response_complete)

        # Core fields
        assert result["name"] == "Glencadam 10 Year Old"
        assert result["brand"] == "Glencadam"
        assert result.get("category") == "Single Malt Scotch"
        assert result.get("description") == "A superb Highland single malt with notes of honey and green apple."
        assert result["abv"] == 46.0
        assert result["age_statement"] == 10
        assert result.get("region") == "Highland"
        assert result.get("country") == "Scotland"

        # Tasting - Nose (CRITICAL)
        assert result.get("nose_description") == "Fresh and floral with notes of honey and green apple"
        assert result.get("primary_aromas") == ["honey", "green apple", "vanilla", "floral"]
        assert result.get("secondary_aromas") == ["citrus", "floral"]
        assert "Opens with fruit" in result.get("aroma_evolution", "")

        # Tasting - Palate (CRITICAL)
        assert result.get("palate_description") == "Smooth and creamy with flavors of butterscotch and citrus"
        assert result.get("palate_flavors") == ["butterscotch", "oak", "citrus", "vanilla"]
        assert result.get("initial_taste") == "Sweet honey and vanilla"
        assert "oak and spice" in result.get("mid_palate_evolution", "")
        assert result.get("mouthfeel") == "smooth-creamy"

        # Tasting - Finish (CRITICAL)
        assert result.get("finish_description") == "Medium-long with lingering honey and oak"
        assert result.get("finish_flavors") == ["honey", "spice", "oak"]
        assert result.get("finish_length") == 7
        assert "warm" in result.get("finish_evolution", "").lower()
        assert "Lingering warmth" in result.get("final_notes", "")

        # Appearance
        assert result.get("color_description") == "Deep amber with golden highlights"
        assert result.get("color_intensity") == 7
        assert result.get("clarity") == "crystal_clear"
        assert result.get("viscosity") == "medium"

        # Ratings
        assert result.get("flavor_intensity") == 7
        assert result.get("complexity") == 8
        assert result.get("warmth") == 5
        assert result.get("dryness") == 4
        assert result.get("balance") == 8
        assert result.get("overall_complexity") == 7
        assert result.get("uniqueness") == 6
        assert result.get("drinkability") == 9

        # Other
        assert result.get("experience_level") == "intermediate"
        assert result.get("serving_recommendation") == "neat"

        # Food pairings (may be list or string depending on model)
        food_pairings = result.get("food_pairings")
        if isinstance(food_pairings, str):
            assert "dark chocolate" in food_pairings
        elif isinstance(food_pairings, list):
            assert "dark chocolate" in food_pairings

        # Production
        assert result.get("natural_color") is True
        assert result.get("non_chill_filtered") is True
        assert result.get("primary_cask") == ["ex-bourbon"]
        assert result.get("wood_type") == ["american_oak"]

    def test_existing_top_level_fields_preserved(self):
        """Verify that existing top-level fields are not overwritten by nested mapping."""
        data = {
            "name": "Test",
            "nose_description": "Existing nose description",  # Top-level
            "tasting_notes": {
                "nose": "Should not overwrite existing"  # Nested
            }
        }

        result = normalize_extracted_data(data)

        # Existing top-level should be preserved
        assert result["nose_description"] == "Existing nose description"


class TestDataTypePreservation:
    """Tests to verify data types are preserved correctly."""

    def test_array_fields_remain_arrays(self, mock_ai_response_complete):
        """Verify that array fields remain as arrays after mapping."""
        result = normalize_extracted_data(mock_ai_response_complete)

        array_fields = [
            "primary_aromas", "secondary_aromas", "palate_flavors",
            "finish_flavors", "primary_cask", "wood_type"
        ]

        for field in array_fields:
            if field in result:
                assert isinstance(result[field], list), f"{field} should be a list"

    def test_integer_fields_remain_integers(self, mock_ai_response_complete):
        """Verify that integer fields remain as integers after mapping."""
        result = normalize_extracted_data(mock_ai_response_complete)

        integer_fields = [
            "color_intensity", "flavor_intensity", "complexity",
            "warmth", "dryness", "balance", "overall_complexity",
            "uniqueness", "drinkability", "finish_length", "age_statement"
        ]

        for field in integer_fields:
            if field in result and result[field] is not None:
                assert isinstance(result[field], int), f"{field} should be an integer"

    def test_boolean_fields_remain_booleans(self, mock_ai_response_complete):
        """Verify that boolean fields remain as booleans after mapping."""
        result = normalize_extracted_data(mock_ai_response_complete)

        boolean_fields = ["natural_color", "non_chill_filtered"]

        for field in boolean_fields:
            if field in result and result[field] is not None:
                assert isinstance(result[field], bool), f"{field} should be a boolean"

    def test_float_fields_remain_floats(self, mock_ai_response_complete):
        """Verify that float fields remain as floats after mapping."""
        result = normalize_extracted_data(mock_ai_response_complete)

        # ABV should remain a float
        if "abv" in result and result["abv"] is not None:
            assert isinstance(result["abv"], (int, float)), "abv should be numeric"
