# tests/integration/test_completeness_scoring.py
"""
Integration tests for Completeness Score Calculation.

Spec Reference: 05-UNIFIED-ARCHITECTURE.md Section 5.3 (lines 112-179)

Completeness Score Breakdown (100 points total):
| Category         | Points | Fields                                          |
|------------------|--------|-------------------------------------------------|
| Tasting Profile  | 40     | Palate (20), Nose (10), Finish (10)             |
| Identification   | 15     | name (10), brand (5)                            |
| Basic Info       | 15     | product_type (5), abv (5), description (5)      |
| Enrichment       | 20     | best_price (5), images (5), ratings (5), awards (5) |
| Verification     | 10     | source_count >= 2 (5), source_count >= 3 (5)    |

Tasting Profile Detail (40 points):
- Palate (20 pts): palate_flavors (10) + palate_description (5) + mid_palate (3) + mouthfeel (2)
- Nose (10 pts): nose_description (5) + primary_aromas (5)
- Finish (10 pts): finish_description (5) + finish_flavors (3) + finish_length (2)
"""
import pytest
import os
import uuid
from decimal import Decimal

pytestmark = [
    pytest.mark.django_db,
]


# ============================================================
# Test Data Constants
# ============================================================

COMPLETE_PRODUCT = {
    "name": "Ardbeg 10",
    "product_type": "whiskey",
    "abv": Decimal("46.0"),
    "description": "A classic Islay single malt",
    "nose_description": "Smoke and citrus",
    "primary_aromas": ["smoke", "lemon", "vanilla"],
    "palate_description": "Rich peat with sweetness",
    "palate_flavors": ["peat", "honey", "espresso"],
    "mid_palate_evolution": "Creamy texture",
    "mouthfeel": "Full-bodied",
    "finish_description": "Long and smoky",
    "finish_flavors": ["smoke", "pepper"],
    "finish_length": 8,
    "best_price": Decimal("49.99"),
    "images": [{"url": "https://example.com/ardbeg.jpg", "type": "bottle"}],
    "awards": [{"name": "Gold", "competition": "IWSC", "year": 2024}],
    "ratings": [{"score": 92, "source": "Whisky Advocate"}],
    "source_count": 3,
}


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def discovered_product_factory(db):
    """Factory to create DiscoveredProduct instances with specified fields."""
    from crawler.models import DiscoveredProduct, CrawlerSource, DiscoveredBrand

    # Create a default source
    source, _ = CrawlerSource.objects.get_or_create(
        slug="test-completeness-source",
        defaults={
            "name": "Test Completeness Source",
            "base_url": "https://example.com",
            "category": "retailer",
            "is_active": True,
        }
    )

    def _create_product(**kwargs):
        """Create a DiscoveredProduct with given kwargs."""
        # Handle brand specially
        brand = None
        if "brand" in kwargs:
            brand_name = kwargs.pop("brand")
            if brand_name:
                brand, _ = DiscoveredBrand.objects.get_or_create(
                    name=brand_name,
                    defaults={"slug": brand_name.lower().replace(" ", "-")}
                )

        # Generate unique source_url using UUID to avoid fingerprint collisions
        unique_id = uuid.uuid4().hex
        defaults = {
            "source_url": f"https://example.com/product/{unique_id}",
            "source": source,
        }
        defaults.update(kwargs)

        product = DiscoveredProduct(**defaults)
        if brand:
            product.brand = brand

        # Skip auto-calculation on first save to test manually
        product._skip_auto_update = True
        product.save()

        return product

    return _create_product


# ============================================================
# Test: Tasting Profile Scoring (40 points)
# ============================================================

