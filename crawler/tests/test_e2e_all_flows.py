"""
End-to-End Tests for All Crawler Flows

This test suite verifies:
1. Competition flow (skeleton creation, enrichment)
2. Discovery flow (search, extraction)
3. Direct crawling flow (content processing)
4. Cross-flow duplicate detection
5. CrawledSource caching behavior
6. URL frontier persistence
7. Multi-source enrichment

All tests use mocked external services (SerpAPI, ScrapingBee, AI Enhancement)
to avoid real API calls while testing the full flow logic.
"""

import pytest
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone

from crawler.models import (
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    CrawledSource,
    ProductAward,
    ProductRating,
    ProductImage,
    ProductSource,
    ProductFieldSource,
    DiscoveredBrand,
    WhiskeyDetails,
    PortWineDetails,
)
from crawler.services.product_saver import save_discovered_product, ProductSaveResult
from crawler.discovery.competitions.skeleton_manager import SkeletonProductManager
from crawler.services.smart_crawler import SmartCrawler, ExtractionResult


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_whiskey_data():
    """Sample whiskey product data."""
    return {
        "name": "Macallan 18 Year Old Sherry Oak",
        "brand": "The Macallan",
        "abv": 43.0,
        "age_statement": 18,
        "volume_ml": 700,
        "region": "Speyside",
        "country": "Scotland",
        "category": "Single Malt Scotch",
        "description": "Rich and complex with dried fruits and spice.",
        "nose_description": "Rich dried fruits, sherry, wood spice",
        "palate_flavors": ["dried fruit", "orange peel", "ginger"],
        "finish_description": "Long and warm with lingering spice",
        "awards": [
            {"competition": "IWSC", "year": 2024, "medal": "gold"},  # lowercase medal
        ],
        "ratings": [
            {"source": "Whisky Advocate", "score": 93, "max_score": 100},
        ],
        "images": [
            {"url": "https://example.com/macallan18.jpg", "type": "bottle", "source": "retailer"},
        ],
    }


@pytest.fixture
def sample_port_data():
    """Sample port wine product data."""
    return {
        "name": "Taylor's Vintage Port 2017",
        "brand": "Taylor's",
        "abv": 20.0,
        "volume_ml": 750,
        "region": "Douro",
        "country": "Portugal",
        "category": "Vintage Port",
        "description": "Deep and complex with dark fruit notes.",
        "nose_description": "Blackberry, plum, violet",
        "palate_flavors": ["dark cherry", "chocolate", "spice"],
        "finish_description": "Long with firm tannins",
        "style": "Vintage",
        "harvest_year": 2017,
    }


@pytest.fixture
def mock_scrapingbee_client():
    """Mock ScrapingBee client."""
    client = Mock()
    client.fetch_page = Mock(return_value={
        "success": True,
        "content": "<html><body>Product page content</body></html>",
    })
    return client


@pytest.fixture
def mock_ai_client(sample_whiskey_data):
    """Mock AI Enhancement client."""
    client = Mock()
    client.enhance_from_crawler = Mock(return_value={
        "success": True,
        "data": {
            "extracted_data": sample_whiskey_data,
            "product_type": "whiskey",
            "confidence": 0.95,
        },
    })
    return client


