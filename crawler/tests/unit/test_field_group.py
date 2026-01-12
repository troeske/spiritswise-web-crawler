"""
Unit tests for FieldGroup Model (V3 Architecture).

Task 1.2: Create FieldGroup Model

Spec Reference: specs/ENRICHMENT_PIPELINE_V3_SPEC.md Section 6.2

TDD Approach: Tests written FIRST, implementation follows.

FieldGroup defines field groups for ECP (Enrichment Completion Percentage) calculation:
- Groups like "tasting_nose", "cask_info", "whiskey_details"
- List of fields in each group
- Used to calculate ECP by group
"""

import uuid
from django.test import TestCase
from django.db import IntegrityError
from crawler.models import (
    ProductTypeConfig,
    FieldGroup,
)


class FieldGroupModelTests(TestCase):
    """Tests for FieldGroup model."""

    def setUp(self):
        """Create ProductTypeConfig for FK relationship."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_create_field_group_minimal(self):
        """Test creating FieldGroup with minimal fields."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="tasting_nose",
            display_name="Tasting Profile - Nose",
            fields=["nose_description", "primary_aromas", "primary_intensity"],
        )

        self.assertIsInstance(group.id, uuid.UUID)
        self.assertEqual(group.product_type_config, self.product_type_config)
        self.assertEqual(group.group_key, "tasting_nose")
        self.assertEqual(group.display_name, "Tasting Profile - Nose")
        self.assertEqual(group.fields, ["nose_description", "primary_aromas", "primary_intensity"])
        self.assertEqual(group.sort_order, 0)  # Default
        self.assertTrue(group.is_active)  # Default

    def test_field_group_uuid_primary_key(self):
        """Test that FieldGroup uses UUID primary key."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="basic_info",
            display_name="Basic Product Info",
            fields=["name", "brand"],
        )
        self.assertIsInstance(group.id, uuid.UUID)

    def test_field_group_unique_together_constraint(self):
        """Test unique_together constraint on (product_type_config, group_key)."""
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="cask_info",
            display_name="Cask Info",
            fields=["primary_cask"],
        )

        # Same group_key for same product type should fail
        with self.assertRaises(IntegrityError):
            FieldGroup.objects.create(
                product_type_config=self.product_type_config,
                group_key="cask_info",
                display_name="Cask Info Duplicate",
                fields=["finishing_cask"],
            )

    def test_field_group_same_key_different_product_type(self):
        """Test that same group_key can exist for different product types."""
        port_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

        # Create cask_info for whiskey
        whiskey_group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="cask_info",
            display_name="Cask Info",
            fields=["primary_cask", "finishing_cask"],
        )

        # Create cask_info for port wine - should work
        port_group = FieldGroup.objects.create(
            product_type_config=port_config,
            group_key="cask_info",
            display_name="Aging/Cask Info",
            fields=["aging_vessel"],
        )

        self.assertEqual(whiskey_group.group_key, port_group.group_key)
        self.assertNotEqual(whiskey_group.product_type_config, port_group.product_type_config)

    def test_field_group_ordering_by_sort_order(self):
        """Test that FieldGroups are ordered by sort_order."""
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="basic_info",
            display_name="Basic Product Info",
            fields=["name"],
            sort_order=1,
        )
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="tasting_nose",
            display_name="Tasting Nose",
            fields=["nose_description"],
            sort_order=3,
        )
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="tasting_palate",
            display_name="Tasting Palate",
            fields=["palate_description"],
            sort_order=2,
        )

        groups = list(FieldGroup.objects.filter(
            product_type_config=self.product_type_config
        ))

        self.assertEqual(groups[0].group_key, "basic_info")
        self.assertEqual(groups[1].group_key, "tasting_palate")
        self.assertEqual(groups[2].group_key, "tasting_nose")

    def test_field_group_fields_as_list(self):
        """Test that fields is stored as JSON list."""
        fields = [
            "nose_description",
            "primary_aromas",
            "primary_intensity",
            "secondary_aromas",
            "aroma_evolution",
        ]

        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="tasting_nose",
            display_name="Tasting Profile - Nose",
            fields=fields,
        )

        self.assertEqual(group.fields, fields)
        self.assertEqual(len(group.fields), 5)
        self.assertIn("primary_aromas", group.fields)

    def test_field_group_is_active_default(self):
        """Test default is_active=True."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="test_group",
            display_name="Test",
            fields=[],
        )
        self.assertTrue(group.is_active)

    def test_field_group_deactivation(self):
        """Test deactivating a field group."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="deprecated_group",
            display_name="Deprecated",
            fields=["old_field"],
            is_active=False,
        )
        self.assertFalse(group.is_active)

    def test_field_group_delete_cascade(self):
        """Test that FieldGroups are deleted when ProductTypeConfig is deleted."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="test_group",
            display_name="Test",
            fields=[],
        )
        group_id = group.id

        self.product_type_config.delete()

        self.assertFalse(FieldGroup.objects.filter(id=group_id).exists())

    def test_field_group_str_representation(self):
        """Test string representation of FieldGroup."""
        group = FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="tasting_nose",
            display_name="Tasting Profile - Nose",
            fields=[],
        )

        str_repr = str(group)
        self.assertIn("tasting_nose", str_repr)

    def test_field_group_related_name(self):
        """Test accessing field groups via ProductTypeConfig."""
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="group1",
            display_name="Group 1",
            fields=["field1"],
        )
        FieldGroup.objects.create(
            product_type_config=self.product_type_config,
            group_key="group2",
            display_name="Group 2",
            fields=["field2"],
        )

        # Access via related name
        groups = self.product_type_config.field_groups.all()
        self.assertEqual(groups.count(), 2)


