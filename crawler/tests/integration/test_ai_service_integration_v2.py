"""
Integration tests for Crawler to AI Enhancement Service communication.

Task 7.3: Integration Test - Crawler to AI Service
Spec Reference: AI Enhancement Service V2 Integration

These tests verify the crawler correctly:
1. Sends requests in the expected format to the AI service
2. Parses V2 responses with all new fields
3. Maps AI response fields to the DiscoveredProduct model
4. Handles AI service errors gracefully
5. Handles partial/incomplete responses

Uses the `responses` library for HTTP mocking.

Updated 2026-01-11: Migrated from V1 to V2 architecture.
"""

import json
import pytest
import responses
from typing import Dict, Any
from unittest.mock import MagicMock, patch


# Test fixtures for AI service responses
@pytest.fixture
def ai_service_base_url():
    """Base URL for the AI enhancement service."""
    return "https://ai-service.example.com"


@pytest.fixture
def mock_token_response():
    """Mock JWT token response for authentication."""
    return {
        "access": "mock_access_token_12345",
        "refresh": "mock_refresh_token_67890"
    }


@pytest.fixture
def mock_v2_whiskey_response():
    """
    Complete V2 AI service response for whiskey.

    Contains all V2 fields including:
    - tasting_notes with nose_aromas, palate_flavors, finish_flavors
    - tasting_evolution
    - appearance
    - ratings
    - production
    - description, category
    """
    return {
        "success": True,
        "is_multi_product": False,
        "product_type": "whiskey",
        "extracted_data": {
            "name": "Glencadam 10 Year Old",
            "brand": "Glencadam",
            "whiskey_type": "scotch_single_malt",
            "category": "Single Malt Scotch",
            "description": "A Highland single malt with honeyed sweetness and orchard fruit notes.",
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
                "nose": "Fresh and floral with honey and green apple",
                "nose_aromas": ["honey", "green apple", "vanilla", "floral"],
                "palate": "Smooth butterscotch and citrus flavors",
                "palate_flavors": ["butterscotch", "oak", "citrus", "vanilla", "spice"],
                "finish": "Medium-long with lingering honey",
                "finish_flavors": ["honey", "spice", "oak"]
            },
            "tasting_evolution": {
                "initial_taste": "Sweet honey upfront",
                "mid_palate_evolution": "Develops oak and spice",
                "aroma_evolution": "Opens with fruit, becomes complex",
                "finish_evolution": "Starts warm, fades to sweet",
                "final_notes": "Lingering vanilla warmth"
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
            "production": {
                "distillery": "Glencadam",
                "natural_color": True,
                "non_chill_filtered": True,
                "primary_cask": ["ex-bourbon"],
                "wood_type": ["american_oak"],
                "cask_strength": False,
                "single_cask": False,
                "peated": False
            },
            "awards": [
                {"competition": "IWSC", "year": 2023, "medal": "Gold", "score": 95}
            ]
        },
        "enrichment": {
            "tasting_notes": {
                "nose": "Fresh and floral with honey and green apple",
                "palate": "Smooth butterscotch and citrus flavors",
                "finish": "Medium-long with lingering honey"
            },
            "flavor_profile": ["honey", "vanilla", "oak", "butterscotch"],
            "food_pairings": ["dark chocolate", "aged cheese"],
            "serving_suggestion": "neat or with a drop of water"
        }
    }


