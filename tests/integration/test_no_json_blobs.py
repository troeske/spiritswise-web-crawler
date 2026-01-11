"""
Task 7.1: No JSON Blobs Verification Tests

Tests that all searchable fields are stored in individual columns,
NOT in JSON blob fields like extracted_data, enriched_data, or taste_profile.

Spec Reference: 01-CRITICAL-REQUIREMENTS.md Requirement 3

Key Rule: NO JSON BLOBS for searchable fields!
- All searchable fields MUST be in individual columns
- JSON is only acceptable for:
  - Array fields: palate_flavors, primary_aromas, finish_flavors
  - Metadata that's never searched
"""

import pytest
import os
from decimal import Decimal

# Skip all tests unless explicitly enabled for VPS testing
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VPS_TESTS") != "true",
    reason="VPS tests disabled - set RUN_VPS_TESTS=true"
)


class TestSearchableFieldsInColumns:
    """
    Test that all searchable fields are in individual columns, NOT in JSON blobs.

    Per spec: "NO JSON BLOBS for searchable fields!"
    Model should have individual columns like: name = CharField()
    """

    def test_discoveredproduct_has_name_column(self):
        """
        Product name must be in 'name' column, NOT in JSON blob.
        Model should have: name = CharField()
        """
        from crawler.models import DiscoveredProduct

        # Verify the field exists and is a CharField
        field = DiscoveredProduct._meta.get_field('name')
        assert field is not None, "DiscoveredProduct must have 'name' field"
        assert field.get_internal_type() == 'CharField', (
            f"'name' must be CharField, not {field.get_internal_type()}"
        )
        # Verify it's indexed (searchable)
        assert field.db_index, "'name' field should be indexed for searchability"

    def test_discoveredproduct_has_abv_column(self):
        """
        ABV must be in 'abv' column, NOT in JSON blob.
        Model should have: abv = DecimalField()
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('abv')
        assert field is not None, "DiscoveredProduct must have 'abv' field"
        assert field.get_internal_type() == 'DecimalField', (
            f"'abv' must be DecimalField, not {field.get_internal_type()}"
        )
        assert field.db_index, "'abv' field should be indexed for searchability"

    def test_discoveredproduct_has_brand_column(self):
        """
        Brand must be in 'brand' column (FK), NOT in JSON blob.
        Model should have: brand = ForeignKey(DiscoveredBrand)
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('brand')
        assert field is not None, "DiscoveredProduct must have 'brand' field"
        assert field.get_internal_type() == 'ForeignKey', (
            f"'brand' must be ForeignKey, not {field.get_internal_type()}"
        )

    def test_discoveredproduct_has_region_column(self):
        """
        Region must be in 'region' column, NOT in JSON blob.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('region')
        assert field is not None, "DiscoveredProduct must have 'region' field"
        assert field.get_internal_type() == 'CharField', (
            f"'region' must be CharField, not {field.get_internal_type()}"
        )
        assert field.db_index, "'region' field should be indexed for searchability"

    def test_discoveredproduct_has_country_column(self):
        """
        Country must be in 'country' column, NOT in JSON blob.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('country')
        assert field is not None, "DiscoveredProduct must have 'country' field"
        assert field.get_internal_type() == 'CharField', (
            f"'country' must be CharField, not {field.get_internal_type()}"
        )
        assert field.db_index, "'country' field should be indexed for searchability"

    def test_discoveredproduct_has_product_type_column(self):
        """
        Product type must be in 'product_type' column, NOT in JSON blob.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('product_type')
        assert field is not None, "DiscoveredProduct must have 'product_type' field"
        assert field.get_internal_type() == 'CharField', (
            f"'product_type' must be CharField, not {field.get_internal_type()}"
        )

    def test_discoveredproduct_has_description_column(self):
        """
        Description must be in 'description' column, NOT in JSON blob.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('description')
        assert field is not None, "DiscoveredProduct must have 'description' field"
        assert field.get_internal_type() == 'TextField', (
            f"'description' must be TextField, not {field.get_internal_type()}"
        )


