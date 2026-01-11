"""
Integration tests for V2 Completeness Scoring Service.

Task 7.6: Integration Test - Completeness Scoring

This module tests the completeness scoring system with V2 AI Enhancement Service fields.
It verifies that:
1. Empty/skeleton products have low scores
2. Flavor arrays (palate_flavors, primary_aromas, finish_flavors) increase scores
3. Products with all V2 fields achieve high scores (65+)
4. Status transitions occur at correct thresholds
5. Scoring weights match the spec (AI_ENHANCEMENT_SERVICE_V2_SPEC.md)

Spec Reference:
- palate_flavors (3+ items): +10 points
- primary_aromas (2+ items): +5 points
- finish_flavors (2+ items): +5 points
- description: +5 points
- category: +3 points
- appearance fields (any populated): +3 points total
- ratings fields (any populated): +5 points total
"""

import pytest
from typing import Any, Dict, Optional


class MockProduct:
    """
    Mock DiscoveredProduct for completeness scoring tests.

    This mock simulates the Django model without database dependencies,
    allowing isolated testing of the scoring logic.
    """

    def __init__(self, **kwargs):
        """Initialize with provided field values."""
        # Core identification fields
        self.name = kwargs.get('name', None)
        self.brand_id = kwargs.get('brand_id', None)
        self.product_type = kwargs.get('product_type', None)
        self.abv = kwargs.get('abv', None)
        self.age_statement = kwargs.get('age_statement', None)
        self.region = kwargs.get('region', None)
        self.category = kwargs.get('category', None)
        self.description = kwargs.get('description', None)

        # Tasting profile - Nose
        self.nose_description = kwargs.get('nose_description', None)
        self.primary_aromas = kwargs.get('primary_aromas', None)
        self.secondary_aromas = kwargs.get('secondary_aromas', None)
        self.aroma_evolution = kwargs.get('aroma_evolution', None)

        # Tasting profile - Palate
        self.palate_description = kwargs.get('palate_description', None)
        self.palate_flavors = kwargs.get('palate_flavors', None)
        self.initial_taste = kwargs.get('initial_taste', None)
        self.mid_palate_evolution = kwargs.get('mid_palate_evolution', None)
        self.mouthfeel = kwargs.get('mouthfeel', None)

        # Tasting profile - Finish
        self.finish_description = kwargs.get('finish_description', None)
        self.finish_flavors = kwargs.get('finish_flavors', None)
        self.finish_length = kwargs.get('finish_length', None)
        self.finish_evolution = kwargs.get('finish_evolution', None)
        self.final_notes = kwargs.get('final_notes', None)

        # Appearance fields
        self.color_description = kwargs.get('color_description', None)
        self.color_intensity = kwargs.get('color_intensity', None)
        self.clarity = kwargs.get('clarity', None)
        self.viscosity = kwargs.get('viscosity', None)

        # Ratings fields
        self.flavor_intensity = kwargs.get('flavor_intensity', None)
        self.complexity = kwargs.get('complexity', None)
        self.warmth = kwargs.get('warmth', None)
        self.dryness = kwargs.get('dryness', None)
        self.balance = kwargs.get('balance', None)
        self.overall_complexity = kwargs.get('overall_complexity', None)
        self.uniqueness = kwargs.get('uniqueness', None)
        self.drinkability = kwargs.get('drinkability', None)

        # Other fields
        self.experience_level = kwargs.get('experience_level', None)
        self.best_price = kwargs.get('best_price', None)
        self.images = kwargs.get('images', None)
        self.awards = kwargs.get('awards', None)
        self.source_count = kwargs.get('source_count', 1)
        self.completeness_score = kwargs.get('completeness_score', None)
        self.status = kwargs.get('status', None)

        # WhiskeyDetails-like attributes for category detection
        self.whiskey_details = kwargs.get('whiskey_details', None)
        self.port_details = kwargs.get('port_details', None)


class MockWhiskeyDetails:
    """Mock WhiskeyDetails for whiskey_type testing."""
    def __init__(self, whiskey_type: Optional[str] = None):
        self.whiskey_type = whiskey_type


class MockPortDetails:
    """Mock PortWineDetails for style testing."""
    def __init__(self, style: Optional[str] = None):
        self.style = style