class TestTastingProfileScoring:
    """
    Test tasting profile = 40% of score.

    Breakdown:
    - Palate (20 pts): palate_flavors (10) + palate_description (5) + mid_palate (3) + mouthfeel (2)
    - Nose (10 pts): nose_description (5) + primary_aromas (5)
    - Finish (10 pts): finish_description (5) + finish_flavors (3) + finish_length (2)
    """

    def test_tasting_profile_worth_40_points(self, discovered_product_factory):
        """
        Complete tasting profile should be worth 40 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            # Palate (20 pts)
            palate_flavors=["vanilla", "honey", "oak"],  # 10 pts
            palate_description="Rich and sweet",  # 5 pts
            mid_palate_evolution="Develops complexity",  # 3 pts
            mouthfeel="Full-bodied",  # 2 pts
            # Nose (10 pts)
            nose_description="Sweet vanilla and honey",  # 5 pts
            primary_aromas=["vanilla", "honey", "citrus"],  # 5 pts
            # Finish (10 pts)
            finish_description="Long and warming",  # 5 pts
            finish_flavors=["oak", "spice", "caramel"],  # 3 pts
            finish_length=8,  # 2 pts
        )

        score = product.calculate_completeness_score()

        # Name = 10, Tasting = 40, Total = 50
        # Verify tasting profile contributes 40 points
        assert score == 50, f"Expected 50 (10 name + 40 tasting), got {score}"

    def test_palate_worth_20_points(self, discovered_product_factory):
        """
        Palate breakdown:
        - palate_flavors: 10 points (requires 2+ flavors)
        - palate_description: 5 points
        - mid_palate: 3 points
        - mouthfeel: 2 points
        """
        # Test palate_flavors only (10 pts)
        product = discovered_product_factory(
            name="Test Whiskey",
            palate_flavors=["vanilla", "honey"],
        )
        score_flavors = product.calculate_completeness_score()
        assert score_flavors == 20, f"Expected 20 (10 name + 10 flavors), got {score_flavors}"

        # Test palate_description only (5 pts)
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            palate_description="Rich and sweet",
        )
        score_desc = product2.calculate_completeness_score()
        assert score_desc == 15, f"Expected 15 (10 name + 5 description), got {score_desc}"

        # Test mid_palate only (3 pts)
        product3 = discovered_product_factory(
            name="Test Whiskey 3",
            mid_palate_evolution="Develops complexity",
        )
        score_mid = product3.calculate_completeness_score()
        assert score_mid == 13, f"Expected 13 (10 name + 3 mid_palate), got {score_mid}"

        # Test mouthfeel only (2 pts)
        product4 = discovered_product_factory(
            name="Test Whiskey 4",
            mouthfeel="Full-bodied",
        )
        score_mouthfeel = product4.calculate_completeness_score()
        assert score_mouthfeel == 12, f"Expected 12 (10 name + 2 mouthfeel), got {score_mouthfeel}"

        # Test all palate fields (20 pts max, capped)
        product5 = discovered_product_factory(
            name="Test Whiskey 5",
            palate_flavors=["vanilla", "honey", "oak"],
            palate_description="Rich and sweet",
            mid_palate_evolution="Develops complexity",
            mouthfeel="Full-bodied",
        )
        score_all = product5.calculate_completeness_score()
        assert score_all == 30, f"Expected 30 (10 name + 20 palate), got {score_all}"

    def test_palate_flavors_requires_2_or_more(self, discovered_product_factory):
        """
        palate_flavors only scores 10 points if there are 2 or more flavors.
        """
        # Single flavor = 0 pts
        product = discovered_product_factory(
            name="Test Whiskey",
            palate_flavors=["vanilla"],
        )
        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only, single flavor=0), got {score}"

        # Two flavors = 10 pts
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            palate_flavors=["vanilla", "honey"],
        )
        score2 = product2.calculate_completeness_score()
        assert score2 == 20, f"Expected 20 (10 name + 10 flavors), got {score2}"

    def test_nose_worth_10_points(self, discovered_product_factory):
        """
        Nose breakdown:
        - nose_description: 5 points
        - primary_aromas: 5 points (requires 2+ aromas)
        """
        # Test nose_description only (5 pts)
        product = discovered_product_factory(
            name="Test Whiskey",
            nose_description="Sweet vanilla and honey",
        )
        score_desc = product.calculate_completeness_score()
        assert score_desc == 15, f"Expected 15 (10 name + 5 nose_desc), got {score_desc}"

        # Test primary_aromas only (5 pts) - requires 2+
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            primary_aromas=["vanilla", "honey"],
        )
        score_aromas = product2.calculate_completeness_score()
        assert score_aromas == 15, f"Expected 15 (10 name + 5 aromas), got {score_aromas}"

        # Test both (10 pts max)
        product3 = discovered_product_factory(
            name="Test Whiskey 3",
            nose_description="Sweet vanilla and honey",
            primary_aromas=["vanilla", "honey", "citrus"],
        )
        score_both = product3.calculate_completeness_score()
        assert score_both == 20, f"Expected 20 (10 name + 10 nose), got {score_both}"

    def test_primary_aromas_requires_2_or_more(self, discovered_product_factory):
        """
        primary_aromas only scores 5 points if there are 2 or more aromas.
        """
        # Single aroma = 0 pts
        product = discovered_product_factory(
            name="Test Whiskey",
            primary_aromas=["vanilla"],
        )
        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only, single aroma=0), got {score}"

        # Two aromas = 5 pts
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            primary_aromas=["vanilla", "honey"],
        )
        score2 = product2.calculate_completeness_score()
        assert score2 == 15, f"Expected 15 (10 name + 5 aromas), got {score2}"

    def test_finish_worth_10_points(self, discovered_product_factory):
        """
        Finish breakdown:
        - finish_description: 5 points
        - finish_flavors: 3 points (requires 2+ flavors)
        - finish_length: 2 points
        """
        # Test finish_description only (5 pts)
        product = discovered_product_factory(
            name="Test Whiskey",
            finish_description="Long and warming",
        )
        score_desc = product.calculate_completeness_score()
        assert score_desc == 15, f"Expected 15 (10 name + 5 finish_desc), got {score_desc}"

        # Test finish_flavors only (3 pts) - requires 2+
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            finish_flavors=["oak", "spice"],
        )
        score_flavors = product2.calculate_completeness_score()
        assert score_flavors == 13, f"Expected 13 (10 name + 3 flavors), got {score_flavors}"

        # Test finish_length only (2 pts)
        product3 = discovered_product_factory(
            name="Test Whiskey 3",
            finish_length=8,
        )
        score_length = product3.calculate_completeness_score()
        assert score_length == 12, f"Expected 12 (10 name + 2 length), got {score_length}"

        # Test all (10 pts max)
        product4 = discovered_product_factory(
            name="Test Whiskey 4",
            finish_description="Long and warming",
            finish_flavors=["oak", "spice", "caramel"],
            finish_length=8,
        )
        score_all = product4.calculate_completeness_score()
        assert score_all == 20, f"Expected 20 (10 name + 10 finish), got {score_all}"

    def test_finish_flavors_requires_2_or_more(self, discovered_product_factory):
        """
        finish_flavors only scores 3 points if there are 2 or more flavors.
        """
        # Single flavor = 0 pts
        product = discovered_product_factory(
            name="Test Whiskey",
            finish_flavors=["oak"],
        )
        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only, single flavor=0), got {score}"

        # Two flavors = 3 pts
        product2 = discovered_product_factory(
            name="Test Whiskey 2",
            finish_flavors=["oak", "spice"],
        )
        score2 = product2.calculate_completeness_score()
        assert score2 == 13, f"Expected 13 (10 name + 3 flavors), got {score2}"


# ============================================================
# Test: Identification Scoring (15 points)
# ============================================================

class TestIdentificationScoring:
    """
    Test identification = 15% of score.

    Breakdown:
    - name: 10 points
    - brand: 5 points
    """

    def test_identification_worth_15_points(self, discovered_product_factory):
        """
        Identification breakdown:
        - name: 10 points
        - brand: 5 points
        """
        product = discovered_product_factory(
            name="Ardbeg 10",
            brand="Ardbeg",
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 brand), got {score}"

    def test_name_alone_worth_10_points(self, discovered_product_factory):
        """
        Product with only name should have 10 points.
        """
        product = discovered_product_factory(
            name="Ardbeg 10",
        )

        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only), got {score}"

    def test_brand_alone_worth_5_points(self, discovered_product_factory):
        """
        Product with only brand should have 5 points.
        """
        product = discovered_product_factory(
            brand="Ardbeg",
        )

        score = product.calculate_completeness_score()
        assert score == 5, f"Expected 5 (brand only), got {score}"

    def test_no_identification_is_0_points(self, discovered_product_factory):
        """
        Product with no name or brand should have 0 identification points.
        """
        product = discovered_product_factory()

        score = product.calculate_completeness_score()
        assert score == 0, f"Expected 0 (no identification), got {score}"


# ============================================================
# Test: Basic Info Scoring (15 points)
# ============================================================

class TestBasicInfoScoring:
    """
    Test basic info = 15% of score.

    Breakdown:
    - product_type: 5 points
    - abv: 5 points
    - description: 5 points
    """

    def test_basic_info_worth_15_points(self, discovered_product_factory):
        """
        Basic info breakdown:
        - product_type: 5 points
        - abv: 5 points
        - description: 5 points
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            product_type="whiskey",
            abv=Decimal("46.0"),
            description="A classic single malt",
        )

        score = product.calculate_completeness_score()
        # 10 name + 5 type + 5 abv + 5 desc = 25
        assert score == 25, f"Expected 25, got {score}"

    def test_product_type_worth_5_points(self, discovered_product_factory):
        """
        Product type alone contributes 5 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            product_type="whiskey",
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 type), got {score}"

    def test_abv_worth_5_points(self, discovered_product_factory):
        """
        ABV alone contributes 5 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            abv=Decimal("46.0"),
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 abv), got {score}"

    def test_description_worth_5_points(self, discovered_product_factory):
        """
        Description alone contributes 5 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            description="A classic single malt whisky",
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 description), got {score}"


# ============================================================
# Test: Enrichment Scoring (20 points)
# ============================================================

class TestEnrichmentScoring:
    """
    Test enrichment = 20% of score.

    Breakdown:
    - best_price: 5 points
    - images: 5 points
    - ratings: 5 points
    - awards: 5 points
    """

    def test_enrichment_worth_20_points(self, discovered_product_factory):
        """
        Enrichment breakdown:
        - best_price: 5 points
        - images: 5 points
        - ratings: 5 points
        - awards: 5 points
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            best_price=Decimal("49.99"),
            images=[{"url": "https://example.com/image.jpg"}],
            ratings=[{"score": 92, "source": "Whisky Advocate"}],
            awards=[{"name": "Gold", "competition": "IWSC"}],
        )

        score = product.calculate_completeness_score()
        # 10 name + 5 price + 5 images + 5 ratings + 5 awards = 30
        assert score == 30, f"Expected 30 (10 name + 20 enrichment), got {score}"

    def test_best_price_worth_5_points(self, discovered_product_factory):
        """
        Best price alone contributes 5 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            best_price=Decimal("49.99"),
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 price), got {score}"

    def test_images_worth_5_points(self, discovered_product_factory):
        """
        Images alone contribute 5 points (requires at least 1 image).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            images=[{"url": "https://example.com/image.jpg"}],
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 images), got {score}"

    def test_empty_images_worth_0_points(self, discovered_product_factory):
        """
        Empty images list contributes 0 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            images=[],
        )

        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only), got {score}"

    def test_ratings_worth_5_points(self, discovered_product_factory):
        """
        Ratings alone contribute 5 points (requires at least 1 rating).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            ratings=[{"score": 92}],
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 ratings), got {score}"

    def test_empty_ratings_worth_0_points(self, discovered_product_factory):
        """
        Empty ratings list contributes 0 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            ratings=[],
        )

        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only), got {score}"

    def test_awards_worth_5_points(self, discovered_product_factory):
        """
        Awards alone contribute 5 points (requires at least 1 award).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            awards=[{"name": "Gold", "competition": "IWSC"}],
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 awards), got {score}"

    def test_empty_awards_worth_0_points(self, discovered_product_factory):
        """
        Empty awards list contributes 0 points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            awards=[],
        )

        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only), got {score}"


# ============================================================
# Test: Verification Scoring (10 points)
# ============================================================

class TestVerificationScoring:
    """
    Test verification = 10% of score.

    Breakdown:
    - source_count >= 2: 5 points
    - source_count >= 3: 5 points (additional)
    """

    def test_verification_worth_10_points(self, discovered_product_factory):
        """
        Verification breakdown:
        - source_count >= 2: 5 points
        - source_count >= 3: 5 points (additional)
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            source_count=3,
        )

        score = product.calculate_completeness_score()
        # 10 name + 5 (>=2) + 5 (>=3) = 20
        assert score == 20, f"Expected 20 (10 name + 10 verification), got {score}"

    def test_source_count_1_gives_0_verification_points(self, discovered_product_factory):
        """
        Single source gives no verification points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            source_count=1,
        )

        score = product.calculate_completeness_score()
        assert score == 10, f"Expected 10 (name only), got {score}"

    def test_source_count_2_gives_5_verification_points(self, discovered_product_factory):
        """
        Two sources gives 5 verification points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            source_count=2,
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 verification), got {score}"

    def test_source_count_3_gives_10_verification_points(self, discovered_product_factory):
        """
        Three+ sources gives full 10 verification points.
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            source_count=3,
        )

        score = product.calculate_completeness_score()
        assert score == 20, f"Expected 20 (10 name + 10 verification), got {score}"

    def test_source_count_4_gives_10_verification_points(self, discovered_product_factory):
        """
        Four+ sources still gives only 10 verification points (capped).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            source_count=4,
        )

        score = product.calculate_completeness_score()
        assert score == 20, f"Expected 20 (10 name + 10 verification), got {score}"


