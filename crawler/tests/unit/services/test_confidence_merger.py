"""
Unit tests for ConfidenceBasedMerger Service.

Task 1.2: Confidence-Based Merger

Spec Reference: specs/GENERIC_SEARCH_V3_SPEC.md Section 2.4 (COMP-LEARN-004)

Tests verify:
- Higher confidence wins for field replacement
- Array fields append unique items
- Dict fields merge recursively
- None value handling
- Field enrichment tracking
"""

from django.test import TestCase

from crawler.services.confidence_merger import ConfidenceBasedMerger


class ConfidenceBasedMergerHigherConfidenceWinsTests(TestCase):
    """Tests for higher confidence winning behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_higher_confidence_replaces_lower(self):
        """Test that higher confidence value replaces lower confidence value."""
        existing_data = {"name": "Old Name", "brand": "Brand A"}
        existing_confidences = {"name": 0.70, "brand": 0.85}

        new_data = {"name": "New Name", "brand": "Brand B"}
        new_confidence = 0.90

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Both should be replaced since new_confidence (0.90) > existing
        self.assertEqual(merged["name"], "New Name")
        self.assertEqual(merged["brand"], "Brand B")
        self.assertIn("name", enriched_fields)
        self.assertIn("brand", enriched_fields)

    def test_lower_confidence_does_not_replace_higher(self):
        """Test that lower confidence value does not replace higher confidence value."""
        existing_data = {"name": "Official Name", "abv": "46%"}
        existing_confidences = {"name": 0.95, "abv": 0.95}

        new_data = {"name": "Review Name", "abv": "45%"}
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Neither should be replaced
        self.assertEqual(merged["name"], "Official Name")
        self.assertEqual(merged["abv"], "46%")
        self.assertEqual(len(enriched_fields), 0)

    def test_equal_confidence_does_not_replace(self):
        """Test that equal confidence value does not replace existing."""
        existing_data = {"name": "Existing Name"}
        existing_confidences = {"name": 0.80}

        new_data = {"name": "Equal Confidence Name"}
        new_confidence = 0.80

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should not replace on equal confidence
        self.assertEqual(merged["name"], "Existing Name")
        self.assertNotIn("name", enriched_fields)

    def test_new_field_added_regardless_of_confidence(self):
        """Test that new fields are always added when not present in existing."""
        existing_data = {"name": "Whiskey Name"}
        existing_confidences = {"name": 0.95}

        new_data = {"description": "A fine whiskey", "abv": "43%"}
        new_confidence = 0.60

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # New fields should be added
        self.assertEqual(merged["description"], "A fine whiskey")
        self.assertEqual(merged["abv"], "43%")
        self.assertIn("description", enriched_fields)
        self.assertIn("abv", enriched_fields)


class ConfidenceBasedMergerArrayMergeTests(TestCase):
    """Tests for array field merging behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_array_append_unique_when_new_confidence_lower(self):
        """Test arrays append unique items when new confidence is lower."""
        existing_data = {"primary_aromas": ["vanilla", "oak"]}
        existing_confidences = {"primary_aromas": 0.85}

        new_data = {"primary_aromas": ["honey", "vanilla", "spice"]}
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should contain all unique items
        aromas = merged["primary_aromas"]
        self.assertIn("vanilla", aromas)
        self.assertIn("oak", aromas)
        self.assertIn("honey", aromas)
        self.assertIn("spice", aromas)
        # No duplicates
        self.assertEqual(len(aromas), 4)
        # Field was enriched (appended new items)
        self.assertIn("primary_aromas", enriched_fields)

    def test_array_no_append_when_no_new_items(self):
        """Test arrays don't track enrichment when no new unique items."""
        existing_data = {"awards": ["Gold 2023", "Silver 2022"]}
        existing_confidences = {"awards": 0.85}

        new_data = {"awards": ["Gold 2023"]}  # Already exists
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should have same items
        self.assertEqual(len(merged["awards"]), 2)
        # Not tracked as enriched since no new items
        self.assertNotIn("awards", enriched_fields)

    def test_array_replaced_when_higher_confidence(self):
        """Test arrays are replaced entirely when new confidence is higher."""
        existing_data = {"secondary_aromas": ["old1", "old2"]}
        existing_confidences = {"secondary_aromas": 0.70}

        new_data = {"secondary_aromas": ["new1", "new2", "new3"]}
        new_confidence = 0.90

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should be completely replaced
        self.assertEqual(merged["secondary_aromas"], ["new1", "new2", "new3"])
        self.assertIn("secondary_aromas", enriched_fields)


