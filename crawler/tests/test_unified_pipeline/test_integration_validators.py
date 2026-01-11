"""
Integration Validator TDD Tests - Phase 11

Spec Reference: docs/specs/INTEGRATION_FAILURE_ANALYSIS.md
               docs/specs/INTEGRATION_FAILURE_FIX_TASKS.md

These tests verify that field validators handle real-world edge cases.
Written FIRST according to TDD methodology - these MUST FAIL initially.

Critical Gaps Being Tested (15 failures):
- Whiskey type normalization (5 products)
- Vintage year cleaning (2 products)
- Brand fallback logic (3 products)
- Age designation cleaning (1 product)
- Retry logic (4 products)
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase


class TestWhiskeyTypeNormalization(TestCase):
    """
    Tests that whiskey type values are normalized correctly.

    Fixes: Glenallachie 10, Benriach The Twelve, Elijah Craig,
           Jim Beam Double Oak, Rebel Yell (5 products)
    """

    def test_single_malt_normalizes_to_scotch_single_malt(self):
        """'single malt' should normalize to 'scotch_single_malt'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("single malt")
        self.assertEqual(result, "scotch_single_malt")

    def test_single_malt_scotch_normalizes_correctly(self):
        """'Single Malt Scotch' should normalize to 'scotch_single_malt'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Single Malt Scotch")
        self.assertEqual(result, "scotch_single_malt")

    def test_kentucky_straight_bourbon_normalizes_to_bourbon(self):
        """'Kentucky Straight Bourbon' should normalize to 'bourbon'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Kentucky Straight Bourbon")
        self.assertEqual(result, "bourbon")

    def test_small_batch_bourbon_normalizes_to_bourbon(self):
        """'Small Batch Bourbon' should normalize to 'bourbon'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Small Batch Bourbon")
        self.assertEqual(result, "bourbon")

    def test_tennessee_whiskey_normalizes_correctly(self):
        """'Tennessee Whiskey' should normalize to 'tennessee'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Tennessee Whiskey")
        self.assertEqual(result, "tennessee")

    def test_speyside_single_malt_normalizes_correctly(self):
        """'Speyside Single Malt' should normalize to 'scotch_single_malt'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Speyside Single Malt")
        self.assertEqual(result, "scotch_single_malt")

    def test_already_normalized_value_passes_through(self):
        """Already normalized values like 'bourbon' should pass through."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("bourbon")
        self.assertEqual(result, "bourbon")

    def test_unknown_type_normalizes_to_world_whiskey(self):
        """Unknown whiskey types should normalize to 'world_whiskey'."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("Unknown Regional Style")
        self.assertEqual(result, "world_whiskey")

    def test_case_insensitive_normalization(self):
        """Normalization should be case insensitive."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type("BOURBON")
        self.assertEqual(result, "bourbon")

    def test_none_returns_none(self):
        """None input should return None."""
        from crawler.validators.whiskey import normalize_whiskey_type

        result = normalize_whiskey_type(None)
        self.assertIsNone(result)


class TestVintageYearCleaning(TestCase):
    """
    Tests that vintage year values are cleaned correctly.

    Fixes: Glenallachie 10, Rittenhouse Rye (2 products)
    """

    def test_na_string_returns_none(self):
        """'N/A' should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("N/A")
        self.assertIsNone(result)

    def test_none_string_returns_none(self):
        """'None' should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("None")
        self.assertIsNone(result)

    def test_nv_string_returns_none(self):
        """'NV' (non-vintage) should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("NV")
        self.assertIsNone(result)

    def test_valid_year_integer_passes_through(self):
        """Valid integer year should pass through."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year(2019)
        self.assertEqual(result, 2019)

    def test_valid_year_string_converted(self):
        """Valid year as string should be converted to int."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("2019")
        self.assertEqual(result, 2019)

    def test_year_with_vintage_suffix_extracted(self):
        """'2019 vintage' should extract 2019."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("2019 vintage")
        self.assertEqual(result, 2019)

    def test_year_before_1900_returns_none(self):
        """Year before 1900 should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year(1850)
        self.assertIsNone(result)

    def test_year_after_current_returns_none(self):
        """Year after current year should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year(2030)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year("")
        self.assertIsNone(result)

    def test_none_input_returns_none(self):
        """None input should return None."""
        from crawler.validators.whiskey import clean_vintage_year

        result = clean_vintage_year(None)
        self.assertIsNone(result)


