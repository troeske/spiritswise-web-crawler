"""
Integration Tests for Product Saver with ContentProcessor.

UNIFIED_PRODUCT_SAVE_REFACTORING - Phase 2: Integration Tests

These tests verify that ContentProcessor correctly uses the unified
save_discovered_product() function from product_saver.py.

Test Coverage:
1. ContentProcessor.process() correctly calls save_discovered_product()
2. Products are created with individual columns populated
3. WhiskeyDetails are created for whiskey products
4. PortWineDetails are created for port wine products
5. ProductAward, ProductRating, ProductImage records are created
6. ProductSource and ProductFieldSource records are created
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
from asgiref.sync import sync_to_async

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    CrawledSource,
    DiscoveredProduct,
    DiscoveredProductStatus,
    DiscoverySource,
    ProductType,
    SourceCategory,
    WhiskeyDetails,
    PortWineDetails,
    ProductAward,
    ProductRating,
    ProductImage,
    ProductSource,
    ProductFieldSource,
    DiscoveredBrand,
    MedalChoices,
    ImageTypeChoices,
    CrawledSourceTypeChoices,
    ExtractionStatusChoices,
    DiscoverySourceConfig,
    SourceTypeChoices,
    CrawlFrequencyChoices,
    CrawlStrategyChoices,
)
from crawler.services.content_processor import ContentProcessor, ProcessingResult
from crawler.services.ai_client import EnhancementResult


# =============================================================================
# Async Database Helpers
# =============================================================================


@sync_to_async
def get_product_by_id(product_id):
    """Get product by ID - wrapped for async context."""
    return DiscoveredProduct.objects.get(id=product_id)


@sync_to_async
def get_product_awards(product):
    """Get product awards - wrapped for async context."""
    return list(ProductAward.objects.filter(product=product))


@sync_to_async
def get_product_sources_with_related(product):
    """Get product sources with source FK eagerly loaded - wrapped for async context."""
    return list(ProductSource.objects.filter(product=product).select_related("source"))


@sync_to_async
def get_product_field_sources(product):
    """Get product field sources - wrapped for async context."""
    return list(ProductFieldSource.objects.filter(product=product))


@sync_to_async
def get_field_source_by_name_with_related(product, field_name):
    """Get field source by name with source FK eagerly loaded - wrapped for async context."""
    return ProductFieldSource.objects.filter(product=product, field_name=field_name).select_related("source").first()


@sync_to_async
def create_second_crawled_source(discovery_source):
    """Create second crawled source - wrapped for async context."""
    return CrawledSource.objects.create(
        url="https://another-site.com/products/glenfiddich-18",
        title="Another Source",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        extraction_status=ExtractionStatusChoices.PENDING,
        discovery_source=discovery_source,
    )


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for testing."""
    return CrawlerSource.objects.create(
        name="Test Integration Source",
        slug="test-integration-source",
        base_url="https://example.com",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey", "port_wine"],
    )


@pytest.fixture
def sample_discovery_source_config(db):
    """Create a sample DiscoverySourceConfig for testing."""
    return DiscoverySourceConfig.objects.create(
        name="Test Integration Discovery Source",
        base_url="https://awards.example.com",
        source_type=SourceTypeChoices.AWARD_COMPETITION,
        crawl_frequency=CrawlFrequencyChoices.WEEKLY,
        crawl_strategy=CrawlStrategyChoices.SIMPLE,
        crawl_priority=5,
        reliability_score=8,
    )


@pytest.fixture
def sample_crawled_source(db, sample_discovery_source_config):
    """Create a sample CrawledSource for testing."""
    return CrawledSource.objects.create(
        url="https://example.com/products/test-whiskey-integration",
        title="Test Whiskey Integration Page",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        extraction_status=ExtractionStatusChoices.PENDING,
        discovery_source=sample_discovery_source_config,
    )