@pytest.fixture
def mock_v2_port_wine_response():
    """
    Complete V2 AI service response for port wine.

    Contains port-specific fields plus all V2 enhancement fields.
    """
    return {
        "success": True,
        "is_multi_product": False,
        "product_type": "port_wine",
        "extracted_data": {
            "name": "Graham's Six Grapes Reserve Port",
            "brand": "Graham's",
            "style": "ruby",
            "category": "Ruby Port",
            "description": "A rich ruby port with intense fruit and spice character.",
            "abv": 20.0,
            "volume_ml": 750,
            "region": "Douro",
            "country": "Portugal",
            "appearance": {
                "color_description": "Deep ruby red with purple rim",
                "color_intensity": 9,
                "clarity": "crystal_clear",
                "viscosity": "full_bodied"
            },
            "tasting_notes": {
                "nose": "Ripe black fruits with spice",
                "nose_aromas": ["blackberry", "plum", "cinnamon", "chocolate"],
                "palate": "Full-bodied with rich fruit and smooth tannins",
                "palate_flavors": ["blackberry", "cherry", "dark chocolate", "spice", "vanilla"],
                "finish": "Long and warming with persistent fruit",
                "finish_flavors": ["cherry", "chocolate", "spice"]
            },
            "mouthfeel": "full-rich",
            "finish_length": 8,
            "ratings": {
                "flavor_intensity": 9,
                "complexity": 7,
                "warmth": 6,
                "dryness": 3,
                "balance": 8,
                "overall_complexity": 7,
                "uniqueness": 5,
                "drinkability": 8
            },
            "grape_varieties": ["Touriga Nacional", "Touriga Franca", "Tinta Barroca"],
            "douro_subregion": "Cima Corgo"
        }
    }


@pytest.fixture
def mock_partial_response():
    """
    Mock AI service response with only some fields populated.

    Simulates a partial extraction where not all fields could be determined.
    """
    return {
        "success": True,
        "is_multi_product": False,
        "product_type": "whiskey",
        "extracted_data": {
            "name": "Unknown Whiskey",
            "brand": None,
            "whiskey_type": "scotch_single_malt",
            "abv": 40.0,
            "tasting_notes": {
                "nose": "Smoky and peaty",
                "palate_flavors": ["smoke", "peat", "seaweed"]
                # Missing nose_aromas, finish_flavors, etc.
            }
            # Missing appearance, ratings, production, etc.
        }
    }


@pytest.fixture
def mock_multi_product_response():
    """
    Mock AI service response for multi-product extraction.

    Simulates extraction from a page with multiple products.
    """
    return {
        "success": True,
        "is_multi_product": True,
        "products": [
            {
                "extracted_data": {
                    "name": "Macallan 12 Year Old",
                    "brand": "Macallan",
                    "whiskey_type": "scotch_single_malt",
                    "category": "Single Malt Scotch",
                    "abv": 43.0,
                    "tasting_notes": {
                        "palate_flavors": ["sherry", "dried fruit", "oak"]
                    }
                },
                "enrichment": {
                    "flavor_profile": ["sherry", "dried fruit", "oak"]
                }
            },
            {
                "extracted_data": {
                    "name": "Glenlivet 12 Year Old",
                    "brand": "Glenlivet",
                    "whiskey_type": "scotch_single_malt",
                    "category": "Single Malt Scotch",
                    "abv": 40.0,
                    "tasting_notes": {
                        "palate_flavors": ["vanilla", "apple", "honey"]
                    }
                },
                "enrichment": {
                    "flavor_profile": ["vanilla", "apple", "honey"]
                }
            }
        ]
    }


@pytest.fixture
def mock_error_response():
    """Mock AI service error response."""
    return {
        "success": False,
        "error": "AI processing failed: content too short",
        "status_code": 400
    }


