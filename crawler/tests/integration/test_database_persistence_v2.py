"""
Integration tests for database persistence - AI Enhancement Service V2.

Task 7.5: Integration Test - Database Persistence

These tests verify that all V2 fields are correctly persisted to the database,
including:
- Array fields (palate_flavors, primary_aromas, finish_flavors, etc.)
- JSON fields (nested objects like ratings, appearance)
- WhiskeyDetails and PortWineDetails relations
- Completeness score calculation
- Product status transitions

Uses Django TestCase for database transactions and rollback.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from crawler.models import (
    DiscoveredProduct,
    DiscoveredBrand,
    WhiskeyDetails,
    PortWineDetails,
    CrawlerSource,
    ProductType,
    DiscoveredProductStatus,
    WhiskeyTypeChoices,
    PortStyleChoices,
)
from crawler.services.completeness import (
    calculate_completeness_score,
    determine_status,
    has_palate_data,
)


class TestArrayFieldsPersistence(TestCase):
    """Test that array fields are correctly saved to and loaded from the database."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="Test Brand",
            slug="test-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="Test Source",
            slug="test-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_palate_flavors_saved_to_database(self):
        """Verify palate_flavors array saves and loads correctly."""
        palate_flavors = ["vanilla", "oak", "honey", "spice", "caramel"]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Palate",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/1",
            raw_content="Test content",
            palate_flavors=palate_flavors,
        )

        # Reload from database
        product.refresh_from_db()

        self.assertEqual(product.palate_flavors, palate_flavors)
        self.assertEqual(len(product.palate_flavors), 5)
        self.assertIn("vanilla", product.palate_flavors)
        self.assertIn("caramel", product.palate_flavors)

    def test_primary_aromas_saved_to_database(self):
        """Verify primary_aromas array saves and loads correctly."""
        primary_aromas = ["honey", "vanilla", "floral", "citrus"]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Aromas",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/2",
            raw_content="Test content",
            primary_aromas=primary_aromas,
        )

        product.refresh_from_db()

        self.assertEqual(product.primary_aromas, primary_aromas)
        self.assertEqual(len(product.primary_aromas), 4)
        self.assertIn("honey", product.primary_aromas)

    def test_finish_flavors_saved_to_database(self):
        """Verify finish_flavors array saves and loads correctly."""
        finish_flavors = ["oak", "spice", "tobacco", "leather"]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Finish",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/3",
            raw_content="Test content",
            finish_flavors=finish_flavors,
        )

        product.refresh_from_db()

        self.assertEqual(product.finish_flavors, finish_flavors)
        self.assertEqual(len(product.finish_flavors), 4)
        self.assertIn("tobacco", product.finish_flavors)

    def test_secondary_aromas_saved_to_database(self):
        """Verify secondary_aromas array saves and loads correctly."""
        secondary_aromas = ["citrus", "floral", "heather", "peat"]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Secondary",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/4",
            raw_content="Test content",
            secondary_aromas=secondary_aromas,
        )

        product.refresh_from_db()

        self.assertEqual(product.secondary_aromas, secondary_aromas)
        self.assertEqual(len(product.secondary_aromas), 4)

    def test_cask_arrays_saved_to_database(self):
        """Verify cask-related array fields save correctly."""
        primary_cask = ["ex-bourbon", "sherry"]
        finishing_cask = ["port", "madeira"]
        wood_type = ["american_oak", "european_oak"]
        cask_treatment = ["charred", "toasted"]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Casks",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/5",
            raw_content="Test content",
            primary_cask=primary_cask,
            finishing_cask=finishing_cask,
            wood_type=wood_type,
            cask_treatment=cask_treatment,
        )

        product.refresh_from_db()

        self.assertEqual(product.primary_cask, primary_cask)
        self.assertEqual(product.finishing_cask, finishing_cask)
        self.assertEqual(product.wood_type, wood_type)
        self.assertEqual(product.cask_treatment, cask_treatment)

    def test_empty_arrays_saved_correctly(self):
        """Verify empty arrays are saved and loaded as empty lists."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Empty",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/6",
            raw_content="Test content",
            palate_flavors=[],
            primary_aromas=[],
            finish_flavors=[],
        )

        product.refresh_from_db()

        self.assertEqual(product.palate_flavors, [])
        self.assertEqual(product.primary_aromas, [])
        self.assertEqual(product.finish_flavors, [])

    def test_array_update_persists(self):
        """Verify updating array fields persists correctly."""
        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Update",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/7",
            raw_content="Test content",
            palate_flavors=["vanilla"],
        )

        # Update the array
        product.palate_flavors = ["vanilla", "oak", "honey", "spice"]
        product.save()

        # Reload and verify
        product.refresh_from_db()
        self.assertEqual(len(product.palate_flavors), 4)
        self.assertIn("spice", product.palate_flavors)


class TestJSONFieldsPersistence(TestCase):
    """Test that JSON/nested object fields are correctly saved to the database."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="JSON Test Brand",
            slug="json-test-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="JSON Test Source",
            slug="json-test-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_ratings_json_field_saved_correctly(self):
        """Verify ratings JSON field saves and loads correctly."""
        ratings = [
            {
                "source": "Whisky Advocate",
                "score": 92,
                "max_score": 100,
                "reviewer": "John Doe",
                "date": "2024-01-15",
                "url": "https://whiskyadvocate.com/review/1",
            },
            {
                "source": "Wine Enthusiast",
                "score": 88,
                "max_score": 100,
                "reviewer": "Jane Smith",
                "date": "2024-02-20",
            },
        ]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Ratings",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/8",
            raw_content="Test content",
            ratings=ratings,
        )

        product.refresh_from_db()

        self.assertEqual(len(product.ratings), 2)
        self.assertEqual(product.ratings[0]["source"], "Whisky Advocate")
        self.assertEqual(product.ratings[0]["score"], 92)
        self.assertEqual(product.ratings[1]["reviewer"], "Jane Smith")

    def test_awards_json_field_saved_correctly(self):
        """Verify awards JSON field saves and loads correctly."""
        awards = [
            {
                "competition": "IWSC",
                "year": 2024,
                "medal": "Gold",
                "category": "Scotch Single Malt",
            },
            {
                "competition": "San Francisco World Spirits",
                "year": 2024,
                "medal": "Double Gold",
                "category": "Single Malt Whiskey",
            },
        ]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Awards",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/9",
            raw_content="Test content",
            awards=awards,
        )

        product.refresh_from_db()

        self.assertEqual(len(product.awards), 2)
        self.assertEqual(product.awards[0]["competition"], "IWSC")
        self.assertEqual(product.awards[0]["medal"], "Gold")
        self.assertEqual(product.awards[1]["medal"], "Double Gold")

    def test_images_json_field_saved_correctly(self):
        """Verify images JSON field saves and loads correctly."""
        images = [
            {
                "url": "https://example.com/bottle.jpg",
                "type": "bottle",
                "width": 800,
                "height": 1200,
            },
            {
                "url": "https://example.com/label.jpg",
                "type": "label",
                "width": 600,
                "height": 400,
            },
        ]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Images",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/10",
            raw_content="Test content",
            images=images,
        )

        product.refresh_from_db()

        self.assertEqual(len(product.images), 2)
        self.assertEqual(product.images[0]["type"], "bottle")
        self.assertEqual(product.images[1]["width"], 600)

    def test_price_history_json_field_saved_correctly(self):
        """Verify price_history JSON field saves and loads correctly."""
        price_history = [
            {
                "price": 89.99,
                "currency": "USD",
                "retailer": "Total Wine",
                "url": "https://totalwine.com/whiskey/1",
                "date": "2024-01-01",
            },
            {
                "price": 79.99,
                "currency": "USD",
                "retailer": "Master of Malt",
                "url": "https://masterofmalt.com/whiskey/1",
                "date": "2024-01-15",
            },
        ]

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Prices",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/11",
            raw_content="Test content",
            price_history=price_history,
        )

        product.refresh_from_db()

        self.assertEqual(len(product.price_history), 2)
        self.assertEqual(product.price_history[0]["price"], 89.99)
        self.assertEqual(product.price_history[1]["retailer"], "Master of Malt")

    def test_nested_json_objects_persisted(self):
        """Verify complex nested JSON structures persist correctly."""
        conflict_details = {
            "field": "abv",
            "values": [
                {"source": "retailer_a", "value": 40.0},
                {"source": "retailer_b", "value": 43.0},
            ],
            "confidence": 0.6,
        }

        product = DiscoveredProduct.objects.create(
            name="Test Whiskey Conflicts",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/whiskey/12",
            raw_content="Test content",
            has_conflicts=True,
            conflict_details=conflict_details,
        )

        product.refresh_from_db()

        self.assertTrue(product.has_conflicts)
        self.assertEqual(product.conflict_details["field"], "abv")
        self.assertEqual(len(product.conflict_details["values"]), 2)
        self.assertEqual(product.conflict_details["values"][0]["value"], 40.0)