# ============================================================
# Test: Total Scoring
# ============================================================

class TestTotalScoring:
    """
    Test total score calculation.
    """

    def test_total_is_exactly_100_points(self, discovered_product_factory):
        """
        Complete product with all fields should score exactly 100.
        """
        product = discovered_product_factory(
            # Identification (15 pts)
            name="Ardbeg 10",  # 10 pts
            brand="Ardbeg",  # 5 pts
            # Basic Info (15 pts)
            product_type="whiskey",  # 5 pts
            abv=Decimal("46.0"),  # 5 pts
            description="A classic Islay single malt",  # 5 pts
            # Tasting Profile (40 pts)
            # Palate (20 pts)
            palate_flavors=["peat", "honey", "espresso"],  # 10 pts
            palate_description="Rich peat with sweetness",  # 5 pts
            mid_palate_evolution="Creamy texture",  # 3 pts
            mouthfeel="Full-bodied",  # 2 pts
            # Nose (10 pts)
            nose_description="Smoke and citrus",  # 5 pts
            primary_aromas=["smoke", "lemon", "vanilla"],  # 5 pts
            # Finish (10 pts)
            finish_description="Long and smoky",  # 5 pts
            finish_flavors=["smoke", "pepper"],  # 3 pts
            finish_length=8,  # 2 pts
            # Enrichment (20 pts)
            best_price=Decimal("49.99"),  # 5 pts
            images=[{"url": "https://example.com/ardbeg.jpg"}],  # 5 pts
            ratings=[{"score": 92, "source": "Whisky Advocate"}],  # 5 pts
            awards=[{"name": "Gold", "competition": "IWSC"}],  # 5 pts
            # Verification (10 pts)
            source_count=3,  # 10 pts (5+5)
        )

        score = product.calculate_completeness_score()
        assert score == 100, f"Expected exactly 100, got {score}"

    def test_empty_product_scores_0(self, discovered_product_factory):
        """
        Product with no data should score 0.
        """
        product = discovered_product_factory()

        score = product.calculate_completeness_score()
        assert score == 0, f"Expected 0, got {score}"

    def test_typical_product_scores_correctly(self, discovered_product_factory):
        """
        A typical product with partial data should score correctly.

        Example: Product from retailer page with:
        - name, brand, product_type, abv, description
        - price, images
        - No tasting notes
        - Single source

        Expected: 10 + 5 + 5 + 5 + 5 + 5 + 5 = 40
        """
        product = discovered_product_factory(
            name="Glenfiddich 12",
            brand="Glenfiddich",
            product_type="whiskey",
            abv=Decimal("40.0"),
            description="A classic Speyside single malt",
            best_price=Decimal("34.99"),
            images=[{"url": "https://example.com/glenfiddich.jpg"}],
            source_count=1,
        )

        score = product.calculate_completeness_score()
        assert score == 40, f"Expected 40, got {score}"

    def test_score_capped_at_100(self, discovered_product_factory):
        """
        Score should never exceed 100 even with extra data.
        """
        product = discovered_product_factory(
            # All fields filled (would be 100 points)
            name="Ardbeg 10",
            brand="Ardbeg",
            product_type="whiskey",
            abv=Decimal("46.0"),
            description="A classic Islay single malt",
            palate_flavors=["peat", "honey", "espresso"],
            palate_description="Rich peat with sweetness",
            mid_palate_evolution="Creamy texture",
            mouthfeel="Full-bodied",
            nose_description="Smoke and citrus",
            primary_aromas=["smoke", "lemon", "vanilla"],
            finish_description="Long and smoky",
            finish_flavors=["smoke", "pepper"],
            finish_length=8,
            best_price=Decimal("49.99"),
            images=[{"url": "https://example.com/ardbeg.jpg"}],
            ratings=[{"score": 92}, {"score": 94}],  # Multiple ratings
            awards=[{"name": "Gold"}, {"name": "Silver"}],  # Multiple awards
            source_count=5,  # More than 3 sources
        )

        score = product.calculate_completeness_score()
        assert score == 100, f"Expected 100 (capped), got {score}"