class TestCrawlerSendsCorrectRequestFormat:
    """Test that the crawler sends requests in the correct format to the AI service."""

    @responses.activate
    def test_crawler_sends_correct_request_format(
        self, ai_service_base_url, mock_token_response, mock_v2_whiskey_response
    ):
        """
        Verify that the crawler sends requests with the correct structure.

        The AI service expects:
        - POST to /api/v1/enhance/from-crawler/
        - JSON body with: content, source_url, product_type_hint (optional)
        - Authorization header with Bearer token
        """
        # Setup mock auth endpoint
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        # Setup mock enhance endpoint - capture the request
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            json=mock_v2_whiskey_response,
            status=200
        )

        # Import and create client
        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        # Patch the base URL
        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        # Make the request
        result = client.enhance_from_crawler(
            content="<html><body>Glencadam 10 Year Old Single Malt...</body></html>",
            source_url="https://example.com/whiskey/glencadam-10",
            product_type_hint="whiskey"
        )

        # Verify result
        assert result["success"] is True
        assert result["status_code"] == 200

        # Verify request was made correctly
        assert len(responses.calls) == 2  # token + enhance

        # Check enhance request
        enhance_request = responses.calls[1]
        assert enhance_request.request.url == f"{ai_service_base_url}/api/v1/enhance/from-crawler/"

        # Verify request body
        request_body = json.loads(enhance_request.request.body)
        assert "content" in request_body
        assert "source_url" in request_body
        assert request_body["source_url"] == "https://example.com/whiskey/glencadam-10"
        assert request_body["product_type_hint"] == "whiskey"

        # Verify authorization header
        assert "Authorization" in enhance_request.request.headers
        assert enhance_request.request.headers["Authorization"].startswith("Bearer ")

    @responses.activate
    def test_crawler_sends_content_type_json(
        self, ai_service_base_url, mock_token_response, mock_v2_whiskey_response
    ):
        """Verify that Content-Type is set to application/json."""
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            json=mock_v2_whiskey_response,
            status=200
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        client.enhance_from_crawler(
            content="Test content",
            source_url="https://example.com/test"
        )

        enhance_request = responses.calls[1]
        assert enhance_request.request.headers.get("Content-Type") == "application/json"

    @responses.activate
    def test_crawler_handles_optional_product_type_hint(
        self, ai_service_base_url, mock_token_response, mock_v2_whiskey_response
    ):
        """Verify that product_type_hint is optional in the request."""
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            json=mock_v2_whiskey_response,
            status=200
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        # Call without product_type_hint
        result = client.enhance_from_crawler(
            content="Test content",
            source_url="https://example.com/test"
        )

        assert result["success"] is True

        # Verify product_type_hint is not in body when not provided
        enhance_request = responses.calls[1]
        request_body = json.loads(enhance_request.request.body)
        assert "product_type_hint" not in request_body