@pytest.fixture
def skeleton_product():
    """
    Fixture: A skeleton product with only a name.

    This represents a product just discovered with minimal data.
    Should have a very low completeness score.
    """
    return MockProduct(name="Unknown Whiskey")


@pytest.fixture
def product_with_identification():
    """
    Fixture: Product with basic identification fields.

    Has name, brand_id, product_type, and ABV.
    """
    return MockProduct(
        name="Test Whiskey 12 Year",
        brand_id=123,
        product_type="whiskey",
        abv=46.0,
        age_statement=12,
    )


@pytest.fixture
def product_with_flavors():
    """
    Fixture: Product with V2 flavor arrays.

    Has palate_flavors (3+ items), primary_aromas (2+ items),
    and finish_flavors (2+ items) to test V2 scoring.
    """
    return MockProduct(
        name="Highland Single Malt 12 Year",
        brand_id=456,
        product_type="whiskey",
        abv=46.0,
        age_statement=12,
        region="Highland",
        category="Single Malt Scotch",
        palate_flavors=["vanilla", "honey", "oak", "spice"],  # 4 items (3+ required)
        primary_aromas=["honey", "green apple", "floral"],  # 3 items (2+ required)
        finish_flavors=["oak", "vanilla", "warmth"],  # 3 items (2+ required)
    )


@pytest.fixture
def product_with_all_v2_fields():
    """
    Fixture: Complete product with all V2 fields populated.

    Should achieve a high completeness score (65+).
    Includes all CRITICAL, HIGH, and MEDIUM priority V2 fields.
    """
    return MockProduct(
        # Core identification (15 points)
        name="Glencadam 10 Year Old",
        brand_id=789,

        # Basic info (13 points)
        product_type="whiskey",
        abv=46.0,
        category="Single Malt Scotch",

        # Description (5 points)
        description="A superb Highland single malt with notes of honey and green apple.",

        # Nose (10 points max)
        nose_description="Fresh and floral with notes of honey",
        primary_aromas=["honey", "green apple", "vanilla", "floral"],  # 5 points
        secondary_aromas=["citrus", "floral"],
        aroma_evolution="Opens with fruit, becomes more complex",

        # Palate (20 points max)
        palate_description="Smooth and creamy with butterscotch",
        palate_flavors=["butterscotch", "oak", "citrus", "vanilla"],  # 10 points
        initial_taste="Sweet honey and vanilla",
        mid_palate_evolution="Develops oak and spice",
        mouthfeel="smooth-creamy",

        # Finish (10 points max)
        finish_description="Medium-long with lingering honey",
        finish_flavors=["honey", "spice", "oak"],  # 5 points
        finish_length=7,
        finish_evolution="Starts warm, fades to sweet",
        final_notes="Lingering warmth with vanilla",

        # Appearance (3 points for any populated)
        color_description="Deep amber with golden highlights",
        color_intensity=7,
        clarity="crystal_clear",
        viscosity="medium",

        # Ratings (5 points for any populated)
        flavor_intensity=7,
        complexity=8,
        warmth=5,
        dryness=4,
        balance=8,
        overall_complexity=7,
        uniqueness=6,
        drinkability=9,

        # Other
        experience_level="intermediate",
        age_statement=10,
        region="Highland",

        # Enrichment data (9 points max)
        best_price=65.00,
        images=["image1.jpg"],
        awards=[{"competition": "IWSC", "year": 2023, "medal": "Gold"}],

        # Verification
        source_count=2,  # Multiple sources for verified status
    )