class ConfidenceBasedMergerDictMergeTests(TestCase):
    """Tests for dict field recursive merging behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_dict_merge_recursive_when_lower_confidence(self):
        """Test dicts merge recursively when new confidence is lower."""
        existing_data = {
            "tasting_profile": {
                "nose": "vanilla",
                "palate": "oak",
            }
        }
        existing_confidences = {"tasting_profile": 0.85}

        new_data = {
            "tasting_profile": {
                "finish": "long and spicy",
                "complexity": "high",
            }
        }
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should have merged keys
        profile = merged["tasting_profile"]
        self.assertEqual(profile["nose"], "vanilla")
        self.assertEqual(profile["palate"], "oak")
        self.assertEqual(profile["finish"], "long and spicy")
        self.assertEqual(profile["complexity"], "high")
        self.assertIn("tasting_profile", enriched_fields)

    def test_dict_not_merge_when_existing_has_key(self):
        """Test dict keys are not overwritten when they already exist (lower confidence)."""
        existing_data = {
            "metadata": {
                "source": "producer_site",
                "quality": "high",
            }
        }
        existing_confidences = {"metadata": 0.90}

        new_data = {
            "metadata": {
                "source": "review_site",  # Should not overwrite
                "extra_info": "new data",  # Should add
            }
        }
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        metadata = merged["metadata"]
        self.assertEqual(metadata["source"], "producer_site")  # Not overwritten
        self.assertEqual(metadata["quality"], "high")
        self.assertEqual(metadata["extra_info"], "new data")  # Added
        self.assertIn("metadata", enriched_fields)

    def test_dict_replaced_when_higher_confidence(self):
        """Test dicts are replaced entirely when new confidence is higher."""
        existing_data = {
            "price_info": {
                "price": 50,
                "currency": "USD",
            }
        }
        existing_confidences = {"price_info": 0.60}

        new_data = {
            "price_info": {
                "price": 55,
                "currency": "EUR",
                "retail_price": 60,
            }
        }
        new_confidence = 0.85

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # Should be completely replaced
        price_info = merged["price_info"]
        self.assertEqual(price_info["price"], 55)
        self.assertEqual(price_info["currency"], "EUR")
        self.assertEqual(price_info["retail_price"], 60)
        self.assertNotIn("USD", str(price_info))


class ConfidenceBasedMergerNoneHandlingTests(TestCase):
    """Tests for None value handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_none_in_new_data_does_not_overwrite(self):
        """Test None values in new data do not overwrite existing values."""
        existing_data = {"name": "Whiskey Name", "abv": "46%"}
        existing_confidences = {"name": 0.80, "abv": 0.80}

        new_data = {"name": None, "description": "A description"}
        new_confidence = 0.90

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # name should not be overwritten by None
        self.assertEqual(merged["name"], "Whiskey Name")
        self.assertNotIn("name", enriched_fields)
        # description should be added
        self.assertEqual(merged["description"], "A description")

    def test_empty_string_does_not_overwrite(self):
        """Test empty strings do not overwrite existing values."""
        existing_data = {"brand": "Brand Name"}
        existing_confidences = {"brand": 0.70}

        new_data = {"brand": "", "category": "Single Malt"}
        new_confidence = 0.90

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        self.assertEqual(merged["brand"], "Brand Name")
        self.assertNotIn("brand", enriched_fields)
        self.assertEqual(merged["category"], "Single Malt")

    def test_empty_list_does_not_overwrite(self):
        """Test empty lists do not overwrite existing values."""
        existing_data = {"awards": ["Gold 2023"]}
        existing_confidences = {"awards": 0.80}

        new_data = {"awards": []}
        new_confidence = 0.95

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        self.assertEqual(merged["awards"], ["Gold 2023"])
        self.assertNotIn("awards", enriched_fields)

    def test_existing_none_can_be_filled(self):
        """Test None values in existing data can be filled by new data."""
        existing_data = {"name": "Whiskey", "description": None}
        existing_confidences = {"name": 0.90, "description": 0.0}

        new_data = {"description": "A fine whiskey"}
        new_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        self.assertEqual(merged["description"], "A fine whiskey")
        self.assertIn("description", enriched_fields)