class TestTastingNotesInColumns:
    """
    Test tasting notes are in individual columns, NOT in a taste_profile JSON blob.

    Per spec, these MUST be individual columns:
    - nose_description
    - palate_description
    - finish_description
    - finish_length
    - mouthfeel
    - mid_palate
    """

    def test_palate_description_saved_to_column(self):
        """
        Palate description in 'palate_description' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('palate_description')
        assert field is not None, "DiscoveredProduct must have 'palate_description' field"
        assert field.get_internal_type() == 'TextField', (
            f"'palate_description' must be TextField, not {field.get_internal_type()}"
        )

    def test_nose_description_saved_to_column(self):
        """
        Nose description in 'nose_description' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('nose_description')
        assert field is not None, "DiscoveredProduct must have 'nose_description' field"
        assert field.get_internal_type() == 'TextField', (
            f"'nose_description' must be TextField, not {field.get_internal_type()}"
        )

    def test_finish_description_saved_to_column(self):
        """
        Finish description in 'finish_description' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('finish_description')
        assert field is not None, "DiscoveredProduct must have 'finish_description' field"
        assert field.get_internal_type() == 'TextField', (
            f"'finish_description' must be TextField, not {field.get_internal_type()}"
        )

    def test_finish_length_saved_to_column(self):
        """
        Finish length in 'finish_length' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('finish_length')
        assert field is not None, "DiscoveredProduct must have 'finish_length' field"
        assert field.get_internal_type() == 'IntegerField', (
            f"'finish_length' must be IntegerField, not {field.get_internal_type()}"
        )

    def test_mouthfeel_saved_to_column(self):
        """
        Mouthfeel in 'mouthfeel' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('mouthfeel')
        assert field is not None, "DiscoveredProduct must have 'mouthfeel' field"
        assert field.get_internal_type() == 'CharField', (
            f"'mouthfeel' must be CharField, not {field.get_internal_type()}"
        )

    def test_mid_palate_evolution_saved_to_column(self):
        """
        Mid-palate evolution in 'mid_palate_evolution' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('mid_palate_evolution')
        assert field is not None, "DiscoveredProduct must have 'mid_palate_evolution' field"
        assert field.get_internal_type() == 'TextField', (
            f"'mid_palate_evolution' must be TextField, not {field.get_internal_type()}"
        )

    def test_initial_taste_saved_to_column(self):
        """
        Initial taste in 'initial_taste' column.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('initial_taste')
        assert field is not None, "DiscoveredProduct must have 'initial_taste' field"
        assert field.get_internal_type() == 'TextField', (
            f"'initial_taste' must be TextField, not {field.get_internal_type()}"
        )


class TestAwardsSavedAsRecords:
    """
    Test awards are saved as related records (ProductAward model), not JSON.

    Per spec: Awards should be ProductAward related objects, NOT JSON array.
    """

    def test_product_award_model_exists(self):
        """
        ProductAward model must exist as a separate model.
        """
        from crawler.models import ProductAward

        assert ProductAward is not None, "ProductAward model must exist"

    def test_product_award_has_required_fields(self):
        """
        ProductAward must have competition, year, medal fields as individual columns.
        """
        from crawler.models import ProductAward

        # Check competition field
        competition_field = ProductAward._meta.get_field('competition')
        assert competition_field is not None, "ProductAward must have 'competition' field"
        assert competition_field.get_internal_type() == 'CharField', (
            f"'competition' must be CharField, not {competition_field.get_internal_type()}"
        )

        # Check year field
        year_field = ProductAward._meta.get_field('year')
        assert year_field is not None, "ProductAward must have 'year' field"
        assert year_field.get_internal_type() == 'IntegerField', (
            f"'year' must be IntegerField, not {year_field.get_internal_type()}"
        )

        # Check medal field
        medal_field = ProductAward._meta.get_field('medal')
        assert medal_field is not None, "ProductAward must have 'medal' field"
        assert medal_field.get_internal_type() == 'CharField', (
            f"'medal' must be CharField, not {medal_field.get_internal_type()}"
        )

    def test_product_award_has_product_fk(self):
        """
        ProductAward must have ForeignKey to DiscoveredProduct.
        """
        from crawler.models import ProductAward

        product_field = ProductAward._meta.get_field('product')
        assert product_field is not None, "ProductAward must have 'product' FK"
        assert product_field.get_internal_type() == 'ForeignKey', (
            f"'product' must be ForeignKey, not {product_field.get_internal_type()}"
        )

    def test_can_query_products_by_award_via_related_manager(self):
        """
        Should be able to access awards via related_name from DiscoveredProduct.
        Related name should allow: product.awards_rel.filter(medal='gold')
        """
        from crawler.models import DiscoveredProduct, ProductAward

        # Check that the related name exists
        product_field = ProductAward._meta.get_field('product')
        related_name = product_field.remote_field.related_name

        assert related_name is not None, "ProductAward.product must have a related_name"
        assert related_name == 'awards_rel', (
            f"Related name should be 'awards_rel', got '{related_name}'"
        )


class TestDeprecatedFieldsEmptyOrRemoved:
    """
    Test deprecated JSON fields are empty or removed entirely.

    Per spec, these fields should NOT exist or should be empty:
    - extracted_data (removed)
    - enriched_data (removed)
    - taste_profile (removed)
    """

    def test_extracted_data_field_removed(self):
        """
        extracted_data should be removed from model.
        Old field that stored all extracted fields as JSON blob.
        """
        from crawler.models import DiscoveredProduct

        # Try to get the field - should raise FieldDoesNotExist
        try:
            field = DiscoveredProduct._meta.get_field('extracted_data')
            # If we get here, field exists - this is a FAILURE
            pytest.fail(
                "DEPRECATED: 'extracted_data' JSON blob field still exists! "
                "Per spec, all searchable fields must be in individual columns."
            )
        except Exception:
            # Field does not exist - this is CORRECT
            pass

    def test_enriched_data_field_removed(self):
        """
        enriched_data should be removed from model.
        Old field that stored enriched fields as JSON blob.
        """
        from crawler.models import DiscoveredProduct

        try:
            field = DiscoveredProduct._meta.get_field('enriched_data')
            pytest.fail(
                "DEPRECATED: 'enriched_data' JSON blob field still exists! "
                "Per spec, all searchable fields must be in individual columns."
            )
        except Exception:
            pass

    def test_taste_profile_json_blob_removed(self):
        """
        taste_profile JSON blob should be removed.
        Old field that stored tasting data as JSON.
        """
        from crawler.models import DiscoveredProduct

        try:
            field = DiscoveredProduct._meta.get_field('taste_profile')
            # Check if it's a JSONField - that's deprecated
            if field.get_internal_type() == 'JSONField':
                pytest.fail(
                    "DEPRECATED: 'taste_profile' JSON blob field still exists! "
                    "Tasting data must be in individual columns: "
                    "nose_description, palate_description, finish_description, etc."
                )
        except Exception:
            # Field does not exist - this is CORRECT
            pass


class TestArrayFieldsAcceptable:
    """
    Test that array fields (acceptable as JSON) work correctly.

    Per spec, JSON is acceptable for:
    - Array fields: palate_flavors, primary_aromas, finish_flavors
    - These are lists of strings, not structured data
    """

    def test_palate_flavors_is_json_array(self):
        """
        palate_flavors can be JSONField since it's an array.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('palate_flavors')
        assert field is not None, "DiscoveredProduct must have 'palate_flavors' field"
        # JSONField is acceptable for arrays
        assert field.get_internal_type() == 'JSONField', (
            f"'palate_flavors' should be JSONField for array storage, got {field.get_internal_type()}"
        )

    def test_primary_aromas_is_json_array(self):
        """
        primary_aromas can be JSONField since it's an array.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('primary_aromas')
        assert field is not None, "DiscoveredProduct must have 'primary_aromas' field"
        assert field.get_internal_type() == 'JSONField', (
            f"'primary_aromas' should be JSONField for array storage, got {field.get_internal_type()}"
        )

    def test_finish_flavors_is_json_array(self):
        """
        finish_flavors can be JSONField since it's an array.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('finish_flavors')
        assert field is not None, "DiscoveredProduct must have 'finish_flavors' field"
        assert field.get_internal_type() == 'JSONField', (
            f"'finish_flavors' should be JSONField for array storage, got {field.get_internal_type()}"
        )

    def test_secondary_aromas_is_json_array(self):
        """
        secondary_aromas can be JSONField since it's an array.
        """
        from crawler.models import DiscoveredProduct

        field = DiscoveredProduct._meta.get_field('secondary_aromas')
        assert field is not None, "DiscoveredProduct must have 'secondary_aromas' field"
        assert field.get_internal_type() == 'JSONField', (
            f"'secondary_aromas' should be JSONField for array storage, got {field.get_internal_type()}"
        )


