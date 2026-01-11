"""
Completeness Score TDD Tests - Phase 2

Spec Reference: docs/spec-parts/05-UNIFIED-ARCHITECTURE.md, Section 5.3

These tests verify that completeness scoring matches the spec exactly.
Written FIRST according to TDD methodology - tests MUST FAIL before implementation.

Spec Point Breakdown (100 total):
- Identification: 15 points (name=10, brand=5)
- Basic Info: 15 points (product_type=5, abv=5, description=5)
- Tasting Profile: 40 points
  - Palate: 20 points (palate_flavors>=2=10, palate_description/initial_taste=5, mid_palate_evolution=3, mouthfeel=2)
  - Nose: 10 points (nose_description=5, primary_aromas>=2=5)
  - Finish: 10 points (finish_description/final_notes=5, finish_flavors>=2=3, finish_length=2)
- Enrichment: 20 points (best_price=5, images=5, ratings=5, awards=5)
- Verification: 10 points (source_count>=2=5, source_count>=3=5)
"""

from decimal import Decimal
from django.test import TestCase

from crawler.models import DiscoveredProduct, DiscoveredBrand


class TestCompletenessIdentification(TestCase):
    """Tests for Identification section (15 points max)."""

    def test_name_worth_10_points(self):
        """Spec: name = 10 points"""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            # NOT setting product_type to isolate name's contribution
        )
        score = product.calculate_completeness_score()
        # Only name populated = 10 points
        self.assertEqual(score, 10)

    def test_brand_worth_5_points(self):
        """Spec: brand = 5 points"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            # NOT setting product_type to isolate identification section
            brand=brand,
        )
        score = product.calculate_completeness_score()
        # name(10) + brand(5) = 15
        self.assertEqual(score, 15)

    def test_identification_max_15_points(self):
        """Spec: Identification section max = 15 points"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey",
            # NOT setting product_type to isolate identification section
            brand=brand,
            gtin="12345678901234",  # GTIN not in scoring per spec
        )
        score = product.calculate_completeness_score()
        # name(10) + brand(5) = 15 (GTIN not scored)
        self.assertEqual(score, 15)


class TestCompletenessBasicInfo(TestCase):
    """Tests for Basic Product Info section (15 points max)."""

    def test_product_type_worth_5_points(self):
        """Spec: product_type = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
        )
        score = product.calculate_completeness_score()
        self.assertEqual(score, 5)

    def test_abv_worth_5_points(self):
        """Spec: abv = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            abv=Decimal("43.0"),
        )
        score = product.calculate_completeness_score()
        # product_type(5) + abv(5) = 10
        self.assertEqual(score, 10)

    def test_description_worth_5_points(self):
        """Spec: description = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            description="A fine whiskey.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + description(5) = 10
        self.assertEqual(score, 10)

    def test_basic_info_max_15_points(self):
        """Spec: Basic info section max = 15 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine whiskey.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + abv(5) + description(5) = 15
        self.assertEqual(score, 15)


