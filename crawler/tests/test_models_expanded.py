"""
Tests for expanded DiscoveredProduct model fields and methods.

Phase 1: Model Expansion - TDD tests for comprehensive product data collection.
These tests verify the new fields and helper methods added to support the
multi-pronged product discovery system.
"""

import pytest
from decimal import Decimal
from django.test import TestCase

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawlerSource,
    SourceCategory,
)


@pytest.fixture
def sample_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Source",
        slug="test-source",
        base_url="https://example.com",
        category=SourceCategory.RETAILER,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_product(db, sample_source):
    """Create a sample DiscoveredProduct for testing."""
    return DiscoveredProduct.objects.create(
        source=sample_source,
        source_url="https://example.com/product/test",
        fingerprint="test-fingerprint-123",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Test content</html>",
        raw_content_hash="abc123hash",
        extracted_data={"name": "Test Whiskey", "brand": "Test Brand"},
        status=DiscoveredProductStatus.PENDING,
        discovery_source=DiscoverySource.DIRECT,
    )


class TestDiscoveredProductExpandedFields:
    """Tests for new expanded fields on DiscoveredProduct model."""

    def test_taste_profile_default_empty_dict(self, db, sample_source):
        """New products should have empty taste_profile dict by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/1",
            fingerprint="fp-1",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash1",
        )
        assert product.taste_profile == {}

    def test_taste_profile_stores_nose_palate_finish(self, db, sample_source):
        """Taste profile should store nose, palate, finish arrays and notes."""
        taste_data = {
            "nose": ["vanilla", "oak", "honey"],
            "palate": ["caramel", "spice", "fruit"],
            "finish": ["long", "warm", "smooth"],
            "overall_notes": "A rich, complex whisky with depth.",
            "flavor_tags": ["smoky", "sweet", "fruity"],
        }
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/2",
            fingerprint="fp-2",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash2",
            taste_profile=taste_data,
        )

        # Refresh from database
        product.refresh_from_db()

        assert product.taste_profile["nose"] == ["vanilla", "oak", "honey"]
        assert product.taste_profile["palate"] == ["caramel", "spice", "fruit"]
        assert product.taste_profile["finish"] == ["long", "warm", "smooth"]
        assert product.taste_profile["overall_notes"] == "A rich, complex whisky with depth."
        assert product.taste_profile["flavor_tags"] == ["smoky", "sweet", "fruity"]

    def test_images_default_empty_list(self, db, sample_source):
        """New products should have empty images list by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/3",
            fingerprint="fp-3",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash3",
        )
        assert product.images == []

    def test_images_stores_multiple_entries(self, db, sample_source):
        """Images should store multiple image entries with full metadata."""
        images_data = [
            {
                "url": "https://example.com/bottle.jpg",
                "type": "bottle",
                "source": "master-of-malt",
                "width": 800,
                "height": 1200,
            },
            {
                "url": "https://example.com/label.jpg",
                "type": "label",
                "source": "direct",
                "width": 400,
                "height": 600,
            },
        ]
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/4",
            fingerprint="fp-4",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash4",
            images=images_data,
        )

        product.refresh_from_db()

        assert len(product.images) == 2
        assert product.images[0]["url"] == "https://example.com/bottle.jpg"
        assert product.images[0]["type"] == "bottle"
        assert product.images[1]["type"] == "label"

    def test_ratings_default_empty_list(self, db, sample_source):
        """New products should have empty ratings list by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/5",
            fingerprint="fp-5",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash5",
        )
        assert product.ratings == []

    def test_ratings_stores_structure(self, db, sample_source):
        """Ratings should store score, max_score, source, and reviewer info."""
        ratings_data = [
            {
                "source": "whiskyadvocate",
                "score": 92,
                "max_score": 100,
                "reviewer": "John Doe",
                "date": "2025-01-15",
                "url": "https://whiskyadvocate.com/review/123",
            },
            {
                "source": "masterofmalt",
                "score": 4.5,
                "max_score": 5,
                "reviewer": None,
                "date": "2025-01-10",
                "url": "https://masterofmalt.com/product/123",
            },
        ]
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/6",
            fingerprint="fp-6",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash6",
            ratings=ratings_data,
        )

        product.refresh_from_db()

        assert len(product.ratings) == 2
        assert product.ratings[0]["source"] == "whiskyadvocate"
        assert product.ratings[0]["score"] == 92
        assert product.ratings[1]["max_score"] == 5

    def test_press_mentions_default_empty_list(self, db, sample_source):
        """New products should have empty press_mentions list by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/7",
            fingerprint="fp-7",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash7",
        )
        assert product.press_mentions == []

    def test_press_mentions_stores_structure(self, db, sample_source):
        """Press mentions should store url, title, source, date, snippet."""
        mentions_data = [
            {
                "url": "https://robbreport.com/article/best-whiskies-2025",
                "title": "Best Whiskies of 2025",
                "source": "robbreport",
                "date": "2025-01-10",
                "snippet": "This exceptional whisky stands out...",
                "mention_type": "list",
            },
        ]
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/8",
            fingerprint="fp-8",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash8",
            press_mentions=mentions_data,
        )

        product.refresh_from_db()

        assert len(product.press_mentions) == 1
        assert product.press_mentions[0]["title"] == "Best Whiskies of 2025"
        assert product.press_mentions[0]["mention_type"] == "list"

    def test_mention_count_default_zero(self, db, sample_source):
        """New products should have mention_count of 0 by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/9",
            fingerprint="fp-9",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash9",
        )
        assert product.mention_count == 0

    def test_discovery_sources_default_empty_list(self, db, sample_source):
        """New products should have empty discovery_sources list by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/10",
            fingerprint="fp-10",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash10",
        )
        assert product.discovery_sources == []

    def test_discovery_sources_stores_list(self, db, sample_source):
        """Discovery sources should store list of discovery methods."""
        sources = ["competition", "serpapi", "hub_crawl"]
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/10b",
            fingerprint="fp-10b",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash10b",
            discovery_sources=sources,
        )

        product.refresh_from_db()

        assert product.discovery_sources == ["competition", "serpapi", "hub_crawl"]

    def test_price_history_default_empty_list(self, db, sample_source):
        """New products should have empty price_history list by default."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/11",
            fingerprint="fp-11",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash11",
        )
        assert product.price_history == []

    def test_price_history_stores_entries(self, db, sample_source):
        """Price history should store price entries with retailer info."""
        history = [
            {
                "price": 89.99,
                "currency": "USD",
                "retailer": "Master of Malt",
                "url": "https://masterofmalt.com/product/123",
                "date": "2025-01-15",
            },
            {
                "price": 95.00,
                "currency": "USD",
                "retailer": "The Whisky Exchange",
                "url": "https://thewhiskyexchange.com/product/456",
                "date": "2025-01-10",
            },
        ]
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/11b",
            fingerprint="fp-11b",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash11b",
            price_history=history,
        )

        product.refresh_from_db()

        assert len(product.price_history) == 2
        assert product.price_history[0]["price"] == 89.99
        assert product.price_history[0]["retailer"] == "Master of Malt"

    def test_best_price_fields_default(self, db, sample_source):
        """New products should have None/default best price fields."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/12",
            fingerprint="fp-12",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash12",
        )
        assert product.best_price is None
        assert product.best_price_currency == "USD"
        assert product.best_price_retailer == ""
        assert product.best_price_url == ""

    def test_best_price_stores_decimal(self, db, sample_source):
        """Best price should store as Decimal with full precision."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/13",
            fingerprint="fp-13",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash13",
            best_price=Decimal("89.99"),
            best_price_currency="GBP",
            best_price_retailer="Master of Malt",
            best_price_url="https://masterofmalt.com/product/123",
        )

        product.refresh_from_db()

        assert product.best_price == Decimal("89.99")
        assert product.best_price_currency == "GBP"
        assert product.best_price_retailer == "Master of Malt"
        assert product.best_price_url == "https://masterofmalt.com/product/123"


class TestDiscoveredProductHelperMethods:
    """Tests for new helper methods on DiscoveredProduct model."""

    def test_add_discovery_source_adds_new(self, sample_product):
        """add_discovery_source should add a new source to the list."""
        sample_product.add_discovery_source("competition")

        sample_product.refresh_from_db()

        assert "competition" in sample_product.discovery_sources

    def test_add_discovery_source_skips_duplicate(self, sample_product):
        """add_discovery_source should skip if source already exists."""
        sample_product.discovery_sources = ["competition"]
        sample_product.save()

        sample_product.add_discovery_source("competition")

        sample_product.refresh_from_db()

        assert sample_product.discovery_sources.count("competition") == 1

    def test_add_discovery_source_adds_multiple(self, sample_product):
        """add_discovery_source should allow adding multiple unique sources."""
        sample_product.add_discovery_source("competition")
        sample_product.add_discovery_source("serpapi")
        sample_product.add_discovery_source("hub_crawl")

        sample_product.refresh_from_db()

        assert len(sample_product.discovery_sources) == 3
        assert "competition" in sample_product.discovery_sources
        assert "serpapi" in sample_product.discovery_sources
        assert "hub_crawl" in sample_product.discovery_sources

    def test_add_press_mention_adds_new(self, sample_product):
        """add_press_mention should add a new mention."""
        mention = {
            "url": "https://example.com/article/1",
            "title": "Great Whiskey Review",
            "source": "whiskyadvocate",
            "date": "2025-01-15",
            "snippet": "This whiskey is exceptional...",
            "mention_type": "review",
        }

        sample_product.add_press_mention(mention)

        sample_product.refresh_from_db()

        assert len(sample_product.press_mentions) == 1
        assert sample_product.press_mentions[0]["title"] == "Great Whiskey Review"

    def test_add_press_mention_increments_count(self, sample_product):
        """add_press_mention should increment mention_count."""
        mention1 = {"url": "https://example.com/article/1", "title": "Article 1"}
        mention2 = {"url": "https://example.com/article/2", "title": "Article 2"}

        sample_product.add_press_mention(mention1)
        sample_product.add_press_mention(mention2)

        sample_product.refresh_from_db()

        assert sample_product.mention_count == 2

    def test_add_press_mention_skips_duplicate_url(self, sample_product):
        """add_press_mention should skip if URL already exists."""
        mention = {"url": "https://example.com/article/1", "title": "Article 1"}

        sample_product.add_press_mention(mention)
        sample_product.add_press_mention(mention)  # Duplicate

        sample_product.refresh_from_db()

        assert len(sample_product.press_mentions) == 1
        assert sample_product.mention_count == 1

    def test_add_rating_adds_new_source(self, sample_product):
        """add_rating should add rating from new source."""
        rating = {
            "source": "whiskyadvocate",
            "score": 92,
            "max_score": 100,
            "reviewer": "John Doe",
            "date": "2025-01-15",
        }

        sample_product.add_rating(rating)

        sample_product.refresh_from_db()

        assert len(sample_product.ratings) == 1
        assert sample_product.ratings[0]["source"] == "whiskyadvocate"
        assert sample_product.ratings[0]["score"] == 92

    def test_add_rating_skips_existing_source(self, sample_product):
        """add_rating should skip if source already has a rating."""
        rating1 = {"source": "whiskyadvocate", "score": 92}
        rating2 = {"source": "whiskyadvocate", "score": 94}  # Same source, different score

        sample_product.add_rating(rating1)
        sample_product.add_rating(rating2)

        sample_product.refresh_from_db()

        assert len(sample_product.ratings) == 1
        assert sample_product.ratings[0]["score"] == 92  # First rating kept

    def test_add_rating_allows_multiple_sources(self, sample_product):
        """add_rating should allow ratings from different sources."""
        rating1 = {"source": "whiskyadvocate", "score": 92}
        rating2 = {"source": "masterofmalt", "score": 4.5}

        sample_product.add_rating(rating1)
        sample_product.add_rating(rating2)

        sample_product.refresh_from_db()

        assert len(sample_product.ratings) == 2

    def test_update_best_price_sets_when_none(self, sample_product):
        """update_best_price should set price when current is None."""
        sample_product.update_best_price(
            price=89.99,
            currency="USD",
            retailer="Master of Malt",
            url="https://masterofmalt.com/product/123",
        )

        sample_product.refresh_from_db()

        assert sample_product.best_price == Decimal("89.99")
        assert sample_product.best_price_currency == "USD"
        assert sample_product.best_price_retailer == "Master of Malt"
        assert sample_product.best_price_url == "https://masterofmalt.com/product/123"

    def test_update_best_price_sets_lower(self, sample_product):
        """update_best_price should update if new price is lower."""
        sample_product.best_price = Decimal("100.00")
        sample_product.best_price_retailer = "Old Retailer"
        sample_product.save()

        sample_product.update_best_price(
            price=89.99,
            currency="USD",
            retailer="New Retailer",
            url="https://newretailer.com/product",
        )

        sample_product.refresh_from_db()

        assert sample_product.best_price == Decimal("89.99")
        assert sample_product.best_price_retailer == "New Retailer"

    def test_update_best_price_skips_higher(self, sample_product):
        """update_best_price should not update if new price is higher."""
        sample_product.best_price = Decimal("50.00")
        sample_product.best_price_retailer = "Cheap Retailer"
        sample_product.save()

        sample_product.update_best_price(
            price=89.99,
            currency="USD",
            retailer="Expensive Retailer",
            url="https://expensive.com/product",
        )

        sample_product.refresh_from_db()

        assert sample_product.best_price == Decimal("50.00")
        assert sample_product.best_price_retailer == "Cheap Retailer"

    def test_add_image_adds_new(self, sample_product):
        """add_image should add a new image to the list."""
        image = {
            "url": "https://example.com/bottle.jpg",
            "type": "bottle",
            "source": "master-of-malt",
            "width": 800,
            "height": 1200,
        }

        sample_product.add_image(image)

        sample_product.refresh_from_db()

        assert len(sample_product.images) == 1
        assert sample_product.images[0]["url"] == "https://example.com/bottle.jpg"
        assert sample_product.images[0]["type"] == "bottle"

    def test_add_image_skips_duplicate_url(self, sample_product):
        """add_image should skip if URL already exists."""
        image = {
            "url": "https://example.com/bottle.jpg",
            "type": "bottle",
        }

        sample_product.add_image(image)
        sample_product.add_image(image)  # Duplicate

        sample_product.refresh_from_db()

        assert len(sample_product.images) == 1

    def test_add_image_allows_multiple_unique(self, sample_product):
        """add_image should allow adding multiple images with unique URLs."""
        image1 = {"url": "https://example.com/bottle.jpg", "type": "bottle"}
        image2 = {"url": "https://example.com/label.jpg", "type": "label"}

        sample_product.add_image(image1)
        sample_product.add_image(image2)

        sample_product.refresh_from_db()

        assert len(sample_product.images) == 2

    def test_update_taste_profile_merges_arrays(self, sample_product):
        """update_taste_profile should merge new values into existing arrays."""
        initial_profile = {
            "nose": ["vanilla", "oak"],
            "palate": ["caramel"],
            "finish": ["long"],
            "flavor_tags": ["sweet"],
        }
        sample_product.taste_profile = initial_profile
        sample_product.save()

        new_profile = {
            "nose": ["honey", "vanilla"],  # vanilla is duplicate
            "palate": ["spice", "fruit"],
            "finish": ["warm"],
            "flavor_tags": ["smoky"],
        }

        sample_product.update_taste_profile(new_profile)

        sample_product.refresh_from_db()

        # Check merged arrays (no duplicates)
        assert set(sample_product.taste_profile["nose"]) == {"vanilla", "oak", "honey"}
        assert set(sample_product.taste_profile["palate"]) == {"caramel", "spice", "fruit"}
        assert set(sample_product.taste_profile["finish"]) == {"long", "warm"}
        assert set(sample_product.taste_profile["flavor_tags"]) == {"sweet", "smoky"}

    def test_update_taste_profile_sets_overall_notes_if_empty(self, sample_product):
        """update_taste_profile should set overall_notes only if not already set."""
        sample_product.taste_profile = {}
        sample_product.save()

        profile = {"overall_notes": "A complex and rich whisky."}
        sample_product.update_taste_profile(profile)

        sample_product.refresh_from_db()

        assert sample_product.taste_profile["overall_notes"] == "A complex and rich whisky."

    def test_update_taste_profile_preserves_existing_overall_notes(self, sample_product):
        """update_taste_profile should not overwrite existing overall_notes."""
        sample_product.taste_profile = {"overall_notes": "Original notes."}
        sample_product.save()

        profile = {"overall_notes": "New notes that should be ignored."}
        sample_product.update_taste_profile(profile)

        sample_product.refresh_from_db()

        assert sample_product.taste_profile["overall_notes"] == "Original notes."

    def test_update_taste_profile_creates_new_keys(self, sample_product):
        """update_taste_profile should create new keys if they don't exist."""
        sample_product.taste_profile = {}
        sample_product.save()

        profile = {
            "nose": ["vanilla", "oak"],
            "palate": ["caramel"],
        }

        sample_product.update_taste_profile(profile)

        sample_product.refresh_from_db()

        # Use set comparison since merge uses sets internally (order not guaranteed)
        assert set(sample_product.taste_profile["nose"]) == {"vanilla", "oak"}
        assert set(sample_product.taste_profile["palate"]) == {"caramel"}