# =============================================================================
# Competition Flow E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestCompetitionFlowE2E:
    """End-to-end tests for competition flow."""

    def test_skeleton_creation_full_flow(self):
        """Test complete skeleton creation from award data."""
        manager = SkeletonProductManager()

        award_data = {
            "product_name": "Glenfiddich 21 Gran Reserva",
            "producer": "Glenfiddich",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
            "category": "Single Malt Scotch",
            "country": "Scotland",
        }

        # Create skeleton
        product = manager.create_skeleton_product(award_data)

        # Verify product created
        assert product is not None
        assert product.name == "Glenfiddich 21 Gran Reserva"
        assert product.status == DiscoveredProductStatus.SKELETON
        assert product.discovery_source == DiscoverySource.COMPETITION

        # Verify brand created
        assert product.brand is not None
        assert product.brand.name == "Glenfiddich"

        # Verify award created as ProductAward (not JSON)
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() == 1
        assert awards.first().competition == "IWSC"
        assert awards.first().medal == "gold"

    def test_duplicate_skeleton_detection_by_fingerprint(self):
        """Test that duplicate skeletons are detected by fingerprint."""
        manager = SkeletonProductManager()

        award_data_1 = {
            "product_name": "Ardbeg 10",
            "producer": "Ardbeg",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        }

        # Create first skeleton
        product_1 = manager.create_skeleton_product(award_data_1)
        initial_count = DiscoveredProduct.objects.count()

        # Try to create duplicate with same fingerprint
        award_data_2 = {
            "product_name": "Ardbeg 10",  # Same product
            "producer": "Ardbeg",
            "competition": "SFWSC",  # Different competition
            "year": 2024,
            "medal": "double_gold",  # Valid medal type
        }

        product_2 = manager.create_skeleton_product(award_data_2)

        # Should return same product, not create duplicate
        assert product_2.id == product_1.id
        assert DiscoveredProduct.objects.count() == initial_count

        # Should have 2 awards now
        awards = ProductAward.objects.filter(product=product_1)
        assert awards.count() == 2

        competitions = set(a.competition for a in awards)
        assert competitions == {"IWSC", "SFWSC"}

    def test_duplicate_skeleton_detection_by_name(self):
        """Test that duplicate skeletons are detected by name match."""
        manager = SkeletonProductManager()

        # Create first product via direct save (not skeleton)
        existing = save_discovered_product(
            extracted_data={"name": "Lagavulin 16", "brand": "Lagavulin"},
            source_url="https://example.com/lagavulin",
            product_type="whiskey",
            discovery_source="search",
        )
        existing.product.status = DiscoveredProductStatus.APPROVED
        existing.product.save()

        initial_count = DiscoveredProduct.objects.count()

        # Try to create skeleton with same name
        award_data = {
            "product_name": "Lagavulin 16",  # Same name!
            "producer": "Lagavulin",
            "competition": "WWA",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        }

        product = manager.create_skeleton_product(award_data)

        # Should return existing product, not create duplicate
        assert product.id == existing.product.id
        assert DiscoveredProduct.objects.count() == initial_count

        # Award should be added to existing product
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() >= 1

    def test_skeleton_enrichment_updates_product(self):
        """Test that skeleton enrichment updates product with full data."""
        manager = SkeletonProductManager()

        # Create skeleton
        award_data = {
            "product_name": "Talisker 10",
            "producer": "Talisker",
            "competition": "IWSC",
            "year": 2024,
            "medal": "silver",  # Valid medal type
        }
        skeleton = manager.create_skeleton_product(award_data)
        assert skeleton.status == DiscoveredProductStatus.SKELETON
        assert skeleton.abv is None  # No ABV yet

        # Enrich skeleton
        enriched_data = {
            "name": "Talisker 10 Year Old",
            "brand": "Talisker",
            "abv": 45.8,
            "age_statement": 10,
            "volume_ml": 700,
            "region": "Isle of Skye",
            "country": "Scotland",
            "nose_description": "Smoke, sea salt, citrus",
        }

        enriched = manager.mark_skeleton_enriched(
            skeleton=skeleton,
            enriched_data=enriched_data,
            source_url="https://example.com/talisker",
        )

        # Verify enrichment
        assert enriched.status == DiscoveredProductStatus.PENDING
        # ABV may be stored as float or Decimal depending on implementation
        assert float(enriched.abv) == 45.8
        assert enriched.age_statement == 10
        assert enriched.source_url == "https://example.com/talisker"