class ConfidenceBasedMergerTypeHandlingTests(TestCase):
    """Tests for different field type handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_integer_field_handling(self):
        """Test integer fields are handled correctly."""
        existing_data = {"age_statement": 12, "volume_ml": 700}
        existing_confidences = {"age_statement": 0.70, "volume_ml": 0.90}

        new_data = {"age_statement": 18, "volume_ml": 750}
        new_confidence = 0.85

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        # age_statement should be updated (0.85 > 0.70)
        self.assertEqual(merged["age_statement"], 18)
        # volume_ml should not (0.85 < 0.90)
        self.assertEqual(merged["volume_ml"], 700)

    def test_float_field_handling(self):
        """Test float fields are handled correctly."""
        existing_data = {"abv_numeric": 46.5}
        existing_confidences = {"abv_numeric": 0.75}

        new_data = {"abv_numeric": 46.8}
        new_confidence = 0.80

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        self.assertEqual(merged["abv_numeric"], 46.8)
        self.assertIn("abv_numeric", enriched_fields)

    def test_boolean_field_handling(self):
        """Test boolean fields are handled correctly."""
        existing_data = {"is_limited_edition": False}
        existing_confidences = {"is_limited_edition": 0.70}

        new_data = {"is_limited_edition": True}
        new_confidence = 0.85

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        self.assertEqual(merged["is_limited_edition"], True)
        self.assertIn("is_limited_edition", enriched_fields)


class ConfidenceBasedMergerConfidenceTrackingTests(TestCase):
    """Tests for updated confidence tracking."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_updated_confidences_returned(self):
        """Test that updated confidences dict is returned."""
        existing_data = {"name": "Whiskey", "brand": "Brand"}
        existing_confidences = {"name": 0.70, "brand": 0.90}

        new_data = {"name": "New Whiskey", "description": "A description"}
        new_confidence = 0.85

        merged, enriched_fields = self.merger.merge(
            existing_data=existing_data,
            existing_confidences=existing_confidences,
            new_data=new_data,
            new_confidence=new_confidence,
        )

        updated_confidences = self.merger.get_updated_confidences()

        # name was updated, should have new confidence
        self.assertEqual(updated_confidences["name"], 0.85)
        # brand was not updated, should keep old confidence
        self.assertEqual(updated_confidences["brand"], 0.90)
        # description is new, should have new confidence
        self.assertEqual(updated_confidences["description"], 0.85)