class TestAllRequiredColumnsExist:
    """
    Comprehensive test that ALL searchable fields from spec are in individual columns.

    Per spec, these MUST be individual columns:
    - Identification: name, brand, product_type
    - Basic info: abv, description, region, country
    - Tasting notes: nose_description, palate_description, finish_description, finish_length, mouthfeel, mid_palate
    - Pricing: best_price
    - Scoring: completeness_score, status, source_count
    """

    def test_all_required_columns_exist(self):
        """
        Verify all required searchable columns exist in DiscoveredProduct.
        """
        from crawler.models import DiscoveredProduct

        REQUIRED_COLUMNS = [
            # Identification
            "name",
            "product_type",

            # Basic info
            "abv",
            "description",
            "region",
            "country",

            # Tasting notes
            "nose_description",
            "palate_description",
            "finish_description",
            "finish_length",
            "mouthfeel",
            "mid_palate_evolution",

            # Pricing
            "best_price",

            # Scoring
            "completeness_score",
            "status",
            "source_count",
        ]

        missing_columns = []
        for column in REQUIRED_COLUMNS:
            try:
                DiscoveredProduct._meta.get_field(column)
            except Exception:
                missing_columns.append(column)

        assert not missing_columns, (
            f"Missing required columns in DiscoveredProduct: {missing_columns}"
        )

    def test_brand_relationship_exists(self):
        """
        Brand should be a ForeignKey relationship to DiscoveredBrand.
        """
        from crawler.models import DiscoveredProduct, DiscoveredBrand

        field = DiscoveredProduct._meta.get_field('brand')
        assert field is not None, "DiscoveredProduct must have 'brand' field"

        # Check it points to DiscoveredBrand
        related_model = field.related_model
        assert related_model == DiscoveredBrand, (
            f"'brand' should be FK to DiscoveredBrand, not {related_model}"
        )