# =============================================================================
# Discovery Flow E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestDiscoveryFlowE2E:
    """End-to-end tests for discovery flow."""

    def test_product_save_creates_all_related_records(self, sample_whiskey_data):
        """Test that save_discovered_product creates all related records."""
        result = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://masterofmalt.com/macallan-18",
            product_type="whiskey",
            discovery_source="search",
        )

        product = result.product

        # Verify product created with individual columns
        assert product.name == "Macallan 18 Year Old Sherry Oak"
        assert float(product.abv) == 43.0
        assert product.age_statement == 18
        assert product.region == "Speyside"

        # Verify brand created
        assert result.brand_created or result.brand is not None
        assert product.brand.name == "The Macallan"

        # Verify WhiskeyDetails created
        assert result.whiskey_details_created
        whiskey_details = WhiskeyDetails.objects.filter(product=product).first()
        assert whiskey_details is not None

        # Verify awards created
        assert result.awards_created >= 1
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() >= 1

        # Verify ratings created
        assert result.ratings_created >= 1
        ratings = ProductRating.objects.filter(product=product)
        assert ratings.count() >= 1

        # Verify images created
        assert result.images_created >= 1
        images = ProductImage.objects.filter(product=product)
        assert images.count() >= 1

    def test_port_wine_creates_port_wine_details(self, sample_port_data):
        """Test that port wine products get PortWineDetails."""
        result = save_discovered_product(
            extracted_data=sample_port_data,
            source_url="https://wine.com/taylors-2017",
            product_type="port_wine",
            discovery_source="search",
        )

        # Verify PortWineDetails created
        assert result.port_wine_details_created
        port_details = PortWineDetails.objects.filter(product=result.product).first()
        assert port_details is not None

    def test_duplicate_detection_by_fingerprint(self, sample_whiskey_data):
        """Test that duplicates are detected by fingerprint."""
        # Create first product
        result_1 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://source1.com/macallan",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        initial_count = DiscoveredProduct.objects.count()

        # Try to create duplicate with same data
        result_2 = save_discovered_product(
            extracted_data=sample_whiskey_data,
            source_url="https://source2.com/macallan",  # Different URL
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should return same product
        assert result_2.product.id == result_1.product.id
        assert result_2.created is False
        assert DiscoveredProduct.objects.count() == initial_count

    def test_duplicate_detection_by_name(self):
        """Test that duplicates are detected by name match."""
        # Create first product
        result_1 = save_discovered_product(
            extracted_data={"name": "Glenlivet 12", "brand": "Glenlivet"},
            source_url="https://source1.com/glenlivet",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        initial_count = DiscoveredProduct.objects.count()

        # Try to create with same name but different other data
        result_2 = save_discovered_product(
            extracted_data={
                "name": "Glenlivet 12",  # Same name
                "brand": "The Glenlivet",  # Slightly different brand
                "abv": 40.0,  # Additional data
            },
            source_url="https://source2.com/glenlivet",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should return same product, updated with new data
        assert result_2.product.id == result_1.product.id
        assert result_2.created is False
        assert DiscoveredProduct.objects.count() == initial_count

        # ABV should be updated (was None, now 40.0)
        result_2.product.refresh_from_db()
        assert float(result_2.product.abv) == 40.0


# =============================================================================
# Cross-Flow Duplicate Detection E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestCrossFlowDuplicateDetection:
    """Test duplicate detection across different flows."""

    def test_skeleton_detects_discovery_product(self):
        """Test that skeleton creation finds products from discovery flow."""
        # Create product via discovery flow
        discovery_result = save_discovered_product(
            extracted_data={
                "name": "Bowmore 12",
                "brand": "Bowmore",
                "abv": 40.0,
            },
            source_url="https://discovery.com/bowmore",
            product_type="whiskey",
            discovery_source="search",
        )
        discovery_result.product.status = DiscoveredProductStatus.APPROVED
        discovery_result.product.save()

        initial_count = DiscoveredProduct.objects.count()

        # Try to create skeleton for same product
        manager = SkeletonProductManager()
        award_data = {
            "product_name": "Bowmore 12",
            "producer": "Bowmore",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        }

        skeleton = manager.create_skeleton_product(award_data)

        # Should find existing product, not create duplicate
        assert skeleton.id == discovery_result.product.id
        assert DiscoveredProduct.objects.count() == initial_count

        # Award should be added
        awards = ProductAward.objects.filter(product=skeleton)
        assert awards.filter(competition="IWSC").exists()

    def test_discovery_detects_skeleton_product(self):
        """Test that discovery flow finds skeleton products."""
        # Create skeleton
        manager = SkeletonProductManager()
        award_data = {
            "product_name": "Laphroaig 10",
            "producer": "Laphroaig",
            "competition": "WWA",
            "year": 2024,
            "medal": "best_in_class",  # Valid medal type
        }
        skeleton = manager.create_skeleton_product(award_data)

        initial_count = DiscoveredProduct.objects.count()

        # Try to create same product via discovery
        discovery_result = save_discovered_product(
            extracted_data={
                "name": "Laphroaig 10",  # Same name
                "brand": "Laphroaig",
                "abv": 40.0,
                "age_statement": 10,
            },
            source_url="https://discovery.com/laphroaig",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should find existing skeleton, not create duplicate
        assert discovery_result.product.id == skeleton.id
        assert discovery_result.created is False
        assert DiscoveredProduct.objects.count() == initial_count

        # Should enrich the skeleton
        discovery_result.product.refresh_from_db()
        assert float(discovery_result.product.abv) == 40.0

    def test_multiple_flows_same_product(self):
        """Test that product found in multiple flows is not duplicated."""
        # Create via competition
        manager = SkeletonProductManager()
        skeleton = manager.create_skeleton_product({
            "product_name": "Highland Park 18",
            "producer": "Highland Park",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        })

        # Add award from different competition
        manager.create_skeleton_product({
            "product_name": "Highland Park 18",
            "producer": "Highland Park",
            "competition": "WWA",
            "year": 2024,
            "medal": "category_winner",  # Valid medal type
        })

        # Add via discovery flow
        discovery_result = save_discovered_product(
            extracted_data={
                "name": "Highland Park 18",
                "brand": "Highland Park",
                "abv": 43.0,
                "age_statement": 18,
            },
            source_url="https://discovery.com/highland-park",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should all be the same product
        assert discovery_result.product.id == skeleton.id

        # Should have 1 product with 2 awards
        assert DiscoveredProduct.objects.filter(
            name__icontains="Highland Park 18"
        ).count() == 1

        awards = ProductAward.objects.filter(product=skeleton)
        assert awards.count() == 2


# =============================================================================
# CrawledSource Caching E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestCrawledSourceCachingE2E:
    """Test CrawledSource caching behavior."""

    def test_cache_check_before_crawling(self, mock_scrapingbee_client, mock_ai_client):
        """Test that cached content is used instead of re-crawling."""
        url = "https://cached.com/product"
        cached_content = "<html><body>Cached product content</body></html>"

        # Create cached CrawledSource
        CrawledSource.objects.create(
            url=url,
            title="Cached Product",
            raw_content=cached_content,
            content_hash=hashlib.sha256(cached_content.encode()).hexdigest(),
            extraction_status="processed",
        )

        # Create SmartCrawler
        crawler = SmartCrawler(mock_scrapingbee_client, mock_ai_client)

        # Try extraction
        result = crawler._try_extraction(url, "whiskey")

        # ScrapingBee should NOT be called (using cache)
        mock_scrapingbee_client.fetch_page.assert_not_called()

        # AI client should be called with cached content
        mock_ai_client.enhance_from_crawler.assert_called_once()

    def test_saves_to_cache_after_crawl(self, mock_scrapingbee_client, mock_ai_client):
        """Test that crawled content is saved to cache."""
        url = "https://newurl.com/product"

        # Verify no cache exists
        assert not CrawledSource.objects.filter(url=url).exists()

        # Create SmartCrawler and crawl
        crawler = SmartCrawler(mock_scrapingbee_client, mock_ai_client)
        result = crawler._try_extraction(url, "whiskey")

        # Should have called ScrapingBee
        mock_scrapingbee_client.fetch_page.assert_called_once()

        # Should have saved to cache
        cached = CrawledSource.objects.filter(url=url).first()
        assert cached is not None
        assert cached.raw_content is not None

    def test_recrawls_if_cache_failed(self, mock_scrapingbee_client, mock_ai_client):
        """Test that failed extractions are re-crawled."""
        url = "https://failed.com/product"

        # Create failed CrawledSource
        CrawledSource.objects.create(
            url=url,
            title="Failed Product",
            raw_content="",
            content_hash="",
            extraction_status="failed",
        )

        # Create SmartCrawler and try extraction
        crawler = SmartCrawler(mock_scrapingbee_client, mock_ai_client)
        result = crawler._try_extraction(url, "whiskey")

        # Should call ScrapingBee (not using failed cache)
        mock_scrapingbee_client.fetch_page.assert_called_once()


# =============================================================================
# URL Frontier Persistence E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestURLFrontierPersistenceE2E:
    """Test URL frontier persistence with database fallback."""

    def test_skips_url_in_crawled_source(self):
        """Test that URLs in CrawledSource are not re-queued."""
        from crawler.queue.url_frontier import URLFrontier

        url = "https://already-crawled.com/product"

        # Create CrawledSource
        CrawledSource.objects.create(
            url=url,
            title="Already Crawled",
            raw_content="Some content",
            content_hash="abc123",
            extraction_status="processed",
        )

        # Create frontier with mock Redis
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False  # Not in Redis

        frontier = URLFrontier(redis_client=mock_redis)

        # Try to add URL
        added = frontier.add_url("test-queue", url)

        # Should not be added (found in CrawledSource)
        assert added is False

    def test_skips_url_in_discovered_product(self):
        """Test that URLs in DiscoveredProduct are not re-queued."""
        from crawler.queue.url_frontier import URLFrontier

        url = "https://product-exists.com/item"

        # Create DiscoveredProduct with this URL
        save_discovered_product(
            extracted_data={"name": "Test Product"},
            source_url=url,
            product_type="whiskey",
            discovery_source="test",
        )

        # Create frontier with mock Redis
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        frontier = URLFrontier(redis_client=mock_redis)

        # Try to add URL
        added = frontier.add_url("test-queue", url)

        # Should not be added (found in DiscoveredProduct)
        assert added is False

    def test_adds_truly_new_url(self):
        """Test that truly new URLs are added to queue."""
        from crawler.queue.url_frontier import URLFrontier

        url = "https://brand-new.com/product"

        # Verify nothing exists
        assert not CrawledSource.objects.filter(url=url).exists()
        assert not DiscoveredProduct.objects.filter(source_url=url).exists()

        # Create frontier with mock Redis
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        frontier = URLFrontier(redis_client=mock_redis)

        # Add URL
        added = frontier.add_url("test-queue", url)

        # Should be added
        assert added is True
        mock_redis.zadd.assert_called()


# =============================================================================
# Multi-Source Enrichment E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestMultiSourceEnrichmentE2E:
    """Test multi-source enrichment functionality."""

    def test_multi_source_extraction(self):
        """Test extraction from multiple sources."""
        # Mock clients
        mock_scrapingbee = Mock()
        mock_scrapingbee.fetch_page = Mock(return_value={
            "success": True,
            "content": "<html>Product page</html>",
        })

        # Different data from different sources
        source_data = [
            {  # Source 1
                "extracted_data": {
                    "name": "Bunnahabhain 12",
                    "brand": "Bunnahabhain",
                    "abv": 46.3,
                },
                "product_type": "whiskey",
                "confidence": 0.9,
            },
            {  # Source 2 - has tasting notes
                "extracted_data": {
                    "name": "Bunnahabhain 12",
                    "brand": "Bunnahabhain",
                    "nose_description": "Honey, nuts, gentle smoke",
                },
                "product_type": "whiskey",
                "confidence": 0.85,
            },
            {  # Source 3 - has images
                "extracted_data": {
                    "name": "Bunnahabhain 12",
                    "brand": "Bunnahabhain",
                    "images": [{"url": "https://img.com/bunna.jpg", "type": "bottle"}],
                },
                "product_type": "whiskey",
                "confidence": 0.88,
            },
        ]

        call_count = [0]
        def mock_enhance(*args, **kwargs):
            result = {"success": True, "data": source_data[call_count[0]]}
            call_count[0] = min(call_count[0] + 1, 2)
            return result

        mock_ai = Mock()
        mock_ai.enhance_from_crawler = Mock(side_effect=mock_enhance)

        # Create SmartCrawler
        crawler = SmartCrawler(mock_scrapingbee, mock_ai)

        # Mock SerpAPI search
        with patch.object(crawler, '_search_product', return_value=[
            "https://source1.com/bunna",
            "https://source2.com/bunna",
            "https://source3.com/bunna",
        ]):
            result = crawler.extract_product_multi_source(
                expected_name="Bunnahabhain 12",
                product_type="whiskey",
                max_sources=3,
            )

        # Should succeed with merged data
        assert result.success
        assert result.source_type == "multi_source"

        # Merged data should have all fields
        merged = result.data["extracted_data"]
        assert merged["name"] == "Bunnahabhain 12"
        assert merged["abv"] == 46.3
        assert merged.get("nose_description") == "Honey, nuts, gentle smoke"
        assert len(merged.get("images", [])) >= 1

    def test_conflict_detection(self):
        """Test that conflicts between sources are detected."""
        mock_scrapingbee = Mock()
        mock_scrapingbee.fetch_page = Mock(return_value={
            "success": True,
            "content": "<html>Product page</html>",
        })

        # Conflicting ABV values
        source_data = [
            {
                "extracted_data": {"name": "Test Whisky", "abv": 40.0},
                "product_type": "whiskey",
                "confidence": 0.9,
            },
            {
                "extracted_data": {"name": "Test Whisky", "abv": 43.0},  # Different!
                "product_type": "whiskey",
                "confidence": 0.9,
            },
        ]

        call_count = [0]
        def mock_enhance(*args, **kwargs):
            result = {"success": True, "data": source_data[call_count[0]]}
            call_count[0] = min(call_count[0] + 1, 1)
            return result

        mock_ai = Mock()
        mock_ai.enhance_from_crawler = Mock(side_effect=mock_enhance)

        crawler = SmartCrawler(mock_scrapingbee, mock_ai)

        with patch.object(crawler, '_search_product', return_value=[
            "https://source1.com/test",
            "https://source2.com/test",
        ]):
            result = crawler.extract_product_multi_source(
                expected_name="Test Whisky",
                product_type="whiskey",
                max_sources=2,
            )

        # Should detect conflict and flag for review
        assert result.success
        assert result.needs_review is True
        assert any("abv" in r.lower() for r in result.review_reasons)


# =============================================================================
# Full Integration E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestFullIntegrationE2E:
    """Full integration tests combining all flows."""

    def test_complete_competition_to_discovery_flow(self):
        """Test complete flow from competition skeleton to discovery enrichment."""
        # Phase 1: Create skeleton from competition
        manager = SkeletonProductManager()
        skeleton = manager.create_skeleton_product({
            "product_name": "Caol Ila 12",
            "producer": "Caol Ila",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        })

        assert skeleton.status == DiscoveredProductStatus.SKELETON
        assert skeleton.abv is None

        # Phase 2: Add award from another competition
        manager.create_skeleton_product({
            "product_name": "Caol Ila 12",
            "producer": "Caol Ila",
            "competition": "WWA",
            "year": 2024,
            "medal": "best_in_class",  # Valid medal type
        })

        awards = ProductAward.objects.filter(product=skeleton)
        assert awards.count() == 2

        # Phase 3: Enrich via discovery
        enriched = save_discovered_product(
            extracted_data={
                "name": "Caol Ila 12",
                "brand": "Caol Ila",
                "abv": 43.0,
                "age_statement": 12,
                "region": "Islay",
                "country": "Scotland",
                "nose_description": "Smoke, citrus, honey",
                "palate_flavors": ["smoke", "lemon", "malt"],
                "ratings": [
                    {"source": "Whisky Bible", "score": 88, "max_score": 100},
                ],
            },
            source_url="https://retailer.com/caol-ila-12",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should enrich existing skeleton
        assert enriched.product.id == skeleton.id
        assert enriched.created is False

        # Verify enrichment
        enriched.product.refresh_from_db()
        assert float(enriched.product.abv) == 43.0
        assert enriched.product.region == "Islay"
        assert enriched.product.nose_description == "Smoke, citrus, honey"

        # Awards preserved
        awards = ProductAward.objects.filter(product=skeleton)
        assert awards.count() == 2

        # New rating added
        ratings = ProductRating.objects.filter(product=skeleton)
        assert ratings.count() >= 1

    def test_no_duplicates_across_multiple_operations(self):
        """Test that no duplicates are created across many operations."""
        product_name = "Oban 14"

        # Operation 1: Competition skeleton
        manager = SkeletonProductManager()
        skeleton = manager.create_skeleton_product({
            "product_name": product_name,
            "producer": "Oban",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        })

        # Operation 2: Same competition, re-crawled
        manager.create_skeleton_product({
            "product_name": product_name,
            "producer": "Oban",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Same award
        })

        # Operation 3: Different competition
        manager.create_skeleton_product({
            "product_name": product_name,
            "producer": "Oban",
            "competition": "WWA",
            "year": 2024,
            "medal": "category_winner",  # Valid medal type
        })

        # Operation 4: Discovery flow
        save_discovered_product(
            extracted_data={"name": product_name, "brand": "Oban", "abv": 43.0},
            source_url="https://source1.com/oban",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Operation 5: Another discovery from different source
        save_discovered_product(
            extracted_data={"name": product_name, "brand": "Oban Distillery"},
            source_url="https://source2.com/oban14",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Verify: Should have exactly 1 product
        products = DiscoveredProduct.objects.filter(
            Q(name__icontains="Oban 14") | Q(name__iexact=product_name)
        )
        assert products.count() == 1

        # Should have 2 awards (IWSC duplicate not added, WWA added)
        awards = ProductAward.objects.filter(product=skeleton)
        assert awards.count() == 2

        # Competitions should be IWSC and WWA
        competitions = set(a.competition for a in awards)
        assert competitions == {"IWSC", "WWA"}


# =============================================================================
# Edge Cases E2E Tests
# =============================================================================

@pytest.mark.django_db
class TestEdgeCasesE2E:
    """Test edge cases and error handling."""

    def test_handles_missing_name(self):
        """Test handling of products with missing name."""
        result = save_discovered_product(
            extracted_data={"brand": "Some Brand", "abv": 40.0},  # No name!
            source_url="https://example.com/no-name",
            product_type="whiskey",
            discovery_source="test",
        )

        # Should still create product, possibly with empty name
        assert result.product is not None

    def test_handles_duplicate_awards(self):
        """Test that duplicate awards are not created."""
        manager = SkeletonProductManager()

        award_data = {
            "product_name": "Test Whisky",
            "producer": "Test",
            "competition": "IWSC",
            "year": 2024,
            "medal": "gold",  # Valid medal type
        }

        # Create skeleton
        product = manager.create_skeleton_product(award_data)

        # Try to add same award again
        manager.create_skeleton_product(award_data)
        manager.create_skeleton_product(award_data)

        # Should only have 1 award
        awards = ProductAward.objects.filter(product=product)
        assert awards.count() == 1

    def test_handles_name_variations(self):
        """Test handling of product name variations."""
        # Create product with one name
        result_1 = save_discovered_product(
            extracted_data={"name": "Glenfarclas 15", "brand": "Glenfarclas"},
            source_url="https://source1.com/glenfarclas",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Same product with slight variation
        result_2 = save_discovered_product(
            extracted_data={"name": "GLENFARCLAS 15", "brand": "Glenfarclas"},  # Uppercase
            source_url="https://source2.com/glenfarclas",
            product_type="whiskey",
            discovery_source="search",
            check_existing=True,
        )

        # Should detect as same product (case-insensitive)
        assert result_2.product.id == result_1.product.id

    def test_handles_unicode_names(self):
        """Test handling of unicode in product names."""
        result = save_discovered_product(
            extracted_data={
                "name": "Château Pétrus 2010",
                "brand": "Pétrus",
            },
            source_url="https://example.com/petrus",
            product_type="port_wine",
            discovery_source="test",
        )

        assert result.product is not None
        assert "Pétrus" in result.product.name or "Petrus" in result.product.name