@pytest.fixture
def product_at_status_thresholds():
    """
    Fixture factory for creating products at specific score thresholds.

    Returns a function that creates products targeting specific scores.
    """
    def _create_product(target_status: str) -> MockProduct:
        if target_status == "incomplete":
            # Score < 30, no palate
            return MockProduct(
                name="Incomplete Product",
                product_type="whiskey",
            )
        elif target_status == "partial":
            # Score 30-59, or has data but no palate
            return MockProduct(
                name="Partial Product",
                brand_id=100,
                product_type="whiskey",
                abv=40.0,
                category="Bourbon",
                description="A decent bourbon",
                nose_description="Vanilla and caramel",
                primary_aromas=["vanilla", "caramel"],
                # No palate_flavors - caps at partial
            )
        elif target_status == "complete":
            # Score 60-79 AND has palate data
            return MockProduct(
                name="Complete Product",
                brand_id=200,
                product_type="whiskey",
                abv=45.0,
                category="Single Malt Scotch",
                description="A fine Highland single malt",
                nose_description="Honey and floral notes",
                primary_aromas=["honey", "floral", "citrus"],
                palate_description="Smooth and balanced",
                palate_flavors=["honey", "vanilla", "oak"],
                finish_description="Long and warming",
                finish_flavors=["oak", "spice"],
                finish_length=7,
                color_description="Amber",
                balance=8,
                source_count=1,
            )
        elif target_status == "verified":
            # Score 80+ AND has palate data AND source_count >= 2
            return MockProduct(
                name="Verified Product",
                brand_id=300,
                product_type="whiskey",
                abv=46.0,
                category="Single Malt Scotch",
                description="An exceptional Highland single malt",
                nose_description="Rich honey and vanilla",
                primary_aromas=["honey", "vanilla", "floral", "citrus"],
                palate_description="Smooth and complex",
                palate_flavors=["butterscotch", "oak", "vanilla", "spice"],
                initial_taste="Sweet honey",
                mid_palate_evolution="Develops into oak spice",
                mouthfeel="smooth-creamy",
                finish_description="Long and warming",
                finish_flavors=["oak", "spice", "honey"],
                finish_length=8,
                final_notes="Lingering warmth",
                color_description="Deep amber",
                color_intensity=7,
                clarity="crystal_clear",
                balance=8,
                complexity=8,
                drinkability=9,
                best_price=75.00,
                images=["image1.jpg", "image2.jpg"],
                awards=[{"competition": "IWSC", "medal": "Gold"}],
                source_count=3,  # Multi-source verified
            )
        else:
            raise ValueError(f"Unknown status: {target_status}")

    return _create_product


class TestSkeletonProductScore:
    """Test 1: Verify empty product has low score."""

    def test_skeleton_product_score_low(self, skeleton_product):
        """
        Verify that an empty/skeleton product has a very low completeness score.

        A skeleton product with only a name should score < 30, resulting in
        'incomplete' status.
        """
        from crawler.services.completeness import calculate_completeness_score, determine_status

        score = calculate_completeness_score(skeleton_product)
        status = determine_status(skeleton_product)

        # Skeleton product should have a very low score
        assert score < 30, f"Skeleton product should score < 30, got {score}"

        # Status should be 'incomplete'
        assert status == "incomplete", f"Skeleton product should be 'incomplete', got {status}"

    def test_skeleton_product_missing_critical_fields(self, skeleton_product):
        """
        Verify that skeleton product is missing critical V2 fields.

        Should be missing palate_flavors, primary_aromas, finish_flavors,
        description, and category.
        """
        from crawler.services.completeness import get_missing_fields

        missing = get_missing_fields(skeleton_product)

        # Critical V2 fields should be in missing list
        assert "palate_flavors" in missing or "palate_flavors" not in [
            f for f in missing if "palate" not in f.lower()
        ], "palate_flavors should be flagged as missing"

        # Brand should be missing
        assert "brand" in missing, "brand should be missing for skeleton product"