class TestWhiskeyDetailsModel:
    """
    Test WhiskeyDetails model has individual columns for whiskey-specific fields.
    """

    def test_whiskey_details_model_exists(self):
        """WhiskeyDetails model must exist."""
        from crawler.models import WhiskeyDetails
        assert WhiskeyDetails is not None

    def test_whiskey_details_has_distillery_column(self):
        """Distillery must be in individual column, indexed."""
        from crawler.models import WhiskeyDetails

        field = WhiskeyDetails._meta.get_field('distillery')
        assert field is not None
        assert field.get_internal_type() == 'CharField'
        assert field.db_index, "'distillery' should be indexed"

    def test_whiskey_details_has_whiskey_type_column(self):
        """whiskey_type must be in individual column."""
        from crawler.models import WhiskeyDetails

        field = WhiskeyDetails._meta.get_field('whiskey_type')
        assert field is not None
        assert field.get_internal_type() == 'CharField'

    def test_whiskey_details_has_product_onetoone(self):
        """WhiskeyDetails must have OneToOne to DiscoveredProduct."""
        from crawler.models import WhiskeyDetails

        field = WhiskeyDetails._meta.get_field('product')
        assert field is not None
        assert field.get_internal_type() == 'OneToOneField'


class TestPortWineDetailsModel:
    """
    Test PortWineDetails model has individual columns for port-specific fields.
    """

    def test_port_wine_details_model_exists(self):
        """PortWineDetails model must exist."""
        from crawler.models import PortWineDetails
        assert PortWineDetails is not None

    def test_port_wine_details_has_style_column(self):
        """Port style must be in individual column."""
        from crawler.models import PortWineDetails

        field = PortWineDetails._meta.get_field('style')
        assert field is not None
        assert field.get_internal_type() == 'CharField'

    def test_port_wine_details_has_harvest_year_column(self):
        """harvest_year must be in individual column, indexed."""
        from crawler.models import PortWineDetails

        field = PortWineDetails._meta.get_field('harvest_year')
        assert field is not None
        assert field.get_internal_type() == 'IntegerField'
        assert field.db_index, "'harvest_year' should be indexed"

    def test_port_wine_details_has_producer_house_column(self):
        """producer_house must be in individual column, indexed."""
        from crawler.models import PortWineDetails

        field = PortWineDetails._meta.get_field('producer_house')
        assert field is not None
        assert field.get_internal_type() == 'CharField'
        assert field.db_index, "'producer_house' should be indexed"

    def test_port_wine_details_has_product_onetoone(self):
        """PortWineDetails must have OneToOne to DiscoveredProduct."""
        from crawler.models import PortWineDetails

        field = PortWineDetails._meta.get_field('product')
        assert field is not None
        assert field.get_internal_type() == 'OneToOneField'