class ConfidenceBasedMergerIntegrationTests(TestCase):
    """Integration tests with real extraction data."""

    def setUp(self):
        """Set up test fixtures."""
        self.merger = ConfidenceBasedMerger()

    def test_merge_producer_page_with_review_site(self):
        """Test merging producer page (0.85) with review site (0.70) data.

        Spec Reference: Task 1.2.3
        Producer page data should be retained when review site has lower confidence.
        """
        # Data from producer page (high confidence)
        producer_data = {
            "name": "GlenAllachie 15 Year Old",
            "brand": "GlenAllachie",
            "producer": "GlenAllachie Distillers Co. Ltd",
            "country": "Scotland",
            "region": "Speyside",
            "abv": "46%",
            "volume_ml": 700,
            "description": "A Speyside single malt matured in a combination of PX and Oloroso sherry casks.",
            "primary_cask": "Sherry",
            "age_statement": 15,
        }
        producer_confidences = {field: 0.85 for field in producer_data.keys()}

        # Data from review site (lower confidence)
        review_data = {
            "name": "GlenAllachie 15yr",  # Slightly different name
            "brand": "Glenallachie Distillery",  # Slightly different
            "description": "Great whisky from Speyside.",  # Less detailed
            "nose_description": "Rich sherry, dried fruits, chocolate",
            "palate_description": "Full bodied, Christmas cake, spice",
            "finish_description": "Long, warm, lingering",
            "primary_aromas": ["sherry", "dried fruits", "chocolate"],
            "awards": ["Gold - IWSC 2023"],
        }
        review_confidence = 0.70

        merged, enriched_fields = self.merger.merge(
            existing_data=producer_data,
            existing_confidences=producer_confidences,
            new_data=review_data,
            new_confidence=review_confidence,
        )

        # Producer data should be retained (higher confidence)
        self.assertEqual(merged["name"], "GlenAllachie 15 Year Old")
        self.assertEqual(merged["brand"], "GlenAllachie")
        self.assertIn("PX and Oloroso", merged["description"])

        # Review site data should be added for new fields
        self.assertEqual(merged["nose_description"], "Rich sherry, dried fruits, chocolate")
        self.assertEqual(merged["palate_description"], "Full bodied, Christmas cake, spice")
        self.assertEqual(merged["finish_description"], "Long, warm, lingering")
        self.assertEqual(merged["primary_aromas"], ["sherry", "dried fruits", "chocolate"])
        self.assertEqual(merged["awards"], ["Gold - IWSC 2023"])

        # Check enriched fields are tracked correctly
        self.assertIn("nose_description", enriched_fields)
        self.assertIn("palate_description", enriched_fields)
        self.assertIn("finish_description", enriched_fields)
        self.assertIn("primary_aromas", enriched_fields)
        self.assertIn("awards", enriched_fields)
        # Producer fields should not be in enriched (not changed)
        self.assertNotIn("name", enriched_fields)
        self.assertNotIn("brand", enriched_fields)
        self.assertNotIn("description", enriched_fields)

    def test_merge_review_sites_accumulates_arrays(self):
        """Test merging multiple review sites accumulates array fields."""
        # Initial data with some awards
        initial_data = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "awards": ["Gold - SF World Spirits 2022"],
        }
        initial_confidences = {"name": 0.85, "brand": 0.85, "awards": 0.75}

        # First review site
        review1_data = {
            "awards": ["Gold - SF World Spirits 2022", "Best in Category - WWA 2023"],
            "primary_aromas": ["heather", "honey"],
        }
        review1_confidence = 0.70

        merged, _ = self.merger.merge(
            existing_data=initial_data,
            existing_confidences=initial_confidences,
            new_data=review1_data,
            new_confidence=review1_confidence,
        )
        updated_confidences = self.merger.get_updated_confidences()

        # Awards should have unique items from both
        self.assertIn("Gold - SF World Spirits 2022", merged["awards"])
        self.assertIn("Best in Category - WWA 2023", merged["awards"])
        self.assertEqual(len(merged["awards"]), 2)  # No duplicates

        # Second review site
        review2_data = {
            "awards": ["Silver - IWSC 2023"],
            "primary_aromas": ["smoke", "honey"],  # honey is duplicate
        }
        review2_confidence = 0.70

        merged2, _ = self.merger.merge(
            existing_data=merged,
            existing_confidences=updated_confidences,
            new_data=review2_data,
            new_confidence=review2_confidence,
        )

        # All awards accumulated
        self.assertEqual(len(merged2["awards"]), 3)
        self.assertIn("Silver - IWSC 2023", merged2["awards"])

        # Aromas accumulated without duplicates
        aromas = merged2["primary_aromas"]
        self.assertIn("heather", aromas)
        self.assertIn("honey", aromas)
        self.assertIn("smoke", aromas)
        self.assertEqual(aromas.count("honey"), 1)  # No duplicate honey