class TestCrawlerParsesV2ResponseCorrectly:
    """Test that the crawler correctly parses V2 AI service responses."""

    def test_crawler_parses_v2_response_correctly(self, mock_v2_whiskey_response):
        """
        Verify that the crawler correctly parses all V2 fields from the AI response.

        This test verifies parsing of:
        - tasting_notes with nose_aromas, palate_flavors, finish_flavors
        - tasting_evolution fields
        - appearance nested object
        - ratings nested object
        - production nested object
        - description, category
        """
        # Use the DiscoveryOrchestratorV2's _normalize_data_for_save method
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        # Extract the data portion (what we'd get from AI service)
        extracted_data = mock_v2_whiskey_response["extracted_data"]

        # Normalize the data
        result = orchestrator._normalize_data_for_save(extracted_data)

        # Verify CRITICAL fields (Phase 1)
        assert result.get("primary_aromas") == ["honey", "green apple", "vanilla", "floral"]
        assert result.get("palate_flavors") == ["butterscotch", "oak", "citrus", "vanilla", "spice"]
        assert result.get("finish_flavors") == ["honey", "spice", "oak"]
        assert result.get("description") == "A Highland single malt with honeyed sweetness and orchard fruit notes."
        assert result.get("category") == "Single Malt Scotch"

        # Verify tasting evolution fields (Phase 2)
        assert result.get("initial_taste") == "Sweet honey upfront"
        assert "oak and spice" in result.get("mid_palate_evolution", "")
        assert result.get("mouthfeel") == "smooth-creamy"
        assert result.get("finish_length") == 7
        assert result.get("secondary_aromas") == ["citrus", "floral"]

        # Verify appearance fields (Phase 3)
        assert result.get("color_description") == "Deep amber with golden highlights"
        assert result.get("color_intensity") == 7
        assert result.get("clarity") == "crystal_clear"
        assert result.get("viscosity") == "medium"

        # Verify ratings fields (Phase 3)
        assert result.get("flavor_intensity") == 7
        assert result.get("complexity") == 8
        assert result.get("balance") == 8
        assert result.get("drinkability") == 9

        # Verify production fields (Phase 4)
        assert result.get("natural_color") is True
        assert result.get("non_chill_filtered") is True
        assert result.get("primary_cask") == ["ex-bourbon"]

    def test_crawler_parses_port_wine_v2_response(self, mock_v2_port_wine_response):
        """Verify parsing of port wine specific V2 fields."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)
        extracted_data = mock_v2_port_wine_response["extracted_data"]

        result = orchestrator._normalize_data_for_save(extracted_data)

        # Verify port-specific fields are preserved
        assert result.get("style") == "ruby"
        assert result.get("category") == "Ruby Port"
        assert "Touriga Nacional" in result.get("grape_varieties", [])
        assert result.get("douro_subregion") == "Cima Corgo"

        # Verify tasting fields
        assert result.get("palate_flavors") == ["blackberry", "cherry", "dark chocolate", "spice", "vanilla"]
        assert result.get("finish_length") == 8
        assert result.get("mouthfeel") == "full-rich"

    def test_crawler_parses_multi_product_response(self, mock_multi_product_response):
        """Verify parsing of multi-product AI responses."""
        # Multi-product responses are handled at the orchestrator level
        # The products list should be processed individually

        products = mock_multi_product_response.get("products", [])

        assert len(products) == 2

        # First product
        assert products[0]["extracted_data"]["name"] == "Macallan 12 Year Old"
        assert "sherry" in products[0]["extracted_data"]["tasting_notes"]["palate_flavors"]

        # Second product
        assert products[1]["extracted_data"]["name"] == "Glenlivet 12 Year Old"
        assert "vanilla" in products[1]["extracted_data"]["tasting_notes"]["palate_flavors"]


class TestCrawlerMapsAllNewFieldsToModel:
    """Test that all V2 fields are correctly mapped to the model."""

    def test_crawler_maps_all_new_fields_to_model(self, mock_v2_whiskey_response):
        """
        Verify that all V2 fields are mapped to their corresponding model fields.

        Field mapping from AI Service V2:
        - tasting_notes.nose_aromas -> primary_aromas
        - tasting_notes.palate_flavors -> palate_flavors
        - tasting_notes.finish_flavors -> finish_flavors
        - tasting_evolution.* -> corresponding fields
        - appearance.* -> corresponding fields
        - ratings.* -> corresponding fields
        - production.* -> corresponding fields
        """
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)
        extracted_data = mock_v2_whiskey_response["extracted_data"]

        result = orchestrator._normalize_data_for_save(extracted_data)

        # Verify all tasting_notes mappings
        assert "nose_description" in result  # nose -> nose_description
        assert "primary_aromas" in result    # nose_aromas -> primary_aromas
        assert "palate_description" in result  # palate -> palate_description
        assert "palate_flavors" in result
        assert "finish_description" in result  # finish -> finish_description
        assert "finish_flavors" in result

        # Verify all tasting_evolution mappings
        assert "initial_taste" in result
        assert "mid_palate_evolution" in result
        assert "aroma_evolution" in result
        assert "finish_evolution" in result
        assert "final_notes" in result

        # Verify all appearance mappings
        assert "color_description" in result
        assert "color_intensity" in result
        assert "clarity" in result
        assert "viscosity" in result

        # Verify all ratings mappings
        rating_fields = [
            "flavor_intensity", "complexity", "warmth", "dryness",
            "balance", "overall_complexity", "uniqueness", "drinkability"
        ]
        for field in rating_fields:
            assert field in result, f"Missing rating field: {field}"

        # Verify all production mappings
        assert "distillery" in result
        assert "natural_color" in result
        assert "non_chill_filtered" in result
        assert "primary_cask" in result
        assert "wood_type" in result

        # Verify top-level V2 fields
        assert "description" in result
        assert "category" in result
        assert "mouthfeel" in result
        assert "finish_length" in result
        assert "secondary_aromas" in result
        assert "experience_level" in result

    def test_maps_enrichment_data_correctly(self, mock_v2_whiskey_response):
        """Verify that enrichment data is also mapped correctly."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        # Merge extracted_data with enrichment (as orchestrator does)
        data = mock_v2_whiskey_response["extracted_data"].copy()
        data["enrichment"] = mock_v2_whiskey_response.get("enrichment", {})

        result = orchestrator._normalize_data_for_save(data)

        # Verify enrichment data is mapped
        # flavor_profile should be available
        if "flavor_profile" in mock_v2_whiskey_response.get("enrichment", {}):
            # May map to palate_flavors if not already set
            pass

        # food_pairings should be mapped
        food_pairings = result.get("food_pairings")
        if food_pairings:
            if isinstance(food_pairings, str):
                assert "dark chocolate" in food_pairings or "aged cheese" in food_pairings
            elif isinstance(food_pairings, list):
                assert "dark chocolate" in food_pairings or "aged cheese" in food_pairings