class FieldGroupWhiskeySpecTests(TestCase):
    """Tests for Whiskey field groups matching V3 spec."""

    def setUp(self):
        """Create ProductTypeConfig for whiskey."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="whiskey",
            display_name="Whiskey",
        )

    def test_whiskey_field_groups_per_spec(self):
        """Test creating all whiskey field groups per V3 spec Appendix B."""
        groups_data = [
            {
                "key": "basic_product_info",
                "name": "Basic Product Info",
                "fields": ["product_type", "category", "abv", "volume_ml", "description",
                          "age_statement", "country", "region", "bottler"],
                "sort_order": 1,
            },
            {
                "key": "tasting_appearance",
                "name": "Tasting Profile - Appearance",
                "fields": ["color_description", "color_intensity", "clarity", "viscosity"],
                "sort_order": 2,
            },
            {
                "key": "tasting_nose",
                "name": "Tasting Profile - Nose",
                "fields": ["nose_description", "primary_aromas", "primary_intensity",
                          "secondary_aromas", "aroma_evolution"],
                "sort_order": 3,
            },
            {
                "key": "tasting_palate",
                "name": "Tasting Profile - Palate",
                "fields": ["initial_taste", "mid_palate_evolution", "palate_flavors",
                          "palate_description", "flavor_intensity", "complexity", "mouthfeel"],
                "sort_order": 4,
            },
            {
                "key": "tasting_finish",
                "name": "Tasting Profile - Finish",
                "fields": ["finish_length", "warmth", "dryness", "finish_flavors",
                          "finish_evolution", "finish_description", "final_notes"],
                "sort_order": 5,
            },
            {
                "key": "tasting_overall",
                "name": "Tasting Profile - Overall",
                "fields": ["balance", "overall_complexity", "uniqueness", "drinkability",
                          "price_quality_ratio", "experience_level", "serving_recommendation",
                          "food_pairings"],
                "sort_order": 6,
            },
            {
                "key": "cask_info",
                "name": "Cask Info",
                "fields": ["primary_cask", "finishing_cask", "wood_type", "cask_treatment",
                          "maturation_notes"],
                "sort_order": 7,
            },
            {
                "key": "whiskey_details",
                "name": "Whiskey-Specific Details",
                "fields": ["whiskey_type", "distillery", "mash_bill", "cask_strength",
                          "single_cask", "cask_number", "vintage_year", "bottling_year",
                          "batch_number", "peated", "peat_level", "peat_ppm",
                          "natural_color", "non_chill_filtered"],
                "sort_order": 8,
            },
        ]

        for data in groups_data:
            FieldGroup.objects.create(
                product_type_config=self.product_type_config,
                group_key=data["key"],
                display_name=data["name"],
                fields=data["fields"],
                sort_order=data["sort_order"],
            )

        # Verify all groups created
        groups = FieldGroup.objects.filter(product_type_config=self.product_type_config)
        self.assertEqual(groups.count(), 8)

        # Verify total field count (59 per spec)
        total_fields = sum(len(g.fields) for g in groups)
        self.assertEqual(total_fields, 59)


class FieldGroupPortWineSpecTests(TestCase):
    """Tests for Port Wine field groups matching V3 spec."""

    def setUp(self):
        """Create ProductTypeConfig for port wine."""
        self.product_type_config = ProductTypeConfig.objects.create(
            product_type="port_wine",
            display_name="Port Wine",
        )

    def test_port_wine_field_groups_per_spec(self):
        """Test creating port wine field groups per V3 spec Appendix D."""
        groups_data = [
            {
                "key": "basic_product_info",
                "name": "Basic Product Info",
                "fields": ["product_type", "style", "abv", "volume_ml", "description",
                          "country", "region", "bottler"],
                "sort_order": 1,
            },
            {
                "key": "tasting_appearance",
                "name": "Tasting Profile - Appearance",
                "fields": ["color_description", "color_intensity", "clarity", "viscosity"],
                "sort_order": 2,
            },
            {
                "key": "tasting_nose",
                "name": "Tasting Profile - Nose",
                "fields": ["nose_description", "primary_aromas", "primary_intensity",
                          "secondary_aromas", "aroma_evolution"],
                "sort_order": 3,
            },
            {
                "key": "tasting_palate",
                "name": "Tasting Profile - Palate",
                "fields": ["initial_taste", "mid_palate_evolution", "palate_flavors",
                          "palate_description", "flavor_intensity", "complexity", "mouthfeel"],
                "sort_order": 4,
            },
            {
                "key": "tasting_finish",
                "name": "Tasting Profile - Finish",
                "fields": ["finish_length", "warmth", "dryness", "finish_flavors",
                          "finish_evolution", "finish_description", "final_notes"],
                "sort_order": 5,
            },
            {
                "key": "tasting_overall",
                "name": "Tasting Profile - Overall",
                "fields": ["balance", "overall_complexity", "uniqueness", "drinkability",
                          "price_quality_ratio", "experience_level", "serving_recommendation",
                          "food_pairings"],
                "sort_order": 6,
            },
            {
                "key": "cask_info",
                "name": "Aging/Cask Info",
                "fields": ["aging_vessel", "maturation_notes"],
                "sort_order": 7,
            },
            {
                "key": "port_details",
                "name": "Port Wine-Specific Details",
                "fields": ["indication_age", "harvest_year", "bottling_year", "producer_house",
                          "quinta", "douro_subregion", "grape_varieties", "decanting_required",
                          "drinking_window"],
                "sort_order": 8,
            },
        ]

        for data in groups_data:
            FieldGroup.objects.create(
                product_type_config=self.product_type_config,
                group_key=data["key"],
                display_name=data["name"],
                fields=data["fields"],
                sort_order=data["sort_order"],
            )

        # Verify all groups created
        groups = FieldGroup.objects.filter(product_type_config=self.product_type_config)
        self.assertEqual(groups.count(), 8)

        # Verify total field count (50 per spec)
        total_fields = sum(len(g.fields) for g in groups)
        self.assertEqual(total_fields, 50)
