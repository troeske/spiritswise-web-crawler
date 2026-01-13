"""
Unit tests for ProductMatchValidator.

Task 1.1: Product Match Validator

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 5.2 (FEAT-002)

Tests verify:
- Level 1: Brand matching (overlap, mismatch, empty cases)
- Level 2: Product type keywords (bourbon vs rye, single malt vs blended)
- Level 3: Name token overlap (>= 30% threshold)
- Full validation pipeline
"""

from django.test import TestCase


class BrandMatchingTests(TestCase):
    """Tests for Level 1: Brand matching validation."""

    def test_exact_brand_match(self):
        """Test exact brand name match returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("Buffalo Trace", "Buffalo Trace")

        self.assertTrue(is_match)
        self.assertIn("brand_overlap", reason)

    def test_brand_overlap_target_in_extracted(self):
        """Test target brand contained in extracted brand returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("Buffalo Trace", "Buffalo Trace Distillery")

        self.assertTrue(is_match)
        self.assertIn("brand_overlap", reason)

    def test_brand_overlap_extracted_in_target(self):
        """Test extracted brand contained in target brand returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("Buffalo Trace Distillery", "Buffalo Trace")

        self.assertTrue(is_match)
        self.assertIn("brand_overlap", reason)

    def test_brand_mismatch(self):
        """Test mismatched brands return False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("Buffalo Trace", "Wild Turkey")

        self.assertFalse(is_match)
        self.assertIn("brand_mismatch", reason)
        self.assertIn("Buffalo Trace", reason)
        self.assertIn("Wild Turkey", reason)

    def test_both_brands_empty(self):
        """Test both brands empty returns True (allowed)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("", "")

        self.assertTrue(is_match)
        self.assertEqual(reason, "both_empty")

    def test_both_brands_none(self):
        """Test both brands None returns True (allowed)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match(None, None)

        self.assertTrue(is_match)
        self.assertEqual(reason, "both_empty")

    def test_target_empty_extracted_has_value(self):
        """Test target empty with extracted having value returns True (allowed)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("", "Buffalo Trace")

        self.assertTrue(is_match)
        self.assertEqual(reason, "one_empty_allowed")

    def test_target_has_value_extracted_empty(self):
        """Test target has value with extracted empty returns True (allowed)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("Buffalo Trace", "")

        self.assertTrue(is_match)
        self.assertEqual(reason, "one_empty_allowed")

    def test_brand_case_insensitive(self):
        """Test brand matching is case insensitive."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("BUFFALO TRACE", "buffalo trace")

        self.assertTrue(is_match)
        self.assertIn("brand_overlap", reason)

    def test_brand_whitespace_handling(self):
        """Test brand matching handles whitespace."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_brand_match("  Buffalo Trace  ", "Buffalo Trace")

        self.assertTrue(is_match)
        self.assertIn("brand_overlap", reason)