class TestCompletenessTastingPalate(TestCase):
    """Tests for Tasting Profile - Palate section (20 points max)."""

    def test_palate_flavors_worth_10_points(self):
        """Spec: palate_flavors with >=2 items = 10 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_flavors=["vanilla", "oak", "honey"],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + palate_flavors(10) = 15
        self.assertEqual(score, 15)

    def test_palate_flavors_needs_at_least_2(self):
        """Spec: palate_flavors needs >= 2 items for points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_flavors=["vanilla"],  # Only 1 item
        )
        score = product.calculate_completeness_score()
        # product_type(5) + palate_flavors(0 - only 1 item) = 5
        self.assertEqual(score, 5)

    def test_palate_description_worth_5_points(self):
        """Spec: palate_description = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_description="Rich and smooth with vanilla notes.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + palate_description(5) = 10
        self.assertEqual(score, 10)

    def test_initial_taste_worth_5_points(self):
        """Spec: initial_taste (alternative to palate_description) = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            initial_taste="Sweet entry with honey.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + initial_taste(5) = 10
        self.assertEqual(score, 10)

    def test_mid_palate_evolution_worth_3_points(self):
        """Spec: mid_palate_evolution = 3 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            mid_palate_evolution="Develops spicy notes.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + mid_palate_evolution(3) = 8
        self.assertEqual(score, 8)

    def test_mouthfeel_worth_2_points(self):
        """Spec: mouthfeel = 2 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            mouthfeel="full_rich",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + mouthfeel(2) = 7
        self.assertEqual(score, 7)

    def test_palate_section_max_20_points(self):
        """Spec: Palate section capped at 20 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            palate_flavors=["vanilla", "oak", "honey"],  # 10
            palate_description="Rich and smooth.",  # 5
            initial_taste="Sweet entry.",  # Would add 5 more but capped
            mid_palate_evolution="Develops spice.",  # 3
            mouthfeel="full_rich",  # 2
        )
        score = product.calculate_completeness_score()
        # product_type(5) + palate(min(10+5+3+2, 20)) = 5 + 20 = 25
        self.assertEqual(score, 25)


class TestCompletenessTastingNose(TestCase):
    """Tests for Tasting Profile - Nose section (10 points max)."""

    def test_nose_description_worth_5_points(self):
        """Spec: nose_description = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            nose_description="Fruity with hints of peat.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + nose_description(5) = 10
        self.assertEqual(score, 10)

    def test_primary_aromas_worth_5_points(self):
        """Spec: primary_aromas with >=2 items = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            primary_aromas=["fruit", "peat", "smoke"],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + primary_aromas(5) = 10
        self.assertEqual(score, 10)

    def test_primary_aromas_needs_at_least_2(self):
        """Spec: primary_aromas needs >= 2 items for points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            primary_aromas=["fruit"],  # Only 1 item
        )
        score = product.calculate_completeness_score()
        # product_type(5) + primary_aromas(0) = 5
        self.assertEqual(score, 5)

    def test_nose_section_max_10_points(self):
        """Spec: Nose section capped at 10 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            nose_description="Fruity with hints of peat.",  # 5
            primary_aromas=["fruit", "peat", "smoke"],  # 5
        )
        score = product.calculate_completeness_score()
        # product_type(5) + nose(min(5+5, 10)) = 5 + 10 = 15
        self.assertEqual(score, 15)


class TestCompletenessTastingFinish(TestCase):
    """Tests for Tasting Profile - Finish section (10 points max)."""

    def test_finish_description_worth_5_points(self):
        """Spec: finish_description = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            finish_description="Long and warming.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + finish_description(5) = 10
        self.assertEqual(score, 10)

    def test_final_notes_worth_5_points(self):
        """Spec: final_notes (alternative to finish_description) = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            final_notes="Lingering spice.",
        )
        score = product.calculate_completeness_score()
        # product_type(5) + final_notes(5) = 10
        self.assertEqual(score, 10)

    def test_finish_flavors_worth_3_points(self):
        """Spec: finish_flavors with >=2 items = 3 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            finish_flavors=["spice", "oak"],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + finish_flavors(3) = 8
        self.assertEqual(score, 8)

    def test_finish_length_worth_2_points(self):
        """Spec: finish_length = 2 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            finish_length=8,  # 1-10 scale
        )
        score = product.calculate_completeness_score()
        # product_type(5) + finish_length(2) = 7
        self.assertEqual(score, 7)

    def test_finish_section_max_10_points(self):
        """Spec: Finish section capped at 10 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            finish_description="Long and warming.",  # 5
            final_notes="Lingering spice.",  # Would add 5 more but only one counts
            finish_flavors=["spice", "oak"],  # 3
            finish_length=8,  # 2
        )
        score = product.calculate_completeness_score()
        # product_type(5) + finish(min(5+3+2, 10)) = 5 + 10 = 15
        self.assertEqual(score, 15)