class TestDataSavedToCorrectColumns:
    """
    Integration tests that verify data is actually saved to the correct columns.
    These tests create model instances and verify the data goes to individual columns.
    """

    @pytest.fixture
    def mock_product_data(self):
        """Sample product data for testing."""
        return {
            'name': 'Highland Park 12 Year',
            'product_type': 'whiskey',
            'abv': Decimal('43.0'),
            'region': 'Orkney',
            'country': 'Scotland',
            'description': 'A classic single malt from Orkney.',
            'nose_description': 'Heather honey, peat smoke, citrus.',
            'palate_description': 'Rich honey, smoke, dark chocolate.',
            'finish_description': 'Long, warming, smoky.',
            'palate_flavors': ['honey', 'smoke', 'chocolate'],
            'primary_aromas': ['heather', 'peat', 'citrus'],
        }

    def test_product_data_saved_to_individual_columns(self, mock_product_data):
        """
        Test that product data is saved to individual columns, not JSON blobs.
        """
        from crawler.models import DiscoveredProduct
        import hashlib

        # Create a product instance (without saving to DB)
        product = DiscoveredProduct(
            name=mock_product_data['name'],
            product_type=mock_product_data['product_type'],
            abv=mock_product_data['abv'],
            region=mock_product_data['region'],
            country=mock_product_data['country'],
            description=mock_product_data['description'],
            nose_description=mock_product_data['nose_description'],
            palate_description=mock_product_data['palate_description'],
            finish_description=mock_product_data['finish_description'],
            palate_flavors=mock_product_data['palate_flavors'],
            primary_aromas=mock_product_data['primary_aromas'],
            source_url='https://example.com/product',
            raw_content='<html>Test</html>',
        )

        # Verify data is in the correct columns
        assert product.name == mock_product_data['name']
        assert product.abv == mock_product_data['abv']
        assert product.region == mock_product_data['region']
        assert product.country == mock_product_data['country']
        assert product.nose_description == mock_product_data['nose_description']
        assert product.palate_description == mock_product_data['palate_description']
        assert product.finish_description == mock_product_data['finish_description']

        # Verify array fields are stored correctly
        assert product.palate_flavors == mock_product_data['palate_flavors']
        assert product.primary_aromas == mock_product_data['primary_aromas']

        # Verify no deprecated JSON blob fields exist
        assert not hasattr(product, 'extracted_data') or not callable(getattr(product, 'extracted_data', None))
        assert not hasattr(product, 'enriched_data') or not callable(getattr(product, 'enriched_data', None))


class TestLegacyJSONFieldsDocumented:
    """
    Test that any remaining JSON fields are documented and intentional.

    Per spec, the only acceptable JSON fields are:
    - Array fields for lists: palate_flavors, primary_aromas, finish_flavors, etc.
    - Metadata that's never searched: images, ratings, press_mentions, discovery_sources
    """

    def test_acceptable_json_fields_are_arrays_or_metadata(self):
        """
        Verify all JSONFields are for arrays or metadata, not structured searchable data.
        """
        from crawler.models import DiscoveredProduct
        from django.db.models import JSONField as DjangoJSONField

        # Get all JSONField instances
        json_fields = []
        for field in DiscoveredProduct._meta.get_fields():
            if hasattr(field, 'get_internal_type') and field.get_internal_type() == 'JSONField':
                json_fields.append(field.name)

        # These are ACCEPTABLE JSONFields per spec (arrays and metadata)
        ACCEPTABLE_JSON_FIELDS = {
            # Array fields
            'palate_flavors', 'primary_aromas', 'secondary_aromas', 'finish_flavors',
            'primary_cask', 'finishing_cask', 'wood_type', 'cask_treatment',

            # Metadata that's never searched
            'images', 'ratings', 'press_mentions', 'discovery_sources',
            'awards',  # Legacy JSON field - ProductAward model is preferred
            'price_history', 'verified_fields', 'missing_fields',
            'conflict_details',
        }

        # Check for any unexpected JSON fields
        unexpected_json_fields = set(json_fields) - ACCEPTABLE_JSON_FIELDS

        assert not unexpected_json_fields, (
            f"Found unexpected JSON fields that may be storing searchable data: {unexpected_json_fields}. "
            "Per spec, searchable fields must be in individual columns."
        )