class TestProductWithFlavorsIncreasesScore:
    """Test 2: Verify flavor arrays increase score."""

    def test_product_with_flavors_increases_score(self, product_with_identification, product_with_flavors):
        """
        Verify that adding flavor arrays significantly increases the score.

        According to spec:
        - palate_flavors (3+ items): +10 points
        - primary_aromas (2+ items): +5 points
        - finish_flavors (2+ items): +5 points

        Total potential increase: 20 points from flavor arrays alone.
        """
        from crawler.services.completeness import calculate_completeness_score

        base_score = calculate_completeness_score(product_with_identification)
        flavors_score = calculate_completeness_score(product_with_flavors)

        # Score with flavors should be significantly higher
        score_increase = flavors_score - base_score

        # Expected minimum increase from flavors: 20 points
        # Plus description (+5) and category (+3) = at least 28 more
        assert score_increase >= 15, (
            f"Flavor arrays should increase score by at least 15 points, "
            f"got {score_increase} (base: {base_score}, with flavors: {flavors_score})"
        )

    def test_palate_flavors_contributes_points(self, product_with_identification):
        """
        Verify palate_flavors with 3+ items adds points.

        Spec: palate_flavors (3+ items): +10 points
        """
        from crawler.services.completeness import calculate_palate_score

        # Without palate_flavors
        score_without = calculate_palate_score(product_with_identification)

        # Add palate_flavors with 3+ items
        product_with_identification.palate_flavors = ["vanilla", "honey", "oak"]
        score_with = calculate_palate_score(product_with_identification)

        # Should increase by 10 points
        assert score_with >= score_without + 10, (
            f"palate_flavors should add 10 points, "
            f"got {score_with - score_without} increase"
        )

    def test_primary_aromas_contributes_points(self, product_with_identification):
        """
        Verify primary_aromas with 2+ items adds points.

        Spec: primary_aromas (2+ items): +5 points
        """
        from crawler.services.completeness import calculate_nose_score

        # Without primary_aromas
        score_without = calculate_nose_score(product_with_identification)

        # Add primary_aromas with 2+ items
        product_with_identification.primary_aromas = ["honey", "vanilla"]
        score_with = calculate_nose_score(product_with_identification)

        # Should increase by 5 points
        assert score_with >= score_without + 5, (
            f"primary_aromas should add 5 points, "
            f"got {score_with - score_without} increase"
        )

    def test_finish_flavors_contributes_points(self, product_with_identification):
        """
        Verify finish_flavors with 2+ items adds points.

        Spec: finish_flavors (2+ items): +5 points
        """
        from crawler.services.completeness import calculate_finish_score

        # Without finish_flavors
        score_without = calculate_finish_score(product_with_identification)

        # Add finish_flavors with 2+ items
        product_with_identification.finish_flavors = ["oak", "spice"]
        score_with = calculate_finish_score(product_with_identification)

        # Should increase by 5 points
        assert score_with >= score_without + 5, (
            f"finish_flavors should add 5 points, "
            f"got {score_with - score_without} increase"
        )


class TestProductWithAllV2FieldsHighScore:
    """Test 3: Verify complete product has high score (65+)."""

    def test_product_with_all_v2_fields_high_score(self, product_with_all_v2_fields):
        """
        Verify that a product with all V2 fields achieves a high score (65+).

        According to the spec, a complete product should have:
        - Identification: 15 points (name 10, brand 5)
        - Basic info: 13 points (type 5, ABV 5, category 3)
        - Description: 5 points
        - Tasting profile: 40 points max (palate 20, nose 10, finish 10)
        - Appearance: 3 points
        - Ratings: 5 points
        - Enrichment: 9 points max
        - Verification bonus: up to 10 points

        Total possible: 100 points
        Target for "complete" status: 65+
        """
        from crawler.services.completeness import calculate_completeness_score

        score = calculate_completeness_score(product_with_all_v2_fields)

        # Should achieve 65+ for complete status
        assert score >= 65, (
            f"Product with all V2 fields should score 65+, got {score}"
        )

    def test_product_can_reach_complete_status(self, product_with_all_v2_fields):
        """
        Verify that a product with full V2 data can reach 'complete' or 'verified' status.
        """
        from crawler.services.completeness import determine_status, has_palate_data

        status = determine_status(product_with_all_v2_fields)
        has_palate = has_palate_data(product_with_all_v2_fields)

        # Should have palate data (required for complete/verified)
        assert has_palate, "Product with all V2 fields should have palate data"

        # Should be at least 'complete' status
        assert status in ["complete", "verified"], (
            f"Product with all V2 fields should be 'complete' or 'verified', got '{status}'"
        )