class TestCompletenessEnrichment(TestCase):
    """Tests for Enrichment Data section (20 points max)."""

    def test_best_price_worth_5_points(self):
        """Spec: best_price = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            best_price=Decimal("49.99"),
        )
        score = product.calculate_completeness_score()
        # product_type(5) + best_price(5) = 10
        self.assertEqual(score, 10)

    def test_images_worth_5_points(self):
        """Spec: has_images = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            images=[{"url": "http://example.com/img.jpg"}],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + images(5) = 10
        self.assertEqual(score, 10)

    def test_ratings_worth_5_points(self):
        """Spec: has_ratings = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            ratings=[{"source": "test", "score": 90}],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + ratings(5) = 10
        self.assertEqual(score, 10)

    def test_awards_worth_5_points(self):
        """Spec: has_awards = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            awards=[{"name": "Gold Medal", "competition": "SFWSC"}],
        )
        score = product.calculate_completeness_score()
        # product_type(5) + awards(5) = 10
        self.assertEqual(score, 10)

    def test_enrichment_max_20_points(self):
        """Spec: Enrichment section max = 20 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            best_price=Decimal("49.99"),  # 5
            images=[{"url": "http://example.com/img.jpg"}],  # 5
            ratings=[{"source": "test", "score": 90}],  # 5
            awards=[{"name": "Gold Medal"}],  # 5
        )
        score = product.calculate_completeness_score()
        # product_type(5) + enrichment(20) = 25
        self.assertEqual(score, 25)


class TestCompletenessVerification(TestCase):
    """Tests for Verification Bonus section (10 points max)."""

    def test_source_count_2_worth_5_points(self):
        """Spec: source_count >= 2 = 5 points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            source_count=2,
        )
        score = product.calculate_completeness_score()
        # product_type(5) + verification(5) = 10
        self.assertEqual(score, 10)

    def test_source_count_3_worth_10_points(self):
        """Spec: source_count >= 3 = 10 points total"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            source_count=3,
        )
        score = product.calculate_completeness_score()
        # product_type(5) + verification(5+5) = 15
        self.assertEqual(score, 15)

    def test_source_count_1_worth_0_points(self):
        """Spec: source_count < 2 = 0 verification points"""
        product = DiscoveredProduct.objects.create(
            product_type="whiskey",
            source_count=1,
        )
        score = product.calculate_completeness_score()
        # product_type(5) + verification(0) = 5
        self.assertEqual(score, 5)


class TestCompletenessTotalScore(TestCase):
    """Tests for total score calculation."""

    def test_empty_product_score_0(self):
        """Empty product should have score 0."""
        product = DiscoveredProduct.objects.create()
        score = product.calculate_completeness_score()
        self.assertEqual(score, 0)

    def test_max_score_is_100(self):
        """Spec: Total max score = 100"""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            # Identification (15)
            name="Test Whiskey 12 Year",
            brand=brand,
            # Basic Info (15)
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine single malt.",
            # Palate (20)
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Rich and smooth.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            # Nose (10)
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke"],
            # Finish (10)
            finish_description="Long and warming.",
            finish_flavors=["spice", "oak"],
            finish_length=8,
            # Enrichment (20)
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            ratings=[{"source": "test", "score": 90}],
            awards=[{"name": "Gold Medal"}],
            # Verification (10)
            source_count=3,
        )
        score = product.calculate_completeness_score()
        self.assertEqual(score, 100)

    def test_score_cannot_exceed_100(self):
        """Score should be capped at 100 even with extra data."""
        brand = DiscoveredBrand.objects.create(name="Test Brand", slug="test-brand")
        product = DiscoveredProduct.objects.create(
            # All fields maxed out plus extras
            name="Test Whiskey 12 Year",
            brand=brand,
            product_type="whiskey",
            abv=Decimal("43.0"),
            description="A fine single malt.",
            palate_flavors=["vanilla", "oak", "honey", "caramel"],
            palate_description="Rich and smooth.",
            initial_taste="Sweet entry.",
            mid_palate_evolution="Develops spice.",
            mouthfeel="full_rich",
            nose_description="Fruity and peaty.",
            primary_aromas=["fruit", "peat", "smoke", "honey"],
            secondary_aromas=["earth", "leather"],
            finish_description="Long and warming.",
            final_notes="Lingering.",
            finish_flavors=["spice", "oak", "smoke"],
            finish_length=8,
            best_price=Decimal("49.99"),
            images=[{"url": "http://example.com/img.jpg"}],
            ratings=[{"source": "test", "score": 90}],
            awards=[{"name": "Gold Medal"}],
            source_count=5,
        )
        score = product.calculate_completeness_score()
        self.assertLessEqual(score, 100)