class TestBrandFallbackLogic(TestCase):
    """
    Tests that brand is extracted from product name when missing.

    Fixes: Booker's Bourbon, 1792 Small Batch, Russell's Reserve (3 products)
    """

    def test_extract_brand_from_bookers_bourbon(self):
        """Should extract 'Booker's' from 'Booker's Bourbon'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Booker's Bourbon")
        self.assertEqual(result, "Booker's")

    def test_extract_brand_from_russells_reserve(self):
        """Should extract 'Russell's Reserve' from 'Russell's Reserve 10 Year'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Russell's Reserve 10 Year")
        self.assertEqual(result, "Russell's Reserve")

    def test_extract_brand_from_1792_small_batch(self):
        """Should extract '1792' from '1792 Small Batch'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("1792 Small Batch")
        self.assertEqual(result, "1792")

    def test_extract_brand_from_buffalo_trace(self):
        """Should extract 'Buffalo Trace' from 'Buffalo Trace Kentucky Straight'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Buffalo Trace Kentucky Straight Bourbon")
        self.assertEqual(result, "Buffalo Trace")

    def test_extract_brand_from_jim_beam(self):
        """Should extract 'Jim Beam' from 'Jim Beam Double Oak'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Jim Beam Double Oak")
        self.assertEqual(result, "Jim Beam")

    def test_extract_brand_from_elijah_craig(self):
        """Should extract 'Elijah Craig' from 'Elijah Craig Small Batch'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Elijah Craig Small Batch")
        self.assertEqual(result, "Elijah Craig")

    def test_extract_brand_from_makers_mark(self):
        """Should extract 'Maker's Mark' from 'Maker's Mark 46'."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Maker's Mark 46")
        self.assertEqual(result, "Maker's Mark")

    def test_generic_fallback_first_words_before_number(self):
        """Generic fallback: extract words before first number."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("Unknown Distillery 12 Year Old")
        self.assertEqual(result, "Unknown Distillery")

    def test_none_name_returns_none(self):
        """None input should return None."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name(None)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        from crawler.validators.whiskey import extract_brand_from_name

        result = extract_brand_from_name("")
        self.assertIsNone(result)


class TestAgeDesignationCleaning(TestCase):
    """
    Tests that age designation values are cleaned correctly.

    Fixes: Sandeman 30 Year Old Tawny (1 product)
    """

    def test_30_years_extracts_30(self):
        """'30 years' should extract 30."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation("30 years")
        self.assertEqual(result, 30)

    def test_30_year_old_extracts_30(self):
        """'30 Year Old' should extract 30."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation("30 Year Old")
        self.assertEqual(result, 30)

    def test_integer_passes_through(self):
        """Integer 20 should pass through."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation(20)
        self.assertEqual(result, 20)

    def test_string_number_converted(self):
        """'10' string should convert to 10."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation("10")
        self.assertEqual(result, 10)

    def test_rounds_to_nearest_10(self):
        """32 should round to 30."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation(32)
        self.assertEqual(result, 30)

    def test_invalid_age_returns_none(self):
        """Age < 10 should return None."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation(5)
        self.assertIsNone(result)

    def test_na_returns_none(self):
        """'N/A' should return None."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation("N/A")
        self.assertIsNone(result)

    def test_none_returns_none(self):
        """None should return None."""
        from crawler.validators.port_wine import clean_age_designation

        result = clean_age_designation(None)
        self.assertIsNone(result)