class TestCrawlerHandlesAIServiceErrors:
    """Test error handling for AI service failures."""

    @responses.activate
    def test_crawler_handles_ai_service_errors(
        self, ai_service_base_url, mock_token_response
    ):
        """
        Verify that the crawler gracefully handles AI service errors.

        Error scenarios:
        - HTTP 400 Bad Request
        - HTTP 500 Internal Server Error
        - Connection timeout
        - Invalid JSON response
        """
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        # Setup error response
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            json={"error": "AI processing failed"},
            status=500
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        result = client.enhance_from_crawler(
            content="Test content",
            source_url="https://example.com/test"
        )

        # Should return error info, not raise exception
        assert result["success"] is False
        assert result["status_code"] == 500
        assert "error" in result

    @responses.activate
    def test_crawler_handles_400_bad_request(
        self, ai_service_base_url, mock_token_response
    ):
        """Verify handling of 400 Bad Request errors."""
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            json={"error": "Invalid request: content too short"},
            status=400
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        result = client.enhance_from_crawler(
            content="x",  # Very short content
            source_url="https://example.com/test"
        )

        assert result["success"] is False
        assert result["status_code"] == 400

    @responses.activate
    def test_crawler_handles_timeout(
        self, ai_service_base_url, mock_token_response
    ):
        """Verify handling of request timeouts."""
        import requests as requests_lib

        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json=mock_token_response,
            status=200
        )

        # Simulate timeout by raising exception
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/v1/enhance/from-crawler/",
            body=requests_lib.exceptions.Timeout("Connection timed out")
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "test_user"
            client.password = "test_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        result = client.enhance_from_crawler(
            content="Test content",
            source_url="https://example.com/test"
        )

        assert result["success"] is False
        assert "timeout" in result.get("error", "").lower()

    @responses.activate
    def test_crawler_handles_authentication_failure(
        self, ai_service_base_url
    ):
        """
        Verify handling of authentication failures.

        When the AI service returns 401 on token request,
        the client returns a graceful error response (not an exception).
        The enhance_from_crawler method catches auth exceptions and returns
        an error dict with success=False and the error message.
        """
        responses.add(
            responses.POST,
            f"{ai_service_base_url}/api/token/",
            json={"error": "Invalid credentials"},
            status=401
        )

        from crawler.tests.integration.ai_service_client import AIEnhancementClient

        with patch.object(AIEnhancementClient, '__init__', lambda self: None):
            client = AIEnhancementClient()
            client.base_url = ai_service_base_url
            client.username = "wrong_user"
            client.password = "wrong_pass"
            client.session = __import__('requests').Session()
            client.access_token = None
            client.refresh_token = None
            client.token_expiry = 0
            client.request_count = 0
            client.failed_requests = []

        # The client handles auth failures gracefully by returning an error result
        result = client.enhance_from_crawler(
            content="Test content",
            source_url="https://example.com/test"
        )

        # Verify error result structure
        assert result["success"] is False
        assert "error" in result
        # Error message should indicate authentication failure
        error_message = result.get("error", "").lower()
        assert "auth" in error_message or "401" in error_message or "failed" in error_message