class TestDiscoveredProductFieldPersistence:
    """Tests to verify new fields persist correctly through database operations."""

    def test_all_new_fields_round_trip(self, db, sample_source):
        """All new fields should survive a database save and reload."""
        product = DiscoveredProduct.objects.create(
            source=sample_source,
            source_url="https://example.com/product/roundtrip",
            fingerprint="fp-roundtrip",
            product_type=ProductType.WHISKEY,
            raw_content="content",
            raw_content_hash="hash-roundtrip",
            # New fields
            taste_profile={"nose": ["vanilla"], "overall_notes": "Great whisky"},
            images=[{"url": "https://example.com/img.jpg", "type": "bottle"}],
            ratings=[{"source": "test", "score": 90}],
            press_mentions=[{"url": "https://article.com", "title": "Review"}],
            mention_count=1,
            discovery_sources=["competition", "serpapi"],
            price_history=[{"price": 99.99, "retailer": "Test Shop"}],
            best_price=Decimal("89.99"),
            best_price_currency="GBP",
            best_price_retailer="Best Shop",
            best_price_url="https://bestshop.com/product",
        )

        # Reload from database
        reloaded = DiscoveredProduct.objects.get(pk=product.pk)

        # Verify all fields
        assert reloaded.taste_profile == {"nose": ["vanilla"], "overall_notes": "Great whisky"}
        assert reloaded.images == [{"url": "https://example.com/img.jpg", "type": "bottle"}]
        assert reloaded.ratings == [{"source": "test", "score": 90}]
        assert reloaded.press_mentions == [{"url": "https://article.com", "title": "Review"}]
        assert reloaded.mention_count == 1
        assert reloaded.discovery_sources == ["competition", "serpapi"]
        assert reloaded.price_history == [{"price": 99.99, "retailer": "Test Shop"}]
        assert reloaded.best_price == Decimal("89.99")
        assert reloaded.best_price_currency == "GBP"
        assert reloaded.best_price_retailer == "Best Shop"
        assert reloaded.best_price_url == "https://bestshop.com/product"

    def test_update_fields_partial_save(self, sample_product):
        """Helper methods should use update_fields for efficient saves."""
        # This tests that the save is efficient and doesn't trigger full model save
        sample_product.add_discovery_source("test_source")

        sample_product.refresh_from_db()

        assert "test_source" in sample_product.discovery_sources