class ProductTypeKeywordTests(TestCase):
    """Tests for Level 2: Product type keyword validation."""

    def test_bourbon_vs_rye_mismatch(self):
        """Test bourbon target with rye extracted returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Frank August Bourbon", "category": "Bourbon"}
        extracted_data = {"name": "Frank August Rye", "category": "Rye Whiskey"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_bourbon_matches_bourbon(self):
        """Test bourbon target with bourbon extracted returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Buffalo Trace Bourbon", "category": "Bourbon"}
        extracted_data = {"name": "Buffalo Trace Kentucky Straight Bourbon", "category": "Bourbon Whiskey"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertTrue(is_match)
        self.assertIn("keywords_compatible", reason)

    def test_single_malt_vs_blended_mismatch(self):
        """Test single malt target with blended extracted returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Glenfiddich 12 Year", "category": "Single Malt Scotch"}
        extracted_data = {"name": "Johnnie Walker Black Label", "category": "Blended Scotch"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_single_malt_matches_single_malt(self):
        """Test single malt target with single malt extracted returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Glenfiddich 12 Year", "category": "Single Malt Scotch"}
        extracted_data = {"name": "Glenfiddich 12 Year Old", "category": "Single Malt Scotch Whisky"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertTrue(is_match)
        self.assertIn("keywords_compatible", reason)

    def test_scotch_vs_irish_mismatch(self):
        """Test scotch target with irish extracted returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Macallan 12", "category": "Scotch Whisky"}
        extracted_data = {"name": "Jameson Original", "category": "Irish Whiskey"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_vintage_vs_lbv_mismatch(self):
        """Test vintage port target with LBV extracted returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Taylor's Vintage Port 2000", "category": "Vintage Port"}
        extracted_data = {"name": "Taylor's LBV", "category": "Late Bottled Vintage Port"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_tawny_vs_ruby_mismatch(self):
        """Test tawny port target with ruby extracted returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Graham's 20 Year Tawny", "category": "Tawny Port"}
        extracted_data = {"name": "Graham's Fine Ruby", "category": "Ruby Port"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_no_conflicting_keywords(self):
        """Test products with no conflicting keywords returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Generic Whiskey", "description": "A fine spirit"}
        extracted_data = {"name": "Generic Whiskey", "description": "Smooth and rich"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertTrue(is_match)
        self.assertIn("keywords_compatible", reason)

    def test_keyword_in_name_field(self):
        """Test keyword detection in name field."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Frank August Small Batch Bourbon"}
        extracted_data = {"name": "Frank August Rye Whiskey"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_keyword_in_description_field(self):
        """Test keyword detection in description field."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {"name": "Frank August", "description": "A premium bourbon whiskey"}
        extracted_data = {"name": "Frank August", "description": "A smooth rye whiskey"}

        is_match, reason = validator._validate_product_type_keywords(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)


class NameTokenOverlapTests(TestCase):
    """Tests for Level 3: Name token overlap validation."""

    def test_exact_name_match(self):
        """Test exact name match returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap(
            "Buffalo Trace Kentucky Straight Bourbon",
            "Buffalo Trace Kentucky Straight Bourbon"
        )

        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)

    def test_high_overlap_ratio(self):
        """Test high overlap ratio returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap(
            "Buffalo Trace Bourbon",
            "Buffalo Trace Kentucky Straight Bourbon Whiskey"
        )

        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)

    def test_low_overlap_ratio_rejected(self):
        """Test low overlap ratio returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap(
            "Buffalo Trace Bourbon",
            "Wild Turkey Kentucky Spirit"
        )

        self.assertFalse(is_match)
        self.assertIn("name_mismatch", reason)
        self.assertIn("overlap", reason)

    def test_stopwords_ignored(self):
        """Test stopwords are ignored in tokenization."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # "The" and "of" should be ignored
        is_match, reason = validator._validate_name_overlap(
            "The Macallan 12 Year of Oak",
            "Macallan 12 Year Oak"
        )

        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)

    def test_short_tokens_ignored(self):
        """Test tokens shorter than MIN_TOKEN_LENGTH are ignored."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # "12", "yr" should be ignored (less than 3 chars)
        is_match, reason = validator._validate_name_overlap(
            "Macallan 12 yr",
            "Macallan yr 12"
        )

        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)

    def test_empty_target_name(self):
        """Test empty target name returns True (insufficient tokens)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap("", "Buffalo Trace Bourbon")

        self.assertTrue(is_match)
        self.assertEqual(reason, "insufficient_tokens")

    def test_empty_extracted_name(self):
        """Test empty extracted name returns True (insufficient tokens)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap("Buffalo Trace Bourbon", "")

        self.assertTrue(is_match)
        self.assertEqual(reason, "insufficient_tokens")

    def test_both_names_empty(self):
        """Test both names empty returns True (insufficient tokens)."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap("", "")

        self.assertTrue(is_match)
        self.assertEqual(reason, "insufficient_tokens")

    def test_overlap_at_threshold(self):
        """Test overlap at exactly 30% threshold returns True."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: 3 significant tokens: "buffalo", "trace", "bourbon"
        # Extracted: 10 significant tokens with 3 overlapping = 30%
        # Tokens: "buffalo", "trace", "bourbon" + 7 unique = 10 total
        # Overlap: 3/10 = 30%
        is_match, reason = validator._validate_name_overlap(
            "Buffalo Trace Bourbon",
            "Buffalo Trace Bourbon Limited Release Special Reserve Collection"
        )

        # Overlap tokens: "buffalo", "trace", "bourbon" (3 tokens)
        # Extracted tokens: "buffalo", "trace", "bourbon", "limited", "release",
        #                   "special", "reserve", "collection" (8 tokens)
        # Max = 8, overlap = 3, ratio = 3/8 = 0.375 > 0.30
        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)

    def test_overlap_below_threshold_rejected(self):
        """Test overlap below 30% threshold returns False."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: 3 significant tokens: "buffalo", "trace", "bourbon"
        # Extracted: 10+ tokens with only 1-2 overlapping = <30%
        is_match, reason = validator._validate_name_overlap(
            "Buffalo Trace Bourbon",
            "Wild Turkey Premium Kentucky American Straight Whiskey Reserve Edition"
        )

        # This should fail because overlap is too low
        self.assertFalse(is_match)
        self.assertIn("name_mismatch", reason)

    def test_case_insensitive_matching(self):
        """Test name matching is case insensitive."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        is_match, reason = validator._validate_name_overlap(
            "BUFFALO TRACE BOURBON",
            "buffalo trace bourbon"
        )

        self.assertTrue(is_match)
        self.assertIn("name_overlap", reason)


class FullValidationPipelineTests(TestCase):
    """Tests for full validation pipeline combining all levels."""

    def test_all_levels_pass(self):
        """Test validation passes when all levels pass."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {
            "name": "Buffalo Trace Kentucky Straight Bourbon",
            "brand": "Buffalo Trace",
            "category": "Bourbon"
        }
        extracted_data = {
            "name": "Buffalo Trace Kentucky Straight Bourbon Whiskey",
            "brand": "Buffalo Trace Distillery",
            "category": "Bourbon Whiskey"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertTrue(is_match)
        self.assertIn("match", reason.lower())

    def test_fails_on_brand_mismatch(self):
        """Test validation fails when brand mismatch detected."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {
            "name": "Buffalo Trace Bourbon",
            "brand": "Buffalo Trace",
            "category": "Bourbon"
        }
        extracted_data = {
            "name": "Wild Turkey Bourbon",
            "brand": "Wild Turkey",
            "category": "Bourbon"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("brand", reason.lower())

    def test_fails_on_product_type_mismatch(self):
        """Test validation fails when product type mismatch detected."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {
            "name": "Frank August Small Batch Bourbon",
            "brand": "Frank August",
            "category": "Bourbon"
        }
        extracted_data = {
            "name": "Frank August Small Batch Rye",
            "brand": "Frank August",
            "category": "Rye Whiskey"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type", reason.lower())

    def test_fails_on_name_mismatch(self):
        """Test validation fails when name overlap is insufficient."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        target_data = {
            "name": "Buffalo Trace Bourbon",
            "brand": "Buffalo Trace",
            "category": "Bourbon"
        }
        extracted_data = {
            "name": "Woodford Reserve Double Oaked",
            "brand": "Buffalo Trace",  # Same brand but different product
            "category": "Bourbon"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("name", reason.lower())

    def test_validation_order_brand_first(self):
        """Test brand validation is checked first."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Brand mismatch, but also name and type would fail
        target_data = {
            "name": "Buffalo Trace Bourbon",
            "brand": "Buffalo Trace",
            "category": "Bourbon"
        }
        extracted_data = {
            "name": "Johnnie Walker Black Label",
            "brand": "Johnnie Walker",
            "category": "Blended Scotch"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        # Should fail on brand first
        self.assertIn("brand", reason.lower())


class IntegrationWithRealProductDataTests(TestCase):
    """Integration tests with real product data scenarios."""

    def test_frank_august_bourbon_vs_rye(self):
        """Test Frank August Bourbon vs Rye scenario from spec."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: Frank August Bourbon being enriched
        target_data = {
            "name": "Frank August Small Batch Bourbon",
            "brand": "Frank August",
            "category": "Kentucky Straight Bourbon",
            "description": "A smooth bourbon whiskey from Kentucky"
        }
        # Extracted: Data from Frank August Rye page (wrong product)
        extracted_data = {
            "name": "Frank August Small Batch Rye",
            "brand": "Frank August",
            "category": "Kentucky Straight Rye Whiskey",
            "description": "A spicy rye whiskey from Kentucky"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_glenallachie_single_malt_vs_blended(self):
        """Test GlenAllachie Single Malt vs Blended scenario."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: GlenAllachie Single Malt
        target_data = {
            "name": "GlenAllachie 12 Year Single Malt",
            "brand": "GlenAllachie",
            "category": "Single Malt Scotch Whisky",
            "description": "A rich single malt from Speyside"
        }
        # Extracted: Data from Blended whisky page (wrong product)
        extracted_data = {
            "name": "Famous Grouse Blended Scotch",
            "brand": "Famous Grouse",
            "category": "Blended Scotch Whisky",
            "description": "A blended scotch whisky"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        # Should fail on brand mismatch first
        self.assertIn("brand_mismatch", reason)

    def test_same_product_different_sources(self):
        """Test same product from different sources is accepted."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: Macallan 12 from one source
        target_data = {
            "name": "The Macallan 12 Year Old Sherry Oak",
            "brand": "The Macallan",
            "category": "Single Malt Scotch",
            "abv": "40%"
        }
        # Extracted: Same product from different source (review site)
        extracted_data = {
            "name": "Macallan 12 Sherry Oak Cask",
            "brand": "Macallan",
            "category": "Single Malt Scotch Whisky",
            "abv": "40%",
            "description": "Matured in sherry-seasoned oak casks"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertTrue(is_match)

    def test_port_wine_vintage_vs_lbv(self):
        """Test port wine Vintage vs LBV cross-contamination prevention."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: Taylor's Vintage Port 2000
        target_data = {
            "name": "Taylor's Vintage Port 2000",
            "brand": "Taylor's",
            "category": "Vintage Port",
            "description": "A declared vintage port from 2000"
        }
        # Extracted: Taylor's LBV (wrong product type)
        extracted_data = {
            "name": "Taylor's Late Bottled Vintage",
            "brand": "Taylor's",
            "category": "LBV Port",
            "description": "Late bottled vintage port"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)

    def test_port_wine_tawny_vs_ruby(self):
        """Test port wine Tawny vs Ruby cross-contamination prevention."""
        from crawler.services.product_match_validator import ProductMatchValidator

        validator = ProductMatchValidator()
        # Target: Graham's 20 Year Tawny
        target_data = {
            "name": "Graham's 20 Year Old Tawny Port",
            "brand": "Graham's",
            "category": "Tawny Port",
            "description": "20 year old tawny port"
        }
        # Extracted: Graham's Ruby (wrong product type)
        extracted_data = {
            "name": "Graham's Six Grapes Ruby Port",
            "brand": "Graham's",
            "category": "Ruby Port",
            "description": "Premium ruby port"
        }

        is_match, reason = validator.validate(target_data, extracted_data)

        self.assertFalse(is_match)
        self.assertIn("product_type_mismatch", reason)