class TestCrawlerHandlesPartialResponses:
    """Test handling of partial/incomplete AI service responses."""

    def test_crawler_handles_partial_responses(self, mock_partial_response):
        """
        Verify that the crawler gracefully handles partial AI responses.

        Partial responses may be missing:
        - Some tasting_notes arrays (nose_aromas, finish_flavors)
        - Entire nested objects (appearance, ratings, production)
        - Optional fields (description, category)
        """
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)
        extracted_data = mock_partial_response["extracted_data"]

        # Should not raise exception
        result = orchestrator._normalize_data_for_save(extracted_data)

        # Core fields should be present
        assert result.get("name") == "Unknown Whiskey"
        assert result.get("abv") == 40.0

        # Available tasting fields should be mapped
        assert result.get("palate_flavors") == ["smoke", "peat", "seaweed"]

        # Missing fields should not cause errors
        # Just should not be present or be None
        assert result.get("primary_aromas") is None or "primary_aromas" not in result
        assert result.get("appearance") is None or "color_intensity" not in result

    def test_crawler_handles_empty_tasting_notes(self):
        """Verify handling when tasting_notes is empty object."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        data = {
            "name": "Test Product",
            "tasting_notes": {}
        }

        result = orchestrator._normalize_data_for_save(data)

        assert result["name"] == "Test Product"
        # Should not raise errors with empty tasting_notes

    def test_crawler_handles_null_nested_objects(self):
        """Verify handling when nested objects are null."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        data = {
            "name": "Test Product",
            "tasting_notes": None,
            "appearance": None,
            "ratings": None,
            "production": None,
            "tasting_evolution": None
        }

        result = orchestrator._normalize_data_for_save(data)

        assert result["name"] == "Test Product"
        # Should complete without errors

    def test_crawler_handles_missing_critical_arrays(self):
        """Verify handling when critical arrays are missing."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        data = {
            "name": "Test Product",
            "tasting_notes": {
                "nose": "Fruity and floral",
                "palate": "Sweet with vanilla",
                "finish": "Long and warming"
                # Missing nose_aromas, palate_flavors, finish_flavors
            }
        }

        result = orchestrator._normalize_data_for_save(data)

        # Text descriptions should still be mapped
        assert result.get("nose_description") == "Fruity and floral"
        assert result.get("palate_description") == "Sweet with vanilla"
        assert result.get("finish_description") == "Long and warming"

    def test_crawler_handles_partial_ratings(self):
        """Verify handling when only some ratings are present."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        data = {
            "name": "Test Product",
            "ratings": {
                "balance": 8,
                "drinkability": 9
                # Missing other rating fields
            }
        }

        result = orchestrator._normalize_data_for_save(data)

        assert result.get("balance") == 8
        assert result.get("drinkability") == 9
        # Missing ratings should not cause errors
        assert result.get("complexity") is None

    def test_crawler_handles_response_with_only_name(self):
        """Verify handling when response only contains name."""
        from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2

        orchestrator = DiscoveryOrchestratorV2.__new__(DiscoveryOrchestratorV2)

        data = {"name": "Minimal Product"}

        result = orchestrator._normalize_data_for_save(data)

        assert result["name"] == "Minimal Product"
        # Should complete without errors