class TestWhiskeyDetailsSaved(TestCase):
    """Test that WhiskeyDetails relation works correctly with database persistence."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="Whiskey Details Brand",
            slug="whiskey-details-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="Whiskey Details Source",
            slug="whiskey-details-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_whiskey_details_created_and_linked(self):
        """Verify WhiskeyDetails can be created and linked to DiscoveredProduct."""
        product = DiscoveredProduct.objects.create(
            name="Glenfiddich 18 Year Old",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/glenfiddich/18",
            raw_content="Test content",
            abv=Decimal("40.0"),
            age_statement="18",
            region="Speyside",
            country="Scotland",
        )

        whiskey_details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.SCOTCH_SINGLE_MALT,
            distillery="Glenfiddich",
            cask_strength=False,
            single_cask=False,
            peated=False,
            peat_level=None,
            natural_color=True,
            non_chill_filtered=True,
        )

        # Reload product and verify relation
        product.refresh_from_db()

        self.assertTrue(hasattr(product, "whiskey_details"))
        self.assertEqual(product.whiskey_details.distillery, "Glenfiddich")
        self.assertEqual(
            product.whiskey_details.whiskey_type,
            WhiskeyTypeChoices.SCOTCH_SINGLE_MALT,
        )
        self.assertTrue(product.whiskey_details.natural_color)
        self.assertTrue(product.whiskey_details.non_chill_filtered)

    def test_whiskey_details_cask_information(self):
        """Verify cask-related fields are saved correctly in WhiskeyDetails."""
        product = DiscoveredProduct.objects.create(
            name="Laphroaig 10 Year Old Cask Strength",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/laphroaig/cs",
            raw_content="Test content",
            abv=Decimal("58.6"),
            age_statement="10",
            region="Islay",
            country="Scotland",
        )

        whiskey_details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.SCOTCH_SINGLE_MALT,
            distillery="Laphroaig",
            cask_strength=True,
            single_cask=False,
            cask_number=None,
            peated=True,
            peat_level="heavily",
            peat_ppm=55,
        )

        product.refresh_from_db()

        self.assertTrue(product.whiskey_details.cask_strength)
        self.assertTrue(product.whiskey_details.peated)
        self.assertEqual(product.whiskey_details.peat_level, "heavily")
        self.assertEqual(product.whiskey_details.peat_ppm, 55)

    def test_whiskey_details_vintage_information(self):
        """Verify vintage and batch information is saved correctly."""
        product = DiscoveredProduct.objects.create(
            name="Bruichladdich Vintage 2010",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/bruichladdich/2010",
            raw_content="Test content",
            abv=Decimal("46.0"),
        )

        whiskey_details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.SCOTCH_SINGLE_MALT,
            distillery="Bruichladdich",
            vintage_year=2010,
            bottling_year=2023,
            batch_number="B23-456",
            single_cask=True,
            cask_number="1234",
        )

        product.refresh_from_db()

        self.assertEqual(product.whiskey_details.vintage_year, 2010)
        self.assertEqual(product.whiskey_details.bottling_year, 2023)
        self.assertEqual(product.whiskey_details.batch_number, "B23-456")
        self.assertEqual(product.whiskey_details.cask_number, "1234")
        self.assertTrue(product.whiskey_details.single_cask)

    def test_whiskey_details_update_persists(self):
        """Verify updates to WhiskeyDetails persist correctly."""
        product = DiscoveredProduct.objects.create(
            name="Test Update Whiskey",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/update",
            raw_content="Test content",
        )

        whiskey_details = WhiskeyDetails.objects.create(
            product=product,
            whiskey_type=WhiskeyTypeChoices.BOURBON,
            distillery="Initial Distillery",
        )

        # Update the details
        whiskey_details.distillery = "Updated Distillery"
        whiskey_details.mash_bill = "75% corn, 15% rye, 10% barley"
        whiskey_details.save()

        # Reload and verify
        product.refresh_from_db()
        self.assertEqual(product.whiskey_details.distillery, "Updated Distillery")
        self.assertEqual(
            product.whiskey_details.mash_bill, "75% corn, 15% rye, 10% barley"
        )


class TestPortWineDetailsSaved(TestCase):
    """Test that PortWineDetails relation works correctly with database persistence."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="Port Wine Details Brand",
            slug="port-wine-details-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="Port Wine Details Source",
            slug="port-wine-details-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_port_wine_details_created_and_linked(self):
        """Verify PortWineDetails can be created and linked to DiscoveredProduct."""
        product = DiscoveredProduct.objects.create(
            name="Taylor's Vintage Port 2000",
            product_type=ProductType.PORT_WINE,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/taylors/2000",
            raw_content="Test content",
            abv=Decimal("20.0"),
            region="Douro",
            country="Portugal",
        )

        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.VINTAGE,
            harvest_year=2000,
            bottling_year=2002,
            grape_varieties=["Touriga Nacional", "Touriga Franca", "Tinta Barroca"],
            quinta="Quinta de Vargellas",
            douro_subregion="cima_corgo",
            producer_house="Taylor's",
            decanting_required=True,
            drinking_window="2025-2060",
        )

        # Reload product and verify relation
        product.refresh_from_db()

        self.assertTrue(hasattr(product, "port_details"))
        self.assertEqual(product.port_details.style, PortStyleChoices.VINTAGE)
        self.assertEqual(product.port_details.harvest_year, 2000)
        self.assertEqual(product.port_details.producer_house, "Taylor's")
        self.assertEqual(len(product.port_details.grape_varieties), 3)
        self.assertIn("Touriga Nacional", product.port_details.grape_varieties)

    def test_port_wine_tawny_details(self):
        """Verify tawny port specific details are saved correctly."""
        product = DiscoveredProduct.objects.create(
            name="Graham's 20 Year Old Tawny",
            product_type=ProductType.PORT_WINE,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/grahams/20",
            raw_content="Test content",
            abv=Decimal("20.0"),
        )

        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.TAWNY,
            indication_age="20 Year",
            grape_varieties=["Touriga Nacional", "Tinta Roriz"],
            producer_house="Graham's",
            aging_vessel="Small oak barrels",
            decanting_required=False,
        )

        product.refresh_from_db()

        self.assertEqual(product.port_details.style, PortStyleChoices.TAWNY)
        self.assertEqual(product.port_details.indication_age, "20 Year")
        self.assertEqual(product.port_details.aging_vessel, "Small oak barrels")
        self.assertFalse(product.port_details.decanting_required)

    def test_port_wine_colheita_details(self):
        """Verify colheita port details with vintage year are saved correctly."""
        product = DiscoveredProduct.objects.create(
            name="Kopke Colheita 1998",
            product_type=ProductType.PORT_WINE,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/kopke/1998",
            raw_content="Test content",
            abv=Decimal("20.0"),
        )

        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.COLHEITA,
            harvest_year=1998,
            bottling_year=2020,
            producer_house="Kopke",
            quinta="Single Quinta",
            douro_subregion="baixo_corgo",
        )

        product.refresh_from_db()

        self.assertEqual(product.port_details.style, PortStyleChoices.COLHEITA)
        self.assertEqual(product.port_details.harvest_year, 1998)
        self.assertEqual(product.port_details.douro_subregion, "baixo_corgo")

    def test_port_wine_details_update_persists(self):
        """Verify updates to PortWineDetails persist correctly."""
        product = DiscoveredProduct.objects.create(
            name="Test Update Port",
            product_type=ProductType.PORT_WINE,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/update-port",
            raw_content="Test content",
        )

        port_details = PortWineDetails.objects.create(
            product=product,
            style=PortStyleChoices.RUBY,
            producer_house="Initial House",
        )

        # Update the details
        port_details.producer_house = "Updated House"
        port_details.grape_varieties = ["Touriga Nacional", "Touriga Franca"]
        port_details.save()

        # Reload and verify
        product.refresh_from_db()
        self.assertEqual(product.port_details.producer_house, "Updated House")
        self.assertEqual(len(product.port_details.grape_varieties), 2)