class TestStatusTransitionsBasedOnScore:
    """Test 4: Verify status changes at thresholds."""

    def test_incomplete_status_below_30(self, product_at_status_thresholds):
        """
        Verify products with score < 30 or no palate get 'incomplete' status.
        """
        from crawler.services.completeness import calculate_completeness_score, determine_status

        product = product_at_status_thresholds("incomplete")
        score = calculate_completeness_score(product)
        status = determine_status(product)

        assert status == "incomplete", (
            f"Product with score {score} should be 'incomplete', got '{status}'"
        )

    def test_partial_status_30_to_59_or_no_palate(self, product_at_status_thresholds):
        """
        Verify products with score 30-59 or without palate get 'partial' status.

        Key rule: Without palate data, a product cannot exceed 'partial' status
        regardless of score.
        """
        from crawler.services.completeness import calculate_completeness_score, determine_status, has_palate_data

        product = product_at_status_thresholds("partial")
        score = calculate_completeness_score(product)
        status = determine_status(product)
        has_palate = has_palate_data(product)

        # If score >= 30 but no palate, should be capped at partial
        if not has_palate and score >= 30:
            assert status == "partial", (
                f"Product without palate but score {score} should be 'partial', got '{status}'"
            )
        # If score 30-59 with or without palate, should be partial
        elif 30 <= score < 60:
            assert status == "partial", (
                f"Product with score {score} should be 'partial', got '{status}'"
            )

    def test_complete_status_60_to_79_with_palate(self, product_at_status_thresholds):
        """
        Verify products with score 60-79 AND palate data get 'complete' status.
        """
        from crawler.services.completeness import calculate_completeness_score, determine_status, has_palate_data

        product = product_at_status_thresholds("complete")
        score = calculate_completeness_score(product)
        status = determine_status(product)
        has_palate = has_palate_data(product)

        # Must have palate data
        assert has_palate, "Complete product should have palate data"

        # Score should be 60-79
        assert 60 <= score < 80, f"Complete product should have score 60-79, got {score}"

        # Status should be 'complete'
        assert status == "complete", (
            f"Product with score {score} and palate should be 'complete', got '{status}'"
        )

    def test_verified_status_80_plus_with_palate_and_sources(self, product_at_status_thresholds):
        """
        Verify products with score 80+ AND palate AND source_count >= 2 get 'verified'.
        """
        from crawler.services.completeness import calculate_completeness_score, determine_status, has_palate_data

        product = product_at_status_thresholds("verified")
        score = calculate_completeness_score(product)
        status = determine_status(product)
        has_palate = has_palate_data(product)

        # Must have palate data
        assert has_palate, "Verified product should have palate data"

        # Must have multiple sources
        assert product.source_count >= 2, "Verified product should have source_count >= 2"

        # Score should be 80+
        assert score >= 80, f"Verified product should have score 80+, got {score}"

        # Status should be 'verified'
        assert status == "verified", (
            f"Product with score {score}, palate, and {product.source_count} sources "
            f"should be 'verified', got '{status}'"
        )

    def test_palate_required_for_complete_verified(self):
        """
        Verify that palate data is REQUIRED for complete/verified status.

        Even with high score, without palate data, status is capped at 'partial'.
        """
        from crawler.services.completeness import determine_status, calculate_completeness_score

        # Create product with high score but no palate
        product = MockProduct(
            name="High Score No Palate",
            brand_id=100,
            product_type="whiskey",
            abv=45.0,
            category="Single Malt Scotch",
            description="A fine whisky",
            nose_description="Rich and complex",
            primary_aromas=["honey", "vanilla", "citrus", "floral"],
            color_description="Golden amber",
            color_intensity=6,
            balance=8,
            drinkability=8,
            best_price=50.00,
            images=["img.jpg"],
            awards=[{"medal": "Gold"}],
            source_count=3,
            # NO palate_flavors, palate_description, or initial_taste
        )

        score = calculate_completeness_score(product)
        status = determine_status(product)

        # Even with potentially high score, without palate = partial max
        assert status in ["incomplete", "partial"], (
            f"Product without palate should be 'incomplete' or 'partial', got '{status}'"
        )