# ============================================================
# Test: Alternative Field Names (Spec Aliases)
# ============================================================

class TestAlternativeFieldNames:
    """
    Test that alternative field names work correctly.

    The implementation allows:
    - initial_taste as alternative to palate_description
    - final_notes as alternative to finish_description
    """

    def test_initial_taste_counts_as_palate_description(self, discovered_product_factory):
        """
        initial_taste should count towards palate_description points (5 pts).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            initial_taste="Sweet vanilla on entry",
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 initial_taste), got {score}"

    def test_final_notes_counts_as_finish_description(self, discovered_product_factory):
        """
        final_notes should count towards finish_description points (5 pts).
        """
        product = discovered_product_factory(
            name="Test Whiskey",
            final_notes="Lingering oak and vanilla",
        )

        score = product.calculate_completeness_score()
        assert score == 15, f"Expected 15 (10 name + 5 final_notes), got {score}"


# ============================================================
# Test: Category Totals Verification
# ============================================================

class TestCategoryTotals:
    """
    Verify that each category sums to the correct total.
    """

    def test_all_categories_sum_to_100(self, discovered_product_factory):
        """
        All category maximums should sum to exactly 100.

        - Identification: 15
        - Basic Info: 15
        - Tasting Profile: 40
        - Enrichment: 20
        - Verification: 10
        Total: 100
        """
        # Identification only (15)
        prod_id = discovered_product_factory(name="Test ID", brand="Brand ID")
        score_id = prod_id.calculate_completeness_score()

        # Basic Info only (15) - need to subtract name
        prod_basic = discovered_product_factory(
            name="Test Basic",
            product_type="whiskey",
            abv=Decimal("40.0"),
            description="Test desc",
        )
        score_basic = prod_basic.calculate_completeness_score() - 10  # Subtract name

        # Tasting only (40) - need to subtract name
        prod_tasting = discovered_product_factory(
            name="Test Tasting",
            palate_flavors=["a", "b"],
            palate_description="palate",
            mid_palate_evolution="mid",
            mouthfeel="full",
            nose_description="nose",
            primary_aromas=["c", "d"],
            finish_description="finish",
            finish_flavors=["e", "f"],
            finish_length=8,
        )
        score_tasting = prod_tasting.calculate_completeness_score() - 10  # Subtract name

        # Enrichment only (20) - need to subtract name
        prod_enrichment = discovered_product_factory(
            name="Test Enrichment",
            best_price=Decimal("50.0"),
            images=[{"url": "test"}],
            ratings=[{"score": 90}],
            awards=[{"name": "Gold"}],
        )
        score_enrichment = prod_enrichment.calculate_completeness_score() - 10  # Subtract name

        # Verification only (10) - need to subtract name
        prod_verify = discovered_product_factory(
            name="Test Verify",
            source_count=3,
        )
        score_verify = prod_verify.calculate_completeness_score() - 10  # Subtract name

        # Verify each category max
        assert score_id == 15, f"Identification should be 15, got {score_id}"
        assert score_basic == 15, f"Basic Info should be 15, got {score_basic}"
        assert score_tasting == 40, f"Tasting should be 40, got {score_tasting}"
        assert score_enrichment == 20, f"Enrichment should be 20, got {score_enrichment}"
        assert score_verify == 10, f"Verification should be 10, got {score_verify}"

        # Verify total (subtract the 10 for name that's included in identification)
        total = score_id + score_basic + score_tasting + score_enrichment + score_verify - 10
        assert total == 90, f"Categories (minus one name) should sum to 90, got {total}"