class TestCompletenessScoreCalculated(TestCase):
    """Test that completeness score is correctly calculated and persisted."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="Completeness Test Brand",
            slug="completeness-test-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="Completeness Test Source",
            slug="completeness-test-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_skeleton_product_has_low_score(self):
        """Verify a skeleton product (name only) has a low completeness score."""
        product = DiscoveredProduct.objects.create(
            name="Skeleton Whiskey",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/skeleton",
            raw_content="Minimal content",
        )

        # Score is auto-calculated on save
        product.refresh_from_db()

        # Skeleton should have very low score (just name = 10 points + type = 5)
        self.assertLess(product.completeness_score, 30)

    def test_product_with_palate_flavors_higher_score(self):
        """Verify palate_flavors (3+ items) adds 10 points to score."""
        product = DiscoveredProduct.objects.create(
            name="Palate Test Whiskey",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/palate-test",
            raw_content="Test content",
            abv=Decimal("40.0"),
            palate_flavors=["vanilla", "oak", "honey", "spice"],
        )

        product.refresh_from_db()

        # Should have: name(10) + brand(5) + type(5) + abv(5) + palate_flavors(10) = 35+
        self.assertGreaterEqual(product.completeness_score, 35)

    def test_product_with_primary_aromas_adds_points(self):
        """Verify primary_aromas (2+ items) adds 5 points to score."""
        product = DiscoveredProduct.objects.create(
            name="Aromas Test Whiskey",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/aromas-test",
            raw_content="Test content",
            abv=Decimal("40.0"),
            primary_aromas=["honey", "vanilla", "citrus"],
            nose_description="Rich honey and vanilla notes",
        )

        product.refresh_from_db()

        # Should have nose contribution
        self.assertGreaterEqual(product.completeness_score, 30)

    def test_product_with_finish_flavors_adds_points(self):
        """Verify finish_flavors (2+ items) adds points to score."""
        product = DiscoveredProduct.objects.create(
            name="Finish Test Whiskey",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/finish-test",
            raw_content="Test content",
            abv=Decimal("40.0"),
            finish_flavors=["oak", "spice", "tobacco"],
            finish_length=8,
        )

        product.refresh_from_db()

        # Should have finish contribution
        self.assertGreaterEqual(product.completeness_score, 25)

    def test_complete_product_high_score(self):
        """Verify a fully populated product achieves high completeness score."""
        product = DiscoveredProduct.objects.create(
            name="Complete Whiskey 18 Year Old",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/complete",
            raw_content="Test content",
            description="A rich and complex single malt whiskey aged 18 years.",
            category="Single Malt Scotch",
            abv=Decimal("43.0"),
            # Tasting profile
            palate_flavors=["vanilla", "oak", "honey", "spice", "dried fruit"],
            palate_description="Rich and creamy with layers of complexity",
            initial_taste="Sweet honey upfront",
            mid_palate_evolution="Develops into oak and spice",
            mouthfeel="smooth-creamy",
            primary_aromas=["honey", "vanilla", "heather"],
            nose_description="Complex nose with honey and floral notes",
            finish_flavors=["oak", "spice", "tobacco"],
            finish_description="Long and warming finish",
            finish_length=8,
            # Additional data
            best_price=Decimal("89.99"),
            images=[{"url": "https://example.com/img.jpg", "type": "bottle"}],
            awards=[{"competition": "IWSC", "year": 2024, "medal": "Gold"}],
        )

        product.refresh_from_db()

        # Should have high score (60+)
        self.assertGreaterEqual(product.completeness_score, 60)

    def test_completeness_score_updates_on_save(self):
        """Verify completeness score updates when product data changes."""
        product = DiscoveredProduct.objects.create(
            name="Update Score Test",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/update-score",
            raw_content="Test content",
        )

        initial_score = product.completeness_score

        # Add more data
        product.brand = self.brand
        product.abv = Decimal("40.0")
        product.palate_flavors = ["vanilla", "oak", "honey"]
        product.palate_description = "Rich palate"
        product.save()

        product.refresh_from_db()

        # Score should have increased
        self.assertGreater(product.completeness_score, initial_score)

    def test_verified_product_with_multiple_sources(self):
        """Verify products with multiple sources get verification bonus."""
        product = DiscoveredProduct.objects.create(
            name="Multi-Source Whiskey",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/multi-source",
            raw_content="Test content",
            abv=Decimal("40.0"),
            source_count=3,
            palate_flavors=["vanilla", "oak", "honey", "spice"],
            palate_description="Rich palate",
            primary_aromas=["honey", "vanilla"],
            nose_description="Complex nose",
            finish_flavors=["oak", "spice"],
            finish_description="Long finish",
            description="Multi-source verified whiskey",
        )

        product.refresh_from_db()

        # source_count >= 2 should add 5 points, >= 3 adds 5 more
        # Should have verification bonus reflected in score
        self.assertGreaterEqual(product.completeness_score, 55)


class TestProductStatusTransitions(TestCase):
    """Test that product status transitions correctly based on completeness."""

    @classmethod
    def setUpTestData(cls):
        """Set up test fixtures for the test class."""
        cls.brand = DiscoveredBrand.objects.create(
            name="Status Test Brand",
            slug="status-test-brand",
        )
        cls.source = CrawlerSource.objects.create(
            name="Status Test Source",
            slug="status-test-source",
            base_url="https://example.com",
            category="review",
            is_active=True,
        )

    def test_skeleton_product_status_incomplete(self):
        """Verify skeleton products get INCOMPLETE status."""
        product = DiscoveredProduct.objects.create(
            name="Skeleton Status Test",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/skeleton-status",
            raw_content="Minimal content",
        )

        product.refresh_from_db()

        self.assertEqual(product.status, DiscoveredProductStatus.INCOMPLETE)

    def test_partial_product_without_palate_stays_partial(self):
        """Verify products without palate data cannot exceed PARTIAL status."""
        product = DiscoveredProduct.objects.create(
            name="Partial No Palate Test",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/partial-no-palate",
            raw_content="Test content",
            abv=Decimal("40.0"),
            description="A nice whiskey",
            category="Single Malt Scotch",
            # No palate data!
            primary_aromas=["honey", "vanilla"],
            nose_description="Nice nose",
            finish_flavors=["oak", "spice"],
            best_price=Decimal("89.99"),
        )

        product.refresh_from_db()

        # Without palate data, max status is PARTIAL
        self.assertIn(
            product.status,
            [DiscoveredProductStatus.INCOMPLETE, DiscoveredProductStatus.PARTIAL],
        )

    def test_complete_product_with_palate_gets_complete_status(self):
        """Verify products with palate data and good score get COMPLETE status."""
        product = DiscoveredProduct.objects.create(
            name="Complete Status Test",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/complete-status",
            raw_content="Test content",
            description="A rich and complex single malt",
            category="Single Malt Scotch",
            abv=Decimal("43.0"),
            # Palate data - MANDATORY for COMPLETE
            palate_flavors=["vanilla", "oak", "honey", "spice", "dried fruit"],
            palate_description="Rich and creamy palate",
            initial_taste="Sweet honey upfront",
            mouthfeel="smooth-creamy",
            # Nose data
            primary_aromas=["honey", "vanilla", "heather"],
            nose_description="Complex nose",
            # Finish data
            finish_flavors=["oak", "spice"],
            finish_description="Long warming finish",
            finish_length=8,
            # Enrichment
            best_price=Decimal("89.99"),
            images=[{"url": "https://example.com/img.jpg"}],
        )

        product.refresh_from_db()

        # With palate data and high score, should be COMPLETE
        self.assertEqual(product.status, DiscoveredProductStatus.COMPLETE)

    def test_verified_product_with_multiple_sources(self):
        """Verify products with multiple sources and high score get VERIFIED status."""
        product = DiscoveredProduct.objects.create(
            name="Verified Status Test",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/verified-status",
            raw_content="Test content",
            description="A verified whiskey from multiple sources",
            category="Single Malt Scotch",
            abv=Decimal("43.0"),
            source_count=3,  # Multiple sources
            # Full tasting profile
            palate_flavors=["vanilla", "oak", "honey", "spice", "dried fruit"],
            palate_description="Rich and creamy palate",
            initial_taste="Sweet honey upfront",
            mid_palate_evolution="Develops into oak and spice",
            mouthfeel="smooth-creamy",
            primary_aromas=["honey", "vanilla", "heather", "citrus"],
            nose_description="Complex nose with layers",
            secondary_aromas=["floral", "peat"],
            finish_flavors=["oak", "spice", "tobacco"],
            finish_description="Long warming finish",
            finish_length=9,
            final_notes="Lingering sweetness",
            # Full enrichment
            best_price=Decimal("129.99"),
            images=[{"url": "https://example.com/img.jpg"}],
            awards=[{"competition": "IWSC", "year": 2024, "medal": "Gold"}],
            color_description="Deep amber",
            color_intensity=7,
            flavor_intensity=8,
            complexity=8,
        )

        product.refresh_from_db()

        # With high score, palate data, and multiple sources -> VERIFIED
        self.assertEqual(product.status, DiscoveredProductStatus.VERIFIED)

    def test_status_transitions_on_update(self):
        """Verify status updates correctly when product data changes."""
        # Start with incomplete product
        product = DiscoveredProduct.objects.create(
            name="Transition Test",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/transition",
            raw_content="Test content",
        )

        self.assertEqual(product.status, DiscoveredProductStatus.INCOMPLETE)

        # Add some data -> should become PARTIAL
        product.brand = self.brand
        product.abv = Decimal("40.0")
        product.description = "A nice whiskey"
        product.save()

        product.refresh_from_db()
        self.assertIn(
            product.status,
            [DiscoveredProductStatus.INCOMPLETE, DiscoveredProductStatus.PARTIAL],
        )

        # Add palate data -> should reach COMPLETE with enough score
        product.palate_flavors = ["vanilla", "oak", "honey", "spice"]
        product.palate_description = "Rich palate"
        product.primary_aromas = ["honey", "vanilla"]
        product.nose_description = "Nice nose"
        product.finish_flavors = ["oak", "spice"]
        product.finish_description = "Long finish"
        product.finish_length = 7
        product.best_price = Decimal("89.99")
        product.save()

        product.refresh_from_db()
        # Should now be at least COMPLETE
        self.assertIn(
            product.status,
            [DiscoveredProductStatus.COMPLETE, DiscoveredProductStatus.VERIFIED],
        )

    def test_rejected_status_preserved(self):
        """Verify REJECTED status is not overwritten by auto-status calculation."""
        product = DiscoveredProduct.objects.create(
            name="Rejected Test",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/rejected",
            raw_content="Test content",
            status=DiscoveredProductStatus.REJECTED,
            palate_flavors=["vanilla", "oak", "honey"],
            palate_description="Good palate",
        )

        # Even with good data, status should remain REJECTED
        product.refresh_from_db()
        self.assertEqual(product.status, DiscoveredProductStatus.REJECTED)

    def test_merged_status_preserved(self):
        """Verify MERGED status is not overwritten by auto-status calculation."""
        product = DiscoveredProduct.objects.create(
            name="Merged Test",
            product_type=ProductType.WHISKEY,
            brand=self.brand,
            source=self.source,
            source_url="https://example.com/merged",
            raw_content="Test content",
            status=DiscoveredProductStatus.MERGED,
            palate_flavors=["vanilla", "oak", "honey"],
        )

        # Even with good data, status should remain MERGED
        product.refresh_from_db()
        self.assertEqual(product.status, DiscoveredProductStatus.MERGED)

    def test_has_palate_data_helper(self):
        """Verify has_palate_data helper function works correctly."""
        # Product with palate_flavors
        product1 = DiscoveredProduct.objects.create(
            name="Has Palate 1",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/has-palate-1",
            raw_content="Test",
            palate_flavors=["vanilla", "oak"],
        )
        self.assertTrue(has_palate_data(product1))

        # Product with palate_description
        product2 = DiscoveredProduct.objects.create(
            name="Has Palate 2",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/has-palate-2",
            raw_content="Test",
            palate_description="Rich and creamy",
        )
        self.assertTrue(has_palate_data(product2))

        # Product with initial_taste
        product3 = DiscoveredProduct.objects.create(
            name="Has Palate 3",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/has-palate-3",
            raw_content="Test",
            initial_taste="Sweet honey upfront",
        )
        self.assertTrue(has_palate_data(product3))

        # Product without any palate data
        product4 = DiscoveredProduct.objects.create(
            name="No Palate",
            product_type=ProductType.WHISKEY,
            source=self.source,
            source_url="https://example.com/no-palate",
            raw_content="Test",
            primary_aromas=["honey"],
        )
        self.assertFalse(has_palate_data(product4))