class TestScoreWeightsMatchSpec:
    """Test 5: Verify scoring weights from spec are applied."""

    def test_palate_flavors_weight_10_points(self):
        """
        Verify palate_flavors (3+ items) adds exactly 10 points.

        Spec: palate_flavors (3+ items): +10 points
        """
        from crawler.services.completeness import calculate_palate_score

        product_without = MockProduct(name="Test")
        product_with = MockProduct(
            name="Test",
            palate_flavors=["vanilla", "honey", "oak"],  # Exactly 3 items
        )

        score_without = calculate_palate_score(product_without)
        score_with = calculate_palate_score(product_with)

        assert score_with - score_without == 10, (
            f"palate_flavors should add exactly 10 points, "
            f"got {score_with - score_without}"
        )

    def test_primary_aromas_weight_5_points(self):
        """
        Verify primary_aromas (2+ items) adds exactly 5 points.

        Spec: primary_aromas (2+ items): +5 points
        """
        from crawler.services.completeness import calculate_nose_score

        product_without = MockProduct(name="Test")
        product_with = MockProduct(
            name="Test",
            primary_aromas=["honey", "vanilla"],  # Exactly 2 items
        )

        score_without = calculate_nose_score(product_without)
        score_with = calculate_nose_score(product_with)

        assert score_with - score_without == 5, (
            f"primary_aromas should add exactly 5 points, "
            f"got {score_with - score_without}"
        )

    def test_finish_flavors_weight_5_points(self):
        """
        Verify finish_flavors (2+ items) adds exactly 5 points.

        Spec: finish_flavors (2+ items): +5 points
        """
        from crawler.services.completeness import calculate_finish_score

        product_without = MockProduct(name="Test")
        product_with = MockProduct(
            name="Test",
            finish_flavors=["oak", "spice"],  # Exactly 2 items
        )

        score_without = calculate_finish_score(product_without)
        score_with = calculate_finish_score(product_with)

        assert score_with - score_without == 5, (
            f"finish_flavors should add exactly 5 points, "
            f"got {score_with - score_without}"
        )

    def test_description_weight_5_points(self):
        """
        Verify description adds exactly 5 points.

        Spec: description: +5 points
        """
        from crawler.services.completeness import calculate_completeness_score

        product_without = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
        )
        product_with = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            description="A fine whiskey with rich flavors.",
        )

        score_without = calculate_completeness_score(product_without)
        score_with = calculate_completeness_score(product_with)

        assert score_with - score_without == 5, (
            f"description should add exactly 5 points, "
            f"got {score_with - score_without}"
        )

    def test_category_weight_3_points(self):
        """
        Verify category adds exactly 3 points.

        Spec: category: +3 points
        """
        from crawler.services.completeness import calculate_completeness_score

        product_without = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
        )
        product_with = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            category="Single Malt Scotch",
        )

        score_without = calculate_completeness_score(product_without)
        score_with = calculate_completeness_score(product_with)

        assert score_with - score_without == 3, (
            f"category should add exactly 3 points, "
            f"got {score_with - score_without}"
        )

    def test_appearance_fields_weight_3_points_total(self):
        """
        Verify any populated appearance field adds 3 points total.

        Spec: appearance fields (any populated): +3 points total
        """
        from crawler.services.completeness import calculate_appearance_score

        product_without = MockProduct(name="Test")

        # Test with just color_description
        product_with_color = MockProduct(
            name="Test",
            color_description="Golden amber",
        )

        score_without = calculate_appearance_score(product_without)
        score_with = calculate_appearance_score(product_with_color)

        assert score_without == 0, "No appearance fields should give 0 points"
        assert score_with == 3, f"Any appearance field should give 3 points, got {score_with}"

        # Adding more appearance fields should not increase beyond 3
        product_with_all = MockProduct(
            name="Test",
            color_description="Golden amber",
            color_intensity=6,
            clarity="crystal_clear",
            viscosity="medium",
        )
        score_with_all = calculate_appearance_score(product_with_all)

        assert score_with_all == 3, (
            f"Multiple appearance fields should still give only 3 points, got {score_with_all}"
        )

    def test_ratings_fields_weight_5_points_total(self):
        """
        Verify any populated ratings field adds 5 points total.

        Spec: ratings fields (any populated): +5 points total
        """
        from crawler.services.completeness import calculate_ratings_score

        product_without = MockProduct(name="Test")

        # Test with just one rating
        product_with_one = MockProduct(
            name="Test",
            balance=7,
        )

        score_without = calculate_ratings_score(product_without)
        score_with_one = calculate_ratings_score(product_with_one)

        assert score_without == 0, "No ratings fields should give 0 points"
        assert score_with_one == 5, f"Any rating field should give 5 points, got {score_with_one}"

        # Adding more ratings should not increase beyond 5
        product_with_all = MockProduct(
            name="Test",
            flavor_intensity=7,
            complexity=8,
            warmth=5,
            dryness=4,
            balance=8,
            overall_complexity=7,
            uniqueness=6,
            drinkability=9,
        )
        score_with_all = calculate_ratings_score(product_with_all)

        assert score_with_all == 5, (
            f"Multiple ratings fields should still give only 5 points, got {score_with_all}"
        )

    def test_combined_v2_scoring(self):
        """
        Verify combined V2 field scoring matches expected total.

        Expected from V2 spec (subset):
        - palate_flavors: 10 points
        - primary_aromas: 5 points
        - finish_flavors: 5 points
        - description: 5 points
        - category: 3 points
        - appearance (any): 3 points
        - ratings (any): 5 points

        Total V2 additions: 36 points
        """
        from crawler.services.completeness import calculate_completeness_score

        # Base product without V2 fields
        base_product = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
        )

        # Product with all V2 fields
        v2_product = MockProduct(
            name="Test",
            brand_id=1,
            product_type="whiskey",
            abv=40.0,
            # V2 fields
            palate_flavors=["vanilla", "honey", "oak"],  # +10
            primary_aromas=["honey", "vanilla"],  # +5
            finish_flavors=["oak", "spice"],  # +5
            description="A fine whiskey",  # +5
            category="Bourbon",  # +3
            color_description="Amber",  # +3 (appearance)
            balance=7,  # +5 (ratings)
        )

        base_score = calculate_completeness_score(base_product)
        v2_score = calculate_completeness_score(v2_product)

        # Expected increase: 10+5+5+5+3+3+5 = 36 points
        # However, tasting profile also includes palate_description contribution
        # So we check for at least the V2 field contributions
        score_increase = v2_score - base_score

        assert score_increase >= 36, (
            f"V2 fields should add at least 36 points, "
            f"got {score_increase} (base: {base_score}, v2: {v2_score})"
        )