@pytest.fixture
def sample_crawl_job(db, sample_crawler_source):
    """Create a sample CrawlJob for testing."""
    return CrawlJob.objects.create(
        source=sample_crawler_source,
    )


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client that returns whiskey data."""
    client = MagicMock()
    return client


@pytest.fixture
def whiskey_enhancement_result():
    """Create an EnhancementResult for whiskey product."""
    return EnhancementResult(
        success=True,
        extracted_data={
            "name": "Glenfiddich 18 Year Old",
            "brand": "Glenfiddich",
            "abv": "43.0",
            "age_statement": "18",
            "volume_ml": "700",
            "region": "Speyside",
            "country": "Scotland",
            "gtin": "5010327325125",
            # Tasting profile
            "color_description": "Deep amber with golden highlights",
            "color_intensity": "7",
            "clarity": "brilliant",
            "viscosity": "medium",
            "nose_description": "Rich oak with hints of dried fruit",
            "primary_aromas": ["oak", "honey", "dried fruit"],
            "primary_intensity": "8",
            "palate_flavors": ["toffee", "cinnamon", "dark chocolate"],
            "initial_taste": "Sweet honey and toffee",
            "finish_length": "8",
            "warmth": "6",
            "dryness": "4",
            # Whiskey-specific
            "whiskey_type": "scotch_single_malt",
            "whiskey_country": "Scotland",
            "whiskey_region": "Speyside",
            "distillery": "Glenfiddich Distillery",
            "cask_type": "ex-bourbon",
            "cask_finish": "sherry",
            # Awards
            "awards": [
                {
                    "competition": "IWSC",
                    "competition_country": "UK",
                    "year": 2024,
                    "medal": "gold",
                    "category": "Single Malt Scotch",
                }
            ],
            # Ratings
            "ratings": [
                {
                    "source": "Whisky Advocate",
                    "score": 92,
                    "max_score": 100,
                    "reviewer": "John Reviewer",
                }
            ],
            # Images
            "images": [
                {
                    "url": "https://example.com/images/glenfiddich18.jpg",
                    "image_type": "bottle",
                    "source": "Official Website",
                }
            ],
        },
        product_type="whiskey",
        confidence=0.92,
        enrichment={},
        field_confidences={
            "name": 0.95,
            "abv": 0.90,
            "age_statement": 0.88,
            "region": 0.85,
        },
    )


@pytest.fixture
def port_wine_enhancement_result():
    """Create an EnhancementResult for port wine product."""
    return EnhancementResult(
        success=True,
        extracted_data={
            "name": "Taylor's 20 Year Old Tawny",
            "brand": "Taylor's",
            "abv": "20.0",
            "volume_ml": "750",
            "region": "Douro",
            "country": "Portugal",
            # Tasting profile
            "color_description": "Rich amber with mahogany rim",
            "nose_description": "Dried fruits, nuts, and caramel",
            "palate_flavors": ["walnut", "fig", "honey"],
            "finish_length": "9",
            # Port-specific
            "style": "tawny",
            "indication_age": "20 Year",
            "producer_house": "Taylor's",
        },
        product_type="port_wine",
        confidence=0.88,
        enrichment={},
        field_confidences={
            "name": 0.92,
            "abv": 0.88,
            "style": 0.90,
        },
    )


# =============================================================================
# Integration Tests: ContentProcessor calls save_discovered_product()
# Using transaction=True to avoid SQLite database locking issues with async
# =============================================================================


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestContentProcessorIntegration:
    """Integration tests for ContentProcessor using save_discovered_product."""

    async def test_process_creates_product_with_individual_columns(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates product with individual columns populated."""
        # Setup mock AI client
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        # Process content
        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test content</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        # Verify result
        assert result.success is True
        assert result.product_id is not None
        assert result.is_new is True

        # Verify product has individual columns populated
        product = await get_product_by_id(result.product_id)
        assert product.name == "Glenfiddich 18 Year Old"
        assert product.abv == 43.0
        assert product.age_statement == 18
        assert product.volume_ml == 700
        assert product.region == "Speyside"
        assert product.country == "Scotland"

    async def test_process_creates_whiskey_details(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates WhiskeyDetails for whiskey products."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test whiskey</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True
        assert result.whiskey_details_created is True

        # Verify WhiskeyDetails record
        @sync_to_async
        def get_whiskey_details():
            product = DiscoveredProduct.objects.get(id=result.product_id)
            return product.whiskey_details

        details = await get_whiskey_details()

        assert details.whiskey_type == "scotch_single_malt"
        assert details.whiskey_country == "Scotland"
        assert details.whiskey_region == "Speyside"
        assert details.distillery == "Glenfiddich Distillery"

    async def test_process_creates_port_wine_details(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        port_wine_enhancement_result,
    ):
        """ContentProcessor.process() creates PortWineDetails for port wine products."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=port_wine_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/taylors-20",
            raw_content="<html><body>Test port wine</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True
        assert result.port_wine_details_created is True

        # Verify PortWineDetails record
        @sync_to_async
        def get_port_details():
            product = DiscoveredProduct.objects.get(id=result.product_id)
            return product.port_details

        details = await get_port_details()

        assert details.style == "tawny"
        assert details.indication_age == "20 Year"
        assert details.producer_house == "Taylor's"

    async def test_process_creates_product_awards(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates ProductAward records."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test awards</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True
        assert result.awards_created >= 1

        # Verify ProductAward record
        product = await get_product_by_id(result.product_id)
        awards = await get_product_awards(product)
        assert len(awards) >= 1

        award = awards[0]
        assert award.competition == "IWSC"
        assert award.year == 2024
        assert award.medal == MedalChoices.GOLD

    async def test_process_creates_product_source_junction(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates ProductSource junction record."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test source</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True
        assert result.product_source_created is True

        # Verify ProductSource junction (use select_related to eager load source)
        product = await get_product_by_id(result.product_id)
        product_sources = await get_product_sources_with_related(product)
        assert len(product_sources) == 1

        ps = product_sources[0]
        # Access source_id instead of source to avoid lazy loading
        assert ps.source_id == sample_crawled_source.id

    async def test_process_creates_field_provenance_records(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates ProductFieldSource provenance records."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test provenance</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True
        assert result.provenance_records_created > 0

        # Verify ProductFieldSource records
        product = await get_product_by_id(result.product_id)
        field_sources = await get_product_field_sources(product)
        assert len(field_sources) > 0

        # Check specific field provenance (use select_related to eager load source)
        name_source = await get_field_source_by_name_with_related(product, "name")
        assert name_source is not None
        # Access source_id instead of source to avoid lazy loading
        assert name_source.source_id == sample_crawled_source.id

    async def test_process_creates_brand(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() creates or links DiscoveredBrand."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test brand</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True

        # Verify brand is linked to product
        @sync_to_async
        def get_product_with_brand():
            product = DiscoveredProduct.objects.select_related("brand").get(id=result.product_id)
            return product, product.brand

        product, brand = await get_product_with_brand()
        assert brand is not None
        assert brand.name == "Glenfiddich"

    async def test_process_populates_tasting_profile(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() populates tasting profile columns."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test tasting</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result.success is True

        # Verify tasting profile columns
        product = await get_product_by_id(result.product_id)
        assert product.color_description == "Deep amber with golden highlights"
        assert product.color_intensity == 7
        assert product.clarity == "brilliant"
        assert product.nose_description == "Rich oak with hints of dried fruit"
        assert product.primary_aromas == ["oak", "honey", "dried fruit"]
        assert product.finish_length == 8

    async def test_process_returns_correct_result_structure(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() returns ProcessingResult with all fields."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test result</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        # Verify result structure
        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.product_id is not None
        assert isinstance(result.is_new, bool)
        assert result.product_type == "whiskey"
        assert result.confidence == 0.92
        assert isinstance(result.awards_created, int)
        assert isinstance(result.product_source_created, bool)
        assert isinstance(result.provenance_records_created, int)
        assert isinstance(result.whiskey_details_created, bool)
        assert isinstance(result.port_wine_details_created, bool)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestContentProcessorExistingProduct:
    """Tests for ContentProcessor handling existing products."""

    async def test_process_updates_existing_product(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
        whiskey_enhancement_result,
    ):
        """ContentProcessor.process() handles existing product correctly."""
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=whiskey_enhancement_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        # Process first time to create product
        result1 = await processor.process(
            url="https://example.com/products/glenfiddich-18",
            raw_content="<html><body>Test content 1</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        assert result1.success is True
        assert result1.is_new is True
        first_product_id = result1.product_id

        # Create another crawled_source for second crawl
        second_crawled_source = await create_second_crawled_source(sample_crawled_source.discovery_source)

        # Process second time - should find existing by fingerprint
        result2 = await processor.process(
            url="https://another-site.com/products/glenfiddich-18",
            raw_content="<html><body>Test content 1</body></html>",  # Same content = same fingerprint
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=second_crawled_source,
        )

        assert result2.success is True
        # Should be same product, not new
        assert result2.product_id == first_product_id
        assert result2.is_new is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestContentProcessorErrorHandling:
    """Tests for ContentProcessor error handling."""

    async def test_process_handles_ai_failure(
        self,
        sample_crawler_source,
        sample_crawl_job,
        sample_crawled_source,
        mock_ai_client,
    ):
        """ContentProcessor.process() handles AI enhancement failure gracefully."""
        # Setup mock to return failure
        failure_result = EnhancementResult(
            success=False,
            extracted_data={},
            product_type="",
            confidence=0.0,
            enrichment={},
            error="AI service unavailable",
        )
        mock_ai_client.enhance_from_crawler = AsyncMock(return_value=failure_result)

        processor = ContentProcessor(ai_client=mock_ai_client)

        result = await processor.process(
            url="https://example.com/products/test-failure",
            raw_content="<html><body>Test content</body></html>",
            source=sample_crawler_source,
            crawl_job=sample_crawl_job,
            crawled_source=sample_crawled_source,
        )

        # Verify failure is handled gracefully
        assert result.success is False
        assert result.error == "AI service unavailable"
        assert result.product_id is None