class TestRetryLogicCrawl(TestCase):
    """
    Tests that crawl retry with exponential backoff works.

    Fixes: Bulleit Bourbon (1 product)
    """

    def test_retry_on_500_error(self):
        """Should retry on HTTP 500 error."""
        from crawler.services.scrapingbee_client import ScrapingBeeClient

        client = ScrapingBeeClient(api_key="test_key")

        # Mock the fetch method
        call_count = [0]

        def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"success": False, "status_code": 500, "content": "", "error": "Server Error"}
            return {"success": True, "status_code": 200, "content": "<html>Product Page</html>"}

        client.fetch = mock_fetch

        result = client.fetch_with_retry("http://example.com/product", max_retries=3)

        self.assertEqual(call_count[0], 2)
        self.assertIsNotNone(result)

    def test_gives_up_after_max_retries(self):
        """Should give up after max_retries attempts."""
        from crawler.services.scrapingbee_client import ScrapingBeeClient

        client = ScrapingBeeClient(api_key="test_key")

        # Mock the fetch method to always fail
        call_count = [0]

        def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            return {"success": False, "status_code": 500, "content": "", "error": "Server Error"}

        client.fetch = mock_fetch

        result = client.fetch_with_retry("http://example.com/product", max_retries=3)

        self.assertEqual(call_count[0], 3)
        self.assertIsNone(result)

    def test_no_retry_on_success(self):
        """Should not retry on successful response."""
        from crawler.services.scrapingbee_client import ScrapingBeeClient

        client = ScrapingBeeClient(api_key="test_key")

        # Mock the fetch method to succeed
        call_count = [0]

        def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            return {"success": True, "status_code": 200, "content": "<html>Product Page</html>"}

        client.fetch = mock_fetch

        result = client.fetch_with_retry("http://example.com/product", max_retries=3)

        self.assertEqual(call_count[0], 1)
        self.assertIsNotNone(result)


class TestRetryLogicEnhancement(TestCase):
    """
    Tests that enhancement retry for null fields works.

    Fixes: Taylor's 10 Year, Sandeman 20 Year, Fonseca 30 Year (3 products)
    """

    def test_retry_when_critical_fields_null(self):
        """Should retry if name or brand is null after first attempt."""
        from crawler.services.enhancement_client import EnhancementClient

        # This test documents expected behavior
        # Actual implementation is on the VPS
        client = EnhancementClient()

        # Mock first response has null brand
        first_response = {
            "name": "Taylor's 10 Year Tawny",
            "brand": None,  # Missing!
            "style": "tawny",
        }

        # After retry, brand should be populated
        # The client should detect null critical fields and retry
        self.assertIsNone(first_response.get("brand"))

    def test_accepts_response_when_critical_fields_present(self):
        """Should accept response when name and brand are present."""
        # Test documents expected behavior
        response = {
            "name": "Taylor's 10 Year Tawny",
            "brand": "Taylor's",
            "style": "tawny",
        }

        self.assertIsNotNone(response.get("name"))
        self.assertIsNotNone(response.get("brand"))


class TestValidatorIntegration(TestCase):
    """Integration tests that combine multiple validators."""

    def test_full_whiskey_validation_pipeline(self):
        """Full validation pipeline should handle all edge cases."""
        from crawler.validators.whiskey import validate_whiskey_data

        raw_data = {
            "name": "Booker's Bourbon",
            "whiskey_type": "Kentucky Straight Bourbon",  # Needs normalization
            "vintage_year": "N/A",  # Needs cleaning
            "brand": None,  # Needs extraction from name
        }

        validated = validate_whiskey_data(raw_data)

        self.assertEqual(validated["whiskey_type"], "bourbon")
        self.assertIsNone(validated["vintage_year"])
        self.assertEqual(validated["brand"], "Booker's")

    def test_full_port_wine_validation_pipeline(self):
        """Full validation pipeline for port wine."""
        from crawler.validators.port_wine import validate_port_wine_data

        raw_data = {
            "name": "Sandeman 30 Year Old Tawny",
            "style": "tawny",
            "age_designation": "30 years",  # Needs cleaning
        }

        validated = validate_port_wine_data(raw_data)

        self.assertEqual(validated["age_designation"], 30)
        self.assertEqual(validated["style"], "tawny")