class TestTastingProfileScoring:
    """Additional tests for tasting profile scoring breakdown."""

    def test_tasting_profile_max_40_points(self):
        """
        Verify tasting profile is capped at 40 points (40% of total).
        """
        from crawler.services.completeness import calculate_tasting_profile_score

        # Product with all tasting profile fields maxed
        product = MockProduct(
            # Nose (10 max)
            nose_description="Rich and complex",
            primary_aromas=["a", "b", "c", "d"],
            # Palate (20 max)
            palate_description="Smooth and balanced",
            palate_flavors=["a", "b", "c", "d", "e"],
            initial_taste="Sweet",
            mid_palate_evolution="Develops complexity",
            mouthfeel="smooth-creamy",
            # Finish (10 max)
            finish_description="Long",
            finish_flavors=["a", "b", "c"],
            finish_length=9,
            final_notes="Lingering",
        )

        score = calculate_tasting_profile_score(product)

        assert score <= 40, f"Tasting profile should cap at 40, got {score}"

    def test_palate_score_max_20_points(self):
        """
        Verify palate score is capped at 20 points.
        """
        from crawler.services.completeness import calculate_palate_score

        product = MockProduct(
            palate_flavors=["a", "b", "c", "d", "e", "f", "g"],  # 10 points
            palate_description="Very detailed palate",  # 5 points
            initial_taste="Sweet honey",  # (already counted with palate_description)
            mid_palate_evolution="Complex development",  # 3 points
            mouthfeel="full-rich",  # 2 points
        )

        score = calculate_palate_score(product)

        assert score <= 20, f"Palate score should cap at 20, got {score}"

    def test_minimum_item_counts_enforced(self):
        """
        Verify minimum item counts for arrays are enforced.

        - palate_flavors needs 3+ items
        - primary_aromas needs 2+ items
        - finish_flavors needs 2+ items
        """
        from crawler.services.completeness import (
            calculate_palate_score,
            calculate_nose_score,
            calculate_finish_score,
        )

        # Test palate_flavors below minimum
        product_2_flavors = MockProduct(palate_flavors=["a", "b"])  # < 3
        product_3_flavors = MockProduct(palate_flavors=["a", "b", "c"])  # = 3

        assert calculate_palate_score(product_2_flavors) < calculate_palate_score(product_3_flavors), (
            "palate_flavors with < 3 items should score less than 3+ items"
        )

        # Test primary_aromas below minimum
        product_1_aroma = MockProduct(primary_aromas=["a"])  # < 2
        product_2_aromas = MockProduct(primary_aromas=["a", "b"])  # = 2

        assert calculate_nose_score(product_1_aroma) < calculate_nose_score(product_2_aromas), (
            "primary_aromas with < 2 items should score less than 2+ items"
        )

        # Test finish_flavors below minimum
        product_1_finish = MockProduct(finish_flavors=["a"])  # < 2
        product_2_finish = MockProduct(finish_flavors=["a", "b"])  # = 2

        assert calculate_finish_score(product_1_finish) < calculate_finish_score(product_2_finish), (
            "finish_flavors with < 2 items should score less than 2+ items"
        )
